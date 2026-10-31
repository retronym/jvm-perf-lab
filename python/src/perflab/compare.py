"""compare.html in a `perflab profdiff` output directory: for each event diffed there, the two runs' flame graphs and the
differential ones in both directions, as tabs over the same frame (after branch-bench's diff view), so that flipping
between them shows what changed. Keys (ui.SHORTCUTS["compare"]): a and b show that run's graph, t or space flips
between them, 1-9 pick a tab of the widget under the pointer (else the first), [ and ] step; a flip keeps the scroll,
and the link keeps the rest of the graph's state.

The graphs' controls are linked: async-profiler's flame graph (retronym/async-profiler's integration branch) posts the
state of its toolbar (view toggles, search, highlights, filters, zoom) after each change, and the page relays it to the
other graphs of the same event, or of every event, or to none (the header's "link" buttons).
"""
import glob, html, json, os, re

from . import flamegraph, ui

# what profdiff writes per event, in tab order
SLOTS = [("a", "{a}", "a-{event}.html", "side"), ("diff", "DIFF", "diff-{event}.html", "diff"),
         ("inverse", "DIFF⁻¹", "diff-{event}-inverse.html", "diff"), ("b", "{b}", "b-{event}.html", "side"),
         ("byleaf", "by leaf", "diff-{event}-byleaf.html", "diff")]
# a light diff's pairs of graphs with one layout (perflab.kinds): a widget each, flipped in place with t
PAIRS = [("⇄", "toggle-{side}-{event}.html"), ("⇄ by leaf", "toggle-{side}-{event}-byleaf.html")]

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
.note{margin:0;padding:4px 12px;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line)}
.lw{flex:1 1 100%;border:1px solid var(--line);border-radius:6px;background:var(--panel)}.lw .lb{overflow:auto;max-height:70vh}
.lt{border-collapse:collapse;font-size:12px;width:100%}.lt th,.lt td{padding:2px 8px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
.lt td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.lt .up{color:var(--bad,#c0392b)}.lt .down{color:var(--good,#1e8449)}
.lt .m{font:12px ui-monospace,monospace;white-space:nowrap}.lt td.s{width:50%;max-width:0}.lt ol{margin:0;padding:0;list-style:none}
.lt li{font:12px ui-monospace,monospace;white-space:nowrap}.lt li b{font-weight:600;display:inline-block;min-width:4.5em}.lt li .v{color:var(--muted);display:inline-block;min-width:4.5em}
.lt li{overflow:hidden;text-overflow:ellipsis}.lt li code{color:var(--fg)}.lt .sep td{color:var(--muted);text-align:center}
"""

SCRIPT = """
let hovered = null;
for (const w of document.querySelectorAll('.w')) {
  w.addEventListener('mouseenter', () => hovered = w);
  w.querySelector('.tabs').addEventListener('click', e => { const t = e.target.closest('.tab'); if (t) show(w, t.dataset.view); });
}
function show(w, v) {
  const to = w.querySelector(`iframe[data-view="${v}"]`);
  if (!to) return;
  // the zoom, search, filters and name mode follow through the link ({flameState}), the scroll as {flameScroll}
  w.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === v));
  w.querySelectorAll('iframe').forEach(f => f.classList.toggle('hidden', f !== to));
}
function onKey(e, from) {
  if (e.target && e.target.tagName === 'INPUT') return;
  const w = from || hovered || document.querySelector('.w'); if (!w) return;
  const tabs = [...w.querySelectorAll('.tab')], cur = tabs.findIndex(t => t.classList.contains('active'));
  // a and b: that run's graph; t or space: flip between them (from any other view, to a), in every widget
  if (!e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'a' || e.key === 'b' || e.key === 't' || e.key === ' ')) {
    const at = cur >= 0 ? tabs[cur].dataset.view : null;
    show(w, e.key === 'a' || e.key === 'b' ? e.key : at === 'a' ? 'b' : 'a'); if (e.preventDefault) e.preventDefault(); return;
  }
  const n = parseInt(e.key);
  const t = n >= 1 && n <= tabs.length ? tabs[n - 1] : e.key === '[' ? tabs[(cur - 1 + tabs.length) % tabs.length]
          : e.key === ']' ? tabs[(cur + 1) % tabs.length] : null;
  if (t) { show(w, t.dataset.view); if (e.preventDefault) e.preventDefault(); }
}
document.addEventListener('keydown', onKey);
// compare.html#<widget id> (a pair: perflab.compare.pair_id) opens on that widget
if (location.hash) { const w = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (w) { hovered = w; addEventListener('load', () => w.scrollIntoView()); } }
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
// a graph's scroll goes to the other graphs of its widget, its keys (flamegraph.LINK_JS: its origin is opaque, so the
// page cannot listen in it) to the widget it is in
const lastScroll = new Map();  // widget -> the last {flameScroll} posted in it
addEventListener('message', e => {
  const from = [...document.querySelectorAll('iframe')].find(f => f.contentWindow === e.source);
  if (!from || !e.data) return;
  if (e.data.flameKey) { onKey({key: e.data.flameKey}, from.closest('.w')); return; }
  if (e.data.flameScroll) {
    const w = from.closest('.w');
    lastScroll.set(w, e.data.flameScroll);
    for (const f of w.querySelectorAll('iframe')) if (f !== from) f.contentWindow.postMessage(e.data, '*');
  }
});
document.querySelectorAll('iframe').forEach(f => f.addEventListener('load', () => {
  const s = lastScroll.get(f.closest('.w'));
  if (s) f.contentWindow.postMessage({flameScroll: s}, '*');
}));
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


def pair_id(event, by_leaf=False):
    """The id of an event's pair widget on the compare page, a URL fragment (compare.html#<id>)."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{event}-pair{'-byleaf' if by_leaf else ''}")


def redirect(path, to):
    """A page at `path` that sends the browser to `to` (relative): a page perflab renamed keeps its URL working."""
    with open(path, "w") as f:
        f.write(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={html.escape(to)}">'
                f'<title>moved</title><p>Moved to <a href="{html.escape(to)}">{html.escape(to)}</a>.</p>')


def si(x):
    from .profdiff import si
    return si(x)


def lines_widget(event, t, a, b, top=25):
    """A curated diff's table by method with each build's lines (perflab.curate.by_method), side by side, with their
    source text; '' without one."""
    esc = html.escape
    ms = t.get("lines") or []
    if not ms:
        return ""

    def side(xs):
        return "<ol>" + "".join(f'<li title="{esc(x[2] or "") if len(x) > 2 else ""}"><b>{esc(str(x[0]))}</b><span class="v">{esc(si(x[1]))}</span>'
                                f'{f"<code>{esc(x[2])}</code>" if len(x) > 2 and x[2] else ""}</li>' for x in xs) + "</ol>"

    def row(m):
        d = m["delta"]
        return (f'<tr><td class="n {"up" if d > 0 else "down"}">{"+" if d > 0 else ""}{esc(si(d))}</td><td class="n">{esc(si(m["a"]))}</td>'
                f'<td class="n">{esc(si(m["b"]))}</td><td class="m" title="{esc(m["name"])}">{esc(m["name"].rpartition("/")[2])}</td><td class="s">{side(m["linesA"])}</td><td class="s">{side(m["linesB"])}</td></tr>')
    p = t.get("precise") or {}
    share = lambda s: "?" if s is None else f"{100 * s:.0f}%"
    body = "".join(row(m) for m in ms[::-1][:top]) + '<tr class="sep"><td colspan=6>…</td></tr>' + "".join(row(m) for m in ms[:top][::-1])
    return (f'<div class="lw" data-event="{esc(event)} lines"><div class="tabs"><span class="ev">{esc(event)} by {esc(t.get("leaf") or "line")}</span>'
            f'<span class="k" title="Samples whose leaf is the PC the PMU latched at the event (the rest: where the interrupt landed)">precise PC: '
            f'{esc(a)} {share(p.get("a"))}, {esc(b)} {share(p.get("b"))}</span></div>'
            f'<div class="lb"><table class="lt"><thead><tr><th>Δ/op</th><th>{esc(a)}</th><th>{esc(b)}</th><th>method (as owner)</th>'
            f'<th>{esc(a)}\'s lines</th><th>{esc(b)}\'s lines</th></tr></thead><tbody>{body}</tbody></table></div></div>')


def write(out, a, b, note=None):
    """(Re)writes <out>/compare.html for every event diffed in `out`; `a` and `b` name the two runs, `note` says how
    the stacks were curated (perflab.curate), shown under the header."""
    esc = html.escape
    events = sorted(os.path.basename(f)[len("diff-"):-len(".html")] for f in glob.glob(os.path.join(out, "diff-*.html"))
                    if not f.endswith(("-inverse.html", "-byleaf.html")))
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
        for _, _, name, _ in slots:
            flamegraph.link_file(os.path.join(out, name))
        widgets.append(f'<div class="w" data-event="{esc(event)}"><div class="tabs"><span class="ev">{esc(event)}</span>{tabs}<span class="act">{links}</span></div>'
                       f'<div class="body">{frames}</div></div>')
        try:
            widgets.append(lines_widget(event, json.load(open(os.path.join(out, f"tables-{event}.json"))), a, b))
        except (OSError, ValueError):
            pass
        for (label, pattern), by_leaf in zip(PAIRS, (False, True)):
            names = [pattern.format(side=side, event=event) for side in ("a", "b")]
            if not all(os.path.exists(os.path.join(out, n)) for n in names):
                continue
            for n in names:
                flamegraph.link_file(os.path.join(out, n))
            tabs = "".join(f'<button class="tab{" active" if side == "a" else ""}" data-view="{side}" title="{esc(n)} (t flips)">{esc(run)}</button>'
                           for side, run, n in zip("ab", (a, b), names))
            frames = "".join(f'<iframe src="{esc(n)}" data-view="{side}"{"" if side == "a" else " class=hidden"}></iframe>' for side, n in zip("ab", names))
            act = ('<a class="btn open" href="#" target="_blank" rel="noopener" title="Open this graph in a new tab">↗</a>'
                   '<button class="btn big" title="Enlarge, over this page (Esc closes)">⤢</button>')
            widgets.append(f'<div class="w pair" id="{pair_id(event, by_leaf)}" data-event="{esc(event)} {esc(label)}"><div class="tabs"><span class="ev">{esc(event)} {esc(label)}</span>'
                           f'{tabs}<span class="act">{act}</span></div><div class="body">{frames}</div></div>')
    help_html = ui.help_popover(
        f"The flame graphs of <b>{esc(a)}</b> and <b>{esc(b)}</b> per op on the benchmark threads, and the differential graphs "
        "between them in both directions (DIFF: a → b; DIFF⁻¹: b → a), as tabs over one frame, so flipping between them shows what "
        "changed; for a light diff, ⇄ pairs: both runs with one layout, per op on one scale, so that a flip changes only the "
        "widths. Keys (? lists them): a and b show that run's graph, t or space flips between them keeping the zoom, scroll, "
        "search, filters and name mode; 1–9 pick a tab of the graph under the pointer, [ and ] step. <i>link</i>: a graph's controls (search, zoom, "
        "toggles) drive the other graphs of its event, of every event, or none.")
    page = (f'{ui.HEAD}<title>{esc(a)} vs {esc(b)}</title>{ui.style(ui.BASE, ui.LIGHTBOX_CSS, CSS)}'
            f'{ui.masthead(home=ui.home_from(out), slim=True)}<header><span class="kind">profdiff</span><h1>{esc(a)} → {esc(b)}</h1>{help_html}<span class="sep"></span>'
            f'<button data-cols="2" class="on">2 columns</button><button data-cols="1">1 column</button><span class="sep"></span>'
            f'<span class="k">link</span><button data-link="event" class="on" title="Each graph\'s controls drive the other graphs of its event">event</button>'
            f'<button data-link="all" title="... and of every event">all</button><button data-link="off" title="Unlinked">off</button></header>'
            f'{f"<p class=note>{esc(note)}</p>" if note else ""}<div id="grid">{"".join(widgets)}</div>{ui.lightbox_script()}<script>{SCRIPT}</script>{ui.shortcuts('lightbox', 'compare')}')
    path = os.path.join(out, "compare.html")
    with open(path, "w") as f:
        f.write(page)
    return path
