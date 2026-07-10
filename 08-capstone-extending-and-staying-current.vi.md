# Chapter 8 — Capstone: Extending & Staying Current

> **Goal:** Ráp tất cả lại với nhau. Viết một custom middleware và một router preset của riêng bạn, đọc một
> merged PR thật của Hono mà không cần hướng dẫn, và nắm được quy trình re-sync cuốn sách này mỗi khi bạn bump
> pin. Grounded trong `honojs/hono` tại **`v4.12.25`** (`fce483e`).

---

## 8.1 Vì sao quan trọng

Bạn đã đọc năm layer từ bên trong. Phép thử của việc *hiểu* là *xây* thêm trên chúng và *đọc* những thay đổi
mới của chúng mà không cần người dẫn đường. Chương này chính là phép thử đó — và nó kiêm luôn vai trò cẩm nang
bảo trì cho chính cuốn sách, vì Hono đi rất nhanh và cái pin của bạn rồi sẽ trôi.

---

## 8.2 Capstone phần 1 — một custom middleware

Bạn đã biết đủ mọi thứ cần thiết: middleware là một hàm `(c, next)` (Chapter 5), `c.res` là response đã được
commit (Chapter 4), và các built-in nằm trong `src/middleware/`. Hãy đọc built-in *đơn giản nhất*,
`poweredBy` (`src/middleware/powered-by/index.ts:30`), làm template của bạn:

```ts
export const poweredBy = (options?) => {
  return async function poweredBy(c, next) {
    await next()                                              // descend the onion first
    c.res.headers.set('X-Powered-By', options?.serverName ?? 'Hono')  // then tweak the response
  }
}
```

Để ý cái hình dạng: một factory trả về một `MiddlewareHandler` (`src/types.ts:83`), và nó làm việc của mình
**sau `await next()`** — pha "trên đường đi ra" từ §5.2. Giờ hãy tự viết một cái của bạn: một server-timing
middleware đo thời lượng handler và set một header.

```ts
// timing-mw.ts
import { Hono } from 'hono'
import type { MiddlewareHandler } from 'hono'

const serverTiming = (): MiddlewareHandler => async (c, next) => {
  const start = performance.now()
  await next()                                  // run the rest of the onion
  const ms = (performance.now() - start).toFixed(1)
  c.res.headers.set('Server-Timing', `app;dur=${ms}`)   // post-next: mutate committed response (§4.5)
}

const app = new Hono()
app.use(serverTiming())
app.get('/', async (c) => { await new Promise((r) => setTimeout(r, 20)); return c.text('ok') })

const res = await app.request('/')
console.log(res.headers.get('Server-Timing'))   // expect app;dur=~20
export default app
```

Mọi quyết định thiết kế ở đây đều truy về được một chương trước đó: nó là một layer trong onion (Ch 5), nó set
một header sau khi response đã được finalize (Ch 4), và nó chạy trên bất kỳ runtime nào vì nó chỉ động tới
`Response` (Ch 6). Đó là toàn bộ framework, đem ra dùng.

---

## 8.3 Capstone phần 2 — preset của riêng bạn

Một preset chỉ là một subclass của `Hono` chọn sẵn một router (§3.7). Đọc `src/preset/tiny.ts:11` — nó ~20
dòng. Hãy build một cái ép dùng `RegExpRouter` một mình (không fallback) để bạn nhận ngay một
`UnsupportedPathError` khi gặp route mập mờ — hữu ích như một lint trong CI để bắt những route lẽ ra sẽ âm thầm
fall back về TrieRouter chậm hơn:

```ts
// strict-preset.ts
import { HonoBase } from 'hono/hono-base'          // the engine (§2.2)
import { RegExpRouter } from 'hono/router/reg-exp-router'

export class StrictHono extends HonoBase {
  constructor(options = {}) {
    super(options)
    this.router = new RegExpRouter()   // no SmartRouter, no TrieRouter fallback
  }
}
```

Giờ bất kỳ route table nào không thể biểu diễn thành một regex sẽ throw ngay ở lần match đầu tiên thay vì lặng
lẽ degrade — đúng là cái sự-từ-chối của §3.5, nhưng được đưa ra làm một guardrail. Bạn đã biến một internal
error signal thành một ràng buộc thiết kế mà bạn có thể enforce.

> 💡 **Tip:** đây chính là cơ chế mà các preset chính thức `tiny`/`quick` dùng. Đọc `src/preset/` chứng minh
> rằng "swap cái router" là một extension point được hỗ trợ, không phải một cú hack.

---

## 8.4 Đọc một PR thật không cần hướng dẫn

Đã đến lúc đọc thay đổi upstream theo cách một maintainer đọc. Mở một merged PR gần đây — ví dụ
**#5013, "fix(lambda-edge): satisfy Deno lib types for Content-Length body encoding"** (merged 2026-06-09):

```bash
gh pr view 5013 --repo honojs/hono
gh pr diff 5013 --repo honojs/hono
```

Vừa đọc, vừa định vị nó trong mental model của bạn:

1. **Layer nào?** Đường dẫn `src/adapter/lambda-edge/` nói ngay cho bạn biết: đây là layer **Adapter**
   (Chapter 6), không phải core. Một thay đổi router/compose ở core sẽ đụng vào `src/router/` hoặc
   `src/compose.ts`.
2. **Nó giữ hợp đồng nào?** Adapter dịch hình dạng native của một runtime sang/từ `Request`/`Response`. Một fix
   về `Content-Length`/body-encoding là adapter làm cho đúng phần dịch `Response` cho một runtime cụ thể — core
   không hề bị đụng, và đó chính là toàn bộ ý nghĩa của §6.2.
3. **Test ở đâu?** Các thay đổi của Hono luôn kèm test; file `*.test.ts` nằm cạnh file nguồn là nơi hành vi
   được ghim lại.

> 🧪 **Ghi vào `labs/lab8-pr.md`:** chọn một PR đã merge gần đây bất kỳ, và trong 3–4 câu nói rõ nó đụng vào cái
> nào trong năm layer và giữ hoặc đổi hợp đồng nào. Nếu bạn đặt được nó vào đúng chỗ mà không cần trợ giúp, bạn
> đã hiểu kiến trúc. (Thử một core PR và một adapter PR để so sánh.)

---

## 8.5 Bắt kịp thay đổi — re-sync cuốn sách

Hono release thường xuyên. Khi bạn bump pin, các citation sẽ trôi. Quy trình:

```bash
# 1. Find the new latest tag and re-pin the clone
gh api repos/honojs/hono/tags --jq '.[0].name'
cd ../hono && git fetch --tags && git checkout <new-tag>
git log -1 --format='%h'        # record the new short SHA

# 2. Update the book's pin in ONE place
#    site_src/build_site.py → PINNED = "<new-tag>"   (and the SHA comment)

# 3. Re-verify the citations that matter most (they're listed in reference/glossary.md "Key files")
sed -n '419p' src/hono-base.ts        # should still be router.match(...)
sed -n '10p'  src/router/reg-exp-router/matcher.ts   # should still be the match() entry
# …spot-check the Key-files table; fix any line numbers that moved

# 4. Rebuild and screenshot
cd ../hono-book && python3 site_src/build_site.py
```

> ⚠️ Thứ mong manh nhất qua một lần bump version là **số dòng**, không phải khái niệm. *Hình dạng* của Hono
> (năm layer, bốn router, cái onion) thì ổn định từ release này sang release khác; còn cái dòng mà một symbol
> nằm trên đó thì không. Bảng "Key files" trong glossary là checklist re-verify của bạn — hãy đi qua nó sau mỗi
> lần re-pin.

---

## 8.6 Final checkpoint — toàn bộ cuốn sách

1. Truy một request từ `app.fetch()` tới một `Response`, gọi tên file cho từng layer trong năm layer.
2. Giải thích cái mẹo RegExpRouter và khi nào SmartRouter fall back — ý tưởng quan trọng nhất trong Hono.
3. Cho biết thứ tự console của một onion hai-middleware, và nói chỗ một error sẽ bị bắt.
4. Giải thích vì sao cùng một app chạy được trên Workers lẫn Bun mà không đổi code (`env()` + adapters).
5. Giải thích `/users/:id` trở thành một lời gọi typed `hc` client mà không cần codegen như thế nào.
6. Viết một middleware chạy logic *trước* và *sau* handler, và nói vì sao nó portable.

> Nếu câu nào còn lung lay, chương cần đọc lại đã được nêu ngay trong câu hỏi. Đây là cả cuốn sách gói trong sáu
> câu — nếu bạn trả lời được cả sáu, bạn đã hiểu `honojs/hono`.

---

## 🔌 Connect to your past (temlet web→native)

Bạn bắt đầu cuốn sách này khi đang mang temlet từ Next.js hướng về Tauri, với một server layer cưới chặt vào
Node. Bạn kết thúc nó với một lựa chọn khác đặt lên bàn: một HTTP layer *runtime-agnostic ngay từ trong cấu
trúc* — một cái chạy trên edge hôm nay, đứng sau một native shell ngày mai, với typed client ở cả hai phía và
logic cross-cutting được diễn đạt thành các onion layer có thể compose.

Bài học sâu hơn không phải là "hãy dùng Hono." Nó là *kỷ luật* mà Hono thể hiện: xây trên chính các hợp đồng
của nền tảng (`Request`/`Response`), đẩy mọi thứ đặc thù cho runtime ra một mép mỏng, có thể swap (các adapter),
và để types — không phải codegen — mang API của bạn băng qua các ranh giới. Đó cũng chính là kỷ luật khiến một
cuộc di cư web→native thành khả thi thay vì một cuộc viết lại. Dù bạn chọn gì cho backend của temlet, giờ bạn
đã biết "portable by design" thật sự trông ra sao trong source — và bạn có thể đọc cái edge framework kế tiếp
xuất hiện bằng đúng thứ ánh sáng năm-layer đó.

**Done.** Đọc lại [flagship router chapter](03-the-router.md) một lần nữa — nó xứng đáng với lượt đọc thứ hai —
và giữ `../hono` mở sẵn. Cuốn sách vẫn hữu ích như một tấm bản đồ mỗi lần bạn mở source ra.

*A RumitX publication · [rumitx.com](https://rumitx.com)*
