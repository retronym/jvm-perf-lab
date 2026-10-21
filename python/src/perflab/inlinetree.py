"""The JIT compilation units of several async-profiler runs, compared against a baseline: what C2 inlined where, and
where a build makes a real call instead. One page, `inlinetree-<event>.html` beside the campaign by default.

  perflab inlinetree [--baseline <label>] [--event cycles] [--top 25] [--min 0.5] [--notes notes.json]
                     [--strip <package>]... [--jfrconv <jfrconv>] [--out <page.html>] <label>=<cell>...

A cell is a campaign cell or a `perflab run` directory with an async profile. Each collapsed stack of the benchmark
threads is split into compilation units: a unit starts at a C2 (`_[j]`) or C1 (`_[1]`) frame and takes the inlined
(`_[i]`) frames above it. For the top units (by own weight, then by the largest change against the baseline), the table
shows the methods each one reaches, marked by how every build reached them: inlined into the unit, a real call into
another compiled unit, or both at different call sites; below an inlined callee, what was inlined into it.

Weights are events per op (samples x interval / ops, as profdiff). A unit's own weight: samples whose innermost unit it
is (its nmethod's code, inlined code included); a row's incl: samples through it within the unit (for a callee,
inlined and called together). A recursive unit or path counts once per sample.

The page shows each run's provenance (checkout, JDK, JVM arguments, score), cards for the totals and the largest
differences (hover previews their rows, a click pins them), and chips to hide builds. --notes is a JSON object
{method: Markdown note}, matched by the method's name or a dotted suffix of it, shown on its rows and in the cards.
"""
import argparse, collections, html, json, os, re, subprocess, sys, tempfile, time

from . import profdiff, ui

FRAME = re.compile(r"^(.*)_\[(\w)\]$")
esc = html.escape


class Node:
    __slots__ = ("own", "incl", "kids", "calls")

    def __init__(self):
        self.own, self.incl, self.kids, self.calls = 0, 0, {}, collections.Counter()


def shortener(strip=()):
    """Frame name -> display name: dots for slashes, without the packages in `strip` (dotted, e.g. `dotty.tools.dotc`)."""
    prefixes = sorted((p.rstrip(".") + "." for p in strip), key=len, reverse=True)

    def short(frame):
        name = frame.replace("/", ".")
        return next((name[len(p):] for p in prefixes if name.startswith(p)), name)
    return short


def tier_key(name, kind, short):
    return f"{short(name)} [{'C2' if kind == 'j' else 'C1'}]"


def base(key):
    return key.rsplit(" [", 1)[0]


def units(lines, short=shortener()):
    """{unit key: Node} from collapsed stacks (`frame;frame;... count`). A unit's kids are what was inlined into it, as
    a tree; its calls, the units it called directly, by key."""
    roots = collections.defaultdict(Node)
    for line in lines:
        stack, _, n = line.rstrip().rpartition(" ")
        if not stack:
            continue
        n = int(n)
        # the stack's compilation units, outermost first: a C2/C1 frame and the inlined frames above it; an
        # interpreted or native frame ends the current unit
        segs, cur = [], None
        for f in stack.split(";"):
            m = FRAME.match(f)
            name, k = (m.group(1), m.group(2)) if m else (f, "n")
            if k in "j1":
                cur = [(name, k)]
                segs.append(cur)
            elif k == "i" and cur is not None:
                cur.append((name, k))
            elif k != "i":
                cur = None
        seen_units, seen_calls, seen_paths = set(), set(), set()
        for si, seg in enumerate(segs):
            key = tier_key(*seg[0], short)
            node = roots[key]
            if key not in seen_units:
                seen_units.add(key)
                node.incl += n
            innermost = si == len(segs) - 1
            if innermost:
                node.own += n
            else:
                callee = tier_key(*segs[si + 1][0], short)
                if (key, callee) not in seen_calls:
                    seen_calls.add((key, callee))
                    node.calls[callee] += n
            path = (key,)
            for depth, (name, _) in enumerate(seg[1:]):
                node = node.kids.setdefault(short(name), Node())
                path += (short(name),)
                if path not in seen_paths:
                    seen_paths.add(path)
                    node.incl += n
                if innermost and depth == len(seg) - 2:
                    node.own += n
    return dict(roots)


class Row:
    __slots__ = ("id", "parent", "depth", "kind", "name", "incl", "own", "how", "kids", "path")

    def __init__(self, id, parent, depth, kind, name, path):
        self.id, self.parent, self.depth, self.kind, self.name, self.path = id, parent, depth, kind, name, path
        self.incl, self.own, self.how, self.kids = {}, {}, {}, False


def build_rows(V, units_by, ops, keys, minw):
    """The table's rows, in order: a unit, the methods it reaches (depth 1), what was inlined into those (deeper).
    incl and own are dicts by build, None where a build does not reach the row within the unit; how is the chip:
    C2/C1 for a unit, inl / call / inl+call for a callee, "" where a build does not reach it."""
    rows = []

    def new(depth, kind, name, parent, path):
        r = Row(len(rows), parent, depth, kind, name, path + (name,))
        rows.append(r)
        return r

    def add(name, nodes, depth, parent, path, how):
        incl = {v: (nodes[v].incl / ops[v] if nodes.get(v) else None) for v in V}
        if depth and max((x or 0) for x in incl.values()) < minw:
            return None
        r = new(depth, "node", name, parent, path)
        r.incl, r.how = incl, how
        r.own = {v: (nodes[v].own / ops[v] if nodes.get(v) else None) for v in V}
        n0 = len(rows)
        kids = {v: (nodes[v].kids if nodes.get(v) else {}) for v in V}
        if depth == 0:
            calls = {v: collections.Counter() for v in V}
            for v in V:
                if nodes.get(v):
                    for c, w in nodes[v].calls.items():
                        calls[v][base(c)] += w / ops[v]
            weight = lambda k: max((kids[v][k].incl / ops[v] if k in kids[v] else 0) + calls[v][k] for v in V)
            for k in sorted(set().union(*kids.values(), *calls.values()), key=lambda k: -weight(k)):
                if weight(k) < minw:
                    continue
                h = {v: "+".join(x for x, y in (("inl", k in kids[v]), ("call", calls[v][k] > 0)) if y) for v in V}
                if any(k in kids[v] for v in V):
                    c = add(k, {v: kids[v].get(k) for v in V}, 1, r.id, r.path, h)
                    if c:
                        for v in V:
                            if calls[v][k]:
                                c.incl[v] = (c.incl[v] or 0) + calls[v][k]
                else:
                    c = new(1, "call", k, r.id, r.path)
                    c.incl = {v: (calls[v][k] if h[v] else None) for v in V}
                    c.own = {v: None for v in V}
                    c.how = h
        else:
            weight = lambda k: max((kids[v][k].incl / ops[v]) if k in kids[v] else 0 for v in V)
            for k in sorted(set().union(*kids.values()), key=lambda k: -weight(k)):
                add(k, {v: kids[v].get(k) for v in V}, depth + 1, r.id, r.path, {v: "inl" if k in kids[v] else "" for v in V})
        r.kids = len(rows) > n0
        return r

    for key in keys:
        tier = key.rsplit(" [", 1)[-1].rstrip("]")
        add(key, {v: units_by[v].get(key) for v in V}, 0, -1, (), {v: (tier if key in units_by[v] else "") for v in V})
    return rows


def top_units(V, B, units_by, ops, top):
    """The units to show: the top by own weight in any build, then the top half as many by change against B."""
    allk = set().union(*units_by.values())
    own = lambda k, v: units_by[v][k].own / ops[v] if k in units_by[v] else 0
    keys = sorted(allk, key=lambda k: (-max(own(k, v) for v in V), k))[:top]
    by_delta = sorted(allk, key=lambda k: (-max(abs(own(k, v) - own(k, B)) for v in V), k))
    return keys + [k for k in by_delta if k not in keys][:top // 2]


def note_for(notes, name):
    b = base(name)
    return next((v for k, v in notes.items() if b == k or b.endswith("." + k)), None)


def inline_md(t):
    """`code` and **bold**, escaped."""
    parts = re.split(r"(`[^`]+`)", t)
    return "".join(f"<code>{esc(x[1:-1])}</code>" if i % 2 else re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc(x))
                   for i, x in enumerate(parts))


def short_name(row):
    return esc(base(row.name).rsplit(".", 1)[-1])


def insights(rows, V, B, totals, event, notes):
    """The cards: (title, html, ids of the rows they name)."""
    others = [v for v in V if v != B]
    roots = [r for r in rows if r.depth == 0]
    d = lambda r, v: (r.own[v] or 0) - (r.own[B] or 0)
    peak = lambda xs: max((x or 0) for x in xs.values())
    cards = [("Benchmark threads", f"{esc(B)} <b>{ui.si(totals[B])}</b> {esc(event)}/op; " + ", ".join(
        f"{esc(v)} <b>{ui.si(totals[v])} ({totals[v] / totals[B] - 1:+.1%})</b>" for v in others) + f". Δ columns are against {esc(B)}.", [])]
    if not others:
        return cards
    big = sorted(roots, key=lambda r: -max(abs(d(r, v)) for v in others))[:4]
    cards.append(("Largest Δ own", f"Compiled methods whose own code time differs most from {esc(B)}: " + "; ".join(
        f"<code>{short_name(r)}</code> " + ", ".join(f"{esc(v)} {d(r, v) / 1e6:+.1f}M" for v in others) for r in big), [r.id for r in big]))
    flips = sorted((r for r in rows if r.depth == 1 and any(r.how[v] != r.how[B] and r.how[v] and r.how[B] for v in others)),
                   key=lambda r: -peak(r.incl))[:4]
    if flips:
        cards.append(("Inlining flipped", f"Callees that the JIT reaches differently from {esc(B)}: " + "; ".join(
            f"<code>{esc(r.name.rsplit('.', 1)[-1])}</code> in <code>{short_name(rows[r.parent])}</code>: " +
            ", ".join(f"{esc(v)} {r.how[v] or '—'}" for v in V) for r in flips) + ".",
            [x for r in flips for x in (r.id, r.parent)]))
    moved = sorted([r for r in roots if any(r.how[v] == "" for v in V)], key=lambda r: -peak(r.incl))[:5]
    if moved:
        cards.append(("Compile boundaries moved", "Compiled units missing from some builds (the same work, cut differently): " + "; ".join(
            f"<code>{short_name(r)}</code> (in {', '.join(esc(v) for v in V if r.how[v])})" for r in moved) + ". Compare totals, not these rows.",
            [r.id for r in moved]))
    c1 = sorted([r for r in roots if r.name.endswith("[C1]")], key=lambda r: -peak(r.own))[:4]
    if c1:
        body = "Hot methods running as C1 code in the measured window: " + ", ".join(
            f"<code>{short_name(r)}</code> {peak(r.own) / 1e6:.1f}M" for r in c1) + "."
        for r in c1:
            nt = note_for(notes, r.name)
            if nt:
                body += f" <b>{short_name(r)}</b>: {inline_md(nt)}"
        cards.append(("Still in C1", body, [r.id for r in c1]))
    return cards


def git(d, *args):
    try:
        return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def campaign_of(cell):
    """The campaign directory of a cell (<campaign>/<corpus>/<variant>/<round>), if it has a spec.json; else None."""
    camp = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(cell))))
    return camp if os.path.exists(os.path.join(camp, "spec.json")) else None


def spec_of(cell):
    camp = campaign_of(cell)
    try:
        return json.load(open(os.path.join(camp, "spec.json"))) if camp else {}
    except (OSError, ValueError):
        return {}


def project_root():
    try:
        from . import config
        return config.get().root
    except (Exception, SystemExit):  # no perflab.toml
        return os.getcwd()


INLINE_FLAGS = ("-XX:MaxInline", "-XX:FreqInline", "-XX:InlineSmall", "-XX:MaxTrivial", "-XX:InlineFrequency", "-XX:-Inline", "-XX:+Inline")


def provenance(V, cells):
    """A card per build: the checkout it was built from, JDK, JVM arguments, benchmark and score, the profile."""
    cols = []
    for v in V:
        cell = os.path.abspath(cells[v])
        d = profdiff.profile_dir(cell)
        r = json.load(open(os.path.join(d, "result.json")))[0]
        spec = spec_of(cell)
        tree = os.path.normpath(os.path.join(project_root(), (spec.get("trees") or {}).get(v, ".")))
        sha, branch = git(tree, "rev-parse", "HEAD"), git(tree, "rev-parse", "--abbrev-ref", "HEAD")
        status = [l[3:] for l in git(tree, "status", "--porcelain").splitlines()]
        rows = []
        if sha:
            rows.append(("checkout", f'<code>{esc(sha[:10])}</code> {esc(branch)} {esc(git(tree, "log", "-1", "--format=%s")[:80])}'
                                     f'<br><span class="k">{esc(tree)}</span>'
                                     + (f'<br><span class="k">{len(status)} uncommitted: ' + ", ".join(f"<code>{esc(x)}</code>" for x in status[:6])
                                        + ("…" if len(status) > 6 else "") + "</span>" if status else "")))
        desc = (spec.get("variantDescriptions") or {}).get(v, "")
        desc = "\n".join(desc) if isinstance(desc, list) else desc
        if desc:
            rows.append(("variant", inline_md(desc)))
        jvm = r.get("jvm", "")
        release = os.path.join(os.path.dirname(os.path.dirname(jvm)), "release")
        jdk_src = ""
        if jvm and os.path.exists(release):
            jdk_src = next((l.split("=", 1)[1].strip().strip('"') for l in open(release) if l.startswith("SOURCE=")), "")
        rows.append(("JDK", f'{esc(r.get("jdkVersion", ""))} · {esc(r.get("vmName", ""))} {esc(r.get("vmVersion", ""))}<br><span class="k">{esc(jvm)}</span>'
                            + (f'<br><span class="k">{esc(jdk_src)}</span>' if jdk_src else "")))
        args = [a for a in r.get("jvmArgs", []) if not a.startswith(("-Dbenchlab.", "-Dperflab."))]
        rows.append(("JVM args", "<code>" + " ".join(f"<b>{esc(a)}</b>" if a.startswith(INLINE_FLAGS) else esc(a) for a in args) + "</code>"))
        pm = r.get("primaryMetric", {})
        params = ", ".join(f"{k}={x}" for k, x in (r.get("params") or {}).items() if x)
        rows.append(("benchmark", f'{esc(r.get("benchmark", "").rsplit(".", 2)[-2] if "." in r.get("benchmark", "") else r.get("benchmark", ""))}'
                                  f'{" · " + esc(params) if params else ""} · JMH {esc(r.get("jmhVersion", ""))}<br>'
                                  f'{r.get("warmupIterations")} × {esc(str(r.get("warmupTime")))} warmup, {r.get("measurementIterations")} × '
                                  f'{esc(str(r.get("measurementTime")))} measured, {r.get("forks")} fork'
                                  + (f' · <b>{ui.num(pm["score"])} ± {ui.num(pm["scoreError"], pm["score"])} {esc(ui.unit(pm.get("scoreUnit")))}</b>'
                                     if isinstance(pm.get("score"), (int, float)) and isinstance(pm.get("scoreError"), (int, float)) else "")))
        prof = os.path.join(cell, "profile.txt")
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(os.path.join(d, "result.json"))))
        rows.append(("profile", f'{esc(open(prof).read().strip()) if os.path.exists(prof) else ""} · {when}<br><span class="k">{esc(cell)}</span>'))
        cols.append(f'<div class="prov v-{esc(v)}"><h3>{esc(v)}</h3><table>'
                    + "".join(f"<tr><th>{k}</th><td>{x}</td></tr>" for k, x in rows) + "</table></div>")
    return '<div class="provs">' + "".join(cols) + "</div>"


def cards_html(cards):
    cs = "".join(f'<div class="ins" data-i="{i}" data-rows="{",".join(map(str, ids))}" title="{esc(re.sub("<[^>]+>", "", body))}">'
                 f'<h3>{t}</h3><p>{body}</p></div>' for i, (t, body, ids) in enumerate(cards))
    # the full cards stay in the page; a fixed bar (out of flow, so nothing moves) with the same cards appears once they
    # have scrolled away
    return f'<div class="insights full">{cs}</div><div class="insights bar">{cs}</div>'


def table_html(rows, V, B, notes):
    others = [v for v in V if v != B]
    unit_ids = {base(r.name): r.id for r in rows if r.depth == 0}
    num = lambda x: '<span class="z">—</span>' if x is None else f"{x / 1e6:.2f}"

    def delta(r, v, f):
        a, b = getattr(r, f)[B], getattr(r, f)[v]
        if a is None or b is None:
            return ""
        x = (b - a) / 1e6
        return f'<span class="{"up" if x > 0.3 else "down" if x < -0.3 else "z"}">{x:+.2f}</span>'

    chip = lambda h: f'<span class="h {h.replace("+", "-").lower()}">{h}</span>' if h else '<span class="h none">—</span>'
    vc = lambda v: f"v-{esc(v)}"
    out = []
    for r in rows:
        tog = '<span class="t">▸</span>' if r.kids else '<span class="t"></span>'
        flip = " flip" if r.depth == 1 and len({h for h in r.how.values() if h}) > 1 else ""
        label = esc(base(r.name) if r.depth == 0 else r.name)
        if r.kind == "call" or (r.depth == 1 and any("call" in h for h in r.how.values())):
            tgt = unit_ids.get(r.name)
            if tgt is not None:
                label += f' <a class="jump" href="#" data-to="{tgt}" title="its own compiled code">↗</a>'
        nt = note_for(notes, r.name)
        if nt:
            label += f' <span class="note" title="{esc(nt)}">ⓘ</span><div class="notetxt">{inline_md(nt)}</div>'
        missing = [v for v in V if not r.how[v]] if r.depth == 0 else []
        if missing:
            label += f' <i>not in {", ".join(esc(v) for v in missing)}</i>'
        tds = "".join(f'<td class="hw {vc(v)}">{chip(r.how[v])}</td>' for v in V)
        no_own = r.kind == "call" or all(x is None for x in r.own.values())
        for f in ("incl", "own"):
            blank = f == "own" and no_own
            tds += f'<td class="{vc(B)} base">{"" if blank else num(getattr(r, f)[B])}</td>'
            for v in others:
                tds += (f'<td class="{vc(v)}">{"" if blank else num(getattr(r, f)[v])}</td>'
                        f'<td class="dl {vc(v)}">{"" if blank else delta(r, v, f)}</td>')
        out.append(f'<tr class="r d{min(r.depth, 2)} {r.kind}{flip}" data-id="{r.id}" data-p="{r.parent}"{" hidden" if r.depth else ""}>'
                   f'<td class="nm" style="padding-left:{8 + 18 * r.depth}px">{tog}{label}</td>{tds}</tr>')
    head = ('<th class="nm">compiled method ▸ its callees ▸ inlined below them</th>'
            + "".join(f'<th class="hw {vc(v)}">{esc(v)}</th>' for v in V))
    for f in ("incl", "own"):
        head += f'<th class="{vc(B)} base">{f} {esc(B)}</th>' + "".join(
            f'<th class="{vc(v)}">{f} {esc(v)}</th><th class="dl {vc(v)}">Δ</th>' for v in others)
    return f'<div class="tree"><table><thead><tr>{head}</tr></thead><tbody>{"".join(out)}</tbody></table></div>'


CSS = """
:root{--up:#b42318;--down:#1e7a3c;--hl:#fff4c2;--hlb:#d9a400;--hv:#e3eeff;--hvb:#3b6fd4;
  --c2:#3b6fd4;--c1:#b7791f;--inl:#d6f0dc;--inl-fg:#1e6b34;--call:#fde2cf;--call-fg:#9a4a12}
@media (prefers-color-scheme: dark){:root{--up:#ff8a80;--down:#6fd69a;--hl:#4a3f10;--hlb:#c9a300;--hv:#1d2f4f;--hvb:#6b9cff;
  --inl:#1f4a2b;--inl-fg:#9fe0b0;--call:#5a3115;--call-fg:#ffc9a0}}
main{padding:12px 20px 40px;max-width:1800px;margin:0 auto}
h1{font-size:16px;margin:4px 0 8px} p.about{color:var(--muted);max-width:1100px}
.tree table{border-collapse:collapse;font:12px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;width:100%;background:var(--panel)}
.tree th{position:sticky;top:var(--bar-h,0px);background:var(--line2);color:var(--fg);text-align:right;padding:4px 8px;font-weight:600;white-space:nowrap;z-index:2;
  transition:top .18s cubic-bezier(.2,.7,.2,1)}
.tree th.nm,.tree td.nm{text-align:left} .tree td{text-align:right;padding:2px 8px;white-space:nowrap;font-variant-numeric:tabular-nums}
.tree td.nm{white-space:normal;word-break:break-all;width:50%} tr.d0{border-top:1px solid var(--line)} tr.d0 td{font-weight:600}
tr.call td{color:var(--muted)} .t{display:inline-block;width:14px;cursor:pointer;color:var(--muted)}
.up{color:var(--up)} .down{color:var(--down)} .z{color:var(--muted)} .tree i{color:var(--muted);font-weight:400}
td.dl,th.dl{border-right:1px solid var(--line)} td.base,th.base{border-left:1px solid var(--line)}
.tree tr:hover td{background:var(--line2)} tr.hl td{background:var(--hl)} tr.hv td{background:var(--hv)}
tr.hl.hv td{background:var(--hl);box-shadow:inset 0 0 0 1px var(--hvb)}
td.hw,th.hw{text-align:center;width:54px;padding:2px 4px} .h{display:inline-block;min-width:34px;border-radius:4px;padding:0 4px;font-size:11px;line-height:16px}
.h.c2{background:var(--c2);color:#fff} .h.c1{background:var(--c1);color:#fff} .h.inl{background:var(--inl);color:var(--inl-fg)}
.h.call{background:var(--call);color:var(--call-fg)} .h.inl-call{background:linear-gradient(90deg,var(--inl) 50%,var(--call) 50%);color:var(--fg)}
.h.none{color:var(--muted)}
tr.flip td.nm{box-shadow:inset 3px 0 0 var(--hlb)} a.jump{color:var(--muted)}
.note{color:var(--hvb);cursor:help;font-weight:600} .notetxt{font:11.5px/1.35 -apple-system,system-ui,sans-serif;color:var(--muted);font-weight:400;margin:2px 0 2px 14px;max-width:720px}
.insights.full{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;margin:12px 0 16px}
.insights.bar{position:fixed;top:0;left:0;right:0;z-index:5;display:flex;flex-wrap:nowrap;overflow-x:auto;gap:8px;padding:6px 16px;
  background:var(--bg);border-bottom:1px solid var(--line);box-shadow:0 2px 8px #0000001f;scroll-snap-type:x proximity;scrollbar-width:thin;
  transform:translateY(-100%);opacity:0;visibility:hidden;pointer-events:none;
  transition:transform .18s cubic-bezier(.2,.7,.2,1),opacity .18s ease,visibility 0s linear .18s}
.insights.bar.on{transform:none;opacity:1;visibility:visible;pointer-events:auto;transition:transform .18s cubic-bezier(.2,.7,.2,1),opacity .18s ease,visibility 0s}
.insights.bar .ins{flex:0 0 300px;scroll-snap-align:start;padding:4px 10px;height:50px;overflow:hidden}
.insights.bar .ins p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:12px}
.insights.bar .ins h3{font-size:12px;margin:0 0 2px}
@media (prefers-reduced-motion: reduce){.insights.bar,.insights.bar.on,.tree th{transition:none}}
.ins{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px;cursor:default}
.ins:hover,.ins.hov{border-color:var(--hvb);background:var(--hv)} .ins.pin{border-color:var(--hlb);background:var(--hl);box-shadow:inset 3px 0 0 var(--hlb)}
.ins.pin:hover,.ins.pin.hov{border-color:var(--hvb)}
.ins h3{margin:0 0 4px;font-size:13px} .ins p{margin:0;font-size:12.5px}
.provs{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:10px;margin:8px 0}
.prov{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 12px} .prov h3{margin:2px 0 4px;font-size:13px}
.prov table{font-size:12px;width:100%;border-collapse:collapse} .prov th{text-align:left;vertical-align:top;color:var(--muted);font-weight:500;padding:2px 8px 2px 0;width:70px}
.prov td{text-align:left;word-break:break-word;padding:2px 0} .prov code{font-size:11px}
.chips{display:flex;gap:6px;align-items:center;margin:8px 0;flex-wrap:wrap}
.chip.base{cursor:default;border-style:dashed}
"""

JS = r"""
const rows=[...document.querySelectorAll('tr.r')], kids={}, byId={};
rows.forEach(r=>{(kids[r.dataset.p]??=[]).push(r); byId[r.dataset.id]=r;});
function setOpen(r,open){const t=r.querySelector('.t');if(t.textContent)t.textContent=open?'▾':'▸';r.dataset.open=open?1:'';
  (kids[r.dataset.id]||[]).forEach(k=>{k.hidden=!open;if(!open)setOpen(k,false);});}
rows.forEach(r=>r.querySelector('.t').onclick=()=>setOpen(r,!r.dataset.open));
function reveal(r){const p=byId[r.dataset.p]; if(p){reveal(p); if(!p.dataset.open) setOpen(p,true);}}
const full=document.querySelector('.insights.full'), bar=document.querySelector('.insights.bar');
let pinned=null;
function centerPinned(smooth){if(pinned===null) return; const c=bar.querySelector(`.ins[data-i="${pinned}"]`); if(!c) return;
  bar.scrollTo({left: c.offsetLeft-(bar.clientWidth-c.offsetWidth)/2, behavior: smooth?'smooth':'auto'});}
function setBar(on){const was=bar.classList.contains('on'); bar.classList.toggle('on',on);
  document.documentElement.style.setProperty('--bar-h', on ? bar.offsetHeight+'px' : '0px'); if(on&&!was) centerPinned(false);}
new IntersectionObserver(([e])=>setBar(!e.isIntersecting && e.boundingClientRect.bottom < 0)).observe(full);
window.addEventListener('resize', ()=>setBar(bar.classList.contains('on')));
const twins=i=>document.querySelectorAll(`.ins[data-i="${i}"]`);
function mark(card,cls,on){(card.dataset.rows||'').split(',').filter(Boolean).forEach(id=>{const r=byId[id]; if(!r) return; if(on) reveal(r); r.classList.toggle(cls,on);});}
document.querySelectorAll('.ins').forEach(c=>{
  c.onmouseenter=()=>{twins(c.dataset.i).forEach(t=>t.classList.add('hov')); mark(c,'hv',true);};
  c.onmouseleave=()=>{twins(c.dataset.i).forEach(t=>t.classList.remove('hov')); mark(c,'hv',false);};
  c.onclick=()=>{
    if(pinned!==null){twins(pinned).forEach(t=>t.classList.remove('pin')); mark(twins(pinned)[0],'hl',false);}
    pinned = pinned===c.dataset.i ? null : c.dataset.i;
    if(pinned!==null){twins(pinned).forEach(t=>t.classList.add('pin')); mark(c,'hl',true); if(bar.classList.contains('on')) centerPinned(true);
      const f=(c.dataset.rows||'').split(',')[0]; if(f&&byId[f]) byId[f].scrollIntoView({block:'center',behavior:'smooth'});}};
});
document.querySelectorAll('a.jump').forEach(a=>a.onclick=e=>{e.preventDefault();const r=byId[a.dataset.to];if(r){r.hidden=false;r.scrollIntoView({block:'center',behavior:'smooth'});r.classList.add('hv');setTimeout(()=>r.classList.remove('hv'),1500);}});
function all(o){rows.forEach(r=>{if(o){r.hidden=false;const t=r.querySelector('.t');if(t.textContent)t.textContent='▾';r.dataset.open=1}else if(r.dataset.p!=='-1'){r.hidden=true}else setOpen(r,false)})}
// build chips: hide or show a build's columns and provenance card; remembered per browser, best effort
const style=document.createElement('style'); document.head.appendChild(style);
function applyChips(){const off=[...document.querySelectorAll('.chip[data-v]:not(.on)')].map(c=>c.dataset.v);
  style.textContent=off.map(v=>`.v-${CSS.escape(v)}{display:none}`).join('\n');
  try{localStorage.setItem('inlinetree-off',JSON.stringify(off));}catch(e){}}
document.querySelectorAll('.chip[data-v]').forEach(c=>c.onclick=()=>{c.classList.toggle('on');applyChips();});
try{(JSON.parse(localStorage.getItem('inlinetree-off')||'[]')).forEach(v=>{const c=document.querySelector(`.chip[data-v="${CSS.escape(v)}"]`); if(c) c.classList.remove('on');});}catch(e){}
applyChips();
"""


def page(V, B, loaded, cells, event="cycles", top=25, minw=0.5e6, notes=None, strip=(), home=None):
    """The page's HTML. `loaded`: {build: profdiff.load(...)}, whose `collapsed` file is read here."""
    notes = notes or {}
    short = shortener(strip)
    ops = {v: loaded[v]["ops"] for v in V}
    units_by = {}
    for v in V:
        with open(loaded[v]["collapsed"]) as f:
            units_by[v] = units(f, short)
    totals = {v: loaded[v]["total"] / ops[v] for v in V}
    rows = build_rows(V, units_by, ops, top_units(V, B, units_by, ops, top), minw)
    chips = "".join((f'<button class="chip base" title="the baseline">{esc(v)} (baseline)</button>' if v == B else
                     f'<button class="chip on" data-v="{esc(v)}" title="show or hide this build">{esc(v)}</button>') for v in V)
    title = f"inline trees: {', '.join(V)}"
    return f"""{ui.HEAD}<title>{esc(title)}</title>{ui.style(ui.BASE, CSS)}
{ui.masthead(title, home, slim=True)}<main>
<h1>Compilation units: {esc(", ".join(V))} <span class="k">({esc(event)}, millions per op; Δ against {esc(B)})</span></h1>
{provenance(V, cells)}
<p class="about">Each bold row is a JIT-compiled method (chip: <span class="h c2">C2</span> or <span class="h c1">C1</span>). Expand it (▸) for the
methods it reaches, one row per callee, with how each build reached it: <span class="h inl">inl</span> inlined into this compiled code,
<span class="h call">call</span> a real call into separately compiled code (↗ jumps to it), <span class="h inl-call">inl+call</span> both at different
call sites, — not at all. Rows where builds differ are marked at the left. Deeper rows are what was inlined into an inlined callee.
A number shows as — where that build does not reach the row inside this compiled method: that cost is in the callee's own compiled code, not zero.
<b>own</b>: time in that code itself; <b>incl</b>: including everything below it. Δ = build − {esc(B)}: red, more; green, less.
Hover a card to preview its rows (blue); click to pin (amber) and scroll to them; click again to unpin.</p>
<div class="chips"><span class="k">builds:</span>{chips}<span class="k" style="margin-left:12px">rows:</span><button class="chip" onclick="all(true)">expand all</button><button class="chip" onclick="all(false)">collapse all</button></div>
{cards_html(insights(rows, V, B, totals, event, notes))}
{table_html(rows, V, B, notes)}
</main><script>{JS}</script>"""


def jfrconv_for(cells):
    """jfrconv beside the async-profiler library of the cells' campaign (its spec's profile.lib), else perflab's."""
    from . import jmh
    prof = next((s.get("profile") for s in map(spec_of, cells) if isinstance(s.get("profile"), dict)), None) or {}
    return jmh.jfrconv(jmh.async_lib(prof.get("lib")))


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab inlinetree", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", metavar="label=cell")
    ap.add_argument("--baseline", help="the label to compare against (default: the first)")
    ap.add_argument("--event", default="cycles")
    ap.add_argument("--top", type=int, default=25, help="compiled methods by own weight (and half as many by change) (default %(default)s)")
    ap.add_argument("--min", type=float, default=0.5, help="hide rows under this many million events per op (default %(default)s)")
    ap.add_argument("--notes", help="JSON {method: Markdown note}")
    ap.add_argument("--strip", action="append", default=[], help="a package to leave out of names, e.g. dotty.tools.dotc (repeatable)")
    ap.add_argument("--jfrconv")
    ap.add_argument("--out", help="the page (default: <campaign>/inlinetree-<event>.html when the cells are of one campaign)")
    x = ap.parse_args(argv)
    bad = [r for r in x.runs if "=" not in r]
    if bad:
        ap.error(f"expected <label>=<cell>, got {' '.join(bad)}")
    cells = dict(r.split("=", 1) for r in x.runs)
    B = x.baseline or next(iter(cells))
    if B not in cells:
        ap.error(f"--baseline {B}: not one of {', '.join(cells)}")
    V = [B] + [v for v in cells if v != B]
    out = x.out
    if not out:
        camps = {campaign_of(c) for c in cells.values()}
        if len(camps) != 1 or None in camps:
            ap.error("--out is needed when the cells are not all of one campaign")
        out = os.path.join(camps.pop(), f"inlinetree-{x.event}.html")
    notes = json.load(open(x.notes)) if x.notes else {}
    jfrconv = x.jfrconv or jfrconv_for(cells.values())
    with tempfile.TemporaryDirectory() as tmp:
        loaded = {v: profdiff.load(cells[v], x.event, jfrconv, tmp, f"{i}") for i, v in enumerate(V)}
        html_ = page(V, B, loaded, cells, x.event, x.top, x.min * 1e6, notes, x.strip, ui.home_from(os.path.dirname(os.path.abspath(out))))
    with open(out, "w") as f:
        f.write(html_)
    print(f"wrote {os.path.abspath(out)} · " + ", ".join(f"{v} {ui.si(loaded[v]['total'] / loaded[v]['ops'])} {x.event}/op" for v in V))
    return 0
