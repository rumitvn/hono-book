# Chapter 0 — Environment & TypeScript / Web-standards Refresher

> **Goal:** Get a green build of `honojs/hono` at the pinned ref **`v4.12.25`** (commit `fce483e`), and
> refresh the two pillars the whole framework rests on — the **Fetch API** (`Request`/`Response`) and the
> **TypeScript generics & conditional types** that make routes type-safe. By the end you can run a tiny
> Hono app and the upstream test suite locally.

---

## 0.1 Why it matters

Most frameworks invent their own request and response objects. Express has `req`/`res`. Next.js has
`NextRequest`/`NextResponse`. Each one is a different shape, and porting code between them means rewriting
the boundary. Hono made the opposite bet: it uses the **web platform's own `Request` and `Response`** —
the same objects your browser's `fetch()` returns, the same objects a Cloudflare Worker's `fetch` handler
receives. Nothing proprietary at the edges.

That single decision is why one `app` can run on Cloudflare Workers, Bun, Deno, Node, and Lambda without
changing a line. So before we read a single line of routing code, we need the two things Hono assumes you
already know: **what `Request`/`Response` are**, and **how TypeScript's type-level features let a string
path become a typed parameter**. If those are fresh, the rest of the book reads easily.

---

## 0.2 Mental model: a framework that is "just" a fetch handler

Strip everything away and a Hono app is one function with this shape:

```text
        ┌─────────────────────────────────────────────┐
        │   (request: Request) => Response | Promise   │
        │                                              │
  HTTP  │   app.fetch  ───►  router  ───►  handler     │  HTTP
  ─────►│        │             │             │         │─────►
 Request│        └── Context (c) ──── c.json/text/html │ Response
        └─────────────────────────────────────────────┘
```

The runtime (Workers, Bun, …) hands Hono a `Request` and expects a `Response` back. Everything Hono
does — match a route, run middleware, build a body — happens *between* those two web-standard objects.
This is exactly the shape a Cloudflare Worker already has:

```ts
export default {
  fetch(request: Request): Response | Promise<Response> {
    return new Response('hi')
  },
}
```

A Hono `app` *is* that `fetch` function, with a router and middleware bolted on. Hold this picture.

---

## 0.3 Refresher: the Fetch API objects

These are global in every modern runtime. No import needed.

**`Request`** — an immutable view of an incoming HTTP request:

```ts
const req = new Request('https://x.dev/users/42?q=hi', {
  method: 'GET',
  headers: { 'content-type': 'application/json' },
})
req.method            // 'GET'
req.url               // 'https://x.dev/users/42?q=hi'
req.headers.get('content-type')   // 'application/json'
await req.json()      // parses the body once (the body is a stream)
```

> ⚠️ A request/response **body is a one-shot stream**. You can read it *once*. This is why Hono caches the
> parsed body — you'll see `bodyCache` in `src/request.ts:69` in the next chapter. Re-reading a consumed
> body throws.

**`Response`** — what you send back:

```ts
new Response('hello', { status: 200, headers: { 'x-foo': 'bar' } })
Response.json({ ok: true })          // sets content-type for you
new Response(null, { status: 302, headers: { location: '/' } })  // redirect
```

Hono's `c.text()`, `c.json()`, and `c.redirect()` are thin, ergonomic wrappers that ultimately construct
one of these. Keep that in mind — when we read `context.ts`, you'll see there is no magic, just `Response`
construction with sensible defaults.

---

## 0.4 Refresher: the TypeScript features Hono leans on

Hono's headline feature is *type-safe routing*: write `/users/:id` and `c.req.param('id')` is typed as a
string with no annotation. That is built entirely from three TypeScript features. You don't need to master
them, but you should recognize them when Chapter 7 cites `src/types.ts`.

**1. Generics carry type information through a call.**

```ts
function first<T>(arr: T[]): T { return arr[0] }
first([1, 2, 3])         // T inferred as number → returns number
```

The `Hono` class is generic: `class Hono<E extends Env, S extends Schema, BasePath extends string>`
(`src/hono.ts:16`). The `S` type parameter is the *accumulated route schema* — every `.get()` call returns
a new `Hono` with `S` widened to include that route. That's how the `hc` client later knows your routes.

**2. Template-literal types let the compiler read a string.**

```ts
type Greeting = `hello ${string}`     // matches "hello world", not "hi"
```

Hono uses these to parse a path *at the type level*. `ParamKeys<'/users/:id'>` evaluates to `'id'`
(`src/types.ts:2706`). The compiler literally splits the path string on `/` and extracts the `:`-prefixed
segments.

**3. Conditional types branch on a type.**

```ts
type IsString<T> = T extends string ? 'yes' : 'no'
```

`ParamKey` (`src/types.ts` near 2698) uses exactly this pattern — `Component extends `:${infer Name}` ?
Name : never` — to pull the name out of a `:param` segment. The `infer` keyword captures the matched piece.

> 🧠 **Mental model:** Hono's type safety is a tiny compile-time interpreter that runs over your path
> strings. It costs zero bytes at runtime — it's all erased. We'll read the real definitions in Chapter 7;
> for now, just know these three features are the whole toolkit.

---

## 0.5 The public surface

Open `src/index.ts` (53 lines). This is everything `import … from 'hono'` gives you:

- `src/index.ts:17` — `import { Hono } from './hono'`, re-exported at `:53`. The class is the whole runtime API.
- `src/index.ts:22-34` — the public **types**: `Env`, `Handler`, `MiddlewareHandler`, `Next`, `Input`,
  `Schema`, `ToSchema`, `TypedResponse`. These are the type-level vocabulary of the framework.
- `src/index.ts:39` — `export { Context } from './context'` — the `c` object's class.
- `src/index.ts:44` — `HonoRequest` (type only).

> 📁 Note how small this is. Middleware (`hono/cors`), adapters (`hono/cloudflare-workers`), the client
> (`hono/client`), and JSX (`hono/jsx`) are **separate entry points**, not bundled into the core. That
> keeps the base import tiny — a deliberate edge-size optimization we'll revisit in Chapter 6.

---

## 0.6 Lab 0 — green build + first app

The upstream repo uses **Bun** as its primary toolchain (see `.tool-versions`: `bun 1.2.19`, `nodejs
24.7.0`, `deno 2.4.5`). Install Bun if you don't have it (`curl -fsSL https://bun.sh/install | bash`), then:

```bash
# 1. Confirm the pin (read-only clone lives beside the book)
cd ../hono
git log -1 --format='%h %d'        # expect: fce483e (tag: v4.12.25)

# 2. Install dev deps and type-check + run the suite
bun install
bun run test                        # = tsc --noEmit && vitest --run
```

Then build the smallest possible app *outside* the clone (so you never mutate it) — this is the
`hono-hello` artifact you'll reuse in later labs:

```bash
mkdir -p ~/hono-hello && cd ~/hono-hello
bun init -y
bun add hono
```

```ts
// index.ts
import { Hono } from 'hono'

const app = new Hono()
app.get('/', (c) => c.text('Hono!'))
app.get('/users/:id', (c) => c.json({ id: c.req.param('id') }))

export default app
```

```bash
bun run --hot index.ts
# in another shell:
curl localhost:3000/
curl localhost:3000/users/42
```

> 🧪 **Save your numbers** in `labs/lab0-setup.md`: your Bun version, whether `bun run test` is green, and
> the two `curl` outputs. You should see `Hono!` and `{"id":"42"}`. Note that `:id` arrived as a **string** —
> that's the typed param from §0.4 in action.

> 💡 **Tip:** `vitest --run` is fast because Hono is pure TypeScript with no native build step. Compare
> that to the C/C++/Rust books in this series, where "get a green build" meant a compiler toolchain. Here
> the whole framework is source you can read top to bottom in an afternoon.

---

## 0.7 Checkpoint

1. What two web-standard objects sit at Hono's input and output boundary, and why does using them make the
   framework portable?
2. Why must Hono cache a parsed request body instead of re-reading it?
3. What does `ParamKeys<'/posts/:slug'>` evaluate to, and which TypeScript feature makes that possible?
4. Is `hono/cors` part of the core `hono` import? Where do middleware and adapters live?
5. When you hit `/users/42`, what is the runtime *type* of `c.req.param('id')`, and where did that type come from?

> If #3 or #5 is shaky, re-read §0.4. If #1–#2 are shaky, re-read §0.3.

---

## 🔌 Connect to your past (temlet web→native)

You've lived the pain this chapter's "one bet" avoids. In **temlet** on Next.js, your API logic is married
to `NextRequest`/`NextResponse` and the Node/Edge runtime split. The moment you carry temlet toward
**Tauri**, that Node server isn't there anymore — and anything bound to Next's request objects has to be
rewritten for the native side.

Hono's bet is the escape hatch: because it speaks only `Request`/`Response`, the *same* router and handlers
run inside a Worker, a Bun server, or a sidecar process behind a Tauri shell. As you read this book, keep
asking: *which of my temlet API handlers could become runtime-agnostic Hono handlers?* The web→native
migration gets dramatically cheaper when your HTTP layer stops caring what's underneath it.

**Next:** [Chapter 1 — Mental Model & Repo Map →](01-mental-model-and-repo-map.md)
