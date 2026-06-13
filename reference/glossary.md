# Glossary & Source-File Index

Quick reference for the Hono internals terms used in this book. Pinned tag `v4.12.25`
(commit `fce483e`). Citations are into the local clone at `../hono/src/`.

## Core concepts

| Term | One-liner | Chapter |
|------|-----------|---------|
| **Web standards** | Hono speaks only the platform's `Request`/`Response` — nothing proprietary at its edges; the source of all portability | 0, 6 |
| **`Request` / `Response`** | the Fetch API objects at Hono's input and output boundary; a Hono app is "just" a function between them | 0 |
| **One-shot body** | a request/response body is a stream you can read once; the reason for `bodyCache` | 0, 2 |
| **Five layers** | App → Router → compose → Context → Adapter | 1 |
| **`HonoBase` / `Hono`** | `HonoBase` is the engine (registration, dispatch); `Hono` is the thin subclass that picks a default router | 2 |
| **`#dispatch`** | the per-request orchestrator inside `HonoBase`: getPath → match → Context → fast/onion path | 1, 2 |
| **Fast path vs onion path** | one matched handler is called directly; multiple handlers go through `compose` | 1, 5 |
| **`RouterRoute`** | the route record kept in `app.routes` for introspection (not used for matching) | 2 |

## The Router (the flagship)

| Term | One-liner | Chapter |
|------|-----------|---------|
| **`Router<T>` interface** | the two-method contract (`add`, `match`) every router implements; generic in the handler payload | 3 |
| **`Result<T>`** | the match return: `[[handler, paramIndexMap][], paramStash]` *or* `[[handler, params][]]` | 3 |
| **LinearRouter** | scans every route per request; zero build cost — good for one-shot workers | 3 |
| **TrieRouter** | a prefix tree of path segments; O(segments), handles *any* routing table — the universal fallback | 3 |
| **RegExpRouter** | merges all routes into **one** `RegExp`; matching is a single `path.match()` | 3 |
| **SmartRouter** | tries RegExpRouter, falls back to TrieRouter on `UnsupportedPathError`; the default | 3 |
| **`UnsupportedPathError`** | thrown when a route table is too ambiguous for one regex; the signal SmartRouter catches | 3 |
| **Static map** | RegExpRouter's O(1) dictionary for purely-static routes, checked before the regex | 3 |
| **Self-replacing `match`** | RegExpRouter/SmartRouter overwrite `this.match` after the first call so later calls skip the build | 3 |
| **Marker group** | the end-anchored empty capture group `$()` whose position reveals which handler matched | 3 |
| **Presets** | `hono/quick` (Linear+Trie, no build) and `hono/tiny` (Pattern, smallest) swap the default router | 3 |

## Context & responses

| Term | One-liner | Chapter |
|------|-----------|---------|
| **`Context` (`c`)** | the per-request object: request, response builder, env, and scratchpad | 4 |
| **`c.json/text/html`** | sugar over `new Response()` — serialize + default content-type + build | 4 |
| **`#newResponse`** | the private response constructor all the `c.*` responders funnel into | 4 |
| **`c.finalized`** | the bit that flips once a response is committed; prevents outer layers clobbering it | 4, 5 |
| **Buffered headers/status** | `c.header`/`c.status` buffer metadata, applied when the response is built (set them *before* the body) | 4 |
| **`c.env`** | the runtime's bindings (KV, secrets, …); the platform-injection seam | 4, 6 |
| **`c.var` / `c.set` / `c.get`** | typed per-request state via a `Map`; the middleware→handler channel | 4 |
| **`HonoRequest`** | the wrapper around the web `Request`; adds `param/query/header/json`, keeps `.raw` | 2, 4 |

## The middleware onion

| Term | One-liner | Chapter |
|------|-----------|---------|
| **`compose`** | the 73-line koa-style function that chains handlers into the onion | 5 |
| **`dispatch(i)`** | the recursive inner function; `await dispatch(i+1)` is what `next()` runs | 5 |
| **`next()`** | literally `() => dispatch(i + 1)` — run the rest of the onion, then resume | 5 |
| **Onion (before/after)** | code before `next()` runs outer→inner; after `next()` runs inner→outer | 5 |
| **`onError` / `notFound`** | the error and 404 handlers `compose` falls back to; overridable via `app.onError`/`app.notFound` | 5 |

## Runtime adapters & portability

| Term | One-liner | Chapter |
|------|-----------|---------|
| **Adapter** | a thin per-runtime shell that maps the native entry shape to/from `app.fetch` | 6 |
| **`getRuntimeKey()`** | runtime detection; prefers standardized `navigator.userAgent`, then vendor globals | 6 |
| **`env(c)`** | resolves bindings per runtime (`process.env` / `Deno.env` / `c.env`); DI at the runtime boundary | 6 |
| **Streaming / SSE** | `stream`/`streamSSE`/`streamText` build a `Response` with a `ReadableStream` body — still web-standard | 6 |

## Types, RPC & validation

| Term | One-liner | Chapter |
|------|-----------|---------|
| **`ParamKeys<Path>`** | a recursive conditional type that extracts `:param` names from a path string | 7 |
| **`ToSchema`** | accumulates each route into the schema type `S` carried by `Hono<E, S, BasePath>` | 7 |
| **`hc` client** | a runtime `Proxy` + compile-time projection of `S` → a typed RPC client, no codegen | 7 |
| **`validator()`** | middleware that reads a target (json/query/param/…), runs a check, stashes validated data | 7 |
| **`c.req.valid(target)`** | reads back the value a `validator()` stashed, fully typed | 7 |

## Key files (start here when investigating)

| File | What | Anchors |
|------|------|---------|
| `src/index.ts` | the public surface | `Hono` import (`:17`), public type exports (`:22`), `Context` (`:39`), `HonoRequest` (`:44`) |
| `src/hono.ts` | the concrete `Hono` class | `class Hono` (`:16`), constructor + default `SmartRouter` (`:26`–`32`) |
| `src/hono-base.ts` | the engine: registration + dispatch | `class Hono`/HonoBase (`:98`), method-handler loop (`:128`), `route` (`:208`), `onError` (`:271`), `notFound` (`:291`), `#addRoute` (`:385`), `router.add` (`:395`), `#dispatch` (`:406`), `router.match` (`:419`), fast path (`:430`), `compose(...)` (`:450`), `fetch` (`:479`), `request` (`:499`); default 404 (`:31`) / error (`:35`) handlers |
| `src/request.ts` | the `HonoRequest` wrapper | `class HonoRequest` (`:36`), `raw` (`:51`), `path` (`:68`), `bodyCache` (`:69`), `param` (`:94`), `query` (`:148`), `header` (`:185`), `json` (`:253`), `valid` (`:351`) |
| `src/router.ts` | the router contract | `interface Router<T>` (`:29`), `Result<T>` (`:98`), `UnsupportedPathError` (`:103`) |
| `src/router/reg-exp-router/router.ts` | the one-regex engine | `add` (`:132`), `buildAllMatchers` (`:208`), `#buildMatcher` (`:224`), `buildMatcherFromPreprocessedRoutes` (`:34`) |
| `src/router/reg-exp-router/trie.ts` / `node.ts` / `matcher.ts` | regex assembly + match | `Trie.buildRegExp` (`trie.ts:49`), marker rewrite (`trie.ts:59`), `Node.buildRegExpStr` (`node.ts:135`), param marker `(k)@varIndex` (`node.ts:142`), `match` entry (`matcher.ts:10`), static fast path (`matcher.ts:18`), which-group (`matcher.ts:27`), self-replace (`matcher.ts:31`) |
| `src/router/smart-router/router.ts` | the fallback tournament | `add` (`:13`), `match` tournament (`:21`), fallback `continue` (`:43`), bind winner (`:46`) |
| `src/router/trie-router/node.ts` | the trie fallback | `insert` (`:44`), `search` (`:114`) |
| `src/router/linear-router/router.ts` / `pattern-router/router.ts` | baselines | LinearRouter `add` (`linear:15`)/`match` (`linear:25`); PatternRouter (`pattern-router/router.ts`) |
| `src/preset/quick.ts` / `tiny.ts` | alternate router defaults | `quick` = Smart(Linear,Trie) (`quick.ts:13`), `tiny` = PatternRouter (`tiny.ts:11`) |
| `src/context.ts` | the `Context` object | `class Context` (`:293`), constructor (`:352`), `env` (`:315`), `finalized` (`:317`), `req` (`:366`), `res` (`:403`), `header` (`:515`), `status` (`:529`), `set` (`:546`), `get` (`:571`), `#newResponse` (`:604`), `body` (`:664`), `text` (`:682`), `json` (`:708`), `html` (`:723`), `redirect` (`:750`), `notFound` (`:776`) |
| `src/compose.ts` | the middleware onion | `compose` (`:15`), guard (`:33`), the i-th handler (`:43`), `await handler(c, next)` (`:51`), `onError` (`:55`), `onNotFound` (`:63`), commit (`:67`) |
| `src/helper/adapter/index.ts` | runtime detection + bindings | `Runtime` type (`:8`), `env()` (`:10`), `getRuntimeKey()` (`:50`) |
| `src/adapter/cloudflare-workers/index.ts` | a representative adapter | `serveStatic` (`:6`), `upgradeWebSocket` (`:7`), `getConnInfo` (`:8`) |
| `src/helper/streaming/index.ts` | streaming helpers | `stream`/`streamSSE`/`streamText` exports, `SSEMessage` (`sse.ts:6`) |
| `src/types.ts` | the type-level machinery (2,778 lines) | `Env` (`:30`), `Input` (`:42`), `Handler` (`:76`), `MiddlewareHandler` (`:83`), `ToSchema` (`:2500`), `ParamKey` (`:2698`), `ParamKeys` (`:2706`), `ParamKeyToRecord` (`:2710`) |
| `src/client/client.ts` | the RPC client | `hc` (`:133`); `InferResponseType` (`client/types.ts:251`) |
| `src/validator/validator.ts` | the validation middleware | `validator` (`:46`) |
| `src/middleware/powered-by/index.ts` | the simplest built-in middleware (a template) | `poweredBy` (`:30`) |

> ⚠️ Line numbers are pinned to `v4.12.25` (`fce483e`). When you bump the pin, the *shape* (five layers,
> four routers, the onion) is stable, but these numbers drift — re-verify this table with `sed -n` after
> every re-pin. (See Chapter 8 §8.5.)

<sub>A **RumitX** publication · [rumitx.com](https://rumitx.com)</sub>
