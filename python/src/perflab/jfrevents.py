"""Reads an async run's .jfr with the JDK's own reader (JfrEvents.java, run as a single-file program by the JDK that
recorded it): how many of some events it has, and G1's promotion census.

The census needs `jdk.PromoteObjectInNewPLAB`, `jdk.PromoteObjectOutsidePLAB` and `jdk.TenuringDistribution` in the
recording, e.g. from a campaign's `"jfrsync": "+jdk.PromoteObjectInNewPLAB+jdk.PromoteObjectOutsidePLAB+jdk.TenuringDistribution"`.
Promotion in a new PLAB is one event per PLAB, so its plabSize stands for the bytes promoted into it: the bytes per class
are an estimate, weighted by the class whose object opened each PLAB.
"""
import glob, json, os, shutil, subprocess

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "JfrEvents.java")
CENSUS = "promotion.json"  # <cell>/promotion.json: the census, cached while it is newer than the recording


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


def run(java, *args, timeout=600):
    r = subprocess.run([java, "-Xmx2g", TOOL, *args], capture_output=True, text=True, timeout=timeout)
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
    n = 0
    for row in rows[1:]:
        cols = row.split("\t")
        if len(cols) > max(k, o) and cols[k] == "measure":
            try:
                n += float(cols[o])
            except ValueError:
                pass
    return n or None
