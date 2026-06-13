# Understanding `hono`

### A from-the-source book on Hono internals

> A self-paced, hands-on study guide that turns the `honojs/hono` repository into something you
> genuinely *understand* — not just `new Hono()` and `app.get()`.

---

## Who this book is for (you)

You've shipped web frameworks for years. You've written Next.js API routes and middleware, wired up
**temlet** as a Next.js app, and you're now carrying it across the **web→native** seam into **Tauri** —
where the same product logic has to run behind a native shell instead of a Node server. Along the way
you've met Hono: the tiny router that turns up inside Cloudflare Workers, Bun, Deno, and edge functions,
the framework whose whole job is to be *the same* no matter what runtime it lands on.

That portability is not an accident, and it is not magic. It falls out of one disciplined decision:
**Hono speaks only the web platform's `Request` and `Response`**, and everything else — routing,
middleware, context, validation — is built on top of that one contract. Learn how that contract is
honored and you understand not just Hono, but the shape every modern edge framework is converging on.

This book opens the box. By the end you'll be able to take a request, predict the exact path it takes
from `app.fetch()` through the router and the middleware onion to a `Response`, point to the precise
`.ts` file and line where each layer does its work, and explain *why* the same `app` runs unchanged on
Workers, Bun, and a Tauri-adjacent server.

---

## What you'll be able to do

- **Trace a request end-to-end** — from `app.fetch(request)` through `router.match()`, `compose()`, the
  `Context`, and back out as a `Response`, naming every hop by `file:line`.
- **Explain the router** — why Hono ships *four* routers behind one interface, how `RegExpRouter` merges
  every route into a single regular expression, and how `SmartRouter` falls back when that trick can't apply.
- **Reason about middleware** — read `compose.ts` and predict the exact order code runs before and after
  `await next()`, and where errors and 404s are caught.
- **Port an app across runtimes** — understand the adapter seam and the `env()` / `getRuntimeKey()`
  helpers well enough to deploy the same code to Workers, Bun, Deno, or Node.
- **Read Hono's type magic** — how a path string like `/users/:id` becomes typed `c.req.param('id')`, and
  how the `hc` RPC client gets end-to-end types for free.

---

## How this book is built (the grounding contract)

Every claim is **grounded in source you can open**:

- 📌 **Pinned ref.** This book is written against Hono **`v4.12.25`** (commit `fce483e`). A read-only clone
  lives beside the book at `../hono`.
- 🔎 **`file:line` citations.** Every walkthrough cites exact locations like `src/hono-base.ts:419`. Open
  the clone and read along — the line numbers resolve to the symbol described.
- 🧪 **Labs you run.** Each chapter ends with a small lab you run yourself with **Bun** (or Node), with a
  stated *expected* result you record in `labs/`.

> ⚠️ When you re-pin to a newer Hono tag, line numbers will drift. Chapter 8 shows you how to re-sync.

---

## The curriculum

Nine chapters, **00–08**, with **Chapter 03 (the Router) as the flagship** — the deepest chapter, where
the "how does this actually work" core lives.

| # | Chapter | Weight |
|---|---------|--------|
| 00 | Environment & TypeScript / Web-standards refresher | Foundation |
| 01 | Mental model & repo map | Foundation |
| 02 | The App object & HonoRequest | Foundation |
| 03 | **★ The Router** | **Flagship** |
| 04 | Context & building responses | Core |
| 05 | The middleware onion | Core |
| 06 | Runtime adapters & portability | Application |
| 07 | Typed routes, the RPC client & validation | Application |
| 08 | Capstone: extending & staying current | Mastery |

Depth is intentionally weighted toward **03**. The router is where Hono earns its reputation, and it
rewards the deepest read.

---

## Per-chapter shape

Every chapter follows the same rhythm:

1. **Goal** — one paragraph, with the pinned ref.
2. **Why it matters** — the problem this layer solves.
3. **Mental model + ASCII diagram** — a picture to hold in your head.
4. **Guided source read** — exact `file:line` citations into `../hono`.
5. **Lab** — commands you run, with an expected observation, recorded in `labs/`.
6. **Checkpoint** — 4–6 questions; if one is shaky, it points you back to the section to re-read.
7. **🔌 Connect to your past** — a bridge from the concept to your temlet / Next.js→Tauri / web→native work.

---

## Pace

This is a two-to-three week book if you do the labs. A reasonable cadence:

- **Days 1–2:** Chapters 00–01 (setup + mental model).
- **Days 3–4:** Chapter 02 (the app & request).
- **Days 5–8:** Chapter 03 — the flagship. Don't rush it.
- **Days 9–12:** Chapters 04–05 (context + middleware).
- **Days 13–16:** Chapters 06–07 (adapters + types).
- **Days 17+:** Chapter 08 (capstone) and a re-read of anything shaky.

---

## Progress checklist

- [ ] 00 — green build, Fetch API + TS generics refreshed
- [ ] 01 — traced one request end-to-end
- [ ] 02 — explained route registration and `fetch`
- [ ] 03 — explained all four routers and the RegExpRouter trick ★
- [ ] 04 — explained how `c.json()` becomes a `Response`
- [ ] 05 — predicted middleware run order around `next()`
- [ ] 06 — ran the same app on two runtimes
- [ ] 07 — explained how `:id` becomes a typed param
- [ ] 08 — read a real Hono PR unaided

---

## Layout

```text
hono-book/
├── README.md                 ← you are here
├── 00..08-*.md               ← the nine chapters (03 is the flagship)
├── labs/                     ← lab notes + a runnable hono-hello artifact
│   ├── README.md
│   ├── dev-baseline.md
│   └── hono-hello/
├── reference/glossary.md     ← terms by category + a Key-files source index
├── diagrams/                 ← (placeholder)
└── site_src/build_site.py    ← the static-site generator (RumitX kit)
```

The companion clone is at `../hono`, pinned to `v4.12.25`. Keep it open.

**Start:** [Chapter 0 — Environment & TypeScript / Web-standards Refresher →](00-environment-and-typescript-web-refresher.md)

---

*A RumitX publication · [rumitx.com](https://rumitx.com)*
