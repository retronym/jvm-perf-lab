"""Flame graph pages that perflab builds from its own frames, in jfrconv's viewer: the template of a page jfrconv rendered
(retronym/async-profiler's, with its toolbar, help, search and filters, short names, wheel and drag zoom, and the
{flameState} link of perflab's compare page) with its frames replaced. One viewer for every flame graph perflab
shows: a page that drew its own would drift from the others' controls.

A jfrconv page is the viewer's code, then `const cpool = [...]` (the frame names), `unpack(cpool);`, a call per frame
(`f(key, level, left, width)`, `u` and `n` its shorthands; key = name index << 3 | frame type), then a tail that
renders. `page` keeps the code and the tail and writes the frames given, with `script` (JavaScript run before the
frames, e.g. wrapping the viewer's functions) between.
"""
import json, re

# the viewer's frame types (async-profiler's FrameType) by jfrconv's name suffix; no suffix: native
TYPES = {"0": 0, "j": 1, "i": 2, "k": 5, "1": 6}
NATIVE = 3
SUFFIX = re.compile(r"_\[([a-z0-9]+)\]$")
FRAME_CALL = re.compile(r"\n[fun]\([0-9,]+\)")


class TemplateError(ValueError):
    pass


def split(template):
    """(the viewer's code, its tail) of a jfrconv page."""
    i = template.find("const cpool = [")
    calls = list(FRAME_CALL.finditer(template))
    if i < 0 or not calls or "function f(" not in template[:i]:
        raise TemplateError("not a jfrconv flame graph page (no cpool, no frames)")
    return template[:i], template[calls[-1].end():]


def name_and_type(frame):
    m = SUFFIX.search(frame)
    return (SUFFIX.sub("", frame), TYPES.get(m.group(1), NATIVE)) if m else (frame, NATIVE)


def page(template, title, frames, script="", h1=None, inverted=False):
    """A page of `template`'s viewer with `frames`: preorder (frame name with jfrconv's suffix, level, left, width),
    left and width integers on one scale, the root first at level 0. `h1`: the heading's HTML, if not the title;
    `inverted`: the roots at the top, as the viewer's invert (I) shows them."""
    head, tail = split(template)
    if inverted:
        head = re.sub(r"let inverted = false;", "let inverted = true;", head, count=1)
    depth = max(level for _, level, _, _ in frames) + 1
    head = re.sub(r"const levels = Array\(\d+\)", f"const levels = Array({depth})", head, count=1)
    head = re.sub(r"(canvas \{width: 100%; height: )\d+px", rf"\g<1>{depth * 16}px", head, count=1)
    head = re.sub(r"<h1>.*?</h1>", lambda _: f"<h1>{h1 or _esc(title)}</h1>", head, count=1, flags=re.S)
    head = re.sub(r"<title>.*?</title>", lambda _: f"<title>{_esc(title)}</title>", head, count=1, flags=re.S)
    names, ids, calls, prev_left = [], {}, [], 0
    for frame, level, left, width in frames:
        name, typ = name_and_type(frame)
        i = ids.get(name)
        if i is None:
            i = ids[name] = len(names)
            names.append(name)
        calls.append(f"f({i << 3 | typ},{level},{left - prev_left},{width})")
        prev_left = left
    # unpack() takes each name after the first as (a char: 32 + the prefix it shares with the previous name) + the rest
    pool = ",\n".join(json.dumps(n if k == 0 else " " + n).replace("<", "\\u003c") for k, n in enumerate(names))
    return link(f"{head}const cpool = [\n{pool}\n];\nunpack(cpool);\n{script}\n" + "\n".join(calls) + tail)


# What every graph page perflab writes has beside the viewer's own link (its {flameState}): its pages are served from an
# opaque origin, so the compare page cannot reach into them. Posts the vertical scroll ({flameScroll}) and the keys the
# compare page binds ({flameKey}: a, b, t, Space, [, ], 1-9) to the parent, and applies a {flameScroll} it relays.
LINK_MARK = "/* perflab: scroll and keys to the compare page */"
LINK_JS = LINK_MARK + r"""
(function() {
  if (window.parent === window) return;
  let applying = false, t = null;
  addEventListener('scroll', () => {
    if (applying) { applying = false; return; }
    clearTimeout(t);
    t = setTimeout(() => window.parent.postMessage({flameScroll: {x: window.scrollX, y: window.scrollY}}, '*'), 30);
  });
  addEventListener('message', e => {
    const s = e.source === window.parent && e.data && e.data.flameScroll;
    if (s && (s.x !== window.scrollX || s.y !== window.scrollY)) { applying = true; window.scrollTo(s.x, s.y); }
  });
  addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    if (/^([abt \[\]]|[1-9])$/.test(e.key)) { window.parent.postMessage({flameKey: e.key}, '*'); if (e.key === ' ') e.preventDefault(); }
  });
})();
"""


def link(html):
    """A graph page with LINK_JS (once), before its last </script>."""
    if LINK_MARK in html:
        return html
    i = html.rfind("</script>")
    if i < 0:
        raise TemplateError("no script to link")
    return html[:i] + "\n" + LINK_JS + html[i:]


def link_file(path):
    """LINK_JS into a graph page jfrconv wrote; quiet if it is not one (a stub, a failed render)."""
    try:
        html = open(path).read()
        out = link(html)
    except (OSError, TemplateError):
        return
    if out != html:
        with open(path, "w") as f:
            f.write(out)


def side_label(label, *labels):
    """`label` as HTML that takes the width of the longest of `labels`, so that a heading naming one run of a pair keeps
    its place when the page flips to the other."""
    width = max(len(x) for x in (label, *labels))
    return f'<span style="display:inline-block;min-width:{width}ch;font-family:ui-monospace,Menlo,monospace;text-align:left">{_esc(label)}</span>'


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
