"""Curated profile diffs of two variants of an A/B campaign: the raw profdiff, and beside it the same pair with the
stacks made comparable, plus tables that say where an event moved.

  perflab ab diff <spec.json | campaign> <a> <b> [--corpus <c>] [--round <n>] [--event <e>]...
                  [--curate <preset> | --curate '<json hints>' | --raw] [--by-leaf] [--leaf line|bci] [--force]

A flame graph diff of a large program compares badly as recorded: interpreter frames, JDK plumbing
(`java/lang/invoke`, reflection, lambdas, lazy-val initializers) in every stack, wrapper frames one build has and the
other lacks (so a whole tower shows as new), and deep recursion that splits every tower. The curated diff, written to
`<campaign>/diff-<a>-<b>-curated/` (or `-<preset>`), applies in order:

1. names: hidden-class addresses and thread ids stripped (as profdiff does), and jfrconv's compilation suffixes
   (`_[j]`, `_[i]`, ...), so inlined and compiled copies of a method are one frame;
2. drop: frames that mean nothing to the comparison (`interpreted`), wherever they are; and transparent: frames one
   build has where the other does the same work inline (a `VarHandle` access where the other loads the field; a
   lab's shared-state helpers and accessors), removed wherever they are, the leaf included, so their events are its
   nearest remaining caller's;
3. anchor (a hint): each stack cut above its first frame matching it, so one subsystem is compared; stacks without
   it are left out;
4. fold: plumbing frames folded into their caller, except as the leaf, where the event landed (`Unsafe.getReference`);
5. recursion: each method's outermost occurrence in a stack kept, the deeper ones dropped (the leaf stays);
6. alignment: a frame that appears above the leaf in only one build's stacks is dropped there (it stays as a leaf),
   so the towers of both builds merge.

The tables are of the stacks after steps 1-3 (they need no alignment, and fold frames are never owners):

- self by owner: each stack's events credited to its nearest frame matching the `owner` prefix (skipping `ownerSkip`
  accessors, unless nothing else matches), so events that moved between methods inlined into one another stay in one
  bucket; without an owner, the leaf method, as profdiff;
- groups: named regexes over the owners, one net row per group;
- growth beyond the overall ratio: frames' inclusive events, b − a × (b's total / a's), for frames of both builds
  above `excessMin` of a's total: the subtrees that grew more than the whole.

Hints come from `[diff]` in perflab.toml (the lab's default), then the campaign spec's `"diff"`, then a named preset
from either one's `presets`, then `--curate '<json>'`:

  [diff]                                   "diff": {
  owner = "dotty/tools/dotc/"                "owner": "dotty/tools/dotc/",
  ownerSkip = ["dotty/tools/dotc/core/Contexts$Context."]
  anchor = "Typer\\.typed"                   "groups": {"denot/symbol": "Types\\$NamedType\\.(denot|symbol)"},
  fold = ["scala/runtime/"]                  "presets": {"typer": {"anchor": "Typer\\.typed"}}}
  drop = []
  transparent = ["dotty/tools/sharing/"]
  byLeaf = false
  [diff.groups]
  "denot/symbol" = "Types\\$NamedType\\.(denot|symbol)"

The built-in preset `light` (`--curate light`, and written by default as `<campaign>/diff-<a>-<b>-light/`) keeps what
the curated diff erases on purpose: names keep their compilation suffixes (a method inlined and the same method
compiled are different frames, coloured by kind), no frame is aligned away and recursion stays; only steps 1 (hidden
classes, thread ids), 2 (without transparent frames: it is for seeing them) and 4 apply. Beside its graphs, `toggle-a-<event>.html` and `toggle-b-<event>.html` (and
`-byleaf`) are the two builds in jfrconv's viewer with one layout, per op on one scale (perflab.kinds), which its
compare page flips between in place (t).

Every diff, raw and light, has the frame-kind flips table (perflab.kinds): per method, its self events per op inlined and in
its own frame in each build, ranked by the self events that changed kind, with C2's reasons when the cells have a
"jitRecording".

With `leaf` ("line" or "bci", or `--leaf`), the leaf frame is a line (`Class.method:42`) or bytecode index
(`Class.method@17`) of its method, and the callers stay methods, so the towers still align: with a PMU event sampled
with a precise PC (kperf's L1D misses), the leaf's line names the load that counted. A transparent leaf's events go to
its caller's line, the call. The owner table is by owner method and line (the line in the owner method, a call if the
event landed below it); groups match its method. The diff goes to `diff-<a>-<b>-<curated>-<leaf>/`, the raw one stays
by method, and each table says what share of each build's samples had a precise PC, where the recording says.

`fold`, `drop` and `transparent` add to the defaults (`"transparent": null` clears them), `groups` and `presets` merge by name, anything else replaces. Each cell's
stacks are cached (perflab.stacks), so curating a pair again with other hints takes seconds. The rules applied are in
the diff's pair.json and on its page.
"""
import argparse, collections, glob, hashlib, json, os, re, subprocess, sys, tempfile

from . import compare, config, flamegraph, jmh, kinds, profdiff, regraph, sources, stacks
from .stacks import LINE

SUFFIX = re.compile(r"_\[[a-z0-9]+\]$")
DROP = [r"^interpreted$"]
FOLD = [r"^java/lang/invoke/", r"^jdk/internal/reflect/", r"^java/lang/reflect/Method\.invoke", r"\$\$Lambda\.",
        r"\$lzyINIT\d*(\$|$)"]
TRANSPARENT = [r"^java/lang/invoke/VarHandle"]  # VarHandle..., VarHandleGuards, VarHandleInts$FieldInstanceReadOnly, ...
DEFAULTS = {"drop": [], "fold": [], "transparent": TRANSPARENT, "anchor": None, "owner": None, "ownerSkip": [], "groups": {}, "byLeaf": False,
            "align": True, "recursion": True, "excessMin": 0.002, "top": 25}
NO_OWNER = "(no owner frame)"
LIGHT = {"kinds": True, "align": False, "recursion": False, "transparent": None}  # the built-in preset `light`


def merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        if k in ("fold", "drop", "ownerSkip", "transparent") and v is not None:
            out[k] = list(out.get(k) or []) + list(v)
        elif k in ("groups", "presets"):
            out[k] = {**(out.get(k) or {}), **v}
        else:
            out[k] = v
    return out


def rules_for(spec, curate=None):
    """The hints for a campaign (`spec`: its spec.json), with `curate` a preset name or a JSON object; (rules, name)."""
    r = merge(merge(DEFAULTS, config.get().data.get("diff")), spec.get("diff"))
    name = "curated"
    if curate:
        if curate.lstrip().startswith("{"):
            extra = json.loads(curate)
            name = "curated-" + hashlib.sha1(json.dumps(extra, sort_keys=True).encode()).hexdigest()[:6]
        elif curate in (r.get("presets") or {}):
            extra, name = r["presets"][curate], curate
        elif curate == "light":
            extra, name = LIGHT, "light"
        else:
            sys.exit(f"--curate {curate}: neither JSON hints nor a preset ({', '.join(r.get('presets') or {}) or 'none defined'})")
        r = merge(r, extra)
    r.pop("presets", None)
    return r, name


def as_list(x):
    return [x] if isinstance(x, str) else list(x or [])


class Curator:
    """The rules compiled once, applied to frames by a table of global ids shared by both builds."""

    def __init__(self, rules):
        self.r = rules
        any_of = lambda pats: re.compile("|".join(f"(?:{p})" for p in pats)) if pats else None
        self.drop_re = any_of(DROP + as_list(rules.get("drop")) + as_list(rules.get("transparent")))
        self.fold_re = any_of(FOLD + as_list(rules.get("fold")))
        self.anchor_re = re.compile(rules["anchor"]) if rules.get("anchor") else None
        self.owners = tuple(as_list(rules.get("owner")))
        self.skip = tuple(as_list(rules.get("ownerSkip")))
        self.names, self.plain, self.lined, self.method, self.ids = [], [], [], [], {}
        self.leaf = rules.get("leaf")
        self.kinds = bool(rules.get("kinds"))
        self.drop, self.fold, self.anchor, self.owner, self.skipped = [], [], [], [], []

    def gid(self, frame):
        lined = profdiff.HIDDEN_ADDRESS.sub("", SUFFIX.sub("", frame))
        name = LINE.sub("", lined) if self.leaf else lined
        if self.kinds:
            k = SUFFIX.search(frame)
            frame = lined + (k.group(0) if k else "")
        else:
            frame = lined
        i = self.ids.get(frame)
        if i is None:
            i = self.ids[frame] = len(self.names)
            self.names.append(frame)
            self.plain.append(name)
            self.lined.append(lined)
            self.method.append(i)  # the frame without its line: below, once the frame's own entries are in
            self.drop.append(bool(self.drop_re and self.drop_re.search(name)))
            self.fold.append(bool(self.fold_re and self.fold_re.search(name)))
            self.anchor.append(bool(self.anchor_re and self.anchor_re.search(name)))
            self.owner.append(bool(self.owners) and name.startswith(self.owners) and not self.fold[i])
            self.skipped.append(name.startswith(self.skip) if self.skip else False)
            if name != lined:
                self.method[i] = self.gid(LINE.sub("", frame))
        return i

    def base(self, st):
        """Steps 1-3: [(global ids, root first; count)], and the events left out for want of the anchor."""
        local = [self.gid(f) for f in st.frames]
        out, outside = [], 0
        for s, n in st.stacks:
            g = [x for x in (local[i] for i in s) if not self.drop[x]]
            if not g:
                continue
            if self.anchor_re:
                k = next((k for k, x in enumerate(g) if self.anchor[x]), None)
                if k is None:
                    outside += n
                    continue
                g = g[k:]
            out.append((g, n))
        return out, outside

    def shaped(self, base):
        """Steps 4-5: (body, leaf, count) per stack; only the leaf keeps its line."""
        out = []
        m = self.method
        for g, n in base:
            leaf, body = g[-1], [m[x] for x in g[:-1] if not self.fold[x]]
            if self.r.get("recursion", True):
                seen = set()
                body = [x for x in body if not (x in seen or seen.add(x))]
            out.append((body, leaf, n))
        return out

    def aligned(self, a, b):
        """Step 6 over both builds, then equal stacks merged: two Counters of `;`-joined names."""
        if self.r.get("align", True):
            above = lambda xs: {x for body, _, _ in xs for x in body}
            one_sided = above(a) ^ above(b)
        else:
            one_sided = set()
        self.one_sided = len(one_sided)

        def fold(xs):
            c = collections.Counter()
            for body, leaf, n in xs:
                c[";".join([self.names[x] for x in body if x not in one_sided] + [self.names[leaf]])] += n
            return c
        return fold(a), fold(b)

    def owner_of(self, g):
        if not self.owners:
            return g[-1]
        first = None
        for x in reversed(g):
            if self.owner[x]:
                if not self.skipped[x]:
                    return x
                first = first if first is not None else x
        return first

    def tables(self, base):
        """{owner name: events}, {frame name: inclusive events} of base stacks (owner frames only, with an owner), by
        method, whatever its kinds."""
        own, incl = collections.Counter(), collections.Counter()
        for g, n in base:
            o = self.owner_of(g)
            own[NO_OWNER if o is None else self.lined[o]] += n
            for name in {self.plain[x] for x in g if (self.owner[x] if self.owners else not self.fold[x])}:
                incl[name] += n
        return own, incl


def summarize(rules, own_a, own_b, incl_a, incl_b, ta, tb, ops_a, ops_b):
    """The tables, per op: owners' self Δ, groups' net Δ, inclusive growth beyond the overall ratio."""
    pa, pb = lambda x: x / ops_a, lambda x: x / ops_b
    TA, TB = pa(ta), pb(tb)
    R = TB / TA if TA else 1.0
    owners = sorted(({"name": k, "a": pa(own_a[k]), "b": pb(own_b[k]), "delta": pb(own_b[k]) - pa(own_a[k])}
                     for k in set(own_a) | set(own_b)), key=lambda r: r["delta"])
    groups = []
    pats = [(g, re.compile(p)) for g, p in (rules.get("groups") or {}).items()]
    if pats:
        acc = {g: {"name": g, "a": 0.0, "b": 0.0, "members": 0} for g, _ in pats}
        rest = {"name": "(ungrouped)", "a": 0.0, "b": 0.0, "members": 0}
        for o in owners:
            g = next((acc[g] for g, p in pats if p.search(LINE.sub("", o["name"]))), rest)
            g["a"] += o["a"]; g["b"] += o["b"]; g["members"] += 1
        groups = sorted(list(acc.values()) + [rest], key=lambda g: -(g["b"] - g["a"]))
        for g in groups:
            g["delta"] = g["b"] - g["a"]
    floor = rules.get("excessMin", 0.002) * TA
    excess = sorted(({"name": k, "a": pa(incl_a[k]), "b": pb(incl_b[k]), "excess": pb(incl_b[k]) - pa(incl_a[k]) * R}
                     for k in set(incl_a) & set(incl_b) if pa(incl_a[k]) + pb(incl_b[k]) > floor), key=lambda r: -r["excess"])
    out = {"total": {"a": TA, "b": TB, "ratio": R}, "owners": owners, "groups": groups, "excess": excess}
    if rules.get("leaf"):
        out["lines"] = by_method(owners)
    return out


def add_text(lines, srcs):
    """Each line of `lines` (by_method's) [line, events] → [line, events, its source text or None], from that build's
    perflab.sources.Source."""
    for m in lines:
        for k, src in zip(("linesA", "linesB"), srcs):
            for x in m[k]:
                x.append(src.line(m["name"], int(x[0])) if src and x[0].isdigit() else None)


def by_method(owners, top=5):
    """The owners by line, gathered by method: the line numbers of two builds of different sources rarely match, so
    each method's Δ and, per build, its lines with the most events."""
    ms = {}
    for o in owners:
        name = LINE.sub("", o["name"])
        m = ms.setdefault(name, {"name": name, "a": 0.0, "b": 0.0, "linesA": [], "linesB": []})
        m["a"] += o["a"]; m["b"] += o["b"]
        at = o["name"][len(name):] or "?"
        for side in ("a", "b"):
            if o[side]:
                m["lines" + side.upper()].append([at.lstrip(":"), o[side]])
    for m in ms.values():
        m["delta"] = m["b"] - m["a"]
        for k in ("linesA", "linesB"):
            m[k] = sorted(m[k], key=lambda x: (-x[1], x[0]))[:top]
    return sorted(ms.values(), key=lambda m: (m["delta"], m["name"]))


def table_md(event, t, la, lb, rules, top):
    si = profdiff.si
    tot = t["total"]
    pct = lambda d: f"{100 * d / tot['a']:+.2f}%" if tot["a"] else ""
    out = [f"{event} per op (benchmark threads, curated): a {si(tot['a'])}, b {si(tot['b'])}, {100 * (tot['ratio'] - 1):+.1f}%  "
           f"(a = {la}, b = {lb}; {'owner ' + ', '.join(as_list(rules['owner'])) if rules.get('owner') else 'by leaf method'})", ""]
    if t.get("leaf"):
        p = t.get("precise") or {}
        share = lambda s: "not recorded" if s is None else f"{100 * s:.0f}%"
        out += [f"by {t['leaf']}: the leaf frame is `method:{'line' if t['leaf'] == 'line' else '@bci'}`, the owner its line; samples "
                f"with a precise PC (the PMU's, so the leaf is the instruction that counted): a {share(p.get('a'))}, b {share(p.get('b'))}", ""]
    row = lambda r: f"| {'+' if r['delta'] > 0 else ''}{si(r['delta'])} | {si(r['a'])} | {si(r['b'])} | {pct(r['delta'])} | `{r['name']}` |"
    out += [f"self {event} per op by {'owner' if rules.get('owner') else 'method'}, biggest increases then decreases (b − a):", "",
            "| Δ | a | b | Δ of a's total | method |", "|---|---|---|---|---|"]
    out += [row(r) for r in t["owners"][::-1][:top]] + ["| … | | | | |"] + [row(r) for r in t["owners"][:top][::-1]]
    if t.get("lines"):
        ln = lambda xs: ", ".join(f"{x[0]} {si(x[1])}" for x in xs)
        mrow = lambda m: f"| {'+' if m['delta'] > 0 else ''}{si(m['delta'])} | {si(m['a'])} | {si(m['b'])} | {pct(m['delta'])} | `{m['name']}` | {ln(m['linesA'])} | {ln(m['linesB'])} |"
        out += ["", f"the same by method, with each build's {t['leaf']}s with the most (their sources differ, so their numbers may not match):", "",
                "| Δ | a | b | Δ of a's total | method | a's | b's |", "|---|---|---|---|---|---|---|"]
        out += [mrow(m) for m in t["lines"][::-1][:top]] + ["| … | | | | | | |"] + [mrow(m) for m in t["lines"][:top][::-1]]
    if t["groups"]:
        out += ["", f"groups (net self {event} per op of their owners):", "", "| group | Δ | a | b | Δ of a's total | owners |", "|---|---|---|---|---|---|"]
        out += [f"| {g['name']} | {'+' if g['delta'] > 0 else ''}{si(g['delta'])} | {si(g['a'])} | {si(g['b'])} | {pct(g['delta'])} | {g['members']} |"
                for g in t["groups"]]
    out += ["", f"inclusive {event} per op beyond the overall {tot['ratio']:.3f}× (b − a × {tot['ratio']:.3f}), frames over "
                f"{100 * rules.get('excessMin', 0.002):g}% of a's total:", "",
            "| beyond | a | b | Δ | Δ of a's total | frame |", "|---|---|---|---|---|---|"]
    out += [f"| {'+' if r['excess'] > 0 else ''}{si(r['excess'])} | {si(r['a'])} | {si(r['b'])} | {si(r['b'] - r['a'])} | {pct(r['excess'])} | `{r['name']}` |"
            for r in t["excess"][:top]]
    return "\n".join(out) + "\n"


def write_collapsed(path, counter, factor=1.0):
    with open(path, "w") as f:
        for k, n in counter.items():
            f.write(f"{k} {profdiff.scaled(n, factor)}\n")


def render(jfrconv, out, event, fa, fb, la, lb, by_leaf=False, note="", k=None):
    """The four graphs (and the by-leaf diff) of two collapsed files, whose counts are per op × `k` (profdiff.per_op)."""
    graph = lambda title, *args: subprocess.run([jfrconv, "-J-Xmx8g", "--minwidth", "0.2", "--title", title, *args], capture_output=True)
    what = (profdiff.per_op_title(event, k) if k else event) + note
    graph(f"{what}: {la} → {lb}", "--diff", fa, fb, os.path.join(out, f"diff-{event}.html"))
    graph(f"{what}: {lb} → {la}", "--diff", fb, fa, os.path.join(out, f"diff-{event}-inverse.html"))
    graph(f"{what}: {la}", fa, os.path.join(out, f"a-{event}.html"))
    graph(f"{what}: {lb}", fb, os.path.join(out, f"b-{event}.html"))
    if by_leaf:
        subprocess.run([jfrconv, "-J-Xmx8g", "--minwidth", "0.05", "--reverse", "--title", f"{what} by leaf: {la} → {lb}",
                        "--diff", fa, fb, os.path.join(out, f"diff-{event}-byleaf.html")], capture_output=True)


def write_flips(out, event, A, B, la, lb, jits=None):
    """flips-<event>.json and its table appended to table-<event>.md (perflab.kinds)."""
    t = kinds.flips(A, B)
    if jits:
        t = kinds.with_jit(t, *jits)
    t.pop("_all", None)
    json.dump(t, open(os.path.join(out, f"flips-{event}.json"), "w"), indent=1)
    md = os.path.join(out, f"table-{event}.md")
    text = open(md).read().split("\n## frame-kind flips")[0] if os.path.exists(md) else ""  # this table again: replaced
    with open(md, "w") as f:
        f.write(text.rstrip("\n") + "\n\n" + kinds.table_md(event, t, la, lb))
    return t


def scratch(out, name, event):
    """A collapsed file of its own for jfrconv's input: two diffs of one pair may run at once."""
    fd, f = tempfile.mkstemp(dir=out, prefix=f".{name}-{event}-", suffix=".collapsed")
    os.close(fd)
    return f


def raw_diff(out, event, A, B, la, lb, jfrconv, top, jits=None):
    """profdiff's output for two cells' cached stacks."""
    tmp = []
    fa, fb, k = profdiff.per_op(A.ops, B.ops)
    for st, name, factor in ((A, "a", fa), (B, "b", fb)):
        f = scratch(out, name, event)
        with open(f, "w") as w:
            for s, n in st.stacks:
                w.write(";".join(st.frames[i] for i in s) + f" {profdiff.scaled(n, factor)}\n")
        tmp.append(f)
    try:
        render(jfrconv, out, event, *tmp, la, lb, k=k)
        selfs = []
        for st in (A, B):
            c = collections.Counter()
            for s, n in st.stacks:
                c[profdiff.FRAME_KIND.sub("", st.frames[s[-1]])] += n
            selfs.append(c)
        t = summarize({}, selfs[0], selfs[1], {}, {}, A.total, B.total, A.ops, B.ops)
        md = table_md(event, t, la, lb, {}, top).replace(" (benchmark threads, curated)", " (benchmark threads)")
        open(os.path.join(out, f"table-{event}.md"), "w").write(md.split("\ninclusive ")[0])
        write_flips(out, event, A, B, la, lb, jits)
    finally:
        for f in tmp:
            if os.path.exists(f):
                os.unlink(f)


def curated_diff(out, event, A, B, la, lb, jfrconv, rules, jits=None, precise=None, srcs=None):
    """The curated graphs, table-<event>.md and tables-<event>.json of two cells' cached stacks (with lines, for a
    `leaf` rule); the tables. `precise`: each build's share of samples with a precise PC, for the table; `srcs`: each
    build's perflab.sources.Source, for the text of a line."""
    c = Curator(rules)
    ba, outside_a = c.base(A)
    bb, outside_b = c.base(B)
    ca, cb = c.aligned(c.shaped(ba), c.shaped(bb))
    tmp = [scratch(out, n, event) for n in ("a", "b")]
    fa, fb, k = profdiff.per_op(A.ops, B.ops)
    write_collapsed(tmp[0], ca, fa)
    write_collapsed(tmp[1], cb, fb)
    try:
        render(jfrconv, out, event, *tmp, la, lb, rules.get("byLeaf"), " (curated)", k)
    finally:
        for f in tmp:
            if os.path.exists(f):
                os.unlink(f)
    own_a, incl_a = c.tables(ba)
    own_b, incl_b = c.tables(bb)
    t = summarize(rules, own_a, own_b, incl_a, incl_b, sum(n for _, n in ba), sum(n for _, n in bb), A.ops, B.ops)
    t["outsideAnchor"] = {"a": outside_a / A.ops, "b": outside_b / B.ops} if rules.get("anchor") else None
    t["oneSidedFrames"] = c.one_sided
    t["leaf"] = c.leaf
    t["precise"] = precise
    if t.get("lines") and c.leaf == "line" and srcs:
        add_text(t["lines"], srcs)
    open(os.path.join(out, f"table-{event}.md"), "w").write(table_md(event, t, la, lb, rules, rules.get("top", 25)))
    json.dump(t, open(os.path.join(out, f"tables-{event}.json"), "w"), indent=1)
    if c.kinds:
        write_flips(out, event, *((stacks.without_lines(A), stacks.without_lines(B)) if c.leaf else (A, B)), la, lb, jits)
        template = os.path.join(out, f"a-{event}.html")  # jfrconv's, just rendered: the viewer of the graphs beside them
        try:
            viewer = open(template).read()
            flamegraph.split(viewer)
        except (OSError, flamegraph.TemplateError) as e:
            print(f"{event}: no toggle graphs ({template}: {e})", file=sys.stderr)
            viewer = None
        if viewer:
            for by_leaf in (False, True):
                sfx = "-byleaf" if by_leaf else ""
                kinds.toggle_graphs(viewer, os.path.join(out, f"toggle-a-{event}{sfx}.html"),
                                    os.path.join(out, f"toggle-b-{event}{sfx}.html"), event, la, lb,
                                    kinds.tree(ca, cb, A.ops, B.ops, by_leaf), by_leaf)
                # the first toggle page's name, handed out before the pairs: to the pair's widget on the compare page
                compare.redirect(os.path.join(out, f"toggle-{event}{sfx}.html"), f"compare.html#{compare.pair_id(event, by_leaf)}")
    return t


def banner(rules):
    """The rules, in a sentence, for the page."""
    parts = ["names keep their compilation suffixes (frames by kind)" if rules.get("kinds") else "names without compilation suffixes", "dropped: " + ", ".join(DROP + as_list(rules.get("drop")))]
    if rules.get("anchor"):
        parts.append(f"stacks cut above {rules['anchor']}")
    if rules.get("transparent"):
        parts.append("transparent (their events their caller's, as the leaf too): " + ", ".join(as_list(rules["transparent"])))
    parts.append("folded into their caller (not as the leaf): " + ", ".join(FOLD + as_list(rules.get("fold"))))
    if rules.get("recursion", True):
        parts.append("recursion collapsed to each method's outermost frame")
    if rules.get("align", True):
        parts.append("frames above the leaf in only one build dropped")
    if rules.get("leaf"):
        parts.append(f"the leaf by {rules['leaf']} (callers by method)")
    if rules.get("owner"):
        parts.append(f"tables by owner {', '.join(as_list(rules['owner']))}"
                     + (f" (skipping {', '.join(as_list(rules['ownerSkip']))})" if rules.get("ownerSkip") else ""))
    return "Curated: " + "; ".join(parts) + "."


# ---- the command

def cell_for(d, corpus, variant, rnd=None):
    cells = sorted((c for c in glob.glob(os.path.join(d, corpus, variant, "*")) if os.path.basename(c).isdigit()),
                   key=lambda c: int(os.path.basename(c)))
    ok = [c for c in cells if glob.glob(os.path.join(c, "**", "*.jfr"), recursive=True)]
    if rnd is not None:
        ok = [c for c in ok if os.path.basename(c) == str(rnd)]
    return ok


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab ab diff", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--corpus")
    ap.add_argument("--round", type=int, help="the round of both cells (default: the last both have a recording of)")
    ap.add_argument("--event", action="append", help="default: every event of the recording")
    ap.add_argument("--curate", help="a preset of [diff] presets, or JSON hints")
    ap.add_argument("--raw", action="store_true", help="the raw diff only")
    ap.add_argument("--no-light", action="store_true", help="without the light diff (the `light` preset) beside the curated one")
    ap.add_argument("--by-leaf", action="store_true", help="also the leaf-rooted differential graph")
    ap.add_argument("--force", action="store_true", help="render the raw diff again even when it is there")
    ap.add_argument("--cross-testbed", action="store_true", help="compare cells of two testbeds (machines) anyway")
    ap.add_argument("--leaf", choices=sorted(stacks.LEAVES), help="the leaf frame by line or bytecode index (the callers by method)")
    x = ap.parse_args(argv)
    path = x.spec if os.path.isfile(x.spec) else os.path.join(config.get().campaigns, x.spec, "spec.json")
    if not os.path.isfile(path):
        sys.exit(f"{x.spec}: neither a spec file nor a campaign in {config.get().campaigns}")
    spec = json.load(open(path))
    d = os.path.join(config.get().campaigns, spec["name"])
    corpora = list(spec.get("corpora") or {}) or sorted(os.path.basename(c) for c in glob.glob(os.path.join(d, "*")) if os.path.isdir(c))
    corpus = x.corpus or corpora[0]
    rounds = [{os.path.basename(c): c for c in cell_for(d, corpus, v, x.round)} for v in (x.a, x.b)]
    common = sorted(set(rounds[0]) & set(rounds[1]), key=int)
    if not common:
        sys.exit(f"{spec['name']}: no round of {corpus} with a recording of both {x.a} and {x.b}")
    ca, cb = rounds[0][common[-1]], rounds[1][common[-1]]
    from . import testbed
    testbed.same(ca, cb, x.cross_testbed)
    jfrconv = jmh.jfrconv(jmh.async_lib(spec.get("lib")))
    events = x.event or [label.removeprefix("hw-") for label, _ in regraph.events_of(ca)]
    stem = f"diff-{corpus + '-' if len(corpora) > 1 else ''}{x.a}-{x.b}"
    la, lb = profdiff.label(ca), profdiff.label(cb)
    rules, name = rules_for(spec, x.curate)
    if x.by_leaf:
        rules["byLeaf"] = True
    if x.leaf:
        rules["leaf"] = x.leaf
    leaf = rules.get("leaf")
    if leaf and leaf not in stacks.LEAVES:
        sys.exit(f"leaf {leaf}: not one of {', '.join(stacks.LEAVES)}")
    pair = {"a": x.a, "b": x.b, "corpus": corpus, "cells": [os.path.relpath(c, d) for c in (ca, cb)]}
    raw_out = os.path.join(d, stem)
    jits = None
    from . import jfrevents
    if all(jfrevents.jit_recordings(c) for c in (ca, cb)):
        try:
            jits = (jfrevents.jit(ca), jfrevents.jit(cb))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"JIT recordings not read: {e}", file=sys.stderr)
    loaded, lined, precise = {}, {}, {}
    for e in events:
        if leaf:
            lined[e] = (stacks.load(ca, e, jfrconv, leaf), stacks.load(cb, e, jfrconv, leaf))
            loaded[e] = tuple(stacks.without_lines(s) for s in lined[e])
        else:
            loaded[e] = (stacks.load(ca, e, jfrconv), stacks.load(cb, e, jfrconv))
        print(f"{e}: {len(loaded[e][0].stacks):,} and {len(loaded[e][1].stacks):,} stacks", flush=True)
    raw_done = (not x.force and os.path.exists(os.path.join(raw_out, "pair.json"))
                and json.load(open(os.path.join(raw_out, "pair.json"))).get("cells") == pair["cells"]
                and all(os.path.exists(os.path.join(raw_out, f"diff-{e}.html")) for e in events))
    if not raw_done:
        os.makedirs(raw_out, exist_ok=True)
        for e in events:
            raw_diff(raw_out, e, *loaded[e], la, lb, jfrconv, rules.get("top", 25), jits)
        json.dump(pair, open(os.path.join(raw_out, "pair.json"), "w"), indent=2)
    else:
        for e in events:  # a raw diff from before the flips table
            if not os.path.exists(os.path.join(raw_out, f"flips-{e}.json")):
                write_flips(raw_out, e, *loaded[e], la, lb, jits)
    compare.write(raw_out, la, lb)  # again for a diff already there: the page's keys and links are its own
    print(f"raw: {os.path.join(raw_out, 'compare.html')}{' (there already)' if raw_done else ''}")
    if leaf:
        for side, c in (("a", ca), ("b", cb)):
            try:
                pc = jfrevents.precise(c)
            except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as ex:
                print(f"precise PCs not read: {ex}", file=sys.stderr)
                pc = {}
            for e in events:
                r = pc.get(e)
                precise.setdefault(e, {})[side] = r["precise"] / r["samples"] if r and r["samples"] else None
    srcs = (sources.of_variant(d, x.a), sources.of_variant(d, x.b)) if leaf == "line" else None
    curations = [] if x.raw else [(rules, name)]
    if not x.raw and not x.no_light and name != "light":
        light, _ = rules_for(spec, "light")
        light["leaf"] = leaf
        curations.append((light, "light"))
    for rules, name in curations:
        cur_out = os.path.join(d, f"{stem}-{name}{'-' + rules['leaf'] if rules.get('leaf') else ''}")
        os.makedirs(cur_out, exist_ok=True)
        for e in events:
            t = curated_diff(cur_out, e, *(lined if rules.get("leaf") else loaded)[e], la, lb, jfrconv, rules, jits, precise.get(e), srcs)
            tot = t["total"]
            print(f"{e} ({name}): {profdiff.si(tot['a'])} → {profdiff.si(tot['b'])} per op ({100 * (tot['ratio'] - 1):+.1f}%)")
            for g in t["groups"]:
                print(f"  {g['name']}: {'+' if g['delta'] > 0 else ''}{profdiff.si(g['delta'])}")
        json.dump({**pair, "curated": name, "rules": rules, "raw": os.path.basename(raw_out), "note": banner(rules)},
                  open(os.path.join(cur_out, "pair.json"), "w"), indent=2)
        compare.write(cur_out, la, lb, note=banner(rules))
        print(f"{name}: {os.path.join(cur_out, 'compare.html')}")
    from . import index
    try:
        index.rebuild(config.get().campaigns)
    except Exception as e:  # the index is a convenience
        print(f"index not rebuilt: {e}", file=sys.stderr)
    return 0
