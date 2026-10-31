"""The checkout's `doc/*.md` as pages of the server (`/doc/<name>`), rendered from the Markdown on each request, so the
Markdown stays the one source. Links between docs stay on the server, the perflab skill is `/skill.md`, and links to
anything else in the repository go to it on GitHub.

The renderer knows the Markdown the docs use: headings (with GitHub's anchors), paragraphs, bullet and numbered lists
(nested by indentation), tables, fenced code, and inline code, links, images and bold.
"""
import html, os, posixpath, re

from . import ui

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                   "doc")  # in the jvm-perf-lab checkout this perflab runs from
SKILL_PATH = ".claude/skills/perflab/SKILL.md"

CSS = """
main{max-width:900px;margin:0 auto;padding:16px 20px 40px} .tabsrow .in{max-width:900px}
.doc{font-size:14px;line-height:1.6;padding:8px 28px 20px} .doc h1{font-size:22px;margin:12px 0 10px}
.doc h2{font-size:17px;margin:26px 0 8px;padding-top:6px;border-top:1px solid var(--line2)} .doc h3{font-size:15px;margin:20px 0 6px}
.doc code{font-size:12.5px;background:var(--line2);border-radius:4px;padding:0 3px}
.doc pre{background:var(--line2);border-radius:6px;padding:8px 12px;overflow-x:auto} .doc pre code{background:none;padding:0}
.doc table.t td,.doc table.t th{font-size:13px;white-space:normal} .doc img{max-width:100%}
.doc .src{float:right;font-size:12px}
@media (max-width:700px){main{padding:12px} .doc{padding:4px 14px 14px}}
"""


def path(name):
    """`doc/<name>.md`, or None for a name that is not one of the docs."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name or ""):
        return None
    f = os.path.join(DOC, name + ".md")
    return f if os.path.isfile(f) else None


def href(target, base="doc"):
    """A link of a doc in `base`, as the server page shows it."""
    if re.match(r"[a-z][a-z0-9+.-]*:|#|/", target):
        return target
    rel, _, frag = target.partition("#")
    p = posixpath.normpath(posixpath.join(base, rel))
    frag = "#" + frag if frag else ""
    if p == SKILL_PATH:
        return "/skill.md"
    m = re.fullmatch(r"doc/([A-Za-z0-9][A-Za-z0-9_-]*)\.md", p)
    if m:
        return f"/doc/{m.group(1)}{frag}"
    return f"{ui.REPO}/blob/main/{p}{frag}"


def slug(text):
    """GitHub's anchor for a heading."""
    return re.sub(r"[^\w\- ]", "", re.sub(r"<[^>]+>", "", text).lower()).replace(" ", "-")


def inline(t, base="doc"):
    """Code spans, images, links and bold; code spans first, so that what is inside one stays literal."""
    def rest(s):
        s = html.escape(s, quote=False)
        s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img alt="{m[1]}" src="{html.escape(raw(m[2], base))}">', s)
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(href(html.unescape(m[2]), base))}">{m[1]}</a>', s)
        return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    parts = re.split(r"(`[^`]+`)", t)
    return "".join(f"<code>{html.escape(p[1:-1], quote=False)}</code>" if i % 2 else rest(p) for i, p in enumerate(parts))


def raw(target, base):
    if re.match(r"[a-z][a-z0-9+.-]*:", target):
        return target
    return ui.REPO.replace("github.com", "raw.githubusercontent.com") + "/main/" + posixpath.normpath(posixpath.join(base, target))


def cells(line):
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def to_html(text, base="doc"):
    """Markdown as HTML (see the module's doc for what it knows)."""
    lines, out, i = text.splitlines(), [], 0
    il = lambda t: inline(t, base)
    item = re.compile(r"( *)([-*]|\d+\.) +(.*)")
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(lines[i + 1:j]), quote=False)}</code></pre>")
            i = j + 1
        elif m := re.match(r"(#{1,6}) +(.*)", line):
            n, h = len(m[1]), il(m[2])
            out.append(f'<h{n} id="{slug(h)}">{h}</h{n}>')
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cs = cells(lines[i])
                if not all(set(c) <= set("-: ") for c in cs):
                    tag = "td" if rows else "th"
                    rows.append("<tr>" + "".join(f"<{tag}>{il(c)}</{tag}>" for c in cs) + "</tr>")
                i += 1
            out.append("<div class='scroll'><table class='t'>" + "".join(rows) + "</table></div>")
        elif item.match(line):
            items = []  # (indent, ordered, text)
            while i < len(lines) and lines[i].strip():
                m = item.match(lines[i])
                if m:
                    items.append([len(m[1]), m[2][0].isdigit(), m[3]])
                elif items:
                    items[-1][2] += " " + lines[i].strip()
                i += 1
            out.append(list_html(items, il))
        else:
            para, i = [line.strip()], i + 1
            while i < len(lines) and lines[i].strip() and not re.match(r"#|```|\||( *)([-*]|\d+\.) ", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{il(' '.join(para))}</p>")
    return "".join(out)


def list_html(items, il):
    """Nested lists from (indent, ordered, text) items: an item indented further than the one before it opens a list
    inside that one."""
    out, stack = [], []  # stack: (indent, tag) of the open lists
    for indent, ordered, text in items:
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if not stack or indent > stack[-1][0]:
            tag = "ol" if ordered else "ul"
            stack.append((indent, tag))
            out.append(f"<{tag}>")
        else:
            out.append("</li>")
        out.append(f"<li>{il(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def title_of(f, name):
    m = re.search(r"^# +(.*)$", open(f, encoding="utf-8").read(), re.M)
    return re.sub(r"[`*]", "", m[1]) if m else name


def chrome(title, projects, body):
    nav = f'<div class="nav"><div class="tabsrow"><div class="in"><nav class="tabs">{ui.nav_tabs(projects)}</nav></div></div></div>'
    return (ui.HEAD + f"<title>{html.escape(title)} · perflab</title>" + ui.style(ui.BASE, ui.NAV_CSS, CSS) + "<body>"
            + ui.masthead("docs", "/", slim=False) + nav + f'<main><article class="card doc">{body}</article></main>'
            + ui.footer() + ui.shortcuts() + "</body>")


def index(projects=()):
    """`/doc/`: every doc, the optimising guide first, and the perflab skill."""
    names = sorted((n[:-3] for n in os.listdir(DOC) if n.endswith(".md") and path(n[:-3])),
                   key=lambda n: (n != "optimising", n))
    items = "".join(f'<li><a href="/doc/{n}">{html.escape(title_of(path(n), n))}</a> <code>doc/{n}.md</code></li>' for n in names)
    return chrome("docs", projects, f'<h1>Docs</h1><ul>{items}<li><a href="/skill.md">The perflab skill</a> '
                                    f'<code>{SKILL_PATH}</code></li></ul>')


def page(name, projects=()):
    """`doc/<name>.md` as a page of the server, under its nav (`projects`: the server's), or None."""
    f = path(name)
    if f is None:
        return None
    text = open(f, encoding="utf-8").read()
    src = f'<a class="src" href="{ui.REPO}/blob/main/doc/{name}.md">Markdown source</a>'
    return chrome(title_of(f, name), projects, src + to_html(text))
