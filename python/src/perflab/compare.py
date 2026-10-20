"""compare.html in a `perflab profdiff` output directory: for each event diffed there, the two runs' flame graphs and the
differential ones in both directions, as tabs over the same frame (after branch-bench's diff view), so that flipping
between them shows what changed. Keys: 1-4 pick a tab of the widget under the pointer (else the first), [ and ] step.

The graphs' controls are linked: async-profiler's flame graph (retronym/async-profiler's integration branch) posts the
state of its toolbar (view toggles, search, highlights, filters, zoom) after each change, and the page relays it to the
other graphs of the same event, or of every event, or to none (the header's "link" buttons).
"""
import glob, html, os

from . import ui

# what profdiff writes per event, in tab order
SLOTS = [("a", "{a}", "a-{event}.html", "side"), ("diff", "DIFF", "diff-{event}.html", "diff"),
         ("inverse", "DIFF⁻¹", "diff-{event}-inverse.html", "diff"), ("b", "{b}", "b-{event}.html", "side")]

CSS = """
:root{--accent:var(--link);--diff:#b4560b;--diffbg:#fdf0e3}
@media (prefers-color-scheme: dark){:root{--diff:#f0883e;--diffbg:#2a1500}}
body{height:100vh;display:flex;flex-direction:column}
header{display:flex;gap:8px;align-items:center;padding:6px 12px;border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}
header h1{font-size:14px;margin:0;overflow-wrap:anywhere}header .sep{width:1px;height:16px;background:var(--line);margin:0 4px}
header button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:4px;padding:2px 8px;cursor:pointer}
header button.on{color:var(--fg);border-color:var(--accent)}
#grid{flex:1;display:flex;flex-wrap:wrap;gap:8px;padding:8px;min-height:0}
.w{flex:1 1 calc(50% - 8px);min-width:320px;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:6px;background:var(--panel);min-height:0}
#grid.cols-1 .w{flex-basis:100%}
.tabs{display:flex;gap:4px;align-items:center;padding:4px 6px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tabs .ev{font-weight:600;margin-right:6px}
.tab{font:12px ui-monospace,monospace;border:1px solid var(--line);background:none;color:var(--muted);border-radius:4px;padding:1px 7px;cursor:pointer}
.tab.active{color:var(--fg);border-color:var(--accent)}
.tab.diff{color:var(--diff)}.tab.diff.active{background:var(--diffbg);border-color:var(--diff)}
.tabs .act{margin-left:auto;display:inline-flex;gap:4px}.tabs .act .btn{padding:0 7px}.tabs .act button.btn{font:inherit;font-size:12px;cursor:pointer;color:var(--fg)}
@media (max-width:700px){#grid{padding:4px}.w{min-width:0;flex-basis:100%}}
.body{position:relative;flex:1;min-height:420px}
.body iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#fff}
.body iframe.hidden{visibility:hidden}
"""

SCRIPT = """
let hovered = null;
for (const w of document.querySelectorAll('.w')) {
  w.addEventListener('mouseenter', () => hovered = w);
  w.querySelector('.tabs').addEventListener('click', e => { const t = e.target.closest('.tab'); if (t) show(w, t.dataset.view); });
}
function show(w, v) {
  w.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === v));
  w.querySelectorAll('iframe').forEach(f => f.classList.toggle('hidden', f.dataset.view !== v));
}
function onKey(e) {
  if (e.target.tagName === 'INPUT') return;
  const w = hovered || document.querySelector('.w'); if (!w) return;
  const tabs = [...w.querySelectorAll('.tab')], cur = tabs.findIndex(t => t.classList.contains('active'));
  const n = parseInt(e.key);
  const t = n >= 1 && n <= tabs.length ? tabs[n - 1] : e.key === '[' ? tabs[(cur - 1 + tabs.length) % tabs.length]
          : e.key === ']' ? tabs[(cur + 1) % tabs.length] : null;
  if (t) { show(w, t.dataset.view); e.preventDefault(); }
}
document.addEventListener('keydown', onKey);
// ↗ opens the widget's current graph in a new tab; ⤢ opens the widget's graphs in the lightbox (not when this page is
// itself shown in one)
for (const w of document.querySelectorAll('.w')) {
  const cur = () => w.querySelector('iframe:not(.hidden)');
  w.querySelector('.open').addEventListener('click', e => { e.currentTarget.href = cur().getAttribute('src'); });
  const big = w.querySelector('.big');
  if (window !== window.top) big.hidden = true;
  big.addEventListener('click', () => {
    const tabs = [...w.querySelectorAll('.tab')];
    Lightbox.open(tabs.map(t => ({href: w.querySelector(`iframe[data-view="${t.dataset.view}"]`).getAttribute('src'),
                                  group: w.dataset.event, label: t.textContent, tip: t.title})),
                  tabs.findIndex(t => t.classList.contains('active')), document.querySelector('header h1').textContent);
  });
}
// the flame graphs take the keys while the pointer is over them
document.querySelectorAll('iframe').forEach(f => f.addEventListener('load', () => {
  try { f.contentWindow.addEventListener('keydown', onKey); } catch (e) {}
}));
// linked controls: a graph's {flameState} goes to the other graphs of its event (or of every event); the last one is
// replayed to a graph that loads later
let linkMode = 'event';
const lastState = new Map();  // widget (or 'all') -> the last state posted in it
function scopeOf(f) { return linkMode === 'all' ? 'all' : f.closest('.w'); }
addEventListener('message', e => {
  if (!e.data || !e.data.flameState || linkMode === 'off') return;
  const from = [...document.querySelectorAll('iframe')].find(f => f.contentWindow === e.source);
  if (!from) return;
  const scope = scopeOf(from);
  lastState.set(scope, e.data.flameState);
  for (const f of document.querySelectorAll('iframe'))
    if (f !== from && scopeOf(f) === scope) f.contentWindow.postMessage(e.data, '*');
});
document.querySelectorAll('iframe').forEach(f => f.addEventListener('load', () => {
  const s = linkMode === 'off' ? null : lastState.get(scopeOf(f));
  if (s) f.contentWindow.postMessage({flameState: s}, '*');
}));
for (const b of document.querySelectorAll('header button[data-link]'))
  b.onclick = () => { linkMode = b.dataset.link; lastState.clear();
                      document.querySelectorAll('header button[data-link]').forEach(x => x.classList.toggle('on', x === b)); };
for (const b of document.querySelectorAll('header button[data-cols]'))
  b.onclick = () => { document.getElementById('grid').className = 'cols-' + b.dataset.cols;
                      document.querySelectorAll('header button[data-cols]').forEach(x => x.classList.toggle('on', x === b)); };
"""


def write(out, a, b):
    """(Re)writes <out>/compare.html for every event diffed in `out`; `a` and `b` name the two runs."""
    esc = html.escape
    events = sorted(os.path.basename(f)[len("diff-"):-len(".html")] for f in glob.glob(os.path.join(out, "diff-*.html"))
                    if not f.endswith("-inverse.html"))
    widgets = []
    for event in events:
        slots = [(view, label.format(a=a, b=b), name.format(event=event), kind) for view, label, name, kind in SLOTS
                 if os.path.exists(os.path.join(out, name.format(event=event)))]
        tabs = "".join(f'<button class="tab{" diff" if kind == "diff" else ""}{" active" if view == "diff" else ""}" '
                       f'data-view="{view}" title="{esc(name)}">{esc(label)}</button>' for view, label, name, kind in slots)
        frames = "".join(f'<iframe src="{esc(name)}" data-view="{view}"{"" if view == "diff" else " class=hidden"}></iframe>'
                         for view, _, name, _ in slots)
        table = f"table-{event}.md"
        links = f'<a class="btn" href="{esc(table)}" title="The differences as a table">table</a>' if os.path.exists(os.path.join(out, table)) else ""
        links += ('<a class="btn open" href="#" target="_blank" rel="noopener" title="Open this graph in a new tab">↗</a>'
                  '<button class="btn big" title="Enlarge, over this page (Esc closes)">⤢</button>')
        widgets.append(f'<div class="w" data-event="{esc(event)}"><div class="tabs"><span class="ev">{esc(event)}</span>{tabs}<span class="act">{links}</span></div>'
                       f'<div class="body">{frames}</div></div>')
    help_html = ui.help_popover(
        f"The flame graphs of <b>{esc(a)}</b> and <b>{esc(b)}</b> per op on the benchmark threads, and the differential graphs "
        "between them in both directions (DIFF: a → b; DIFF⁻¹: b → a), as tabs over one frame, so flipping between them shows what "
        "changed. Keys: 1–4 pick a tab of the graph under the pointer, [ and ] step. <i>link</i>: a graph's controls (search, zoom, "
        "toggles) drive the other graphs of its event, of every event, or none.")
    page = (f'{ui.HEAD}<title>{esc(a)} vs {esc(b)}</title>{ui.style(ui.BASE, ui.LIGHTBOX_CSS, CSS)}'
            f'<header><span class="kind">profdiff</span><h1>{esc(a)} → {esc(b)}</h1>{help_html}<span class="sep"></span>'
            f'<button data-cols="2" class="on">2 columns</button><button data-cols="1">1 column</button><span class="sep"></span>'
            f'<span class="k">link</span><button data-link="event" class="on" title="Each graph\'s controls drive the other graphs of its event">event</button>'
            f'<button data-link="all" title="... and of every event">all</button><button data-link="off" title="Unlinked">off</button></header>'
            f'<div id="grid">{"".join(widgets)}</div>{ui.lightbox_script()}<script>{SCRIPT}</script>')
    path = os.path.join(out, "compare.html")
    with open(path, "w") as f:
        f.write(page)
    return path
