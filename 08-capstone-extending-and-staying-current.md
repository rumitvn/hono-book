# Chapter 8 — Capstone: Extending & Staying Current

> **Goal:** Put it all together. Write a custom middleware and your own router preset, read a real merged
> Hono PR unaided, and learn the workflow to re-sync this book when you bump the pin. Grounded in
> `honojs/hono` at **`v4.12.25`** (`fce483e`).

---

## 8.1 Why it matters

You've read the five layers from the inside. The test of understanding is *building* on them and *reading*
new changes to them without a guide. This chapter is that test — and it doubles as the maintenance manual
for the book itself, since Hono moves fast and your pin will eventually drift.

---

## 8.2 Capstone part 1 — a custom middleware

You already know everything you need: middleware is a `(c, next)` function (Chapter 5), `c.res` is the
committed response (Chapter 4), and built-ins live in `src/middleware/`. Read the *simplest* built-in,
`poweredBy` (`src/middleware/powered-by/index.ts:30`), as your template:

```ts
export const poweredBy = (options?) => {
  return async function poweredBy(c, next) {
    await next()                                              // descend the onion first
    c.res.headers.set('X-Powered-By', options?.serverName ?? 'Hono')  // then tweak the response
  }
}
```

Notice the shape: a factory that returns a `MiddlewareHandler` (`src/types.ts:83`), and it does its work
**after `await next()`** — the "on the way out" phase from §5.2. Now write your own: a server-timing
middleware that measures handler duration and sets a header.

```ts
// timing-mw.ts
import { Hono } from 'hono'
import type { MiddlewareHandler } from 'hono'

const serverTiming = (): MiddlewareHandler => async (c, next) => {
  const start = performance.now()
  await next()                                  // run the rest of the onion
  const ms = (performance.now() - start).toFixed(1)
  c.res.headers.set('Server-Timing', `app;dur=${ms}`)   // post-next: mutate committed response (§4.5)
}

const app = new Hono()
app.use(serverTiming())
app.get('/', async (c) => { await new Promise((r) => setTimeout(r, 20)); return c.text('ok') })

const res = await app.request('/')
console.log(res.headers.get('Server-Timing'))   // expect app;dur=~20
export default app
```

Every design choice here traces to an earlier chapter: it's a layer in the onion (Ch 5), it sets a header
after the response is finalized (Ch 4), and it works on any runtime because it touches only `Response`
(Ch 6). That's the whole framework, used.

---

## 8.3 Capstone part 2 — your own preset

A preset is just a `Hono` subclass that picks a router (§3.7). Read `src/preset/tiny.ts:11` — it's ~20
lines. Build one that forces `RegExpRouter` alone (no fallback) so you get an immediate
`UnsupportedPathError` on ambiguous routes — useful as a lint in CI to catch routes that would silently
fall back to the slower TrieRouter:

```ts
// strict-preset.ts
import { HonoBase } from 'hono/hono-base'          // the engine (§2.2)
import { RegExpRouter } from 'hono/router/reg-exp-router'

export class StrictHono extends HonoBase {
  constructor(options = {}) {
    super(options)
    this.router = new RegExpRouter()   // no SmartRouter, no TrieRouter fallback
  }
}
```

Now any route table that can't be expressed as one regex throws at first match instead of quietly
degrading — exactly the §3.5 refusal, surfaced as a guardrail. You've turned an internal error signal into
a design constraint you can enforce.

> 💡 **Tip:** this is the same mechanism the official `tiny`/`quick` presets use. Reading `src/preset/`
> proved that "swap the router" is a supported extension point, not a hack.

---

## 8.4 Read a real PR unaided

Time to read upstream changes the way a maintainer does. Open a recent merged PR — for example
**#5013, "fix(lambda-edge): satisfy Deno lib types for Content-Length body encoding"** (merged 2026-06-09):

```bash
gh pr view 5013 --repo honojs/hono
gh pr diff 5013 --repo honojs/hono
```

As you read, locate it in your mental model:

1. **Which layer?** The path `src/adapter/lambda-edge/` tells you instantly: this is the **Adapter** layer
   (Chapter 6), not the core. A core router/compose change would touch `src/router/` or `src/compose.ts`.
2. **What contract does it preserve?** Adapters translate a runtime's native shape to/from
   `Request`/`Response`. A `Content-Length`/body-encoding fix is the adapter getting the `Response`
   translation right for one runtime — the core is untouched, which is the whole point of §6.2.
3. **Where are the tests?** Hono changes ship with tests; the `*.test.ts` beside the file is where the
   behavior is pinned.

> 🧪 **Record in `labs/lab8-pr.md`:** pick any recently merged PR, and in 3–4 sentences state which of the
> five layers it touches and which contract it preserves or changes. If you can place it without help, you
> understand the architecture. (Try one core PR and one adapter PR for contrast.)

---

## 8.5 Staying current — re-syncing the book

Hono releases often. When you bump the pin, citations drift. The workflow:

```bash
# 1. Find the new latest tag and re-pin the clone
gh api repos/honojs/hono/tags --jq '.[0].name'
cd ../hono && git fetch --tags && git checkout <new-tag>
git log -1 --format='%h'        # record the new short SHA

# 2. Update the book's pin in ONE place
#    site_src/build_site.py → PINNED = "<new-tag>"   (and the SHA comment)

# 3. Re-verify the citations that matter most (they're listed in reference/glossary.md "Key files")
sed -n '419p' src/hono-base.ts        # should still be router.match(...)
sed -n '10p'  src/router/reg-exp-router/matcher.ts   # should still be the match() entry
# …spot-check the Key-files table; fix any line numbers that moved

# 4. Rebuild and screenshot
cd ../hono-book && python3 site_src/build_site.py
```

> ⚠️ The single most fragile thing across a version bump is **line numbers**, not concepts. The *shape* of
> Hono (five layers, four routers, the onion) is stable release to release; the line a symbol sits on is
> not. The glossary's "Key files" table is your re-verification checklist — work through it after every
> re-pin.

---

## 8.6 Final checkpoint — the whole book

1. Trace a request from `app.fetch()` to a `Response`, naming the file for each of the five layers.
2. Explain the RegExpRouter trick and when SmartRouter falls back — the single most important idea in Hono.
3. Give the console order for a two-middleware onion, and say where an error would be caught.
4. Explain how the same app runs on Workers and Bun without code changes (`env()` + adapters).
5. Explain how `/users/:id` becomes a typed `hc` client call with no codegen.
6. Write a middleware that runs logic *before* and *after* the handler, and say why it's portable.

> If any of these is shaky, the chapter to re-read is named in the question. This is the book in six
> sentences — if you can answer all six, you understand `honojs/hono`.

---

## 🔌 Connect to your past (temlet web→native)

You started this book carrying temlet from Next.js toward Tauri, with a server layer married to Node. You
end it with a different option on the table: an HTTP layer that is *runtime-agnostic by construction* — one
that runs on the edge today, behind a native shell tomorrow, with typed clients on both sides and
cross-cutting logic expressed as composable onion layers.

The deeper takeaway isn't "use Hono." It's the *discipline* Hono demonstrates: build on the platform's own
contracts (`Request`/`Response`), push everything runtime-specific to a thin, swappable edge (the
adapters), and let types — not codegen — carry your API across boundaries. That's the same discipline that
makes a web→native migration tractable instead of a rewrite. Whatever you choose for temlet's backend, you
now know what "portable by design" actually looks like in source — and you can read the next edge framework
that comes along by the same five-layer light.

**Done.** Re-read the [flagship router chapter](03-the-router.md) once more — it rewards a second pass — and
keep `../hono` open. The book stays useful as a map every time you open the source.

*A RumitX publication · [rumitx.com](https://rumitx.com)*
