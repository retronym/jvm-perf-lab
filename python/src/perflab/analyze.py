"""Hot methods and the split by phase of async-profiler runs, for the benchmark threads.

  perflab analyze [--phases <table.toml>] [--top 25] <run-dir>...       per recording and kind: phases, then top self
  perflab analyze --share <table.toml> <jfr> <kind>                       phase shares, tab-separated (kind: cpu, alloc,
                                                                          wall, lock, or hw:<event>)

The phase table (default: [analyze] phases in perflab.toml) names the program's phases by stack frames:

    [[phase]]
    label = "typer"
    pattern = 'dotty/tools/dotc/typer/TyperPhase\\.'

    [[phase]]
    label = "transforms"
    pattern = 'dotty/tools/dotc/transform/MegaPhase\\.'
    sub = 'dotty/tools/dotc/transform/([A-Za-z0-9]+)[.$]'   # name the part: the first frame below the innermost match
    subExclude = ["MegaPhase"]                              # whose group(1) is not one of these, as "transforms:<name>"

    [[phase]]
    label = "other phases"
    pattern = 'dotty/tools/dotc/core/Phases\\$Phase\\.runOn'
    fallback = true                                         # only when no other phase matches

A sample's phase is the first non-fallback phase matching any of its frames, from the root; else the first fallback;
else "outside phases".
"""
import argparse, collections, glob, os, re, subprocess, sys, tomllib

from . import config, jmh, regraph


class Phases:
    def __init__(self, path):
        self.rows = []
        if path:
            with open(path, "rb") as f:
                for p in tomllib.load(f).get("phase", []):
                    self.rows.append((p["label"], re.compile(p["pattern"]), re.compile(p["sub"]) if p.get("sub") else None,
                                      set(p.get("subExclude", [])), p.get("fallback", False)))

    def __bool__(self):
        return bool(self.rows)

    def of(self, frames):
        for fallback in (False, True):
            for f in frames:
                for label, rx, sub, exclude, fb in self.rows:
                    if fb == fallback and rx.search(f):
                        return self._sub(label, rx, sub, exclude, frames)
        return "outside phases"

    @staticmethod
    def _sub(label, rx, sub, exclude, frames):
        if not sub:
            return label
        last = max(i for i, f in enumerate(frames) if rx.search(f))
        for f in frames[last + 1:]:
            m = sub.search(f)
            if m and m.group(1) not in exclude:
                return f"{label}:{m.group(1)}"
        return f"{label}:(itself)"


def collapsed(jfr, kind):
    args = ["--hw", kind[3:]] if kind.startswith("hw:") else [f"--{kind}"]
    out = subprocess.run([jmh.jfrconv(jmh.async_lib()), *args, "--threads", "-I", ".*jmh-worker.*", "-o", "collapsed", jfr, "/dev/stdout"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        stack, _, n = line.rpartition(" ")
        if stack and n.isdigit():
            yield stack.split(";"), int(n)


def clean(fr):
    return re.sub(r"_\[[0-9a-z]\]$", "", fr)


def kinds_of(run):
    return [("hw:" + label[3:]) if label.startswith("hw-") else label for label, _ in regraph.events_of(run)]


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab analyze", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phases")
    ap.add_argument("--share", nargs=3, metavar=("TABLE", "JFR", "KIND"))
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("runs", nargs="*")
    x = ap.parse_args(argv)
    if x.share:
        table, jfr, kind = x.share
        phases, by, total = Phases(table), collections.Counter(), 0
        for frames, n in collapsed(jfr, kind):
            total += n
            by[phases.of(frames)] += n
        for p, n in by.most_common():
            print(f"{p}\t{n / total if total else 0:.4f}")
        return 0
    phases = Phases(x.phases or config.get().path("analyze", "phases"))
    for run in x.runs:
        for jfr in sorted(glob.glob(os.path.join(run, "**", "*.jfr"), recursive=True)):
            for kind in kinds_of(run):
                by_phase, by_self, total = collections.Counter(), collections.Counter(), 0
                for frames, n in collapsed(jfr, kind):
                    total += n
                    if phases:
                        by_phase[phases.of(frames)] += n
                    leaf = clean(frames[-1])
                    if kind == "alloc":  # the leaf is the allocated type; name the allocating method too
                        leaf = clean(frames[-2]) + " -> " + leaf if len(frames) > 1 else leaf
                    by_self[leaf] += n
                if total == 0:
                    continue
                print(f"\n## {os.path.relpath(jfr)}: {kind} ({total})\n")
                if phases:
                    print("by phase: " + ", ".join(f"{p} {100 * n / total:.1f}%" for p, n in by_phase.most_common()))
                print(f"\ntop {'allocation sites' if kind == 'alloc' else 'self'}:")
                for m, n in by_self.most_common(x.top):
                    print(f"  {100 * n / total:5.1f}%  {m}")
    return 0
