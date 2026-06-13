# Labs

Hands-on counterparts to each chapter. Run them with **Bun** (`bun run …`) — or Node/Deno where noted —
beside the pinned clone in `../hono`. Nothing here needs a server you can't kill with Ctrl-C, and several
labs use Hono's server-less `app.request(...)` test entrypoint so you don't even need a port.

## What's here

- **`dev-baseline.md`** — the baseline template you fill in once during Chapter 0 (your Bun/Node version,
  the pin SHA, the green-build result) and reference throughout.
- **`hono-hello/`** — a minimal runnable Hono app (one app, a couple of routes, a custom middleware). It's
  the artifact every later lab builds on: copy a probe file into it and `bun run` it.

## How labs work

Each chapter ends with a lab and tells you to record results in a `labN-*.md` file here (e.g.
`lab3-router.md`). Create that file, paste the command + its **expected** observation + what you actually
saw, and note any surprise. Those notes are the proof points in the README's progress checklist.

Suggested files (create as you go):

```text
labs/
├── lab0-setup.md        # the pin, Bun version, green build, first curl
├── lab1-trace.md        # the request trace with a logging middleware
├── lab2-app.md          # app.routes + the app.request() test entrypoint
├── lab3-router.md       # SmartRouter picking RegExp vs Trie     ← the big one
├── lab4-context.md      # buffered headers + the c.set/c.get handoff
├── lab5-onion.md        # middleware run order + error catch
├── lab6-adapters.md     # the SAME app on two runtimes
├── lab7-types.md        # ParamKeys → ToSchema → hc, end to end
└── lab8-pr.md           # a real merged PR placed in the layer model
```

## Bootstrap the artifact

```bash
cd labs/hono-hello
bun install
bun run dev          # serves http://localhost:3000
# then drop a probe file (e.g. router-probe.ts from Ch 3) beside index.ts and: bun run router-probe.ts
```
