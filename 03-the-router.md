# Chapter 3 — The Router ★

> **Goal:** Understand Hono's central abstraction: **four routers behind one interface**, and the trick
> that makes Hono one of the fastest routers in JavaScript — `RegExpRouter`'s merging of every registered
> route into a *single* regular expression. Then understand why that trick can't always apply, and how
> `SmartRouter` quietly falls back. Grounded in `honojs/hono` at **`v4.12.25`** (`fce483e`).
>
> This is the flagship chapter. Take your time; read every cited file.

---

## 3.1 Why it matters

Routing is the hot loop of a web framework: it runs on *every single request*, before any of your code.
A slow router taxes every endpoint. Most frameworks store routes in a list or a tree and walk it per
request — fine, but linear in the number of routes or path segments.

Hono asks a sharper question: *what if matching a path were a single regex test, regardless of how many
routes you registered?* The answer is `RegExpRouter`, and the engineering around "but sometimes that's
impossible" is what makes the design genuinely clever rather than merely fast. Understanding it teaches
you something that generalizes far beyond Hono: how to turn an O(n) lookup into O(1) by precompiling.

---

## 3.2 The contract: one interface, four implementations

Every router implements the same tiny interface (`src/router.ts:29`):

```ts
export interface Router<T> {
  name: string
  add(method: string, path: string, handler: T): void   // :42
  match(method: string, path: string): Result<T>          // :51
}
```

Two methods. `add` registers; `match` looks up. The interface is **generic in `T`** — the router never
knows what a "handler" is. (Recall §2.4: the App hands it the tuple `[handler, routerRoute]`. The router
carries that opaque payload through and hands it back.)

The return type is the subtle part (`src/router.ts:98`):

```ts
export type Result<T> = [[T, ParamIndexMap][], ParamStash] | [[T, Params][]]
```

A union of two shapes. Either `[[handler, paramIndexMap][], paramStash]` — handlers paired with *indices*
into a shared array of captured strings — or `[[handler, paramsObject][]]` — handlers paired with
ready-made param objects. The first shape is the fast one (used by `RegExpRouter`): it avoids building a
params object until you actually call `c.req.param()`.

And one special error (`src/router.ts:103`):

```ts
export class UnsupportedPathError extends Error {}
```

Remember this class. It is the entire hinge of the design.

```text
                       ┌──────────────────────────┐
   app.get/post  ───►  │   Router<T> interface     │  ◄── one contract
                       │   add() / match()          │
                       └────────────┬───────────────┘
            ┌───────────────┬───────┴───────┬────────────────┐
            ▼               ▼               ▼                ▼
      LinearRouter    TrieRouter     RegExpRouter      SmartRouter
      scan a list     walk a trie    ONE big regex    try fast, fall back
      (simplest)      (general)      (fastest)        (the default)
```

Let's read each — four case studies, simplest to cleverest.

---

## 3.3 Case study 1 — LinearRouter (the baseline)

`src/router/linear-router/router.ts` (144 lines). The simplest thing that could work.

- `add` (`src/router/linear-router/router.ts:15`) pushes `[method, path, handler]` onto an array. O(1),
  no preprocessing.
- `match` (`src/router/linear-router/router.ts:25`) **scans the whole array** on every request, testing
  each route against the path with string checks and per-route regex for `:params`.

This is O(routes) per request, but with *zero* build cost — which is why the `quick` preset uses it
(§3.7): for a short-lived Worker that registers a few routes and handles one request, building a big regex
isn't worth it. LinearRouter wins when registration-to-first-match time dominates.

> 💡 **Tip:** "the naive version is sometimes the right version" is a real engineering lesson here. Hono
> ships LinearRouter not as a teaching toy but as a genuine production choice for cold-start-sensitive
> environments.

---

## 3.4 Case study 2 — TrieRouter (the general one)

`src/router/trie-router/` — `router.ts` (28 lines) delegates to `node.ts` (234 lines), a prefix tree.

- `add` → `Node.insert` (`src/router/trie-router/node.ts:44`): split the path into segments and walk/build
  a tree, one node per segment. A `:param` segment becomes a node with a pattern; `*` becomes a wildcard
  node.
- `match` → `Node.search` (`src/router/trie-router/node.ts:114`): walk the tree following the incoming
  path's segments, collecting handlers and binding params as you descend.

Matching is O(path segments), independent of how many routes exist — a real improvement over LinearRouter.
And crucially, **a trie can represent any routing table**, including the ambiguous ones that defeat
`RegExpRouter` (next section). That universality is why TrieRouter is always the *fallback*.

> 🧠 **Mental model:** a trie is the "obvious correct" data structure for routing — every path is a walk
> from the root. RegExpRouter is the "clever fast" structure. Hono keeps both because each wins a different
> race: TrieRouter never fails; RegExpRouter is faster when it can.

---

## 3.5 Case study 3 — RegExpRouter ★ (the one-regex trick)

`src/router/reg-exp-router/` — `router.ts` (252), `trie.ts` (74), `node.ts` (162), `matcher.ts` (33). This
is the centerpiece. The idea:

> **Compile *all* registered routes into a single `RegExp`.** Matching a request is then one `path.match()`
> call. Which route matched is read from *which capture group* fired.

### Registration defers the work

`add` (`src/router/reg-exp-router/router.ts:132`) does **not** build the regex. It just files each route
into `#middleware` / `#routes` maps keyed by method and path. The expensive compilation is deferred until
the first `match()`.

### First match triggers compilation

The `match` method (`src/router/reg-exp-router/matcher.ts:10`) is doing something sneaky on its first call:

```ts
export function match<R, T>(this: R, method, path): Result<T> {
  const matchers = this.buildAllMatchers()   // compile, ONCE   ← :12

  const match = ((method, path) => {          // the real, fast matcher
    const matcher = matchers[method] || matchers[METHOD_NAME_ALL]
    const staticMatch = matcher[2][path]       // O(1) static-route map  ← :18
    if (staticMatch) return staticMatch
    const m = path.match(matcher[0])           // THE ONE REGEX           ← :23
    if (!m) return [[], emptyParam]
    const index = m.indexOf('', 1)             // which group fired?      ← :27
    return [matcher[1][index], m]
  })

  this.match = match                           // self-replace!           ← :31
  return match(method, path)
}
```

Two beautiful tricks here:

1. **Self-replacing method (`:31`).** On the first call it compiles, then *overwrites `this.match`* with
   the fast closure. Every subsequent request skips compilation entirely — no `if (built)` check on the hot
   path, because the function literally rewrites itself out of existence.
2. **Static fast path (`:18`).** Purely static routes (`/health`, `/api/users`) are kept in a plain object
   `matcher[2]` for O(1) lookup, *before* the regex even runs. Static-heavy APIs barely touch the regex.

### Building the one regex

`buildAllMatchers` (`src/router/reg-exp-router/router.ts:208`) compiles one matcher per HTTP method, then
**releases the route maps** to free memory — after which adding a route throws "matcher is already built".
The heavy lifting is `buildMatcherFromPreprocessedRoutes` (`src/router/reg-exp-router/router.ts:34`):

1. It feeds every path into a `Trie` (`src/router/reg-exp-router/trie.ts`).
2. `trie.buildRegExp()` (`src/router/reg-exp-router/trie.ts:49`) walks that trie via
   `Node.buildRegExpStr()` (`src/router/reg-exp-router/node.ts:135`) and emits **one regex string** built
   from the routing tree, with embedded marker tokens:
   - `#N` marks "handler N matches here" — a param node emits `(${pattern})@varIndex`
     (`src/router/reg-exp-router/node.ts:142`).
   - A post-processing `replace` (`trie.ts:59`) rewrites each `#N` marker into an **end-anchored empty
     capture group `$()`**, recording in `indexReplacementMap` which capture-group position maps to which
     handler.

So for routes `/foo` (handler 0) and `/posts/:id` (handler 1), you get one regex shaped roughly like:

```text
^(?:foo$()|posts/([^/]+)$())
        └─ empty group #1 → handler 0
                         └─ empty group #2 → handler 1, with ([^/]+) capturing :id
```

When a path matches, `m.indexOf('', 1)` (`matcher.ts:27`) finds the *first empty string* in the match
array — that's the empty marker group that fired — and its index tells you the handler. **One regex test,
constant-ish time, no matter how many routes you registered.** That is the whole trick.

### When the trick fails

A single regex can't disambiguate every routing table. Two routes whose params collide at the same
position — e.g. `/:user/entries` and `/entry/:name`, where `/entry/entries` is genuinely ambiguous — can't
be encoded as one unambiguous regex. When `Node.insert` detects such a conflict it throws `PATH_ERROR`,
which `buildMatcherFromPreprocessedRoutes` converts into `UnsupportedPathError`
(`src/router/reg-exp-router/router.ts` in the `trie.insert` try/catch). RegExpRouter does **not** degrade
gracefully — it refuses. That refusal is a feature, because of the next case study.

---

## 3.6 Case study 4 — SmartRouter (the default)

`src/router/smart-router/router.ts` (70 lines). This is the router `new Hono()` actually uses (recall
`src/hono.ts:31`: `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`).

- `add` (`src/router/smart-router/router.ts:13`) just queues `[method, path, handler]` — it doesn't commit
  to a router yet.
- `match` (`src/router/smart-router/router.ts:21`) runs a **tournament** on the first request:

```ts
for (; i < len; i++) {
  const router = routers[i]
  try {
    for (…) router.add(...routes[i])      // replay all routes into this candidate
    res = router.match(method, path)       // try to match
  } catch (e) {
    if (e instanceof UnsupportedPathError) continue   // ← fall back to next router
    throw e
  }
  this.match = router.match.bind(router)   // winner! self-replace            (:46)
  this.#routers = [router]                  // discard the losers
  this.#routes = undefined                  // free the queue
  break
}
```

It tries `RegExpRouter` first. If that throws `UnsupportedPathError` (the §3.5 refusal), it `continue`s to
`TrieRouter`, which never refuses. Once a router succeeds, SmartRouter **binds `this.match` to the
winner** (`src/router/smart-router/router.ts:46`) and drops the rest — so, like RegExpRouter, every later
request skips the tournament entirely.

> 🧠 **Mental model:** SmartRouter is "optimistic with a safety net." It bets on the fast router, and the
> `UnsupportedPathError` is the signal that says "your routes are too ambiguous for the trick — use the
> general one." You pay the tournament cost *once*. This is why you rarely think about Hono's router at
> all: the default quietly gives you RegExpRouter speed when your routes allow it, and TrieRouter
> correctness when they don't.

---

## 3.7 Presets: choosing a different default

Two presets swap the router for different trade-offs (read both — they're ~20 lines each):

- `hono/quick` (`src/preset/quick.ts:13`) — `SmartRouter([LinearRouter, TrieRouter])`. No regex build:
  optimized for environments that handle **one request per worker** (classic FaaS cold starts), where
  build cost would never amortize.
- `hono/tiny` (`src/preset/tiny.ts:11`) — `PatternRouter` alone (`src/router/pattern-router/router.ts`,
  60 lines: one regex *per route*). The smallest code size — for bundle-size-critical deploys.

The base `hono` import is tuned for long-lived servers/Workers that handle many requests, so amortizing a
one-time regex build is the right call.

| Preset | Routers | Best for |
|--------|---------|----------|
| `hono` (default) | Smart(RegExp, Trie) | long-lived servers / Workers — amortized speed |
| `hono/quick` | Smart(Linear, Trie) | one-shot FaaS — no build cost |
| `hono/tiny`  | Pattern | smallest bundle |

---

## 3.8 Lab 3 — watch SmartRouter pick a router

`SmartRouter.name` updates to record its winner (`src/router/smart-router/router.ts` sets
`SmartRouter + <winner>`). Exploit that to *see* the fallback happen:

```ts
// router-probe.ts
import { RegExpRouter } from 'hono/router/reg-exp-router'
import { TrieRouter } from 'hono/router/trie-router'
import { SmartRouter } from 'hono/router/smart-router'

function probe(label: string, register: (r: SmartRouter<string>) => void) {
  const r = new SmartRouter<string>({ routers: [new RegExpRouter(), new TrieRouter()] })
  register(r)
  r.match('GET', '/x')                 // force the tournament
  console.log(label, '→', r.name)
}

probe('clean routes', (r) => { r.add('GET', '/users/:id', 'h') })
probe('ambiguous   ', (r) => {
  r.add('GET', '/:user/entries', 'a')
  r.add('GET', '/entry/:name', 'b')
})
```

```bash
bun run router-probe.ts
```

> 🧪 **Record in `labs/lab3-router.md`:** the two printed router names. Expected: the clean table resolves
> to `SmartRouter + RegExpRouter`, while the ambiguous table forces `SmartRouter + TrieRouter`. You've just
> watched `UnsupportedPathError` trigger the fallback from §3.6 — the single most important control-flow in
> Hono's routing.

---

## 3.9 Checkpoint

1. State the `Router<T>` interface from memory. Why is it generic in `T`?
2. In one sentence: what does `RegExpRouter` do that the other routers don't?
3. What are the two "tricks" in `matcher.ts` — the self-replacing method and the static map — and what does
   each save?
4. When the merged regex matches, how does Hono know *which* route matched? (Name the marker and the line.)
5. What does `UnsupportedPathError` signal, who throws it, and who catches it?
6. Which router does `new Hono()` use by default, and which does `hono/quick` use — and why the difference?

> If #2 or #4 is shaky, re-read §3.5. If #5 is shaky, re-read §3.5–§3.6 together — the throw and the catch
> are two halves of one idea.

---

## 🔌 Connect to your past (temlet web→native)

Next.js's router is a black box: file-system conventions compiled by the framework, with performance you
can't see or reason about. You trust it works. Hono hands you the opposite — a router you can *read in an
afternoon* and whose performance model you can explain.

That matters for temlet's web→native journey in a specific way. On the edge (Workers), request latency is
dominated by cold starts and per-request overhead — exactly what RegExpRouter's precompile-once + static
fast-path optimizes, and exactly what `hono/quick` trades away when you're one-shot. Behind a **Tauri**
shell, where the server is long-lived and local, you'd want the default's amortized speed. The lesson
isn't "Hono is fast"; it's that the router's strategy is a *knob you control*, chosen for the runtime
you're targeting. When you port temlet's routing onto something like this, you stop hoping the framework
made the right call and start making it yourself — per deployment target.

**Next:** [Chapter 4 — Context & Building Responses →](04-context-and-responses.md)
