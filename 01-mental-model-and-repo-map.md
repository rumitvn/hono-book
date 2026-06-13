# Chapter 1 — Mental Model & Repo Map

> **Goal:** Build the five-layer mental model of Hono — **App → Router → compose → Context → Adapter** —
> and trace one real request end-to-end through `honojs/hono` at **`v4.12.25`** (`fce483e`), naming every
> hop by `file:line`. By the end you can point at the exact function that runs at each stage of a request.

---

## 1.1 Why it matters

Hono is small — the core is a few thousand lines of TypeScript — but "small" doesn't mean "obvious." If
you don't have a layer model, the code reads as a tangle of generics and clever regex. With the model,
every file has an obvious home and the request flow becomes a straight line you can follow with your
finger.

The payoff is debugging power. When a request returns the wrong status, or middleware runs in a
surprising order, or a route matches that shouldn't — you'll know *which layer* owns the bug and which
file to open, instead of guessing.

---

## 1.2 The five-layer model

Every Hono request passes through these five layers, top to bottom and back:

```text
   ┌──────────────────────────────────────────────────────────────┐
   │  ADAPTER          src/adapter/*        runtime → Request       │
   │  (Workers, Bun, Deno, Node, Lambda)    Response → runtime      │
   └───────────────┬──────────────────────────────────────────────┘
                   │  app.fetch(request, env, ctx)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  APP            src/hono-base.ts       #dispatch: orchestrate  │
   │                 src/hono.ts            route table + handlers  │
   └───────────────┬──────────────────────────────────────────────┘
                   │  this.router.match(method, path)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  ROUTER ★       src/router/*           path → [handlers, params]│
   │                 (Smart/RegExp/Trie/Linear)                     │
   └───────────────┬──────────────────────────────────────────────┘
                   │  compose(matched handlers)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  COMPOSE        src/compose.ts         middleware onion + next()│
   └───────────────┬──────────────────────────────────────────────┘
                   │  handler(c, next)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  CONTEXT        src/context.ts         c.req / c.json / c.env  │
   │                 src/request.ts         → builds the Response   │
   └──────────────────────────────────────────────────────────────┘
```

- **Adapter** is the only runtime-specific layer. It does almost nothing: receive a `Request`, call
  `app.fetch`, return the `Response`. (Chapter 6.)
- **App** is the orchestrator — it owns the route table and runs the dispatch algorithm. (Chapter 2.)
- **Router** turns a method+path into a list of matching handlers. This is the flagship. (Chapter 3.)
- **Compose** chains those handlers into the middleware onion via `next()`. (Chapter 5.)
- **Context** is the `c` your handler receives, and the response builder. (Chapter 4.)

> 🧠 **Mental model:** the App is a thin conductor. The *interesting* work is delegated: matching to the
> Router, chaining to Compose, response-building to Context. `hono-base.ts` mostly wires these together.

---

## 1.3 Repo map — where everything lives

```text
src/
├── index.ts          public exports (Ch 0)
├── hono.ts           the Hono class — picks the default router (Ch 2)
├── hono-base.ts      HonoBase — route registration, #dispatch, fetch (Ch 2)
├── router.ts         the Router<T> interface every router implements (Ch 3)
├── router/           ★ the four router implementations (Ch 3)
│   ├── linear-router/    simplest: scan every route
│   ├── pattern-router/   one regex per route
│   ├── trie-router/      a prefix tree of segments
│   ├── reg-exp-router/   the "one big regex" engine
│   └── smart-router/     tries RegExp, falls back to Trie
├── compose.ts        the middleware onion (Ch 5)
├── context.ts        the Context `c` + response builders (Ch 4)
├── request.ts        HonoRequest — wraps web Request (Ch 2/4)
├── adapter/          per-runtime entry points (Ch 6)
├── helper/           env(), streaming, cookies, SSE … (Ch 6)
├── middleware/       25 built-in middleware (cors, jwt, …) (Ch 8)
├── preset/           tiny / quick — alternate router defaults (Ch 3)
├── validator/        validator() middleware (Ch 7)
├── client/           the hc RPC client (Ch 7)
└── types.ts          the type-level machinery — 2,778 lines (Ch 7)
```

> 📁 The single biggest file, `types.ts` (2,778 lines), contains **no runtime code** — it's all
> compile-time types. The runtime core (`hono-base.ts` + `context.ts` + `compose.ts` + `router/`) is
> remarkably compact. Hono's complexity budget is spent on *types*, not logic.

---

## 1.4 The end-to-end trace: one GET request

Let's follow `app.get('/users/:id', handler)` being hit by `GET /users/42`. Open the cited files and
read along.

**Registration (happens once, at startup):**

1. `app.get('/users/:id', handler)` is dispatched by the method handler. Its type is declared at
   `src/hono-base.ts:104` (`get!: HandlerInterface<…>`); its *implementation* is generated in the
   constructor loop at `src/hono-base.ts:128`, which ultimately calls the private `#addRoute`.
2. `src/hono-base.ts:385` — `#addRoute(method, path, handler)` uppercases the method, merges the base
   path, builds a `RouterRoute` record, then does the two key lines:
   - `src/hono-base.ts:395` — `this.router.add(method, path, [handler, r])` (hand the route to the router)
   - `src/hono-base.ts:396` — `this.routes.push(r)` (keep a copy for introspection)

**Dispatch (happens per request):**

3. `src/hono-base.ts:479` — `fetch(request, …)` is the entrypoint. It calls `#dispatch`.
4. `src/hono-base.ts:406` — `#dispatch(request, executionCtx, env, method)` runs the request:
   - `src/hono-base.ts:418` — `const path = this.getPath(request, { env })` — extract the pathname.
     (`getPath` is `src/utils/url.ts:106`, wired up at `src/hono-base.ts:172`.)
   - `src/hono-base.ts:419` — **`const matchResult = this.router.match(method, path)`** — the Router runs.
   - `src/hono-base.ts:421` — `const c = new Context(request, { path, matchResult, env, … })` — build `c`.
5. **Fast path** — `src/hono-base.ts:430`: *if exactly one handler matched*, call it directly without
   `compose`, for speed. Most routes hit this path.
6. **Onion path** — `src/hono-base.ts:450`: with multiple handlers (middleware + route handler),
   `const composed = compose(matchResult[0], this.errorHandler, this.#notFoundHandler)` builds the chain,
   then it's awaited at `:452`.
7. The handler runs, calls `c.json({...})` (`src/context.ts:708`), which builds a `Response`.
8. `#dispatch` returns that `Response`; `fetch` returns it to the adapter; the adapter hands it to the runtime.

That's the whole request. Five layers, one straight line.

```text
fetch ──► #dispatch ──► getPath ──► router.match ──► new Context
   (479)      (406)        (418)        (419)            (421)
                                          │
                    one handler? ─yes──► call directly        (430)
                          │no
                          └──► compose(...) ──► handler(c) ──► c.json() ──► Response
                                  (450)                          (708)
```

> 💡 **Tip:** the fast path at `:430` is a real performance decision, not an accident. A bare route with no
> middleware skips building the entire `compose` closure. Keep this in mind in Chapter 5 — `compose` only
> runs when there's actually an onion to build.

---

## 1.5 Lab 1 — instrument the trace

Reuse your `hono-hello` app from Lab 0. Add a logging middleware so you can *see* the layers fire in order:

```ts
import { Hono } from 'hono'
const app = new Hono()

app.use('*', async (c, next) => {
  console.log('→ before', c.req.method, c.req.path)   // Context + Request
  await next()                                         // descend the onion
  console.log('← after ', c.res.status)                // Response exists now
})

app.get('/users/:id', (c) => c.json({ id: c.req.param('id') }))

export default app
```

```bash
bun run --hot index.ts
curl -s localhost:3000/users/42
```

> 🧪 **Record in `labs/lab1-trace.md`:** the console output order. You should see `→ before GET /users/42`,
> then `← after 200`. Because you added a `use('*')` middleware, this request takes the **onion path**
> (`hono-base.ts:450`), not the fast path. Now remove the middleware and note that the response is identical —
> that request took the fast path at `:430`. Same output, different internal route.

---

## 1.6 Checkpoint

1. Name the five layers, top to bottom, and the one file that owns each.
2. Which single line in `hono-base.ts` invokes the Router? Which line invokes `compose`?
3. What is the difference between the "fast path" and the "onion path" in `#dispatch`, and what decides
   which one a request takes?
4. `types.ts` is the largest file in the repo. What kind of code does it contain — and what does that tell
   you about where Hono spends its complexity?
5. When does `this.router.add(...)` run — per request, or once at startup?

> If #2–#3 are shaky, re-read §1.4. If #1 is shaky, re-read §1.2.

---

## 🔌 Connect to your past (temlet web→native)

The five-layer model maps cleanly onto what you already know from Next.js — and it's *cleaner*. In Next,
"routing" (the file-system router), "middleware" (`middleware.ts` running at the edge), and "handler"
(your route file) are spread across three different mechanisms with three different mental models. Hono
collapses them into one explicit pipeline you can read in a single file.

That legibility is exactly what you want crossing into **Tauri**. When temlet's server logic becomes a
process behind the native shell, you don't want a framework whose request flow is implicit and
framework-magic; you want one where you can point at `#dispatch` and say "the request is *here* now." As
you read on, notice how little the App layer actually does — that thinness is what makes Hono cheap to
reason about when you no longer have Next's runtime holding your hand.

**Next:** [Chapter 2 — The App Object & HonoRequest →](02-app-lifecycle-and-request.md)
