# Chapter 2 — The App Object & HonoRequest

> **Goal:** Hiểu tầng runtime nền tảng mà Chương 3 dựng lên bên trên — `new Hono()` ra đời thế nào, `.get()` / `.use()` đăng ký route ra sao, `fetch` dispatch một request như thế nào, và `HonoRequest` bọc quanh `Request` của web ra sao. Bám theo `honojs/hono` tại **`v4.12.25`** (`fce483e`).

---

## 2.1 Vì sao quan trọng

`Hono` app là cái object bạn đụng vào mỗi ngày, nhưng phần ruột của nó thường vô hình. Trước khi hiểu được router (Chương 3) hay lớp middleware onion (Chương 5), ta cần biết *ai gọi chúng và lúc nào*: route được cất ở đâu, `app.get(...)` thực sự làm gì, và cái entrypoint `fetch` chuyển xuống các tầng dưới những gì. Chương này là xương sống mà phần còn lại của cuốn sách treo lên.

---

## 2.2 Hai class: `Hono` và `HonoBase`

Mở `src/hono.ts` — nó chỉ vỏn vẹn 34 dòng. Class `Hono` bạn import gần như không tự làm gì:

```ts
// src/hono.ts:16
export class Hono<…> extends HonoBase<…> {
  constructor(options: HonoOptions<E> = {}) {
    super(options)
    this.router =
      options.router ??
      new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })  // :28–32
  }
}
```

Toàn bộ nhiệm vụ của `Hono` là **chọn một router mặc định** (`src/hono.ts:28`). Mọi thứ khác — đăng ký, dispatch, xử lý lỗi — nằm trong class cha `HonoBase` (`src/hono-base.ts:98`). Sự tách đôi này là cố ý: các *preset* (`src/preset/tiny.ts`, `src/preset/quick.ts`) là những subclass `Hono` khác nhau, mỗi cái chọn một router khác nhau nhưng tái dùng nguyên vẹn toàn bộ `HonoBase`. Ta sẽ gặp lại chúng ở Chương 3.

> 🧠 **Mental model:** `HonoBase` là động cơ; `Hono` là lớp vỏ mỏng bắt vít thêm một router. Nếu bạn từng thắc mắc vì sao lại có tới hai class, thì đây chính là câu trả lời — đó là đường ghép cho phép tráo router.

---

## 2.3 Route sống ở đâu

`HonoBase` giữ route ở **hai** chỗ (`src/hono-base.ts`):

- `src/hono-base.ts:118` — `router!: Router<[H, RouterRoute]>` — router đang hoạt động. Đây là thứ *match* lúc có request. (Dấu `!` nghĩa là một subclass phải gán nó — mà `Hono` làm đúng như vậy ở §2.2.)
- `src/hono-base.ts:124` — `routes: RouterRoute[] = []` — một bản sao dạng mảng phẳng của mọi route đã đăng ký, dùng để introspection (ví dụ `app.routes`) và để mount qua `app.route()`. Nó *không* dùng cho việc match.

Vậy nên đăng ký ghi vào hai cấu trúc: router (tối ưu cho match) và mảng (một bản ghi phẳng). Nhớ kỹ ranh giới này — router là hot path, còn mảng là sổ sách.

---

## 2.4 Đăng ký route: `app.get(...)` làm gì

`get`, `post`, v.v. được khai báo dưới dạng field có kiểu (`src/hono-base.ts:104`) nhưng **được implement trong constructor** bằng một vòng lặp (`src/hono-base.ts:128`):

```ts
// src/hono-base.ts:128 — for each HTTP method, install a handler:
this[method] = (args1: string | H, ...args: H[]) => {
  if (typeof args1 === 'string') {
    this.#path = args1            // app.get('/path', handler) — remember the path
  } else {
    this.#addRoute(method, this.#path, args1)   // app.get(handler) — reuse last path
  }
  args.forEach((handler) => {
    this.#addRoute(method, this.#path, handler)  // each handler is its own route entry
  })
  return this as any            // chainable: app.get(...).post(...)
}
```

Hai điều đáng để ý. Thứ nhất, **nhiều handler đăng ký thành nhiều route** cho cùng một path — đó là cách `app.get('/x', mw1, mw2, finalHandler)` chạy được; mỗi cái trở thành một entry được match riêng. Thứ hai, method trả về `this`, nên các lời gọi nối chuỗi được.

`use` cũng cùng ý tưởng nhưng luôn đăng ký dưới `METHOD_NAME_ALL` và mặc định path là `'*'` (`src/hono-base.ts:156`). Đó là lý do `app.use(mw)` (không path) áp lên mọi route.

Tất cả đều đổ về đúng một private method:

```ts
// src/hono-base.ts:385
#addRoute(method, path, handler, baseRoutePath?) {
  method = method.toUpperCase()
  path = mergePath(this._basePath, path)
  const r: RouterRoute = { basePath: …, path, method, handler }
  this.router.add(method, path, [handler, r])   // :395 → hand to the router
  this.routes.push(r)                            // :396 → bookkeeping array
}
```

> 📌 Cái handler được cất trong router là **tuple** `[handler, r]` (`:395`), không phải handler trần. Router mang cái payload mờ đục đó xuyên qua quá trình match rồi trả lại y nguyên — router không bao giờ biết một "handler" là cái gì. Đây là lý do interface `Router<T>` generic theo `T`; ta sẽ thấy điều đó ở Chương 3.

Còn có `app.route(path, subApp)` (`src/hono-base.ts:208`) để mount một Hono app vào bên trong một Hono app khác, `onError` (`src/hono-base.ts:271`), và `notFound` (`src/hono-base.ts:291`) — ta sẽ dùng chúng ở Chương 5 và 8.

---

## 2.5 Dispatch: `fetch` làm gì

```text
fetch(request, env, ctx)              src/hono-base.ts:479
   │
   └─► #dispatch(request, ctx, env, method)        :406
          ├─ HEAD? re-dispatch as GET, body stripped      :413
          ├─ path   = this.getPath(request)               :418
          ├─ match  = this.router.match(method, path)     :419   ◄── Router (Ch 3)
          ├─ c      = new Context(request, {…match…})      :421   ◄── Context (Ch 4)
          ├─ 1 handler?  call it directly (fast path)      :430
          └─ N handlers? compose(...)(c) (onion path)      :450   ◄── Compose (Ch 5)
```

Entrypoint bé xíu (`src/hono-base.ts:479`): `fetch` chỉ chuyển tiếp sang private `#dispatch`. Phần việc thật nằm ở `#dispatch` (`src/hono-base.ts:406`):

- **Xử lý HEAD** (`:413`) — một request `HEAD` được dispatch lại thành `GET` và bỏ body của nó đi. Hono không bao giờ bắt bạn phải viết một HEAD handler riêng.
- **Trích path** (`:418`) — `this.getPath(request, { env })`. Mặc định đây là `getPath` từ `src/utils/url.ts:106`, được nối dây ở `src/hono-base.ts:172` (hoặc `getPathNoStrict` khi `strict: false`).
- **Match** (`:419`) — `this.router.match(method, path)` trả về `[handlers, paramStash]`. Đây là tầng Router; Chương 3.
- **Tạo Context** (`:421`) — `new Context(request, { path, matchResult, env, executionCtx, notFoundHandler })`. Kết quả match được giao cho Context để `c.req.param()` giải quyết được về sau.
- **Fast vs onion** (`:430` / `:450`) — đã nói ở §1.4 và mổ kỹ ở Chương 5.

> 💡 **Tip:** có một entrypoint thứ hai, `app.request(...)` (`src/hono-base.ts` ~499), nhận một chuỗi URL hoặc một `Request` và được thiết kế cho **test** — nó cho phép bạn gọi app của mình mà không cần server. Bạn sẽ dùng nó trong lab của chương này.

---

## 2.6 `HonoRequest`: một wrapper, không phải bản thay thế

`c.req` là một `HonoRequest`, không phải `Request` thô. Mở `src/request.ts:36`:

```ts
export class HonoRequest<P extends string = '/', I … = {}> {
  raw: Request              // :51 — the underlying web Request, always reachable
  path: string              // :68 — the matched pathname
  bodyCache: BodyCache = {} // :69 — caches parsed bodies (one-shot stream!)
  routeIndex: number = 0
}
```

Ý cốt lõi: `HonoRequest` **bọc** quanh `Request` của web (giữ tại `.raw`, `src/request.ts:51`) và thêm sự tiện tay lên trên. Không có gì bị giấu — `c.req.raw` luôn là hàng thật.

Những method bạn dùng hằng ngày:

- `param(key?)` (`src/request.ts:94`) — path param lấy từ kết quả match của router. `c.req.param('id')`.
- `query(key?)` (`src/request.ts:148`) — param từ search-string. `c.req.query('q')`.
- `header(name?)` (`src/request.ts:185`) — header của request.
- `json()` (`src/request.ts:253`) — `this.#cachedBody('text').then(JSON.parse)` — để ý nó đi qua **body cache**, nên lần thứ hai gọi `c.req.json()` không cố đọc lại cái stream đã bị tiêu thụ.

> ⚠️ Đây chính là cái bẫy §0.3 được cụ thể hoá: body của một `Request` là stream chỉ đọc được một lần. `bodyCache` (`src/request.ts:69`) là toàn bộ lý do bạn *có thể* gọi `c.req.json()` từ hai middleware khác nhau trên cùng một request mà không dính exception. Cache lại kết quả parse ở đây không phải là tối ưu — nó là một yêu cầu về tính đúng đắn.

---

## 2.7 Lab 2 — đăng ký và test entrypoint

Trong dự án `hono-hello` của bạn, hãy chứng minh rằng nhiều handler trở thành nhiều route, và dùng test entrypoint để thậm chí chẳng cần tới server:

```ts
// probe.ts
import { Hono } from 'hono'
const app = new Hono()

app.use('*', async (c, next) => { c.header('x-mw', 'ran'); await next() })
app.get('/users/:id', (c) => c.json({ id: c.req.param('id'), q: c.req.query('q') }))

console.log(app.routes)   // ← the bookkeeping array from §2.3

const res = await app.request('/users/42?q=hi')   // ← src/hono-base.ts:499, no server!
console.log(res.status, res.headers.get('x-mw'), await res.json())
```

```bash
bun run probe.ts
```

> 🧪 **Ghi vào `labs/lab2-app.md`:** nội dung của `app.routes` (bạn sẽ thấy *hai* entry cho `/users/:id` — một `ALL` từ middleware `use('*')`, một `GET`), và dòng response. Kỳ vọng: `200 ran {"id":"42","q":"hi"}`. Header `x-mw: ran` chứng minh route của middleware đã match đúng path như handler — chính là điểm "nhiều handler, nhiều route" từ §2.4.

---

## 2.8 Checkpoint

1. Nhiệm vụ *duy nhất* của class `Hono` là gì, và class nào mới làm phần việc thật?
2. Route được cất ở hai chỗ. Kể tên cả hai và nói cái nào dùng để match.
3. Router thật ra cất cái gì làm payload "handler" của nó, và vì sao interface `Router<T>` lại generic?
4. Bám theo `app.fetch(req)` tới dòng gọi router và dòng tạo `Context`.
5. Vì sao `HonoRequest` cache body đã parse? Không có `bodyCache` thì hỏng ở chỗ nào?

> Nếu #3 còn lung lay, đọc lại §2.4. Nếu #5 còn lung lay, đọc lại §2.6 (và §0.3).

---

## 🔌 Connect to your past (temlet web→native)

Trong Next.js, "route của mình sống ở đâu?" có một câu trả lời không-ra-trả-lời: chúng sống trong *hệ thống file*, và framework tái dựng một bảng route mà bạn không bao giờ thấy. Sự ngầm định đó ổn cho tới khi bạn migrate — lúc ấy bạn phải reverse-engineer các quy ước của framework mới biết được thứ gì thực sự đã được đăng ký.

Mảng `app.routes` của Hono (`src/hono-base.ts:124`) thì ngược lại: một danh sách tường minh, soi được, mà bạn có thể `console.log`. Khi bạn mang temlet tiến về phía Tauri và cần audit chính xác endpoint nào tồn tại và middleware của chúng chạy theo thứ tự nào, một bảng route tường minh là vàng. Và `app.request(...)` — cái test entrypoint không-cần-server từ §2.5 — nghĩa là bạn có thể unit-test toàn bộ mặt API đó mà không phải khởi động Next, Node, *hay* lớp vỏ native. Khả năng test đó là một trong những cái được thầm lặng khi dời tầng HTTP lên một thứ runtime-agnostic.

**Next:** [Chapter 3 — The Router ★ →](03-the-router.md)
