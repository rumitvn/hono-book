# Glossary & Source-File Index

Quick reference for the Hono internals terms used in this book. Pinned tag `v4.12.25`
(commit `fce483e`). Citations are into the local clone at `../hono/src/`.

## Khái niệm cốt lõi

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **Web standards** | Hono chỉ nói đúng `Request`/`Response` của nền tảng — không có gì proprietary ở ranh giới; đây là gốc rễ của mọi tính portable | 0, 6 |
| **`Request` / `Response`** | các object của Fetch API nằm ở ranh giới input và output của Hono; một Hono app "chỉ" là một hàm nằm giữa chúng | 0 |
| **One-shot body** | body của request/response là một stream chỉ đọc được một lần; đây là lý do tồn tại của `bodyCache` | 0, 2 |
| **Five layers** | App → Router → compose → Context → Adapter | 1 |
| **`HonoBase` / `Hono`** | `HonoBase` là engine (registration, dispatch); `Hono` là subclass mỏng chọn sẵn một router mặc định | 2 |
| **`#dispatch`** | bộ điều phối theo từng request bên trong `HonoBase`: getPath → match → Context → fast/onion path | 1, 2 |
| **Fast path vs onion path** | một handler khớp thì được gọi thẳng; nhiều handler thì đi qua `compose` | 1, 5 |
| **`RouterRoute`** | bản ghi route được giữ trong `app.routes` để introspection (không dùng cho việc matching) | 2 |

## Router (bản flagship)

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **`Router<T>` interface** | hợp đồng hai method (`add`, `match`) mà mọi router phải hiện thực; generic theo payload của handler | 3 |
| **`Result<T>`** | giá trị match trả về: `[[handler, paramIndexMap][], paramStash]` *hoặc* `[[handler, params][]]` | 3 |
| **LinearRouter** | quét mọi route cho mỗi request; zero build cost — hợp cho các one-shot worker | 3 |
| **TrieRouter** | một prefix tree gồm các path segment; O(segments), xử lý được *bất kỳ* routing table nào — fallback vạn năng | 3 |
| **RegExpRouter** | gộp mọi route thành **một** `RegExp` duy nhất; việc matching chỉ là một lần `path.match()` | 3 |
| **SmartRouter** | thử RegExpRouter trước, gặp `UnsupportedPathError` thì fallback sang TrieRouter; đây là mặc định | 3 |
| **`UnsupportedPathError`** | được ném ra khi một routing table quá mơ hồ để gói vào một regex; tín hiệu mà SmartRouter bắt lấy | 3 |
| **Static map** | từ điển O(1) của RegExpRouter cho các route thuần tĩnh, được kiểm trước khi chạy regex | 3 |
| **Self-replacing `match`** | RegExpRouter/SmartRouter ghi đè `this.match` sau lần gọi đầu để các lần sau bỏ qua bước build | 3 |
| **Marker group** | nhóm capture rỗng neo ở cuối `$()`, mà vị trí của nó cho biết handler nào đã khớp | 3 |
| **Presets** | `hono/quick` (Linear+Trie, no build) và `hono/tiny` (Pattern, nhỏ nhất) thay router mặc định | 3 |

## Context & response

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **`Context` (`c`)** | object theo từng request: request, response builder, env, và vùng nháp | 4 |
| **`c.json/text/html`** | lớp cú pháp gọn phủ lên `new Response()` — serialize + content-type mặc định + build | 4 |
| **`#newResponse`** | constructor response private mà mọi responder `c.*` đều dồn về | 4 |
| **`c.finalized`** | cái bit lật lên khi một response đã được commit; ngăn các layer bên ngoài ghi đè lên nó | 4, 5 |
| **Buffered headers/status** | `c.header`/`c.status` buffer phần metadata, được áp khi response được build (đặt chúng *trước* body) | 4 |
| **`c.env`** | các binding của runtime (KV, secrets, …); điểm nối để nền tảng inject vào | 4, 6 |
| **`c.var` / `c.set` / `c.get`** | state theo từng request, có type, qua một `Map`; kênh nối middleware→handler | 4 |
| **`HonoRequest`** | lớp wrapper quanh `Request` của web; thêm `param/query/header/json`, giữ lại `.raw` | 2, 4 |

## Middleware onion

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **`compose`** | hàm 73 dòng kiểu koa, xâu chuỗi các handler thành cái onion | 5 |
| **`dispatch(i)`** | hàm con đệ quy; `await dispatch(i+1)` chính là thứ mà `next()` chạy | 5 |
| **`next()`** | đúng nghĩa đen là `() => dispatch(i + 1)` — chạy nốt phần còn lại của onion, rồi quay lại chạy tiếp | 5 |
| **Onion (before/after)** | code trước `next()` chạy theo hướng ngoài→trong; sau `next()` chạy trong→ngoài | 5 |
| **`onError` / `notFound`** | các handler xử lý lỗi và 404 mà `compose` fallback về; có thể override qua `app.onError`/`app.notFound` | 5 |

## Adapter runtime & tính portable

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **Adapter** | một lớp vỏ mỏng theo từng runtime, ánh xạ hình dạng entry native qua lại với `app.fetch` | 6 |
| **`getRuntimeKey()`** | phát hiện runtime; ưu tiên `navigator.userAgent` đã chuẩn hóa, rồi mới đến các global riêng của vendor | 6 |
| **`env(c)`** | resolve các binding theo từng runtime (`process.env` / `Deno.env` / `c.env`); DI ngay tại ranh giới runtime | 6 |
| **Streaming / SSE** | `stream`/`streamSSE`/`streamText` build ra một `Response` với body là `ReadableStream` — vẫn thuần web-standard | 6 |

## Type, RPC & validation

| Term | Nghĩa | Chương |
|------|-----------|---------|
| **`ParamKeys<Path>`** | một conditional type đệ quy, rút các tên `:param` ra từ một chuỗi path | 7 |
| **`ToSchema`** | dồn từng route vào schema type `S` mà `Hono<E, S, BasePath>` mang theo | 7 |
| **`hc` client** | một `Proxy` lúc runtime + phép chiếu `S` lúc compile-time → một RPC client có type, không cần codegen | 7 |
| **`validator()`** | middleware đọc một target (json/query/param/…), chạy kiểm tra, rồi cất phần data đã validate | 7 |
| **`c.req.valid(target)`** | đọc lại giá trị mà `validator()` đã cất, có type đầy đủ | 7 |

## Key files (bắt đầu từ đây khi điều tra)

| File | What | Anchors |
|------|------|---------|
| `src/index.ts` | bề mặt công khai | `Hono` import (`:17`), public type exports (`:22`), `Context` (`:39`), `HonoRequest` (`:44`) |
| `src/hono.ts` | class `Hono` cụ thể | `class Hono` (`:16`), constructor + default `SmartRouter` (`:26`–`32`) |
| `src/hono-base.ts` | engine: registration + dispatch | `class Hono`/HonoBase (`:98`), method-handler loop (`:128`), `route` (`:208`), `onError` (`:271`), `notFound` (`:291`), `#addRoute` (`:385`), `router.add` (`:395`), `#dispatch` (`:406`), `router.match` (`:419`), fast path (`:430`), `compose(...)` (`:450`), `fetch` (`:479`), `request` (`:499`); default 404 (`:31`) / error (`:35`) handlers |
| `src/request.ts` | lớp wrapper `HonoRequest` | `class HonoRequest` (`:36`), `raw` (`:51`), `path` (`:68`), `bodyCache` (`:69`), `param` (`:94`), `query` (`:148`), `header` (`:185`), `json` (`:253`), `valid` (`:351`) |
| `src/router.ts` | hợp đồng của router | `interface Router<T>` (`:29`), `Result<T>` (`:98`), `UnsupportedPathError` (`:103`) |
| `src/router/reg-exp-router/router.ts` | engine một-regex | `add` (`:132`), `buildAllMatchers` (`:208`), `#buildMatcher` (`:224`), `buildMatcherFromPreprocessedRoutes` (`:34`) |
| `src/router/reg-exp-router/trie.ts` / `node.ts` / `matcher.ts` | lắp ráp regex + match | `Trie.buildRegExp` (`trie.ts:49`), marker rewrite (`trie.ts:59`), `Node.buildRegExpStr` (`node.ts:135`), param marker `(k)@varIndex` (`node.ts:142`), `match` entry (`matcher.ts:10`), static fast path (`matcher.ts:18`), which-group (`matcher.ts:27`), self-replace (`matcher.ts:31`) |
| `src/router/smart-router/router.ts` | giải đấu fallback | `add` (`:13`), `match` tournament (`:21`), fallback `continue` (`:43`), bind winner (`:46`) |
| `src/router/trie-router/node.ts` | trie fallback | `insert` (`:44`), `search` (`:114`) |
| `src/router/linear-router/router.ts` / `pattern-router/router.ts` | các bản nền | LinearRouter `add` (`linear:15`)/`match` (`linear:25`); PatternRouter (`pattern-router/router.ts`) |
| `src/preset/quick.ts` / `tiny.ts` | các router mặc định thay thế | `quick` = Smart(Linear,Trie) (`quick.ts:13`), `tiny` = PatternRouter (`tiny.ts:11`) |
| `src/context.ts` | object `Context` | `class Context` (`:293`), constructor (`:352`), `env` (`:315`), `finalized` (`:317`), `req` (`:366`), `res` (`:403`), `header` (`:515`), `status` (`:529`), `set` (`:546`), `get` (`:571`), `#newResponse` (`:604`), `body` (`:664`), `text` (`:682`), `json` (`:708`), `html` (`:723`), `redirect` (`:750`), `notFound` (`:776`) |
| `src/compose.ts` | cái middleware onion | `compose` (`:15`), guard (`:33`), the i-th handler (`:43`), `await handler(c, next)` (`:51`), `onError` (`:55`), `onNotFound` (`:63`), commit (`:67`) |
| `src/helper/adapter/index.ts` | phát hiện runtime + bindings | `Runtime` type (`:8`), `env()` (`:10`), `getRuntimeKey()` (`:50`) |
| `src/adapter/cloudflare-workers/index.ts` | một adapter tiêu biểu | `serveStatic` (`:6`), `upgradeWebSocket` (`:7`), `getConnInfo` (`:8`) |
| `src/helper/streaming/index.ts` | các helper streaming | `stream`/`streamSSE`/`streamText` exports, `SSEMessage` (`sse.ts:6`) |
| `src/types.ts` | bộ máy ở tầng type (2,778 lines) | `Env` (`:30`), `Input` (`:42`), `Handler` (`:76`), `MiddlewareHandler` (`:83`), `ToSchema` (`:2500`), `ParamKey` (`:2698`), `ParamKeys` (`:2706`), `ParamKeyToRecord` (`:2710`) |
| `src/client/client.ts` | cái RPC client | `hc` (`:133`); `InferResponseType` (`client/types.ts:251`) |
| `src/validator/validator.ts` | middleware validation | `validator` (`:46`) |
| `src/middleware/powered-by/index.ts` | middleware built-in đơn giản nhất (một template) | `poweredBy` (`:30`) |

> ⚠️ Số dòng được pin theo `v4.12.25` (`fce483e`). Khi bạn bump cái pin, *hình dạng* tổng thể (năm layer,
> bốn router, cái onion) vẫn ổn định, nhưng các con số này sẽ trôi — hãy verify lại bảng này bằng `sed -n`
> sau mỗi lần re-pin. (Xem Chương 8 §8.5.)

<sub>A **RumitX** publication · [rumitx.com](https://rumitx.com)</sub>
