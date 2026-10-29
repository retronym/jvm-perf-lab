"""A branch campaign's history (doc/branch-explore.md, decisions 3 and 4): its commits newest first, first-parent, with
one column per corpus, and a chart of the same data with commits on x. A campaign is a branch campaign when its
directory has the branch.json the runner writes (doc/branch-explore-PLAN.md has the contract); its variants are the
commits' short shas, its cells where every campaign's are, <campaign>/<corpus>/<variant>/<round>/result.json.

`branch_view` gathers what the page draws, `section` puts it on the campaign's card, and BRANCH_JS draws it: the
history table (numbers, shaded by a bar on a scale shared down the column), the chart (score left, a second metric right, each
commit's mean with its 99.9% CI over forks, its forks' means and every measurement iteration), and the comparison of two
selected rows. The view's state is in the page's URL (`?b.<campaign>=...`), so a view can be linked and survives the
index's refresh.

The unit of variation is the fork: fork-to-fork variance (JIT decisions, code layout) dominates, and a fork's
iterations are autocorrelated, so pooling iterations would make the interval far too narrow. Per commit, corpus and
metric, each fork of each round contributes the mean of its measurement iterations (`rawData` in result.json, the
score's and those secondary metrics that have one; a metric without it, its round's value). The commit's mean is
theirs, and its 99.9% CI is t(df)·sd/√n over its n forks. Its sd is its own from four forks; with fewer, when the pool has more
degrees of freedom (always for one fork; with two its own CI would be t(1) = 637 times its sd, with three t(2) = 32), the fork-to-fork
relative sd pooled over the campaign's commits with two forks or more (same corpus and metric, each weighted by its df,
with the pool's df), marked as pooled; with no such commit yet one fork has no interval.

A Δ is against the previous measured commit, and the comparison of two rows uses the same test (`metrics.welch`, and
`welch` in the page): Welch's t on the forks' means, Welch–Satterthwaite df, a pooled sd for a side of one fork. Δ% is
shown ± the half-width of its 99.9% CI and coloured only when significant at 99.9%.

Within a fork, its iterations give an interval of their own (`within`: t(n-1)·sd/√n, JMH's error for one fork). It is
no interval for the commit, since it leaves out the fork-to-fork variance, so it is shown muted (±~) only where there is
nothing better (one fork, nothing to pool), never colours a Δ, and is drawn as a thin whisker on each fork's dash; the
ratio of the between-fork sd to it says whether more forks would pay. Each measurement iteration's competing load comes
from the cell's load.json (`ab.load_check`), or for an older cell from its load.tsv. Clicking a value opens the
popover of its rounds (`rounds_of`) and voided cells (`voided`), with Void & rerun on the server (`bhVoid`).
"""
import datetime, glob, html, json, math, os

from . import loadgate, metrics, ui

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
    """A cell's JMH result, "failed" when its run did (a branch campaign records why), "running" while its result.json
    is empty or partial, None before it has one."""
    f = os.path.join(cell, "result.json")
    try:
        r = json.load(open(f))[0]
        r["primaryMetric"]["score"]
        return r
    except (OSError, ValueError, IndexError, KeyError, TypeError):
        pass
    if os.path.exists(os.path.join(cell, "failed.txt")):  # ab.FAILED: its run failed
        return "failed"
    return "running" if os.path.exists(f) else None


def results(d):
    """A commit's cells on a corpus, in `d` (<campaign>/<corpus>/<variant>), by round: ([(JMH result, cell)] of those
    done, whether any is running, the last failed cell or None)."""
    rs, running, failed = [], False, None
    for cell in sorted(glob.glob(os.path.join(d, "*")), key=lambda c: (len(c), c)):
        if not (os.path.isdir(cell) and os.path.basename(cell).isdigit()):
            continue
        r = load_cell(cell)
        if r == "running":
            running = True
        elif r == "failed":
            failed = cell
        elif r is not None:
            rs.append((r, cell))
    return rs, running, failed


def failed_cell(cell, rel_to):
    return {"why": open(os.path.join(cell, "failed.txt")).read().strip(), "log": os.path.relpath(os.path.join(cell, "jmh.log"), rel_to)}


PROFILED = "p:"  # a profile pass's metric is keyed apart from the measurement's of the same name


def fork_units(rs, per_unit, prefix="", keep=lambda k, kind: True):
    """A commit's metrics (`metrics.of`, with an async kperf profile's events) over its cells `rs` ([(result, cell)]),
    those `keep` takes, keyed `prefix` + key: ({key: [per fork, the mean of its measurement iterations]}, {key: kind},
    {key: [[iteration, ...] per fork]}, [(key, label, kind)] in the order first seen). A metric without per-iteration
    samples has a value per round (JMH's mean over the round's forks)."""
    of = [metrics.of(r, per_unit, metrics.cached_hw_events(cell)) for r, cell in rs]
    kinds, raw, us, cols, wf = {}, {}, {}, [], {}
    for ms in of:
        for k, label, kind, _, _ in ms:
            if keep(k, kind) and prefix + k not in kinds:
                kinds[prefix + k] = kind
                cols.append((prefix + k, label, kind))
    for pk in kinds:
        k = pk[len(prefix):]
        forks = [f for (r, _) in rs for f in raw_of(r, k, metrics.units_per_op(r, per_unit) if per_unit else 1.0) if f]
        if forks:
            raw[pk] = [[sig(x) for x in f] for f in forks]
            wf[pk] = [within(f) for f in forks]
        us[pk] = [sum(f) / len(f) for f in forks] or [x for ms in of for kk, _, _, _, x in ms if kk == k and fin(x) is not None]
    return us, kinds, raw, cols, wf


def within(xs):
    """A fork's spread over its measurement iterations: (the half-width of their 99.9% CI, t(n-1)·sd/√n, as JMH's
    scoreError for a run of one fork; the standard error of its mean, sd/√n), both None under two iterations. It
    takes the iterations as independent, which they are not quite, and it says nothing of the fork-to-fork variance:
    an interval for that fork's mean, not the commit's."""
    if len(xs) < 2:
        return None, None
    mean, sd = metrics.stats(xs)
    se = sd / len(xs) ** 0.5
    return metrics.t999(len(xs) - 1) * se, se


def within_of(fs, sd):
    """A commit's within-fork spread of a metric, from its forks' `within` [(half-width, se)] and the sd of its forks'
    means `sd` (its own, or pooled; None without either): (the within-fork CI: its one fork's, else the root mean square
    of its forks', the ratio of the between-fork sd to the within-fork one, sd / √mean(se²)), None without forks. The
    ratio is about 1 when forks agree as closely as their iterations do, and far above it when each fork lands somewhere
    of its own (JIT decisions, code layout): then more forks pay off, and more iterations do not."""
    if not fs:
        return None
    hs = [h for h, _ in fs if h is not None]
    ses = [se for _, se in fs if se is not None]
    ciw = (hs[0] if len(fs) == 1 else (sum(h * h for h in hs) / len(hs)) ** 0.5) if hs else None
    ws = (sum(se * se for se in ses) / len(ses)) ** 0.5 if ses else 0
    return ciw, sd / ws if sd is not None and ws > 0 else None


LOAD_CHECK = "load.json"  # ab.LOAD_CHECK: a cell's measurement iterations' competing load, and the gate's verdict
MAX_CORES = 1.5  # the load gate's default maxCores
VOID = ".void"  # <campaign>/.void/<corpus>/<variant>/<round>-<stamp>/: a cell set aside, with void.txt saying why
VOID_REASON = "void.txt"


def cell_load(cell, max_cores):
    """A cell's competing load: (maxCores, [{"index", "start", "end", "score", "cores", "top"} per measurement
    iteration], [indices of those over maxCores]), from its load.json (`ab.load_check`), else, for a cell from before
    it, from its load.tsv and iterations.tsv over `max_cores` (the spec's); no iterations without either."""
    try:
        j = json.load(open(os.path.join(cell, LOAD_CHECK)))
        return j.get("maxCores", max_cores), j.get("iterations") or [], list(j.get("disturbed") or [])
    except (OSError, ValueError, AttributeError):
        pass
    if not os.path.exists(os.path.join(cell, "load.tsv")):
        return max_cores, [], []
    its = loadgate.per_iteration(os.path.join(cell, "load.tsv"), os.path.join(cell, "iterations.tsv"))
    return max_cores, its, [i["index"] for i in its if i["cores"] is not None and i["cores"] > max_cores]


def iteration_forks(cell, lengths):
    """{iteration index: (fork, j)} for a cell's measurement iterations (iterations.tsv): its fork, from 0 in the order
    they ran, and its place among that fork's measurement iterations, from 0, as in result.json's rawData, whose forks
    have `lengths` iterations. By pid when the forks' counts match rawData's, else in order when the total does; {}
    when neither does."""
    try:
        rows = open(os.path.join(cell, "iterations.tsv")).read().splitlines()
    except OSError:
        return {}
    head = rows[0].split("\t") if rows else []
    its = []
    for r in rows[1:]:
        x = dict(zip(head, r.split("\t")))
        if x.get("kind") in ("measure", "measurement"):
            try:
                its.append((float(x.get("start_ms") or 0), int(x.get("index") or 0), x.get("pid", "")))
            except ValueError:
                continue
    its.sort()
    pids = list(dict.fromkeys(p for _, _, p in its))
    groups = [[i for _, i, p in its if p == pid] for pid in pids]
    if [len(g) for g in groups] != list(lengths):
        if len(its) != sum(lengths):
            return {}
        flat, groups = [i for _, i, _ in its], []
        for n in lengths:
            groups.append(flat[:n])
            flat = flat[n:]
    return {i: (f, j) for f, g in enumerate(groups) for j, i in enumerate(g)}


def cell_links(cell, rel_to):
    """A cell's timeline and logs, {"timeline", "jmh", "build"}: those it has."""
    names = {"timeline": "timeline.html", "jmh": "jmh.log", "build": "build.log"}
    return {k: os.path.relpath(os.path.join(cell, n), rel_to) for k, n in names.items() if os.path.exists(os.path.join(cell, n))}


def rounds_of(d, rel_to, per_unit=None, max_cores=MAX_CORES):
    """A commit's rounds on a corpus (d is <campaign>/<corpus>/<variant>), as the cell's popover lists them, and where
    other load disturbed their measurement iterations in the cell's rawData, for the chart: ([{"round", "state" (done,
    failed with "why", running, pending), "forks": [{"mean", "ci" (within the fork, over its iterations), "n"}] of the
    score, "load" (the most of any measurement iteration, cores) and "maxCores", "disturbed": [{"i" (its index in
    iterations.tsv), "fork", "j" (from 1, when known), "cores", "top"}], "links", "graphs"}], [[fork, j] from 0, the
    forks of every done round in turn, as `fork_units` has them])."""
    rounds, hot, offset = [], [], 0
    for cell in sorted(glob.glob(os.path.join(d, "*")), key=lambda c: (len(c), c)):
        if not (os.path.isdir(cell) and os.path.basename(cell).isdigit()):
            continue
        r = load_cell(cell)
        state = r if isinstance(r, str) else "done" if r else "pending"
        x = {"round": int(os.path.basename(cell)), "state": state}
        forks = []
        if state == "done":
            forks = [f for f in raw_of(r, "score", metrics.units_per_op(r, per_unit) if per_unit else 1.0) if f]
            x["forks"] = [{"mean": sig(sum(f) / len(f)), "ci": None if h is None else sig(h, 3), "n": len(f)}
                          for f in forks for h in [within(f)[0]]]
        elif state == "failed":
            x["why"] = open(os.path.join(cell, "failed.txt")).read().strip()
        mc, its, dist = cell_load(cell, max_cores)
        loads = [i["cores"] for i in its if i.get("cores") is not None]
        if loads:
            x["load"], x["maxCores"] = max(loads), mc
        if dist:
            where = iteration_forks(cell, [len(f) for f in forks]) if forks else {}
            by = {i.get("index"): i for i in its}
            x["disturbed"] = [{"i": i, **({"fork": where[i][0] + 1, "j": where[i][1] + 1} if i in where else {}),
                               "cores": by.get(i, {}).get("cores"), "top": by.get(i, {}).get("top") or ""} for i in dist]
            hot += [[offset + where[i][0], where[i][1]] for i in dist if i in where]
        x["links"] = cell_links(cell, rel_to)
        g = graph_links(cell, rel_to)
        if g:
            x["graphs"] = g
        offset += len(forks)
        rounds.append(x)
    return rounds, hot


def voided(campaign_dir, corpus, variant, rel_to):
    """A commit's voided cells on a corpus (<campaign>/.void/<corpus>/<variant>/<round>-<stamp>/), which count for
    nothing: [{"round", "when", "why" (void.txt), "links"}], oldest first."""
    out = []
    for cell in sorted(glob.glob(os.path.join(campaign_dir, VOID, corpus, variant, "*"))):
        name = os.path.basename(cell)
        rnd, _, stamp = name.partition("-")
        if not (os.path.isdir(cell) and rnd.isdigit()):
            continue
        try:
            why = open(os.path.join(cell, VOID_REASON)).read().strip()
        except OSError:
            why = ""
        try:
            when = datetime.datetime.strptime(stamp, "%Y%m%d-%H%M%S").strftime("%a %d %b %H:%M")
        except ValueError:
            when = stamp
        out.append({"round": int(rnd), "when": when, "why": why, "links": cell_links(cell, rel_to)})
    return out


def own_graphs(rs, rel_to):
    """The flame graphs of a commit's own cells (a campaign measured under an async profile), [[event, kind, href]],
    the event with its round when more than one round has graphs."""
    per = [(os.path.basename(cell), graph_links(cell, rel_to)) for _, cell in rs]
    per = [(n, gs) for n, gs in per if gs]
    return [[f"{ev} #{n}" if len(per) > 1 else ev, k, href] for n, gs in per for ev, k, href in gs]


def date_shown(iso):
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%a %d %b %Y")
    except (TypeError, ValueError):
        return iso or ""


def branch_view(campaign_dir, rel_to=None):
    """What the page draws for a branch campaign, None when `campaign_dir` has no branch.json:

    {"commits": [newest first: {sha, short, v (variant), subject, author, date, shown (date), index, merged}],
     "corpora": [...], "metrics": [{k, h (heading), kind, src: "profile" for the profile pass's}], the score first,
     "cells": {corpus: {variant: {"state": "done" | "running" | "failed" (with "why" and "log"), "rounds": n,
                                  "pr": n rounds of the profile pass, "ms": the score's state when only profiled,
                                  "graphs": [[event, kind, href]] of its own cells, when measured under an async profile,
                                  "pv": {k: variant} the Δ is against, when not "prev" (a metric "prev" lacks),
                                  "forks": n, "m": {k: [mean, sd of the forks' means, CI half-width, Δ against it
                                  means something, n forks, df, sd pooled]} (sd, CI and df None without a spread),
                                  "s": {k: [mean shown, CI shown]}, "raw": {k: [[x, ...] per fork, of every round]},
                                  "d": {k: [Δ%, half-width of its CI, verdict, a side pooled]},
                                  "prev": variant of the previous measured commit,
                                  "w": {k: [within-fork CI (`within_of`), between/within-fork sd ratio, the CI shown]},
                                  "wf": {k: [each fork's within-fork CI, as "raw" has the forks]},
                                  "rd": [its rounds, `rounds_of`], "hot": [[fork, j] of "raw"'s iterations other load
                                  disturbed], "void": [its voided cells, `voided`]}}},
     a cell's "state" is "none" when it has only voided rounds,

    The profile pass (<campaign>.profile, `profiles`) contributes its cells' metrics, keyed "p:<key>", but not the
    score: a profiler perturbs it (allocation, PMU counters and their ratios it does not, or not much). They have the
    same statistics as the measurement's, over the profile cells' forks; a commit profiled and not measured has a cell
    of them alone.
     "diffs": [{name, href}], "unbuildable": {variant: {reason, log (href of its build.log)}}}

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
    max_cores = (spec.get("loadgate") or {}).get("maxCores", MAX_CORES)
    commits = sorted(branch.get("commits", []), key=lambda c: c.get("index", 0))
    variants = [c.get("variant") or c["short"] for c in commits]
    on_disk = sorted(os.path.basename(d.rstrip("/")) for d in glob.glob(os.path.join(campaign_dir, "*/"))
                     if not os.path.basename(d.rstrip("/")).startswith(("diff-", ".")))
    named = list(spec.get("corpora") or [])
    corpora = [c for c in named] + [c for c in on_disk if c not in named and any(os.path.isdir(os.path.join(campaign_dir, c, v)) for v in variants)]

    pdir = os.path.normpath(campaign_dir) + PROFILE_SUFFIX
    pdir = pdir if os.path.isdir(pdir) else None
    if pdir:  # a corpus only the profile pass ran on gets its columns too
        corpora += [c for c in profile_corpora(pdir) if c not in corpora and any(os.path.isdir(os.path.join(pdir, c, v)) for v in variants)]
    rel_to = rel_to or campaign_dir
    cols, pcols, cells = {}, {}, {}
    for corpus in corpora:
        per_v, units = {}, {}
        prev = None  # the previous commit with a score
        for v in variants:
            rs, running, failed = results(os.path.join(campaign_dir, corpus, v))
            # the profile pass's cells: their metrics, but not the score (or anything else timed: the profiler perturbs it)
            prs = results(os.path.join(pdir, corpus, v))[0] if pdir else []
            # its rounds, for the popover, and the measurement iterations other load disturbed, for the chart's cloud
            rd, hot = rounds_of(os.path.join(campaign_dir, corpus, v), rel_to, per_unit, max_cores)
            extra = {k: x for k, x in (("rd", rd), ("void", voided(campaign_dir, corpus, v, rel_to)), ("hot", hot)) if x}
            if not rs and not prs:
                if running:
                    per_v[v] = {"state": "running", **extra}
                elif failed:
                    per_v[v] = {"state": "failed", **failed_cell(failed, rel_to), **extra}
                elif extra:  # only voided rounds: nothing to show but them
                    per_v[v] = {"state": "none", **extra}
                continue
            us, kinds, raw, cs, wf = fork_units(rs, per_unit)
            pus, pkinds, praw, pcs, pwf = fork_units(prs, per_unit, PROFILED, lambda k, kind: kind != "score")
            for c in cs:
                cols.setdefault(c[0], c)
            for c in pcs:
                pcols.setdefault(c[0], c)
            x = per_v[v] = {"state": "done", "rounds": len(rs), "forks": max((len(u) for u in us.values()), default=0),
                            "m": {}, "s": {}, "raw": {**raw, **praw}, "d": {}, "prev": prev, "w": {},
                            "wf": {k: [None if h is None else sig(h, 3) for h, _ in fs] for k, fs in {**wf, **pwf}.items()}, **extra}
            if prs:
                x["pr"] = len(prs)
            if not rs:  # profiled, not measured (yet): the score's state
                x.update({"ms": "running"} if running else {"ms": "failed", **failed_cell(failed, rel_to)} if failed else {})
            if running:
                x["running"] = True
            g = own_graphs(rs, rel_to)
            if g:
                x["graphs"] = g
            units[v] = ({**us, **pus}, {**kinds, **pkinds}, {**wf, **pwf})
            if "score" in us:
                prev = v
        # per metric, the fork-to-fork relative sd pooled over the commits with two forks or more (ANOVA's within-group
        # estimate, assuming a common relative spread), for a commit of fewer than metrics.OWN_FORKS forks when the pool has more
        # degrees of freedom: with two forks a commit's own 99.9% CI is t(1) = 637 times its sd, with three t(2) = 32;
        # from four, its own spread says something (a commit whose forks land in two places should show it)
        stat = {v: {k: (*metrics.stats(xs), len(xs)) for k, xs in us.items() if xs} for v, (us, _, _) in units.items()}
        keys = {k for st in stat.values() for k in st}
        pool = {k: metrics.pooled_rel_sd([(st[k][0], st[k][1], st[k][2] - 1) for st in stat.values() if k in st]) for k in keys}
        last = {}  # per metric, the latest commit with it so far: a Δ is against it
        for v, (us, kinds, wfs) in units.items():
            x = per_v[v]
            for k, (mean, sd, n) in stat[v].items():
                kind = kinds[k]
                sd, df, pooled = metrics.fork_spread(mean, sd, n, pool[k])
                ci = None if sd is None else metrics.t999(df) * sd / n ** 0.5
                x["m"][k] = [fin(mean), fin(sd), fin(ci), metrics.delta_ok(mean, kind, per_unit), n, df, pooled]
                x["s"][k] = [metrics.fmt(kind, mean), "" if ci is None else ci_shown(kind, ci, mean)]
                w = within_of(wfs.get(k), sd)
                if w:
                    x["w"][k] = [fin(w[0]), fin(w[1]), "" if w[0] is None else ci_shown(kind, w[0], mean)]
            for k, m in x["m"].items():
                if k in last:
                    pm = per_v[last[k]]["m"][k]
                    d, half, _ = metrics.welch(fork_stats(pm), fork_stats(m))
                    if d is not None:
                        x["d"][k] = [fin(d), fin(half), index.verdict(d, half, pm[3]), pm[6] or m[6]]
                        if last[k] != x["prev"]:  # the commit before it lacks this metric: what its Δ is against
                            x.setdefault("pv", {})[k] = last[k]
                last[k] = v
        if per_v:
            cells[corpus] = per_v
    corpora = [c for c in corpora if c in cells] + [c for c in named if c not in cells]
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
            "corpora": corpora, "metrics": [{"k": k, "h": label, "kind": kind} for k, label, kind in cols.values()]
                                          + [{"k": k, "h": label, "kind": kind, "src": "profile"} for k, label, kind in pcols.values()],
            "cells": cells, "diffs": diffs, "range": branch.get("range", ""), "perUnit": per_unit,
            "unbuildable": unbuildable(campaign_dir, rel_to), "measureProfile": spec.get("profile"),
            "profile": profiles(campaign_dir, variants, rel_to)}


def unbuildable(campaign_dir, rel_to):
    """{variant: {"reason": ..., "log": href of its build.log}} of the commits that did not build (unbuildable.json)."""
    try:
        u = json.load(open(os.path.join(campaign_dir, "unbuildable.json")))
    except (OSError, ValueError):
        return {}
    return {v: {"reason": x.get("reason", ""), "log": os.path.relpath(os.path.join(campaign_dir, x.get("log", "")), rel_to)}
            for v, x in u.items()}


PROFILE_SUFFIX = ".profile"  # the profile campaign beside a branch campaign (perflab.branchprofile)


def graph_links(cell, rel_to):
    """A profile cell's rendered flame graphs, [[event, kind, href], ...], as the index's cell rows link them."""
    from . import regraph
    pf = os.path.join(cell, "profile.txt")
    if not (os.path.exists(pf) and open(pf).read().startswith("async")):  # xctrace, say: no flame graphs
        return []
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

    {"campaign": its name, "profile": its profile (as `perflab run --profile`), "corpora": [the corpora it profiles],
     "cells": {corpus: {variant: {"state": "done" | "running", "graphs": [[event, kind, href], ...]}}},
     "diffs": [{"a", "b" (variants), "corpus", "href" (compare.html), "events": [{"ev", "slots": [[view, href], ...]}]}]}

    A diff is one `perflab branch diff` wrote (its pair.json names the commits and the corpus), so the view matches it
    to a pair of rows exactly."""
    from . import compare, regraph
    pdir = os.path.normpath(campaign_dir) + PROFILE_SUFFIX
    if not os.path.isdir(pdir):
        return None
    try:
        spec = json.load(open(os.path.join(pdir, "spec.json")))
    except (OSError, ValueError):
        spec = {}
    cells = {}
    corpora = list(spec.get("corpora") or [])
    for corpus in profile_corpora(pdir):
        d = os.path.join(pdir, corpus)
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
    return {"campaign": os.path.basename(pdir), "profile": spec.get("profile", ""), "corpora": corpora, "cells": cells, "diffs": diffs}


def profile_corpora(pdir):
    """The corpora a profile campaign has cells of, by its directories."""
    return [c for c in (os.path.basename(d.rstrip("/")) for d in sorted(glob.glob(os.path.join(pdir, "*/")))) if not c.startswith(("diff-", "."))]


def ci_shown(kind, ci, mean):
    """A CI's half-width as its mean is shown: a score to the score's decimals."""
    return ui.num(ci, mean) if kind == "score" else metrics.fmt(kind, ci)


def section(campaign_dir, rel_to, corpus_param="corpus"):
    """The History section of a branch campaign's card, "" for any other campaign."""
    p = parts(campaign_dir, rel_to, corpus_param)
    return f'<h3 class="sub">History <span class="k">{p[0]}</span> {p[1]}</h3>{p[2]}' if p else ""


def parts(campaign_dir, rel_to, corpus_param="corpus"):
    """A branch campaign's history as (the note for its heading, its help popover, its body), None for any other
    campaign: the index shows it as the first of the summary's views."""
    data = branch_view(campaign_dir, rel_to)
    if data is None:
        return None
    name = os.path.basename(os.path.normpath(campaign_dir))
    data["corpusParam"] = corpus_param
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    n = len(data["commits"])
    measured = len({v for cs in data["cells"].values() for v, c in cs.items() if "score" in c.get("m", {})})
    note = (f"{n} first-parent commits of <code>{esc(data['range'])}</code>, newest first; {measured} measured. "
            "Mean over forks ± 99.9% CI over forks; Δ against the previous measured commit")
    help_ = ui.help_popover(
        "<p style='margin-top:0'>A row per first-parent commit; a merge's <b>+n</b> lists the commits it brought in. Per corpus, the "
        "score, shaded by a bar on a scale shared down the column (the lighter band at its end is the CI), and a second metric "
        "beside it.</p>"
        "<p>The unit is the <b>fork</b>: each fork of each round counts once, as the mean of its measurement iterations (they vary "
        "far less within a fork than between forks, and are not independent). A value is the mean over forks ± a 99.9% confidence "
        "interval over forks. † marks an interval from the fork-to-fork sd pooled over this corpus's commits with two forks or more, "
        "for a commit of fewer than four forks (one fork has no spread of its own; with two, its own CI is 637 times its sd). Until there is a pool, a commit of one fork has none, and shows instead, muted, <b>±~</b> the 99.9% "
        "CI within its one fork, over its iterations (as JMH's error for one fork): it understates run-to-run uncertainty, and never "
        "colours a Δ. A value's tooltip has the ratio of the between-fork to the within-fork sd: about 1, the forks agree; far above, "
        "each fork lands somewhere of its own, and more forks pay off where more iterations do not.</p>"
        "<p>A <span class='bh-hot'></span>ring marks a value with measurement iterations run while other load was over the load gate's "
        "limit (in the chart, those iterations' dots). <b>Click a value</b> for its rounds: each fork's mean ± its CI within the fork, "
        "the load, the timeline and logs, and voided cells (<code>.void/</code>, which count for nothing); served by "
        "<code>perflab server</code>, <b>Void &amp; rerun</b> sets a round aside with a reason and queues the campaign's resume.</p>"
        "<p>Δ is against the previous (older) measured commit, ± its 99.9% CI (Welch's t over the forks' means), coloured only when "
        "significant at 99.9%. Comparing two rows uses the same test.</p>"
        "<p><b>Chart</b>: commits oldest to newest, gaps where a commit is unmeasured; error bars are the 99.9% CI over forks "
        "(lighter when pooled), dashes each fork's mean with a thin whisker for its CI over its own iterations, the faint cloud every "
        "iteration. Tick two rows (or one, against the commit "
        "before it) to compare them. The view is kept in the "
        "page's URL.</p><p style='margin-bottom:0'><b>Profiles</b> are runs of their own (a profiler perturbs the score), in the "
        "campaign <i>&lt;name&gt;.profile</i> beside this one, from the same builds: <code>perflab branch profile</code>. A row's "
        "<b>profile</b> badge opens its flame graphs; comparing two rows shows their differential flame graphs (<code>perflab branch "
        "diff</code>), or offers to make them. The profile pass's metrics, other than the score, are second metrics marked "
        "<b>· profile</b> (allocation, PMU counters), with the same statistics over its own forks, and a Δ against the commit profiled "
        "before. A campaign measured under an async profile has a <b>graphs</b> badge for its own cells' flame graphs.</p>", right=True)
    return (note, help_, f'<div class="bh" data-campaign="{esc(name)}"><div class="bh-ctl"></div><div class="bh-chart"></div>'
            f'<div class="bh-table"></div><div class="bh-cmp"></div><script type="application/json">{blob}</script></div>')


CSS = """
.bh{margin:2px 0 10px} .bh-ctl{display:flex;flex-wrap:wrap;gap:4px 18px;margin:6px 0 4px;align-items:center}
.bh-ctl select{font:inherit;font-size:12px;padding:1px 4px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}
table.bh-t td{vertical-align:middle} table.bh-t th{vertical-align:bottom} table.bh-t th.cg{text-align:center;color:var(--fg);border-bottom:1px solid var(--line2)}
table.bh-t td.gs,table.bh-t th.gs{border-left:1px solid var(--line2)}
table.bh-t td.cm,table.bh-t th.cm{position:sticky;left:0;z-index:1;background:var(--panel);white-space:normal;min-width:180px;max-width:480px}
.bh-cm{display:flex;gap:8px;align-items:flex-start} .bh-cm input{margin:3px 0 0}
.bh-c{min-width:0} .bh-subj{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:min(440px,34vw)}
.bh-who{display:block;font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:min(440px,34vw)}
.bh-mg{font:11px/15px inherit;border:1px solid var(--line);background:var(--panel);color:var(--link);border-radius:999px;padding:0 6px;margin-left:4px;cursor:pointer;vertical-align:1px}
table.bh-t tr.hl td{background:var(--line2)} table.bh-t tr.sel td{background:var(--link-bg)}
table.bh-t tr.bh-sub td{padding-top:0;border-bottom:1px solid var(--line2)} table.bh-t tr.has-sub td{border-bottom:0}
.bh-sub ul{margin:0;padding:0 0 0 26px;list-style:none;font-size:12px} .bh-sub li{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:420px}
.bh-v{display:block;white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums;padding:3px 6px;margin:-3px -6px;border-radius:3px} .bh-v .pm{white-space:nowrap}
.bh-v .mv{font-weight:500}
.bh-v.bar{min-width:118px;background:linear-gradient(to right,transparent var(--c0,var(--w)),var(--bh-ci) var(--c0,var(--w)),var(--bh-ci) var(--c1,var(--w)),transparent var(--c1,var(--w))),linear-gradient(to right,var(--bh-bar) var(--w),var(--bh-rest) var(--w))}
.bh-v.bar.pl{background:linear-gradient(to right,var(--bh-bar) var(--w),var(--bh-rest) var(--w))}
.bh{--bh-bar:color-mix(in srgb,var(--link) 17%,transparent);--bh-ci:color-mix(in srgb,var(--link) 9%,transparent);--bh-rest:color-mix(in srgb,var(--link) 4%,transparent)}
table.bh-t td .d{display:inline-block;padding:1px 5px;border-radius:3px;margin:0 -5px}
table.bh-t td .d.better{background:color-mix(in srgb,var(--ok) 13%,transparent)} table.bh-t td .d.worse{background:color-mix(in srgb,var(--bad) 13%,transparent)}
.bh-pend{color:var(--muted);font-size:11.5px}
.bh-fail{color:var(--bad);font-size:11.5px}
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
:root{--bh-load:#c27c00} @media (prefers-color-scheme: dark){:root{--bh-load:#f0b040}}
button.bh-v{font:inherit;color:inherit;border:0;background:none;cursor:pointer;width:calc(100% + 12px)}
button.bh-v:hover .mv{text-decoration:underline} button.bh-v:focus-visible{outline:2px solid var(--link);outline-offset:-1px}
button.bh-v[aria-expanded=true]{box-shadow:inset 0 0 0 1.5px var(--link)}
.bh-v .wi{color:var(--muted);font-size:11.5px}
.bh-hot{display:inline-block;width:7px;height:7px;border-radius:50%;border:1.5px solid var(--bh-load);margin-right:5px;vertical-align:1px}
svg.bh-g .hot{fill:none;stroke:var(--bh-load);stroke-width:1.3} svg.bh-g .w1{stroke:var(--link);stroke-width:1;opacity:.4} svg.bh-g .w2{stroke:var(--brand);stroke-width:1;opacity:.4}
.bh-leg i.hot{background:none;border:1.5px solid var(--bh-load);width:8px;height:8px} .bh-leg i.wh{width:1.5px;height:11px;border-radius:0;opacity:.5;vertical-align:-2px}
#bh-pop{position:absolute;z-index:50;width:min(460px,calc(100vw - 16px));max-height:min(70vh,560px);overflow:auto;background:var(--panel);color:var(--fg);
  border:1px solid var(--line);border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.22);padding:8px 12px 10px;font-size:12.5px}
#bh-pop[hidden]{display:none} #bh-pop:focus{outline:none}
#bh-pop .ph{display:flex;gap:8px;align-items:baseline;margin:0 0 4px} #bh-pop .ph h4{margin:0;font-size:13px;flex:1;min-width:0;overflow-wrap:anywhere}
#bh-pop .x{font:15px/22px inherit;width:28px;height:28px;flex:none;border:1px solid var(--line);border-radius:6px;background:none;color:var(--fg);cursor:pointer}
#bh-pop ul{list-style:none;margin:0;padding:0} #bh-pop li{border-top:1px solid var(--line2);padding:6px 0}
#bh-pop .rh{display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline} #bh-pop .fk{font-variant-numeric:tabular-nums}
#bh-pop .fk .pm{color:var(--muted)} #bh-pop .dz{color:var(--fg);margin:2px 0;font-size:12px} #bh-pop .dz .bh-hot{margin-left:1px}
#bh-pop .btns{margin-top:4px} #bh-pop li.void{color:var(--muted)} #bh-pop li.void .why{color:var(--fg)}
#bh-pop .act{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;margin-top:5px}
#bh-pop .act input{font:inherit;font-size:12px;flex:1 1 180px;min-width:0;padding:2px 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}
#bh-pop .msg{flex-basis:100%;font-size:12px} #bh-pop .msg.err{color:var(--bad)}
#bh-pop .chip.warn{border-color:var(--bad);color:var(--bad)}
@media (max-width:600px){#bh-pop{position:fixed;left:0!important;right:0;top:auto!important;bottom:0;width:auto;max-height:75vh;border-radius:12px 12px 0 0;
  padding-bottom:calc(10px + env(safe-area-inset-bottom))} #bh-pop .act .chip{padding:4px 12px}}
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
// the server's endpoints the history's actions use (perflab server, under /p/<project>/)
const BH_API = {projects: '/api/projects', void: '/api/v1/void', rerun: '/api/v1/rerun'};
// Voids a cell and queues its campaign's resume, which measures it again: POST BH_API.void {project, campaign, corpus,
// variant, round, reason}, then BH_API.rerun {project, campaign}, with the token of the server that served the page.
// Resolves to {void, rerun} (their JSON replies); rejects with an Error whose message is the server's error text, and
// whose `stage` is 'void' or 'rerun' (a rerun that fails leaves the cell voided).
async function bhVoid(campaign, corpus, variant, round, reason) {
  const m = document.querySelector('meta[name="perflab-token"]');
  if (!m || !location.pathname.startsWith('/p/')) throw Object.assign(new Error('the page is not served by perflab server'), {stage: 'void'});
  const id = decodeURIComponent(location.pathname.split('/')[2]);
  const post = async (stage, url, body) => {
    let r, text = '';
    try {
      r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Perflab-Token': m.content}, body: JSON.stringify(body)});
      text = await r.text();
    } catch (e) { throw Object.assign(new Error(e.message || String(e)), {stage}); }
    let j = null;
    try { j = text ? JSON.parse(text) : null; } catch (e) {}
    if (!r.ok) throw Object.assign(new Error((j && j.error) || text.trim() || `${r.status} ${r.statusText}`), {stage});
    return j;
  };
  let proj;
  try { proj = (await (await fetch(BH_API.projects)).json()).find(p => String(p.id) === id); } catch (e) {}
  if (!proj) throw Object.assign(new Error('this project is not registered with the server'), {stage: 'void'});
  const v = await post('void', BH_API.void, {project: proj.id, campaign, corpus, variant, round, reason});
  const q = await post('rerun', BH_API.rerun, {project: proj.id, campaign});
  return {void: v, rerun: q};
}
const BH = (() => {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);
  const mem = {};  // per campaign, for this page only: the merges opened, the commit hovered, the jobs queued by pair
  // the cell whose popover is open, {camp, c, v}, and per round shown in one, its Void & rerun's state
  let pop = null;
  const act = {};
  const memOf = el => mem[el.dataset.campaign] = mem[el.dataset.campaign] || {open: new Set(), hover: null, jobs: {}};
  let filter = new Set();
  const key = n => 'b.' + n;
  const data = el => el._d || (el._d = JSON.parse(el.querySelector('script').textContent));
  // ?b.<campaign>=form:bar;chart:0;c:<corpus>;m2:<metric>;sel:<variant>,<variant>
  function state(el) {
    const d = data(el), st = {form: 'bar', chart: false, c: '', m2: '', sel: []};
    let raw = '';
    try { raw = new URLSearchParams(location.search).get(key(el.dataset.campaign)) || ''; } catch (e) {}
    for (const part of raw.split(';')) {
      const i = part.indexOf(':');
      if (i < 0) continue;
      const k = part.slice(0, i), v = part.slice(i + 1);
      if (k === 'form') st.form = v === 'num' ? 'num' : 'bar';  // 'dot' and 'both' of older links: the bar
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
  // (`s`, the step between ticks: enough digits that neighbours differ)
  function tick(kind, x, s) {
    const a = Math.abs(x), p = (y, div) => s ? `${+y.toFixed(Math.max(0, -Math.floor(Math.log10(s / div))))}` : `${+y.toPrecision(3)}`;
    if (kind === 'alloc') return a >= 1e5 ? `${p(x / 1e6, 1e6)}MB` : a >= 1e3 ? `${p(x / 1e3, 1e3)}KB` : `${p(x, 1)}B`;
    if (kind === 'count') return a >= 1e9 ? `${p(x / 1e9, 1e9)}G` : a >= 1e6 ? `${p(x / 1e6, 1e6)}M` : a >= 1e3 ? `${p(x / 1e3, 1e3)}K` : `${p(x, 1)}`;
    if (kind === 'pct') return `${p(x)}%`;
    return a >= 1e4 ? Math.round(x).toLocaleString('en') : `${+x.toPrecision(4)}`;
  }
  function step(span) { const p = Math.pow(10, Math.floor(Math.log10(span / 4))), r = span / 4 / p; return p * (r >= 5 ? 5 : r >= 2 ? 2 : 1); }
  const pct = (d, sp) => `${d >= 0 ? '+' : ''}${d.toFixed(1)}%` + (sp != null ? ` <span class="pm">± ${sp.toFixed(1)}</span>` : '');
  const TITLE = {flat: 'inconclusive: not significant at 99.9% (Welch’s t over forks)', worse: 'higher, significant at 99.9% (Welch’s t over forks)',
                 better: 'lower, significant at 99.9% (Welch’s t over forks)'};
  const POOLED = '† its spread is the fork-to-fork sd pooled over this corpus’s commits with two forks or more, which has more degrees of freedom than its own forks';
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
      if (withRaw) ((x.raw || {})[k] || []).forEach((f, fi) => {
        ys.push(...f);
        const h = ((x.wf || {})[k] || [])[fi], fm = f.length ? f.reduce((p, s) => p + s, 0) / f.length : null;
        if (h != null && fm != null) ys.push(fm - h, fm + h);  // a fork's whisker
      });
      for (const y of ys) { lo = Math.min(lo, y); hi = Math.max(hi, y); }
    }
    if (!isFinite(lo)) return null;
    if (hi - lo <= Math.abs(hi) * 1e-9) { const e = Math.abs(hi) * 0.01 || 1; lo -= e; hi += e; }
    const p = (hi - lo) * 0.06;
    return [lo - p, hi + p];
  }
  // a value's bar, as CSS variables of its cell: the mean's width on the column's scale, and its CI as a band; the scale
  // starts a little below the column's lowest value, so that steps between commits show
  function bar(m, ext) {
    const P = y => Math.max(0, Math.min(100, 8 + 92 * (y - ext[0]) / (ext[1] - ext[0]))).toFixed(1) + '%';
    const ci = m[2] != null ? `;--c0:${P(m[0] - m[2])};--c1:${P(m[0] + m[2])}` : '';
    return ` style="--w:${P(m[0])}${ci}"`;
  }
  // a column's unit for sizes and counts (alloc in MB/op, say): in its header, so that its values are plain numbers
  function scaleOf(d, k) {
    const kind = metric(d, k).kind;
    if (kind !== 'alloc' && kind !== 'count') return null;
    let hi = 0;
    for (const cs of Object.values(d.cells)) for (const x of Object.values(cs)) { const m = x.m && x.m[k]; if (m && m[0] != null) hi = Math.max(hi, Math.abs(m[0])); }
    const us = kind === 'alloc' ? [[1e9, 'GB'], [1e6, 'MB'], [1e3, 'KB'], [1, 'B']] : [[1e9, 'G'], [1e6, 'M'], [1e3, 'K'], [1, '']];
    const [div, u] = us.find(([v]) => hi >= v * 10) || us[us.length - 1];
    return {div, u};
  }
  const plain = x => Math.abs(x) >= 1000 ? Math.round(x).toLocaleString('en') : `${+x.toPrecision(4)}`;
  const plainCI = ci => ci >= 100 ? Math.round(ci).toLocaleString('en') : `${+ci.toPrecision(2)}`;
  function shown(d, k, m, s) {  // [mean, CI] as the cell shows them: plain numbers in the header's unit
    const sc = scaleOf(d, k);
    if (!sc) return s;
    return [plain(m[0] / sc.div), m[2] != null ? plainCI(m[2] / sc.div) : ''];
  }
  // a metric of the profile pass (<campaign>.profile): "· profile" after its heading, keyed p:<key>
  const fromProfile = (d, k) => metric(d, k).src === 'profile';
  function heading(d, k) {
    const m = metric(d, k), sc = scaleOf(d, k), p = fromProfile(d, k) ? ' · profile' : '';
    if (!sc) return unitFix(m.h) + p;
    const per = String(m.h).includes('/') ? '/' + String(m.h).split('/').pop() : '';
    return `${String(m.h).split('/')[0]} ${sc.u || '×'}${per}${p}`;
  }
  function headTip(d, k) {
    if (!fromProfile(d, k)) return '';
    const P = d.profile || {};
    return `from the profile pass, ${P.campaign || 'the profile campaign'}${P.profile ? ` (${P.profile})` : ''}: runs of their own under the profiler, so no score from them`;
  }
  const th = (d, k, cls) => `<th class="${cls}"${fromProfile(d, k) ? ` title="${esc(headTip(d, k))}"` : ''}>${esc(heading(d, k))}</th>`;
  // a commit's score when it is profiled and not measured: its measurement's state
  function unmeasured(x, v, d) {
    const u = (d.unbuildable || {})[v];
    if (x.ms === 'running') return '<span class="badge running">running</span>';
    if (x.ms === 'failed') return `<a class="bh-fail" href="${esc(x.log)}" title="${esc(x.why)}">run failed</a>`;
    return u ? `<a class="bh-fail" href="${esc(u.log)}" title="${esc(u.reason)}">build failed</a>` : '<span class="bh-pend" title="profiled, not measured yet">pending</span>';
  }
  // a cell's value is a button opening its popover (its rounds, `popover`)
  const cellBtn = (c, v, cls, attrs, tip, inner) => `<button type="button" class="bh-v${cls}" data-bcell="${esc(c)}" data-bcv="${esc(v)}" aria-haspopup="dialog"`
    + ` aria-expanded="${!!(pop && pop.c === c && pop.v === v)}"${attrs} title="${tip}">${inner}</button>`;
  const WITHIN = 'within one fork, over its iterations; understates run-to-run uncertainty';
  // the measurement iterations other load disturbed, over a cell's rounds: [[round, {i, fork, j, cores, top}]]
  const disturbed = x => (x.rd || []).flatMap(r => (r.disturbed || []).map(z => [r, z]));
  // a round's disturbed iterations, a run of consecutive ones of a fork as one: [{i, i1, fork, j, j1, cores (the most), top}]
  function runs(zs) {
    const out = [];
    for (const z of zs) {
      const p = out[out.length - 1];
      if (p && z.i === p.i1 + 1 && z.fork === p.fork) {
        Object.assign(p, {i1: z.i, j1: z.j});
        if ((z.cores || 0) > (p.cores || 0)) Object.assign(p, {cores: z.cores, top: z.top});
      } else out.push({...z, i1: z.i, j1: z.j});
    }
    return out;
  }
  const coresOf = z => z.cores == null ? '' : `${z.i1 !== z.i ? 'up to ' : ''}${(+z.cores).toFixed(1)} cores`;
  const span = (a, b) => a === b ? `${a}` : `${a}–${b}`;
  const itName = z => `iteration${z.i1 !== z.i ? 's' : ''} ${span(z.i, z.i1)}${z.fork ? ` (fork ${z.fork}, measurement${z.i1 !== z.i ? 's' : ''} ${span(z.j, z.j1)})` : ''}`;
  function hotTip(x) {
    const zs = disturbed(x);
    if (!zs.length) return '';
    const lim = zs[0][0].maxCores;
    return `Other load over ${lim != null ? lim + ' cores' : 'the limit'} during ${zs.length} measurement iteration${zs.length > 1 ? 's' : ''}: `
      + (x.rd || []).filter(r => (r.disturbed || []).length).flatMap(r => runs(r.disturbed).map(z => `#${r.round} ${itName(z)} ${coresOf(z)}${z.top ? ` (${z.top})` : ''}`)).join('; ');
  }
  function value(d, st, c, v, k, exts) {
    const x = cellOf(d, c, v);
    const u = (d.unbuildable || {})[v];
    if (!x) return u ? `<a class="bh-fail" href="${esc(u.log)}" title="${esc(u.reason)}">build failed</a>` : '<span class="bh-pend">pending</span>';
    const nv = (x.void || []).length, vd = nv ? ` <span class="bh-pend">· ${nv} voided</span>` : '';
    if (x.state === 'running') return cellBtn(c, v, '', '', 'running: its rounds', '<span class="badge running">running</span>' + vd);
    if (x.state === 'failed') return cellBtn(c, v, '', '', esc(x.why) + ' (its rounds and logs)', '<span class="bh-fail">run failed</span>' + vd);
    if (x.state === 'none') return k === 'score' ? cellBtn(c, v, '', '', 'its voided rounds', '<span class="bh-pend">pending</span>' + vd) : '';
    const m = x.m[k];
    if (!m) return k === 'score' ? unmeasured(x, v, d) : '';
    const rounds = fromProfile(d, k) ? x.pr : x.rounds;
    const s = shown(d, k, m, x.s[k]), sc = scaleOf(d, k), un = sc ? ` ${sc.u}` : '';
    const dag = m[6] ? '†' : '', w = (x.w || {})[k];
    // one fork and nothing to pool: its interval over its own iterations, muted, for want of one over forks
    const ws = w && w[0] != null ? (sc ? plainCI(w[0] / sc.div) : w[2]) : '';
    const n = `<span class="mv">${esc(s[0])}</span>${s[1] ? ` <span class="pm">± ${esc(s[1])}${dag}</span>`
      : ws ? ` <span class="pm wi" title="${WITHIN}">±~ ${esc(ws)}</span>` : ''}`;
    const hot = k === 'score' && disturbed(x).length ? `<span class="bh-hot" role="img" aria-label="disturbed by other load"></span>` : '';
    const g = st.form === 'num' || !exts[c + '|' + k] ? '' : bar(m, exts[c + '|' + k]);
    const tip = `${esc(s[0])}${un}${s[1] ? ' ± ' + esc(s[1]) + un + dag + ' (99.9% CI over forks)' : ''}; ${m[4]} fork${m[4] > 1 ? 's' : ''}, ${rounds} round${rounds > 1 ? 's' : ''}${fromProfile(d, k) ? ' of the profile pass' : ''}`
      + (m[1] == null ? '; 1 fork: no spread yet' : m[6] ? `. ${POOLED}: ${(100 * m[1] / m[0]).toFixed(1)}%` : `, sd of the forks’ means ${(100 * m[1] / m[0]).toFixed(1)}%`)
      + (ws ? `. ±~ ${esc(ws)}${un} ${m[4] > 1 ? '(root mean square over its forks) ' : ''}is the 99.9% CI ${WITHIN}` : '')
      + (w && w[1] != null ? `. Between/within-fork sd ratio ${w[1].toFixed(1)}${m[6] ? ' (between: pooled)' : ''}: ≈1, forks agree; ≫1, forks land in different places, so more forks pay off` : '')
      + (hot ? '. ' + esc(hotTip(x)) : '') + '. Click for its rounds';
    return cellBtn(c, v, `${g ? ' bar' : ''}${m[2] != null && m[6] ? ' pl' : ''}`, g, tip, hot + n);
  }
  // the corpora the filter bar picked, all when it picked none of these
  function corpora(d) {
    const cs = d.corpora.filter(c => !filter.size || filter.has(c));
    return cs.length ? cs : d.corpora;
  }
  // a commit's profile cells (in <campaign>.profile): a badge opening its flame graphs in the lightbox, every graph of
  // every profiled corpus in its group
  // a badge opening a commit's flame graphs in the lightbox: per corpus [corpus, {graphs}], every graph in its group
  function graphBadge(group, per, label, tip) {
    const gs = per.flatMap(([cp, x]) => (x.graphs || []).map(g => [per.length > 1 ? `${cp} · ${g[0]}` : g[0], g[1], g[2]]));
    if (!gs.length) return '';
    return ` <span class="bh-pf" data-lb-group="${esc(group)}">`
      + gs.map((g, i) => `<a class="bh-pb"${i ? ' hidden' : ''} href="${esc(g[2])}" data-lb="${esc(g[0])}|${esc(g[1])}" title="${esc(tip)}">${label}</a>`).join('')
      + '</span>';
  }
  function profBadge(d, c) {
    const P = d.profile;
    if (!P) return '';
    const per = P.corpora.map(cp => [cp, (P.cells[cp] || {})[c.v]]).filter(x => x[1]);
    if (!per.length) return '';
    const tip = `flame graphs of its profile${per.length > 1 ? 's' : ''} (${P.campaign}: ${per.map(x => x[0]).join(', ')})`;
    return graphBadge(`${P.campaign} · ${c.short.slice(0, 7)}`, per, 'profile', tip)
      || (per.some(x => x[1].state === 'running') ? ' <span class="bh-pb run" title="its profile is running">profiling</span>'
        : ' <span class="bh-pb" title="profiled; its flame graphs are not rendered yet">profiled</span>');
  }
  // the flame graphs of the commit's own cells, when the campaign measures under an async profile
  function ownBadge(el, d, c) {
    const per = d.corpora.map(cp => [cp, cellOf(d, cp, c.v)]).filter(x => x[1] && x[1].graphs && x[1].graphs.length);
    if (!per.length) return '';
    const tip = `flame graphs of its cells (${d.measureProfile || 'profiled'}, as measured: ${per.map(x => x[0]).join(', ')})`;
    return graphBadge(`${el.dataset.campaign} · ${c.short.slice(0, 7)}`, per, 'graphs', tip);
  }
  function drawTable(el, d, st) {
    const cs = corpora(d), m2 = st.m2 !== 'none' ? metric(d, st.m2) : null, m1 = metric(d, 'score');
    const exts = {};
    for (const c of cs) for (const m of [m1, m2]) if (m) exts[c + '|' + m.k] = extent(d, c, m.k, false);
    const per = m2 ? 4 : 2, open = memOf(el).open;
    let h = '<div class="scroll"><table class="t bh-t"><tr><th class="cm" rowspan="2">commit</th>'
      + cs.map(c => `<th class="cg gs" colspan="${per}">${esc(c)}</th>`).join('') + '</tr><tr>'
      + cs.map(() => th(d, 'score', 'n gs') + '<th>Δ</th>' + (m2 ? th(d, m2.k, 'n') + '<th>Δ</th>' : '')).join('') + '</tr>';
    for (const c of d.commits) {
      const sel = st.sel.includes(c.v), merged = c.merged.length, opened = merged && open.has(c.v);
      h += `<tr data-v="${esc(c.v)}" class="${sel ? 'sel' : ''}${opened ? ' has-sub' : ''}"><td class="cm"><div class="bh-cm">`
        + `<input type="checkbox" data-bsel="${esc(c.v)}"${sel ? ' checked' : ''} aria-label="compare ${esc(c.short)}">`
        + `<span class="bh-c"><span class="bh-subj" title="${esc(c.subject)}">${sha(c, 7)} ${esc(c.subject)}</span>`
        + `<span class="bh-who" title="${esc(c.date)}">${esc(c.author)} · ${esc(c.shown)}`
        + (merged ? `<button class="bh-mg" data-bmerge="${esc(c.v)}" aria-expanded="${!!opened}" title="a merge of ${merged} commit${merged > 1 ? 's' : ''}: list them">+${merged}</button>` : '')
        + ownBadge(el, d, c) + profBadge(d, c) + '</span></span></div></td>';
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
    let g = '', bands = '', hits = '', xl = '', hotSeen = false;
    const lines = ['', ''];
    const every = Math.max(1, Math.ceil(56 / band));
    order.forEach((cm, i) => {
      bands += `<rect class="band${st.sel.includes(cm.v) ? ' sel' : ''}" data-bband="${esc(cm.v)}" x="${f1(L + i * band)}" y="${T}" width="${f1(band)}" height="${H - T - B}"/>`;
      hits += `<rect class="hit" data-bhv="${esc(cm.v)}" x="${f1(L + i * band)}" y="${T}" width="${f1(band)}" height="${H - T}"/>`;
      const x = cells[cm.v];
      if ((N - 1 - i) % every === 0)
        xl += `<text class="${x && x.state === 'done' && x.m.score ? '' : 'un'}" x="${f1(X(i))}" y="${H - B + 14}" text-anchor="middle">${esc(cm.short.slice(0, 7))}</text>`;
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
        const forks = (x.raw || {})[m.k] || [], wf = (x.wf || {})[m.k] || [];
        // the iterations other load disturbed (`hot`, of the measurement's forks; not the profile pass's) as rings
        const hot = new Set(fromProfile(d, m.k) ? [] : (x.hot || []).map(p => p.join(',')));
        forks.forEach((f, fi) => f.forEach((s, si) => {
          const px = f1(cx + jit(i * 7 + n, j++) * spread), py = f1(y(s));
          if (hot.has(fi + ',' + si)) { hotSeen = true; g += `<circle class="hot" cx="${px}" cy="${py}" r="2.6"><title>${esc(hotTip(x))}</title></circle>`; }
          else g += `<circle class="c${n}" cx="${px}" cy="${py}" r="1.7"/>`;
        }));
        // each fork's mean, a short dash: the unit the interval is over; and its 99.9% CI over its own iterations, a thin
        // whisker on the dash's right half (the commit's bar, over forks, is at its centre)
        forks.forEach((f, fi) => {
          if (!f.length) return;
          const fm = f.reduce((p, s) => p + s, 0) / f.length, fy = f1(y(fm));
          g += `<path class="f${n}" d="M${f1(cx - spread * 0.5)} ${fy}h${f1(spread)}"/>`;
          if (wf[fi] != null) { const wx = f1(cx + spread * (0.12 + 0.36 * (fi + 0.5) / forks.length)); g += `<path class="w${n}" d="M${wx} ${f1(y(fm - wf[fi]))}V${f1(y(fm + wf[fi]))}"/>`; }
        });
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
        ax += `<line class="gl" x1="${L}" x2="${W - R}" y1="${f1(y(t))}" y2="${f1(y(t))}"/><text class="yl" x="${L - 5}" y="${f1(y(t) + 3.5)}" text-anchor="end">${tick(m1.kind, t, s)}</text>`;
    }
    if (e2) {
      const y = Y(e2), s = step(e2[1] - e2[0]);
      ax += `<line class="ax" x1="${W - R}" x2="${W - R}" y1="${T}" y2="${H - B}"/>`;
      for (let t = Math.ceil(e2[0] / s) * s; t <= e2[1]; t += s)
        ax += `<text class="yl" x="${W - R + 5}" y="${f1(y(t) + 3.5)}">${tick(m2.kind, t, s)}</text>`;
    }
    const empty = !e1 && !e2 ? `<text x="${(L + W - R) / 2}" y="${H / 2}" text-anchor="middle">nothing measured on ${esc(c)} yet</text>` : '';
    const pick = d.corpora.length > 1 ? `<div class="bh-ctl"><span class="fg"><span class="fl">${esc(d.corpusParam || 'corpus')}</span>`
      + d.corpora.map(x => `<button class="chip" data-bc="${esc(x)}" aria-pressed="${x === c}">${esc(x)}</button>`).join('') + '</span></div>' : '';
    box.innerHTML = `<figure>${pick}<div class="bh-leg"><span><i></i>${esc(heading(d, 'score'))} (left)</span>`
      + (m2 ? `<span><i class="s2"></i>${esc(heading(d, m2.k))} (right)</span>` : '')
      + '<span>oldest → newest · error bars: 99.9% CI over forks (lighter, †: a spread pooled over the corpus’s commits) · dashes: each fork’s mean, '
      + '<i class="wh" style="background:var(--link)"></i>its own 99.9% CI over its iterations · faint dots: every iteration</span>'
      + (hotSeen ? '<span><i class="hot"></i>an iteration while other load was over the gate’s limit</span>' : '') + '</div>'
      + `<svg class="bh-g" viewBox="0 0 ${W} ${H}">${bands}${ax}<path class="l1" d="${lines[0]}"/><path class="l2" d="${lines[1]}"/>${g}${xl}${empty}${hits}</svg>`
      + '<p class="bh-tip k">Hover a commit to see its numbers; click to select it.</p></figure>';
  }
  function tipText(d, st, v) {
    const cm = d.commits.find(c => c.v === v), x = cellOf(d, st.c, v);
    if (!cm) return '';
    const val = k => { const m = x && x.state === 'done' && x.m[k]; if (!m) return ''; const s = shown(d, k, m, x.s[k]); return `${esc(s[0])}${s[1] ? ' ± ' + esc(s[1]) + (m[6] ? '†' : '') : ''}`; };
    const m2 = st.m2 !== 'none' ? metric(d, st.m2) : null;
    const nums = !x ? 'pending' : x.state === 'running' ? 'running' : x.state === 'failed' ? 'run failed: ' + esc(x.why)
      : (val('score') ? `${val('score')} ${esc(heading(d, 'score'))} ${delta(x.d.score)}` : 'score pending')
        + (m2 && val(m2.k) ? ` · ${val(m2.k)} ${esc(heading(d, m2.k))} ${delta(x.d[m2.k])}` : '');
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
    // (per metric: the profile pass's against the commit profiled before it, its Δ column too)
    const base = (c, k) => { if (!one) return picked[0].v; const x = cellOf(d, c, b.v) || {}; return (k && (x.pv || {})[k]) || x.prev; };
    const head = one ? `<h4>${sha(b)} against the commit measured before it</h4><span class="k">tick a second row to compare any two</span>`
      : `<h4>${sha(picked[0])} → ${sha(b)}</h4><span class="k">${esc(picked[0].subject)} → ${esc(b.subject)}</span>`;
    // the corpora both have results on
    cs = cs.filter(c => d.metrics.some(m => pairDelta(cellOf(d, c, base(c, m.k)), cellOf(d, c, b.v), m.k)));
    let rows = '';
    for (const m of d.metrics) {
      const tds = cs.map(c => {
        const bv = base(c, m.k), a = cellOf(d, c, bv), y = cellOf(d, c, b.v), x = pairDelta(a, y, m.k);
        const vs = bv !== base(c) && byV(bv) ? ` (vs ${sha(byV(bv), 7)})` : '';
        return x ? `<td>${delta(x)}<span class="ab">${esc(shown(d, m.k, a.m[m.k], a.s[m.k])[0])} → ${esc(shown(d, m.k, y.m[m.k], y.s[m.k])[0])}${vs}</span></td>` : '<td></td>';
      });
      const t = headTip(d, m.k);
      if (tds.some(t => t !== '<td></td>')) rows += `<tr><td${t ? ` title="${esc(t)}"` : ''}>${esc(heading(d, m.k))}</td>${tds.join('')}</tr>`;
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
  // a score as `ui.num` shows it: four significant digits, whole numbers with separators from 1,000; with `like`, an
  // error to its score's decimals
  function num(x, like) {
    if (like == null) return Math.abs(x) >= 1000 ? Math.round(x).toLocaleString('en') : `${+x.toPrecision(4)}`;
    const dec = (num(like).split('.')[1] || '').length;
    return x.toLocaleString('en', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  }
  // a commit × corpus's popover: its rounds (forks, score ± the CI within each fork, load, state, timeline, logs and
  // flame graphs, and on the server Void & rerun), then its voided cells, which count for nothing
  function popover(d, name, c, v, server) {
    const cm = d.commits.find(k => k.v === v) || {sha: v, short: v, subject: ''}, x = cellOf(d, c, v) || {};
    const BADGE = {done: 'done', failed: 'failed', running: 'running'};
    let h = `<div class="ph"><h4 id="bh-pop-t">${sha(cm, 7)} on ${esc(c)} <span class="k">${esc(cm.subject)}</span></h4>`
      + '<button type="button" class="x" data-bpclose="1" aria-label="Close" title="Close (Esc)">✕</button></div>'
      + `<div class="k">Each fork’s mean ${esc(heading(d, 'score'))} ± its 99.9% CI ${WITHIN}.</div><ul>`;
    for (const r of x.rd || []) {
      const key = [name, c, v, r.round].join('|');
      const a = act[key] = act[key] || {camp: name, c, v, round: r.round, reason: (r.disturbed || []).length ? 'disturbed by other load' : ''};
      const fks = (r.forks || []).map((f, i) => `<span class="fk">${r.forks.length > 1 ? `fork ${i + 1}: ` : ''}<b>${esc(num(f.mean))}</b>`
        + `${f.ci != null ? ` <span class="pm">± ${esc(num(f.ci, f.mean))}</span>` : ''} <span class="k">${f.n} iteration${f.n > 1 ? 's' : ''}</span></span>`).join(' · ');
      h += `<li><div class="rh"><b>#${esc(r.round)}</b> <span class="badge ${BADGE[r.state] || 'partial'}">${esc(r.state)}</span> ${fks}`
        + (r.load != null ? ` <span class="k" title="the most other load over any of its measurement iterations">other load ≤ ${r.load.toFixed(1)} cores${r.maxCores != null ? `, limit ${esc(r.maxCores)}` : ''}</span>` : '')
        + '</div>' + (r.why ? `<div class="dz bh-fail">${esc(r.why)}</div>` : '')
        + runs(r.disturbed || []).map(z => `<div class="dz"><span class="bh-hot"></span>${esc(itName(z))}: ${esc(coresOf(z))}${z.top ? ` <span class="k">${esc(z.top)}</span>` : ''}</div>`).join('');
      const L = r.links || {};
      const links = (L.timeline ? `<a class="btn" href="${esc(L.timeline)}" data-lb="timeline" title="each fork from JVM start to exit: iterations, GC pauses, load">timeline</a>` : '')
        + (L.jmh ? `<a class="btn" href="${esc(L.jmh)}">jmh.log</a>` : '') + (L.build ? `<a class="btn" href="${esc(L.build)}">build.log</a>` : '')
        + (r.graphs || []).map(g => `<a class="btn" href="${esc(g[2])}" data-lb="${esc(g[0])}|${esc(g[1])}">${esc(g[0])} ${esc(g[1])}</a>`).join('');
      if (links) h += `<div class="btns" data-lb-group="${esc(name)} · ${esc(c)} · ${esc(cm.short.slice(0, 7))} #${esc(r.round)}">${links}</div>`;
      if (server && (r.state === 'done' || r.state === 'failed')) {
        const k = esc(key);
        h += '<div class="act">' + (a.done ? ''
          : a.form ? `<input type="text" data-bvreason="${k}" value="${esc(a.reason)}" placeholder="why it is voided" aria-label="why round ${esc(r.round)} is voided"${a.busy ? ' disabled' : ''}>`
            + `<button type="button" class="chip warn" data-bvgo="${k}"${a.busy ? ' disabled' : ''}>Void &amp; rerun</button><button type="button" class="chip" data-bvcancel="${k}"${a.busy ? ' disabled' : ''}>cancel</button>`
          : `<button type="button" class="chip" data-bvopen="${k}" title="move this cell to .void with a reason, and queue the campaign’s resume, which measures it again">Void &amp; rerun…</button>`)
          + (a.msg ? `<span class="msg${a.err ? ' err' : ''}" role="status">${a.msg}</span>` : '') + '</div>';
      }
      h += '</li>';
    }
    for (const z of x.void || []) {
      const L = z.links || {};
      const links = (L.timeline ? `<a class="btn" href="${esc(L.timeline)}" data-lb="timeline">timeline</a>` : '') + (L.jmh ? `<a class="btn" href="${esc(L.jmh)}">jmh.log</a>` : '');
      h += `<li class="void"><div class="rh"><b>#${esc(z.round)}</b> <span>voided: <span class="why">${esc(z.why || 'no reason given')}</span></span> <span class="k">${esc(z.when)}</span></div>`
        + (links ? `<div class="btns" data-lb-group="${esc(name)} · ${esc(c)} · ${esc(cm.short.slice(0, 7))} #${esc(z.round)} (voided)">${links}</div>` : '') + '</li>';
    }
    if (!(x.rd || []).length && !(x.void || []).length) h += '<li class="k">No rounds yet.</li>';
    return h + '</ul>' + (server ? '' : '<div class="k" style="margin-top:4px">Served by <code>perflab server</code>, a round can be voided and measured again here.</div>');
  }
  const elOf = camp => [...document.querySelectorAll('.bh')].find(e => e.dataset.campaign === camp);
  function popBox() {
    let box = document.getElementById('bh-pop');
    if (!box) {
      box = document.createElement('div');
      Object.assign(box, {id: 'bh-pop', hidden: true, tabIndex: -1});
      box.setAttribute('role', 'dialog');
      box.setAttribute('aria-labelledby', 'bh-pop-t');
      document.body.appendChild(box);
    }
    return box;
  }
  function renderPop(el, force) {
    const box = popBox(), a = document.activeElement;
    if (!pop || !el || (!force && box.contains(a) && a.tagName === 'INPUT')) return;  // a refresh waits while its reason is typed
    const h = popover(data(el), pop.camp, pop.c, pop.v, !!SERVER);
    if (force || box._h !== h) { box.innerHTML = h; box._h = h; }
  }
  const triggers = () => document.querySelectorAll('[data-bcell]');
  function openPop(el, c, v, trigger) {
    pop = {camp: el.dataset.campaign, c, v};
    const box = popBox();
    renderPop(el, true);
    box.hidden = false;
    triggers().forEach(t => t.setAttribute('aria-expanded', String(t.dataset.bcell === c && t.dataset.bcv === v && t.closest('.bh') === el)));
    if (!matchMedia('(max-width:600px)').matches) {  // beside its value; on a phone, a sheet along the bottom
      const r = trigger.getBoundingClientRect(), w = box.offsetWidth, hgt = box.offsetHeight;
      const left = Math.max(8, Math.min(r.right - w, innerWidth - w - 8));
      const below = r.bottom + 4 + hgt <= innerHeight || r.top - 4 - hgt < 0;
      box.style.left = `${left + scrollX}px`;
      box.style.top = `${(below ? r.bottom + 4 : r.top - 4 - hgt) + scrollY}px`;
    }
    box.focus({preventScroll: true});
  }
  function closePop(refocus) {
    const box = document.getElementById('bh-pop');
    if (!pop || !box) return;
    const was = pop;
    pop = null;
    box.hidden = true;
    triggers().forEach(t => t.setAttribute('aria-expanded', 'false'));
    const el = elOf(was.camp), t = el && [...el.querySelectorAll('[data-bcell]')].find(t => t.dataset.bcell === was.c && t.dataset.bcv === was.v);
    if (refocus && t) t.focus({preventScroll: true});
  }
  async function voidRound(key) {
    const a = act[key];
    if (!a || a.busy) return;
    const el = elOf(a.camp), redraw = () => { const box = document.getElementById('bh-pop'); if (box) box._h = null; renderPop(el, true); };
    Object.assign(a, {busy: true, err: false, msg: 'voiding…'});
    redraw();
    try {
      const r = await bhVoid(a.camp, a.c, a.v, a.round, a.reason.trim());
      const j = (r.rerun && r.rerun.job) || {}, again = r.rerun && r.rerun.deduped;  // api.rerun: {job, deduped}
      Object.assign(a, {done: true, msg: `voided; ${again ? 'the rerun already queued measures it' : 'its rerun is queued'}`
        + `${j.id != null ? ` as <a href="/#job-${esc(j.id)}">job ${esc(j.id)}</a>` : ''}. The round moves under “voided” when the index next refreshes.`});
    } catch (e) {
      Object.assign(a, {err: true, done: e.stage === 'rerun', msg: (e.stage === 'rerun' ? 'voided, but its rerun was not queued: ' : 'not voided: ') + esc(e.message || e)});
    }
    a.busy = false;
    redraw();
    const box = document.getElementById('bh-pop');  // its controls were redrawn: keep the focus in the popover
    if (box && !box.hidden && !box.contains(document.activeElement)) box.focus({preventScroll: true});
  }
  document.addEventListener('click', e => {
    const box = document.getElementById('bh-pop');
    if (!pop || !box) return;
    const t = e.target.closest && e.target.closest('[data-bpclose],[data-bvopen],[data-bvcancel],[data-bvgo]');
    if (t && box.contains(t)) {
      const a = act[t.dataset.bvopen || t.dataset.bvcancel || t.dataset.bvgo];
      if (t.dataset.bpclose) return closePop(true);
      if (!a) return;
      if (t.dataset.bvgo) return voidRound(t.dataset.bvgo);
      a.form = !!t.dataset.bvopen;
      renderPop(elOf(a.camp), true);
      const inp = box.querySelector('[data-bvreason]');
      if (inp) { inp.focus(); inp.select(); }
      return;
    }
    // a click elsewhere closes it (not one on a value, which opens its own, nor in the lightbox over it)
    if (!box.contains(e.target) && !(e.target.closest && e.target.closest('[data-bcell],#lb'))) closePop(false);
  });
  document.addEventListener('input', e => { const k = e.target.dataset && e.target.dataset.bvreason; if (k && act[k]) act[k].reason = e.target.value; });
  document.addEventListener('keydown', e => {
    if (!pop || e.defaultPrevented) return;
    const lb = document.getElementById('lb');
    if (lb && !lb.hidden) return;  // Esc is the lightbox's first
    const k = e.target.dataset && e.target.dataset.bvreason;
    if (e.key === 'Enter' && k) { e.preventDefault(); voidRound(k); }
    else if (e.key === 'Escape') { e.preventDefault(); closePop(true); }
  });
  function drawOne(el) {
    const d = data(el), st = state(el), others = d.metrics.filter(m => m.k !== 'score');
    const opts = ms => ms.map(m => `<option value="${esc(m.k)}"${m.k === st.m2 ? ' selected' : ''}${m.src === 'profile' ? ` title="${esc(headTip(d, m.k))}"` : ''}>${esc(heading(d, m.k))}</option>`).join('');
    const chip = (a, v, on, label, t) => `<button class="chip" ${a}="${v}" aria-pressed="${on}"${t ? ` title="${t}"` : ''}>${label}</button>`;
    el.querySelector('.bh-ctl').innerHTML = '<span class="fg"><span class="fl">show</span>'
      + chip('data-bform', 'bar', st.form === 'bar', 'shaded', 'a bar behind each value, on a scale shared down the column; its lighter end is the CI')
      + chip('data-bform', 'num', st.form === 'num', 'numbers', 'mean ± CI only') + '</span>'
      + `<span class="fg">${chip('data-bchart', '1', st.chart, 'chart', 'commits on x, the score left, the second metric right')}</span>`
      + '<label class="fg"><span class="fl">second metric</span><select data-bm2><option value="none">none</option>'
      + opts(others.filter(m => m.src !== 'profile'))
      + (others.some(m => m.src === 'profile') ? `<optgroup label="profile pass (${esc((d.profile || {}).campaign || '')})">${opts(others.filter(m => m.src === 'profile'))}</optgroup>` : '')
      + '</select></label>';
    drawChart(el, d, st); drawTable(el, d, st); drawCompare(el, d, st);
    if (pop && pop.camp === el.dataset.campaign) renderPop(el);
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
    const el = e.target.closest && e.target.closest('.bh'), t = el && e.target.closest('[data-bform],[data-bchart],[data-bc],[data-bmerge],[data-bhv],[data-bclear],[data-bprof],[data-bcopy],[data-bcell]');
    if (!t) return;
    if (t.dataset.bcell != null) { if (pop && pop.camp === el.dataset.campaign && pop.c === t.dataset.bcell && pop.v === t.dataset.bcv) closePop(false); else openPop(el, t.dataset.bcell, t.dataset.bcv, t); }
    else if (t.dataset.bform) update(el, st => { st.form = t.dataset.bform; });
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
  return {draw, popover};
})();
"""
