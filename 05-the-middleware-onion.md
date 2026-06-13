# Chapter 5 — The Middleware Onion

> **Goal:** Read `src/compose.ts` end to end and understand the middleware "onion" precisely — how `await
> next()` builds the layered structure, why ordering works the way it does, and exactly where errors and
> 404s are caught. After this chapter you can predict the run order of any middleware stack. Grounded in
> `honojs/hono` at **`v4.12.25`** (`fce483e`).

---

## 5.1 Why it matters

Middleware is where most real framework bugs live: "why did this run before that?", "why didn't my error
handler fire?", "why is the response empty?". Almost all of these are misunderstandings of the *onion* —
the fact that each middleware runs in two phases, before and after `next()`, wrapped around the inner
layers. The remarkable thing about Hono is that the entire mechanism is **one 73-line file** with no
hidden state. If you can read `compose.ts`, you can answer every middleware question definitively.

---

## 5.2 Mental model: the onion

Given `app.use(A); app.use(B); app.get('/', H)`, the runtime structure is:

```text
        request ──►┌─────────────── A ───────────────┐
                   │  A: before next()                │
                   │   ┌──────────── B ─────────────┐ │
                   │   │  B: before next()           │ │
                   │   │   ┌───────── H ──────────┐  │ │
                   │   │   │  handler runs,        │  │ │
                   │   │   │  builds the Response  │  │ │
                   │   │   └───────────────────────┘  │ │
                   │   │  B: after next()            │ │
                   │   └─────────────────────────────┘ │
                   │  A: after next()                  │
        response ◄─└───────────────────────────────────┘
```

Code *before* `await next()` runs on the way **in** (outer→inner). Code *after* `await next()` runs on the
way **out** (inner→outer). The handler `H` is the core of the onion. This is the koa model, and `compose.ts`
implements it in the most literal possible way.

---

## 5.3 The whole algorithm, read line by line

`compose` (`src/compose.ts:15`) takes the matched handler list and returns a function. The magic is the
nested recursive `dispatch` (`src/compose.ts:32`). Read it once, slowly:

```ts
export const compose = (middleware, onError?, onNotFound?) => {
  return (context, next) => {
    let index = -1
    return dispatch(0)                                   // :23 — start the onion

    async function dispatch(i) {
      if (i <= index) throw new Error('next() called multiple times')  // :33 — guard
      index = i

      let res, isError = false, handler
      if (middleware[i]) {
        handler = middleware[i][0][0]                    // :43 — the i-th handler
        context.req.routeIndex = i
      } else {
        handler = (i === middleware.length && next) || undefined  // :46 — past the end
      }

      if (handler) {
        try {
          res = await handler(context, () => dispatch(i + 1))   // :51 — run it, give it next
        } catch (err) {
          if (err instanceof Error && onError) {
            context.error = err
            res = await onError(err, context)            // :55 — error path
            isError = true
          } else { throw err }
        }
      } else {
        if (context.finalized === false && onNotFound) {
          res = await onNotFound(context)                // :63 — 404 path
        }
      }

      if (res && (context.finalized === false || isError)) {
        context.res = res                                // :68 — commit the response
      }
      return context
    }
  }
}
```

### The one line that builds the onion

Everything hinges on `src/compose.ts:51`:

```ts
res = await handler(context, () => dispatch(i + 1))
```

The handler is given a `next` function that is *literally* `() => dispatch(i + 1)` — "run the next layer."
When your middleware calls `await next()`, it **pauses inside its own function body** and runs the entire
rest of the onion (all deeper layers, including the handler) to completion. Only when that returns does
your code after `await next()` resume. That's the whole onion: it's just a recursive call you `await` in
the middle of a function.

### The guard

`src/compose.ts:33` — `if (i <= index) throw 'next() called multiple times'`. Each layer may descend
*once*. Calling `next()` twice in one middleware would re-enter a layer that already ran, so it throws.
`index` is a monotonic high-water mark.

### Reaching the end

When `i` runs past the registered middleware (`src/compose.ts:46`), `handler` becomes the optional outer
`next` (for nested composition) or `undefined`. If it's `undefined` and nothing has produced a response
(`src/compose.ts:62`), `onNotFound` runs — that's how an unmatched route yields a 404.

---

## 5.4 Errors and 404s: where they're caught

This is the part everyone gets wrong, so be precise:

- **Errors** (`src/compose.ts:52`): the `try/catch` wraps the `await handler(...)` call. Because `next()`
  is `dispatch(i+1)` and you `await` it, **a throw deep in the onion propagates up through every awaiting
  layer** — and is caught at the *first* layer that's inside this try. The `onError` handler
  (`src/compose.ts:55`) runs, sets `context.error`, and its return becomes the response. A non-`Error`
  throw, or no `onError`, re-throws (`src/compose.ts:58`).
- **404s** (`src/compose.ts:62`): only when no handler matched *and* nothing finalized a response.

Recall where `onError` and `onNotFound` come from: `#dispatch` passes `this.errorHandler` and
`this.#notFoundHandler` into `compose` (`src/hono-base.ts:450`), and those default to the handlers at
`src/hono-base.ts:31` (404) and `src/hono-base.ts:35` (error). You override them with `app.onError(...)`
(`src/hono-base.ts:271`) and `app.notFound(...)` (`src/hono-base.ts:291`).

### The finalized check

`src/compose.ts:67` — `if (res && (context.finalized === false || isError)) context.res = res`. A returned
response is only committed if the context isn't already finalized (or this is the error path). This is the
link back to §4.5: `c.finalized` (`src/context.ts:317`) is the bit that prevents an outer middleware from
clobbering a response an inner layer already committed.

> 💡 **Tip:** the fast path from §1.4 (`src/hono-base.ts:430`) *skips `compose` entirely* when only one
> handler matched. So the onion only exists when you actually have middleware. A bare `app.get('/', h)`
> with no `use()` never allocates a single `dispatch` closure.

---

## 5.5 Predicting run order

Apply the model. For:

```ts
app.use(async (c, n) => { console.log('A in');  await n(); console.log('A out') })
app.use(async (c, n) => { console.log('B in');  await n(); console.log('B out') })
app.get('/', (c) => { console.log('H'); return c.text('ok') })
```

The output is:

```text
A in
B in
H
B out
A out
```

`A in → B in` (outer→inner, before `next`), then `H`, then `B out → A out` (inner→outer, after `next`).
If `H` threw, the throw would unwind through `B`'s and `A`'s `await n()` calls to `onError`. If you forgot
`await` on `next()`, `A out` could print *before* `H` finished — the classic async-middleware bug.

---

## 5.6 Lab 5 — see the onion unwind, and break it

```ts
// onion.ts
import { Hono } from 'hono'
const app = new Hono()
const log: string[] = []

app.use(async (c, n) => { log.push('A in'); await n(); log.push('A out') })
app.use(async (c, n) => { log.push('B in'); await n(); log.push('B out') })
app.get('/', (c) => { log.push('H'); return c.text('ok') })
app.get('/boom', () => { throw new Error('kaboom') })
app.onError((err, c) => c.text(`caught: ${err.message}`, 500))

await app.request('/')
console.log('order:', log.join(' → '))

const boom = await app.request('/boom')
console.log('error:', boom.status, await boom.text())
```

```bash
bun run onion.ts
```

> 🧪 **Record in `labs/lab5-onion.md`:** the order string and the error line. Expected: `A in → B in → H →
> B out → A out`, then `500 caught: kaboom`. Now *remove* the `await` from one `n()` and re-run — note how
> the `out` lines reorder. You've just reproduced the most common middleware bug in the wild, and you can
> explain it from `src/compose.ts:51`.

---

## 5.7 Checkpoint

1. Draw the onion for `use(A); use(B); get(H)` and give the exact console order.
2. What is `next`, literally, in `compose.ts`? Quote the line.
3. Why does calling `next()` twice throw, and which line enforces it?
4. Where exactly is an error thrown by the handler caught, and what makes it propagate up through the
   middleware?
5. What does the `c.finalized` check at `compose.ts:67` prevent?
6. When is `compose` *not* called at all?

> If #2 or #4 is shaky, re-read §5.3–§5.4. If #6 is shaky, re-read §5.4's tip and §1.4.

---

## 🔌 Connect to your past (temlet web→native)

You already know this shape — you just know it as React's `useEffect` cleanup, or Express's
`(req, res, next)`, or Next's `middleware.ts`. But Next's middleware is *flat*: it runs before your route
and can rewrite/redirect, but it has no "after" phase wrapped around your handler. Hono's onion gives you
both halves in one mental model — and you can *see* the mechanism, because it's 73 lines, not a framework
internal.

That visibility pays off when temlet crosses into Tauri. Cross-cutting concerns you currently scatter
across Next middleware, route wrappers, and React effects — request logging, auth, timing, error shaping —
collapse into composable `(c, next)` functions that run identically on the edge and behind the native
shell. And because `compose` is just `await`ed recursion, your async cleanup ("after next()") behaves
predictably, instead of the subtle ordering surprises you hit when React effect cleanup and server
middleware disagree about when "after" is. When you port temlet, treat each cross-cutting concern as one onion layer
and you'll delete a surprising amount of glue.

**Next:** [Chapter 6 — Runtime Adapters & Portability →](06-runtime-adapters-and-portability.md)
