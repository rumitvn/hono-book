# Chapter 4 — Context & Building Responses

> **Goal:** Understand the `Context` object — the `c` every handler receives — and how `c.json()`,
> `c.text()`, and `c.html()` turn your data into a web-standard `Response`. Learn the `c.env` and `c.var`
> seams that make the same handler portable and stateful. Grounded in `honojs/hono` at **`v4.12.25`**
> (`fce483e`).

---

## 4.1 Why it matters

`c` is the one argument your handlers actually use. It's the request, the response builder, the
environment bindings, and a per-request scratchpad, all in one object. If you understand `Context`, you
understand the entire surface area you program against — and you'll see that, like the rest of Hono, it's
a thin, readable layer over web standards, not a mysterious framework god-object.

The deeper payoff: knowing *when* a `Response` is actually constructed (and when headers are buffered vs.
committed) is what lets you reason about middleware that modifies responses — the subject of Chapter 5.

---

## 4.2 Mental model: c is a per-request envelope

```text
        new Context(request, { path, matchResult, env, executionCtx, … })
                                  src/context.ts:352
        ┌──────────────────────────────────────────────────────────┐
   c.   │  req      → HonoRequest (the incoming request)   :366     │
        │  env      → runtime bindings (KV, secrets, …)    :315     │
        │  var/get/set → per-request scratchpad            :546/571 │
        │  ─────────────────────────────────────────────────────── │
        │  json/text/html/body → BUILD a Response          :708 …   │
        │  header/status       → buffer response metadata  :515/529 │
        │  res / finalized     → the committed Response     :403/317 │
        └──────────────────────────────────────────────────────────┘
```

A fresh `Context` is created per request in `#dispatch` (recall `src/hono-base.ts:421`). It is
**not** reused across requests — so anything you put on it (`c.set(...)`) is request-scoped and
automatically discarded. That isolation is why Hono needs no request-local-storage tricks for the common
case.

---

## 4.3 The two halves: reading and responding

Open `src/context.ts:293` (the class) and `:352` (the constructor — it just stashes the options). The
class splits cleanly into a **reading** half and a **responding** half.

**Reading the request and environment:**

- `c.req` (`src/context.ts:366`) — lazily constructs the `HonoRequest` from Chapter 2. `c.req.param('id')`,
  `c.req.query('q')`, `c.req.json()`.
- `c.env` (`src/context.ts:315`) — the runtime's bindings: a Cloudflare Worker's KV namespaces, D1
  databases, and secrets; environment variables elsewhere. This is the seam where the *platform* enters
  your handler. (Chapter 6 goes deep.)
- `c.set(key, value)` (`src/context.ts:546`) / `c.get(key)` (`src/context.ts:571`) — a per-request
  key/value store backed by a `Map`. Middleware writes (`c.set('user', …)`), downstream handlers read
  (`c.get('user')`). This is how authentication middleware passes a user object to your route.

**Building the response:**

- `c.json(obj, status?, headers?)` (`src/context.ts:708`)
- `c.text(str, …)` (`src/context.ts:682`)
- `c.html(str, …)` (`src/context.ts:723`)
- `c.body(data, …)` (`src/context.ts:664`)
- `c.redirect(loc, status?)` (`src/context.ts:750`), `c.notFound()` (`src/context.ts:776`)

---

## 4.4 How `c.json()` becomes a `Response`

This is the moment to dispel any "framework magic." Read the body of `c.json` (`src/context.ts:708`):

```ts
json: JSONRespond = (object, arg?, headers?) => {
  return this.#newResponse(
    JSON.stringify(object),                                   // serialize
    arg,                                                       // status or ResponseInit
    setDefaultContentType('application/json', headers)         // add content-type if absent
  )
}
```

That's it. `c.json({...})` is `JSON.stringify` + a default `Content-Type` + a call to the private
`#newResponse` (`src/context.ts:604`), which constructs an actual web `Response`. `c.text` and `c.html`
are the same shape with different defaults (`text/plain`, `text/html`). `setDefaultContentType`
(`src/context.ts:281`) only sets the header if you didn't provide one — so you can always override.

> 🧠 **Mental model:** the `c.json/text/html` family is *sugar over `new Response()`*. There is no hidden
> response object in Hono — when you call `c.json`, a real `Response` is built right then and returned.
> Compare to `c.res` (`src/context.ts:403`), which lazily *materializes* a mutable response for the cases
> where middleware needs to tweak one. Two paths: build-and-return (handlers) vs. lazily-mutate
> (middleware).

---

## 4.5 Headers and status: buffered, then committed

Why does `c.header('x', 'y')` work *before* you call `c.json()`? Because header and status are
**buffered** on the context and applied when the response is built:

- `c.status(code)` (`src/context.ts:529`) stashes the status in a private `#status` field — it doesn't
  build anything.
- `c.header(name, value, options?)` (`src/context.ts:515`) writes into a buffered `Headers` object — but
  notice the first lines: *if the response is already finalized* (`src/context.ts:516`), it mutates the
  committed response's headers instead. This dual behavior is what lets both handlers (pre-build) and
  middleware (post-build) set headers correctly.
- `c.finalized` (`src/context.ts:317`) flips to `true` (`src/context.ts:433`) once a response has been
  committed. `compose` checks this flag to decide whether a middleware produced a response — the link into
  Chapter 5.

> ⚠️ **Footgun:** order matters for the *buffered* path. `c.status(201)` then `return c.json(obj)` →
> 201. But `return c.json(obj)` *then* `c.status(201)` is too late — the response was already built with the
> default 200. The buffering is one-way: set metadata, *then* build the body.

---

## 4.6 `c.env` and `c.var`: the portability and state seams

Two small properties carry a lot of weight:

**`c.env`** is how the *runtime* reaches your code without your code naming the runtime. On Workers,
`c.env.MY_KV` is a KV binding; on Node, you'd read `process.env`. Your handler says `c.env.DATABASE` and
stays runtime-agnostic — the adapter (Chapter 6) decides what `env` actually is. This is the single most
important property for the web→native story.

**`c.var`** (and `c.set`/`c.get`) is typed per-request state. With TypeScript, you declare what lives there
via the `Variables` half of your `Env` type, and `c.get('user')` is typed. It's a `Map` under the hood
(`src/context.ts:546`) — nothing exotic — but the typing makes middleware→handler hand-offs safe.

---

## 4.7 Lab 4 — the middleware → handler handoff

Prove the buffered-header rule and the `c.set`/`c.get` channel in one probe (reuse `hono-hello`):

```ts
// ctx-probe.ts
import { Hono } from 'hono'
const app = new Hono<{ Variables: { reqId: string } }>()

app.use('*', async (c, next) => {
  c.set('reqId', 'abc-123')          // middleware writes per-request state  (:546)
  c.header('x-powered-by', 'hono-book')
  await next()
  c.header('x-after', 'yes')          // set AFTER next(): response is finalized → mutates committed headers (:516)
})

app.get('/', (c) => {
  c.status(201)                       // buffer status BEFORE building body
  return c.json({ id: c.get('reqId') })   // reads middleware's value         (:571)
})

const res = await app.request('/')
console.log(res.status, await res.json())
console.log('powered-by:', res.headers.get('x-powered-by'), '| after:', res.headers.get('x-after'))
```

```bash
bun run ctx-probe.ts
```

> 🧪 **Record in `labs/lab4-context.md`:** the status, body, and both headers. Expected: `201
> {"id":"abc-123"}`, and *both* `x-powered-by` and `x-after` present. The `x-after` header — set *after*
> `await next()` — proves the §4.5 dual path: once finalized, `c.header` mutates the committed response.
> Now swap the order in the handler (`return c.json(...)` then `c.status(201)`) and watch the status fall
> back to 200 — the §4.5 footgun.

---

## 4.8 Checkpoint

1. When is a `Context` created, and what is its lifetime?
2. Walk through what `c.json({a:1})` does, step by step, to produce a `Response`.
3. Why can you call `c.header(...)` both before and after `c.json(...)`? What does `c.finalized` have to do
   with it?
4. What is the difference between `c.env` and `c.var`, and which one is the key to runtime portability?
5. Show the order-of-operations footgun with `c.status()` and explain why it happens.

> If #2–#3 are shaky, re-read §4.4–§4.5. If #4 is shaky, re-read §4.6.

---

## 🔌 Connect to your past (temlet web→native)

`c.env` is the cleanest answer to a problem you'll hit head-on migrating temlet. In Next.js you reach for
`process.env` and assume a Node process exists. The moment temlet runs on the edge — or behind Tauri,
where "the environment" is the OS and a bundled config, not a Node process — `process.env` is the wrong
abstraction. Hono's `c.env` inverts it: your handler *declares a dependency* (`c.env.DATABASE`) and the
adapter *supplies it*, per runtime. That's dependency injection at the request boundary.

And `c.set`/`c.get` is the request-scoped equivalent of the React context you already think in: a
middleware "provides" a value (`c.set('user', …)`), descendants "consume" it (`c.get('user')`), and it's
torn down when the request ends. If you've ever lifted auth state through a Next middleware into a route,
this is the same pattern with an explicit, typed channel — and one that survives the move off Node.

**Next:** [Chapter 5 — The Middleware Onion →](05-the-middleware-onion.md)
