"""A branch campaign's history (doc/branch-explore.md, decisions 3 and 4): its commits newest first, first-parent, with
one column per corpus, and a chart of the same data with commits on x. A campaign is a branch campaign when its
directory has the branch.json the runner writes (doc/branch-explore-PLAN.md has the contract); its variants are the
commits' short shas, its cells where every campaign's are, <campaign>/<corpus>/<variant>/<round>/result.json.

`branch_view` gathers what the page draws, `section` puts it on the campaign's card, and BRANCH_JS draws it: the
history table (numbers, dots on a shared per-column scale, or both), the chart (score left, a second metric right, each
commit's mean with its 99.9% CI over forks, its forks' means and every measurement iteration), and the comparison of two
selected rows. The view's state is in the page's URL (`?b.<campaign>=...`), so a view can be linked and survives the
index's refresh.

The unit of variation is the fork: fork-to-fork variance (JIT decisions, code layout) dominates, and a fork's
iterations are autocorrelated, so pooling iterations would make the interval far too narrow. Per commit, corpus and
metric, each fork of each round contributes the mean of its measurement iterations (`rawData` in result.json, the
score's and those secondary metrics that have one; a metric without it, its round's value). The commit's mean is
theirs, and its 99.9% CI is t(n-1)·sd/√n over its n forks. A commit with one fork has no spread of its own: it takes
the fork-to-fork relative sd pooled over the campaign's commits with two forks or more (same corpus and metric, each
weighted by its df), marked as pooled; with no such commit yet it has no interval.

A Δ is against the previous measured commit, and the comparison of two rows uses the same test (`metrics.welch`, and
`welch` in the page): Welch's t on the forks' means, Welch–Satterthwaite df, a pooled sd for a side of one fork. Δ% is
shown ± the half-width of its 99.9% CI and coloured only when significant at 99.9%.
"""
import datetime, glob, html, json, math, os

from . import metrics, ui

BRANCH_NAME = "branch.json"
esc = html.escape

# where a metric of `metrics.of` has per-iteration samples: the primary metric, or a secondary metric of result.json
RAW_SOURCE = {"score": None, "alloc": "gc.alloc.rate.norm", "cycles": "xctrace.CORE_ACTIVE_CYCLE", "instructions": "xctrace.INST_ALL"}


def raw_source(k):
    return RAW_SOURCE.get(k, f"xctrace.{k[3:]}" if k.startswith("ev:") and "/" not in k else False)


def raw_of(r, k, u):
    """The forks' measurement iterations of metric `k` in a JMH result, divided by `u` (units per op), [[x, ...] per fork]."""
    src = raw_source(k)
    if src is False:
        return []
    m = r["primaryMetric"] if src is None else r.get("secondaryMetrics", {}).get(src)
    raw = (m or {}).get("rawData") or []
    return [[x / u for x in fork if isinstance(x, (int, float)) and math.isfinite(x)] for fork in raw] if u else []


def fin(x):
    return x if x is not None and math.isfinite(x) else None


def fork_stats(m):
    """A cell's metric `m` (as `branch_view` has it) as `metrics.welch` takes it: (mean, sd, n forks, df)."""
    return m[0], m[1], m[4], m[5]


def sig(x, n=5):
    """`x` to `n` significant digits, for the raw samples on the page."""
    return float(f"{x:.{n}g}")


def load_cell(cell):
    """A cell's JMH result, "running" while its result.json is empty or partial, None before it has one."""
    f = os.path.join(cell, "result.json")
    if not os.path.exists(f):
        return None
    try:
        r = json.load(open(f))[0]
        r["primaryMetric"]["score"]
        return r
    except (OSError, ValueError, IndexError, KeyError, TypeError):
        return "running"


def date_shown(iso):
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%a %d %b %Y")
    except (TypeError, ValueError):
        return iso or ""


def branch_view(campaign_dir, rel_to=None):
    """What the page draws for a branch campaign, None when `campaign_dir` has no branch.json:

    {"commits": [newest first: {sha, short, v (variant), subject, author, date, shown (date), index, merged}],
     "corpora": [...], "metrics": [{k, h (heading), kind}], the score first,
     "cells": {corpus: {variant: {"state": "done" | "running", "rounds": n,
                                  "forks": n, "m": {k: [mean, sd of the forks' means, CI half-width, Δ against it
                                  means something, n forks, df, sd pooled]} (sd, CI and df None without a spread),
                                  "s": {k: [mean shown, CI shown]}, "raw": {k: [[x, ...] per fork, of every round]},
                                  "d": {k: [Δ%, half-width of its CI, verdict, a side pooled]},
                                  "prev": variant of the previous measured commit}}},
     "diffs": [{name, href}]}

    `rel_to` is the directory the page's links are relative to (default `campaign_dir`)."""
    bf = os.path.join(campaign_dir, BRANCH_NAME)
    if not os.path.exists(bf):
        return None
    from . import index
    branch = json.load(open(bf))
    try:
        spec = json.load(open(os.path.join(campaign_dir, "spec.json")))
    except (OSError, ValueError):
        spec = {}
    per_unit = spec.get("perUnit")
    commits = sorted(branch.get("commits", []), key=lambda c: c.get("index", 0))
    variants = [c.get("variant") or c["short"] for c in commits]
    on_disk = sorted(os.path.basename(d.rstrip("/")) for d in glob.glob(os.path.join(campaign_dir, "*/"))
                     if not os.path.basename(d.rstrip("/")).startswith(("diff-", ".")))
    named = list(spec.get("corpora") or [])
    corpora = [c for c in named] + [c for c in on_disk if c not in named and any(os.path.isdir(os.path.join(campaign_dir, c, v)) for v in variants)]

    cols, cells = {}, {}
    for corpus in corpora:
        per_v, units, prev = {}, {}, None
        for v in variants:
            rs, running = [], False
            for cell in sorted(glob.glob(os.path.join(campaign_dir, corpus, v, "*"))):
                if not (os.path.isdir(cell) and os.path.basename(cell).isdigit()):
                    continue
                r = load_cell(cell)
                if r == "running":
                    running = True
                elif r is not None:
                    rs.append((r, cell))
            if not rs:
                if running:
                    per_v[v] = {"state": "running"}
                continue
            of = [metrics.of(r, per_unit, metrics.cached_hw_events(cell)) for r, cell in rs]
            kinds, raw, us = {}, {}, {}
            for ms in of:
                for k, label, kind, main, _ in ms:
                    cols.setdefault(k, (k, label, kind, main))
                    kinds[k] = kind
            for k in kinds:
                forks = [f for (r, _) in rs for f in raw_of(r, k, metrics.units_per_op(r, per_unit) if per_unit else 1.0) if f]
                if forks:
                    raw[k] = [[sig(x) for x in f] for f in forks]
                # the unit of variation is the fork: the mean of its measurement iterations; a metric without them has
                # the round's value (JMH's mean over the round's forks)
                us[k] = [sum(f) / len(f) for f in forks] or [x for ms in of for kk, _, _, _, x in ms if kk == k and fin(x) is not None]
            units[v] = (us, kinds)
            per_v[v] = {"state": "done", "rounds": len(rs), "forks": max((len(u) for u in us.values()), default=0),
                        "m": {}, "s": {}, "raw": raw, "d": {}, "prev": prev}
            if running:
                per_v[v]["running"] = True
            prev = v
        # per metric, the fork-to-fork relative sd pooled over the commits with two forks or more, for those with one
        stat = {v: {k: (*metrics.stats(xs), len(xs)) for k, xs in us.items() if xs} for v, (us, _) in units.items()}
        keys = {k for st in stat.values() for k in st}
        pool = {k: metrics.pooled_rel_sd([(st[k][0], st[k][1], st[k][2] - 1) for st in stat.values() if k in st]) for k in keys}
        for v, (us, kinds) in units.items():
            x = per_v[v]
            for k, (mean, sd, n) in stat[v].items():
                kind, pooled, df = kinds[k], n < 2, n - 1
                if pooled:
                    r, df = pool[k]
                    sd = None if r is None else r * abs(mean)
                ci = None if sd is None else metrics.t999(df) * sd / n ** 0.5
                x["m"][k] = [fin(mean), fin(sd), fin(ci), metrics.delta_ok(mean, kind, per_unit), n, df if sd is not None else None, pooled and sd is not None]
                x["s"][k] = [metrics.fmt(kind, mean), "" if ci is None else ci_shown(kind, ci, mean)]
            if x["prev"]:
                pm = per_v[x["prev"]]["m"]
                for k, m in x["m"].items():
                    if k not in pm:
                        continue
                    d, half, _ = metrics.welch(fork_stats(pm[k]), fork_stats(m))
                    if d is not None:
                        x["d"][k] = [fin(d), fin(half), index.verdict(d, half, pm[k][3]), pm[k][6] or m[6]]
        if per_v:
            cells[corpus] = per_v
    corpora = [c for c in corpora if c in cells] + [c for c in named if c not in cells]
    rel_to = rel_to or campaign_dir
    # profdiff outputs in the campaign itself (made by hand): a pair when the name is exactly <a>-<b> of two commits
    forms = {f: v for v in variants for f in (v, v[:7])}
    diffs = []
    for f in sorted(glob.glob(os.path.join(campaign_dir, "diff-*", "compare.html"))):
        name = os.path.basename(os.path.dirname(f)).removeprefix("diff-")
        pair = [(forms[name[:i]], forms[name[i + 1:]]) for i, ch in enumerate(name) if ch == "-" and name[:i] in forms and name[i + 1:] in forms]
        diffs.append({"name": name, "href": os.path.relpath(f, rel_to), "a": pair[0][0] if pair else None, "b": pair[0][1] if pair else None})
    return {"commits": [{"sha": c["sha"], "short": c["short"], "v": v, "subject": c.get("subject", ""), "author": c.get("author", ""),
                         "date": c.get("date", ""), "shown": date_shown(c.get("date")), "index": c.get("index", i),
                         "merged": c.get("merged") or []}
                        for i, (c, v) in reversed(list(enumerate(zip(commits, variants))))],
            "corpora": corpora, "metrics": [{"k": k, "h": label, "kind": kind} for k, label, kind, _ in cols.values()],
            "cells": cells, "diffs": diffs, "range": branch.get("range", ""), "perUnit": per_unit,
            "profile": profiles(campaign_dir, variants, rel_to)}


PROFILE_SUFFIX = ".profile"  # the profile campaign beside a branch campaign (perflab.branchprofile)


def graph_links(cell, rel_to):
    """A profile cell's rendered flame graphs, [[event, kind, href], ...], as the index's cell rows link them."""
    from . import regraph
    jfr = (glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True) or [None])[0]
    events = regraph.events_of(cell)
    if not jfr and events:  # a published copy leaves the recording out: its first event's bench graph names it
        g = (glob.glob(os.path.join(cell, "**", f"*-{events[0][0]}.html"), recursive=True) or [None])[0]
        jfr = g and g[:-len(f"-{events[0][0]}.html")] + ".jfr"
    if not jfr:
        return []
    return [[label.removeprefix("hw-"), k, os.path.relpath(regraph.graph_path(jfr, label, k), rel_to)]
            for label, _ in events for k in regraph.kinds() if os.path.exists(regraph.graph_path(jfr, label, k))]


def profiles(campaign_dir, variants, rel_to):
    """The branch campaign's profiles, from <campaign>.profile beside it, None without one:

    {"campaign": its name, "corpora": [the corpora it profiles],
     "cells": {corpus: {variant: {"state": "done" | "running", "graphs": [[event, kind, href], ...]}}},
     "diffs": [{"a", "b" (variants), "corpus", "href" (compare.html), "events": [{"ev", "slots": [[view, href], ...]}]}]}

    A diff is one `perflab branch diff` wrote (its pair.json names the commits and the corpus), so the view matches it
    to a pair of rows exactly."""
    from . import compare, regraph
    pdir =os.path.normpath(campaign_dir) + PROFILE_SUFFIX
    if not os.path.isdir(pdir):
        return None
    try:
        spec = json.load(open(os.path.join(pdir, "spec.json")))
    except (OSError, ValueError):
        spec = {}
    cells = {}
    corpora = list(spec.get("corpora") or [])
    for d in sorted(glob.glob(os.path.join(pdir, "*/"))):
        corpus = os.path.basename(d.rstrip("/"))
        if corpus.startswith(("diff-", ".")):
            continue
        for v in variants:
            for cell in sorted(glob.glob(os.path.join(d, v, "*")), key=lambda c: (len(c), c)):
                if not (os.path.isdir(cell) and os.path.basename(cell).isdigit()):
                    continue
                r = load_cell(cell)
                if r == "running":
                    cells.setdefault(corpus, {}).setdefault(v, {"state": "running", "graphs": []})
                elif r is not None:
                    cells.setdefault(corpus, {})[v] = {"state": "done", "graphs": graph_links(cell, rel_to)}
                    break
        if corpus in cells and corpus not in corpora:
            corpora.append(corpus)
    diffs = []
    for pf in sorted(glob.glob(os.path.join(pdir, "diff-*", "pair.json"))):
        d = os.path.dirname(pf)
        try:
            pair = json.load(open(pf))
        except (OSError, ValueError):
            continue
        if not os.path.exists(os.path.join(d, "compare.html")):
            continue
        # in the profile's order of events (cpu before alloc), then any others
        order = [label.removeprefix("hw-") for label, _ in regraph.events_of(spec.get("profile") or "", bool(spec.get("kperf")))]
        events = sorted((os.path.basename(f)[len("diff-"):-len(".html")] for f in glob.glob(os.path.join(d, "diff-*.html"))
                         if not f.endswith("-inverse.html")), key=lambda e: (order.index(e) if e in order else len(order), e))
        diffs.append({"a": pair.get("a"), "b": pair.get("b"), "corpus": pair.get("corpus"),
                      "href": os.path.relpath(os.path.join(d, "compare.html"), rel_to),
                      "events": [{"ev": ev, "slots": [[view, os.path.relpath(os.path.join(d, name.format(event=ev)), rel_to)]
                                                      for view, _, name, _ in compare.SLOTS
                                                      if os.path.exists(os.path.join(d, name.format(event=ev)))]}
                                 for ev in events]})
    return {"campaign": os.path.basename(pdir), "corpora": corpora, "cells": cells, "diffs": diffs}


def ci_shown(kind, ci, mean):
    """A CI's half-width as its mean is shown: a score to the score's decimals."""
    return ui.num(ci, mean) if kind == "score" else metrics.fmt(kind, ci)


def section(campaign_dir, rel_to, corpus_param="corpus"):
    """The History section of a branch campaign's card, "" for any other campaign."""
    data = branch_view(campaign_dir, rel_to)
    if data is None:
        return ""
    name = os.path.basename(os.path.normpath(campaign_dir))
    data["corpusParam"] = corpus_param
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    n = len(data["commits"])
    measured = len({v for cs in data["cells"].values() for v, c in cs.items() if c["state"] == "done"})
    note = (f"{n} first-parent commits of <code>{esc(data['range'])}</code>, newest first; {measured} measured. "
            "Mean over forks ± 99.9% CI over forks; Δ against the previous measured commit")
    help_ = ui.help_popover(
        "<p style='margin-top:0'>A row per first-parent commit; a merge's <b>+n</b> lists the commits it brought in. Per corpus, the "
        "score as a number, as a dot on a scale shared down the column, or both, and a second metric beside it.</p>"
        "<p>The unit is the <b>fork</b>: each fork of each round counts once, as the mean of its measurement iterations (they vary "
        "far less within a fork than between forks, and are not independent). A value is the mean over forks ± a 99.9% confidence "
        "interval over forks. A commit with one fork has no spread of its own: † marks an interval from the fork-to-fork sd pooled "
        "over this corpus's commits with two forks or more; until there is one, it has none.</p>"
        "<p>Δ is against the previous (older) measured commit, ± its 99.9% CI (Welch's t over the forks' means), coloured only when "
        "significant at 99.9%. Comparing two rows uses the same test.</p>"
        "<p><b>Chart</b>: commits oldest to newest, gaps where a commit is unmeasured; error bars are the 99.9% CI over forks "
        "(lighter when pooled), dashes each fork's mean, the faint cloud every iteration. Tick two rows (or one, against the commit "
        "before it) to compare them. The view is kept in the "
        "page's URL.</p><p style='margin-bottom:0'><b>Profiles</b> are runs of their own (a profiler perturbs the score), in the "
        "campaign <i>&lt;name&gt;.profile</i> beside this one, from the same builds: <code>perflab branch profile</code>. A row's "
        "<b>profile</b> badge opens its flame graphs; comparing two rows shows their differential flame graphs (<code>perflab branch "
        "diff</code>), or offers to make them.</p>", right=True)
    return (f'<h3 class="sub">History <span class="k">{note}</span> {help_}</h3>'
            f'<div class="bh" data-campaign="{esc(name)}"><div class="bh-ctl"></div><div class="bh-chart"></div>'
            f'<div class="bh-table"></div><div class="bh-cmp"></div><script type="application/json">{blob}</script></div>')


CSS = """
.bh{margin:2px 0 10px} .bh-ctl{display:flex;flex-wrap:wrap;gap:4px 18px;margin:6px 0 4px;align-items:center}
.bh-ctl select{font:inherit;font-size:12px;padding:1px 4px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}
table.bh-t td{vertical-align:middle} table.bh-t th{vertical-align:bottom} table.bh-t th.cg{text-align:center;color:var(--fg);border-bottom:1px solid var(--line2)}
table.bh-t td.gs,table.bh-t th.gs{border-left:1px solid var(--line2)}
table.bh-t td.cm,table.bh-t th.cm{position:sticky;left:0;z-index:1;background:var(--panel);white-space:normal;min-width:180px;max-width:360px}
.bh-cm{display:flex;gap:8px;align-items:flex-start} .bh-cm input{margin:3px 0 0}
.bh-c{min-width:0} .bh-subj{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px}
.bh-who{display:block;font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px}
.bh-mg{font:11px/15px inherit;border:1px solid var(--line);background:var(--panel);color:var(--link);border-radius:999px;padding:0 6px;margin-left:4px;cursor:pointer;vertical-align:1px}
table.bh-t tr.hl td{background:var(--line2)} table.bh-t tr.sel td{background:var(--link-bg)}
table.bh-t tr.bh-sub td{padding-top:0;border-bottom:1px solid var(--line2)} table.bh-t tr.has-sub td{border-bottom:0}
.bh-sub ul{margin:0;padding:0 0 0 26px;list-style:none;font-size:12px} .bh-sub li{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:420px}
.bh-v{display:inline-flex;align-items:center;gap:8px;justify-content:flex-end} .bh-v .pm{white-space:nowrap}
.bh-pend{color:var(--muted);font-size:11.5px}
svg.bh-dot{display:block;overflow:visible} svg.bh-dot .bl{stroke:var(--line)} svg.bh-dot .wh{stroke:var(--muted);stroke-width:1.2}
svg.bh-dot .wh.pl{opacity:.45;stroke-dasharray:2 1.5} svg.bh-dot circle{fill:var(--fg)} svg.bh-dot circle.better{fill:var(--ok)} svg.bh-dot circle.worse{fill:var(--bad)}
.bh-chart figure{margin:4px 0 8px} .bh-leg{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:12px;color:var(--muted);margin:0 0 2px}
.bh-leg i{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--link);margin-right:4px;vertical-align:-1px}
.bh-leg i.s2{background:var(--brand);border-radius:1px;transform:rotate(45deg) scale(.85)}
svg.bh-g{width:100%;height:auto;display:block;overflow:visible;user-select:none} svg.bh-g text{font-size:11px;fill:var(--muted)}
svg.bh-g .ax{stroke:var(--line)} svg.bh-g .gl{stroke:var(--line2)} svg.bh-g .hit{fill:transparent;cursor:pointer}
svg.bh-g .band{fill:transparent} svg.bh-g .band.sel{fill:var(--link-bg)} svg.bh-g .band.hl{fill:var(--line2)}
svg.bh-g .c1{fill:var(--link);opacity:.28} svg.bh-g .c2{fill:var(--brand);opacity:.28}
svg.bh-g .e1{stroke:var(--link);stroke-width:1.6} svg.bh-g .e2{stroke:var(--brand);stroke-width:1.6} svg.bh-g .pl{opacity:.45;stroke-dasharray:3 2}
svg.bh-g .f1{stroke:var(--link);stroke-width:1.3;opacity:.75} svg.bh-g .f2{stroke:var(--brand);stroke-width:1.3;opacity:.75}
svg.bh-g .p1{fill:var(--link);stroke:var(--panel);stroke-width:1.2} svg.bh-g .p2{fill:var(--brand);stroke:var(--panel);stroke-width:1.2}
svg.bh-g .l1{fill:none;stroke:var(--link);stroke-width:1;opacity:.6} svg.bh-g .l2{fill:none;stroke:var(--brand);stroke-width:1;opacity:.6;stroke-dasharray:3 2}
svg.bh-g text.un{opacity:.45} svg.bh-g text.yl{font-size:10.5px}
.bh-tip{font-size:12px;min-height:1.5em;margin:2px 0 0;overflow-wrap:anywhere}
.bh-cmp{margin:8px 0 0} .bh-cmp:empty{display:none} .bh-ph{display:flex;flex-wrap:wrap;gap:2px 10px;align-items:baseline;margin:0 0 2px}
.bh-cmp h4{margin:0;font-size:12.5px} .bh-cmp table.t td{text-align:right} .bh-cmp table.t td:first-child,.bh-cmp table.t th:first-child{text-align:left}
.bh-cmp .ab{display:block;font-size:11px;color:var(--muted)}
.bh-pb{font:11px/15px inherit;border:1px solid var(--line);background:var(--panel);color:var(--brand);border-radius:999px;padding:0 6px;margin-left:4px;vertical-align:1px}
a.bh-pb:hover{text-decoration:none;border-color:var(--brand)} .bh-pb.run{color:var(--muted)}
.bh-pd{margin:8px 0 0} .bh-pd .diffs{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;margin:2px 0}
.bh-pd .diffs>.k{min-width:60px} .bh-ev{font-weight:600;font-size:12px;margin-left:6px}
.bh-pd a.btn.dd{color:var(--brand)} .bh-act{margin:4px 0;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center}
.bh-cmd{background:var(--line2);border-radius:4px;padding:1px 6px;overflow-wrap:anywhere}
@media (max-width:700px){table.bh-t td.cm,table.bh-t th.cm{min-width:150px;max-width:170px} .bh-subj,.bh-who{max-width:130px}}
"""

# `metrics.t999` and `metrics.welch` for the page, on a cell's metric as `branch_view` has it: [mean, sd, CI, Δ ok,
# n forks, df, pooled]; welch(x, y) is [Δ% of y against x, half-width of its 99.9% CI, verdict, a side pooled] or null
STATS_JS = r"""
const BH_STATS = (() => {
  const T999 = __T999__;
  function t999(df) {
    for (let i = 1; i < T999.length; i++) {
      const [d0, t0] = T999[i - 1], [d1, t1] = T999[i];
      if (d1 == null || df <= d1) {
        if (df <= d0) return t0;
        return t0 + (1 / d0 - 1 / df) / (1 / d0 - (d1 == null ? 0 : 1 / d1)) * (t1 - t0);
      }
    }
    return T999[T999.length - 1][1];
  }
  function welch(x, y) {
    if (!x || !y || x[0] == null || y[0] == null || !x[0]) return null;
    const d = 100 * (y[0] / x[0] - 1);
    let h = null;
    if (x[1] != null && y[1] != null) {
      const va = x[1] * x[1] / x[4], vb = y[1] * y[1] / y[4];
      if (va + vb === 0) h = 0;
      else {
        const df = (va + vb) ** 2 / ((va ? va * va / x[5] : 0) + (vb ? vb * vb / y[5] : 0));
        h = 100 * t999(df) * Math.sqrt(va + vb) / Math.abs(x[0]);
      }
    }
    const v = !x[3] ? 'na' : h == null || Math.abs(d) <= h || Math.abs(d) < 0.005 ? 'flat' : d > 0 ? 'worse' : 'better';
    return [d, h, v, !!(x[6] || y[6])];
  }
  return {t999, welch};
})();
""".replace("__T999__", json.dumps([[d if math.isfinite(d) else None, t] for d, t in metrics.T999]))

# draws each branch campaign's history (`section`) from its data (`branch_view`), in the state in the page's URL
JS = STATS_JS + r"""
const BH = (() => {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  const mem = {};  // per campaign, for this page only: the merges opened, the commit hovered, the jobs queued by pair
  const memOf = el => mem[el.dataset.campaign] = mem[el.dataset.campaign] || {open: new Set(), hover: null, jobs: {}};
  let filter = new Set();
  const key = n => 'b.' + n;
  const data = el => el._d || (el._d = JSON.parse(el.querySelector('script').textContent));
  // ?b.<campaign>=form:both;chart:0;c:<corpus>;m2:<metric>;sel:<variant>,<variant>
  function state(el) {
    const d = data(el), st = {form: 'both', chart: false, c: '', m2: '', sel: []};
    let raw = '';
    try { raw = new URLSearchParams(location.search).get(key(el.dataset.campaign)) || ''; } catch (e) {}
    for (const part of raw.split(';')) {
      const i = part.indexOf(':');
      if (i < 0) continue;
      const k = part.slice(0, i), v = part.slice(i + 1);
      if (k === 'form' && ['num', 'dot', 'both'].includes(v)) st.form = v;
      else if (k === 'chart') st.chart = v === '1';
      else if (k === 'c') st.c = v;
      else if (k === 'm2') st.m2 = v;
      else if (k === 'sel') st.sel = v.split(',').filter(Boolean);
    }
    if (!d.corpora.includes(st.c)) st.c = d.corpora[0] || '';
    const others = d.metrics.filter(m => m.k !== 'score');
    if (st.m2 !== 'none' && !others.some(m => m.k === st.m2))
      st.m2 = others.some(m => m.k === 'alloc') ? 'alloc' : others.length ? others[0].k : 'none';
    st.sel = st.sel.filter(v => d.commits.some(c => c.v === v)).slice(-2);
    return st;
  }
  function save(el, st) {
    try {
      const q = new URLSearchParams(location.search);
      q.set(key(el.dataset.campaign), `form:${st.form};chart:${st.chart ? 1 : 0};c:${st.c};m2:${st.m2};sel:${st.sel.join(',')}`);
      history.replaceState(history.state, '', location.pathname + '?' + q.toString() + location.hash);
    } catch (e) {}
  }
  const metric = (d, k) => d.metrics.find(m => m.k === k) || {k, h: k, kind: 'score'};
  const cellOf = (d, c, v) => (d.cells[c] || {})[v];
  const unitFix = s => String(s).replace('us/', 'µs/');
  const sha = (c, n) => `<code title="${esc(c.sha)}">${esc(c.short.slice(0, n || 10))}</code>`;
  // a tick's label: three or four significant digits, with the unit's scale for sizes and counts
  function tick(kind, x) {
    const a = Math.abs(x), p = y => +y.toPrecision(3);
    if (kind === 'alloc') return a >= 1e5 ? `${p(x / 1e6)}MB` : a >= 1e3 ? `${p(x / 1e3)}KB` : `${p(x)}B`;
    if (kind === 'count') return a >= 1e9 ? `${p(x / 1e9)}G` : a >= 1e6 ? `${p(x / 1e6)}M` : a >= 1e3 ? `${p(x / 1e3)}K` : `${p(x)}`;
    if (kind === 'pct') return `${p(x)}%`;
    return a >= 1e4 ? Math.round(x).toLocaleString('en') : `${+x.toPrecision(4)}`;
  }
  function step(span) { const p = Math.pow(10, Math.floor(Math.log10(span / 4))), r = span / 4 / p; return p * (r >= 5 ? 5 : r >= 2 ? 2 : 1); }
  const pct = (d, sp) => `${d >= 0 ? '+' : ''}${d.toFixed(2)}%` + (sp != null ? ` <span class="pm">± ${sp.toFixed(2)}</span>` : '');
  const TITLE = {flat: 'inconclusive: not significant at 99.9% (Welch’s t over forks)', worse: 'higher, significant at 99.9% (Welch’s t over forks)',
                 better: 'lower, significant at 99.9% (Welch’s t over forks)'};
  const POOLED = '† a commit with one fork: its spread is the fork-to-fork sd pooled over this corpus’s commits with two forks or more';
  function delta(x) {
    if (!x || x[0] == null) return '';
    if (x[2] === 'na') return '<span class="d na" title="the values are about zero: no percent change">–</span>';
    const t = x[1] == null ? '1 fork: no spread yet' : TITLE[x[2]] + '; ± the 99.9% CI of Δ' + (x[3] ? '. ' + POOLED : '');
    return `<span class="d ${x[2]}" title="${t}">${pct(x[0], x[1])}${x[1] != null && x[3] ? '†' : ''}</span>`;
  }
  // Δ of b against a, as `branchview.branch_view` computes the Δ column (`metrics.welch`)
  const pairDelta = (a, b, k) => BH_STATS.welch(a && a.m && a.m[k], b && b.m && b.m[k]);
  // the extent of a metric's mean ± CI (and with `withRaw` its samples) down a corpus's column
  function extent(d, c, k, withRaw) {
    let lo = Infinity, hi = -Infinity;
    for (const x of Object.values(d.cells[c] || {})) {
      const m = x.m && x.m[k];
      if (!m || m[0] == null) continue;
      const ys = [m[0] - (m[2] || 0), m[0] + (m[2] || 0)];
      if (withRaw) for (const f of (x.raw || {})[k] || []) ys.push(...f);
      for (const y of ys) { lo = Math.min(lo, y); hi = Math.max(hi, y); }
    }
    if (!isFinite(lo)) return null;
    if (hi - lo <= Math.abs(hi) * 1e-9) { const e = Math.abs(hi) * 0.01 || 1; lo -= e; hi += e; }
    const p = (hi - lo) * 0.06;
    return [lo - p, hi + p];
  }
  function dot(m, ext, verdict) {
    const W = 90, X = y => (3 + (y - ext[0]) / (ext[1] - ext[0]) * (W - 6)).toFixed(1);
    const ci = m[2] != null ? `<path class="wh${m[6] ? ' pl' : ''}" d="M${X(m[0] - m[2])} 7H${X(m[0] + m[2])}M${X(m[0] - m[2])} 4v6M${X(m[0] + m[2])} 4v6"/>` : '';
    return `<svg class="bh-dot" viewBox="0 0 ${W} 14" width="${W}" height="14" aria-hidden="true"><line class="bl" x1="0" x2="${W}" y1="7" y2="7"/>${ci}`
      + `<circle cx="${X(m[0])}" cy="7" r="3.2" class="${verdict || ''}"/></svg>`;
  }
  function value(d, st, c, v, k, exts) {
    const x = cellOf(d, c, v);
    if (!x) return '<span class="bh-pend">pending</span>';
    if (x.state === 'running') return '<span class="badge running">running</span>';
    const m = x.m[k], s = x.s[k];
    if (!m) return '';
    const dag = m[6] ? '†' : '';
    const n = st.form === 'dot' ? '' : `<span>${esc(s[0])}${s[1] ? ` <span class="pm">± ${esc(s[1])}${dag}</span>` : ''}</span>`;
    const g = st.form === 'num' || !exts[c + '|' + k] ? '' : dot(m, exts[c + '|' + k], (x.d[k] || [])[2]);
    const tip = `${esc(s[0])}${s[1] ? ' ± ' + esc(s[1]) + dag + ' (99.9% CI over forks)' : ''}; ${m[4]} fork${m[4] > 1 ? 's' : ''}, ${x.rounds} round${x.rounds > 1 ? 's' : ''}`
      + (m[1] == null ? '; 1 fork: no spread yet' : m[6] ? `. ${POOLED}: ${(100 * m[1] / m[0]).toFixed(2)}%` : `, sd of the forks’ means ${(100 * m[1] / m[0]).toFixed(2)}%`);
    return `<span class="bh-v" title="${tip}">${n}${g}</span>`;
  }
  // the corpora the filter bar picked, all when it picked none of these
  function corpora(d) {
    const cs = d.corpora.filter(c => !filter.size || filter.has(c));
    return cs.length ? cs : d.corpora;
  }
  // a commit's profile cells (in <campaign>.profile): a badge opening its flame graphs in the lightbox, every graph of
  // every profiled corpus in its group
  function profBadge(d, c) {
    const P = d.profile;
    if (!P) return '';
    const per = P.corpora.map(cp => [cp, (P.cells[cp] || {})[c.v]]).filter(x => x[1]);
    if (!per.length) return '';
    const gs = per.flatMap(([cp, x]) => x.graphs.map(g => [per.length > 1 ? `${cp} · ${g[0]}` : g[0], g[1], g[2]]));
    if (!gs.length)
      return per.some(x => x[1].state === 'running') ? ' <span class="bh-pb run" title="its profile is running">profiling</span>'
        : ' <span class="bh-pb" title="profiled; its flame graphs are not rendered yet">profiled</span>';
    const tip = `flame graphs of its profile${per.length > 1 ? 's' : ''} (${esc(P.campaign)}: ${per.map(x => esc(x[0])).join(', ')})`;
    return ` <span class="bh-pf" data-lb-group="${esc(P.campaign)} · ${esc(c.short.slice(0, 7))}">`
      + gs.map((g, i) => `<a class="bh-pb"${i ? ' hidden' : ''} href="${esc(g[2])}" data-lb="${esc(g[0])}|${esc(g[1])}" title="${tip}">profile</a>`).join('')
      + '</span>';
  }
  function drawTable(el, d, st) {
    const cs = corpora(d), m2 = st.m2 !== 'none' ? metric(d, st.m2) : null, m1 = metric(d, 'score');
    const exts = {};
    for (const c of cs) for (const m of [m1, m2]) if (m) exts[c + '|' + m.k] = extent(d, c, m.k, false);
    const per = m2 ? 4 : 2, open = memOf(el).open;
    let h = '<div class="scroll"><table class="t bh-t"><tr><th class="cm" rowspan="2">commit</th>'
      + cs.map(c => `<th class="cg gs" colspan="${per}">${esc(c)}</th>`).join('') + '</tr><tr>'
      + cs.map(() => `<th class="n gs">${esc(unitFix(m1.h))}</th><th>Δ</th>` + (m2 ? `<th class="n">${esc(unitFix(m2.h))}</th><th>Δ</th>` : '')).join('') + '</tr>';
    for (const c of d.commits) {
      const sel = st.sel.includes(c.v), merged = c.merged.length, opened = merged && open.has(c.v);
      h += `<tr data-v="${esc(c.v)}" class="${sel ? 'sel' : ''}${opened ? ' has-sub' : ''}"><td class="cm"><div class="bh-cm">`
        + `<input type="checkbox" data-bsel="${esc(c.v)}"${sel ? ' checked' : ''} aria-label="compare ${esc(c.short)}">`
        + `<span class="bh-c"><span class="bh-subj" title="${esc(c.subject)}">${sha(c, 7)} ${esc(c.subject)}</span>`
        + `<span class="bh-who" title="${esc(c.date)}">${esc(c.author)} · ${esc(c.shown)}`
        + (merged ? `<button class="bh-mg" data-bmerge="${esc(c.v)}" aria-expanded="${!!opened}" title="a merge of ${merged} commit${merged > 1 ? 's' : ''}: list them">+${merged}</button>` : '')
        + profBadge(d, c) + '</span></span></div></td>';
      for (const cp of cs) {
        const x = cellOf(d, cp, c.v), dd = x && x.d || {};
        h += `<td class="n gs">${value(d, st, cp, c.v, 'score', exts)}</td><td>${delta(dd.score)}</td>`;
        if (m2) h += `<td class="n">${x && x.state === 'done' ? value(d, st, cp, c.v, m2.k, exts) : ''}</td><td>${delta(dd[m2.k])}</td>`;
      }
      h += '</tr>';
      if (opened)
        h += `<tr class="bh-sub${sel ? ' sel' : ''}" data-v="${esc(c.v)}"><td class="cm"><ul>`
          + c.merged.map(m => `<li title="${esc(m.subject)}">${sha({sha: m.sha, short: m.sha}, 7)} ${esc(m.subject)}</li>`).join('')
          + `</ul></td><td colspan="${cs.length * per}"></td></tr>`;
    }
    el.querySelector('.bh-table').innerHTML = h + '</table></div>';
  }
  function drawChart(el, d, st) {
    const box = el.querySelector('.bh-chart');
    if (!st.chart) { box.innerHTML = ''; return; }
    const c = st.c, cells = d.cells[c] || {}, order = [...d.commits].reverse(), N = order.length;
    const m1 = metric(d, 'score'), m2 = st.m2 !== 'none' ? metric(d, st.m2) : null;
    const W = Math.max(300, Math.round(el.clientWidth || 700)), H = 250, L = 54, R = m2 ? 58 : 14, T = 8, B = 30;
    const band = (W - L - R) / Math.max(1, N), X = i => L + (i + 0.5) * band;
    const e1 = extent(d, c, 'score', true), e2 = m2 && extent(d, c, m2.k, true);
    const Y = e => y => T + (H - T - B) * (1 - (y - e[0]) / (e[1] - e[0]));
    const off = e2 ? band * 0.17 : 0, spread = Math.min(band * (e2 ? 0.2 : 0.4), 26);
    const jit = (i, j) => { const s = Math.sin(i * 12.9898 + j * 78.233) * 43758.5453; return s - Math.floor(s) - 0.5; };
    const f1 = x => x.toFixed(1);
    let g = '', bands = '', hits = '', xl = '';
    const lines = ['', ''];
    const every = Math.max(1, Math.ceil(56 / band));
    order.forEach((cm, i) => {
      bands += `<rect class="band${st.sel.includes(cm.v) ? ' sel' : ''}" data-bband="${esc(cm.v)}" x="${f1(L + i * band)}" y="${T}" width="${f1(band)}" height="${H - T - B}"/>`;
      hits += `<rect class="hit" data-bhv="${esc(cm.v)}" x="${f1(L + i * band)}" y="${T}" width="${f1(band)}" height="${H - T}"/>`;
      const x = cells[cm.v];
      if ((N - 1 - i) % every === 0)
        xl += `<text class="${x && x.state === 'done' ? '' : 'un'}" x="${f1(X(i))}" y="${H - B + 14}" text-anchor="middle">${esc(cm.short.slice(0, 7))}</text>`;
    });
    [[m1, e1, -off, 1], [m2, e2, off, 2]].forEach(([m, e, dx, n]) => {
      if (!m || !e) return;
      const y = Y(e);
      let prev = null;
      order.forEach((cm, i) => {
        const x = cells[cm.v], v = x && x.state === 'done' && x.m[m.k];
        if (!v || v[0] == null) { prev = null; return; }
        const cx = X(i) + dx;
        let j = 0;
        const forks = (x.raw || {})[m.k] || [];
        for (const f of forks) for (const s of f) g += `<circle class="c${n}" cx="${f1(cx + jit(i * 7 + n, j++) * spread)}" cy="${f1(y(s))}" r="1.7"/>`;
        // each fork's mean, a short dash: the unit the interval is over
        for (const f of forks) if (f.length) { const fy = f1(y(f.reduce((p, s) => p + s, 0) / f.length)); g += `<path class="f${n}" d="M${f1(cx - spread * 0.5)} ${fy}h${f1(spread)}"/>`; }
        if (v[2] != null) g += `<path class="e${n}${v[6] ? ' pl' : ''}" d="M${f1(cx)} ${f1(y(v[0] - v[2]))}V${f1(y(v[0] + v[2]))}M${f1(cx - 4)} ${f1(y(v[0] - v[2]))}h8M${f1(cx - 4)} ${f1(y(v[0] + v[2]))}h8"/>`;
        g += n === 1 ? `<circle class="p1" cx="${f1(cx)}" cy="${f1(y(v[0]))}" r="4"/>`
          : `<rect class="p2" x="${f1(cx - 3.5)}" y="${f1(y(v[0]) - 3.5)}" width="7" height="7" transform="rotate(45 ${f1(cx)} ${f1(y(v[0]))})"/>`;
        // the means joined only between neighbours: an unmeasured commit is a gap
        if (prev) lines[n - 1] += `M${f1(prev[0])} ${f1(prev[1])}L${f1(cx)} ${f1(y(v[0]))}`;
        prev = [cx, y(v[0])];
      });
    });
    let ax = `<line class="ax" x1="${L}" x2="${L}" y1="${T}" y2="${H - B}"/><line class="ax" x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}"/>`;
    if (e1) {
      const y = Y(e1), s = step(e1[1] - e1[0]);
      for (let t = Math.ceil(e1[0] / s) * s; t <= e1[1]; t += s)
        ax += `<line class="gl" x1="${L}" x2="${W - R}" y1="${f1(y(t))}" y2="${f1(y(t))}"/><text class="yl" x="${L - 5}" y="${f1(y(t) + 3.5)}" text-anchor="end">${tick(m1.kind, t)}</text>`;
    }
    if (e2) {
      const y = Y(e2), s = step(e2[1] - e2[0]);
      ax += `<line class="ax" x1="${W - R}" x2="${W - R}" y1="${T}" y2="${H - B}"/>`;
      for (let t = Math.ceil(e2[0] / s) * s; t <= e2[1]; t += s)
        ax += `<text class="yl" x="${W - R + 5}" y="${f1(y(t) + 3.5)}">${tick(m2.kind, t)}</text>`;
    }
    const empty = !e1 && !e2 ? `<text x="${(L + W - R) / 2}" y="${H / 2}" text-anchor="middle">nothing measured on ${esc(c)} yet</text>` : '';
    const pick = d.corpora.length > 1 ? `<div class="bh-ctl"><span class="fg"><span class="fl">${esc(d.corpusParam || 'corpus')}</span>`
      + d.corpora.map(x => `<button class="chip" data-bc="${esc(x)}" aria-pressed="${x === c}">${esc(x)}</button>`).join('') + '</span></div>' : '';
    box.innerHTML = `<figure>${pick}<div class="bh-leg"><span><i></i>${esc(unitFix(m1.h))} (left)</span>`
      + (m2 ? `<span><i class="s2"></i>${esc(unitFix(m2.h))} (right)</span>` : '')
      + '<span>oldest → newest · error bars: 99.9% CI over forks (lighter, †: one fork, a pooled spread) · dashes: each fork’s mean · faint dots: every iteration</span></div>'
      + `<svg class="bh-g" viewBox="0 0 ${W} ${H}">${bands}${ax}<path class="l1" d="${lines[0]}"/><path class="l2" d="${lines[1]}"/>${g}${xl}${empty}${hits}</svg>`
      + '<p class="bh-tip k">Hover a commit to see its numbers; click to select it.</p></figure>';
  }
  function tipText(d, st, v) {
    const cm = d.commits.find(c => c.v === v), x = cellOf(d, st.c, v);
    if (!cm) return '';
    const val = k => { const s = x && x.state === 'done' && x.s[k]; return s ? `${esc(s[0])}${s[1] ? ' ± ' + esc(s[1]) + (x.m[k][6] ? '†' : '') : ''}` : ''; };
    const m2 = st.m2 !== 'none' ? metric(d, st.m2) : null;
    const nums = !x ? 'pending' : x.state === 'running' ? 'running'
      : `${val('score')} ${esc(unitFix(metric(d, 'score').h))} ${delta(x.d.score)}`
        + (m2 && val(m2.k) ? ` · ${val(m2.k)} ${esc(unitFix(m2.h))} ${delta(x.d[m2.k])}` : '');
    return `${sha(cm)} ${esc(cm.subject)} · <b>${esc(st.c)}</b>: ${nums}`;
  }
  function drawCompare(el, d, st) {
    const box = el.querySelector('.bh-cmp');
    if (!st.sel.length) { box.innerHTML = ''; return; }
    const byV = v => d.commits.find(c => c.v === v);
    const picked = st.sel.map(byV).sort((a, b) => a.index - b.index);
    const one = picked.length === 1, b = picked[picked.length - 1];
    let cs = corpora(d);
    // one row: against the commit measured before it on each corpus (the Δ column); two: the older against the newer
    const base = c => one ? (cellOf(d, c, b.v) || {}).prev : picked[0].v;
    const head = one ? `<h4>${sha(b)} against the commit measured before it</h4><span class="k">tick a second row to compare any two</span>`
      : `<h4>${sha(picked[0])} → ${sha(b)}</h4><span class="k">${esc(picked[0].subject)} → ${esc(b.subject)}</span>`;
    // the corpora both have results on
    cs = cs.filter(c => d.metrics.some(m => pairDelta(cellOf(d, c, base(c)), cellOf(d, c, b.v), m.k)));
    let rows = '';
    for (const m of d.metrics) {
      const tds = cs.map(c => {
        const a = cellOf(d, c, base(c)), y = cellOf(d, c, b.v), x = pairDelta(a, y, m.k);
        return x ? `<td>${delta(x)}<span class="ab">${esc(a.s[m.k][0])} → ${esc(y.s[m.k][0])}</span></td>` : '<td></td>';
      });
      if (tds.some(t => t !== '<td></td>')) rows += `<tr><td>${esc(unitFix(m.h))}</td>${tds.join('')}</tr>`;
    }
    let h = `<div class="bh-ph">${head}<button class="chip" data-bclear="1">clear</button></div>`;
    h += rows ? '<div class="scroll"><table class="t"><tr><th>metric</th>'
      + cs.map(c => `<th class="n">${esc(c)}${one && base(c) ? ` <span class="k">vs ${sha(byV(base(c)), 7)}</span>` : ''}</th>`).join('') + `</tr>${rows}</table></div>`
      : '<p class="k">They have no results on the same corpus yet.</p>';
    // the profiles: of the two rows, or of the one and the commit before it in history
    const a = one ? d.commits.find(c => c.index === b.index - 1) : picked[0];
    if (a) h += profilePanel(el, d, a, b);
    box.innerHTML = h;
  }
  const same = (x, a, b) => (x.a === a.v && x.b === b.v) || (x.a === b.v && x.b === a.v);
  const shq = s => /^[\w@%+=:,./-]+$/.test(s) ? s : `'${String(s).replace(/'/g, `'\\''`)}'`;
  // profdiff of commits a (older) and b per profiled corpus: each event's graphs of a and b and the differential ones both
  // ways, opening in the lightbox; for what is missing, the command that makes it, queued on the server when the page is
  // the server's (it carries the server's token), else to copy
  function profilePanel(el, d, a, b) {
    const P = d.profile, name = el.dataset.campaign, A = sha(a, 7), B = sha(b, 7);
    let h = `<div class="bh-pd"><div class="bh-ph"><h4>Profiles</h4><span class="k">${A} → ${B}, from ${esc(P ? P.campaign : name + '.profile')}`
      + ' (a profiler perturbs the score, so these are runs of their own)</span></div>';
    const found = P ? P.diffs.filter(x => same(x, a, b)) : [];
    for (const x of found) {
      const label = v => v === 'diff' ? 'DIFF' : v === 'inverse' ? 'DIFF⁻¹' : (v === 'a') === (x.a === a.v) ? a.short.slice(0, 7) : b.short.slice(0, 7);
      const title = v => v === 'diff' ? `${x.a.slice(0, 7)} → ${x.b.slice(0, 7)}: red grew, blue shrank` : v === 'inverse' ? `${x.b.slice(0, 7)} → ${x.a.slice(0, 7)}` : 'its own flame graph';
      h += `<div class="diffs" data-lb-group="${esc(name)} · ${esc(x.corpus)} · ${esc(a.short.slice(0, 7))} → ${esc(b.short.slice(0, 7))}">`
        + `<span class="k">${esc(x.corpus)}</span>`
        + x.events.map(e => `<span class="bh-ev">${esc(e.ev)}</span>` + ['a', 'diff', 'inverse', 'b'].map(v => e.slots.find(s => s[0] === v)).filter(Boolean)
          .map(s => `<a class="btn${s[0] === 'diff' || s[0] === 'inverse' ? ' dd' : ''}" href="${esc(s[1])}" data-lb="${esc(e.ev)}|${esc(label(s[0]))}" title="${esc(title(s[0]))}">${esc(label(s[0]))}</a>`).join('')).join('')
        + `<a class="btn" href="${esc(x.href)}" data-lb="all|tabs" title="every event's four graphs as tabs over one frame (1–4, [ ])">tabs</a></div>`;
    }
    // a profdiff output made by hand in the campaign itself, diff-<a>-<b>
    const legacy = d.diffs.filter(x => x.a && same(x, a, b));
    if (legacy.length)
      h += `<div class="diffs" data-lb-group="${esc(name)} · differential flame graphs"><span class="k">by hand</span>`
        + legacy.map(x => `<a class="btn" href="${esc(x.href)}" data-lb="diff|${esc(x.name)}">${esc(x.name)}</a>`).join('') + '</div>';
    const corpora = P && P.corpora.length ? P.corpora : [''];
    const missing = corpora.filter(c => !found.some(x => x.corpus === c));
    if (missing.length && !(legacy.length && !P)) {
      const has = v => P && missing.every(c => ((P.cells[c] || {})[v] || {}).state === 'done');
      const profiled = has(a.v) && has(b.v);
      const argv = profiled ? ['branch', 'diff', name, a.v, b.v] : ['branch', 'profile', name, a.v, b.v, '--diff'];
      const cmd = 'perflab ' + argv.map(shq).join(' '), what = profiled ? 'Diff these two' : 'Profile & diff these two';
      const why = profiled ? 'both are profiled; their diff is not made yet' : `${[a, b].filter(c => !has(c.v)).map(c => sha(c, 7)).join(' and ')} not profiled yet`;
      const job = memOf(el).jobs[a.v + '-' + b.v];
      h += `<div class="bh-act"><span class="k">${missing[0] ? esc(missing.join(', ')) + ': ' : ''}${why}.</span> `
        + (job ? `<span class="k">${job}</span>`
          : SERVER ? `<button class="chip on" data-bprof="${esc(JSON.stringify(argv))}" data-bkey="${esc(a.v + '-' + b.v)}" title="${esc(cmd)}">${what}</button>`
          : `<code class="bh-cmd">${esc(cmd)}</code> <button class="chip" data-bcopy="${esc(cmd)}" title="copy the command">copy</button>`
            + ' <span class="k">in the project, or queue it with <code>perflab submit --</code></span>')
        + '</div>';
    }
    return h + '</div>';
  }
  // under `perflab server`, the project's index carries the server's token (its pages share the queue page's origin)
  const SERVER = (() => { const m = document.querySelector('meta[name="perflab-token"]'); return m && location.pathname.startsWith('/p/') ? m.content : null; })();
  async function queue(el, argv, key) {
    const say = s => { memOf(el).jobs[key] = s; drawOne(el); };
    try {
      say('queueing…');
      const id = decodeURIComponent(location.pathname.split('/')[2]);
      const proj = (await (await fetch('/api/projects')).json()).find(p => String(p.id) === id);
      if (!proj) throw new Error('this project is not registered with the server');
      const r = await fetch('/api/jobs', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Perflab-Token': SERVER},
                                          body: JSON.stringify({argv, cwd: proj.root})});
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      say(`queued as <a href="/">job ${esc(j.id)}</a>${j.position ? ` (#${esc(j.position)} in the queue)` : ''}; the diff appears here when it is done`);
    } catch (e) { say(`not queued: ${esc(e.message || e)}`); }
  }
  function drawOne(el) {
    const d = data(el), st = state(el), others = d.metrics.filter(m => m.k !== 'score');
    const chip = (a, v, on, label, t) => `<button class="chip" ${a}="${v}" aria-pressed="${on}"${t ? ` title="${t}"` : ''}>${label}</button>`;
    el.querySelector('.bh-ctl').innerHTML = '<span class="fg"><span class="fl">show</span>'
      + chip('data-bform', 'num', st.form === 'num', 'numbers', 'mean ± CI')
      + chip('data-bform', 'dot', st.form === 'dot', 'dots', 'the mean on a scale shared down the column, the CI as a whisker')
      + chip('data-bform', 'both', st.form === 'both', 'both') + '</span>'
      + `<span class="fg">${chip('data-bchart', '1', st.chart, 'chart', 'commits on x, the score left, the second metric right')}</span>`
      + '<label class="fg"><span class="fl">second metric</span><select data-bm2><option value="none">none</option>'
      + others.map(m => `<option value="${esc(m.k)}"${m.k === st.m2 ? ' selected' : ''}>${esc(unitFix(m.h))}</option>`).join('') + '</select></label>';
    drawChart(el, d, st); drawTable(el, d, st); drawCompare(el, d, st);
    if (memOf(el).hover) hover(el, memOf(el).hover);
  }
  function draw(cs) {
    if (cs) filter = cs;
    for (const el of document.querySelectorAll('.bh')) drawOne(el);
  }
  function hover(el, v) {
    memOf(el).hover = v;
    el.querySelectorAll('tr[data-v]').forEach(tr => tr.classList.toggle('hl', tr.dataset.v === v));
    el.querySelectorAll('rect[data-bband]').forEach(r => r.classList.toggle('hl', r.dataset.bband === v));
    const tip = el.querySelector('.bh-tip');
    if (tip) tip.innerHTML = tipText(data(el), state(el), v);
  }
  function update(el, f) { const st = state(el); f(st); save(el, st); drawOne(el); }
  const toggle = (st, v) => { st.sel = st.sel.includes(v) ? st.sel.filter(x => x !== v) : [...st.sel, v].slice(-2); };
  document.addEventListener('click', e => {
    const el = e.target.closest && e.target.closest('.bh'), t = el && e.target.closest('[data-bform],[data-bchart],[data-bc],[data-bmerge],[data-bhv],[data-bclear],[data-bprof],[data-bcopy]');
    if (!t) return;
    if (t.dataset.bform) update(el, st => { st.form = t.dataset.bform; });
    else if (t.dataset.bchart) update(el, st => { st.chart = !st.chart; });
    else if (t.dataset.bc) update(el, st => { st.c = t.dataset.bc; });
    else if (t.dataset.bclear) update(el, st => { st.sel = []; });
    else if (t.dataset.bprof) queue(el, JSON.parse(t.dataset.bprof), t.dataset.bkey);
    else if (t.dataset.bcopy) { if (navigator.clipboard) navigator.clipboard.writeText(t.dataset.bcopy).then(() => { t.textContent = 'copied'; }, () => {}); }
    else if (t.dataset.bhv) update(el, st => toggle(st, t.dataset.bhv));
    else {
      const o = memOf(el).open, v = t.dataset.bmerge;
      if (o.has(v)) o.delete(v); else o.add(v);
      drawOne(el);
    }
  });
  document.addEventListener('change', e => {
    const el = e.target.closest && e.target.closest('.bh');
    if (!el) return;
    if (e.target.matches('[data-bm2]')) update(el, st => { st.m2 = e.target.value; });
    else if (e.target.matches('[data-bsel]')) update(el, st => toggle(st, e.target.dataset.bsel));
  });
  document.addEventListener('mouseover', e => {
    const t = e.target.closest && e.target.closest('.bh tr[data-v], .bh rect[data-bhv]');
    if (!t) return;
    const el = t.closest('.bh'), v = t.dataset.v || t.dataset.bhv;
    if (memOf(el).hover !== v) hover(el, v);
  });
  let rz = 0;
  addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => draw(), 150); });
  return {draw};
})();
"""
