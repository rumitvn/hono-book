# Chapter 2 — The App Object & HonoRequest

> **Goal:** Understand the foundational runtime that Chapter 3 builds on — how `new Hono()` is born, how
> `.get()` / `.use()` register routes, how `fetch` dispatches a request, and how `HonoRequest` wraps the
> web `Request`. Grounded in `honojs/hono` at **`v4.12.25`** (`fce483e`).

---

## 2.1 Why it matters

The `Hono` app is the object you touch every day, but its internals are usually invisible. Before we can
understand the router (Chapter 3) or the middleware onion (Chapter 5), we need to know *who calls them and
when*: where routes are stored, what `app.get(...)` actually does, and what the `fetch` entrypoint hands
down to the lower layers. This chapter is the spine the rest of the book hangs on.

---

## 2.2 Two classes: `Hono` and `HonoBase`

Open `src/hono.ts` — it's only 34 lines. The `Hono` class you import does almost nothing itself:

```ts
// src/hono.ts:16
export class Hono<…> extends HonoBase<…> {
  constructor(options: HonoOptions<E> = {}) {
    super(options)
    this.router =
      options.router ??
      new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })  // :28–32
  }
}
```

`Hono`'s entire job is to **choose a default router** (`src/hono.ts:28`). Everything else — registration,
dispatch, error handling — lives in the parent class `HonoBase` (`src/hono-base.ts:98`). This split is
deliberate: the *presets* (`src/preset/tiny.ts`, `src/preset/quick.ts`) are alternate `Hono` subclasses
that pick a different router, reusing all of `HonoBase` unchanged. We'll meet them in Chapter 3.

> 🧠 **Mental model:** `HonoBase` is the engine; `Hono` is a thin trim package that bolts on a router. If
> you ever wondered why there are two classes, this is it — it's the seam that lets the router be swapped.

---

## 2.3 Where routes live

`HonoBase` keeps routes in **two** places (`src/hono-base.ts`):

- `src/hono-base.ts:118` — `router!: Router<[H, RouterRoute]>` — the active router. This is what *matches*
  at request time. (The `!` means a subclass must assign it — which `Hono` does in §2.2.)
- `src/hono-base.ts:124` — `routes: RouterRoute[] = []` — a plain array copy of every registered route,
  used for introspection (e.g. `app.routes`) and for `app.route()` mounting. It is *not* used for matching.

So registration writes to two structures: the router (optimized for matching) and the array (a flat
record). Keep that distinction — the router is the hot path, the array is bookkeeping.

---

## 2.4 Route registration: what `app.get(...)` does

`get`, `post`, etc. are declared as typed fields (`src/hono-base.ts:104`) but **implemented in the
constructor** by a loop (`src/hono-base.ts:128`):

```ts
// src/hono-base.ts:128 — for each HTTP method, install a handler:
this[method] = (args1: string | H, ...args: H[]) => {
  if (typeof args1 === 'string') {
    this.#path = args1            // app.get('/path', handler) — remember the path
  } else {
    this.#addRoute(method, this.#path, args1)   // app.get(handler) — reuse last path
  }
  args.forEach((handler) => {
    this.#addRoute(method, this.#path, handler)  // each handler is its own route entry
  })
  return this as any            // chainable: app.get(...).post(...)
}
```

Two things to notice. First, **multiple handlers register as multiple routes** for the same path — that's
how `app.get('/x', mw1, mw2, finalHandler)` works; each becomes a separately-matched entry. Second, the
method returns `this`, so calls chain.

`use` is the same idea but always registers under `METHOD_NAME_ALL` and defaults the path to `'*'`
(`src/hono-base.ts:156`). That's why `app.use(mw)` (no path) applies to every route.

All of these funnel into the single private method:

```ts
// src/hono-base.ts:385
#addRoute(method, path, handler, baseRoutePath?) {
  method = method.toUpperCase()
  path = mergePath(this._basePath, path)
  const r: RouterRoute = { basePath: …, path, method, handler }
  this.router.add(method, path, [handler, r])   // :395 → hand to the router
  this.routes.push(r)                            // :396 → bookkeeping array
}
```

> 📌 The handler stored in the router is the **tuple** `[handler, r]` (`:395`), not the bare handler. The
> router carries that opaque payload through matching and hands it back untouched — the router never knows
> what a "handler" is. This is why the `Router<T>` interface is generic in `T`; we'll see that in Chapter 3.

There's also `app.route(path, subApp)` (`src/hono-base.ts:208`) for mounting one Hono app under another,
`onError` (`src/hono-base.ts:271`), and `notFound` (`src/hono-base.ts:291`) — we'll use those in Chapters 5
and 8.

---

## 2.5 Dispatch: what `fetch` does

```text
fetch(request, env, ctx)              src/hono-base.ts:479
   │
   └─► #dispatch(request, ctx, env, method)        :406
          ├─ HEAD? re-dispatch as GET, body stripped      :413
          ├─ path   = this.getPath(request)               :418
          ├─ match  = this.router.match(method, path)     :419   ◄── Router (Ch 3)
          ├─ c      = new Context(request, {…match…})      :421   ◄── Context (Ch 4)
          ├─ 1 handler?  call it directly (fast path)      :430
          └─ N handlers? compose(...)(c) (onion path)      :450   ◄── Compose (Ch 5)
```

The entrypoint is tiny (`src/hono-base.ts:479`): `fetch` just forwards to the private `#dispatch`. The
real work is `#dispatch` (`src/hono-base.ts:406`):

- **HEAD handling** (`:413`) — a `HEAD` request is re-dispatched as `GET` and its body discarded. Hono
  never makes you write a separate HEAD handler.
- **Path extraction** (`:418`) — `this.getPath(request, { env })`. By default this is `getPath` from
  `src/utils/url.ts:106`, wired up at `src/hono-base.ts:172` (or `getPathNoStrict` when `strict: false`).
- **Matching** (`:419`) — `this.router.match(method, path)` returns `[handlers, paramStash]`. This is the
  Router layer; Chapter 3.
- **Context creation** (`:421`) — `new Context(request, { path, matchResult, env, executionCtx,
  notFoundHandler })`. The match result is handed to the Context so `c.req.param()` can resolve later.
- **Fast vs onion** (`:430` / `:450`) — covered in §1.4 and detailed in Chapter 5.

> 💡 **Tip:** there's a second entrypoint, `app.request(...)` (`src/hono-base.ts` ~499), that accepts a URL
> string or a `Request` and is meant for **tests** — it lets you call your app without a server. You'll use
> it in this chapter's lab.

---

## 2.6 `HonoRequest`: a wrapper, not a replacement

`c.req` is a `HonoRequest`, not the raw `Request`. Open `src/request.ts:36`:

```ts
export class HonoRequest<P extends string = '/', I … = {}> {
  raw: Request              // :51 — the underlying web Request, always reachable
  path: string              // :68 — the matched pathname
  bodyCache: BodyCache = {} // :69 — caches parsed bodies (one-shot stream!)
  routeIndex: number = 0
}
```

The key idea: `HonoRequest` **wraps** the web `Request` (kept at `.raw`, `src/request.ts:51`) and adds
ergonomics on top. Nothing is hidden — `c.req.raw` is always the real thing.

The methods you use daily:

- `param(key?)` (`src/request.ts:94`) — path params from the router's match. `c.req.param('id')`.
- `query(key?)` (`src/request.ts:148`) — search-string params. `c.req.query('q')`.
- `header(name?)` (`src/request.ts:185`) — request headers.
- `json()` (`src/request.ts:253`) — `this.#cachedBody('text').then(JSON.parse)` — note it goes through the
  **body cache** so a second `c.req.json()` doesn't try to re-read the consumed stream.

> ⚠️ This is the §0.3 gotcha made concrete: a `Request` body is a one-shot stream. `bodyCache`
> (`src/request.ts:69`) is the entire reason you *can* call `c.req.json()` from two different middleware on
> the same request without an exception. Caching the parse result is not an optimization here — it's a
> correctness requirement.

---

## 2.7 Lab 2 — registration and the test entrypoint

In your `hono-hello` project, prove that multiple handlers become multiple routes, and use the test
entrypoint so you don't even need a server:

```ts
// probe.ts
import { Hono } from 'hono'
const app = new Hono()

app.use('*', async (c, next) => { c.header('x-mw', 'ran'); await next() })
app.get('/users/:id', (c) => c.json({ id: c.req.param('id'), q: c.req.query('q') }))

console.log(app.routes)   // ← the bookkeeping array from §2.3

const res = await app.request('/users/42?q=hi')   // ← src/hono-base.ts:499, no server!
console.log(res.status, res.headers.get('x-mw'), await res.json())
```

```bash
bun run probe.ts
```

> 🧪 **Record in `labs/lab2-app.md`:** the contents of `app.routes` (you should see *two* entries for
> `/users/:id` — one `ALL` from the `use('*')` middleware, one `GET`), and the response line. Expected:
> `200 ran {"id":"42","q":"hi"}`. The `x-mw: ran` header proves the middleware route matched the same path
> as the handler — exactly the "multiple handlers, multiple routes" point from §2.4.

---

## 2.8 Checkpoint

1. What is the *only* job of the `Hono` class, and which class does the real work?
2. Routes are stored in two places. Name both and say which one is used for matching.
3. What does the router actually store as its "handler" payload, and why is the `Router<T>` interface
   generic?
4. Trace `app.fetch(req)` to the line that calls the router and the line that creates the `Context`.
5. Why does `HonoRequest` cache the parsed body? What goes wrong without `bodyCache`?

> If #3 is shaky, re-read §2.4. If #5 is shaky, re-read §2.6 (and §0.3).

---

## 🔌 Connect to your past (temlet web→native)

In Next.js, "where do my routes live?" has a non-answer: they live in the *file system*, and the framework
reconstructs a route table you never see. That implicitness is fine until you're migrating — then you're
reverse-engineering the framework's conventions to know what actually got registered.

Hono's `app.routes` array (`src/hono-base.ts:124`) is the opposite: an explicit, inspectable list you can
`console.log`. When you carry temlet toward Tauri and need to audit exactly which endpoints exist and in
what order their middleware runs, an explicit route table is gold. And `app.request(...)` — the
server-less test entrypoint from §2.5 — means you can unit-test that entire API surface without booting
Next, Node, *or* the native shell. That testability is one of the quiet wins of moving the HTTP layer onto
something runtime-agnostic.

**Next:** [Chapter 3 — The Router ★ →](03-the-router.md)
