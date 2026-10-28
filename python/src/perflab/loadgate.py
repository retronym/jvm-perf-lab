"""Competing load on the machine: CPU used by processes other than the benchmark's own (a given root process and
its descendants: the sbt server, JMH's launcher and forks, xctrace), measured as the change in cumulative CPU time.

  perflab loadgate wait   <root-pid> [max-cores=1.5] [quiet-secs=60]   blocks until other load stays under max-cores
  perflab loadgate sample <root-pid> <out.tsv>                          appends "epoch<TAB>cores<TAB>top" every 5 s until killed
  perflab loadgate mean   <out.tsv> [since-epoch]                       mean other-load in cores over the samples
"""
import json, os, subprocess, sys, time

from . import transcript

# macOS daemons that run at background QoS, which Apple Silicon confines to the efficiency cores: reported, but not
# counted against the limit, since the benchmark runs on the performance cores.
BACKGROUND = {"mediaanalysisd", "photoanalysisd", "spotlightknowledged", "spotlightknowledged.updater", "mds", "mds_stores", "mdworker",
              "mdworker_shared", "mdbulkimport", "backupd", "backupd-helper", "corespotlightd", "suggestd",
              "knowledge-agent", "duetexpertd", "triald", "softwareupdated", "fseventsd"}

def cputimes():
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,time=,comm="], capture_output=True, text=True).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, t, comm = int(parts[0]), int(parts[1]), parts[2], parts[3]
        secs = 0.0
        d, _, hms = t.rpartition("-")
        for x in hms.split(":"):
            secs = secs * 60 + float(x)
        if d:
            secs += int(d) * 86400
        procs[pid] = (ppid, secs, comm.rsplit("/", 1)[-1])
    return procs

def ours(procs, root):
    # the parent is launchd (pid 1) once a detaching shell has exited: everything would count as ours
    keep = {root, *(p for p in (subprocess.os.getpid(), subprocess.os.getppid()) if p > 1)}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _, comm) in procs.items():
            if pid not in keep and (ppid in keep or comm == "xctrace"):
                keep.add(pid)
                changed = True
    return keep

def other_load(root, interval=5.0):
    a = cputimes()
    time.sleep(interval)
    b = cputimes()
    mine = ours(b, root)
    per = {}
    for pid, (_, secs, comm) in b.items():
        if pid in mine or pid not in a:
            continue
        d = secs - a[pid][1]
        if d > 0:
            per[comm] = per.get(comm, 0) + d / interval
    total = sum(v for c, v in per.items() if c not in BACKGROUND)
    bg = sum(v for c, v in per.items() if c in BACKGROUND)
    fg = [(c, v) for c, v in sorted(per.items(), key=lambda kv: -kv[1]) if c not in BACKGROUND]
    top = ", ".join(f"{c} {v:.1f}" for c, v in fg[:3])
    if bg >= 0.1:
        top += f"; background daemons {bg:.1f}"
    return total, top

STATE_NAME = "loadgate.json"
# where the wait is published: <campaigns> of this checkout, or of the one `perflab trees` runs from
LIVE_ENV = "PERFLAB_LIVE_DIR"


def state_path():
    from . import config
    return os.path.join(os.environ.get(LIVE_ENV) or config.get().campaigns, STATE_NAME)


def publish(state):
    """<campaigns>/loadgate.json while a wait lasts (the index draws it), removed when it ends."""
    path = state_path()
    try:
        if state is None:
            os.unlink(path)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(path + ".tmp", path)
    except OSError:
        pass


def wait(root, limit=1.5, quiet=60):
    """Blocks until other processes' load stays under `limit` cores for `quiet` seconds. While it waits, the samples
    are published for the index (`publish`) and each is a line of the transcript."""
    since = None
    state = {"pid": os.getpid(), "started": time.time(), "limit": limit, "quiet": quiet, "quietSince": None, "samples": []}
    try:
        while True:
            load, top = other_load(root)
            now = time.time()
            if load <= limit:
                since = since or now
                if now - since >= quiet:
                    transcript.say(f"idle: other load {load:.2f} cores")
                    return
                transcript.write(f"quiet: other load {load:.2f} cores for {now - since:.0f} of {quiet:.0f} s")
            else:
                since = None
                transcript.say(f"waiting: other load {load:.1f} cores ({top})")
            state["samples"] = (state["samples"] + [[round(now), round(load, 2), top]])[-720:]
            state["quietSince"] = since
            publish(state)
    finally:
        publish(None)


def server_pid():
    """The root of the process tree that runs this project's benchmarks ([build] server in perflab.toml): the sbt server
    of this checkout (the process holding the socket named in project/target/active.json), or perflab itself."""
    from . import config
    cfg = config.get()
    if cfg.get("build", "server") == "sbt":
        try:
            uri = json.load(open(os.path.join(cfg.root, "project", "target", "active.json")))["uri"]
        except (OSError, ValueError, KeyError):
            sys.exit("loadgate: no sbt server found for this checkout; start one with `sbt --client` first")
        out = subprocess.run(["lsof", "-t", uri.removeprefix("local://")], capture_output=True, text=True).stdout.split()
        if not out:
            sys.exit("loadgate: the sbt server of this checkout is not running")
        return int(out[0])
    return os.getpid()


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "wait":
        wait(int(argv[1]), float(argv[2]) if len(argv) > 2 else 1.5, float(argv[3]) if len(argv) > 3 else 60)
    elif cmd == "sample":
        root, path = int(argv[1]), argv[2]
        while True:
            load, top = other_load(root)
            with open(path, "a") as f:
                f.write(f"{time.time():.0f}\t{load:.2f}\t{top}\n")
    elif cmd == "mean":
        path = argv[1]
        since = float(argv[2]) if len(argv) > 2 else 0
        try:
            xs = [float(l.split("\t")[1]) for l in open(path) if l.strip() and float(l.split("\t")[0]) >= since]
        except FileNotFoundError:   # the run ended before the first sample
            xs = [0.0]
        print(f"{sum(xs) / len(xs):.2f}" if xs else "nan")
    else:
        sys.exit(__doc__)
    return 0
