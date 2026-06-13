# Dev Baseline — Hono `v4.12.25` (commit `fce483e`)

Captured during Chapter 0 setup. Reference line for every later lab.

## Machine
- Device/CPU: **<fill in: e.g. Apple M-series, x86_64>**, OS **<fill in>**, arch **<fill in>**
- Primary runtime: **<fill: Bun | Node | Deno>**

## Versions & build
| measure | command | result |
|---------|---------|--------|
| pinned commit | `cd ../hono && git log -1 --format='%h %d'` | **<fill: fce483e (tag: v4.12.25)>** |
| Bun version | `bun --version` | **<fill: e.g. 1.2.19>** |
| Node version | `node --version` | **<fill: e.g. v24.7.0>** |
| green build | `cd ../hono && bun install && bun run test` | **<fill: pass / fail + first failure>** |

## First app (save it — later labs reuse it)
```ts
import { Hono } from 'hono'
const app = new Hono()
app.get('/', (c) => c.text('Hono!'))
app.get('/users/:id', (c) => c.json({ id: c.req.param('id') }))
export default app
```
| probe | command | result |
|-------|---------|--------|
| root | `curl -s localhost:3000/` | **<fill: Hono!>** |
| param | `curl -s localhost:3000/users/42` | **<fill: {"id":"42"}>** |

## Quick interpretation
- The pinned commit matching `fce483e` = your `file:line` citations will resolve.
- `bun run test` green = the whole framework compiles and its suite passes locally.
- `{"id":"42"}` with `42` as a **string** = the type-safe `:id` param (Ch 0/7) is in play.

## Reproduce
```bash
cd ~/Documents/learning/hono
git log -1 --format='%h %d'
bun install && bun run test
```

## TODO (fill in later chapters)
- [ ] Ch3: record which router SmartRouter picks for clean vs ambiguous routes in `lab3-router.md`.
- [ ] Ch5: record the `A in → B in → H → B out → A out` onion order in `lab5-onion.md`.
- [ ] Ch6: record `getRuntimeKey()` on two runtimes in `lab6-adapters.md`.
- [ ] Ch7: confirm the `@ts-expect-error` RPC type failure in `lab7-types.md`.
