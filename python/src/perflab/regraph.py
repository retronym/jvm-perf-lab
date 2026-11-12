"""(Re)renders the flame graphs of async-profiler runs with jfrconv (by default the one in perflab.toml, $JFRCONV, or
beside the async-profiler library). Multi-event kperf recordings need a jfrconv with `--hw` (retronym/async-profiler).

  perflab regraph [--jfrconv <jfrconv>] [-j <jobs>] <run-dir>...

A run directory is one `perflab run` or a campaign cell wrote with an async profile. For each JFR under it, each event and
each graph kind (KINDS below; `[async] graphs = [...]` in perflab.toml or --kinds picks some; by default the whole JVM, with its threads as frames the
viewer zooms into (`jvm`, `jvm-reverse`; the viewer's Threads and Categories buttons merge those layers away or back, so there is no graph of each); not a graph with the other threads already dropped), writes
`<jfr stem>-<label>[-<kind>].html`.

With `[async] spans = true` the `bench` graphs get the span panel (`jfrconv --spans`), for recordings with spans from the
program (async-profiler's Span API, the perflab-spans jar); `[async] span_config` names the panel's groupings.
"""
import argparse, concurrent.futures, glob, os, re, shutil, subprocess, sys


# The benchmark's threads, for the kinds that keep only them (`bench`, `reverse`, `*-classify`, profdiff, `perflab analyze`):
# JMH's workers, unless [async] threads in perflab.toml names others (a benchmark that does its work on threads of its own).
THREADS = ".*jmh-worker.*"


def bench_threads():
    """The regex of the benchmark's threads: [async] threads in perflab.toml, else JMH's workers."""
    from . import config
    return config.get().get("async", "threads") or THREADS


def bench_filter():
    return ["--threads", "-I", bench_threads()]


# per kind: jfrconv options (thread filter, classification), and whether to render bottom-up
BENCH = ["--threads", "-I", THREADS]  # the default; kinds() and render_one() use bench_filter(), which honours [async] threads
KINDS = {
    "jvm": (["--threads", "--classify"], False),
    "jvm-reverse": (["--threads", "--classify"], True),
    "bench": (BENCH, False),
    "reverse": (BENCH, True),
    "threads": (["--threads"], False),
    "classify": (["--classify"], False),
    "bench-classify": (BENCH + ["--classify"], False),
    "reverse-classify": (BENCH + ["--classify"], True),
}


# what each kind and event shows, for tooltips on the pages that link the graphs
FILTERED = ("bench", "reverse", "bench-classify", "reverse-classify")
KIND_HELP = {
    "jvm": "The whole JVM, every thread: one tower per thread (the benchmark's, the JIT compilers, GC, ...) under a common root. Click a thread's frame to zoom into just that thread. The viewer's Threads and Categories buttons merge the thread names away, or add a category frame ([gc], [c2_comp], [Interpreter], ...) under each; search and the other controls filter further. Root at the bottom, callees above.",
    "jvm-reverse": "The whole JVM, every thread, stacks reversed: the methods where the event lands (leaves) at the top level, their callers beneath. Self cost by method. The viewer's Threads and Categories buttons merge the thread names away, or add the category frames.",
    "bench": "DEPRECATED, drops every other thread: use jvm. Benchmark threads (JMH workers, or [async] threads) only. Root at the bottom, callees above: where the benchmark spends this event, by call path.",
    "reverse": "DEPRECATED, drops every other thread: use jvm-reverse. Benchmark threads only (JMH workers, or [async] threads), stacks reversed: the methods where the event lands (leaves) at the top level, their callers beneath. Self cost by method.",
    "bench-classify": "DEPRECATED, drops every other thread: use jvm and its Categories button. Benchmark threads only, each sample put under a category frame at the root by what it was doing: [c2_comp], [c1_comp], [Interpreter], [native], [vm], [gc], [jit], [class_load], ...",
    "reverse-classify": "DEPRECATED, drops every other thread. Benchmark threads only, by category as in bench-classify, with stacks reversed (leaves at the top level).",
    "threads": "Every thread of the JVM, one tower per thread (jvm has this, with the viewer's Threads button to merge them).",
    "classify": "Every thread of the JVM, by category: [gc], [jit], [vm], [c2_comp], [Interpreter], [class_load], ... (jvm has this, with the viewer's Categories button).",
}
EVENT_HELP = {
    "cpu": "CPU time: a sample per 1 ms of CPU time on a thread (async-profiler cpu).",
    "wall": "Wall-clock time: samples of every thread at a fixed interval, running or not; shows waiting as well as running.",
    "alloc": "Allocations: a sample about every 512 KB allocated on a thread, from TLAB refills and allocations outside TLABs. A benchmark that does not allocate has none on its threads.",
    "lock": "Lock contention: samples of threads blocked entering a monitor or ReentrantLock.",
    "cycles": "PMU core cycles (user mode), sampled via kperf: where the CPU's time goes, independent of frequency.",
    "instructions": "PMU retired instructions (user mode), sampled via kperf: where the work is.",
    "cache-misses": "PMU L1D load misses (L1D_CACHE_MISS_LD_NONSPEC, user mode), sampled via kperf, charged to the load that missed.",
    "branch-misses": "PMU branch mispredictions (BRANCH_MISPRED_NONSPEC, user mode), sampled via kperf, charged to the branch.",
}


def span_args():
    """jfrconv options for the span panel of `bench` graphs, from [async] spans and span_config in perflab.toml."""
    from . import config
    c = config.get()
    conf = c.path("async", "span_config")
    if not (c.get("async", "spans") or conf):
        return []
    return ["--spans", *(["--span-config", conf] if conf else [])]


_warned = []


def kind_label(kind):
    """What a button says: the kind, and for those that drop all but the benchmark's threads, that they do."""
    return f"{kind} (bench threads only)" if kind in FILTERED else kind


def kinds(explicit=None):
    """The graph kinds to render: `explicit`, else [async] graphs in perflab.toml, else all of KINDS."""
    from . import config
    ks = explicit or config.get().get("async", "graphs") or ["jvm", "jvm-reverse"]
    filtered = [k for k in ks if k in FILTERED]
    if filtered and not _warned:
        _warned.append(1)
        print(f"perflab: graph kinds {filtered} keep only the benchmark threads ({bench_threads()}) and drop the rest of the JVM: "
              "use jvm and jvm-reverse (the viewer filters), or name the threads with [async] threads", file=sys.stderr)
    unknown = [k for k in ks if k not in KINDS]
    if unknown:
        sys.exit(f"unknown graph kinds {unknown}; known: {', '.join(KINDS)}")
    return ks


def events_of(profile, kperf=False):
    """The events of an async profile, from a profile string (`async:cycles+instructions`, `async:cpu,alloc`) or a run's
    directory (its profile.txt, written by `perflab run`): [("hw-cycles", ["--hw", "cycles"]), ...] or cpu, alloc, ...
    A kperf recording's events are hardware events even when there is only one (`async:cycles@10000000`): `kperf` says
    so for a profile string; a run's directory says so in its jmh.args."""
    f = os.path.join(profile, "profile.txt")
    if os.path.isdir(profile) and os.path.exists(f):
        args = os.path.join(profile, "jmh.args")
        kperf = kperf or (os.path.exists(args) and "kperf=" in open(args).read())
        profile = open(f).read().strip()
    kind, _, spec = profile.partition(":")
    spec = spec if kind == "async" else "cpu"
    if "+" in spec or (kperf and kind == "async"):
        return [(f"hw-{e.split('@')[0]}", ["--hw", e.split("@")[0]]) for e in spec.split("+")]
    names = [e.split("@")[0] for e in re.split(r"[,-]", spec)]
    return [(e, [f"--{e}"]) for e in names if e in ("cpu", "wall", "alloc", "lock")] or [("cpu", ["--cpu"])]


FORCE = False
# set by a remote worker for its job: a cell's graphs are rendered by the coordinator once it is uploaded
# (remote.wants_graphs), so the measuring machine spends nothing on them between cells
SKIP_ENV = "PERFLAB_NO_GRAPHS"
MINWIDTH = "0.001"  # percent of samples below which jfrconv drops a frame: finer than the page shows (below), so the viewer's Collapse merges thin pieces of work into boxes that are wide enough to see
DISPLAY_MINWIDTH = "0.01"  # percent of the graph below which the viewer hides a frame (jfrconv --display-minwidth), after merging frames
HEAP = "24g"


# `<jfr stem>.regraph` records which jfrconv build rendered that recording's graphs: graphs that bench-lab (or an
# older build) rendered are redone even when they are newer than the recording
def stamp(jfrconv):
    path = shutil.which(jfrconv) or jfrconv
    spans = span_args()
    conf = f" {os.path.getmtime(spans[-1]):.0f}" if len(spans) > 1 and os.path.exists(spans[-1]) else ""
    return f"{os.path.realpath(path)} {os.path.getmtime(path):.0f} minwidth={MINWIDTH}/{DISPLAY_MINWIDTH}" + (f" {' '.join(spans)}{conf}" if spans else "")


def stamp_of(jfr):
    try:
        return open(jfr[:-4] + ".regraph").read().strip()
    except OSError:
        return None


def graph_path(jfr, label, kind):
    return f"{jfr[:-4]}-{label}{'' if kind == 'bench' else '-' + kind}.html"


def render_one(jfrconv, jfr, label, select, kind, title):
    extra, reverse = KINDS[kind]
    if kind in FILTERED:
        extra = bench_filter() + [e for e in extra if e not in BENCH]
    if kind == "bench":
        extra = extra + span_args()
    out = graph_path(jfr, label, kind)
    if not FORCE and os.path.exists(out) and stamp_of(jfr) == stamp(jfrconv) and os.path.getmtime(out) > os.path.getmtime(jfr):
        return None
    # reverse graphs of deep Scala stacks need a lot of heap (over 8 GB for a 1 GB kperf JFR)
    cmd = [jfrconv, f"-J-Xmx{HEAP if reverse else '4g'}", *select, *extra, *(["--reverse"] if reverse else []), "--minwidth", MINWIDTH, "--display-minwidth", DISPLAY_MINWIDTH, "--title", title, jfr, out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{out}: jfrconv failed: {r.stderr.strip()[:300]}" if r.returncode else None


def regraph(dirs, jfrconv=None, jobs=4, title_of=None, kinds_=None):
    if not jfrconv:
        from . import jmh
        jfrconv = jmh.jfrconv(jmh.async_lib())
    tasks = []
    for d in dirs:
        for jfr in sorted(glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)):
            name = title_of(d) if title_of else os.path.basename(d.rstrip("/"))
            for label, select in events_of(d):
                for kind in kinds(kinds_):
                    tasks.append((jfrconv, jfr, label, select, kind, f"{name}: {label.removeprefix('hw-')}, {kind}"))
    # reverse graphs one at a time (each may take HEAP), the rest in parallel
    reverse = [t for t in tasks if KINDS[t[4]][1]]
    forward = [t for t in tasks if not KINDS[t[4]][1]]
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        problems = [p for p in pool.map(lambda t: render_one(*t), forward) if p]
    problems += [p for p in map(lambda t: render_one(*t), reverse) if p]
    for p in problems:
        print(p, file=sys.stderr)
    for jfr in {t[1] for t in tasks}:
        if not any(p.startswith(jfr[:-4]) for p in problems):
            with open(jfr[:-4] + ".regraph", "w") as f:
                f.write(stamp(jfrconv) + "\n")
    return len(tasks) - len(problems), problems


def main(argv):
    global FORCE, HEAP, MINWIDTH, DISPLAY_MINWIDTH
    ap = argparse.ArgumentParser(prog="perflab regraph", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jfrconv")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--heap", default=HEAP, help="jfrconv heap for reverse graphs")
    ap.add_argument("--force", action="store_true", help="redo graphs that are already up to date")
    ap.add_argument("--minwidth", default=MINWIDTH, help="jfrconv --minwidth, in percent (default %(default)s)")
    ap.add_argument("--display-minwidth", default=DISPLAY_MINWIDTH, help="jfrconv --display-minwidth, in percent: what the viewer hides after merging frames (default %(default)s)")
    ap.add_argument("--kinds", help=f"comma-separated graph kinds (default: [async] graphs in perflab.toml, else jvm,jvm-reverse; all kinds: {','.join(KINDS)})")
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args(argv)
    FORCE, HEAP, MINWIDTH, DISPLAY_MINWIDTH = a.force, a.heap, a.minwidth, a.display_minwidth
    ok, problems = regraph(a.dirs, a.jfrconv, a.jobs, kinds_=a.kinds.split(",") if a.kinds else None)
    print(f"{ok} graphs written, {len(problems)} problems")
    return 1 if problems else 0
