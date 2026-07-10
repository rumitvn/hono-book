# Chapter 4 — Context & Building Responses

> **Goal:** Hiểu object `Context` — cái `c` mà mọi handler nhận được — và cách `c.json()`,
> `c.text()`, `c.html()` biến dữ liệu của bạn thành một `Response` chuẩn web. Nắm hai đường nối `c.env` và `c.var`
> khiến cùng một handler vừa portable vừa giữ được state. Neo vào `honojs/hono` tại **`v4.12.25`**
> (`fce483e`).

---

## 4.1 Vì sao quan trọng

`c` là tham số duy nhất mà handler của bạn thực sự dùng. Nó vừa là request, vừa là bộ dựng response, vừa là các
environment binding, vừa là một cuốn sổ nháp theo từng request — gom hết vào một object. Hiểu được `Context` là
hiểu trọn bề mặt mà bạn lập trình lên — và bạn sẽ thấy rằng, giống phần còn lại của Hono, nó chỉ là một lớp mỏng,
dễ đọc phủ lên các web standard, chứ không phải một god-object framework bí ẩn nào.

Phần thưởng sâu hơn: biết được *khi nào* một `Response` thực sự được dựng (và khi nào header đang được buffer so
với đã commit) chính là thứ cho phép bạn suy luận về middleware sửa response — chủ đề của Chương 5.

---

## 4.2 Mental model: c là một phong bì theo từng request

```text
        new Context(request, { path, matchResult, env, executionCtx, … })
                                  src/context.ts:352
        ┌──────────────────────────────────────────────────────────┐
   c.   │  req      → HonoRequest (the incoming request)   :366     │
        │  env      → runtime bindings (KV, secrets, …)    :315     │
        │  var/get/set → per-request scratchpad            :546/571 │
        │  ─────────────────────────────────────────────────────── │
        │  json/text/html/body → BUILD a Response          :708 …   │
        │  header/status       → buffer response metadata  :515/529 │
        │  res / finalized     → the committed Response     :403/317 │
        └──────────────────────────────────────────────────────────┘
```

Mỗi request sinh ra một `Context` mới trong `#dispatch` (nhớ lại `src/hono-base.ts:421`). Nó
**không** được tái dùng giữa các request — nên bất cứ thứ gì bạn gắn lên nó (`c.set(...)`) đều bó gọn trong phạm vi
một request và tự động bị vứt đi. Chính sự cô lập đó là lý do Hono không cần đến mấy trò request-local-storage cho
trường hợp thông thường.

---

## 4.3 Hai nửa: đọc và trả lời

Mở `src/context.ts:293` (class) và `:352` (constructor — nó chỉ cất lại đống option). Class tách ra rất
gọn thành một nửa **đọc** và một nửa **trả lời**.

**Đọc request và environment:**

- `c.req` (`src/context.ts:366`) — dựng lazy ra `HonoRequest` từ Chương 2. `c.req.param('id')`,
  `c.req.query('q')`, `c.req.json()`.
- `c.env` (`src/context.ts:315`) — các binding của runtime: KV namespace, D1 database, và secret của một
  Cloudflare Worker; còn ở nơi khác là environment variable. Đây là đường nối mà *platform* bước vào
  handler của bạn. (Chương 6 sẽ đào sâu.)
- `c.set(key, value)` (`src/context.ts:546`) / `c.get(key)` (`src/context.ts:571`) — một kho key/value theo
  từng request, tựa trên một `Map`. Middleware ghi vào (`c.set('user', …)`), handler phía dưới đọc ra
  (`c.get('user')`). Đây chính là cách middleware authentication chuyển một object user xuống route của bạn.

**Dựng response:**

- `c.json(obj, status?, headers?)` (`src/context.ts:708`)
- `c.text(str, …)` (`src/context.ts:682`)
- `c.html(str, …)` (`src/context.ts:723`)
- `c.body(data, …)` (`src/context.ts:664`)
- `c.redirect(loc, status?)` (`src/context.ts:750`), `c.notFound()` (`src/context.ts:776`)

---

## 4.4 `c.json()` trở thành một `Response` như thế nào

Đây là lúc xua tan mọi ảo tưởng về "phép màu framework". Đọc thân của `c.json` (`src/context.ts:708`):

```ts
json: JSONRespond = (object, arg?, headers?) => {
  return this.#newResponse(
    JSON.stringify(object),                                   // serialize
    arg,                                                       // status or ResponseInit
    setDefaultContentType('application/json', headers)         // add content-type if absent
  )
}
```

Chỉ có vậy. `c.json({...})` là `JSON.stringify` + một `Content-Type` mặc định + một lời gọi tới hàm private
`#newResponse` (`src/context.ts:604`), nơi dựng ra một `Response` web thật. `c.text` và `c.html`
cùng một hình dạng, chỉ khác mặc định (`text/plain`, `text/html`). `setDefaultContentType`
(`src/context.ts:281`) chỉ đặt header khi bạn chưa tự cung cấp — nên bạn luôn có thể ghi đè.

> 🧠 **Mental model:** cả họ `c.json/text/html` là *đường mật phủ lên `new Response()`*. Không có object
> response ẩn nào trong Hono — khi bạn gọi `c.json`, một `Response` thật được dựng ngay tại chỗ và trả về.
> So với `c.res` (`src/context.ts:403`), thứ *hiện thực hoá* một response có thể sửa được một cách lazy cho
> những trường hợp middleware cần chỉnh sửa. Hai đường: dựng-rồi-trả (handler) so với sửa-lazy
> (middleware).

---

## 4.5 Header và status: buffer trước, commit sau

Vì sao `c.header('x', 'y')` chạy được *trước cả khi* bạn gọi `c.json()`? Bởi vì header và status được
**buffer** lên context và chỉ áp dụng khi response được dựng:

- `c.status(code)` (`src/context.ts:529`) giấu status vào một field private `#status` — nó không dựng gì cả.
- `c.header(name, value, options?)` (`src/context.ts:515`) ghi vào một object `Headers` đang được buffer — nhưng
  để ý mấy dòng đầu: *nếu response đã finalized* (`src/context.ts:516`), nó sẽ sửa thẳng header của response
  đã commit. Chính hành vi hai mặt này cho phép cả handler (trước khi dựng) lẫn middleware (sau khi dựng) đặt
  header đúng cách.
- `c.finalized` (`src/context.ts:317`) chuyển sang `true` (`src/context.ts:433`) khi một response đã được
  commit. `compose` kiểm cờ này để quyết định xem một middleware có sinh ra response hay không — đó là mối nối
  sang Chương 5.

> ⚠️ **Footgun:** thứ tự có ý nghĩa với đường *buffer*. `c.status(201)` rồi `return c.json(obj)` →
> 201. Nhưng `return c.json(obj)` *rồi mới* `c.status(201)` thì đã muộn — response đã được dựng với mặc định
> 200 mất rồi. Việc buffer là một chiều: đặt metadata *trước*, dựng body *sau*.

---

## 4.6 `c.env` và `c.var`: đường nối cho tính portable và cho state

Hai property nhỏ nhưng gánh rất nặng:

**`c.env`** là cách *runtime* với tới code của bạn mà code không phải gọi tên runtime. Trên Workers,
`c.env.MY_KV` là một KV binding; trên Node, bạn sẽ đọc `process.env`. Handler của bạn viết `c.env.DATABASE` và
giữ nguyên tính runtime-agnostic — adapter (Chương 6) mới là bên quyết định `env` thực chất là gì. Đây là
property quan trọng bậc nhất cho câu chuyện web→native.

**`c.var`** (cùng `c.set`/`c.get`) là state theo từng request có kiểu. Với TypeScript, bạn khai báo những gì
sống ở đó qua nửa `Variables` trong kiểu `Env` của mình, và `c.get('user')` sẽ có kiểu. Bên dưới nó là một `Map`
(`src/context.ts:546`) — chẳng có gì kỳ lạ — nhưng phần kiểu khiến việc bàn giao middleware→handler trở nên an toàn.

---

## 4.7 Lab 4 — cú bàn giao middleware → handler

Chứng minh luật buffer-header và kênh `c.set`/`c.get` trong cùng một probe (tái dùng `hono-hello`):

```ts
// ctx-probe.ts
import { Hono } from 'hono'
const app = new Hono<{ Variables: { reqId: string } }>()

app.use('*', async (c, next) => {
  c.set('reqId', 'abc-123')          // middleware writes per-request state  (:546)
  c.header('x-powered-by', 'hono-book')
  await next()
  c.header('x-after', 'yes')          // set AFTER next(): response is finalized → mutates committed headers (:516)
})

app.get('/', (c) => {
  c.status(201)                       // buffer status BEFORE building body
  return c.json({ id: c.get('reqId') })   // reads middleware's value         (:571)
})

const res = await app.request('/')
console.log(res.status, await res.json())
console.log('powered-by:', res.headers.get('x-powered-by'), '| after:', res.headers.get('x-after'))
```

```bash
bun run ctx-probe.ts
```

> 🧪 **Ghi vào `labs/lab4-context.md`:** status, body, và cả hai header. Kỳ vọng: `201
> {"id":"abc-123"}`, và *cả hai* `x-powered-by` lẫn `x-after` đều có mặt. Header `x-after` — được đặt *sau*
> `await next()` — chứng minh đường hai mặt ở §4.5: một khi đã finalized, `c.header` sửa thẳng response đã
> commit. Giờ đảo thứ tự trong handler (`return c.json(...)` rồi mới `c.status(201)`) và xem status rơi
> về 200 — đúng footgun ở §4.5.

---

## 4.8 Checkpoint

1. `Context` được tạo lúc nào, và vòng đời của nó dài bao lâu?
2. Đi từng bước qua những gì `c.json({a:1})` làm để sinh ra một `Response`.
3. Vì sao bạn gọi được `c.header(...)` cả trước lẫn sau `c.json(...)`? `c.finalized` liên quan gì đến chuyện
   đó?
4. `c.env` khác `c.var` ở điểm nào, và cái nào là chìa khoá cho tính portable giữa các runtime?
5. Chỉ ra footgun về thứ tự thao tác với `c.status()` và giải thích vì sao nó xảy ra.

> Nếu câu #2–#3 còn lung lay, đọc lại §4.4–§4.5. Nếu câu #4 còn lung lay, đọc lại §4.6.

---

## 🔌 Connect to your past (temlet web→native)

`c.env` là lời giải sạch nhất cho một bài toán bạn sẽ đụng thẳng mặt khi migrate temlet. Trong Next.js bạn với
tay lấy `process.env` và mặc định là có một Node process tồn tại. Ngay khoảnh khắc temlet chạy ở edge — hay nấp
sau Tauri, nơi "environment" là OS cộng một file config được bundle chứ không phải một Node process — thì
`process.env` là abstraction sai. `c.env` của Hono lật ngược lại: handler của bạn *khai báo một dependency*
(`c.env.DATABASE`) còn adapter *cung cấp nó*, theo từng runtime. Đó chính là dependency injection ngay tại ranh
giới request.

Và `c.set`/`c.get` là bản theo-phạm-vi-request của cái React context mà bạn vốn đã tư duy theo: một middleware
"provide" một giá trị (`c.set('user', …)`), các nhánh con "consume" nó (`c.get('user')`), rồi nó bị tháo dỡ khi
request kết thúc. Nếu bạn từng nâng auth state qua một Next middleware vào trong một route, thì đây đúng là mẫu
hình đó, chỉ khác là có một kênh tường minh và có kiểu — và một kênh sống sót qua cú rời bỏ Node.

**Next:** [Chapter 5 — The Middleware Onion →](05-the-middleware-onion.md)
