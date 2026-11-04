"""The metrics of a campaign's cells, for its summary (the index's campaign card) and `perflab ab report`: the score,
the benchmark threads' cycles, instructions and IPC, allocation, and every PMU counter a cell recorded, with its
per-kinst or %-of-cycles form, then the thread groups' share of cycles and IPC. Nothing is named by event: an xctrace
template's counters come from result.json, an async kperf profile's from its recording (`hw_events`).

XctraceProfiler's per-op counts (`xctrace.<event>`) are of the benchmark threads already; it reports JIT, GC and other
threads beside them as `xctrace.cycles%.<group>` and `xctrace.IPC.<group>`, from which the all-thread cycles,
instructions and IPC are derived (not shown in the table: the pivot and chart offer them).

With a spec's "perUnit" (an aux counter of the benchmark, e.g. "files"), counts, allocation and the score are divided
by that counter's units per op (its sum over the measurement iterations over their ops), so variants that do different
amounts of work per op compare: cycles/file, not cycles/op. Ratios (IPC, /kinst, % of cycles) stay as they are.
"""
import functools, glob, json, math, os, plistlib, random, re, statistics
from typing import NamedTuple

# events counting cycles are shown as % of cycles, the others per 1,000 instructions: by the event's description in
# macOS's PMU event database (kpep), else by its name, as XctraceProfiler does
KPEP = "/usr/share/kpep"
CYCLE_EVENT = re.compile(r"WAITING|STALL|BUBBLE|CYCLE")
JMH_TIME_MS = {"ns": 1e-6, "us": 1e-3, "ms": 1, "s": 1000, "min": 60_000, "hr": 3_600_000, "day": 86_400_000}
GROUPS = ("jit", "gc", "other")
TOP_DOWN = ("useful", "processing", "delivery", "discarded")  # Instruments' "CPU Counters" template, % of the bench's
# JitProfiler's per-fork totals (jit.<name> in result.json): compilations, compile time and deopts while measuring and
# in the last warmup iteration; (name, label)
JIT = (("compilations", "JIT compilations while measuring"), ("compileTime", "JIT compile ms while measuring"),
       ("deopts", "deopts while measuring"), ("lastWarmup.compilations", "JIT compilations, last warmup"),
       ("lastWarmup.deopts", "deopts, last warmup"))
EVENTS_NAME = "hw-events.json"  # per cell: an async kperf profile's events on the benchmark threads
EVENTS_FORMAT = 2  # {"format", "totals": {event: n}}; the first was {event: n per op}


def ops(r):
    """A fork's measured ops: JMH runs whole ops until the iteration time is up, so an iteration with mean op time t has
    ceil(time / t) ops (avgt); one op per iteration otherwise. The mean over forks."""
    raw = r["primaryMetric"].get("rawData") or []
    if r.get("mode") != "avgt" or not raw:
        return r.get("measurementIterations", 1) * r.get("measurementBatchSize", 1)
    n, unit = r["measurementTime"].split()
    if unit not in JMH_TIME_MS:
        raise ValueError(f"measurementTime {r['measurementTime']!r}: unknown unit")
    iteration_ms = float(n) * JMH_TIME_MS[unit]
    return sum(math.ceil(iteration_ms / t) for fork in raw for t in fork) / len(raw)


@functools.cache
def kpep_descriptions():
    """{event: description} from every CPU's kpep database (an event's description is the same across them)."""
    out = {}
    for f in glob.glob(os.path.join(KPEP, "*.plist")):
        try:
            events = plistlib.load(open(f, "rb"))["system"]["cpu"]["events"]
        except (OSError, KeyError, plistlib.InvalidFileException):
            continue
        for name, e in events.items():
            out.setdefault(name, e.get("description", ""))
    return out


def counts_cycles(event):
    """Whether a PMU event counts cycles ("Cycles while ..."), not occurrences."""
    d = kpep_descriptions().get(event.upper())
    return d.startswith("Cycles") if d is not None else bool(CYCLE_EVENT.search(event.upper()))


def unit_name(counter):
    """An aux counter's unit in labels: files -> file (cycles/file)."""
    return counter.removesuffix("s")


def units_per_op(r, per_unit):
    """The aux counter `per_unit` per op (JMH sums an events counter over the iterations), None if not recorded."""
    m = r.get("secondaryMetrics", {})
    if per_unit not in m or not m[per_unit]["score"]:
        return None
    return m[per_unit]["score"] / ops(r)


def hw_events(cell, profile, jfrconv=None):
    """An async kperf profile's events (`async:cycles+instructions`) per op on the benchmark threads, from the cell's
    recording through jfrconv; the totals are kept in the cell's hw-events.json. {} for other profiles."""
    from . import regraph
    events = [label.removeprefix("hw-") for label, _ in regraph.events_of(profile) if label.startswith("hw-")]
    f = os.path.join(cell, EVENTS_NAME)
    if not events or not glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True):
        return {}
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(os.path.join(cell, "result.json")):
        return cached_hw_events(cell)
    from . import profdiff
    totals = {}
    for e in events:  # streamed: a recording's collapsed stacks can run to gigabytes
        totals[e] = profdiff.load(cell, e, jfrconv, None, "events", keep=False)["total"]
    json.dump({"format": EVENTS_FORMAT, "totals": totals}, open(f, "w"), indent=1)
    return per_op_events(cell, totals)


def per_op_events(cell, totals):
    from . import profdiff
    try:
        ops = profdiff.ops_of(cell)
    except (OSError, ValueError, KeyError, IndexError):
        return {}
    return {e: n / ops for e, n in totals.items()} if ops else {}


def old_ops(r):
    """The op count of an hw-events.json before EVENTS_FORMAT 2: ceil(time / t) per iteration, whatever the mode."""
    n, unit = r["measurementTime"].split()
    return sum(math.ceil(float(n) * JMH_TIME_MS[unit] / t) for t in r["primaryMetric"]["rawData"][0])


def cached_hw_events(cell):
    """What `hw_events` kept for the cell, without running jfrconv (the index is rebuilt every few seconds). A file of
    the first format (events per op, by an op count that was wrong in SingleShotTime) is rewritten as totals."""
    f = os.path.join(cell, EVENTS_NAME)
    try:
        c = json.load(open(f))
    except (OSError, ValueError):
        return {}
    if c.get("format") != EVENTS_FORMAT:
        try:
            ops = old_ops(json.load(open(os.path.join(cell, "result.json")))[0])
        except (OSError, ValueError, KeyError, IndexError):
            return {}
        c = {"format": EVENTS_FORMAT, "totals": {e: x * ops for e, x in c.items()}}
        t = os.stat(f)
        json.dump(c, open(f, "w"), indent=1)
        os.utime(f, (t.st_atime, t.st_mtime))  # still as fresh as it was against result.json
    return per_op_events(cell, c["totals"])


def of(r, per_unit=None, hw=None):
    """A JMH result's metrics: [(key, label, kind, main, value)]. `kind` picks the format and Δ floor (score, count,
    alloc, ratio, pct, total); `main` ones are the summary table's columns. `hw` is an async kperf profile's events per op."""
    m = r.get("secondaryMetrics", {})
    get = lambda k: m[k]["score"] if k in m else None
    u, per = 1.0, "op"
    if per_unit:
        u, per = units_per_op(r, per_unit), unit_name(per_unit)
    norm = lambda x: None if x is None or u is None else x / u
    unit = r["primaryMetric"].get("scoreUnit", "")
    out = [("score", unit.replace("/op", f"/{per}") if per_unit else unit, "score", True, norm(r["primaryMetric"]["score"]))]
    hw = hw or {}
    xc = {k.removeprefix("xctrace."): v["score"] for k, v in m.items()
          if k.startswith("xctrace.") and v.get("scoreUnit") == "#/op"}
    cyc = xc.pop("CORE_ACTIVE_CYCLE", None) or hw.get("cycles")
    ins = xc.pop("INST_ALL", None) or hw.get("instructions")
    out += [("cycles", f"cycles/{per}", "count", True, norm(cyc)), ("instructions", f"instructions/{per}", "count", True, norm(ins)),
            ("ipc", "IPC", "ratio", True, get("xctrace.IPC.bench") or (ins / cyc if ins and cyc else None)),
            ("alloc", f"alloc/{per}", "alloc", True, norm(get("gc.alloc.rate.norm")))]
    counters = [(e, x, get(f"xctrace.{e}/kinst"), get(f"xctrace.{e}/cycles")) for e, x in xc.items()]
    for e, x in hw.items():
        if e not in ("cycles", "instructions"):
            cycles_kind = counts_cycles(e)
            counters.append((e, x, 1000 * x / ins if ins and not cycles_kind else None, 100 * x / cyc if cyc and cycles_kind else None))
    for e, x, kinst, pct in counters:
        out.append((f"ev:{e}", f"{e}/{per}", "count", True, norm(x)))
        if kinst is not None:
            out.append((f"ev:{e}/kinst", f"{e}/kinst", "ratio", True, kinst))
        if pct is not None:
            out.append((f"ev:{e}/cycles", f"{e} % of cycles", "pct", True, pct))
    for t in TOP_DOWN:
        if get(f"xctrace.{t}.bench") is not None:
            out.append((f"td:{t}", f"{t} %", "pct", True, get(f"xctrace.{t}.bench")))
    bench_pct = get("xctrace.cycles%.bench")
    if bench_pct:
        for g in GROUPS:
            if get(f"xctrace.cycles%.{g}") is not None:
                out.append((f"cyc%:{g}", f"{g.upper() if g != 'other' else g} % of cycles", "pct", g != "other", get(f"xctrace.cycles%.{g}")))
        for g in GROUPS:
            if get(f"xctrace.IPC.{g}") is not None:
                out.append((f"ipc:{g}", f"IPC {g.upper() if g != 'other' else g}", "ratio", False, get(f"xctrace.IPC.{g}")))
        if cyc:
            # every thread of the JVM: the bench's cycles over its share, instructions from each group's share and IPC
            all_cyc = cyc / (bench_pct / 100)
            groups = ["bench", *GROUPS]
            if all(get(f"xctrace.IPC.{g}") is not None or not get(f"xctrace.cycles%.{g}") for g in groups):
                all_ins = all_cyc * sum((get(f"xctrace.cycles%.{g}") or 0) / 100 * (get(f"xctrace.IPC.{g}") or 0) for g in groups)
            else:
                all_ins = None
            out += [("cycles:all", f"cycles/{per}, all threads", "count", False, norm(all_cyc)),
                    ("instructions:all", f"instructions/{per}, all threads", "count", False, norm(all_ins)),
                    ("ipc:all", "IPC, all threads", "ratio", False, all_ins / all_cyc if all_ins else None)]
    for name, label in JIT:
        jm = m.get(f"jit.{name}")
        if jm:
            # JMH's score of these is the largest fork's (AggregationPolicy.MAX), so take the mean of the forks' own
            forks = [f[0] for f in jm.get("rawData") or [] if f and isinstance(f[0], (int, float))]
            out.append((f"jit:{name}", label, "total", False, sum(forks) / len(forks) if forks else jm["score"]))
    return [x for x in out if x[4] is not None]


def fmt(kind, x):
    from . import ui
    return {"score": ui.num, "count": ui.si, "alloc": ui.size, "ratio": lambda y: f"{y:.3g}", "total": ui.num, "pct": lambda y: f"{y:.1f}%"}[kind](x)


def higher_is_better(key, label=""):
    """Whether a rise in the metric `key` (labelled `label`) is an improvement: IPC (the benchmark's, a thread group's,
    all threads'), and a throughput score (ops/s); for every other metric lower is better."""
    return key == "ipc" or key.startswith("ipc:") or key == "score" and label.startswith("ops/")


def delta_ok(base, kind, per_unit):
    """Whether a percent change against `base` means anything; per unit, a count of a few is no longer about zero."""
    from . import ui
    return ui.delta_ok(base, "score" if per_unit and kind == "count" else kind)


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    mean = sum(xs) / len(xs)
    sd = (sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5 if len(xs) > 1 else 0.0
    return mean, sd


# Student's t at 0.9995 (a two-sided 99.9% interval, as JMH's scoreError) by degrees of freedom; between entries
# it is interpolated in 1/df, beyond the last it tends to the normal's 3.291
T999 = ((1, 636.62), (2, 31.599), (3, 12.924), (4, 8.610), (5, 6.869), (6, 5.959), (7, 5.408), (8, 5.041), (9, 4.781),
        (10, 4.587), (12, 4.318), (15, 4.073), (20, 3.850), (25, 3.725), (30, 3.646), (40, 3.551), (60, 3.460),
        (120, 3.373), (math.inf, 3.291))


def t999(df):
    for (d0, t0), (d1, t1) in zip(T999, T999[1:]):
        if df <= d1:
            if df <= d0:
                return t0
            w = (1 / d0 - 1 / df) / (1 / d0 - (0 if d1 == math.inf else 1 / d1))
            return t0 + w * (t1 - t0)
    return T999[-1][1]


def ci999(xs):
    """(mean, half-width of its 99.9% confidence interval) of samples taken as independent, as JMH's score ± error;
    the half-width is None for fewer than two."""
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    if not xs:
        return None, None
    mean, sd = stats(xs)
    return mean, (t999(len(xs) - 1) * sd / len(xs) ** 0.5 if len(xs) > 1 else None)


OWN_FORKS = 4  # from this many forks a group's spread is its own; before, the pooled one when it has more df


def fork_spread(mean, sd, n, pool):
    """(sd, df, pooled) of a group of `n` forks with mean `mean` and sd `sd`, given `pool` = pooled_rel_sd(...) of its
    kind: its own from OWN_FORKS forks; with fewer, the pooled relative sd when that has more degrees of freedom (always
    for one fork, which has none; with two, its own 99.9% CI would be t(1) = 637 sds, with three t(2) = 32). sd and df
    are None without either."""
    r, pdf = pool
    if n < 2 or (n < OWN_FORKS and r is not None and pdf > n - 1):
        return (None, None, False) if r is None else (r * abs(mean), pdf, True)
    return sd, n - 1, False


def pooled_rel_sd(groups):
    """(relative sd, df) pooled over groups of samples [(mean, sd, df)], each group's relative variance weighted by its
    df; (None, 0) when no group has df >= 1 and a nonzero mean. A spread for a group of one sample, from groups of the same
    kind that have more."""
    gs = [(sd / mean, df) for mean, sd, df in groups if df and df >= 1 and mean and sd is not None]
    df = sum(df for _, df in gs)
    return ((sum(df * r * r for r, df in gs) / df) ** 0.5, df) if df else (None, 0)


def welch(a, b):
    """Welch's t of b against a, each (mean, sd, n, df) of independent samples (sd and df may be a pool's): (Δ% of b
    against a, half-width in % of its 99.9% CI with the Welch–Satterthwaite df, that df). The half-width and df are None
    when either sd is unknown; Δ is None when a's mean is zero. The difference is significant at 99.9% exactly when
    |Δ| > half-width."""
    (ma, sa, na, dfa), (mb, sb, nb, dfb) = a, b
    if not ma or mb is None:
        return None, None, None
    d = 100 * (mb / ma - 1)
    if sa is None or sb is None:
        return d, None, None
    va, vb = sa * sa / na, sb * sb / nb
    if va + vb == 0:
        return d, 0.0, math.inf
    df = (va + vb) ** 2 / sum(v * v / f for v, f in ((va, dfa), (vb, dfb)) if v)
    return d, 100 * t999(df) * (va + vb) ** 0.5 / abs(ma), df


# ---- comparing variants or commits: the one rule every view (an A/B card, the branch view, the API, `perflab ab
# report`) gives a Δ. The fork is the unit: a metric's value per fork is the mean of its measurement iterations
# (`fork_units`); a variant's or commit's is the mean over its forks ± the 99.9% CI over them (`fork_stats`, with a pooled
# sd for one of few forks); a Δ is Welch's t on the forks' means (`compare`), or for the median and min of every
# iteration a bootstrap over forks and iterations (`pooled_delta`). Either way it is ± the half-width of its 99.9% CI,
# and better or worse (`verdict`) only when that excludes zero.

# where a metric of `of` has per-iteration samples: the primary metric, or a secondary metric of result.json
RAW_SOURCE = {"score": None, "alloc": "gc.alloc.rate.norm", "cycles": "xctrace.CORE_ACTIVE_CYCLE", "instructions": "xctrace.INST_ALL"}


def raw_source(k):
    if k.startswith("jit:"):
        return f"jit.{k[4:]}"  # one sample per fork
    return RAW_SOURCE.get(k, f"xctrace.{k[3:]}" if k.startswith("ev:") and "/" not in k else False)


def raw_of(r, k, u):
    """The forks' measurement iterations of metric `k` in a JMH result, divided by `u` (units per op), [[x, ...] per fork]."""
    src = raw_source(k)
    if src is False:
        return []
    m = r["primaryMetric"] if src is None else r.get("secondaryMetrics", {}).get(src)
    if k.startswith("jit:"):
        u = 1.0  # a fork's total, not per op
    raw = (m or {}).get("rawData") or []
    return [[x / u for x in fork if isinstance(x, (int, float)) and math.isfinite(x)] for fork in raw] if u else []


def fork_units(rs, per_unit=None, prefix="", keep=lambda k, kind: True):
    """The metrics (`of`) of rounds `rs` ([(JMH result, hw events)]), those `keep` takes, keyed `prefix` + key:
    ({key: [per fork, the mean of its measurement iterations]}, {key: kind}, {key: [[iteration, ...] per fork]},
    [(key, label, kind, main)] in the order first seen). A metric without per-iteration samples has a value per round
    (JMH's mean over the round's forks)."""
    of_ = [of(r, per_unit, hw) for r, hw in rs]
    kinds, raw, us, cols = {}, {}, {}, []
    for ms in of_:
        for k, label, kind, main, _ in ms:
            if keep(k, kind) and prefix + k not in kinds:
                kinds[prefix + k] = kind
                cols.append((prefix + k, label, kind, main))
    for pk in kinds:
        k = pk[len(prefix):]
        forks = [f for r, _ in rs for f in raw_of(r, k, units_per_op(r, per_unit) if per_unit else 1.0) if f]
        if forks:
            raw[pk] = forks
        us[pk] = [sum(f) / len(f) for f in forks] or [x for ms in of_ for kk, _, _, _, x in ms if kk == k and x is not None and math.isfinite(x)]
    return us, kinds, raw, cols


def fork_stats(units):
    """{group (a variant, a commit): {key: [value per fork]}} -> {group: {key: (mean, sd, half-width of the mean's 99.9%
    CI, n forks, df, sd pooled)}}, the groups those to compare (a campaign's variants on a corpus, a branch's commits).
    sd, CI and df are None without a spread; for a group of few forks the sd is the relative sd pooled over the groups
    (`fork_spread`)."""
    stat = {g: {k: (*stats(xs), len(xs)) for k, xs in us.items() if xs} for g, us in units.items()}
    keys = {k for st in stat.values() for k in st}
    pool = {k: pooled_rel_sd([(st[k][0], st[k][1], st[k][2] - 1) for st in stat.values() if k in st]) for k in keys}
    out = {}
    for g, st in stat.items():
        out[g] = {}
        for k, (mean, sd, n) in st.items():
            sd, df, pooled_ = fork_spread(mean, sd, n, pool[k])
            out[g][k] = (mean, sd, None if sd is None else t999(df) * sd / n ** 0.5, n, df, pooled_)
    return out


def compare(a, b, ok=True, up=False):
    """`fork_stats` b against a: (Δ%, half-width of its 99.9% CI or None, `verdict`, a side's sd pooled), None when a's
    mean is zero. `ok`: a Δ against a means something (`delta_ok`); `up`: higher is better."""
    d, half, _ = welch((a[0], a[1], a[3], a[4]), (b[0], b[1], b[3], b[4]))
    return None if d is None else (d, half, verdict(d, half, ok, up), a[5] or b[5])


def verdict(d, half=None, ok=True, up=False):
    """A percent change's class: better or worse when its 99.9% CI (± `half`) excludes zero (lower is better, or with
    `up` higher, `higher_is_better`), flat when it does not or is unknown, na when the base is about zero."""
    return "na" if not ok else "flat" if half is None or abs(d) <= half or abs(d) < 0.005 else "worse" if (d > 0) != up else "better"


# ---- what JMH reports for a benchmark run with several forks (1.37: RunResult.getAggregatedResult takes every fork's
# iterations, ListStatistics their mean and, with N > 2, t(N - 1) * sd / sqrt(N)). A campaign forks once per cell, so its
# result.json files have this only per fork. Shown first on a card, it is not what a verdict rests on: it takes iterations
# as independent, while those of one fork share JIT decisions, code layout and GC state.

class Jmh(NamedTuple):
    score: float  # the mean of every iteration
    error: float | None  # JMH's scoreError, the 99.9% half-width; None (its NaN) with N <= 2
    n: int  # JMH's Cnt: forks x iterations
    sd: float | None  # the iterations' sd; None with N <= 2, for which JMH gives no interval


def jmh_score(forks):
    """What JMH reports for `forks` ([[x, ...] per fork]) as one run: a `Jmh`, or None without any iterations."""
    xs = [x for f in forks for x in f]
    if not xs:
        return None
    score, sd = stats(xs)
    n = len(xs)
    return Jmh(score, t999(n - 1) * sd / n ** 0.5, n, sd) if n > 2 else Jmh(score, None, n, None)


def jmh_delta(a, b, ok=True, up=False):
    """`Jmh` b against a by Welch's t over the pooled iterations: (Δ%, half-width of its 99.9% CI or None, the `verdict`
    such a test would give), None when a's score is zero. Far narrower than `compare`'s, and for that reason no verdict
    a view colours by."""
    d, half, _ = welch((a.score, a.sd, a.n, a.n - 1), (b.score, b.sd, b.n, b.n - 1))
    return None if d is None else (d, half, verdict(d, half, ok, up))


def of_jmh(key, forks):
    """`jmh_score` of a metric `key`, None for one JMH does not average: a JIT total's score is the largest fork's."""
    return None if key.startswith("jit:") else jmh_score(forks)


class Summary(NamedTuple):
    """A metric of a variant on a corpus, in `summarise`."""
    mean: float  # over forks
    ci: float | None  # half-width of its 99.9% CI
    d: float | None  # Δ% against the baseline, Welch's t on the forks' means: what `verdict` goes by
    half: float | None  # half-width of Δ's 99.9% CI
    ok: bool  # a Δ means something (`delta_ok`)
    n: int  # forks
    df: float | None  # of the sd behind `ci`
    pooled: bool  # that sd is `pooled_rel_sd`'s
    jmh: Jmh | None  # `of_jmh`, None without per-iteration samples
    jmh_d: tuple | None  # `jmh_delta` against the baseline


def summarise(variants, per_unit=None):
    """{variant: [(JMH result, hw events) per round]}, the first variant the baseline -> (columns [(key, label, kind,
    main)] in the order first seen, {variant: {key: `Summary`}}), by `fork_stats`, `compare`, `of_jmh` and `jmh_delta`."""
    per = {v: fork_units(rs, per_unit) for v, rs in variants.items()}
    jm = {v: {k: of_jmh(k, f) for k, f in raw.items()} for v, (_, _, raw, _) in per.items()}
    cols = {}
    for _, _, _, cs in per.values():
        for c in cs:
            cols.setdefault(c[0], c)
    st = fork_stats({v: us for v, (us, _, _, _) in per.items()})
    names = list(variants)
    base = st.get(names[0], {}) if names else {}
    out = {}
    for v in names:
        out[v] = {}
        for k, m in st[v].items():
            b = base.get(k)
            ok = delta_ok(b[0] if b else m[0], cols[k][2], per_unit)
            c = compare(b, m, ok) if b and v != names[0] else None
            j, ja = jm[v].get(k), jm.get(names[0], {}).get(k)
            up = higher_is_better(k, cols[k][1])
            out[v][k] = Summary(m[0], m[2], c and c[0], c and c[1], ok, m[3], m[4], m[5], j,
                                jmh_delta(ja, j, ok, up) if j and ja and v != names[0] else None)
    return list(cols.values()), out


# ---- distributions: statistics of every measured iteration, pooled over a variant's forks

STATS = ("mean", "median", "min")  # what a summary can show; mean is JMH's beside `fork_stats`'s (over forks), the rest `pooled`'s
BOOT = 200  # bootstrap resamples for the spread of a pooled statistic's Δ


def pooled(forks, stat):
    """`stat` (median, min) of every iteration of `forks` ([[x, ...] per fork]), pooled; None without any."""
    xs = [x for f in forks for x in f]
    if not xs:
        return None
    return statistics.median(xs) if stat == "median" else min(xs)


def resample(forks, rng):
    """A bootstrap sample of `forks`: forks drawn with replacement, then each fork's iterations, so that the fork stays
    the unit of variation as it is for the mean."""
    return [rng.choices(f, k=len(f)) for f in rng.choices(forks, k=len(forks))]


def pooled_delta(base, forks, stat, kind="score", per_unit=None, seed=0):
    """(value, Δ% against `base`'s, half-width of Δ's 99.9% CI (from the bootstrap's sd, in percentage points, as
    `compare`'s), Δ ok) of the pooled `stat` of `forks` against `base` (both [[x, ...] per fork]); Δ and half-width None
    without a base."""
    x = pooled(forks, stat)
    b = pooled(base, stat) if base else None
    if x is None or not b:
        return x, None, None, x is not None and delta_ok(x, kind, per_unit)
    d = 100 * (x / b - 1)
    if base is forks:
        return x, 0.0, 0.0, delta_ok(b, kind, per_unit)
    if min(sum(map(len, base)), sum(map(len, forks))) < 2:  # one sample a side: a bootstrap of it has no spread
        return x, d, None, delta_ok(b, kind, per_unit)
    rng = random.Random(seed)
    ds = []
    for _ in range(BOOT):
        bb = pooled(resample(base, rng), stat)
        if bb:
            ds.append(100 * (pooled(resample(forks, rng), stat) / bb - 1))
    half = t999(math.inf) * statistics.stdev(ds) if len(ds) > 1 else None
    return x, d, half, delta_ok(b, kind, per_unit)


def describe(xs):
    """n, min, p25, median, mean, p75, max and the coefficient of variation of `xs`."""
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda p: xs[min(len(xs) - 1, max(0, round(p * (len(xs) - 1))))]
    mean = sum(xs) / len(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {"n": len(xs), "min": xs[0], "p25": q(0.25), "median": statistics.median(xs), "mean": mean, "p75": q(0.75),
            "max": xs[-1], "cv": sd / mean if mean else None}
