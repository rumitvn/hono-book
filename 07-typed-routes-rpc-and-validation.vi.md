# Chapter 7 — Typed Routes, the RPC Client & Validation

> **Goal:** Đọc bộ máy ở tầng type khiến Hono *type-safe*: một chuỗi path sinh ra một typed
> `c.req.param()` bằng cách nào, mỗi route tích luỹ vào một schema ra sao, và `hc` RPC client cùng
> middleware `validator()` cưỡi lên trên tất cả những thứ đó thế nào. Neo trong `honojs/hono` tại
> **`v4.12.25`** (`fce483e`).

---

## 7.1 Vì sao quan trọng

Tính năng đinh của Hono không phải tốc độ — mà là *type chảy thẳng từ server sang client, không phải viết
lại lần nào*. Viết `app.get('/users/:id', …)` là ba thứ tự động có type miễn phí: `c.req.param('id')` phía
server, hình dạng request, và — qua `hc` client — lời gọi được type đầy đủ trên frontend. Không codegen,
không bước OpenAPI, không file schema. Đây chính là tính năng khiến người ta chuyển sang Hono, và nó *hoàn
toàn* là một construction ở tầng TypeScript với **zero runtime cost** (tất cả bị xoá sạch lúc compile).

Đây là chương duy nhất trong sách đọc type thay vì đọc logic. Và đó mới là điểm mấu chốt: đây là nơi Hono
dồn hết ngân sách phức tạp của mình (nhớ lại §1.3 — `types.ts` dài 2,778 dòng type thuần).

---

## 7.2 Mental model: a compile-time interpreter

```text
   "/users/:id"   ──ParamKeys──►  "id"   ──►  { id: string }   ──►  c.req.param('id'): string
   (a string)       (Ch 7.3)              (a typed record)            (typed accessor)

   app.get('/users/:id', h)  ──ToSchema──►  S grows: { '/users/:id': { $get: … } }
                                (Ch 7.4)         │
                                                 └──►  hc<typeof app>  ──►  client.users[':id'].$get()
                                                          (Ch 7.5)            fully typed
```

Hai type-level engine, xếp chồng lên nhau. `ParamKeys` đọc một chuỗi path đơn lẻ. `ToSchema` gom mọi route
lại thành một type khổng lồ `S`, được mang theo dưới dạng type parameter thứ hai của `Hono<E, S, BasePath>`
(`src/hono.ts:16`). `hc` client "chỉ" là một hàm đọc ngược `S` ra.

---

## 7.3 Path → typed params: `ParamKeys`

Engine nhỏ nhất trước. Làm sao `/users/:id` biến thành `'id'`? Đọc `src/types.ts:2706`:

```ts
export type ParamKeys<Path> = Path extends `${infer Component}/${infer Rest}`
  ? ParamKey<Component> | ParamKeys<Rest>     // split on '/', recurse
  : ParamKey<Path>
```

Nó tách đệ quy chuỗi path theo `/` (template-literal inference, §0.4) rồi cho từng segment chạy qua
`ParamKey` (`src/types.ts:2698`):

```ts
type ParamKey<Component> = Component extends `:${infer NameWithPattern}`   // starts with ':'
  ? NameWithPattern extends `${infer Name}{${infer Rest}`                  // has a {pattern}?
    ? Rest extends `${infer _Pattern}?` ? `${Name}?` : Name               // optional?
    : NameWithPattern                                                       // plain :name
  : never                                                                   // literal segment → drop
```

Vậy `ParamKeys<'/users/:id/posts/:slug'>` cho ra `'id' | 'slug'`. Một type đi kèm, `ParamKeyToRecord`
(`src/types.ts:2710`), biến union đó thành `{ id: string; slug: string }` — đúng bằng return type của
`c.req.param()`. Đó là toàn bộ engine lo phần path-typing: một conditional type đệ quy cộng với một mapped
type. Không có phép màu nào — chỉ là một interpreter tí hon mà compiler chạy trên các string literal của bạn.

> 🧠 **Mental model:** compiler đang *parse các route path của bạn ngay lúc type-check*. Mỗi `:param` thành
> một key; segment literal thành `never` rồi biến mất. Khi bạn thấy `c.req.param('id')` autocomplete, ấy là
> lúc bạn đang xem `ParamKeys` chạy.

---

## 7.4 Routes → a schema: `ToSchema`

Mỗi lần gọi `app.get(...)` trả về một `Hono` với `S` *rộng hơn* — chính là route schema tích luỹ được. Việc
nới rộng đó do `ToSchema` (`src/types.ts:2500`) đảm nhiệm, sinh ra một entry có dạng:

```ts
{ '/users/:id': { $get: { input: …; output: …; outputFormat: … } } }
```

key theo path, rồi theo `$method`. Khi bạn chain `.get().post()`, các entry này gộp lại thành một `S` to
đùng. Tính chất then chốt: `S` là một phần *type* của app, nên `typeof app` mang theo trọn bộ mô tả API. Đó
chính là thứ client đọc ở bước sau. (`Handler` `src/types.ts:76`, `MiddlewareHandler` `:83`, `Env` `:30`,
`Input` `:42` là bộ từ vựng nền mà các schema type này dựng lên trên.)

> 📌 Bạn không bao giờ thấy `S` một cách trực tiếp — nó được infer ra. Nhưng nó chính là lý do
> `export type AppType = typeof app` (dòng mà mọi tutorial Hono RPC đều bảo bạn viết) đủ để trao cho một
> project client riêng biệt toàn bộ thông tin type. Bạn đang export chính `S`.

---

## 7.5 The RPC client: `hc`

Giờ đến phần đáng tiền. `hc` (`src/client/client.ts:133`) là một hàm nhận *type* của app cùng một base URL,
rồi trả về một typed client:

```ts
export const hc = <T extends Hono<any, any, any>, Prefix extends string = string>(
  baseUrl: Prefix,
  options?: ClientRequestOptions
) => createProxy(/* path-building Proxy */, []) as UnionToIntersection<Client<T, Prefix>>
```

Lúc runtime nó là một **`Proxy`** dựng URL từ property path bạn truy cập rồi bắn một `fetch`. Lúc *compile*,
type `Client<T>` đọc schema `S` ra khỏi `T` và chiếu nó thành một object lồng nhau gồm các method đã có type.
Cụ thể:

```ts
import { hc } from 'hono/client'
const client = hc<typeof app>('https://api.example.com')
const res = await client.users[':id'].$get({ param: { id: '42' } })  // ← param typed from the route!
const data = await res.json()                                         // ← response type from the handler
```

Tham số `param` được type bởi `ParamKeys` (§7.3); response được type bởi đúng thứ handler của bạn trả về.
`InferRequestType` / `InferResponseType` (`src/client/types.ts:251`) là các helper rút những type đó ra cho
bạn khi cần dùng type trần. **No generated code** — client chỉ là một `Proxy` cộng với một phép chiếu type.

> 💡 **Tip:** đây đúng là chiêu mà tRPC đã làm cho nổi tiếng, nhưng Hono làm được mà không cần server adapter
> hay bước codegen — vì route schema vốn đã nằm sẵn trong type của app. Frontend import một *type* từ backend,
> không bao giờ import một value, nên chẳng có gì bị bundle băng qua ranh giới cả.

---

## 7.6 Validation: `validator()`

Type mô tả cái *shape* mà compiler tin tưởng; `validator()` thì cưỡng chế nó lúc *runtime*. Đọc
`src/validator/validator.ts:46`. Nó là một middleware factory:

```ts
export const validator = (target, validationFunc) => async (c, next) => {
  // 1. pull the raw value for `target`: 'json' | 'form' | 'query' | 'param' | 'header' | 'cookie'
  // 2. value = await validationFunc(value, c)
  // 3. if it returned a Response (validation failed) → return it (short-circuit)
  // 4. else c.req.addValidatedData(target, value)   ← stash the parsed/typed value
  // 5. await next()
}
```

`target` nói *chỗ nào* cần đọc (JSON body, query string, path params…); `validationFunc` là phần kiểm tra
của bạn (thường là một Zod schema qua `@hono/zod-validator`). Khi thành công, nó cất giá trị đã validate qua
`c.req.addValidatedData(...)` để handler của bạn đọc lại được, đầy đủ type, bằng `c.req.valid('json')`
(`src/request.ts:351`). Khi thất bại, nó trả về một `Response` và cái onion short-circuit ngay — route handler
không bao giờ chạy. Nó là một middleware bình thường (Chapter 5), nên nó compose như bất kỳ layer nào khác.

---

## 7.7 Lab 7 — types end-to-end

Bạn sẽ tận mắt thấy compiler cưỡng chế route type. Trong một editor hiểu TS (hoặc với `tsc`), dùng lại
`hono-hello`:

```ts
// rpc.ts
import { Hono } from 'hono'
import { hc } from 'hono/client'

const app = new Hono()
  .get('/users/:id', (c) => c.json({ id: c.req.param('id'), name: 'Ada' }))

export type AppType = typeof app             // ← exporting S

const client = hc<AppType>('http://localhost:3000')
async function demo() {
  const res = await client.users[':id'].$get({ param: { id: '42' } })
  const user = await res.json()
  console.log(user.name.toUpperCase())       // user.name is typed as string
  // @ts-expect-error — 'id' must be a string; this should fail to compile:
  await client.users[':id'].$get({ param: { id: 42 } })
}
```

```bash
cd ../hono && npx tsc --noEmit ~/hono-hello/rpc.ts   # or just hover types in your editor
```

> 🧪 **Ghi vào `labs/lab7-types.md`:** xác nhận `user.name` autocomplete ra kiểu string, và rằng dòng
> `@ts-expect-error` đúng là một lỗi thật nếu bạn bỏ comment đi (truyền `id: 42` phải fail — `ParamKeys` đã
> type nó là string). Giờ bạn đã thấy trọn chuỗi: `ParamKeys` → `ToSchema` → `hc`, tất cả ở compile time,
> tất cả bị xoá lúc runtime.

---

## 7.8 Checkpoint

1. `ParamKeys<'/a/:b/c/:d'>` cho ra kết quả gì, và hai type nào hiện thực nó?
2. `S` trong `Hono<E, S, BasePath>` là gì, và nó lớn dần lên thế nào khi bạn thêm route?
3. Lúc runtime, `hc` client thực chất *là* cái gì? Lúc compile time, các type của nó đến từ đâu?
4. Vì sao Hono RPC không cần bước sinh code, khác với các client dựa trên OpenAPI?
5. `validator('json', fn)` làm gì khi thành công so với khi thất bại, và nó liên hệ thế nào với Chapter 5?

> Nếu #1 còn lung lay, đọc lại §7.3. Nếu #3–#4 còn lung lay, đọc lại §7.4–§7.5 cùng lúc — schema và client là
> hai đầu của cùng một sợi dây.

---

## 🔌 Connect to your past (temlet web→native)

Đây là chương đáng để bạn ngồi thẳng dậy, nhất là khi bạn có temlet. Bạn đã nếm nỗi đau giữ cho frontend type
khớp với response của backend — những DTO cứ trôi lệch dần, cái `any` len lỏi vào chỗ ranh giới fetch, cái
OpenAPI generator nằm trong build của bạn. `hc` của Hono xoá sổ cả một loại công việc đó: client import
`typeof app` và *chính là* cái API contract.

Với một cuộc migration Next.js→Tauri thì điều này còn giá trị gấp đôi. Tauri vốn đã cho bạn các lời gọi
`invoke()` có type tới các Rust command băng qua native bridge; Hono cho bạn đúng kiểu typing end-to-end đó,
nhưng băng qua *HTTP* bridge. Vậy nên dù một capability nào đó của temlet cuối cùng nằm sau một Tauri command
hay sau một Hono endpoint, frontend vẫn gọi nó với type safety đầy đủ và không cần client viết tay. Bạn có một
câu chuyện nhất quán, không-cần-sinh-code cho việc "gọi backend" ở cả hai phía của đường nối web→native — và
đó đúng là kiểu nhất quán giữ cho một cuộc migration khỏi phình ra mất kiểm soát.

**Next:** [Chapter 8 — Capstone: Extending & Staying Current →](08-capstone-extending-and-staying-current.md)
