# hono-hello

The minimal runnable Hono app used across the labs in the [Hono Internals Handbook](../../README.md).
Pinned to `hono@4.12.25` to match the book's source citations.

## Run

```bash
bun install
bun run dev        # serves http://localhost:3000

# in another shell:
curl -s localhost:3000/                ; echo   # → Hono!
curl -s localhost:3000/users/42        ; echo   # → {"id":"42","reqId":"…"}
curl -si localhost:3000/ | grep -i 'x-request-id\|server-timing'   # the middleware headers
```

Prefer Node? Add [`@hono/node-server`](https://github.com/honojs/node-server) and a `serve(app)` entry,
or run on Deno — the `index.ts` app object is identical (Chapter 6).

## What each part demonstrates

| Code | Chapter | Concept |
|------|---------|---------|
| `new Hono<{…}>()` | 2 | the App object + typed `Env` |
| `app.use('*', …)` with `await next()` | 5 | the middleware onion (before/after) |
| `app.get('/users/:id', …)` | 3 | the router + a typed path param |
| `c.set` / `c.get`, `c.json`, `c.res.headers` | 4 | the Context: state + response building |
| `export default app` | 6 | runtime portability (a Hono app *is* a `{ fetch }`) |

## Probes

The chapter labs ask you to drop small probe files beside `index.ts` (e.g. `router-probe.ts` in Chapter 3,
`onion.ts` in Chapter 5) and run them with `bun run <file>.ts`. Keep your filled-in results in the parent
`labs/labN-*.md` notes.
