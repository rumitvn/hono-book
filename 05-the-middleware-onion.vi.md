# Chapter 5 — The Middleware Onion

> **Goal:** Đọc trọn `src/compose.ts` từ đầu tới cuối và hiểu thật chính xác cái "onion" của middleware — `await
> next()` dựng nên cấu trúc phân lớp thế nào, vì sao thứ tự chạy lại đúng như vậy, và error cùng 404 bị bắt
> chính xác ở đâu. Sau chương này bạn dự đoán được thứ tự chạy của bất kỳ stack middleware nào. Grounded trong
> `honojs/hono` tại **`v4.12.25`** (`fce483e`).

---

## 5.1 Vì sao quan trọng

Middleware là nơi phần lớn bug framework thật sự trú ngụ: "sao cái này chạy trước cái kia?", "sao error handler
của tôi không kích hoạt?", "sao response lại rỗng?". Gần như tất cả đều là hiểu nhầm về cái *onion* — sự thật
rằng mỗi middleware chạy làm hai pha, trước và sau `next()`, bọc quanh các lớp bên trong. Điều đáng nể ở Hono là
toàn bộ cơ chế nằm gọn trong **một file 73 dòng**, không có state ẩn nào cả. Đọc được `compose.ts` là bạn trả lời
dứt điểm được mọi câu hỏi về middleware.

---

## 5.2 Mental model: the onion

Cho `app.use(A); app.use(B); app.get('/', H)`, cấu trúc lúc runtime là:

```text
        request ──►┌─────────────── A ───────────────┐
                   │  A: before next()                │
                   │   ┌──────────── B ─────────────┐ │
                   │   │  B: before next()           │ │
                   │   │   ┌───────── H ──────────┐  │ │
                   │   │   │  handler runs,        │  │ │
                   │   │   │  builds the Response  │  │ │
                   │   │   └───────────────────────┘  │ │
                   │   │  B: after next()            │ │
                   │   └─────────────────────────────┘ │
                   │  A: after next()                  │
        response ◄─└───────────────────────────────────┘
```

Code *trước* `await next()` chạy trên đường đi **vào** (outer→inner). Code *sau* `await next()` chạy trên đường
đi **ra** (inner→outer). Handler `H` là lõi của onion. Đây chính là mô hình koa, và `compose.ts` hiện thực nó theo
cách sát nghĩa đen nhất có thể.

---

## 5.3 Toàn bộ thuật toán, đọc từng dòng

`compose` (`src/compose.ts:15`) nhận danh sách handler đã match và trả về một function. Phép màu nằm ở hàm đệ quy
lồng nhau `dispatch` (`src/compose.ts:32`). Đọc nó một lần, thật chậm:

```ts
export const compose = (middleware, onError?, onNotFound?) => {
  return (context, next) => {
    let index = -1
    return dispatch(0)                                   // :23 — start the onion

    async function dispatch(i) {
      if (i <= index) throw new Error('next() called multiple times')  // :33 — guard
      index = i

      let res, isError = false, handler
      if (middleware[i]) {
        handler = middleware[i][0][0]                    // :43 — the i-th handler
        context.req.routeIndex = i
      } else {
        handler = (i === middleware.length && next) || undefined  // :46 — past the end
      }

      if (handler) {
        try {
          res = await handler(context, () => dispatch(i + 1))   // :51 — run it, give it next
        } catch (err) {
          if (err instanceof Error && onError) {
            context.error = err
            res = await onError(err, context)            // :55 — error path
            isError = true
          } else { throw err }
        }
      } else {
        if (context.finalized === false && onNotFound) {
          res = await onNotFound(context)                // :63 — 404 path
        }
      }

      if (res && (context.finalized === false || isError)) {
        context.res = res                                // :68 — commit the response
      }
      return context
    }
  }
}
```

### Đúng một dòng dựng nên cái onion

Mọi thứ xoay quanh `src/compose.ts:51`:

```ts
res = await handler(context, () => dispatch(i + 1))
```

Handler được trao cho một hàm `next` mà *đúng theo nghĩa đen* là `() => dispatch(i + 1)` — "chạy lớp kế tiếp".
Khi middleware của bạn gọi `await next()`, nó **tạm dừng ngay bên trong thân hàm của chính nó** và chạy toàn bộ
phần còn lại của onion (mọi lớp sâu hơn, kể cả handler) cho tới khi xong. Chỉ khi phần đó trả về thì đoạn code sau
`await next()` của bạn mới chạy tiếp. Đó là toàn bộ cái onion: nó chỉ là một lời gọi đệ quy mà bạn `await` ở giữa
một hàm.

### The guard

`src/compose.ts:33` — `if (i <= index) throw 'next() called multiple times'`. Mỗi lớp chỉ được đi xuống *một lần*.
Gọi `next()` hai lần trong cùng một middleware sẽ vào lại một lớp đã chạy rồi, nên nó throw. `index` là một mốc
cao-nhất tăng đơn điệu (monotonic high-water mark).

### Chạm tới điểm cuối

Khi `i` vượt quá số middleware đã đăng ký (`src/compose.ts:46`), `handler` trở thành `next` bên ngoài tuỳ chọn (cho
trường hợp compose lồng nhau) hoặc `undefined`. Nếu nó là `undefined` và chưa có gì tạo ra response
(`src/compose.ts:62`), thì `onNotFound` chạy — đó là cách một route không match sinh ra một 404.

---

## 5.4 Error và 404: bị bắt ở đâu

Đây là phần ai cũng hiểu sai, nên phải nói cho chính xác:

- **Error** (`src/compose.ts:52`): khối `try/catch` bọc quanh lời gọi `await handler(...)`. Vì `next()` chính là
  `dispatch(i+1)` và bạn `await` nó, nên **một throw sâu trong onion sẽ lan ngược lên qua mọi lớp đang await** — và
  bị bắt tại lớp *đầu tiên* nằm trong khối try này. Handler `onError` (`src/compose.ts:55`) chạy, gán `context.error`,
  và giá trị trả về của nó trở thành response. Một throw không phải `Error`, hoặc khi không có `onError`, sẽ được
  re-throw (`src/compose.ts:58`).
- **404** (`src/compose.ts:62`): chỉ khi không handler nào match *và* không có gì đã finalize một response.

Nhớ lại `onError` và `onNotFound` đến từ đâu: `#dispatch` truyền `this.errorHandler` và `this.#notFoundHandler` vào
`compose` (`src/hono-base.ts:450`), và hai cái đó mặc định là các handler ở `src/hono-base.ts:31` (404) và
`src/hono-base.ts:35` (error). Bạn ghi đè chúng bằng `app.onError(...)` (`src/hono-base.ts:271`) và
`app.notFound(...)` (`src/hono-base.ts:291`).

### The finalized check

`src/compose.ts:67` — `if (res && (context.finalized === false || isError)) context.res = res`. Một response trả về
chỉ được commit nếu context chưa bị finalize (hoặc đây là đường error). Đây là mắt xích nối ngược về §4.5:
`c.finalized` (`src/context.ts:317`) là bit ngăn một middleware bên ngoài đè lên một response mà lớp bên trong đã
commit.

> 💡 **Tip:** đường fast path từ §1.4 (`src/hono-base.ts:430`) *bỏ qua hẳn `compose`* khi chỉ có đúng một handler
> match. Nên cái onion chỉ tồn tại khi bạn thật sự có middleware. Một `app.get('/', h)` trơ trọi không có `use()` sẽ
> không bao giờ cấp phát lấy một closure `dispatch` nào.

---

## 5.5 Dự đoán thứ tự chạy

Áp dụng mô hình. Với:

```ts
app.use(async (c, n) => { console.log('A in');  await n(); console.log('A out') })
app.use(async (c, n) => { console.log('B in');  await n(); console.log('B out') })
app.get('/', (c) => { console.log('H'); return c.text('ok') })
```

Output là:

```text
A in
B in
H
B out
A out
```

`A in → B in` (outer→inner, trước `next`), rồi `H`, rồi `B out → A out` (inner→outer, sau `next`). Nếu `H` throw,
throw đó sẽ tháo ngược qua các lời gọi `await n()` của `B` và `A` để tới `onError`. Nếu bạn quên `await` ở `next()`,
`A out` có thể in ra *trước khi* `H` chạy xong — đúng cái bug kinh điển của async middleware.

---

## 5.6 Lab 5 — nhìn onion tháo ngược ra, và làm nó vỡ

```ts
// onion.ts
import { Hono } from 'hono'
const app = new Hono()
const log: string[] = []

app.use(async (c, n) => { log.push('A in'); await n(); log.push('A out') })
app.use(async (c, n) => { log.push('B in'); await n(); log.push('B out') })
app.get('/', (c) => { log.push('H'); return c.text('ok') })
app.get('/boom', () => { throw new Error('kaboom') })
app.onError((err, c) => c.text(`caught: ${err.message}`, 500))

await app.request('/')
console.log('order:', log.join(' → '))

const boom = await app.request('/boom')
console.log('error:', boom.status, await boom.text())
```

```bash
bun run onion.ts
```

> 🧪 **Ghi vào `labs/lab5-onion.md`:** chuỗi thứ tự và dòng error. Kỳ vọng: `A in → B in → H →
> B out → A out`, rồi `500 caught: kaboom`. Giờ *bỏ* `await` khỏi một `n()` rồi chạy lại — để ý các dòng `out` đảo
> thứ tự thế nào. Bạn vừa tái hiện đúng cái bug middleware phổ biến nhất ngoài thực tế, và bạn giải thích được nó
> từ `src/compose.ts:51`.

---

## 5.7 Checkpoint

1. Vẽ cái onion cho `use(A); use(B); get(H)` và cho biết thứ tự console chính xác.
2. `next` là gì, theo đúng nghĩa đen, trong `compose.ts`? Trích nguyên dòng đó.
3. Vì sao gọi `next()` hai lần thì throw, và dòng nào cưỡng chế điều đó?
4. Một error do handler ném ra bị bắt chính xác ở đâu, và cái gì khiến nó lan ngược lên qua các middleware?
5. Kiểm tra `c.finalized` ở `compose.ts:67` ngăn chặn điều gì?
6. Khi nào `compose` hoàn toàn *không* được gọi?

> Nếu #2 hoặc #4 còn lung lay, đọc lại §5.3–§5.4. Nếu #6 còn lung lay, đọc lại tip của §5.4 và §1.4.

---

## 🔌 Connect to your past (temlet web→native)

Bạn đã quen với hình dạng này rồi — chỉ là bạn biết nó dưới dạng cleanup của `useEffect` trong React, hay
`(req, res, next)` của Express, hay `middleware.ts` của Next. Nhưng middleware của Next thì *phẳng*: nó chạy trước
route của bạn và có thể rewrite/redirect, nhưng nó không có pha "sau" bọc quanh handler. Onion của Hono cho bạn cả
hai nửa trong một mô hình tư duy — và bạn *nhìn thấy* được cơ chế, vì nó là 73 dòng, chứ không phải một chỗ nội bộ
của framework.

Cái độ nhìn thấy đó sinh lời khi temlet bước sang Tauri. Những mối quan tâm cross-cutting mà bây giờ bạn rải khắp
Next middleware, các route wrapper, và React effect — request logging, auth, đo thời gian, nắn error — gộp lại thành
những hàm `(c, next)` compose được, chạy giống hệt nhau ở edge lẫn phía sau native shell. Và vì `compose` chỉ là đệ
quy được `await`, phần cleanup async của bạn ("after next()") hành xử đoán trước được, thay vì mấy pha đảo thứ tự tinh
vi mà bạn gặp khi React effect cleanup và server middleware bất đồng về việc "after" là lúc nào. Khi port temlet, hãy
coi mỗi mối quan tâm cross-cutting là một lớp onion, bạn sẽ xoá được một lượng code keo dán nhiều đến bất ngờ.

**Next:** [Chapter 6 — Runtime Adapters & Portability →](06-runtime-adapters-and-portability.md)
