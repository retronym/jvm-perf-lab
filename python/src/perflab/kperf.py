"""Sampling periods of async-profiler's kperf (macOS PMU) events, and a check of how many samples a cell's recording
took.

A period is chosen for a number of samples per fork, not a rate: a profdiff needs about 50-100k samples of an event per
fork, and many more only make the recording, its collapsed stacks and every graph of it larger (a compile sampling L1D
misses at async-profiler's default of 10,000 took about a million samples per fork, and its collapsed stacks filled
gigabytes). So the period is about (events per op x ops per fork) / 100k. An event that the profile gives no period
(`async:cycles+cache-misses`) takes `DEFAULT_PERIODS`'s, sized for a typical JMH fork; after the run, `check` reads the
helper's sample counts from the cell's jmh.log, keeps them in the cell's kperf-samples.json, and warns of an event over
`MAX_SAMPLES` with the period that would have taken about `TARGET_SAMPLES`.
"""
import glob, json, os, re

TARGET_SAMPLES = 100_000
MAX_SAMPLES = 500_000
SAMPLES_NAME = "kperf-samples.json"  # per cell: {event: {"samples": n, "period": p}}

# by the event's name (an async-profiler alias or a kpep name), first match: about 100k samples per event in a fork of
# ~10^11 cycles (~25 s of one busy core at 4 GHz), from what a compiler-sized workload counts per cycle (IPC 2-3, an
# L1D load miss per ~50 cycles, an L2 miss per ~100-200, TLB misses and branch mispredictions rarer still)
DEFAULT_PERIODS = [
    (re.compile(r"^(cycles|CORE_ACTIVE_CYCLE|FIXED_CYCLES)$", re.I), 2_000_000),
    (re.compile(r"^(instructions|INST_ALL|FIXED_INSTRUCTIONS)$", re.I), 5_000_000),
    (re.compile(r"^INST_", re.I), 1_000_000),  # a kind of instruction
    (re.compile(r"^(cache-misses|L1D_CACHE_MISS)", re.I), 50_000),
]
CYCLES_WHILE = 1_000_000  # an event counting cycles while something (a stall): a share of all cycles
OTHER = 20_000  # L2 and memory-system misses, TLB misses, branch mispredictions, L1I misses, ...

SAMPLES = re.compile(r"kperf: (\S+): (\d+) samples")
PERIOD = re.compile(r"kperf: (\S+) \([^)]*\) every (\d+)")


def default_period(event):
    from . import metrics
    return next((p for pat, p in DEFAULT_PERIODS if pat.search(event)),
                CYCLES_WHILE if metrics.counts_cycles(event) else OTHER)


def with_periods(events):
    """A `+`-joined list of kperf events with each event that names no period given its default:
    `cycles+cache-misses@10000` -> `cycles@2000000+cache-misses@10000`."""
    return "+".join(e if "@" in e else f"{e}@{default_period(e)}" for e in events.split("+"))


def suggest(samples, period, target=TARGET_SAMPLES):
    """The period that would have taken about `target` samples, rounded to one significant digit."""
    p = max(1, period * samples / target)
    scale = 10 ** (len(str(int(p))) - 1)
    return max(1, round(p / scale)) * scale


def samples(cell):
    """{event: {"samples": n, "period": p}} from the helper's log lines in the cell's jmh.log: the last session's (the
    measurement's; a warmup's comes first). Lines of the fork's output can interleave, so a garbled one is skipped."""
    try:
        log = open(os.path.join(cell, "jmh.log"), errors="replace").read()
    except OSError:
        return {}
    periods = {m[1]: int(m[2]) for m in PERIOD.finditer(log)}
    return {e: {"samples": int(n), "period": periods.get(e)} for e, n in SAMPLES.findall(log)}


def warnings_of(counts):
    out = []
    for e, c in counts.items():
        if c["samples"] > MAX_SAMPLES:
            at = f" at period {c['period']:,}" if c["period"] else ""
            fix = f"; @{suggest(c['samples'], c['period'])} would take about {TARGET_SAMPLES // 1000}k" if c["period"] else ""
            out.append(f"{e}: {c['samples']:,} samples per fork{at}{fix}")
    return out


def check(cell):
    """The cell's sample counts, kept in its kperf-samples.json, and a warning for each event with too many."""
    counts = samples(cell)
    if counts:
        json.dump(counts, open(os.path.join(cell, SAMPLES_NAME), "w"), indent=1)
    return warnings_of(counts)


def campaign_warnings(spec_dir):
    """A warning for each event over a campaign's cells, from the cell that took the most samples of it."""
    worst = {}
    for f in glob.glob(os.path.join(spec_dir, "*", "*", "*", SAMPLES_NAME)):
        try:
            counts = json.load(open(f))
        except (OSError, ValueError):
            continue
        for e, c in counts.items():
            if c["samples"] > worst.get(e, {"samples": MAX_SAMPLES})["samples"]:
                worst[e] = c
    return warnings_of(worst)
