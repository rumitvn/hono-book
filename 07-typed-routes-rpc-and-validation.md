# Chapter 7 — Typed Routes, the RPC Client & Validation

> **Goal:** Read the type-level machinery that makes Hono *type-safe*: how a path string yields a typed
> `c.req.param()`, how each route accumulates into a schema, and how the `hc` RPC client and `validator()`
> middleware ride on top of it. Grounded in `honojs/hono` at **`v4.12.25`** (`fce483e`).

---

## 7.1 Why it matters

Hono's marquee feature isn't speed — it's that your *types flow from server to client with zero
duplication*. Write `app.get('/users/:id', …)` and three things become typed for free: `c.req.param('id')`
on the server, the request shape, and — via the `hc` client — the fully-typed call on the frontend. No
codegen, no OpenAPI step, no schema file. This is the feature that makes people switch to Hono, and it is
*entirely* a TypeScript construction with **zero runtime cost** (it all erases at compile time).

This chapter is the one place the book reads types rather than logic. That's the point: this is where
Hono's complexity budget went (recall §1.3 — `types.ts` is 2,778 lines of pure types).

---

## 7.2 Mental model: a compile-time interpreter

```text
   "/users/:id"   ──ParamKeys──►  "id"   ──►  { id: string }   ──►  c.req.param('id'): string
   (a string)       (Ch 7.3)              (a typed record)            (typed accessor)

   app.get('/users/:id', h)  ──ToSchema──►  S grows: { '/users/:id': { $get: … } }
                                (Ch 7.4)         │
                                                 └──►  hc<typeof app>  ──►  client.users[':id'].$get()
                                                          (Ch 7.5)            fully typed
```

Two type-level engines, layered. `ParamKeys` reads a single path string. `ToSchema` accumulates every
route into a giant type `S`, carried as the second type parameter of `Hono<E, S, BasePath>`
(`src/hono.ts:16`). The `hc` client is "just" a function that reads `S` back out.

---

## 7.3 Path → typed params: `ParamKeys`

The smallest engine first. How does `/users/:id` become `'id'`? Read `src/types.ts:2706`:

```ts
export type ParamKeys<Path> = Path extends `${infer Component}/${infer Rest}`
  ? ParamKey<Component> | ParamKeys<Rest>     // split on '/', recurse
  : ParamKey<Path>
```

It recursively splits the path string on `/` (template-literal inference, §0.4) and runs each segment
through `ParamKey` (`src/types.ts:2698`):

```ts
type ParamKey<Component> = Component extends `:${infer NameWithPattern}`   // starts with ':'
  ? NameWithPattern extends `${infer Name}{${infer Rest}`                  // has a {pattern}?
    ? Rest extends `${infer _Pattern}?` ? `${Name}?` : Name               // optional?
    : NameWithPattern                                                       // plain :name
  : never                                                                   // literal segment → drop
```

So `ParamKeys<'/users/:id/posts/:slug'>` evaluates to `'id' | 'slug'`. A companion type,
`ParamKeyToRecord` (`src/types.ts:2710`), turns that union into `{ id: string; slug: string }`, which is
the return type of `c.req.param()`. That's the entire path-typing engine: a recursive conditional type
plus a mapped type. No magic — a tiny interpreter the compiler runs over your string literals.

> 🧠 **Mental model:** the compiler is *parsing your route paths at type-check time*. Every `:param`
> becomes a key; literal segments become `never` and vanish. When you see `c.req.param('id')` autocomplete,
> you're watching `ParamKeys` run.

---

## 7.4 Routes → a schema: `ToSchema`

Each call to `app.get(...)` returns a `Hono` with a *wider* `S` — the accumulated route schema. The widening
is done by `ToSchema` (`src/types.ts:2500`), which produces an entry shaped like:

```ts
{ '/users/:id': { $get: { input: …; output: …; outputFormat: … } } }
```

keyed by path, then by `$method`. As you chain `.get().post()`, these entries merge into one big `S`. The
crucial property: `S` is part of the app's *type*, so `typeof app` carries the complete API description.
That's what the client reads next. (`Handler` `src/types.ts:76`, `MiddlewareHandler` `:83`, `Env` `:30`,
`Input` `:42` are the supporting vocabulary these schema types are built from.)

> 📌 You never see `S` directly — it's inferred. But it's why `export type AppType = typeof app` (the line
> every Hono RPC tutorial tells you to write) is enough to give a separate client project full type
> information. You're exporting `S`.

---

## 7.5 The RPC client: `hc`

Now the payoff. `hc` (`src/client/client.ts:133`) is a function that takes your app *type* and a base URL,
and returns a typed client:

```ts
export const hc = <T extends Hono<any, any, any>, Prefix extends string = string>(
  baseUrl: Prefix,
  options?: ClientRequestOptions
) => createProxy(/* path-building Proxy */, []) as UnionToIntersection<Client<T, Prefix>>
```

At runtime it's a **`Proxy`** that builds a URL from the property path you access and issues a `fetch`. At
*compile* time, the `Client<T>` type reads the `S` schema out of `T` and projects it into a nested object of
typed methods. So:

```ts
import { hc } from 'hono/client'
const client = hc<typeof app>('https://api.example.com')
const res = await client.users[':id'].$get({ param: { id: '42' } })  // ← param typed from the route!
const data = await res.json()                                         // ← response type from the handler
```

The `param` argument is typed by `ParamKeys` (§7.3); the response is typed by what your handler returned.
`InferRequestType` / `InferResponseType` (`src/client/types.ts:251`) are the helpers that extract those for
you when you need the bare types. **No generated code** — the client is a `Proxy` plus a type projection.

> 💡 **Tip:** this is the same trick tRPC popularized, but Hono does it without a server adapter or a
> codegen step — because the route schema is already in the app's type. The frontend imports a *type* from
> the backend, never a value, so nothing bundles across the boundary.

---

## 7.6 Validation: `validator()`

Types describe the *shape* the compiler trusts; `validator()` enforces it at *runtime*. Read
`src/validator/validator.ts:46`. It's a middleware factory:

```ts
export const validator = (target, validationFunc) => async (c, next) => {
  // 1. pull the raw value for `target`: 'json' | 'form' | 'query' | 'param' | 'header' | 'cookie'
  // 2. value = await validationFunc(value, c)
  // 3. if it returned a Response (validation failed) → return it (short-circuit)
  // 4. else c.req.addValidatedData(target, value)   ← stash the parsed/typed value
  // 5. await next()
}
```

`target` says *where* to read (the JSON body, the query string, path params…); `validationFunc` is your
check (often a Zod schema via `@hono/zod-validator`). On success it stashes the validated value via
`c.req.addValidatedData(...)` so your handler reads it back, fully typed, with `c.req.valid('json')`
(`src/request.ts:351`). On failure it returns a `Response` and the onion short-circuits — the route handler
never runs. It's an ordinary middleware (Chapter 5), so it composes like any other layer.

---

## 7.7 Lab 7 — types end-to-end

You'll watch the compiler enforce the route type. In a TS-aware editor (or with `tsc`), reuse `hono-hello`:

```ts
// rpc.ts
import { Hono } from 'hono'
import { hc } from 'hono/client'

const app = new Hono()
  .get('/users/:id', (c) => c.json({ id: c.req.param('id'), name: 'Ada' }))

export type AppType = typeof app             // ← exporting S

const client = hc<AppType>('http://localhost:3000')
async function demo() {
  const res = await client.users[':id'].$get({ param: { id: '42' } })
  const user = await res.json()
  console.log(user.name.toUpperCase())       // user.name is typed as string
  // @ts-expect-error — 'id' must be a string; this should fail to compile:
  await client.users[':id'].$get({ param: { id: 42 } })
}
```

```bash
cd ../hono && npx tsc --noEmit ~/hono-hello/rpc.ts   # or just hover types in your editor
```

> 🧪 **Record in `labs/lab7-types.md`:** confirm `user.name` autocompletes as a string, and that the
> `@ts-expect-error` line is genuinely an error if you remove the comment (passing `id: 42` must fail —
> `ParamKeys` typed it as a string). You've now seen the full chain: `ParamKeys` → `ToSchema` → `hc`, all
> at compile time, all erased at runtime.

---

## 7.8 Checkpoint

1. What does `ParamKeys<'/a/:b/c/:d'>` evaluate to, and which two types implement it?
2. What is `S` in `Hono<E, S, BasePath>`, and how does it grow as you add routes?
3. At runtime, what *is* the `hc` client? At compile time, where do its types come from?
4. Why does Hono RPC need no code generation step, unlike OpenAPI-based clients?
5. What does `validator('json', fn)` do on success vs. failure, and how does it relate to Chapter 5?

> If #1 is shaky, re-read §7.3. If #3–#4 are shaky, re-read §7.4–§7.5 together — the schema and the client
> are two ends of one wire.

---

## 🔌 Connect to your past (temlet web→native)

This is the chapter that should make you sit up, given temlet. You've felt the pain of keeping frontend
types in sync with backend responses — the DTOs that drift, the `any` that creeps in at the fetch boundary,
the OpenAPI generator in your build. Hono's `hc` deletes that whole category of work: the client imports
`typeof app` and *is* the API contract.

For a Next.js→Tauri migration this is doubly valuable. Tauri already gives you typed `invoke()` calls to
Rust commands across the native bridge; Hono gives you the same end-to-end typing across the *HTTP* bridge.
So whether a given temlet capability ends up behind a Tauri command or behind a Hono endpoint, the frontend
calls it with full type safety and no hand-written client. You get one consistent, generated-code-free story
for "call the backend" on both sides of the web→native seam — which is exactly the kind of consistency that
keeps a migration from sprawling.

**Next:** [Chapter 8 — Capstone: Extending & Staying Current →](08-capstone-extending-and-staying-current.md)
