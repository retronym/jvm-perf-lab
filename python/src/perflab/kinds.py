"""Frame kinds in a profile diff: where a method ran inlined into its caller (jfrconv's `_[i]`) and where as a frame of
its own (`_[j]` C2, `_[1]` C1, `_[0]` interpreted), and how that moved between two builds. A method that C2 stopped
inlining (a caller grew past `FreqInlineSize`, or the method past `MaxInlineSize`: "too big", "hot method too big") is
spread over every call site, hundreds of slivers in a flame graph, and the curated diff merges the kinds on purpose; here
it is one row.

- `flips(A, B)`: per method, its inclusive events per op as inlined and as a real frame in each build, ranked by the
  weight that moved between the two (|b's real share − a's| × its mean weight), with its self events per op; with the
  cells' JIT recordings (a spec's "jitRecording"), C2's decisions about it as a callee in each (`jit_reasons`).
- `toggle_page`: one flame graph that flips between the two builds in place (key t): both per op on one scale, laid
  out once over both, so the zoom, the scroll and every frame's place stay put and only the widths change; frames
  coloured by kind, as async-profiler's. Top-down, or by leaf (all of a method's self events in one root bar, split by
  kind: a callee that went from inlined to called shows as a new compiled part of its bar).
"""
import collections, html, json, re

KIND = re.compile(r"_\[([a-z0-9]+)\]$")
JAVA = {"i": "inlined", "j": "compiled", "1": "c1", "0": "interpreted"}
NAMES = {**JAVA, "k": "kernel"}  # anything else (no suffix): native


def kind_of(frame):
    m = KIND.search(frame)
    return NAMES.get(m.group(1), "native") if m else "native"


def plain(frame):
    return KIND.sub("", frame)


def weights(st):
    """{method: [inlined, real]} inclusive events (a stack counts once per method and kind), {method: self events}."""
    ids, code = {}, []
    for f in st.frames:
        m = KIND.search(f)
        k = m.group(1) if m else None
        if k in JAVA:
            i = ids.setdefault(plain(f), len(ids))
            code.append(2 * i + (k != "i"))
        else:
            code.append(-1)
    incl = [0] * (2 * len(ids))
    own = collections.Counter()
    names = list(ids)
    for s, n in st.stacks:
        for c in set(map(code.__getitem__, s)):
            if c >= 0:
                incl[c] += n
        c = code[s[-1]]
        if c >= 0:
            own[names[c >> 1]] += n
    return {m: [incl[2 * i], incl[2 * i + 1]] for m, i in ids.items()}, own


def flips(A, B, top=50, min_frac=0.0005):
    """The methods whose events moved most between inlined and real frames, a -> b, per op."""
    wa, sa = weights(A)
    wb, sb = weights(B)
    ta, tb = A.total / A.ops, B.total / B.ops
    rows = []
    for m in wa.keys() | wb.keys():
        ai, ar = (x / A.ops for x in wa.get(m, (0, 0)))
        bi, br = (x / B.ops for x in wb.get(m, (0, 0)))
        if ai + ar + bi + br < min_frac * (ta + tb):
            continue
        share_a = ar / (ai + ar) if ai + ar else None
        share_b = br / (bi + br) if bi + br else None
        if share_a is None or share_b is None:
            continue  # in one build only: not a change of kind
        moved = abs(share_b - share_a) * (ai + ar + bi + br) / 2
        if moved <= 0:
            continue
        rows.append({"method": m, "moved": moved,
                     "a": {"inlined": ai, "real": ar, "realShare": share_a, "self": sa.get(m, 0) / A.ops},
                     "b": {"inlined": bi, "real": br, "realShare": share_b, "self": sb.get(m, 0) / B.ops}})
    rows.sort(key=lambda r: -r["moved"])
    return {"total": {"a": ta, "b": tb}, "rows": rows[:top]}


def jit_reasons(jit):
    """{method (dotted, no descriptor): {inlined, notInlined, messages}}: C2's decisions with it as the callee, over
    every method's last C2 compile (perflab.jfrevents.jit)."""
    out = {}
    for m in jit["methods"]:
        for d in (m.get("c2") or {}).get("inlining") or []:
            r = out.setdefault(d["callee"].split("(")[0], {"inlined": 0, "notInlined": 0, "messages": collections.Counter()})
            r["inlined"] += d["inlined"]
            r["notInlined"] += d["notInlined"]
            r["messages"].update(d["messages"])
    return out


def with_jit(t, jit_a, jit_b):
    """The flips table `t` with each method's C2 decisions as a callee in a and b (`jit`: None without a recording)."""
    ra, rb = jit_reasons(jit_a), jit_reasons(jit_b)
    for r in t["rows"]:
        k = r["method"].replace("/", ".")
        side = lambda x: {"inlined": x["inlined"], "notInlined": x["notInlined"], "messages": dict(x["messages"].most_common())} if x else None
        r["jit"] = {"a": side(ra.get(k)), "b": side(rb.get(k))}
    t["jit"] = True
    return t


def table_md(event, t, la, lb, top=25):
    from .profdiff import si
    pct = lambda x: "" if x is None else f"{100 * x:.0f}%"
    out = [f"## frame-kind flips: {event} per op where a method ran inlined (`_[i]`) vs as its own frame (`_[j]`, `_[1]`, `_[0]`)", "",
           f"a = {la}, b = {lb}. moved: the weight whose kind changed, |b's real share − a's| × its mean inclusive events per op."
           + (" C2: its decisions as a callee in the last C2 compiles (inlined/not inlined call sites; b's reasons)." if t.get("jit") else ""), "",
           "| moved | a inlined | a real | a real % | b inlined | b real | b real % | a self | b self |" + (" C2 a | C2 b |" if t.get("jit") else "") + " method |",
           "|---|---|---|---|---|---|---|---|---|" + ("---|---|" if t.get("jit") else "") + "---|"]
    for r in t["rows"][:top]:
        a, b = r["a"], r["b"]
        cells = [si(r["moved"]), si(a["inlined"]), si(a["real"]), pct(a["realShare"]), si(b["inlined"]), si(b["real"]), pct(b["realShare"]),
                 si(a["self"]), si(b["self"])]
        if t.get("jit"):
            j = r.get("jit") or {}
            c2 = lambda x, why=False: "" if not x else f"{x['inlined']}/{x['notInlined']}" + (
                " " + ", ".join(f"{m} {n}" for m, n in x["messages"].items() if not m.startswith("inline")) if why else "")
            cells += [c2(j.get("a")), c2(j.get("b"), True)]
        out.append("| " + " | ".join(cells) + f" | `{r['method']}` |")
    return "\n".join(out) + "\n"


# ---- the toggle page

def tree(ca, cb, ops_a, ops_b, by_leaf=False, min_frac=0.0005):
    """Collapsed Counters of a and b (`;`-joined, root first) as one tree laid out over both: preorder (names, depth,
    a, b per op, x, slot), a node's slot max(a self, b self) plus its children's slots, siblings ordered by method,
    then kind. Nodes under `min_frac` of the root's slot are left out (their events stay in their parent's self)."""
    key = {}  # (parent, name) -> node
    name, parent, w = ["all"], [-1], [[0.0, 0.0]]
    for side, (c, ops) in enumerate(((ca, ops_a), (cb, ops_b))):
        for stack, n in c.items():
            fs = stack.split(";")
            if by_leaf:
                fs.reverse()
            x = n / ops
            node = 0
            w[0][side] += x
            for f in fs:
                k = (node, f)
                nxt = key.get(k)
                if nxt is None:
                    nxt = key[k] = len(name)
                    name.append(f)
                    parent.append(node)
                    w.append([0.0, 0.0])
                w[nxt][side] += x
                node = nxt
    kids = collections.defaultdict(list)
    floor = min_frac * max(w[0])
    for i in range(1, len(name)):
        if max(w[i]) >= floor:
            kids[parent[i]].append(i)
    order_key = lambda i: (plain(name[i]), name[i])
    slot = {}

    def size(i):  # iterative post-order
        stack = [(i, False)]
        while stack:
            j, done = stack.pop()
            if done:
                ks = kids.get(j, [])
                own = [w[j][s] - sum(w[k][s] for k in ks) for s in (0, 1)]
                slot[j] = max(own) + sum(slot[k] for k in ks)
            else:
                stack.append((j, True))
                stack.extend((k, False) for k in kids.get(j, []))
    size(0)
    out = {"names": [], "depth": [], "a": [], "b": [], "x": [], "slot": []}
    ids = {}
    stack = [(0, 0, 0.0)]
    while stack:
        i, d, x = stack.pop()
        nm = ids.setdefault(name[i], len(ids))
        for k, v in (("names", nm), ("depth", d), ("a", w[i][0]), ("b", w[i][1]), ("x", x), ("slot", slot[i])):
            out[k].append(v)
        ks = sorted(kids.get(i, []), key=order_key)
        xs, cx = [], x
        for k in ks:
            xs.append((k, d + 1, cx))
            cx += slot[k]
        stack.extend(reversed(xs))
    out["table"] = list(ids)
    r = lambda v: float(f"{v:.5g}")
    for k in ("a", "b", "x", "slot"):
        out[k] = [r(v) for v in out[k]]
    return out


CSS = """
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--line:#d0d7de;--panel:#f6f8fa;--slot:#eef0f2;--hl:#e040e0}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--line:#30363d;--panel:#161b22;--slot:#1c2128}}
*{box-sizing:border-box}body{margin:0;font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;z-index:2;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 12px;border-bottom:1px solid var(--line);background:var(--panel)}
header b.side{font:600 14px ui-monospace,monospace;padding:2px 8px;border-radius:4px;color:#fff}
.sa{background:#0969da}.sb{background:#bf3989}
button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:4px;padding:2px 8px;cursor:pointer}
input{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:4px;padding:2px 6px;width:16em}
.k{color:var(--muted);font-size:12px}.legend span{display:inline-block;padding:0 6px;margin-right:2px;border-radius:3px;color:#000;font-size:11px}
#wrap{padding:0 12px 12px}canvas{display:block;width:100%}
#tip{position:fixed;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:4px 8px;font:12px ui-monospace,monospace;display:none;z-index:3;max-width:60vw;overflow-wrap:anywhere}
"""

COLORS = {"compiled": "#64d464", "inlined": "#5ad2d2", "c1": "#d4d464", "interpreted": "#e88a5a", "kernel": "#e8b35a", "native": "#e86a6a"}

SCRIPT = r"""
const D = DATA, N = D.depth.length, H = 16, C = document.getElementById('c'), g = C.getContext('2d');
const KIND = /_\[([a-z0-9]+)\]$/, KN = {i:'inlined', j:'compiled', '1':'c1', '0':'interpreted', k:'kernel'};
const kind = D.table.map(n => { const m = KIND.exec(n); return m ? (KN[m[1]] || 'native') : 'native'; });
const shortName = D.table.map(n => n.replace(KIND, '').replace(/^.*\//, ''));
let side = 0, x0 = 0, x1 = D.slot[0], focus = 0, re = null;
const maxDepth = Math.max(...D.depth);
function resize() { C.style.height = ((maxDepth + 1) * H) + 'px'; C.width = C.clientWidth * devicePixelRatio; C.height = (maxDepth + 1) * H * devicePixelRatio; draw(); }
function w(i) { return side ? D.b[i] : D.a[i]; }
function draw() {
  const W = C.width / devicePixelRatio, k = W / (x1 - x0);
  g.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  g.clearRect(0, 0, W, C.height); g.font = '11px ui-monospace,monospace'; g.textBaseline = 'middle';
  const css = getComputedStyle(document.documentElement), slotC = css.getPropertyValue('--slot'), hl = css.getPropertyValue('--hl');
  for (let i = 0; i < N; i++) {
    const sx = (D.x[i] - x0) * k, sw = D.slot[i] * k;
    if (sx > W || sx + sw < 0 || sw < 0.3) continue;
    const y = D.depth[i] * H, bw = w(i) * k;
    g.fillStyle = slotC; g.fillRect(sx, y, Math.max(sw - 0.5, 0.3), H - 1);
    if (bw < 0.3) continue;
    const name = D.table[D.names[i]];
    g.fillStyle = re && re.test(name) ? hl : i === 0 ? '#bbb' : COLORS[kind[D.names[i]]] || '#ccc';
    g.fillRect(sx, y, Math.max(bw - 0.5, 0.3), H - 1);
    if (bw > 28) { g.fillStyle = '#000'; const t = shortName[D.names[i]]; const fit = Math.floor((bw - 6) / 6.6);
      g.fillText(t.length > fit ? t.slice(0, Math.max(fit - 1, 1)) + '…' : t, Math.max(sx, 0) + 3, y + H / 2); }
  }
  document.getElementById('side').textContent = side ? LB : LA;
  document.getElementById('side').className = 'side ' + (side ? 'sb' : 'sa');
  document.getElementById('tot').textContent = `${si(D.a[focus])} → ${si(D.b[focus])} per op` + (D.a[focus] ? ` (${pct(D.b[focus] / D.a[focus] - 1)})` : '');
}
function si(x) { const a = Math.abs(x); return a >= 1e9 ? (x / 1e9).toPrecision(3) + 'G' : a >= 1e6 ? (x / 1e6).toPrecision(3) + 'M' : a >= 1e3 ? (x / 1e3).toPrecision(3) + 'k' : x.toPrecision(3); }
function pct(x) { return (x >= 0 ? '+' : '') + (100 * x).toFixed(1) + '%'; }
function at(ev) {
  const r = C.getBoundingClientRect(), W = r.width, k = W / (x1 - x0), d = Math.floor((ev.clientY - r.top) / H);
  const x = x0 + (ev.clientX - r.left) / k;
  for (let i = 0; i < N; i++) if (D.depth[i] === d && D.x[i] <= x && x < D.x[i] + D.slot[i]) return i;
  return -1;
}
const tip = document.getElementById('tip');
C.addEventListener('mousemove', ev => {
  const i = at(ev); if (i < 0) { tip.style.display = 'none'; return; }
  const n = D.table[D.names[i]], a = D.a[i], b = D.b[i];
  tip.innerHTML = `${esc(n)}<br>${kind[D.names[i]]} · ${LA} ${si(a)} · ${LB} ${si(b)} per op · Δ ${b - a >= 0 ? '+' : ''}${si(b - a)}` + (a ? ` (${pct(b / a - 1)})` : '')
    + ` · ${(100 * (side ? b : a) / (side ? D.b[0] : D.a[0])).toFixed(2)}% of ${side ? LB : LA}`;
  tip.style.display = 'block'; tip.style.left = Math.min(ev.clientX + 12, innerWidth - tip.offsetWidth - 8) + 'px'; tip.style.top = (ev.clientY + 14) + 'px';
});
C.addEventListener('mouseleave', () => tip.style.display = 'none');
C.addEventListener('click', ev => { const i = at(ev); if (i >= 0) { focus = i; x0 = D.x[i]; x1 = D.x[i] + D.slot[i]; draw(); } });
function esc(s) { return s.replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'})[c]); }
function flip(to) { side = to === undefined ? 1 - side : to; draw(); }
function reset() { x0 = 0; x1 = D.slot[0]; focus = 0; draw(); }
addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') { if (e.key === 'Escape') e.target.blur(); return; }
  if (e.key === 't' || e.key === ' ') { flip(); e.preventDefault(); }
  else if (e.key === 'a') flip(0); else if (e.key === 'b') flip(1);
  else if (e.key === 'Escape' || e.key === 'r') reset();
  else if (e.key === '/') { document.getElementById('q').focus(); e.preventDefault(); }
});
document.getElementById('flip').onclick = () => flip();
document.getElementById('reset').onclick = reset;
document.getElementById('q').addEventListener('input', e => { try { re = e.target.value ? new RegExp(e.target.value) : null; } catch (x) { re = null; } draw(); });
addEventListener('resize', resize);
resize();
"""


def toggle_page(path, event, la, lb, t, by_leaf=False, note=""):
    esc = html.escape
    legend = "".join(f'<span style="background:{c}">{k}</span>' for k, c in COLORS.items())
    title = f"{event}{' by leaf' if by_leaf else ''}: {la} ⇄ {lb}"
    page = (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'<style>{CSS}</style><header><b id="side" class="side sa">{esc(la)}</b><button id="flip" title="Flip between the two builds (t or space; a, b)">'
            f'⇄ {esc(la)} / {esc(lb)}</button><span class="k" id="tot"></span><button id="reset" title="Zoom out (Esc or r)">reset zoom</button>'
            f'<input id="q" placeholder="highlight: regex (/)"><span class="legend">{legend}</span>'
            f'<span class="k">{esc(event)}{" by leaf" if by_leaf else ""} per op, one scale and one layout for both builds: each frame\'s grey slot fits '
            f'the larger of the two, its bar is this build\'s. Click zooms.{" " + esc(note) if note else ""}</span></header>'
            f'<div id="wrap"><canvas id="c"></canvas></div><div id="tip"></div>'
            f'<script>const DATA = {json.dumps(t, separators=(",", ":"))}, LA = {json.dumps(la)}, LB = {json.dumps(lb)}, '
            f'COLORS = {json.dumps(COLORS)};{SCRIPT}</script>')
    with open(path, "w") as f:
        f.write(page)
