# Chapter 6 — Runtime Adapters & Portability

> **Goal:** Understand the seam that makes *one* Hono app run unchanged on Cloudflare Workers, Bun, Deno,
> Node, and Lambda. Read the adapters, the `getRuntimeKey()` detector, and the `env()` helper, and meet the
> streaming/SSE helpers. This is the **web→native bridge** chapter. Grounded in `honojs/hono` at
> **`v4.12.25`** (`fce483e`).

---

## 6.1 Why it matters

This is the chapter that explains Hono's reason to exist. Every other framework picks a runtime — Express
picks Node, Next picks its own server, Workers code picks `workerd`. Hono picks *none*: the core knows only
`Request`/`Response` (Chapter 0), and a thin **adapter** per runtime translates the runtime's native entry
shape into a `fetch` call. Understanding this seam is understanding how the same code ships everywhere — and
it's the exact mechanism you'll lean on carrying temlet across the web→native line.

---

## 6.2 Mental model: a thin translation shell

```text
   Cloudflare Workers          Bun / Deno              AWS Lambda
   export default {            export default {        export const handler =
     fetch(req, env, ctx)        fetch(req)              (event) => …
   }                           }                       │
        │                          │                   │ (event → Request)
        └──────────┬───────────────┴───────────────────┘
                   ▼
            app.fetch(request, env, ctx)        ← the ONE universal entry
                   │
            [ Router → compose → Context ]      ← runtime-agnostic core
                   │
                   ▼
              Response  ───────────────────────► back to each runtime's native shape
```

Each runtime has a different *native* entry shape. The adapter's whole job is to massage that shape into
`app.fetch(request, env, ctx)` and massage the returned `Response` back. The core never learns which
runtime it's on.

> 🧠 **Mental model:** the adapter is a *power plug adapter*, not a transformer. It changes the shape of
> the connector; it doesn't change the electricity. Your app is the appliance and it runs the same
> everywhere.

---

## 6.3 The simplest adapter: Cloudflare Workers

For Workers, the runtime's native entry *already* matches Hono's: `export default { fetch(req, env, ctx) }`.
So you don't even import an adapter to run — you just `export default app`, because a Hono app *is* a
`{ fetch }` object. The `hono/cloudflare-workers` entry point (`src/adapter/cloudflare-workers/index.ts`)
adds only the *runtime-specific extras* that can't be web-standard:

```ts
// src/adapter/cloudflare-workers/index.ts
export { serveStatic } from './serve-static-module'   // :6 — serve from Workers' static assets
export { upgradeWebSocket } from './websocket'        // :7 — CF's WebSocket pair API
export { getConnInfo } from './conninfo'              // :8 — read cf-connecting-ip
```

`getConnInfo` (`src/adapter/cloudflare-workers/conninfo.ts`) is one line — it reads the client IP from the
`cf-connecting-ip` header. Compare it to the **Bun** and **Deno** adapters (`src/adapter/bun/`,
`src/adapter/deno/`), each of which has its *own* `conninfo.ts`, `serve-static.ts`, and `websocket.ts`.
Same exported names, runtime-specific bodies. That uniform surface is the adapter contract.

> 📁 Nine adapters ship in `src/adapter/`: `aws-lambda`, `bun`, `cloudflare-pages`, `cloudflare-workers`,
> `deno`, `lambda-edge`, `netlify`, `service-worker`, `vercel`. Each is small — the cleverness is in the
> core *not* needing them.

---

## 6.4 Runtime detection: `getRuntimeKey()`

When code *does* need to branch on the runtime, Hono detects it rather than asking you. Read
`getRuntimeKey()` (`src/helper/adapter/index.ts:50`):

```ts
export const getRuntimeKey = (): Runtime => {
  const global = globalThis as any
  // 1. Prefer the standardized navigator.userAgent (Deno/Bun/Workers/Node all set it)
  if (userAgentSupported) {
    for (const [key, ua] of Object.entries(knownUserAgents)) {
      if (checkUserAgentEquals(ua)) return key as Runtime
    }
  }
  if (typeof global?.EdgeRuntime === 'string') return 'edge-light'   // Vercel Edge
  if (global?.fastly !== undefined) return 'fastly'
  if (global?.process?.release?.name === 'node') return 'node'        // fallback (Node < 21.1)
  return 'other'
}
```

The `Runtime` type (`src/helper/adapter/index.ts:8`) is the closed set:
`'node' | 'deno' | 'bun' | 'workerd' | 'fastly' | 'edge-light' | 'other'`. Detection prefers the
**standardized `navigator.userAgent`** (which Deno, Bun, Workers, and modern Node all populate —
`knownUserAgents` maps `'Cloudflare-Workers' → 'workerd'`, etc.), and only falls back to runtime-specific
globals like `EdgeRuntime` or `process` when needed. This is itself a web-standards-first design: detect by
the standard signal, degrade to vendor checks.

---

## 6.5 The `env()` seam: where the platform enters

`c.env` (Chapter 4) is the runtime's bindings — but *what `env` is* differs per runtime, and that
difference is centralized in one helper. Read `env()` (`src/helper/adapter/index.ts:10`):

```ts
export const env = (c, runtime?) => {
  const globalEnv = (globalThis as any)?.process?.env
  runtime ??= getRuntimeKey()
  const runtimeEnvHandlers = {
    bun:          () => globalEnv,     // process.env
    node:         () => globalEnv,     // process.env
    'edge-light': () => globalEnv,     // process.env
    deno:         () => Deno.env.toObject(),
    workerd:      () => c.env,         // the Worker's bindings object
    fastly:       () => ({}),
    other:        () => ({}),
  }
  return runtimeEnvHandlers[runtime]()
}
```

This is the whole portability payoff in one table. On Node/Bun, `env(c)` reads `process.env`. On Deno, it
calls `Deno.env.toObject()`. On Workers, it returns `c.env` (the bindings the platform injected). Your code
writes `env(c).DATABASE_URL` *once* and it resolves correctly everywhere — you never write
`process.env` (which doesn't exist on Workers) or `Deno.env` (which doesn't exist on Node).

> 💡 **Tip:** this is dependency injection at the runtime boundary. The framework asks the environment
> "what are my secrets/bindings?" and each runtime answers in its own dialect. Your handler stays in one
> language.

---

## 6.6 Streaming & SSE: still just `Response`

Long-lived responses (streaming, server-sent events) are where you'd expect runtime-specific code — and
Hono still keeps them web-standard. The streaming helpers (`src/helper/streaming/index.ts`) export:

- `stream(c, cb)` — write to a `ReadableStream`-backed `Response`.
- `streamSSE(c, cb)` — server-sent events; the `SSEMessage` shape is `{ data, event?, id?, retry? }`
  (`src/helper/streaming/sse.ts:6`).
- `streamText(c, cb)` — chunked text.

All three build a `Response` whose body is a stream — the same `Response` from Chapter 0, just with a
streaming body. Because `ReadableStream` is a web standard, this works identically on Workers, Bun, and
Deno without per-runtime branches.

---

## 6.7 Lab 6 — one app, two runtimes

Prove portability by running the *identical* app file on two runtimes. Reuse `hono-hello`:

```ts
// portable.ts — note: ZERO runtime-specific imports
import { Hono } from 'hono'
import { getRuntimeKey, env } from 'hono/adapter'

const app = new Hono()
app.get('/', (c) => c.json({ runtime: getRuntimeKey(), greeting: env(c).GREETING ?? '(unset)' }))
export default app
```

```bash
# Run on Bun:
GREETING=hi bun run --hot portable.ts &       # serves on :3000
curl -s localhost:3000/ ; echo               # expect runtime "bun"
kill %1

# Run the SAME FILE on Node (via @hono/node-server) or Deno:
GREETING=hi deno run --allow-net --allow-env npm:hono   # (or wire @hono/node-server)
```

> 🧪 **Record in `labs/lab6-adapters.md`:** the `runtime` value reported by each runtime you try (e.g.
> `"bun"`, `"deno"`), and confirm `GREETING` resolved on each via the `env(c)` seam from §6.5 — *without*
> the file ever importing a runtime-specific module. That "no runtime import in the app file" property is
> the entire chapter in one observation.

---

## 6.8 Checkpoint

1. What is the universal entry point every adapter targets? What does an adapter actually *do*?
2. Why can a Cloudflare Worker just `export default app` with no adapter import?
3. How does `getRuntimeKey()` detect the runtime, and which signal does it prefer over vendor globals?
4. Walk through `env(c)` on Workers vs. Node — what does each return, and why does that let your code stay
   runtime-agnostic?
5. Why do streaming and SSE *not* need per-runtime adapters?

> If #4 is shaky, re-read §6.5. If #1–#2 are shaky, re-read §6.2–§6.3.

---

## 🔌 Connect to your past (temlet web→native)

This is the chapter you'll come back to. temlet's hardest migration problem isn't UI — it's that its
server-side logic assumes Node. `process.env`, the Node `fs`, a long-lived server: none of those survive
the trip to a Worker, and they get awkward behind Tauri, where the "backend" is a bundled process on the
user's machine. Every one of those assumptions is a rewrite.

Hono's adapter seam is the pattern that makes the rewrite a *configuration*, not a reimplementation. Move
temlet's API handlers onto runtime-agnostic Hono handlers that read `env(c)` instead of `process.env`, and
the same code can serve from Cloudflare's edge today and from a sidecar behind your Tauri shell tomorrow —
you swap the adapter, not the app. The `getRuntimeKey()` detector even lets you keep the rare genuinely
runtime-specific branch (say, a native-only capability behind Tauri) explicit and contained, instead of
smeared across the codebase as ambient `process` assumptions. That's the difference between porting temlet
once and porting it cleanly.

**Next:** [Chapter 7 — Typed Routes, the RPC Client & Validation →](07-typed-routes-rpc-and-validation.md)
