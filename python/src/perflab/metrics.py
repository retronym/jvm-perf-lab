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
import functools, glob, json, math, os, plistlib, re

# events counting cycles are shown as % of cycles, the others per 1,000 instructions: by the event's description in
# macOS's PMU event database (kpep), else by its name, as XctraceProfiler does
KPEP = "/usr/share/kpep"
CYCLE_EVENT = re.compile(r"WAITING|STALL|BUBBLE|CYCLE")
JMH_TIME_MS = {"ns": 1e-6, "us": 1e-3, "ms": 1, "s": 1000, "min": 60_000, "hr": 3_600_000, "day": 86_400_000}
GROUPS = ("jit", "gc", "other")
TOP_DOWN = ("useful", "processing", "delivery", "discarded")  # Instruments' "CPU Counters" template, % of the bench's
EVENTS_NAME = "hw-events.json"  # per cell: an async kperf profile's events per op on the benchmark threads


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
    recording through jfrconv, kept in the cell's hw-events.json; {} for other profiles."""
    from . import regraph
    events = [label.removeprefix("hw-") for label, _ in regraph.events_of(profile) if label.startswith("hw-")]
    f = os.path.join(cell, EVENTS_NAME)
    if not events or not glob.glob(os.path.join(cell, "**", "*.jfr"), recursive=True):
        return {}
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(os.path.join(cell, "result.json")):
        return json.load(open(f))
    import tempfile
    from . import profdiff
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for e in events:
            r = profdiff.load(cell, e, jfrconv, tmp, "events")
            out[e] = r["total"] / r["ops"]
    json.dump(out, open(f, "w"), indent=1)
    return out


def cached_hw_events(cell):
    """What `hw_events` kept for the cell, without running jfrconv (the index is rebuilt every few seconds)."""
    try:
        return json.load(open(os.path.join(cell, EVENTS_NAME)))
    except (OSError, ValueError):
        return {}


def of(r, per_unit=None, hw=None):
    """A JMH result's metrics: [(key, label, kind, main, value)]. `kind` picks the format and Δ floor (score, count,
    alloc, ratio, pct); `main` ones are the summary table's columns. `hw` is an async kperf profile's events per op."""
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
    return [x for x in out if x[4] is not None]


def fmt(kind, x):
    from . import ui
    return {"score": ui.num, "count": ui.si, "alloc": ui.size, "ratio": lambda y: f"{y:.3g}", "pct": lambda y: f"{y:.1f}%"}[kind](x)


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


def summarise(variants, per_unit=None):
    """{variant: [metrics of each round (`of`)]}, the first variant the baseline -> (columns [(key, label, kind, main)]
    in the order first seen, {variant: {key: (mean, sd or None for one round, Δ% or None, spread of Δ or None, Δ ok)}}).
    The spread of a Δ combines both variants' relative spreads over rounds."""
    cols, rounds = {}, {}
    for v, rs in variants.items():
        rounds[v] = [{k: x for k, _, _, _, x in ms} for ms in rs]
        for ms in rs:
            for k, label, kind, main, _ in ms:
                cols.setdefault(k, (k, label, kind, main))
    names = list(variants)
    base = {k: stats([r.get(k) for r in rounds[names[0]]]) for k in cols}
    out = {}
    for v in names:
        n, nb = len(rounds[v]), len(rounds[names[0]])
        out[v] = {}
        for k, (_, _, kind, _) in cols.items():
            mean, sd = stats([r.get(k) for r in rounds[v]])
            if mean is None:
                continue
            b, bsd = base[k]
            spread = 100 * ((sd / mean) ** 2 + (bsd / b) ** 2) ** 0.5 if b and mean and n > 1 and nb > 1 else None
            d = None if v == names[0] or not b else 100 * (mean / b - 1)
            out[v][k] = (mean, sd if n > 1 else None, d, spread, delta_ok(b, kind, per_unit))
    return list(cols.values()), out
