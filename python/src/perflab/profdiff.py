"""Compares the async-profiler recordings of two bench-lab runs (e.g. two cells of a campaign with an async profile):
a differential flame graph of the benchmark threads (and the reverse one, and each run's own), and the methods whose self
time per op changed most. `compare.html` in the output directory shows the graphs of every event diffed there as tabs
over one frame, to flip between them (`compare.write`).

  perflab profdiff [--event cycles] [--jfrconv <jfrconv>] [--top 25] <run-a> <run-b> <out-dir>

A run is a directory written by `perflab run` or a campaign cell, with an async profile. Samples are
normalized per op (each iteration has ceil(iteration time / its mean op time) ops), so runs of different lengths or speeds compare;
with hardware events the table is in events per op.
"""
import argparse, collections, glob, io, json, math, os, re, subprocess, sys

from . import compare, regraph


LAMBDA_ADDRESS = re.compile(r"\$\$Lambda[./]0x[0-9a-f]+")
FRAME_KIND = re.compile(r"_\[[a-z0-9]+\]$")


def si(x):
    """`x` with an SI suffix: 1.2G, 340M, 5.6k."""
    for div, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if abs(x) >= div:
            return f"{x / div:.3g}{suffix}"
    return f"{x:.3g}"


def profile_dir(run):
    p = os.path.join(run, "profile-dir")
    return open(p).read().strip() if os.path.exists(p) else run


def load(run, event, jfrconv, out_dir, name):
    if not jfrconv:
        from . import jmh
        jfrconv = jmh.jfrconv(jmh.async_lib())
    d = profile_dir(run)
    jfr = glob.glob(os.path.join(d, "**", "*.jfr"), recursive=True)[0]
    res = json.load(open(os.path.join(d, "result.json")))[0]
    # JMH runs whole ops until the iteration time is up, so an iteration with mean op time t has ceil(time / t) ops
    iteration_ms = float(res["measurementTime"].split()[0]) * 1000
    ops = sum(math.ceil(iteration_ms / t) for t in res["primaryMetric"]["rawData"][0])
    collapsed = os.path.join(out_dir, f"{name}-{event}.collapsed")
    select = [s for label, s in regraph.events_of(d) if label.removeprefix("hw-") == event][0]
    subprocess.run([jfrconv, "-J-Xmx8g", *select, "--threads", "-I", ".*jmh-worker.*", "-o", "collapsed", jfr, collapsed],
                   check=True, capture_output=True)
    # a lambda's hidden class is named for its address in that JVM (`Foo$$Lambda.0x0000f80140b6b0`), which differs
    # between the runs: without it, the same lambda in both runs is one frame
    lines = [LAMBDA_ADDRESS.sub("$$Lambda", line) for line in open(collapsed)]
    with open(collapsed, "w") as f:
        f.writelines(lines)
    self_, total = collections.Counter(), 0
    for line in lines:
        stack, _, n = line.rstrip().rpartition(" ")
        n = int(n)
        total += n
        # by method, however it was compiled (jfrconv's _[j] JIT, _[i] inlined, _[1] C1, ...)
        self_[FRAME_KIND.sub("", stack.rsplit(";", 1)[-1])] += n
    return {"collapsed": collapsed, "ops": ops, "self": self_, "total": total,
            "score": res["primaryMetric"]["score"], "dir": d}


def label(run):
    """A run's name in titles: a campaign cell's variant and round (`base/1`), else its directory."""
    parts = os.path.normpath(run).split(os.sep)
    return "/".join(parts[-2:]) if parts[-1].isdigit() else parts[-1]


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab profdiff", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="cycles")
    ap.add_argument("--jfrconv")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("out")
    x = ap.parse_args(argv)
    if not x.jfrconv:
        from . import jmh
        x.jfrconv = jmh.jfrconv(jmh.async_lib())
    os.makedirs(x.out, exist_ok=True)
    A = load(x.a, x.event, x.jfrconv, x.out, "a")
    B = load(x.b, x.event, x.jfrconv, x.out, "b")
    # collapsed hardware-event stacks count events (samples × period), not samples
    per_op = lambda r, n: n / r["ops"]
    la, lb = label(x.a), label(x.b)
    graph = lambda title, *args: subprocess.run([x.jfrconv, "-J-Xmx8g", "--minwidth", "0.2", "--title", title, *args],
                                                capture_output=True)
    diff_html = os.path.join(x.out, f"diff-{x.event}.html")
    graph(f"{x.event}: {la} → {lb}", "--diff", A["collapsed"], B["collapsed"], diff_html)
    graph(f"{x.event}: {lb} → {la}", "--diff", B["collapsed"], A["collapsed"], os.path.join(x.out, f"diff-{x.event}-inverse.html"))
    graph(f"{x.event}: {la}", A["collapsed"], os.path.join(x.out, f"a-{x.event}.html"))
    graph(f"{x.event}: {lb}", B["collapsed"], os.path.join(x.out, f"b-{x.event}.html"))
    ta, tb = per_op(A, A["total"]), per_op(B, B["total"])
    table = io.StringIO()
    out = lambda s="": (print(s), table.write(s + "\n"))
    out(f"{x.event} per op (benchmark threads): a {si(ta)}, b {si(tb)}, {100 * (tb / ta - 1):+.1f}%  "
        f"(ms/op a {A['score']:.0f}, b {B['score']:.0f}; ops a {A['ops']}, b {B['ops']}; a = {la}, b = {lb})")
    delta = {m: per_op(B, B["self"][m]) - per_op(A, A["self"][m]) for m in set(A["self"]) | set(B["self"])}
    rows = sorted(delta.items(), key=lambda kv: kv[1])
    fmt = lambda m, d: (f"| {'+' if d > 0 else ''}{si(d)} | {si(per_op(A, A['self'][m]))} | {si(per_op(B, B['self'][m]))} | "
                       f"{100 * d / ta:+.2f}% | `{m}` |")
    out(f"\nself {x.event} per op, biggest decreases then increases (b − a):\n")
    out("| Δ | a | b | Δ of a's total | method |\n|---|---|---|---|---|")
    for m, d in rows[:x.top]:
        out(fmt(m, d))
    out("| … | | | | |")
    for m, d in rows[-x.top:][::-1]:
        out(fmt(m, d))
    with open(os.path.join(x.out, f"table-{x.event}.md"), "w") as f:
        f.write(table.getvalue())
    print(f"\ndifferential flame graph: {diff_html}\ncompared: {compare.write(x.out, la, lb)}")
    for f in (A["collapsed"], B["collapsed"]):
        os.unlink(f)
