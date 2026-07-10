# Chapter 3 — The Router ★

> **Goal:** Hiểu abstraction trung tâm của Hono: **four routers behind one interface**, và cái mánh
> khiến Hono trở thành một trong những router nhanh nhất trong JavaScript — việc `RegExpRouter` gộp mọi
> route đã đăng ký thành một regex *duy nhất*. Rồi hiểu vì sao mánh đó không phải lúc nào cũng áp dụng
> được, và cách `SmartRouter` lặng lẽ fallback. Neo trên `honojs/hono` tại **`v4.12.25`** (`fce483e`).
>
> Đây là chương flagship. Cứ thong thả; đọc kỹ từng file được trích dẫn.

---

## 3.1 Vì sao quan trọng

Routing là hot loop của một web framework: nó chạy trên *mọi request*, trước cả code của bạn. Một router
chậm sẽ đánh thuế lên từng endpoint. Đa số framework lưu route trong một list hoặc một tree rồi duyệt qua
nó mỗi request — ổn thôi, nhưng tuyến tính theo số lượng route hoặc số path segment.

Hono đặt một câu hỏi sắc hơn: *nếu như match một path chỉ là một phép test regex duy nhất, bất kể bạn đã
đăng ký bao nhiêu route thì sao?* Câu trả lời là `RegExpRouter`, và phần kỹ thuật xoay quanh "nhưng đôi khi
điều đó bất khả thi" mới là thứ khiến thiết kế này thực sự thông minh chứ không đơn thuần là nhanh. Hiểu
được nó, bạn học được một điều vượt xa khỏi Hono: cách biến một lookup O(n) thành O(1) bằng cách precompile.

---

## 3.2 Bản hợp đồng: một interface, bốn implementation

Mọi router đều implement cùng một interface bé xíu (`src/router.ts:29`):

```ts
export interface Router<T> {
  name: string
  add(method: string, path: string, handler: T): void   // :42
  match(method: string, path: string): Result<T>          // :51
}
```

Hai method. `add` để đăng ký; `match` để tra cứu. Interface này **generic theo `T`** — router không bao giờ
biết một "handler" thực chất là gì. (Nhớ lại §2.4: App trao cho nó tuple `[handler, routerRoute]`. Router
mang cái payload mờ đục đó xuyên qua rồi trả lại nguyên vẹn.)

Kiểu trả về mới là chỗ tinh tế (`src/router.ts:98`):

```ts
export type Result<T> = [[T, ParamIndexMap][], ParamStash] | [[T, Params][]]
```

Một union của hai hình dạng. Hoặc là `[[handler, paramIndexMap][], paramStash]` — handler đi kèm *chỉ số*
trỏ vào một mảng dùng chung chứa các chuỗi đã capture — hoặc `[[handler, paramsObject][]]` — handler đi kèm
object param dựng sẵn. Hình dạng thứ nhất là hình dạng nhanh (được `RegExpRouter` dùng): nó tránh việc dựng
một object param cho tới khi bạn thực sự gọi `c.req.param()`.

Và một error đặc biệt (`src/router.ts:103`):

```ts
export class UnsupportedPathError extends Error {}
```

Nhớ lấy class này. Nó là bản lề của toàn bộ thiết kế.

```text
                       ┌──────────────────────────┐
   app.get/post  ───►  │   Router<T> interface     │  ◄── one contract
                       │   add() / match()          │
                       └────────────┬───────────────┘
            ┌───────────────┬───────┴───────┬────────────────┐
            ▼               ▼               ▼                ▼
      LinearRouter    TrieRouter     RegExpRouter      SmartRouter
      scan a list     walk a trie    ONE big regex    try fast, fall back
      (simplest)      (general)      (fastest)        (the default)
```

Đọc từng cái một — bốn case study, từ đơn giản nhất tới thông minh nhất.

---

## 3.3 Case study 1 — LinearRouter (the baseline)

`src/router/linear-router/router.ts` (144 dòng). Thứ đơn giản nhất mà vẫn chạy được.

- `add` (`src/router/linear-router/router.ts:15`) đẩy `[method, path, handler]` vào một mảng. O(1), không
  cần tiền xử lý.
- `match` (`src/router/linear-router/router.ts:25`) **quét toàn bộ mảng** trên mỗi request, kiểm mỗi route
  so với path bằng string check và một regex riêng cho từng route để xử lý `:params`.

Cách này tốn O(routes) mỗi request, nhưng chi phí build bằng *không* — nên preset `quick` mới dùng nó
(§3.7): với một Worker đời ngắn chỉ đăng ký vài route và xử lý đúng một request, việc build một regex to là
không đáng. LinearRouter thắng khi thời gian từ lúc đăng ký tới match đầu tiên mới là thứ chi phối.

> 💡 **Tip:** "phiên bản ngây thơ đôi khi lại là phiên bản đúng" là một bài học kỹ thuật thật sự ở đây. Hono
> ship LinearRouter không phải như một món đồ chơi để dạy học mà như một lựa chọn production thực thụ cho các
> môi trường nhạy cảm với cold start.

---

## 3.4 Case study 2 — TrieRouter (the general one)

`src/router/trie-router/` — `router.ts` (28 dòng) ủy thác cho `node.ts` (234 dòng), một prefix tree.

- `add` → `Node.insert` (`src/router/trie-router/node.ts:44`): tách path thành các segment rồi duyệt/dựng
  một tree, mỗi segment một node. Một segment `:param` trở thành một node mang pattern; `*` trở thành một
  node wildcard.
- `match` → `Node.search` (`src/router/trie-router/node.ts:114`): duyệt tree lần theo các segment của path
  đến, gom handler và bind param trong lúc đi xuống.

Match tốn O(số path segment), không phụ thuộc vào việc có bao nhiêu route — một cải thiện thực sự so với
LinearRouter. Và quan trọng hơn cả, **một trie biểu diễn được mọi routing table**, kể cả những bảng nhập
nhằng làm `RegExpRouter` bó tay (phần sau). Chính tính phổ quát đó là lý do TrieRouter luôn là **fallback**.

> 🧠 **Mental model:** trie là cấu trúc dữ liệu "hiển nhiên đúng" cho routing — mỗi path là một hành trình đi
> từ root. RegExpRouter là cấu trúc "thông minh nhanh". Hono giữ cả hai vì mỗi cái thắng ở một cuộc đua khác
> nhau: TrieRouter không bao giờ hỏng; RegExpRouter nhanh hơn khi nó làm được.

---

## 3.5 Case study 3 — RegExpRouter ★ (the one-regex trick)

`src/router/reg-exp-router/` — `router.ts` (252), `trie.ts` (74), `node.ts` (162), `matcher.ts` (33). Đây
là trung tâm của mọi thứ. Ý tưởng:

> **Compile *all* registered routes into a single `RegExp`.** Match một request khi đó chỉ còn là một lời gọi
> `path.match()`. Route nào khớp thì đọc ra từ việc *capture group nào* đã kích hoạt.

### Đăng ký thì hoãn phần việc lại

`add` (`src/router/reg-exp-router/router.ts:132`) **không** build regex. Nó chỉ xếp mỗi route vào các map
`#middleware` / `#routes`, key theo method và path. Phần compile tốn kém được hoãn lại tới lần `match()` đầu
tiên.

### match đầu tiên kích hoạt compile

Method `match` (`src/router/reg-exp-router/matcher.ts:10`) làm một chuyện ranh mãnh ngay ở lần gọi đầu tiên:

```ts
export function match<R, T>(this: R, method, path): Result<T> {
  const matchers = this.buildAllMatchers()   // compile, ONCE   ← :12

  const match = ((method, path) => {          // the real, fast matcher
    const matcher = matchers[method] || matchers[METHOD_NAME_ALL]
    const staticMatch = matcher[2][path]       // O(1) static-route map  ← :18
    if (staticMatch) return staticMatch
    const m = path.match(matcher[0])           // THE ONE REGEX           ← :23
    if (!m) return [[], emptyParam]
    const index = m.indexOf('', 1)             // which group fired?      ← :27
    return [matcher[1][index], m]
  })

  this.match = match                           // self-replace!           ← :31
  return match(method, path)
}
```

Hai mánh đẹp ở đây:

1. **Method tự thay thế chính mình (`:31`).** Ở lần gọi đầu nó compile, rồi *ghi đè `this.match`* bằng
   closure nhanh. Mọi request sau đó bỏ qua hoàn toàn bước compile — không có phép kiểm `if (built)` nào
   trên hot path, vì hàm này tự viết lại chính nó ra khỏi sự tồn tại.
2. **Đường tắt cho static (`:18`).** Các route thuần static (`/health`, `/api/users`) được giữ trong một
   object thường `matcher[2]` để lookup O(1), *trước cả khi* regex chạy. Những API nặng về static gần như
   không đụng tới regex.

### Dựng cái regex duy nhất

`buildAllMatchers` (`src/router/reg-exp-router/router.ts:208`) compile một matcher cho mỗi HTTP method, rồi
**giải phóng các map route** để trả lại bộ nhớ — sau đó thêm một route sẽ ném ra "matcher is already built".
Phần nặng nhọc nằm ở `buildMatcherFromPreprocessedRoutes` (`src/router/reg-exp-router/router.ts:34`):

1. Nó đưa mọi path vào một `Trie` (`src/router/reg-exp-router/trie.ts`).
2. `trie.buildRegExp()` (`src/router/reg-exp-router/trie.ts:49`) duyệt cái trie đó qua
   `Node.buildRegExpStr()` (`src/router/reg-exp-router/node.ts:135`) và phát ra **một chuỗi regex duy nhất**
   dựng từ cây route, có nhúng sẵn các marker token:
   - `#N` đánh dấu "handler N khớp ở đây" — một node param phát ra `(${pattern})@varIndex`
     (`src/router/reg-exp-router/node.ts:142`).
   - Một bước `replace` hậu xử lý (`trie.ts:59`) viết lại mỗi marker `#N` thành một **empty capture group
     neo-cuối `$()`**, ghi lại trong `indexReplacementMap` xem vị trí capture-group nào ánh xạ tới handler
     nào.

Vậy với hai route `/foo` (handler 0) và `/posts/:id` (handler 1), bạn nhận được một regex có hình dạng đại
khái như:

```text
^(?:foo$()|posts/([^/]+)$())
        └─ empty group #1 → handler 0
                         └─ empty group #2 → handler 1, with ([^/]+) capturing :id
```

Khi một path khớp, `m.indexOf('', 1)` (`matcher.ts:27`) tìm ra *chuỗi rỗng đầu tiên* trong mảng kết quả
match — đó chính là empty marker group đã kích hoạt — và chỉ số của nó cho bạn biết handler. **Một phép test
regex, thời gian gần như hằng số, bất kể bạn đăng ký bao nhiêu route.** Đó là toàn bộ mánh khóe.

### Khi mánh này thất bại

Một regex đơn lẻ không thể phân định mọi routing table. Hai route mà param của chúng va nhau ở cùng một vị
trí — ví dụ `/:user/entries` và `/entry/:name`, nơi `/entry/entries` thực sự nhập nhằng — không thể mã hóa
thành một regex không nhập nhằng. Khi `Node.insert` phát hiện một xung đột như thế, nó ném `PATH_ERROR`, và
`buildMatcherFromPreprocessedRoutes` chuyển nó thành `UnsupportedPathError`
(`src/router/reg-exp-router/router.ts`, trong khối try/catch quanh `trie.insert`). RegExpRouter **không**
xuống cấp một cách êm ái — nó từ chối thẳng. Sự từ chối đó là một tính năng, nhờ vào case study kế tiếp.

---

## 3.6 Case study 4 — SmartRouter (the default)

`src/router/smart-router/router.ts` (70 dòng). Đây là router mà `new Hono()` thực sự dùng (nhớ lại
`src/hono.ts:31`: `new SmartRouter({ routers: [new RegExpRouter(), new TrieRouter()] })`).

- `add` (`src/router/smart-router/router.ts:13`) chỉ xếp `[method, path, handler]` vào hàng đợi — nó chưa
  commit vào router nào cả.
- `match` (`src/router/smart-router/router.ts:21`) chạy một **giải đấu** ngay ở request đầu tiên:

```ts
for (; i < len; i++) {
  const router = routers[i]
  try {
    for (…) router.add(...routes[i])      // replay all routes into this candidate
    res = router.match(method, path)       // try to match
  } catch (e) {
    if (e instanceof UnsupportedPathError) continue   // ← fall back to next router
    throw e
  }
  this.match = router.match.bind(router)   // winner! self-replace            (:46)
  this.#routers = [router]                  // discard the losers
  this.#routes = undefined                  // free the queue
  break
}
```

Nó thử `RegExpRouter` trước. Nếu cái đó ném `UnsupportedPathError` (chính là cú từ chối ở §3.5), nó
`continue` sang `TrieRouter`, cái không bao giờ từ chối. Khi một router thành công, SmartRouter **bind
`this.match` vào kẻ thắng cuộc** (`src/router/smart-router/router.ts:46`) và bỏ đi phần còn lại — nên, giống
như RegExpRouter, mọi request về sau bỏ qua hoàn toàn giải đấu.

> 🧠 **Mental model:** SmartRouter là kiểu "lạc quan nhưng có lưới an toàn." Nó đặt cược vào router nhanh, và
> `UnsupportedPathError` là tín hiệu nói rằng "route của bạn quá nhập nhằng cho cái mánh này — dùng cái tổng
> quát đi." Bạn trả cái giá của giải đấu đúng *một lần*. Đây là lý do bạn hiếm khi phải bận tâm về router của
> Hono: mặc định lặng lẽ cho bạn tốc độ của RegExpRouter khi route cho phép, và sự đúng đắn của TrieRouter
> khi không.

---

## 3.7 Preset: chọn một default khác

Hai preset đánh đổi router lấy những trade-off khác nhau (đọc cả hai — mỗi cái chừng ~20 dòng):

- `hono/quick` (`src/preset/quick.ts:13`) — `SmartRouter([LinearRouter, TrieRouter])`. Không build regex:
  tối ưu cho những môi trường xử lý **một request cho mỗi worker** (kiểu cold start FaaS kinh điển), nơi chi
  phí build sẽ chẳng bao giờ khấu hao nổi.
- `hono/tiny` (`src/preset/tiny.ts:11`) — chỉ mỗi `PatternRouter` (`src/router/pattern-router/router.ts`,
  60 dòng: một regex *cho mỗi route*). Kích thước code nhỏ nhất — cho những deploy khắt khe về bundle-size.

Bản import `hono` cơ bản được chỉnh cho các server/Worker sống lâu xử lý nhiều request, nên khấu hao một lần
build regex là lựa chọn đúng.

| Preset | Router | Phù hợp nhất cho |
|--------|---------|----------|
| `hono` (mặc định) | Smart(RegExp, Trie) | server / Worker sống lâu — tốc độ đã khấu hao |
| `hono/quick` | Smart(Linear, Trie) | FaaS một-phát — không chi phí build |
| `hono/tiny`  | Pattern | bundle nhỏ nhất |

---

## 3.8 Lab 3 — xem SmartRouter chọn router

`SmartRouter.name` được cập nhật để ghi lại kẻ thắng cuộc (`src/router/smart-router/router.ts` gán
`SmartRouter + <winner>`). Tận dụng điều đó để *thấy tận mắt* cú fallback diễn ra:

```ts
// router-probe.ts
import { RegExpRouter } from 'hono/router/reg-exp-router'
import { TrieRouter } from 'hono/router/trie-router'
import { SmartRouter } from 'hono/router/smart-router'

function probe(label: string, register: (r: SmartRouter<string>) => void) {
  const r = new SmartRouter<string>({ routers: [new RegExpRouter(), new TrieRouter()] })
  register(r)
  r.match('GET', '/x')                 // force the tournament
  console.log(label, '→', r.name)
}

probe('clean routes', (r) => { r.add('GET', '/users/:id', 'h') })
probe('ambiguous   ', (r) => {
  r.add('GET', '/:user/entries', 'a')
  r.add('GET', '/entry/:name', 'b')
})
```

```bash
bun run router-probe.ts
```

> 🧪 **Ghi vào `labs/lab3-router.md`:** hai tên router được in ra. Kỳ vọng: bảng route sạch cho ra
> `SmartRouter + RegExpRouter`, còn bảng nhập nhằng buộc phải là `SmartRouter + TrieRouter`. Bạn vừa chứng
> kiến `UnsupportedPathError` kích hoạt cú fallback từ §3.6 — luồng điều khiển quan trọng bậc nhất trong
> routing của Hono.

---

## 3.9 Checkpoint

1. Trình bày interface `Router<T>` từ trí nhớ. Vì sao nó generic theo `T`?
2. Trong một câu: `RegExpRouter` làm điều gì mà các router khác không làm?
3. Hai "mánh" trong `matcher.ts` là gì — method tự thay thế và static map — và mỗi cái tiết kiệm được gì?
4. Khi regex đã gộp khớp, làm sao Hono biết *route nào* đã khớp? (Nêu tên marker và dòng.)
5. `UnsupportedPathError` báo hiệu điều gì, ai ném nó, và ai bắt nó?
6. `new Hono()` dùng router nào theo mặc định, còn `hono/quick` dùng cái nào — và vì sao lại khác nhau?

> Nếu câu #2 hoặc #4 còn lung lay, đọc lại §3.5. Nếu câu #5 còn lung lay, đọc §3.5–§3.6 cùng nhau — cú ném và
> cú bắt là hai nửa của cùng một ý tưởng.

---

## 🔌 Connect to your past (temlet web→native)

Router của Next.js là một hộp đen: các quy ước file-system được framework compile, với hiệu năng bạn không
nhìn thấy cũng không suy luận được. Bạn tin là nó chạy. Hono trao cho bạn điều ngược lại — một router bạn
*đọc hết trong một buổi chiều* và có thể giải thích được mô hình hiệu năng của nó.

Điều đó có ý nghĩa với hành trình web→native của temlet theo một cách rất cụ thể. Trên edge (Workers), độ
trễ request bị chi phối bởi cold start và overhead mỗi request — đúng cái mà precompile-một-lần + đường tắt
static của RegExpRouter tối ưu, và cũng đúng cái mà `hono/quick` đánh đổi đi khi bạn chạy một-phát. Đằng sau
một lớp vỏ **Tauri**, nơi server sống lâu và chạy cục bộ, bạn sẽ muốn tốc độ đã khấu hao của bản mặc định.
Bài học không phải là "Hono nhanh"; mà là chiến lược của router là một *cái núm bạn điều khiển*, chọn theo
runtime bạn đang nhắm tới. Khi bạn port routing của temlet lên một thứ như thế này, bạn thôi hy vọng
framework đã chọn đúng và bắt đầu tự mình chọn — theo từng deployment target.

**Next:** [Chapter 4 — Context & Building Responses →](04-context-and-responses.md)
