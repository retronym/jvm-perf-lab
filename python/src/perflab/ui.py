"""The look shared by perflab's pages (index, timeline, site, profdiff's compare page): colour tokens for light and dark,
base styles, and a lightbox for flame graphs. Each page inlines what it uses, so it stays one file that works from
file:// as well as under `perflab serve`.

Lightbox: a link `<a data-lb="<event>|<kind>" href=...>` opens its graph in an overlay over the page instead of
navigating away. The overlay's bar offers the other `a[data-lb]` of the closest `[data-lb-group]` (a run, a cell, a
campaign's diffs) as chips, grouped by event; `↗` opens the current graph in a new tab, `[` and `]` step, Esc closes.
A modified click (new tab, new window) is left to the browser.
"""
import urllib.parse

HEAD = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'

TOKENS = """
:root{--bg:#f6f7f9;--panel:#fff;--fg:#1d232b;--muted:#5d6875;--line:#dde2e8;--line2:#eef1f4;--link:#2f6fb2;--link-bg:#e8f0fa;
  --ok:#22663a;--ok-bg:#e3f1e7;--warn:#7a5200;--warn-bg:#fdf0d5;--bad:#9b1c1c;--bad-bg:#fbe3e3;--shadow:0 1px 2px rgba(20,30,40,.06)}
@media (prefers-color-scheme: dark){:root{--bg:#14181d;--panel:#1b2027;--fg:#e3e8ee;--muted:#94a0ad;--line:#2c333c;--line2:#232931;
  --link:#6ea8e6;--link-bg:#1f2d3d;--ok:#7fd3a0;--ok-bg:#183326;--warn:#f0c46a;--warn-bg:#3a2d12;--bad:#ff9b9b;--bad-bg:#3d1c1f;
  --shadow:none;color-scheme:dark}}
"""

BASE = """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.5 -apple-system,system-ui,"Segoe UI",sans-serif}
a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
code{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace}
.k{color:var(--muted);font-size:12px} .when{color:var(--muted);font-weight:normal;font-size:12px;white-space:nowrap}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 14px;box-shadow:var(--shadow)}
.card-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;margin:0 0 6px}
.card-h h2{font-size:15px;margin:0;overflow-wrap:anywhere} .card-h .btns{margin-left:auto}
.kind{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px;line-height:16px}
.btns{display:inline-flex;flex-wrap:wrap;gap:4px}
.btn{display:inline-block;font-size:12px;line-height:18px;border:1px solid var(--line);border-radius:6px;padding:1px 8px;background:var(--panel);color:var(--link);white-space:nowrap}
.btn:hover{background:var(--link-bg);text-decoration:none} .btn.pending{color:var(--muted);border-style:dashed}
.badge{display:inline-block;font-size:11.5px;font-weight:500;border-radius:999px;padding:0 8px;line-height:19px;white-space:nowrap}
.badge.running,.badge.partial{background:var(--warn-bg);color:var(--warn)} .badge.finished,.badge.done{background:var(--ok-bg);color:var(--ok)}
.badge.failed,.badge.interrupted{background:var(--bad-bg);color:var(--bad)}
.facts{color:var(--muted);margin:0 0 8px;overflow-wrap:anywhere} .facts b{color:var(--fg);font-weight:600} .facts code{color:var(--fg)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%;
  /* edge shadows while there is more to scroll to */
  background:linear-gradient(to right,var(--panel) 30%,transparent),linear-gradient(to left,var(--panel) 30%,transparent) right,
    radial-gradient(farthest-side at 0 50%,rgba(0,0,0,.2),transparent),radial-gradient(farthest-side at 100% 50%,rgba(0,0,0,.2),transparent) right;
  background-repeat:no-repeat;background-size:40px 100%,40px 100%,12px 100%,12px 100%;background-attachment:local,local,scroll,scroll;background-color:var(--panel)}
table.t{border-collapse:collapse;font-variant-numeric:tabular-nums;margin:4px 0 8px}
table.t th{font-weight:600;font-size:12px;color:var(--muted);text-align:left;border-bottom:1px solid var(--line);padding:4px 10px;white-space:nowrap}
table.t td{border-bottom:1px solid var(--line2);padding:4px 10px;text-align:left;vertical-align:top}
table.t tr:last-child td{border-bottom:0} table.t .n{text-align:right;white-space:nowrap}
details.help{display:inline-block;position:relative} details.help>summary{list-style:none;cursor:pointer;display:inline-block;width:18px;height:18px;
  line-height:16px;text-align:center;border:1px solid var(--line);border-radius:50%;color:var(--muted);font-size:11px;font-weight:600}
details.help>summary::-webkit-details-marker{display:none}
details.help[open]>div{position:absolute;z-index:20;top:24px;left:0;width:min(420px,80vw);background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:8px 12px;box-shadow:0 6px 24px rgba(0,0,0,.18);font-size:12px;font-weight:normal;color:var(--fg)}
details.help.right[open]>div{left:auto;right:0}
.chip{font:inherit;font-size:12px;line-height:18px;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:999px;padding:1px 10px;cursor:pointer}
.chip.on,.chip[aria-pressed=true]{background:var(--link);border-color:var(--link);color:var(--panel)}
.graphs{display:grid;grid-template-columns:max-content 1fr;gap:2px 10px;align-items:baseline;margin:4px 0}
.graphs .ev{font-weight:600;font-size:12px} .graphs .btns{gap:3px}
"""

LIGHTBOX_CSS = """
#lb{position:fixed;inset:0;z-index:100;background:rgba(10,14,20,.55);display:flex;padding:16px}
#lb[hidden]{display:none}
#lb .box{flex:1;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.35)}
#lb .bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:6px 10px;border-bottom:1px solid var(--line)}
#lb .ttl{font-weight:600;overflow-wrap:anywhere} #lb .grp{display:inline-flex;gap:3px;align-items:center;flex-wrap:wrap}
#lb .grp b{font-size:12px;color:var(--muted);font-weight:600;margin-right:2px}
#lb .chip{font:12px/18px inherit;border:1px solid var(--line);background:none;color:var(--fg);border-radius:6px;padding:0 7px;cursor:pointer}
#lb .chip.on{background:var(--link);border-color:var(--link);color:var(--panel)}
#lb .act{margin-left:auto;display:flex;gap:4px} #lb .act a,#lb .act button{font:14px/22px inherit;width:28px;text-align:center;border:1px solid var(--line);
  border-radius:6px;background:none;color:var(--fg);cursor:pointer;text-decoration:none}
#lb iframe{flex:1;border:0;width:100%;background:#fff}
@media (max-width:600px){#lb{padding:0} #lb .box{border-radius:0}}
"""

LIGHTBOX_JS = r"""
const Lightbox = (() => {
  let box = null, items = [], cur = 0, title = '';
  function build() {
    box = document.createElement('div');
    box.id = 'lb'; box.hidden = true;
    box.innerHTML = '<div class="box"><div class="bar"><span class="ttl"></span><span class="chips"></span><span class="act">'
      + '<a class="open" target="_blank" rel="noopener" title="Open in a new tab">↗</a>'
      + '<button class="x" title="Close (Esc)">✕</button></span></div><iframe></iframe></div>';
    document.body.appendChild(box);
    box.querySelector('.x').onclick = close;
    box.addEventListener('click', e => { if (e.target === box) close(); });
    box.querySelector('.chips').addEventListener('click', e => { const c = e.target.closest('.chip'); if (c) show(+c.dataset.i); });
    const fr = box.querySelector('iframe');
    // the graph takes the keys while it has the focus
    fr.addEventListener('load', () => { try { fr.contentWindow.addEventListener('keydown', key); } catch (e) {} });
  }
  function open(list, i, name) {
    if (!box) build();
    items = list; title = name || ''; box.hidden = false;
    document.documentElement.style.overflow = 'hidden';
    const groups = [];
    list.forEach((it, j) => { let g = groups.find(g => g.name === it.group); if (!g) groups.push(g = {name: it.group, items: []}); g.items.push([j, it]); });
    box.querySelector('.chips').innerHTML = list.length < 2 ? '' : groups.map(g => '<span class="grp">' + (g.name ? `<b>${esc(g.name)}</b>` : '')
      + g.items.map(([j, it]) => `<button class="chip" data-i="${j}" title="${esc(it.tip || '')}">${esc(it.label)}</button>`).join('') + '</span>').join('');
    show(i);
  }
  function show(i) {
    cur = (i + items.length) % items.length;
    const it = items[cur];
    box.querySelector('iframe').src = it.href;
    box.querySelector('.open').href = it.href;
    box.querySelector('.ttl').textContent = title;
    box.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', +c.dataset.i === cur));
  }
  function close() {
    if (!box || box.hidden) return;
    box.hidden = true; box.querySelector('iframe').src = 'about:blank';
    document.documentElement.style.overflow = '';
  }
  function key(e) {
    if (!box || box.hidden || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.key === 'Escape') { close(); e.preventDefault(); }
    else if (e.key === ']') { show(cur + 1); e.preventDefault(); }
    else if (e.key === '[') { show(cur - 1); e.preventDefault(); }
  }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  document.addEventListener('keydown', key);
  // links marked data-lb open in the overlay, with the other graphs of their group
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[data-lb]');
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const g = a.closest('[data-lb-group]') || document.body;
    const links = [...g.querySelectorAll('a[data-lb]')];
    const list = links.map(l => { const [group, label] = l.dataset.lb.includes('|') ? l.dataset.lb.split('|') : ['', l.dataset.lb];
                                  return {href: l.getAttribute('href'), group, label, tip: l.title}; });
    open(list, links.indexOf(a), g.dataset.lbGroup || '');
  });
  // an open `?` closes on a click elsewhere
  document.addEventListener('click', e => document.querySelectorAll('details.help[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }));
  return {open, close};
})();
"""


# number formats shared by the pages and `perflab ab report`

def unit(u):
    return (u or "").replace("us/", "µs/")


def num(x, like=None):
    """A score: four significant digits, whole numbers with separators from 1,000; an error `like` its score, to the
    score's decimals."""
    if like is None:
        return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.4g}"
    shown = num(like)
    return f"{x:,.{len(shown.partition('.')[2]) if 'e' not in shown else 2}f}"


def si(x):
    """A count per op: 3 significant digits with K, M or G."""
    for scale, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "K")):
        if x >= scale:
            return f"{x / scale:.3g}{suffix}"
    return f"{x:.3g}"


def size(b):
    return "" if not b else f"{b / 1e6:.1f}MB" if b >= 1e5 else f"{b / 1e3:.1f}KB" if b >= 1e3 else f"{b:.0f}B"


def delta_ok(base, kind="score"):
    """Whether a percent change against `base` means anything: not for a count or size that is about zero."""
    floor = {"alloc": 1024, "count": 1000}.get(kind, 0)
    return base is not None and abs(base) > floor


def kind_of(label):
    """The kind of a metric by its column label: alloc (bytes), count (per op) or score."""
    return "alloc" if label.startswith("alloc") else "count" if label.endswith("/op") else "score"


# the brand: a mark (three flame-graph bars), the name, and the ink band it sits on

NAME = "jvm-perf-lab"
TAGLINE = "JMH profilers, PMU counters and paired campaigns for the JVM"
REPO = "https://github.com/retronym/jvm-perf-lab"
DOCS = "https://github.com/retronym/jvm-perf-lab/tree/main/doc"

MARK = ('<svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#1c2632"/>'
        '<rect x="5" y="21" width="22" height="5" rx="1.5" fill="#f59f00"/><rect x="5" y="14.5" width="15" height="5" rx="1.5" fill="#f76707"/>'
        '<rect x="21.5" y="14.5" width="5.5" height="5" rx="1.5" fill="#ffd43b"/><rect x="5" y="8" width="8" height="5" rx="1.5" fill="#e03131"/></svg>')
# the mark as the pages' icon: inline, so that a static site, a file:// page and the server all have it (the server also
# answers /favicon.ico with it, for what it serves that is not HTML)
ICON_SVG = MARK.replace(' class="mark"', ' xmlns="http://www.w3.org/2000/svg"').replace(' aria-hidden="true"', "")
HEAD += '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' + urllib.parse.quote(ICON_SVG) + '">'

GITHUB = ('<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 '
          '6.53 5.47 7.59.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.06-.49.06-.49.8.06 1.23.83 '
          '1.23.83.72 1.23 1.88.87 2.34.67.07-.52.28-.87.51-1.07-1.78-.2-3.65-.89-3.65-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 '
          '0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 '
          '3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')

BRAND_CSS = """
:root{--brand:#f76707;--ink:#10161d;--ink2:#1c2632;--ink-line:#2b3744;--ink-fg:#e9eef3;--ink-muted:#93a1b0}
.band{background:var(--ink);color:var(--ink-fg)} .band a{color:var(--ink-fg)}
.band .in{max-width:1400px;margin:0 auto;padding:0 20px}
.brand{display:flex;align-items:center;gap:12px;padding:14px 0 4px} .mark{width:34px;height:34px;flex:none}
.brand .name{font-weight:700;font-size:19px;line-height:1.15;letter-spacing:-.01em;color:#fff}
.brand .name a{color:#fff} .brand .proj{color:var(--ink-muted);font-weight:500}
.brand .tag{color:var(--ink-muted);font-size:12.5px;margin-top:2px}
.brand .links{margin-left:auto;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.brand .links a{border:1px solid var(--ink-line);border-radius:6px;padding:3px 10px;font-size:12.5px;display:inline-flex;gap:6px;align-items:center;white-space:nowrap}
.brand .links a:hover{background:var(--ink2);text-decoration:none}
.band.slim .brand{padding:8px 0} .band.slim .mark{width:24px;height:24px} .band.slim .name{font-size:15px}
.framed .band.slim{display:none}
@media (max-width:700px){.brand .tag{display:none} .band .in{padding:0 12px} .brand .name{font-size:16px} .brand .proj{display:block;font-size:14px}
  .brand .links{flex-wrap:nowrap} .brand .links a{padding:3px 7px}}
"""

FRAMED_JS = "<script>if (window !== window.top) document.documentElement.classList.add('framed')</script>"


FOOTER_CSS = ("footer.agents{max-width:1100px;margin:0 auto;padding:12px 20px 28px;font-size:12px;color:var(--muted)}"
              " footer.agents a{color:inherit}")


def footer():
    """The server pages' footer: where an agent reads on."""
    return (f'<style>{FOOTER_CSS}</style><footer class="agents">For agents: <a href="/llms.txt">llms.txt</a> · '
            '<a href="/skill.md">the perflab skill</a> · <a href="/api/v1/docs">API</a> · '
            '<a href="/api/v1/openapi.json">OpenAPI</a> · MCP: <code>perflab mcp</code></footer>')


def masthead(title=None, home=None, slim=False, tagline=True):
    """The brand band: mark, name (linking `home`), the project's title after it, tagline, GitHub and docs. Slim on the
    pages the index links (timeline, compare, reports), where it is hidden inside the index's lightbox."""
    import html
    name = f'<a href="{html.escape(home)}">{NAME}</a>' if home else NAME
    proj = f' <span class="proj">/ {html.escape(title)}</span>' if title else ""
    tag = f'<div class="tag">{TAGLINE}</div>' if tagline and not slim else ""
    return (f'<div class="band{" slim" if slim else ""}"><div class="in"><div class="brand">{MARK}<div><div class="name">{name}{proj}</div>{tag}</div>'
            f'<span class="links"><a href="{REPO}">{GITHUB} GitHub</a><a href="{DOCS}">Docs</a></span></div></div></div>'
            + (FRAMED_JS if slim else ""))


def home_from(page_dir):
    """The relative link from a page in `page_dir` to the project's index (<campaigns>/index.html), or None."""
    import os
    try:
        from . import config
        target = os.path.join(config.get().campaigns, "index.html")
        return os.path.relpath(target, page_dir)
    except (Exception, SystemExit):  # no perflab.toml
        return None


def style(*parts):
    return "<style>" + TOKENS + BRAND_CSS + "".join(parts) + "</style>"


def lightbox_script():
    return f"<script>{LIGHTBOX_JS}</script>"


def help_popover(html_body, right=False):
    """A `?` that opens a short explanation."""
    return f'<details class="help{" right" if right else ""}"><summary title="What is this?">?</summary><div>{html_body}</div></details>'
