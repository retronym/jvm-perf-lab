"""(Re)renders the flame graphs of async-profiler runs with jfrconv (by default the one in perflab.toml, $JFRCONV, or
beside the async-profiler library). Multi-event kperf recordings need a jfrconv with `--hw` (retronym/async-profiler).

  perflab regraph [--jfrconv <jfrconv>] [-j <jobs>] <run-dir>...

A run directory is one `perflab run` or a campaign cell wrote with an async profile. For each JFR under it, each event and
each graph kind below, writes `<jfr stem>-<label>[-<kind>].html`.
"""
import argparse, concurrent.futures, glob, os, re, shutil, subprocess, sys


# per kind: jfrconv options (thread filter, classification), and whether to render bottom-up
BENCH = ["--threads", "-I", ".*jmh-worker.*"]
KINDS = {
    "bench": (BENCH, False),
    "reverse": (BENCH, True),
    "threads": (["--threads"], False),
    "classify": (["--classify"], False),
    "bench-classify": (["-I", ".*jmh-worker.*", "--classify"], False),
    "reverse-classify": (["-I", ".*jmh-worker.*", "--classify"], True),
}


def events_of(profile):
    """The events of an async profile, from a profile string (`async:cycles+instructions`, `async:cpu,alloc`) or a run's
    directory (its profile.txt, written by `perflab run`): [("hw-cycles", ["--hw", "cycles"]), ...] or cpu, alloc, ..."""
    f = os.path.join(profile, "profile.txt")
    if os.path.isdir(profile) and os.path.exists(f):
        profile = open(f).read().strip()
    kind, _, spec = profile.partition(":")
    spec = spec if kind == "async" else "cpu"
    if "+" in spec:
        return [(f"hw-{e.split('@')[0]}", ["--hw", e.split("@")[0]]) for e in spec.split("+")]
    names = [e.split("@")[0] for e in re.split(r"[,-]", spec)]
    return [(e, [f"--{e}"]) for e in names if e in ("cpu", "wall", "alloc", "lock")] or [("cpu", ["--cpu"])]


FORCE = False
MINWIDTH = "0.01"  # percent of samples below which jfrconv drops a frame; small enough to zoom into details
HEAP = "24g"


# `<jfr stem>.regraph` records which jfrconv build rendered that recording's graphs: graphs that bench-lab (or an
# older build) rendered are redone even when they are newer than the recording
def stamp(jfrconv):
    path = shutil.which(jfrconv) or jfrconv
    return f"{os.path.realpath(path)} {os.path.getmtime(path):.0f} minwidth={MINWIDTH}"


def stamp_of(jfr):
    try:
        return open(jfr[:-4] + ".regraph").read().strip()
    except OSError:
        return None


def graph_path(jfr, label, kind):
    return f"{jfr[:-4]}-{label}{'' if kind == 'bench' else '-' + kind}.html"


def render_one(jfrconv, jfr, label, select, kind, title):
    extra, reverse = KINDS[kind]
    out = graph_path(jfr, label, kind)
    if not FORCE and os.path.exists(out) and stamp_of(jfr) == stamp(jfrconv) and os.path.getmtime(out) > os.path.getmtime(jfr):
        return None
    # reverse graphs of deep Scala stacks need a lot of heap (over 8 GB for a 1 GB kperf JFR)
    cmd = [jfrconv, f"-J-Xmx{HEAP if reverse else '4g'}", *select, *extra, *(["--reverse"] if reverse else []), "--minwidth", MINWIDTH, "--title", title, jfr, out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return f"{out}: jfrconv failed: {r.stderr.strip()[:300]}" if r.returncode else None


def regraph(dirs, jfrconv=None, jobs=4, title_of=None):
    if not jfrconv:
        from . import jmh
        jfrconv = jmh.jfrconv(jmh.async_lib())
    tasks = []
    for d in dirs:
        for jfr in sorted(glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)):
            name = title_of(d) if title_of else os.path.basename(d.rstrip("/"))
            for label, select in events_of(d):
                for kind in KINDS:
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
    global FORCE, HEAP, MINWIDTH
    ap = argparse.ArgumentParser(prog="perflab regraph", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jfrconv")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--heap", default=HEAP, help="jfrconv heap for reverse graphs")
    ap.add_argument("--force", action="store_true", help="redo graphs that are already up to date")
    ap.add_argument("--minwidth", default=MINWIDTH, help="jfrconv --minwidth, in percent (default %(default)s)")
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args(argv)
    FORCE, HEAP, MINWIDTH = a.force, a.heap, a.minwidth
    ok, problems = regraph(a.dirs, a.jfrconv, a.jobs)
    print(f"{ok} graphs written, {len(problems)} problems")
    return 1 if problems else 0
