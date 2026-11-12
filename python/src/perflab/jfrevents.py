"""Reads an async run's .jfr with the JDK's own reader (JfrEvents.java, run as a single-file program by the JDK that
recorded it): how many of some events it has, G1's promotion census, and the JIT's work.

The JIT summary prefers a spec's "jitRecording" (<cell>/jit-<pid>.jitrec, perflab-jit.jfc), which covers the whole fork
with every inlining decision; an async run's recording starts at the first measured iteration, after warmup compiled
the hot code, and has no inlining decisions (perflab.jfc does not record jdk.CompilerInlining).

The census needs `jdk.PromoteObjectInNewPLAB`, `jdk.PromoteObjectOutsidePLAB` and `jdk.TenuringDistribution` in the
recording, e.g. from a campaign's `"jfrsync": "+jdk.PromoteObjectInNewPLAB+jdk.PromoteObjectOutsidePLAB+jdk.TenuringDistribution"`.
Promotion in a new PLAB is one event per PLAB, so its plabSize stands for the bytes promoted into it: the bytes per class
are an estimate, weighted by the class whose object opened each PLAB.
"""
import glob, json, os, shutil, subprocess

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "JfrEvents.java")
CENSUS = "promotion.json"  # <cell>/promotion.json: the census, cached while it is newer than the recording
JIT = "jit.json"  # <cell>/jit.json: the JIT summary, cached while it is newer than the recording
PRECISE = "precise.json"  # <cell>/precise.json: the PMU samples with a precise PC, cached likewise


def recording(cell):
    from . import profdiff
    jfrs = sorted(glob.glob(os.path.join(profdiff.profile_dir(cell), "**", "*.jfr"), recursive=True))
    return jfrs[0] if jfrs else None


def java_for(cell):
    """The `java` that ran the cell (result.json's jvm), else JAVA_HOME's, else the PATH's."""
    try:
        jvm = json.load(open(os.path.join(cell, "result.json")))[0].get("jvm")
        if jvm and os.path.exists(jvm):
            return jvm
    except (OSError, ValueError, IndexError, KeyError):
        pass
    home = os.environ.get("JAVA_HOME")
    if home and os.path.exists(os.path.join(home, "bin", "java")):
        return os.path.join(home, "bin", "java")
    return shutil.which("java") or "java"


def run(java, *args, timeout=600, heap="2g"):
    r = subprocess.run([java, f"-Xmx{heap}", TOOL, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"JfrEvents {args[0]}: {(r.stderr or r.stdout).strip()[-1500:]}")
    return json.loads(r.stdout)


def count(cell, events):
    """{event: n} in the cell's recording."""
    jfr = recording(cell)
    if not jfr:
        raise FileNotFoundError(f"{cell}: no recording")
    return run(java_for(cell), "count", jfr, *events)["counts"]


def promotion(cell):
    """The cell's promotion census (cached in <cell>/promotion.json)."""
    jfr = recording(cell)
    if not jfr:
        raise FileNotFoundError(f"{cell}: no recording")
    f = os.path.join(cell, CENSUS)
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(jfr):
        try:
            return json.load(open(f))
        except ValueError:
            pass
    c = run(java_for(cell), "promotion", jfr)
    with open(f + ".tmp", "w") as out:
        json.dump(c, out)
    os.replace(f + ".tmp", f)
    return c


def jit_recordings(cell):
    """The cell's whole-fork JIT recordings (a spec's "jitRecording"), one per fork."""
    from . import jmh
    return sorted(glob.glob(os.path.join(cell, jmh.JIT_RECORDING)))


def jit(cell):
    """The cell's JIT summary (cached in <cell>/jit.json): JfrEvents' `jit` of its first fork's whole-fork recording,
    else of its async recording, with "source" ("fork" or "measured"), "recording" and "forks" (whole-fork recordings)."""
    forks = jit_recordings(cell)
    jfr = forks[0] if forks else recording(cell)
    if not jfr:
        raise FileNotFoundError(f"{cell}: no recording")
    f = os.path.join(cell, JIT)
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(jfr):
        try:
            c = json.load(open(f))
            if c.get("recording") == jfr:
                return c
        except ValueError:
            pass
    c = {"source": "fork" if forks else "measured", "recording": jfr, "forks": len(forks), **run(java_for(cell), "jit", jfr)}
    with open(f + ".tmp", "w") as out:
        json.dump(c, out)
    os.replace(f + ".tmp", f)
    return c


def precise(cell):
    """{event: {"samples", "precise", "value", "preciseValue"}} of the cell's kperf samples on the benchmark threads
    (async-profiler's profiler.HardwareSample), cached in <cell>/precise.json; {} for a recording without them."""
    jfr = recording(cell)
    if not jfr:
        raise FileNotFoundError(f"{cell}: no recording")
    f = os.path.join(cell, PRECISE)
    if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(jfr):
        try:
            return json.load(open(f))
        except ValueError:
            pass
    c = run(java_for(cell), "precise", jfr, regraph.bench_threads(), heap="8g")["events"]  # a kperf recording's constant pools are large
    with open(f + ".tmp", "w") as out:
        json.dump(c, out)
    os.replace(f + ".tmp", f)
    return c


def measured_ops(cell):
    """The ops of the measured iterations (iterations.tsv), which the recording covers; None if unknown."""
    tsv = os.path.join(cell, "iterations.tsv")
    if not os.path.exists(tsv):
        return None
    rows = open(tsv).read().splitlines()
    if not rows:
        return None
    head = rows[0].split("\t")
    if "ops" not in head or "kind" not in head:
        return None
    k, o = head.index("kind"), head.index("ops")
    measured = [cols for cols in (row.split("\t") for row in rows[1:]) if len(cols) > max(k, o) and cols[k] == "measure"]
    # the agent appends to iterations.tsv: more measured rows than the result has iterations are another run's (an
    # attempt the loadgate voided, before set_aside cleared the cell), which came first
    its = result_iterations(cell)
    if its is not None and len(measured) > its:
        measured = measured[len(measured) - its:]
    n = 0
    for cols in measured:
        try:
            n += float(cols[o])
        except ValueError:
            pass
    return n or None


def result_iterations(cell):
    """How many measured iterations the cell's result.json has, over its forks; None without one."""
    try:
        r = json.load(open(os.path.join(cell, "result.json")))[0]
        return sum(len(fork) for fork in r["primaryMetric"]["rawData"])
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
