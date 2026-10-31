"""Frame kinds in a profile diff: where a method ran inlined into its caller (jfrconv's `_[i]`) and where as a frame of
its own (`_[j]` C2, `_[1]` C1, `_[0]` interpreted), and how that moved between two builds. A method that C2 stopped
inlining (a caller grew past `FreqInlineSize`, or the method past `MaxInlineSize`: "too big", "hot method too big") is
spread over every call site, hundreds of slivers in a flame graph, and the curated diff merges the kinds on purpose; here
it is one row.

- `flips(A, B)`: per method, its self events per op as an inlined frame and in one of its own in each build, ranked
  by the self events that moved into its own frames (b's − a's), then, with the cells' JIT recordings (a spec's
  "jitRecording"), by the call sites C2 no longer inlined it at, with C2's reasons (`with_jit`); its inclusive events
  whose kind changed are a column, marked where they are most of the flip (a caller's compile reshaped).
- `toggle_graphs`: the two builds as a pair of flame graphs in jfrconv's viewer (perflab.flamegraph) with one layout,
  per op on one scale, which compare.html flips between in place (key t) with the zoom, scroll, search, filters and
  name mode linked: every frame keeps its place and only the widths change. Top-down, or by leaf (all of a method's
  self events in one root bar, split by kind: a callee that went from inlined to called shows as a new compiled part
  of its bar).
"""
import collections, json, re

KIND = re.compile(r"_\[([a-z0-9]+)\]$")
JAVA = {"i": "inlined", "j": "compiled", "1": "c1", "0": "interpreted"}
NAMES = {**JAVA, "k": "kernel"}  # anything else (no suffix): native


def kind_of(frame):
    m = KIND.search(frame)
    return NAMES.get(m.group(1), "native") if m else "native"


def plain(frame):
    return KIND.sub("", frame)


def weights(st):
    """{method: [inlined, real]} of its inclusive events (a stack counts once per method and kind), and of its self
    events (the leaf's kind)."""
    ids, code = {}, []
    for f in st.frames:
        m = KIND.search(f)
        k = m.group(1) if m else None
        if k in JAVA:
            i = ids.setdefault(plain(f), len(ids))
            code.append(2 * i + (k != "i"))
        else:
            code.append(-1)
    incl, own = [0] * (2 * len(ids)), [0] * (2 * len(ids))
    for s, n in st.stacks:
        for c in set(map(code.__getitem__, s)):
            if c >= 0:
                incl[c] += n
        c = code[s[-1]]
        if c >= 0:
            own[c] += n
    return ({m: [incl[2 * i], incl[2 * i + 1]] for m, i in ids.items()},
            {m: [own[2 * i], own[2 * i + 1]] for m, i in ids.items()})


def flips(A, B, top=50, min_frac=0.0002):
    """The methods whose self events moved into (or out of) frames of their own, a -> b, per op, most moved in first:
    the call overhead of a lost inlining lands in the callee's own frames, a little at each of its call sites.
    Inclusive weight would rank methods high in the tree first, whose whole subtree changes kind when one caller's
    compile is reshaped; it is a column (`inclusiveMoved`), and `reshuffle` marks rows where it is most of the flip."""
    ia, wa = weights(A)
    ib, wb = weights(B)
    ta, tb = A.total / A.ops, B.total / B.ops
    rows = []
    for m in wa.keys() | wb.keys():
        ai, ar = (x / A.ops for x in wa.get(m, (0, 0)))
        bi, br = (x / B.ops for x in wb.get(m, (0, 0)))
        if ai + ar + bi + br < min_frac * (ta + tb) or not ai + ar or not bi + br:
            continue  # small, or in one build only: not a change of kind
        to_real = br - ar
        xa, xb = ([x / ops for x in incl.get(m, (0, 0))] for incl, ops in ((ia, A.ops), (ib, B.ops)))
        share = lambda x: x[1] / (x[0] + x[1]) if x[0] + x[1] else 0.0
        incl_moved = abs(share(xb) - share(xa)) * (sum(xa) + sum(xb)) / 2
        if not to_real and not incl_moved:
            continue
        side = lambda i, r, x: {"inlined": i, "real": r, "realShare": r / (i + r), "inclusiveInlined": x[0], "inclusiveReal": x[1]}
        rows.append({"method": m, "selfToReal": to_real, "inclusiveMoved": incl_moved,
                     "reshuffle": incl_moved > 0.005 * (ta + tb) / 2 and abs(to_real) < 0.01 * incl_moved,
                     "a": side(ai, ar, xa), "b": side(bi, br, xb)})
    rows.sort(key=lambda r: -r["selfToReal"])
    # "_all": every method's selfToReal, for with_jit's callees beyond the top (not kept)
    return {"total": {"a": ta, "b": tb}, "rows": rows[:top], "_all": {r["method"].replace("/", "."): r["selfToReal"] for r in rows}}


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


def with_jit(t, jit_a, jit_b, top=25):
    """The flips table `t` with each method's C2 decisions as a callee in a and b (`jit`: None without a recording), and
    `sitesFlipped`: its call sites not inlined in b − in a, the second sort key; and `bySites`: the callees with the
    most call sites C2 stopped inlining, whatever the profile says (a callee refused at hundreds of sites may still
    have fewer self events in its own frames, if b does less of its work, or none at all, if it is too cheap to sample)."""
    ra, rb = jit_reasons(jit_a), jit_reasons(jit_b)
    side = lambda x: {"inlined": x["inlined"], "notInlined": x["notInlined"], "messages": dict(x["messages"].most_common())} if x else None
    profile = t.pop("_all", {})
    flipped = lambda k: (rb[k]["notInlined"] if k in rb else 0) - (ra[k]["notInlined"] if k in ra else 0)
    t["bySites"] = [{"method": k, "sitesFlipped": flipped(k), "jit": {"a": side(ra.get(k)), "b": side(rb.get(k))},
                     "selfToReal": profile.get(k)}
                    for k in sorted(ra.keys() | rb.keys(), key=lambda k: -flipped(k))[:top] if flipped(k) > 0]
    for r in t["rows"]:
        k = r["method"].replace("/", ".")
        a, b = ra.get(k), rb.get(k)
        r["jit"] = {"a": side(a), "b": side(b)}
        r["sitesFlipped"] = (b["notInlined"] if b else 0) - (a["notInlined"] if a else 0)
    t["rows"].sort(key=lambda r: (-r["selfToReal"], -r["sitesFlipped"]))
    t["jit"] = True
    return t


def table_md(event, t, la, lb, top=25):
    from .profdiff import si
    pct = lambda x: "" if x is None else f"{100 * x:.0f}%"
    jit = t.get("jit")
    sgn = lambda x: ("+" if x > 0 else "") + si(x)
    out = []
    if t.get("bySites"):
        c2 = lambda x: "" if not x else f"{x['inlined']}/{x['notInlined']}"
        why = lambda x: "" if not x else ", ".join(f"{m} {n}" for m, n in x["messages"].items() if not m.startswith("inline"))
        out += [f"## C2: callees no longer inlined, {la} → {lb}", "",
                "Call sites C2 did not inline the method at, b − a, over every method's last C2 compile (the cells' jitRecording); "
                "Δ real: its self events per op in its own frames, b − a (empty: not in the profile as a Java frame).", "",
                "| sites | Δ real | C2 a | C2 b | b's reasons | method |", "|---|---|---|---|---|---|"]
        out += [f"| +{r['sitesFlipped']} | {'' if r['selfToReal'] is None else sgn(r['selfToReal'])} | {c2(r['jit']['a'])} | {c2(r['jit']['b'])} "
                f"| {why(r['jit']['b'])} | `{r['method']}` |" for r in t["bySites"][:top]]
        out += [""]
    out += [f"## frame-kind flips: self {event} per op of a method inlined (`_[i]`) vs in its own frame (`_[j]`, `_[1]`, `_[0]`)", "",
           f"a = {la}, b = {lb}. Δ real: b's self events per op in its own frames − a's, the sort key"
           + ("; then sites: its call sites not inlined in b − in a (C2)" if jit else "")
           + ". incl moved: its inclusive events whose kind changed, |b's real share − a's| × their mean; ⟳: most of the flip is "
           "inclusive, a caller's compile reshaped rather than this method." + (" C2: inlined/not inlined call sites as a callee "
           "in the last C2 compiles, with b's reasons." if jit else ""), "",
           "| Δ real | a inlined | a real | b inlined | b real |" + (" sites |" if jit else "") + " incl moved |" + (" C2 a | C2 b |" if jit else "") + " method |",
           "|---|---|---|---|---|" + ("---|" if jit else "") + "---|" + ("---|---|" if jit else "") + "---|"]
    for r in t["rows"][:top]:
        a, b = r["a"], r["b"]
        cells = [sgn(r["selfToReal"]), si(a["inlined"]), si(a["real"]), si(b["inlined"]), si(b["real"])]
        if jit:
            cells.append(f"{r.get('sitesFlipped', 0):+d}")
        cells.append(si(r["inclusiveMoved"]) + (" ⟳" if r["reshuffle"] else ""))
        if jit:
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


# the overlay on the viewer: each frame is drawn over its slot (the same in both graphs, so that the viewer's zoom,
# pan, search and filters mean the same in both), then the part of the slot beyond this build's own weight (W) is
# greyed; the tooltip's details give both builds' events per op. Wraps the viewer's top-level functions, so it works
# with whatever else the viewer does.
OVERLAY = r"""
(function() {
  let i = 0;
  const f0 = f;
  f = function(key, level, left, width) {
    f0.apply(this, arguments);
    const lv = levels[level], fr = lv[lv.length - 1];
    if (fr) { fr.w = W[i]; fr.details = (fr.details || '') + DETAILS[i]; }
    i++;
  };
  const render0 = render;
  render = function(newRoot, nav) {
    const total = render0(newRoot, nav);
    const zf = typeof zoomFactor === 'undefined' ? 1 : zoomFactor;
    const X0 = typeof x0Rendered === 'undefined' ? root.left : x0Rendered, X1 = X0 + root.width / zf;
    const dark = document.documentElement.classList.contains('dark');
    c.fillStyle = dark ? '#2a2a2a' : '#e8e8e8';
    for (let h = 0; h < levels.length; h++) {
      const y = inverted ? h * 16 : canvasHeight - (h + 1) * 16;
      for (const fr of levels[h]) {
        if (fr.w === undefined || fr.w >= fr.width) continue;
        const l = Math.max(fr.left + fr.w, X0), r = Math.min(fr.left + fr.width, X1);
        if (r > l) c.fillRect((l - X0) * px, y, (r - l) * px, 15);
      }
    }
    return total;
  };
  samples = function(n) { return (n / SCALE).toPrecision(4) + ' ' + UNIT + ' (slot)'; };
  // the bottom-up view would regroup the slots, not the events: the by-leaf pair is the bottom-up view
  const bu = document.getElementById('buview');
  if (bu) bu.style.display = 'none';
})();
"""


def toggle_graphs(template, out_a, out_b, event, la, lb, t, by_leaf=False):
    """The two graphs of `tree`'s `t`, in the viewer of `template` (a page jfrconv rendered, e.g. the diff's a-<event>.html):
    the same frames at the same places, each drawn to its own build's weight."""
    from . import flamegraph
    n = len(t["depth"])
    scale = 1e7 / t["slot"][0] if t["slot"][0] else 1.0
    q = lambda v: int(round(v * scale))
    frames = [(t["table"][t["names"][i]], t["depth"][i], q(t["x"][i]), max(q(t["slot"][i]), 1)) for i in range(n)]
    frames[0] = ("all", 0, 0, frames[0][3])
    si = lambda v: f"{v:.4g}"
    details = [f", {la} {si(t['a'][i])} · {lb} {si(t['b'][i])} per op" for i in range(n)]
    unit = f"{event}/op"
    for out, side, label in ((out_a, "a", la), (out_b, "b", lb)):
        script = (f"const W = {json.dumps([q(v) for v in t[side]], separators=(',', ':'))}, "
                  f"DETAILS = {json.dumps(details, separators=(',', ':'))}, SCALE = {scale!r}, UNIT = {json.dumps(unit)};\n" + OVERLAY)
        what = f"{event}{' by leaf' if by_leaf else ''}"
        title = f"{what}: {label} ({la} ⇄ {lb}, one layout)"
        h1 = f"{flamegraph._esc(what)}: {flamegraph.side_label(label, la, lb)}"
        with open(out, "w") as f:
            f.write(flamegraph.page(template, title, frames, script, h1, inverted=by_leaf))
