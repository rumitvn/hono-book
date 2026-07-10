# Chapter 6 — Runtime Adapters & Portability

> **Goal:** Hiểu cái seam khiến *một* app Hono chạy y nguyên trên Cloudflare Workers, Bun, Deno,
> Node, và Lambda. Đọc các adapter, hàm dò `getRuntimeKey()`, helper `env()`, và làm quen với mấy
> helper streaming/SSE. Đây là chương **web→native bridge**. Neo vào `honojs/hono` tại
> **`v4.12.25`** (`fce483e`).

---

## 6.1 Vì sao quan trọng

Đây là chương giải thích lý do tồn tại của Hono. Mọi framework khác đều chọn sẵn một runtime — Express
chọn Node, Next chọn server riêng của nó, code Workers chọn `workerd`. Hono chọn *không cái nào*: lõi chỉ
biết `Request`/`Response` (Chương 0), và một **adapter** mỏng cho mỗi runtime lo việc dịch cái entry shape
gốc của runtime đó thành một lời gọi `fetch`. Hiểu cái seam này là hiểu vì sao cùng một đoạn code ship được
đi khắp nơi — và nó cũng chính là cơ chế bạn sẽ dựa vào khi mang temlet vượt qua ranh giới web→native.

---

## 6.2 Mental model: một lớp vỏ dịch mỏng

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

Mỗi runtime có một entry shape *gốc* khác nhau. Toàn bộ nhiệm vụ của adapter là nhào cái shape đó thành
`app.fetch(request, env, ctx)` rồi nhào ngược `Response` trả về. Lõi không bao giờ biết nó đang chạy trên
runtime nào.

> 🧠 **Mental model:** adapter là một *cục chuyển đầu phích cắm*, không phải một cục biến áp. Nó đổi hình
> dạng của đầu nối; nó không đổi dòng điện. App của bạn là cái thiết bị điện, và nó chạy giống hệt nhau ở
> mọi nơi.

---

## 6.3 Adapter đơn giản nhất: Cloudflare Workers

Với Workers, entry gốc của runtime *vốn đã* khớp với Hono: `export default { fetch(req, env, ctx) }`.
Nên bạn thậm chí chẳng cần import một adapter để chạy — chỉ cần `export default app`, bởi một app Hono *chính
là* một object `{ fetch }`. Entry point `hono/cloudflare-workers` (`src/adapter/cloudflare-workers/index.ts`)
chỉ thêm những *thứ phụ đặc thù cho runtime* mà không thể chuẩn-hoá-theo-web được:

```ts
// src/adapter/cloudflare-workers/index.ts
export { serveStatic } from './serve-static-module'   // :6 — serve from Workers' static assets
export { upgradeWebSocket } from './websocket'        // :7 — CF's WebSocket pair API
export { getConnInfo } from './conninfo'              // :8 — read cf-connecting-ip
```

`getConnInfo` (`src/adapter/cloudflare-workers/conninfo.ts`) chỉ một dòng — nó đọc client IP từ header
`cf-connecting-ip`. Đặt cạnh các adapter **Bun** và **Deno** (`src/adapter/bun/`,
`src/adapter/deno/`), mỗi cái có `conninfo.ts`, `serve-static.ts`, và `websocket.ts` *riêng*.
Cùng tên export, thân hàm đặc thù cho runtime. Cái bề mặt đồng nhất đó chính là adapter contract.

> 📁 Có chín adapter ship trong `src/adapter/`: `aws-lambda`, `bun`, `cloudflare-pages`, `cloudflare-workers`,
> `deno`, `lambda-edge`, `netlify`, `service-worker`, `vercel`. Cái nào cũng nhỏ — chỗ khéo nằm ở việc lõi
> *không* cần đến chúng.

---

## 6.4 Nhận diện runtime: `getRuntimeKey()`

Khi code *thật sự* cần rẽ nhánh theo runtime, Hono tự dò chứ không bắt bạn khai báo. Đọc
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

Type `Runtime` (`src/helper/adapter/index.ts:8`) là tập đóng:
`'node' | 'deno' | 'bun' | 'workerd' | 'fastly' | 'edge-light' | 'other'`. Việc dò ưu tiên
**`navigator.userAgent` chuẩn hoá** (mà Deno, Bun, Workers, và Node hiện đại đều điền vào —
`knownUserAgents` map `'Cloudflare-Workers' → 'workerd'`, v.v.), và chỉ lùi về các global đặc thù cho
runtime như `EdgeRuntime` hay `process` khi cần. Bản thân điều này đã là một thiết kế web-standards-first:
dò bằng tín hiệu chuẩn, rồi hạ dần xuống mấy phép kiểm tra riêng của từng vendor.

---

## 6.5 Đường nối `env()`: nơi platform bước vào

`c.env` (Chương 4) là các binding của runtime — nhưng *`env` là cái gì* lại khác nhau tuỳ runtime, và cái
khác biệt đó được gom vào một helper duy nhất. Đọc `env()` (`src/helper/adapter/index.ts:10`):

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

Đây là toàn bộ phần lời của portability, gói trong một cái bảng. Trên Node/Bun, `env(c)` đọc `process.env`.
Trên Deno, nó gọi `Deno.env.toObject()`. Trên Workers, nó trả về `c.env` (các binding mà platform đã inject).
Code của bạn viết `env(c).DATABASE_URL` *một lần* và nó resolve đúng ở mọi nơi — bạn không bao giờ phải viết
`process.env` (thứ không tồn tại trên Workers) hay `Deno.env` (thứ không tồn tại trên Node).

> 💡 **Tip:** đây chính là dependency injection ngay tại ranh giới runtime. Framework hỏi môi trường
> "secret/binding của tôi là gì?" và mỗi runtime trả lời bằng thổ ngữ của riêng nó. Handler của bạn vẫn
> nói đúng một thứ tiếng.

---

## 6.6 Streaming & SSE: vẫn chỉ là `Response`

Các response sống lâu (streaming, server-sent events) là chỗ bạn dễ tưởng sẽ cần code đặc thù cho runtime —
vậy mà Hono vẫn giữ chúng chuẩn-web. Các helper streaming (`src/helper/streaming/index.ts`) export ra:

- `stream(c, cb)` — ghi vào một `Response` được backed bằng `ReadableStream`.
- `streamSSE(c, cb)` — server-sent events; shape `SSEMessage` là `{ data, event?, id?, retry? }`
  (`src/helper/streaming/sse.ts:6`).
- `streamText(c, cb)` — text chia chunk.

Cả ba đều build một `Response` mà body là một stream — vẫn cái `Response` từ Chương 0, chỉ khác là body dạng
streaming. Vì `ReadableStream` là một web standard, cái này chạy y hệt trên Workers, Bun, và Deno mà không
cần rẽ nhánh cho từng runtime.

---

## 6.7 Lab 6 — một app, hai runtime

Chứng minh portability bằng cách chạy *cùng một* file app trên hai runtime. Tái dùng `hono-hello`:

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

> 🧪 **Record in `labs/lab6-adapters.md`:** giá trị `runtime` mà mỗi runtime bạn thử báo về (ví dụ
> `"bun"`, `"deno"`), và xác nhận `GREETING` resolve được trên từng cái qua đường nối `env(c)` ở §6.5 — *mà*
> file app không hề import một module đặc thù cho runtime nào. Cái tính chất "không import runtime trong file
> app" đó chính là cả chương gói lại trong một quan sát.

---

## 6.8 Checkpoint

1. Entry point phổ quát mà mọi adapter nhắm tới là gì? Adapter thật ra *làm* cái gì?
2. Vì sao một Cloudflare Worker chỉ cần `export default app` mà không import adapter nào?
3. `getRuntimeKey()` dò runtime bằng cách nào, và nó ưu tiên tín hiệu nào hơn các global của vendor?
4. Đi qua `env(c)` trên Workers so với Node — mỗi cái trả về gì, và vì sao điều đó giữ cho code của bạn
   runtime-agnostic?
5. Vì sao streaming và SSE *không* cần adapter riêng cho từng runtime?

> Nếu #4 còn lung lay, đọc lại §6.5. Nếu #1–#2 còn lung lay, đọc lại §6.2–§6.3.

---

## 🔌 Connect to your past (temlet web→native)

Đây là chương bạn sẽ còn quay lại. Bài toán migration khó nhất của temlet không phải UI — mà là phần logic
server-side của nó mặc định là Node. `process.env`, `fs` của Node, một server sống lâu: không cái nào sống
sót qua chuyến đi sang một Worker, và chúng trở nên vụng về khi nằm sau Tauri, nơi "backend" là một process
được bundle chạy trên máy người dùng. Mỗi giả định như thế là một lần viết lại.

Cái adapter seam của Hono chính là mẫu hình biến việc viết lại thành một *cấu hình*, chứ không phải một lần
cài đặt lại. Chuyển các API handler của temlet sang các Hono handler runtime-agnostic đọc `env(c)` thay vì
`process.env`, thì cùng một đoạn code có thể serve từ edge của Cloudflare hôm nay và từ một sidecar nằm sau
lớp vỏ Tauri của bạn ngày mai — bạn thay adapter, chứ không thay app. Cái detector `getRuntimeKey()` còn cho
phép bạn giữ cái nhánh hiếm hoi thật sự đặc thù cho runtime (chẳng hạn một capability native-only nằm sau
Tauri) một cách tường minh và gọn gàng, thay vì bôi nó khắp codebase dưới dạng những giả định `process` mập
mờ. Đó là khác biệt giữa port temlet một lần và port nó cho sạch.

**Next:** [Chapter 7 — Typed Routes, the RPC Client & Validation →](07-typed-routes-rpc-and-validation.md)
