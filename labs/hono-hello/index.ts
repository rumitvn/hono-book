// hono-hello — the runnable artifact for the Hono Internals Handbook labs.
//
// Run it:   bun install && bun run dev   (serves http://localhost:3000)
// Probe it: curl -s localhost:3000/ ; curl -s localhost:3000/users/42
//
// This single file exercises every layer you read about:
//   - route registration + the App object        (Ch 2)
//   - the Router resolving /users/:id             (Ch 3)
//   - a middleware onion via app.use(...)         (Ch 5)
//   - the Context building responses (c.json/text)(Ch 4)
//   - runtime portability (export default app)    (Ch 6)
import { Hono } from 'hono'

type Bindings = {}
type Variables = { reqId: string }

const app = new Hono<{ Bindings: Bindings; Variables: Variables }>()

// A middleware onion layer (Ch 5): runs before AND after the handler.
app.use('*', async (c, next) => {
  const reqId = Math.random().toString(36).slice(2, 8)
  c.set('reqId', reqId) // per-request state (Ch 4)
  const start = performance.now()
  await next() // descend into the rest of the onion
  c.res.headers.set('Server-Timing', `app;dur=${(performance.now() - start).toFixed(1)}`)
  c.res.headers.set('X-Request-Id', reqId)
})

app.get('/', (c) => c.text('Hono!'))

// A typed path param (Ch 3 routing, Ch 7 types): `id` is a string.
app.get('/users/:id', (c) => c.json({ id: c.req.param('id'), reqId: c.get('reqId') }))

export default app
