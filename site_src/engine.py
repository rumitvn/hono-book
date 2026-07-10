#!/usr/bin/env python3
"""RumitX book engine — renders a bilingual static site from a book's markdown.

This file is IDENTICAL in every RumitX book. Everything book-specific lives in
book.py next to it. To spin up a new book, copy engine.py verbatim and write a
new book.py.

Locales:  en (default, at site/)   vi (at site/vi/)
Sources:  en -> 03-foo.md          vi -> 03-foo.vi.md  (falls back to the .md
          when a translation does not exist yet, so a half-translated book
          still builds)

Usage:  python3 site_src/build_site.py
Output: site/*.html + site/vi/*.html + site/assets/code.css
        (assets/styles.css + app.js are hand-authored, never generated)
"""
import os, re, html, sys
import markdown
from pygments.formatters import HtmlFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import book

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ASSETS = os.path.join(SITE, "assets")

REPO_BLOB = book.REPO_URL + "/blob/main"

LOCALES = ("en", "vi")
DEFAULT = "en"
VI_SUFFIX = ".vi.md"

GLOSSARY_STEM = "reference/glossary"
GLOSSARY_HTML = "glossary.html"


# ---- locale plumbing ---------------------------------------------------------
def src_path(stem, loc):
    """Absolute path to a stem's source for `loc`, falling back to English."""
    if loc != DEFAULT:
        cand = os.path.join(ROOT, stem + VI_SUFFIX)
        if os.path.exists(cand):
            return cand
    return os.path.join(ROOT, stem + ".md")


def out_dir(loc):
    return SITE if loc == DEFAULT else os.path.join(SITE, loc)


def asset_prefix(loc):
    """Relative hop from a page in `loc` back up to site/."""
    return "" if loc == DEFAULT else "../"


def other(loc):
    return "vi" if loc == DEFAULT else DEFAULT


def sibling_href(page, loc):
    """Href to the same page in the other locale."""
    return ("vi/" + page) if loc == DEFAULT else ("../" + page)


def chapter_meta(ch, loc):
    """(title, description) for a CHAPTERS entry, falling back to English."""
    _num, _stem, _flag, copy = ch
    return copy.get(loc) or copy[DEFAULT]


def flagship_stem():
    for _num, stem, flag, _c in book.CHAPTERS:
        if flag.startswith("★"):
            return stem
    return book.CHAPTERS[3][1]


# stem -> output html, for link rewriting. Both the .md and .vi.md spellings
# map to the same output file, because each locale lives in its own directory.
LINK_MAP = {"README.md": "index.html",
            GLOSSARY_STEM + ".md": GLOSSARY_HTML,
            GLOSSARY_STEM + VI_SUFFIX: GLOSSARY_HTML}
for _n, _stem, *_r in book.CHAPTERS:
    LINK_MAP[_stem + ".md"] = _stem + ".html"
    LINK_MAP[_stem + VI_SUFFIX] = _stem + ".html"

# stem -> anchor prefix, for the single-file handbook
PREFIX = {"README.md": "top",
          GLOSSARY_STEM + ".md": "glossary",
          GLOSSARY_STEM + VI_SUFFIX: "glossary"}
for _n, _stem, *_r in book.CHAPTERS:
    PREFIX[_stem + ".md"] = "ch" + _n
    PREFIX[_stem + VI_SUFFIX] = "ch" + _n

EMOJI = {
    "🧠": ("note", "🧠"), "🔌": ("connect", "🔌"), "🧪": ("lab", "🧪"),
    "💡": ("tip", "💡"), "⚠️": ("warn", "⚠️"), "⚠": ("warn", "⚠️"),
    "📁": ("info", "📁"), "🔎": ("info", "🔎"), "📌": ("info", "📌"), "🎯": ("goal", "🎯"),
}

# Callout markers stay in English in every locale — quote_repl() keys off these
# literals to pick the callout class. Translations keep `**Goal:**` verbatim.
MARKERS = r"(Goal|Lesson|The big picture|Mental model|Pinned)"


# ---- markdown -> html body ---------------------------------------------------
def scan_langs(md):
    langs, infence = [], False
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
              "html": "html", "css": "css", "js": "javascript", "diff": "diff"}
LANG_LABEL.update(getattr(book, "LANG_LABEL_EXTRA", {}))


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
        stripped = re.sub(r"^\s*<p>\s*", "", inner)
        for em, (c, ic) in EMOJI.items():
            if stripped.startswith(em):
                cls, icon = c, ic
                inner = inner.replace(em, "", 1)
                break
        if not cls:
            if re.search(r"<strong>\s*" + MARKERS, stripped):
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
        body = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}--{m.group(1)}"', body)

    def link_repl(m):
        href = m.group(1)
        anchor = ""
        if "#" in href:
            href, anchor = href.split("#", 1); anchor = "#" + anchor
        if href.startswith("labs/"):
            return f'href="{REPO_BLOB}/{href}{anchor}"'
        if single:
            if href == "" and anchor:
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

    # Stripping tags leaves HTML entities behind (`State<T>` -> "State&lt;T&gt;").
    # Unescape to plain text here; callers escape exactly once when emitting.
    def plain(fragment):
        return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()

    toc = []
    for hm in re.finditer(r'<h([23])(?: class="[^"]*")? id="([^"]+)">(.*?)</h\1>', body, flags=re.S):
        toc.append((hm.group(1), hm.group(2), plain(hm.group(3))))

    title = re.search(r"<h1[^>]*>(.*?)</h1>", body, flags=re.S)
    title = plain(title.group(1)) if title else "Handbook"
    return body, toc, title


# ---- chrome ------------------------------------------------------------------
SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>'
PRINTER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v8H6z"/></svg>'

# The language switcher is styled here rather than in assets/styles.css so that
# the hand-authored RumitX kit stays byte-for-byte what it is in every book.
# It borrows the kit's own tokens, so it themes and prints correctly for free.
LANG_CSS = """
.lang-switch{display:inline-flex;align-items:center;gap:.1rem;padding:.15rem;
  border:1px solid var(--border);border-radius:999px;background:var(--surface);
  font-family:var(--font-mono);font-size:.7rem;line-height:1;letter-spacing:.04em}
.lang-switch span,.lang-switch a{padding:.3rem .5rem;border-radius:999px;text-decoration:none}
.lang-switch span{background:var(--rx-navy,#0B1E2D);color:#fff;font-weight:700}
.lang-switch a{color:var(--text-faint)}
.lang-switch a:hover{color:var(--accent);text-decoration:none}
@media print{.lang-switch{display:none}}
"""


def lang_switch(page, loc):
    """EN | VI pill. The active locale is a span (no self-link); the other is a link."""
    out = ['<div class="lang-switch">']
    for l in LOCALES:
        label = l.upper()
        if l == loc:
            out.append(f'<span aria-current="true">{label}</span>')
        else:
            out.append(f'<a href="{sibling_href(page, loc)}" hreflang="{l}">{label}</a>')
    out.append("</div>")
    return "".join(out)


def alternates(page, loc):
    """hreflang alternates, relative to the current page."""
    here, there = page, sibling_href(page, loc)
    en_href = here if loc == DEFAULT else there
    vi_href = there if loc == DEFAULT else here
    return (f'<link rel="alternate" hreflang="en" href="{en_href}">\n'
            f'<link rel="alternate" hreflang="vi" href="{vi_href}">\n'
            f'<link rel="alternate" hreflang="x-default" href="{en_href}">')


def rail_html(active, loc):
    c = book.COPY[loc]; ui = c["ui"]; p = asset_prefix(loc)
    out = ['<aside class="rail"><nav>',
           '<a class="brand-mini" href="index.html">'
           f'<img src="{p}assets/brand/logo_x.svg" alt="" width="22" height="22">'
           '<span class="bm-name">RumitX</span>'
           f'<span class="bm-pub">{html.escape(c["brand"])}</span></a>',
           f'<h4>{html.escape(ui["chapters"])}</h4>']
    for num, stem, flag, _copy in book.CHAPTERS:
        ttl, _desc = chapter_meta((num, stem, flag, _copy), loc)
        cls = "active" if stem + ".html" == active else ""
        flagspan = '<span class="flag">★</span>' if flag.startswith("★") else ""
        out.append(f'<a class="{cls}" href="{stem}.html"><span class="num">{num}</span>'
                   f'<span>{html.escape(ttl)}</span>{flagspan}</a>')
    g_active = "active" if active == GLOSSARY_HTML else ""
    out.append(f'<h4>{html.escape(ui["reference"])}</h4>')
    out.append(f'<a class="{g_active}" href="{GLOSSARY_HTML}"><span class="num">§</span>'
               f'<span>{html.escape(ui["glossary"])}</span></a>')
    out.append(f'<a href="{book.REPO_URL}" target="_blank" rel="noopener"><span class="num">↗</span>'
               f'<span>{html.escape(ui["repo"])}</span></a>')
    out.append("</nav></aside>")
    return "\n".join(out)


def toc_html(toc, loc):
    if not toc:
        return '<aside class="toc"></aside>'
    ui = book.COPY[loc]["ui"]
    items = [f'<aside class="toc"><nav><h4>{html.escape(ui["on_this_page"])}</h4>']
    for lvl, hid, txt in toc:
        items.append(f'<a class="lvl-{lvl}" href="#{hid}">{html.escape(txt)}</a>')
    items.append("</nav></aside>")
    return "\n".join(items)


def pager_html(idx, loc):
    ui = book.COPY[loc]["ui"]
    prev_a = next_a = '<span class="placeholder"></span>'
    seq = ([("index.html", ui["home"])]
           + [(stem + ".html", chapter_meta(ch, loc)[0]) for ch in book.CHAPTERS for _num, stem, *_ in [ch]]
           + [(GLOSSARY_HTML, ui["glossary_short"])])
    if idx > 0:
        h, t = seq[idx-1]
        prev_a = (f'<a class="prev" href="{h}"><span class="lbl">{html.escape(ui["previous"])}</span>'
                  f'<span class="ttl">{html.escape(t)}</span></a>')
    if idx < len(seq)-1:
        h, t = seq[idx+1]
        next_a = (f'<a class="next" href="{h}"><span class="lbl">{html.escape(ui["next"])}</span>'
                  f'<span class="ttl">{html.escape(t)}</span></a>')
    return f'<nav class="pager">{prev_a}{next_a}</nav>'


def footer_html(loc):
    c = book.COPY[loc]; ui = c["ui"]
    # footer_note is optional — several books end the line at the pinned tag, and a
    # hard-coded " · " would leave a dangling separator (or tempt us to invent copy).
    note = c.get("footer_note", "").strip()
    note = f" · {note}" if note else ""
    return (f'<footer class="site-foot">\n'
            f'  <a class="foot-brand" href="https://rumitx.com" target="_blank" rel="noopener">'
            f'<span class="foot-x">X</span> RumitX</a>\n'
            f'  {html.escape(c["brand"])} · {ui["grounded_in"]} '
            f'<a href="{book.UPSTREAM_PINNED}" target="_blank" rel="noopener">{book.UPSTREAM_NAME}</a>\n'
            f'  @ <code>{book.PINNED}</code>{note}<br>\n'
            f'  {ui["a_publication"]}\n'
            f'</footer>')


def page(title, active, body, toc, crumbs, pager, loc):
    c = book.COPY[loc]; p = asset_prefix(loc)
    return f"""<!DOCTYPE html>
<html lang="{loc}" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · {html.escape(c["brand"])} · RumitX</title>
<meta name="description" content="{html.escape(c["meta_description"])}">
<link rel="icon" type="image/svg+xml" href="{p}assets/brand/logo_x.svg">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
{alternates(active, loc)}
<link rel="stylesheet" href="{p}assets/styles.css">
<link rel="stylesheet" href="{p}assets/code.css">
<style>{LANG_CSS}</style>
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <button class="icon-btn" id="menu-btn" aria-label="Open navigation">{MENU}</button>
  <a class="brand" href="index.html"><span class="mark"><span>X</span></span> {html.escape(c["brand"])}</a>
  <span class="spacer"></span>
  <span class="meta-pill">{html.escape(c["ui"]["pinned"])}&nbsp;{book.PINNED}</span>
  {lang_switch(active, loc)}
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<div class="backdrop"></div>
<div class="shell">
  {rail_html(active, loc)}
  <main class="content"><article class="article">
    {crumbs}
    {body}
    {pager}
  </article></main>
  {toc_html(toc, loc)}
</div>
{footer_html(loc)}
<script src="{p}assets/app.js"></script>
</body>
</html>"""


# ---- landing -----------------------------------------------------------------
def landing(loc):
    c = book.COPY[loc]; ui = c["ui"]; p = asset_prefix(loc)
    cards = []
    for num, stem, flag, _copy in book.CHAPTERS:
        ttl, desc = chapter_meta((num, stem, flag, _copy), loc)
        extra = "feature" if flag.startswith("★") else ""
        cards.append(f"""<a class="card {extra}" href="{stem}.html">
      <span class="cnum">CH {num} <span class="cflag">{html.escape(flag)}</span></span>
      <h3>{html.escape(ttl)}</h3>
      <p>{html.escape(desc)}</p>
      <span class="go">{html.escape(ui["read_chapter"])}</span>
    </a>""")
    cards_html = "\n".join(cards)

    howto = "\n".join(
        f'<div class="card{" wide" if i == 0 else ""}"><span class="cnum">{html.escape(h["kicker"])}</span>'
        f'<h3>{html.escape(h["h3"])}</h3><p>{h["p"]}</p></div>'
        for i, h in enumerate(c["how_to_use"]))

    chips = "\n    ".join(f'<span class="chip">{ch}</span>' for ch in c["chips"])

    # CTA targets are derived, never hand-typed — this is why they cannot rot.
    start_href = book.CHAPTERS[0][1] + ".html"
    flag_href = flagship_stem() + ".html"

    return f"""<!DOCTYPE html>
<html lang="{loc}" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(c["landing_title"])} · RumitX</title>
<meta name="description" content="{html.escape(c["meta_description"])}">
<link rel="icon" type="image/svg+xml" href="{p}assets/brand/logo_x.svg">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
{alternates("index.html", loc)}
<link rel="stylesheet" href="{p}assets/styles.css">
<link rel="stylesheet" href="{p}assets/code.css">
<style>{LANG_CSS}</style>
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <a class="brand" href="index.html"><span class="mark"><span>X</span></span> {html.escape(c["brand"])}</a>
  <span class="spacer"></span>
  <span class="meta-pill">{html.escape(ui["pinned"])}&nbsp;{book.PINNED}</span>
  {lang_switch("index.html", loc)}
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<section class="hero">
  <span class="kicker">{c["kicker"]}</span>
  <h1>{c["h1"]}</h1>
  <p class="sub">{c["sub"]}</p>
  <div class="chips">
    {chips}
  </div>
  <div class="cta">
    <a class="btn primary" href="{start_href}">{html.escape(c["cta_start"])}</a>
    <a class="btn ghost" href="{flag_href}">{html.escape(c["cta_flagship"])}</a>
  </div>
</section>
<main class="landing">
  <div class="section-label">{html.escape(c["label_curriculum"])}</div>
  <div class="bento">
    {cards_html}
  </div>
  <div class="section-label">{html.escape(c["label_howto"])}</div>
  <div class="bento">
    {howto}
  </div>
</main>
{footer_html(loc)}
<script src="{p}assets/app.js"></script>
</body>
</html>"""


# ---- code.css (light + dark) -------------------------------------------------
def write_code_css():
    light = HtmlFormatter(style="xcode").get_style_defs(".codeblock")
    dark = HtmlFormatter(style="dracula").get_style_defs('[data-theme="dark"] .codeblock')
    light = re.sub(r"\.codeblock\s*\{[^}]*\}", "", light, count=1)
    dark = re.sub(r'\[data-theme="dark"\] \.codeblock\s*\{[^}]*\}', "", dark, count=1)
    with open(os.path.join(ASSETS, "code.css"), "w", encoding="utf-8") as fh:
        fh.write("/* generated by build_site.py — pygments tokens (light: xcode, dark: dracula) */\n")
        fh.write(light + "\n" + dark + "\n")


# ---- single-file handbook ----------------------------------------------------
SPY = """
(function(){var links=[].slice.call(document.querySelectorAll('.rail a[href^="#ch"],.rail a[href="#glossary"]'));
var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
function s(){var p=window.scrollY+140,idx=-1;for(var i=0;i<secs.length;i++){if(secs[i]&&secs[i].offsetTop<=p)idx=i;}
links.forEach(function(a,i){a.classList.toggle('active',i===idx);});}
window.addEventListener('scroll',s,{passive:true});s();})();
"""


def single_file(loc):
    c = book.COPY[loc]; ui = c["ui"]; p = asset_prefix(loc)
    styles = open(os.path.join(ASSETS, "styles.css"), encoding="utf-8").read()
    # CSS is inlined here, so @font-face url()s resolve relative to the handbook,
    # not to site/assets/styles.css — repoint them at the assets/fonts dir.
    styles = styles.replace("url('fonts/", f"url('{p}assets/fonts/")
    code_css = open(os.path.join(ASSETS, "code.css"), encoding="utf-8").read()
    app_js = open(os.path.join(ASSETS, "app.js"), encoding="utf-8").read()

    rail = [f'<aside class="rail"><nav><h4>{html.escape(ui["chapters"])}</h4>']
    for num, stem, flag, _copy in book.CHAPTERS:
        ttl, _d = chapter_meta((num, stem, flag, _copy), loc)
        star = '<span class="flag">★</span>' if flag.startswith("★") else ""
        rail.append(f'<a href="#ch{num}"><span class="num">{num}</span><span>{html.escape(ttl)}</span>{star}</a>')
    rail.append(f'<h4>{html.escape(ui["reference"])}</h4>')
    rail.append(f'<a href="#glossary"><span class="num">§</span><span>{html.escape(ui["glossary"])}</span></a>')
    rail.append(f'<a href="{book.REPO_URL}" target="_blank" rel="noopener"><span class="num">↗</span>'
                f'<span>{html.escape(ui["repo"])}</span></a>')
    rail.append("</nav></aside>")
    rail = "\n".join(rail)

    sections = []
    for num, stem, _flag, _copy in book.CHAPTERS:
        body, _toc, _t = convert(src_path(stem, loc), single=True, prefix="ch" + num)
        sections.append(f'<section id="ch{num}" class="chapter article">{body}</section>')
    gbody, _t2, _t3 = convert(src_path(GLOSSARY_STEM, loc), single=True, prefix="glossary")
    sections.append(f'<section id="glossary" class="chapter article">{gbody}</section>')
    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="{loc}" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(c["brand"])} — {html.escape(ui["single_file"])} · RumitX</title>
<meta name="description" content="{html.escape(c["meta_description"])}">
<meta name="author" content="RumitX">
<meta name="theme-color" content="#0B1E2D">
<link rel="icon" type="image/svg+xml" href="{p}assets/brand/logo_x.svg">
{alternates("handbook.html", loc)}
<style>{styles}
{code_css}
{LANG_CSS}</style>
</head>
<body>
<div class="progress" id="progress"></div>
<header class="header">
  <button class="icon-btn" id="menu-btn" aria-label="Open navigation">{MENU}</button>
  <a class="brand" href="#top"><span class="mark"><span>X</span></span> {html.escape(c["brand"])}</a>
  <span class="spacer"></span>
  <span class="meta-pill">{html.escape(ui["single_file"])} · {book.PINNED}</span>
  {lang_switch("handbook.html", loc)}
  <button class="icon-btn" id="print-btn" aria-label="Print / Save as PDF" onclick="window.print()" title="Print / Save as PDF">{PRINTER}</button>
  <button class="icon-btn" id="theme-btn" aria-label="Toggle theme">{SUN}</button>
</header>
<div class="backdrop"></div>
<div class="shell" style="grid-template-columns: var(--w-rail) minmax(0,1fr);">
  {rail}
  <main class="content">
    <section id="top" class="hero" style="text-align:left;max-width:var(--maxw-content);margin:0;padding-top:1rem;">
      <span class="kicker">{c["kicker"]}</span>
      <h1 style="font-size:var(--text-h1);">{html.escape(c["brand"])}</h1>
      <p class="sub" style="margin-left:0;">{c["handbook_sub"]}</p>
    </section>
    {sections_html}
  </main>
</div>
{footer_html(loc)}
<script>{app_js}
{SPY}</script>
</body>
</html>"""


# ---- main --------------------------------------------------------------------
def main():
    os.makedirs(ASSETS, exist_ok=True)
    write_code_css()

    pages = 0
    for loc in LOCALES:
        d = out_dir(loc)
        os.makedirs(d, exist_ok=True)
        ui = book.COPY[loc]["ui"]

        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(landing(loc))
        pages += 1

        for i, (num, stem, flag, _copy) in enumerate(book.CHAPTERS, start=1):
            body, toc, title = convert(src_path(stem, loc))
            crumbs = (f'<div class="crumbs"><a href="index.html">{html.escape(ui["home"])}</a>'
                      f' / {html.escape(ui["chapter"])} {num}</div>')
            out = page(title, stem + ".html", body, toc, crumbs, pager_html(i, loc), loc)
            with open(os.path.join(d, stem + ".html"), "w", encoding="utf-8") as fh:
                fh.write(out)
            pages += 1

        body, toc, title = convert(src_path(GLOSSARY_STEM, loc))
        crumbs = (f'<div class="crumbs"><a href="index.html">{html.escape(ui["home"])}</a>'
                  f' / {html.escape(ui["reference"])}</div>')
        out = page(title, GLOSSARY_HTML, body, toc, crumbs, pager_html(len(book.CHAPTERS)+1, loc), loc)
        with open(os.path.join(d, GLOSSARY_HTML), "w", encoding="utf-8") as fh:
            fh.write(out)
        pages += 1

        with open(os.path.join(d, "handbook.html"), "w", encoding="utf-8") as fh:
            fh.write(single_file(loc))

    print(f"built {pages} pages + {len(LOCALES)} handbook.html "
          f"({', '.join(LOCALES)}) into {SITE}")


if __name__ == "__main__":
    main()
