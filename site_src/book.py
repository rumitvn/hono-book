#!/usr/bin/env python3
"""Per-book configuration for the Hono Internals Handbook.

This is the ONLY file that differs between RumitX books. engine.py next to it is
byte-identical everywhere.

Register note (see learning/CLAUDE.md): chapter titles stay in English in both
locales — they name the technology, they match each chapter's H1, and the reader
meets them in the source. Vietnamese carries the prose: descriptions, hero copy,
and UI chrome.
"""

REPO_URL = "https://github.com/rumitvn/hono-book"   # the book's own repo (labs/ blob links)
UPSTREAM = "https://github.com/honojs/hono"          # the framework we study
UPSTREAM_NAME = "honojs/hono"
PINNED = "v4.12.25"                                  # pinned tag (commit fce483e)
UPSTREAM_PINNED = UPSTREAM + "/tree/" + PINNED

# code-fence languages this book uses beyond the engine's defaults
LANG_LABEL_EXTRA = {
    "rust": "Rust", "rs": "Rust", "toml": "TOML", "jsonc": "jsonc",
    "ts": "TypeScript", "typescript": "TypeScript", "tsx": "TSX",
    "sql": "SQL", "tcl": "Tcl", "make": "Makefile", "y": "Lemon",
}

# (number, stem, flag, {locale: (title, description)})
CHAPTERS = [
    ("00", "00-environment-and-typescript-web-refresher", "Foundation", {
        "en": ("Environment & TypeScript / Web-standards Refresher",
               "Get a green build with Bun + Vitest, and refresh the two pillars Hono is built on — the Fetch API (`Request`/`Response`) and the TypeScript generics & conditional types that power its type-safe routes."),
        "vi": ("Environment & TypeScript / Web-standards Refresher",
               "Dựng một build chạy xanh với Bun + Vitest, rồi ôn lại hai trụ cột mà Hono dựa lên — Fetch API (`Request`/`Response`) và generics & conditional types của TypeScript, thứ làm nên các route type-safe của nó."),
    }),
    ("01", "01-mental-model-and-repo-map", "Foundation", {
        "en": ("Mental Model & Repo Map",
               "The five-layer model — App → Router → compose → Context → Adapter — and a real end-to-end trace of one request from `app.fetch()` to a `Response`."),
        "vi": ("Mental Model & Repo Map",
               "Mô hình năm tầng — App → Router → compose → Context → Adapter — và một trace thật từ đầu đến cuối của một request, từ `app.fetch()` tới một `Response`."),
    }),
    ("02", "02-app-lifecycle-and-request", "Foundation", {
        "en": ("The App Object & HonoRequest",
               "How `new Hono()`, `.get()`/`.use()` route registration, and the `fetch` entrypoint actually work, plus the `HonoRequest` wrapper around the web `Request`."),
        "vi": ("The App Object & HonoRequest",
               "Cách `new Hono()`, việc đăng ký route bằng `.get()`/`.use()`, và entrypoint `fetch` thực sự hoạt động ra sao, cùng với wrapper `HonoRequest` bọc quanh `Request` của web."),
    }),
    ("03", "03-the-router", "★ Flagship", {
        "en": ("The Router",
               "Hono's central abstraction: four routers, one interface. LinearRouter, TrieRouter, the RegExpRouter “merge every route into one regex” trick, and the SmartRouter that picks between them — in four case studies."),
        "vi": ("The Router",
               "Abstraction trung tâm của Hono: bốn router, một interface. LinearRouter, TrieRouter, mẹo “gộp mọi route vào một regex” của RegExpRouter, và SmartRouter chọn giữa chúng — qua bốn case study."),
    }),
    ("04", "04-context-and-responses", "Core", {
        "en": ("Context & Building Responses",
               "The `c` object: `c.json/text/html`, `c.req`, `c.env`, the `c.var` store, and how headers and status are buffered then finalized into a `Response`."),
        "vi": ("Context & Building Responses",
               "Object `c`: `c.json/text/html`, `c.req`, `c.env`, kho `c.var`, và cách header cùng status được buffer rồi chốt lại thành một `Response`."),
    }),
    ("05", "05-the-middleware-onion", "Core", {
        "en": ("The Middleware Onion",
               "The `compose()` algorithm: how `await next()` builds the onion, how ordering works, and how errors and 404s propagate through `onError` and `notFound`."),
        "vi": ("The Middleware Onion",
               "Thuật toán `compose()`: cách `await next()` dựng nên lớp onion, thứ tự chạy ra sao, và cách error cùng 404 lan qua `onError` và `notFound`."),
    }),
    ("06", "06-runtime-adapters-and-portability", "Application", {
        "en": ("Runtime Adapters & Portability",
               "One app, every runtime: Cloudflare Workers, Bun, Deno, Node and Lambda. Runtime detection, the `env()` seam, and streaming/SSE helpers — the web→native bridge."),
        "vi": ("Runtime Adapters & Portability",
               "Một app, mọi runtime: Cloudflare Workers, Bun, Deno, Node và Lambda. Runtime detection, mối nối `env()`, và các helper streaming/SSE — cầu nối web→native."),
    }),
    ("07", "07-typed-routes-rpc-and-validation", "Application", {
        "en": ("Typed Routes, the RPC Client & Validation",
               "The type-level machinery: how a path string yields typed params, how `ToSchema` accumulates a route map, and how the `hc` RPC client and `validator()` ride on top of it."),
        "vi": ("Typed Routes, the RPC Client & Validation",
               "Bộ máy ở tầng type: cách một path string sinh ra các param có kiểu, cách `ToSchema` tích lũy một route map, và cách RPC client `hc` cùng `validator()` chạy trên nền đó."),
    }),
    ("08", "08-capstone-extending-and-staying-current", "Mastery", {
        "en": ("Capstone: Extending & Staying Current",
               "Write a custom middleware and your own preset, read a real merged Hono PR unaided, and re-sync after an upstream update."),
        "vi": ("Capstone: Extending & Staying Current",
               "Viết một custom middleware và preset của riêng bạn, tự đọc một PR Hono đã merge mà không cần trợ giúp, và re-sync sau một update từ upstream."),
    }),
]

_UI_EN = {
    "chapters": "Chapters", "reference": "Reference", "glossary": "Glossary & Index",
    "glossary_short": "Glossary", "repo": "GitHub repo", "on_this_page": "On this page",
    "previous": "← Previous", "next": "Next →", "home": "Handbook", "chapter": "Chapter",
    "read_chapter": "Read chapter →", "pinned": "pinned", "single_file": "single file",
    "grounded_in": "grounded in",
    "a_publication": 'A <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> '
                     'publication · Edge AI, human-centric design',
}
_UI_VI = {
    "chapters": "Chương", "reference": "Tham khảo", "glossary": "Glossary & Index",
    "glossary_short": "Glossary", "repo": "GitHub repo", "on_this_page": "Trong trang này",
    "previous": "← Trước", "next": "Tiếp →", "home": "Handbook", "chapter": "Chương",
    "read_chapter": "Đọc chương →", "pinned": "pinned", "single_file": "một file",
    "grounded_in": "neo vào",
    "a_publication": 'Một ấn phẩm của <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> '
                     '· Edge AI, human-centric design',
}

COPY = {
    "en": {
        "brand": "Hono Internals Handbook",
        "landing_title": "Hono Internals Handbook · Hono v4.12.25 from the source",
        "meta_description": "A from-the-source handbook on Hono internals — the four-router routing "
                            "engine and its RegExpRouter one-regex trick, the Context object, the "
                            "compose middleware onion, multi-runtime adapters, and the type-safe "
                            "routing & RPC client.",
        "kicker": "● Hono v4.12.25 · TypeScript · from the source",
        "h1": "Understand the framework,<br>not just call it.",
        "sub": "A from-the-source handbook that turns <code>honojs/hono</code> into something you "
               "genuinely understand — the <b>four-router routing engine</b> and its one-regex trick, "
               "the <code>Context</code> object, the <code>compose</code> middleware onion, the "
               "multi-runtime adapters, and the type-safe routes and RPC client. Hands-on, "
               "source-grounded, run live with <code>bun</code>.",
        "chips": ["9 chapters · 1 flagship", f"pinned <b>{PINNED}</b>",
                  "labs you run with <b>Bun &amp; Vitest</b>",
                  "bridges <b>Next.js · Tauri · the edge</b>"],
        "cta_start": "Start with Chapter 0 →",
        "cta_flagship": "Jump to the flagship ★",
        "label_curriculum": "The curriculum — depth weighted toward the router",
        "label_howto": "How to use this book",
        "how_to_use": [
            {"kicker": "METHOD", "h3": "Read with the source open",
             "p": f"Every chapter cites exact <code>file:line</code> locations in a local clone pinned "
                  f"to {PINNED}. Keep <code>../hono</code> open beside each page. Each chapter ends with "
                  f"checkpoint questions and a “Connect to your past” sidebar tying Hono back to your "
                  f"temlet Next.js→Tauri and web→native work."},
            {"kicker": "SHAPE", "h3": "Why → model → source → lab",
             "p": "Concept, then a mental model + diagram, then a guided source read, then a hands-on "
                  "lab you run with <code>bun run</code> and a stated expected result."},
        ],
        "footer_note": "",
        "handbook_sub": f"The complete book in one file — the four-router routing engine, the Context "
                        f"object, the compose middleware onion, the multi-runtime adapters, and the "
                        f"type-safe routes and RPC client. Grounded in <code>{UPSTREAM_NAME}</code> @ "
                        f"<code>{PINNED}</code>. Use the rail to jump; press the printer icon to save "
                        f"as PDF.",
        "ui": _UI_EN,
    },
    "vi": {
        "brand": "Hono Internals Handbook",
        "landing_title": "Hono Internals Handbook · Đọc Hono v4.12.25 từ source",
        "meta_description": "Cuốn sách đọc thẳng từ source về internals của Hono — routing engine bốn "
                            "router và mẹo gộp-một-regex của RegExpRouter, Context object, compose "
                            "middleware onion, các runtime adapter, và routing type-safe cùng RPC "
                            "client.",
        "kicker": "● Hono v4.12.25 · TypeScript · đọc từ source",
        "h1": "Hiểu cái framework,<br>không chỉ gọi nó.",
        "sub": "Một cuốn sách đọc thẳng từ source, biến <code>honojs/hono</code> thành thứ bạn thực sự "
               "hiểu — <b>routing engine bốn router</b> và mẹo one-regex của nó, <code>Context</code> "
               "object, <code>compose</code> middleware onion, các multi-runtime adapter, và route "
               "type-safe cùng RPC client. Thực hành, neo vào source, chạy trực tiếp với "
               "<code>bun</code>.",
        "chips": ["9 chương · 1 flagship", f"pinned <b>{PINNED}</b>",
                  "lab chạy với <b>Bun &amp; Vitest</b>",
                  "bắc cầu <b>Next.js · Tauri · the edge</b>"],
        "cta_start": "Bắt đầu từ Chương 0 →",
        "cta_flagship": "Nhảy tới chương flagship ★",
        "label_curriculum": "Lộ trình — chiều sâu dồn vào router",
        "label_howto": "Dùng cuốn sách này thế nào",
        "how_to_use": [
            {"kicker": "PHƯƠNG PHÁP", "h3": "Đọc với source mở sẵn bên cạnh",
             "p": f"Mỗi chương trích dẫn chính xác vị trí <code>file:line</code> trong một bản clone "
                  f"local đã pin ở {PINNED}. Hãy mở <code>../hono</code> bên cạnh từng trang. Cuối mỗi "
                  f"chương là các câu hỏi checkpoint và một sidebar “Connect to your past” nối Hono "
                  f"ngược về công việc temlet Next.js→Tauri và web→native của bạn."},
            {"kicker": "CẤU TRÚC", "h3": "Vì sao → model → source → lab",
             "p": "Khái niệm trước, rồi tới mental model kèm diagram, rồi một lượt đọc source có dẫn "
                  "đường, rồi một lab bạn tự chạy với <code>bun run</code> và một kết quả mong đợi "
                  "được nói rõ."},
        ],
        "footer_note": "",
        "handbook_sub": f"Trọn cuốn sách trong một file — routing engine bốn router, Context object, "
                        f"compose middleware onion, các multi-runtime adapter, và route type-safe cùng "
                        f"RPC client. Neo vào <code>{UPSTREAM_NAME}</code> @ <code>{PINNED}</code>. "
                        f"Dùng thanh rail để nhảy chương; bấm icon máy in để lưu PDF.",
        "ui": _UI_VI,
    },
}
