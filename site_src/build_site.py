#!/usr/bin/env python3
"""Build the Hono Internals Handbook HTML site from the book's markdown.

Usage:  python3 site_src/build_site.py
Output: site/*.html + site/assets/code.css   (assets/styles.css + app.js are hand-authored)
"""
import os, re, html
import markdown
from pygments.formatters import HtmlFormatter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ASSETS = os.path.join(SITE, "assets")
REPO_URL = "https://github.com/rumitvn/hono-book"          # the book's own repo (labs/ blob links)
REPO_BLOB = REPO_URL + "/blob/main"
UPSTREAM = "https://github.com/honojs/hono"                 # the project we study
PINNED = "v4.12.25"                                         # pinned tag (commit fce483e)
UPSTREAM_PINNED = UPSTREAM + "/tree/" + PINNED

# ---- ordered pages -----------------------------------------------------------
CHAPTERS = [
    ("00", "00-environment-and-typescript-web-refresher.md", "Environment & TypeScript / Web-standards Refresher", "Foundation",
     "Get a green build with Bun + Vitest, and refresh the two pillars Hono is built on — the Fetch API (`Request`/`Response`) and the TypeScript generics & conditional types that power its type-safe routes."),
    ("01", "01-mental-model-and-repo-map.md",   "Mental Model & Repo Map",      "Foundation",
     "The five-layer model — App → Router → compose → Context → Adapter — and a real end-to-end trace of one request from `app.fetch()` to a `Response`."),
    ("02", "02-app-lifecycle-and-request.md",   "The App Object & HonoRequest", "Foundation",
     "How `new Hono()`, `.get()`/`.use()` route registration, and the `fetch` entrypoint actually work, plus the `HonoRequest` wrapper around the web `Request`."),
    ("03", "03-the-router.md",                  "The Router",                   "★ Flagship",
     "Hono's central abstraction: four routers, one interface. LinearRouter, TrieRouter, the RegExpRouter “merge every route into one regex” trick, and the SmartRouter that picks between them — in four case studies."),
    ("04", "04-context-and-responses.md",       "Context & Building Responses", "Core",
     "The `c` object: `c.json/text/html`, `c.req`, `c.env`, the `c.var` store, and how headers and status are buffered then finalized into a `Response`."),
    ("05", "05-the-middleware-onion.md",        "The Middleware Onion",         "Core",
     "The `compose()` algorithm: how `await next()` builds the onion, how ordering works, and how errors and 404s propagate through `onError` and `notFound`."),
    ("06", "06-runtime-adapters-and-portability.md", "Runtime Adapters & Portability", "Application",
     "One app, every runtime: Cloudflare Workers, Bun, Deno, Node and Lambda. Runtime detection, the `env()` seam, and streaming/SSE helpers — the web→native bridge."),
    ("07", "07-typed-routes-rpc-and-validation.md", "Typed Routes, the RPC Client & Validation", "Application",
     "The type-level machinery: how a path string yields typed params, how `ToSchema` accumulates a route map, and how the `hc` RPC client and `validator()` ride on top of it."),
    ("08", "08-capstone-extending-and-staying-current.md", "Capstone: Extending & Staying Current", "Mastery",
     "Write a custom middleware and your own preset, read a real merged Hono PR unaided, and re-sync after an upstream update."),
]
GLOSSARY = ("reference/glossary.md", "glossary.html", "Glossary & Source Index")

# map md filename -> output html for link rewriting
LINK_MAP = {"README.md": "index.html", "reference/glossary.md": "glossary.html"}
for _n, f, *_ in CHAPTERS:
    LINK_MAP[f] = f[:-3] + ".html"

# map md filename -> single-file anchor prefix (for handbook.html)
PREFIX = {"README.md": "top", "reference/glossary.md": "glossary"}
for _n, f, *_ in CHAPTERS:
    PREFIX[f] = "ch" + _n

EMOJI = {
    "🧠": ("note", "🧠"), "🔌": ("connect", "🔌"), "🧪": ("lab", "🧪"),
    "💡": ("tip", "💡"), "⚠️": ("warn", "⚠️"), "⚠": ("warn", "⚠️"),
    "📁": ("info", "📁"), "🔎": ("info", "🔎"), "📌": ("info", "📌"), "🎯": ("goal", "🎯"),
}

# ---- markdown -> html body ---------------------------------------------------
def scan_langs(md):
    langs, infence, cur = [], False, None
    for line in md.splitlines():
        m = re.match(r"^```([\w+\-.]*)", line)
        if m:
            if not infence:
                infence = True; langs.append(m.group(1) or "text")
            else:
                infence = False
    return langs

LANG_LABEL = {"c": "C", "cpp": "C++", "bash": "bash", "sh": "bash", "json": "json",
              "python": "python", "py": "python", "text": "text", "": "text",
              "html": "html", "css": "css", "js": "javascript",
              "rust": "Rust", "rs": "Rust", "toml": "TOML", "jsonc": "jsonc",
              "ts": "TypeScript", "typescript": "TypeScript", "tsx": "TSX", "diff": "diff",
              "sql": "SQL", "tcl": "Tcl", "make": "Makefile", "y": "Lemon"}

def convert(md_path, single=False, prefix=None):
    with open(md_path, encoding="utf-8") as fh:
        md = fh.read()
    langs = scan_langs(md)
    md_engine = markdown.Markdown(extensions=["extra", "codehilite", "toc", "sane_lists", "attr_list"],
                                  extension_configs={"codehilite": {"guess_lang": False, "css_class": "codehilite"}})
    body = md_engine.convert(md)

    # tables -> scroll wrapper
    body = re.sub(r"<table>", '<div class="table-wrap"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)

    # code blocks -> figure with bar + copy
    counter = {"i": 0}
    def code_repl(m):
        lang = langs[counter["i"]] if counter["i"] < len(langs) else "text"
        counter["i"] += 1
        label = LANG_LABEL.get(lang.lower(), lang)
        inner = m.group(0)
        bar = ('<div class="cb-bar"><span class="dot"></span>'
               f'<span class="cb-lang">{html.escape(label)}</span>'
               '<button class="cb-copy" type="button">copy</button></div>')
        return f'<figure class="codeblock">{bar}{inner}</figure>'
    body = re.sub(r'<div class="codehilite">.*?</pre>\s*</div>', code_repl, body, flags=re.S)

    # blockquotes -> callouts
    def quote_repl(m):
        inner = m.group(1)
        cls, icon = "", ""
        # find first visible char
        stripped = re.sub(r"^\s*<p>\s*", "", inner)
        for em, (c, ic) in EMOJI.items():
            if stripped.startswith(em):
                cls, icon = c, ic
                inner = inner.replace(em, "", 1)
                break
        if not cls:
            if re.search(r"<strong>\s*(Goal|Lesson|The big picture|Mental model)", stripped):
                cls = "goal" if "Goal" in stripped[:40] else "note"
            else:
                cls = "note"
        icon_html = f'<span class="ic">{icon}</span>' if icon else ""
        return f'<div class="callout {cls}">{icon_html}{inner}</div>'
    body = re.sub(r"<blockquote>(.*?)</blockquote>", quote_repl, body, flags=re.S)

    # task lists
    body = re.sub(r"<li>\s*\[ \]\s*", '<li class="task"><span class="box"></span> ', body)
    body = re.sub(r"<li>\s*\[[xX]\]\s*", '<li class="task done"><span class="box"></span> ', body)

    # connect headings
    body = re.sub(r'<h2 id="([^"]+)">(\s*🔌)', r'<h2 class="connect" id="\1">\2', body)

    if single:
        # namespace heading ids so concatenated chapters stay unique
        body = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}--{m.group(1)}"', body)

    # rewrite links
    def link_repl(m):
        href = m.group(1)
        anchor = ""
        if "#" in href:
            href, anchor = href.split("#", 1); anchor = "#" + anchor
        if href.startswith("labs/"):
            return f'href="{REPO_BLOB}/{href}{anchor}"'
        if single:
            if href == "" and anchor:                       # intra-page anchor
                return f'href="#{prefix}--{anchor[1:]}"'
            if href in PREFIX:
                tgt = PREFIX[href]
                dest = "#top" if tgt == "top" else (f"#{tgt}--{anchor[1:]}" if anchor else f"#{tgt}")
                return f'href="{dest}"'
            return m.group(0)
        if href in LINK_MAP:
            return f'href="{LINK_MAP[href]}{anchor}"'
        return m.group(0)
    body = re.sub(r'href="([^"]+)"', link_repl, body)

    # toc entries (h2/h3)
    toc = []
    for hm in re.finditer(r'<h([23])(?: class="[^"]*")? id="([^"]+)">(.*?)</h\1>', body, flags=re.S):
        lvl, hid, txt = hm.group(1), hm.group(2), re.sub(r"<[^>]+>", "", hm.group(3)).strip()
        toc.append((lvl, hid, txt))

    title = re.search(r"<h1[^>]*>(.*?)</h1>", body, flags=re.S)
    title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else "Handbook"
    return body, toc, title

# ---- html shell --------------------------------------------------------------
SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>'
PRINTER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v8H6z"/></svg>'

def rail_html(active):
    out = ['<aside class="rail"><nav>',
           '<a class="brand-mini" href="index.html">'
           '<img src="assets/brand/logo_x.svg" alt="" width="22" height="22">'
           '<span class="bm-name">RumitX</span>'
           '<span class="bm-pub">Hono Internals Handbook</span></a>',
           '<h4>Chapters</h4>']
    for num, f, ttl, flag, _ in CHAPTERS:
        cls = "active" if LINK_MAP[f] == active else ""
        flagspan = f'<span class="flag">{html.escape("★")}</span>' if flag.startswith("★") else ""
        out.append(f'<a class="{cls}" href="{LINK_MAP[f]}"><span class="num">{num}</span>'
                   f'<span>{html.escape(ttl)}</span>{flagspan}</a>')
    g_active = "active" if active == "glossary.html" else ""
    out.append('<h4>Reference</h4>')
    out.append(f'<a class="{g_active}" href="glossary.html"><span class="num">§</span><span>Glossary &amp; Index</span></a>')
    out.append(f'<a href="{REPO_URL}" target="_blank" rel="noopener"><span class="num">↗</span><span>GitHub repo</span></a>')
    out.append("</nav></aside>")
    return "\n".join(out)

def toc_html(toc):
    if not toc:
        return '<aside class="toc"></aside>'
    items = ['<aside class="toc"><nav><h4>On this page</h4>']
    for lvl, hid, txt in toc:
        items.append(f'<a class="lvl-{lvl}" href="#{hid}">{html.escape(txt)}</a>')
    items.append("</nav></aside>")
    return "\n".join(items)

def pager_html(idx):
    prev_a = next_a = '<span class="placeholder"></span>'
    seq = [("index.html", "Home")] + [(LINK_MAP[f], ttl) for _, f, ttl, _, _ in CHAPTERS] + [("glossary.html", "Glossary")]
    if idx > 0:
        h, t = seq[idx-1]; prev_a = f'<a class="prev" href="{h}"><span class="lbl">← Previous</span><span class="ttl">{html.escape(t)}</span></a>'
    if idx < len(seq)-1:
        h, t = seq[idx+1]; next_a = f'<a class="next" href="{h}"><span class="lbl">Next →</span><span class="ttl">{html.escape(t)}</span></a>'
    return f'<nav class="pager">{prev_a}{next_a}</nav>'

def page(title, active, body, toc, crumbs, pager, idx):
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Hono Internals Handbook · RumitX</title>
<meta name="description" content="A from-the-source handbook on Hono internals — the router (RegExpRouter & TrieRouter), the Context object, the compose middleware onion, runtime adapters, and the type-safe routing & RPC client.">
<link rel="icon" type="image/svg+xml" href="assets/brand/logo_x.svg">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
<link rel="stylesheet" href="assets/styles.css">
<link rel="stylesheet" href="assets/code.css">
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <button class="icon-btn" id="menu-btn" aria-label="Open navigation">{MENU}</button>
  <a class="brand" href="index.html"><span class="mark"><span>X</span></span> Hono Internals Handbook</a>
  <span class="spacer"></span>
  <span class="meta-pill">pinned&nbsp;{PINNED}</span>
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<div class="backdrop"></div>
<div class="shell">
  {rail_html(active)}
  <main class="content"><article class="article">
    {crumbs}
    {body}
    {pager}
  </article></main>
  {toc_html(toc)}
</div>
<footer class="site-foot">
  <a class="foot-brand" href="https://rumitx.com" target="_blank" rel="noopener"><span class="foot-x">X</span> RumitX</a>
  Hono Internals Handbook · grounded in <a href="{UPSTREAM_PINNED}" target="_blank" rel="noopener">honojs/hono</a>
  @ <code>{PINNED}</code><br>
  A <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> publication · Edge AI, human-centric design
</footer>
<script src="assets/app.js"></script>
</body>
</html>"""

# ---- landing -----------------------------------------------------------------
def landing():
    cards = []
    spans = {"03": "feature"}
    for num, f, ttl, flag, desc in CHAPTERS:
        extra = spans.get(num, "")
        flaghtml = f'<span class="cflag">{html.escape(flag)}</span>'
        cards.append(f"""<a class="card {extra}" href="{LINK_MAP[f]}">
      <span class="cnum">CH {num} {flaghtml}</span>
      <h3>{html.escape(ttl)}</h3>
      <p>{html.escape(desc)}</p>
      <span class="go">Read chapter →</span>
    </a>""")
    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hono Internals Handbook · Hono v4.12.25 from the source · RumitX</title>
<meta name="description" content="A from-the-source handbook on Hono internals — the four-router routing engine and its RegExpRouter one-regex trick, the Context object, the compose middleware onion, multi-runtime adapters, and the type-safe routing & RPC client.">
<link rel="icon" type="image/svg+xml" href="assets/brand/logo_x.svg">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
<link rel="stylesheet" href="assets/styles.css">
<link rel="stylesheet" href="assets/code.css">
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <a class="brand" href="index.html"><span class="mark"><span>X</span></span> Hono Internals Handbook</a>
  <span class="spacer"></span>
  <span class="meta-pill">pinned&nbsp;{PINNED}</span>
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<section class="hero">
  <span class="kicker">● Hono v4.12.25 · TypeScript · from the source</span>
  <h1>Understand the framework,<br>not just call it.</h1>
  <p class="sub">A from-the-source handbook that turns <code>honojs/hono</code> into something you
  genuinely understand — the <b>four-router routing engine</b> and its one-regex trick, the <code>Context</code>
  object, the <code>compose</code> middleware onion, the multi-runtime adapters, and the type-safe routes and
  RPC client. Hands-on, source-grounded, run live with <code>bun</code>.</p>
  <div class="chips">
    <span class="chip">9 chapters · 1 flagship</span>
    <span class="chip">pinned <b>{PINNED}</b></span>
    <span class="chip">labs you run with <b>Bun &amp; Vitest</b></span>
    <span class="chip">bridges <b>Next.js · Tauri · the edge</b></span>
  </div>
  <div class="cta">
    <a class="btn primary" href="00-environment-and-typescript-web-refresher.html">Start with Chapter 0 →</a>
    <a class="btn ghost" href="03-the-router.html">Jump to the flagship ★</a>
  </div>
</section>
<main class="landing">
  <div class="section-label">The curriculum — depth weighted toward the router</div>
  <div class="bento">
    {cards_html}
  </div>
  <div class="section-label">How to use this book</div>
  <div class="bento">
    <div class="card wide"><span class="cnum">METHOD</span><h3>Read with the source open</h3>
      <p>Every chapter cites exact <code>file:line</code> locations in a local clone pinned to {PINNED}.
      Keep <code>../hono</code> open beside each page. Each chapter ends with checkpoint questions and a
      “Connect to your past” sidebar tying Hono back to your temlet Next.js→Tauri and web→native work.</p></div>
    <div class="card"><span class="cnum">SHAPE</span><h3>Why → model → source → lab</h3>
      <p>Concept, then a mental model + diagram, then a guided source read, then a hands-on lab you run with
      <code>bun run</code> and a stated expected result.</p></div>
  </div>
</main>
<footer class="site-foot">
  <a class="foot-brand" href="https://rumitx.com" target="_blank" rel="noopener"><span class="foot-x">X</span> RumitX</a>
  Hono Internals Handbook · grounded in <a href="{UPSTREAM_PINNED}" target="_blank" rel="noopener">honojs/hono</a>
  @ <code>{PINNED}</code><br>
  A <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> publication · Edge AI, human-centric design
</footer>
<script src="assets/app.js"></script>
</body>
</html>"""

# ---- write code.css (light + dark) ------------------------------------------
def write_code_css():
    light = HtmlFormatter(style="xcode").get_style_defs(".codeblock")
    dark = HtmlFormatter(style="dracula").get_style_defs('[data-theme="dark"] .codeblock')
    # neutralize pygments-set backgrounds (our CSS controls them)
    light = re.sub(r"\.codeblock\s*\{[^}]*\}", "", light, count=1)
    dark = re.sub(r'\[data-theme="dark"\] \.codeblock\s*\{[^}]*\}', "", dark, count=1)
    with open(os.path.join(ASSETS, "code.css"), "w", encoding="utf-8") as fh:
        fh.write("/* generated by build_site.py — pygments tokens (light: xcode, dark: dracula) */\n")
        fh.write(light + "\n" + dark + "\n")

# ---- single-file handbook ----------------------------------------------------
def single_file():
    styles = open(os.path.join(ASSETS, "styles.css"), encoding="utf-8").read()
    # CSS is inlined here, so @font-face url()s resolve relative to site/handbook.html
    # (not site/assets/styles.css) — repoint them at the assets/fonts dir.
    styles = styles.replace("url('fonts/", "url('assets/fonts/")
    code_css = open(os.path.join(ASSETS, "code.css"), encoding="utf-8").read()
    app_js = open(os.path.join(ASSETS, "app.js"), encoding="utf-8").read()

    # rail (anchor mode)
    rail = ['<aside class="rail"><nav><h4>Chapters</h4>']
    for num, f, ttl, flag, _ in CHAPTERS:
        star = '<span class="flag">★</span>' if flag.startswith("★") else ""
        rail.append(f'<a href="#ch{num}"><span class="num">{num}</span><span>{html.escape(ttl)}</span>{star}</a>')
    rail.append('<h4>Reference</h4>')
    rail.append('<a href="#glossary"><span class="num">§</span><span>Glossary &amp; Index</span></a>')
    rail.append(f'<a href="{REPO_URL}" target="_blank" rel="noopener"><span class="num">↗</span><span>GitHub repo</span></a>')
    rail.append("</nav></aside>")
    rail = "\n".join(rail)

    # sections
    sections = []
    for num, f, ttl, flag, _ in CHAPTERS:
        body, _toc, _t = convert(os.path.join(ROOT, f), single=True, prefix="ch" + num)
        sections.append(f'<section id="ch{num}" class="chapter article">{body}</section>')
    gbody, _t2, _t3 = convert(os.path.join(ROOT, GLOSSARY[0]), single=True, prefix="glossary")
    sections.append(f'<section id="glossary" class="chapter article">{gbody}</section>')
    sections_html = "\n".join(sections)

    spy = """
(function(){var links=[].slice.call(document.querySelectorAll('.rail a[href^="#ch"],.rail a[href="#glossary"]'));
var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
function s(){var p=window.scrollY+140,idx=-1;for(var i=0;i<secs.length;i++){if(secs[i]&&secs[i].offsetTop<=p)idx=i;}
links.forEach(function(a,i){a.classList.toggle('active',i===idx);});}
window.addEventListener('scroll',s,{passive:true});s();})();
"""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hono Internals Handbook — Hono v4.12.25 from the source (single file) · RumitX</title>
<meta name="description" content="Complete from-the-source handbook on Hono internals — one file.">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
<link rel="icon" type="image/svg+xml" href="assets/brand/logo_x.svg">
<style>{styles}
{code_css}</style>
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <button class="icon-btn" id="menu-btn" aria-label="Open navigation">{MENU}</button>
  <a class="brand" href="#top"><span class="mark"><span>X</span></span> Hono Internals Handbook</a>
  <span class="spacer"></span>
  <span class="meta-pill">single file · {PINNED}</span>
  <button class="icon-btn" id="print-btn" aria-label="Print / Save as PDF" onclick="window.print()" title="Print / Save as PDF">{PRINTER}</button>
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<div class="backdrop"></div>
<div class="shell" style="grid-template-columns: var(--w-rail) minmax(0,1fr);">
  {rail}
  <main class="content">
    <section id="top" class="hero" style="text-align:left;max-width:var(--maxw-content);margin:0;padding-top:1rem;">
      <span class="kicker">● Hono v4.12.25 · TypeScript · from the source</span>
      <h1 style="font-size:var(--text-h1);">Hono Internals Handbook</h1>
      <p class="sub" style="margin-left:0;">The complete book in one file — the four-router routing engine,
      the Context object, the compose middleware onion, the multi-runtime adapters, and the type-safe routes
      and RPC client. Grounded in <code>honojs/hono</code> @ <code>{PINNED}</code>. Use the rail to jump; press the printer icon to save as PDF.</p>
    </section>
    {sections_html}
  </main>
</div>
<footer class="site-foot">
<a class="foot-brand" href="https://rumitx.com" target="_blank" rel="noopener"><span class="foot-x">X</span> RumitX</a>
Hono Internals Handbook · single-file edition · grounded in
<a href="{UPSTREAM_PINNED}" target="_blank" rel="noopener">honojs/hono</a> @ <code>{PINNED}</code><br>
A <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> publication</footer>
<script>{app_js}
{spy}</script>
</body>
</html>"""

# ---- main --------------------------------------------------------------------
def main():
    os.makedirs(ASSETS, exist_ok=True)
    write_code_css()

    # landing
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(landing())

    seq_titles = ["Home"] + [t for _, _, t, _, _ in CHAPTERS] + ["Glossary"]
    # chapters
    for i, (num, f, ttl, flag, _) in enumerate(CHAPTERS, start=1):
        body, toc, title = convert(os.path.join(ROOT, f))
        crumbs = f'<div class="crumbs"><a href="index.html">Handbook</a> / Chapter {num}</div>'
        out = page(title, LINK_MAP[f], body, toc, crumbs, pager_html(i), i)
        with open(os.path.join(SITE, LINK_MAP[f]), "w", encoding="utf-8") as fh:
            fh.write(out)

    # glossary
    body, toc, title = convert(os.path.join(ROOT, GLOSSARY[0]))
    crumbs = '<div class="crumbs"><a href="index.html">Handbook</a> / Reference</div>'
    out = page(title, "glossary.html", body, toc, crumbs, pager_html(len(CHAPTERS)+1), len(CHAPTERS)+1)
    with open(os.path.join(SITE, "glossary.html"), "w", encoding="utf-8") as fh:
        fh.write(out)

    # single-file edition
    with open(os.path.join(SITE, "handbook.html"), "w", encoding="utf-8") as fh:
        fh.write(single_file())

    print(f"built {len(CHAPTERS)+2} pages + handbook.html into {SITE}")

if __name__ == "__main__":
    main()
