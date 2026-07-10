# Chapter 1 — Mental Model & Repo Map

> **Goal:** Build the five-layer mental model of Hono — **App → Router → compose → Context → Adapter** —
> and trace one real request end-to-end through `honojs/hono` at **`v4.12.25`** (`fce483e`), naming every
> hop by `file:line`. By the end you can point at the exact function that runs at each stage of a request.

---

## 1.1 Vì sao quan trọng

Hono nhỏ — phần lõi chỉ vài nghìn dòng TypeScript — nhưng "nhỏ" không đồng nghĩa với "hiển nhiên". Nếu
trong đầu bạn không có một mô hình phân lớp, đoạn code đọc lên như một mớ generic và regex khôn lỏi rối
tung. Có mô hình rồi, mỗi file có một chỗ đứng rõ ràng và luồng request trở thành một đường thẳng bạn dò
được bằng ngón tay.

Phần thưởng là sức mạnh khi debug. Khi một request trả về sai status, hay middleware chạy theo một thứ tự
lạ đời, hay một route lại khớp trong khi lẽ ra không được — bạn sẽ biết ngay *lớp nào* đang giữ con bug và
phải mở file nào, thay vì đoán mò.

---

## 1.2 Mô hình năm lớp

Mọi request của Hono đều đi xuyên năm lớp này, từ trên xuống dưới rồi ngược lại:

```text
   ┌──────────────────────────────────────────────────────────────┐
   │  ADAPTER          src/adapter/*        runtime → Request       │
   │  (Workers, Bun, Deno, Node, Lambda)    Response → runtime      │
   └───────────────┬──────────────────────────────────────────────┘
                   │  app.fetch(request, env, ctx)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  APP            src/hono-base.ts       #dispatch: orchestrate  │
   │                 src/hono.ts            route table + handlers  │
   └───────────────┬──────────────────────────────────────────────┘
                   │  this.router.match(method, path)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  ROUTER ★       src/router/*           path → [handlers, params]│
   │                 (Smart/RegExp/Trie/Linear)                     │
   └───────────────┬──────────────────────────────────────────────┘
                   │  compose(matched handlers)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  COMPOSE        src/compose.ts         middleware onion + next()│
   └───────────────┬──────────────────────────────────────────────┘
                   │  handler(c, next)
   ┌───────────────▼──────────────────────────────────────────────┐
   │  CONTEXT        src/context.ts         c.req / c.json / c.env  │
   │                 src/request.ts         → builds the Response   │
   └──────────────────────────────────────────────────────────────┘
```

- **Adapter** là lớp duy nhất phụ thuộc runtime. Nó gần như chẳng làm gì: nhận một `Request`, gọi
  `app.fetch`, trả về `Response`. (Chương 6.)
- **App** là nhạc trưởng — nó sở hữu route table và chạy thuật toán dispatch. (Chương 2.)
- **Router** biến một method+path thành danh sách các handler khớp. Đây là chương flagship. (Chương 3.)
- **Compose** xâu các handler đó thành middleware onion thông qua `next()`. (Chương 5.)
- **Context** chính là `c` mà handler của bạn nhận được, đồng thời là bộ dựng response. (Chương 4.)

> 🧠 **Mental model:** App là một nhạc trưởng mỏng. Phần việc *thú vị* đều được uỷ thác ra ngoài: match thì
> giao cho Router, xâu chuỗi thì giao cho Compose, dựng response thì giao cho Context. `hono-base.ts` phần
> lớn chỉ nối chúng lại với nhau.

---

## 1.3 Repo map — mọi thứ nằm ở đâu

```text
src/
├── index.ts          public exports (Ch 0)
├── hono.ts           the Hono class — picks the default router (Ch 2)
├── hono-base.ts      HonoBase — route registration, #dispatch, fetch (Ch 2)
├── router.ts         the Router<T> interface every router implements (Ch 3)
├── router/           ★ the four router implementations (Ch 3)
│   ├── linear-router/    simplest: scan every route
│   ├── pattern-router/   one regex per route
│   ├── trie-router/      a prefix tree of segments
│   ├── reg-exp-router/   the "one big regex" engine
│   └── smart-router/     tries RegExp, falls back to Trie
├── compose.ts        the middleware onion (Ch 5)
├── context.ts        the Context `c` + response builders (Ch 4)
├── request.ts        HonoRequest — wraps web Request (Ch 2/4)
├── adapter/          per-runtime entry points (Ch 6)
├── helper/           env(), streaming, cookies, SSE … (Ch 6)
├── middleware/       25 built-in middleware (cors, jwt, …) (Ch 8)
├── preset/           tiny / quick — alternate router defaults (Ch 3)
├── validator/        validator() middleware (Ch 7)
├── client/           the hc RPC client (Ch 7)
└── types.ts          the type-level machinery — 2,778 lines (Ch 7)
```

> 📁 File to nhất, `types.ts` (2,778 dòng), **không chứa một dòng runtime code nào** — toàn bộ là type ở
> compile-time. Phần lõi runtime (`hono-base.ts` + `context.ts` + `compose.ts` + `router/`) thì gọn gàng
> đến bất ngờ. Ngân sách phức tạp của Hono được tiêu vào *type*, không phải logic.

---

## 1.4 Lần trace end-to-end: một GET request

Hãy bám theo `app.get('/users/:id', handler)` khi nó bị gọi bởi `GET /users/42`. Mở các file được trích
dẫn ra và đọc song song.

**Đăng ký route (xảy ra một lần, lúc startup):**

1. `app.get('/users/:id', handler)` được điều phối bởi method handler. Kiểu của nó được khai báo ở
   `src/hono-base.ts:104` (`get!: HandlerInterface<…>`); còn *phần hiện thực* thì được sinh ra trong vòng
   lặp constructor ở `src/hono-base.ts:128`, và rốt cuộc gọi tới `#addRoute` (private).
2. `src/hono-base.ts:385` — `#addRoute(method, path, handler)` viết hoa method, ghép base path vào, build
   một record `RouterRoute`, rồi thực hiện hai dòng cốt lõi:
   - `src/hono-base.ts:395` — `this.router.add(method, path, [handler, r])` (trao route cho router)
   - `src/hono-base.ts:396` — `this.routes.push(r)` (giữ một bản sao để introspection)

**Dispatch (xảy ra mỗi request):**

3. `src/hono-base.ts:479` — `fetch(request, …)` là entrypoint. Nó gọi `#dispatch`.
4. `src/hono-base.ts:406` — `#dispatch(request, executionCtx, env, method)` chạy request:
   - `src/hono-base.ts:418` — `const path = this.getPath(request, { env })` — trích ra pathname.
     (`getPath` nằm ở `src/utils/url.ts:106`, được nối vào ở `src/hono-base.ts:172`.)
   - `src/hono-base.ts:419` — **`const matchResult = this.router.match(method, path)`** — Router chạy tại đây.
   - `src/hono-base.ts:421` — `const c = new Context(request, { path, matchResult, env, … })` — dựng `c`.
5. **Fast path** — `src/hono-base.ts:430`: *nếu chỉ đúng một handler khớp*, gọi thẳng nó mà không qua
   `compose`, để nhanh. Phần lớn route rơi vào đường này.
6. **Onion path** — `src/hono-base.ts:450`: khi có nhiều handler (middleware + route handler),
   `const composed = compose(matchResult[0], this.errorHandler, this.#notFoundHandler)` dựng nên chuỗi,
   rồi được await ở `:452`.
7. Handler chạy, gọi `c.json({...})` (`src/context.ts:708`), và hàm này build nên một `Response`.
8. `#dispatch` trả về `Response` đó; `fetch` trả nó cho adapter; adapter đưa tiếp cho runtime.

Đó là trọn vẹn một request. Năm lớp, một đường thẳng.

```text
fetch ──► #dispatch ──► getPath ──► router.match ──► new Context
   (479)      (406)        (418)        (419)            (421)
                                          │
                    one handler? ─yes──► call directly        (430)
                          │no
                          └──► compose(...) ──► handler(c) ──► c.json() ──► Response
                                  (450)                          (708)
```

> 💡 **Tip:** fast path ở `:430` là một quyết định hiệu năng có chủ đích, không phải ngẫu nhiên. Một route
> trơn không middleware sẽ bỏ qua toàn bộ việc dựng closure `compose`. Nhớ điều này khi tới Chương 5 —
> `compose` chỉ chạy khi thực sự có một onion cần dựng.

---

## 1.5 Lab 1 — gắn đo cho lần trace

Dùng lại app `hono-hello` từ Lab 0. Thêm một logging middleware để bạn *nhìn thấy* các lớp kích hoạt theo đúng thứ tự:

```ts
import { Hono } from 'hono'
const app = new Hono()

app.use('*', async (c, next) => {
  console.log('→ before', c.req.method, c.req.path)   // Context + Request
  await next()                                         // descend the onion
  console.log('← after ', c.res.status)                // Response exists now
})

app.get('/users/:id', (c) => c.json({ id: c.req.param('id') }))

export default app
```

```bash
bun run --hot index.ts
curl -s localhost:3000/users/42
```

> 🧪 **Ghi vào `labs/lab1-trace.md`:** thứ tự output trên console. Bạn sẽ thấy `→ before GET /users/42`,
> rồi `← after 200`. Vì bạn đã thêm một middleware `use('*')`, request này đi theo **onion path**
> (`hono-base.ts:450`), chứ không phải fast path. Giờ gỡ middleware đó ra và để ý rằng response y hệt —
> request đó đã đi fast path ở `:430`. Cùng output, khác đường đi bên trong.

---

## 1.6 Checkpoint

1. Kể tên năm lớp, từ trên xuống dưới, và file duy nhất sở hữu mỗi lớp.
2. Dòng nào trong `hono-base.ts` gọi Router? Dòng nào gọi `compose`?
3. "fast path" và "onion path" trong `#dispatch` khác nhau ở đâu, và cái gì quyết định một request đi
   đường nào?
4. `types.ts` là file lớn nhất repo. Nó chứa loại code gì — và điều đó nói lên Hono tiêu phức tạp của mình
   vào đâu?
5. `this.router.add(...)` chạy khi nào — mỗi request, hay một lần lúc startup?

> Nếu #2–#3 còn lung lay, đọc lại §1.4. Nếu #1 còn lung lay, đọc lại §1.2.

---

## 🔌 Connect to your past (temlet web→native)

Mô hình năm lớp ánh xạ gọn gàng sang những gì bạn đã biết từ Next.js — mà lại *sạch hơn*. Ở Next, "routing"
(file-system router), "middleware" (`middleware.ts` chạy ở edge), và "handler" (file route của bạn) bị
tách ra ba cơ chế khác nhau với ba mô hình tư duy khác nhau. Hono gộp chúng lại thành một pipeline tường
minh mà bạn đọc gọn trong một file.

Chính sự dễ đọc đó là thứ bạn cần khi bước sang **Tauri**. Khi phần server logic của temlet trở thành một
process nằm sau lớp vỏ native, bạn sẽ không muốn một framework mà luồng request là ngầm định và đầy phép
thuật; bạn muốn một framework nơi bạn chỉ tay được vào `#dispatch` và nói "request đang *ở đây* này." Đọc
tiếp, để ý xem lớp App thực ra làm ít đến mức nào — chính sự mỏng nhẹ đó khiến Hono rẻ để suy luận, khi bạn
không còn runtime của Next dắt tay nữa.

**Next:** [Chapter 2 — The App Object & HonoRequest →](02-app-lifecycle-and-request.md)
