# Chapter 0 — Environment & TypeScript / Web-standards Refresher

> **Goal:** Có được một green build của `honojs/hono` tại pinned ref **`v4.12.25`** (commit `fce483e`), và
> ôn lại hai trụ cột mà cả framework dựa lên — **Fetch API** (`Request`/`Response`) và **TypeScript
> generics & conditional types** làm cho route trở nên type-safe. Hết chương này bạn chạy được một app Hono
> tí hon cùng test suite của upstream ngay trên máy mình.

---

## 0.1 Vì sao quan trọng

Hầu hết framework đều tự bịa ra cặp request và response object của riêng mình. Express thì có `req`/`res`.
Next.js thì có `NextRequest`/`NextResponse`. Mỗi bên một hình dạng khác nhau, nên port code qua lại giữa
chúng đồng nghĩa với viết lại toàn bộ phần ranh giới. Hono đặt cược theo hướng ngược lại: nó dùng thẳng
**`Request` và `Response` của chính web platform** — đúng những object mà `fetch()` trong trình duyệt trả
về, đúng những object mà `fetch` handler của một Cloudflare Worker nhận vào. Không có gì độc quyền ở hai đầu.

Chính quyết định đó là lý do cùng một `app` chạy được trên Cloudflare Workers, Bun, Deno, Node và Lambda mà
không phải sửa một dòng. Nên trước khi đọc bất kỳ dòng code routing nào, ta cần hai thứ Hono mặc định bạn đã
biết sẵn: **`Request`/`Response` là gì**, và **các tính năng ở tầng type của TypeScript biến một chuỗi path
thành một tham số có kiểu ra sao**. Nếu hai thứ đó còn tươi trong đầu, phần còn lại của cuốn sách đọc rất nhẹ.

---

## 0.2 Mental model: một framework "chỉ là" một fetch handler

Bóc hết mọi thứ đi thì một app Hono chỉ là một function với đúng hình dạng này:

```text
        ┌─────────────────────────────────────────────┐
        │   (request: Request) => Response | Promise   │
        │                                              │
  HTTP  │   app.fetch  ───►  router  ───►  handler     │  HTTP
  ─────►│        │             │             │         │─────►
 Request│        └── Context (c) ──── c.json/text/html │ Response
        └─────────────────────────────────────────────┘
```

Runtime (Workers, Bun, …) trao cho Hono một `Request` và chờ nhận lại một `Response`. Mọi thứ Hono làm —
match một route, chạy middleware, dựng một body — đều diễn ra *ở giữa* hai object chuẩn web đó. Đây đúng là
hình dạng mà một Cloudflare Worker vốn đã có sẵn:

```ts
export default {
  fetch(request: Request): Response | Promise<Response> {
    return new Response('hi')
  },
}
```

Một `app` Hono *chính là* cái `fetch` function đó, chỉ gắn thêm một router và middleware lên trên. Giữ lấy
bức tranh này.

---

## 0.3 Ôn nhanh: các object của Fetch API

Chúng là global trong mọi runtime hiện đại. Không cần import gì cả.

**`Request`** — một view chỉ-đọc, bất biến của một HTTP request đang đến:

```ts
const req = new Request('https://x.dev/users/42?q=hi', {
  method: 'GET',
  headers: { 'content-type': 'application/json' },
})
req.method            // 'GET'
req.url               // 'https://x.dev/users/42?q=hi'
req.headers.get('content-type')   // 'application/json'
await req.json()      // parses the body once (the body is a stream)
```

> ⚠️ Một request/response **body là một stream chỉ đọc được một lần**. Bạn chỉ đọc nó được *một lần* duy
> nhất. Đây là lý do Hono cache lại body đã parse — bạn sẽ thấy `bodyCache` ở `src/request.ts:69` trong
> chương sau. Đọc lại một body đã bị tiêu thụ sẽ ném lỗi.

**`Response`** — cái bạn gửi trả về:

```ts
new Response('hello', { status: 200, headers: { 'x-foo': 'bar' } })
Response.json({ ok: true })          // sets content-type for you
new Response(null, { status: 302, headers: { location: '/' } })  // redirect
```

`c.text()`, `c.json()` và `c.redirect()` của Hono là những wrapper mỏng, tiện tay, rốt cuộc chỉ dựng ra một
trong hai object trên. Nhớ điều đó — khi ta đọc `context.ts`, bạn sẽ thấy chẳng có phép màu nào, chỉ là việc
dựng một `Response` với vài default hợp lý.

---

## 0.4 Ôn nhanh: những tính năng TypeScript mà Hono dựa vào

Tính năng đinh của Hono là *type-safe routing*: bạn viết `/users/:id` thì `c.req.param('id')` tự có kiểu
string mà chẳng cần annotation nào. Toàn bộ chuyện đó dựng nên từ đúng ba tính năng của TypeScript. Bạn không
cần thành thạo chúng, nhưng nên nhận ra chúng khi Chapter 7 trích `src/types.ts`.

**1. Generics chuyển thông tin kiểu xuyên qua một lời gọi.**

```ts
function first<T>(arr: T[]): T { return arr[0] }
first([1, 2, 3])         // T inferred as number → returns number
```

Class `Hono` là generic: `class Hono<E extends Env, S extends Schema, BasePath extends string>`
(`src/hono.ts:16`). Type parameter `S` chính là *route schema được tích luỹ dần* — mỗi lời gọi `.get()` trả
về một `Hono` mới với `S` được nới rộng ra để bao thêm route đó. Đó là cách mà client `hc` sau này biết được
các route của bạn.

**2. Template-literal type cho phép compiler đọc được một chuỗi.**

```ts
type Greeting = `hello ${string}`     // matches "hello world", not "hi"
```

Hono dùng chúng để parse một path *ngay ở tầng type*. `ParamKeys<'/users/:id'>` cho ra `'id'`
(`src/types.ts:2706`). Compiler theo đúng nghĩa đen cắt chuỗi path tại dấu `/` rồi rút ra những segment có
tiền tố `:`.

**3. Conditional type rẽ nhánh dựa trên một kiểu.**

```ts
type IsString<T> = T extends string ? 'yes' : 'no'
```

`ParamKey` (`src/types.ts` gần dòng 2698) dùng đúng mẫu này — `Component extends `:${infer Name}` ? Name : never` — để moi cái tên ra khỏi một segment `:param`. Từ khoá `infer` bắt lấy đoạn khớp được.

> 🧠 **Mental model:** Type safety của Hono là một trình thông dịch tí hon chạy lúc compile-time, quét qua
> các chuỗi path của bạn. Nó tốn zero byte lúc runtime — bị xoá sạch hết. Ta sẽ đọc các định nghĩa thật ở
> Chapter 7; còn giờ, chỉ cần biết ba tính năng này là toàn bộ bộ đồ nghề.

---

## 0.5 Bề mặt public

Mở `src/index.ts` (53 dòng). Đây là toàn bộ những gì `import … from 'hono'` trao cho bạn:

- `src/index.ts:17` — `import { Hono } from './hono'`, được re-export ở `:53`. Class này chính là toàn bộ runtime API.
- `src/index.ts:22-34` — các **type** public: `Env`, `Handler`, `MiddlewareHandler`, `Next`, `Input`,
  `Schema`, `ToSchema`, `TypedResponse`. Đây là bộ từ vựng ở tầng type của framework.
- `src/index.ts:39` — `export { Context } from './context'` — class của object `c`.
- `src/index.ts:44` — `HonoRequest` (chỉ có type).

> 📁 Để ý xem nó nhỏ cỡ nào. Middleware (`hono/cors`), adapter (`hono/cloudflare-workers`), client
> (`hono/client`) và JSX (`hono/jsx`) đều là **các entry point riêng biệt**, không gói vào core. Nhờ vậy
> phần import cơ sở giữ được cực gọn — một tối ưu về kích thước ở edge có chủ đích mà ta sẽ quay lại ở Chapter 6.

---

## 0.6 Lab 0 — green build + app đầu tiên

Repo upstream dùng **Bun** làm toolchain chính (xem `.tool-versions`: `bun 1.2.19`, `nodejs
24.7.0`, `deno 2.4.5`). Cài Bun nếu bạn chưa có (`curl -fsSL https://bun.sh/install | bash`), rồi:

```bash
# 1. Confirm the pin (read-only clone lives beside the book)
cd ../hono
git log -1 --format='%h %d'        # expect: fce483e (tag: v4.12.25)

# 2. Install dev deps and type-check + run the suite
bun install
bun run test                        # = tsc --noEmit && vitest --run
```

Rồi build một app nhỏ nhất có thể *bên ngoài* clone (để không bao giờ đụng vào nó) — đây là artifact
`hono-hello` mà bạn sẽ tái dùng ở các lab sau:

```bash
mkdir -p ~/hono-hello && cd ~/hono-hello
bun init -y
bun add hono
```

```ts
// index.ts
import { Hono } from 'hono'

const app = new Hono()
app.get('/', (c) => c.text('Hono!'))
app.get('/users/:id', (c) => c.json({ id: c.req.param('id') }))

export default app
```

```bash
bun run --hot index.ts
# in another shell:
curl localhost:3000/
curl localhost:3000/users/42
```

> 🧪 **Lưu lại các con số của bạn** vào `labs/lab0-setup.md`: phiên bản Bun, `bun run test` có green không,
> và output của hai lệnh `curl`. Bạn phải thấy `Hono!` và `{"id":"42"}`. Để ý `:id` về dưới dạng một
> **string** — đó chính là typed param từ §0.4 đang hoạt động.

> 💡 **Tip:** `vitest --run` chạy nhanh vì Hono thuần TypeScript, không có bước native build nào. So với mấy
> cuốn C/C++/Rust trong series này, nơi "có được một green build" nghĩa là cả một compiler toolchain. Ở đây
> cả framework là source bạn đọc từ đầu đến cuối gọn trong một buổi chiều.

---

## 0.7 Checkpoint

1. Hai object chuẩn web nào nằm ở ranh giới input và output của Hono, và vì sao dùng chúng lại khiến framework
   trở nên portable?
2. Vì sao Hono buộc phải cache một request body đã parse thay vì đọc lại nó?
3. `ParamKeys<'/posts/:slug'>` cho ra kết quả gì, và tính năng TypeScript nào làm được điều đó?
4. `hono/cors` có nằm trong phần import `hono` lõi không? Middleware và adapter sống ở đâu?
5. Khi bạn gọi `/users/42`, *kiểu* lúc runtime của `c.req.param('id')` là gì, và cái kiểu đó đến từ đâu?

> Nếu #3 hoặc #5 còn lung lay, đọc lại §0.4. Nếu #1–#2 còn lung lay, đọc lại §0.3.

---

## 🔌 Connect to your past (temlet web→native)

Bạn đã sống qua đúng nỗi đau mà "canh bạc lớn" của chương này né được. Trong **temlet** trên Next.js, logic
API của bạn bị cưới chặt vào `NextRequest`/`NextResponse` cùng cái ranh giới runtime Node/Edge. Ngay khoảnh
khắc bạn mang temlet tiến về phía **Tauri**, cái Node server đó không còn ở đó nữa — và bất cứ thứ gì buộc
vào các request object của Next đều phải viết lại cho phía native.

Canh bạc của Hono chính là lối thoát: vì nó chỉ nói bằng `Request`/`Response`, nên *cùng một* router và các
handler chạy được bên trong một Worker, một Bun server, hay một tiến trình sidecar nấp sau lớp vỏ Tauri. Khi
đọc cuốn sách này, cứ tự hỏi hoài: *những API handler nào trong temlet của mình có thể biến thành các Hono
handler runtime-agnostic?* Cuộc di cư web→native rẻ đi thấy rõ khi lớp HTTP của bạn không còn quan tâm bên
dưới nó là gì nữa.

**Next:** [Chapter 1 — Mental Model & Repo Map →](01-mental-model-and-repo-map.md)
