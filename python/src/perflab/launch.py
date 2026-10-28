"""Launch mode (doc/direct-launch.md): perflab starts JMH itself, from a snapshot of the build, instead of through the
build tool.

    [build]
    mode = "launch"
    launch = "sbt -batch 'lab/perflabLaunch {out}'"   # compiles the benchmarks and writes {out}/launch.json

launch.json, as the build writes it:

    {"mainClass": "...", "java": "<the build's JDK>/bin/java", "classpath": [...], "javaOptions": [...],
     "roots": [<directories whose files are the build's own output>], "build": {"checkout": ..., "commit": ..., "dirty": ...}}

`build` runs the step once and snapshots it into <dir>: every classpath entry and every path in a -D option that lies
under a root is copied (cloned, where the file system can) into <dir>/snapshot, and <dir>/launch.json points at the
copies. Jars outside the roots (the build tool's caches) stay where they are, recorded with their size and time. A run
or campaign then measures the build it took, whatever happens to the checkout afterwards, with no build tool running.
"""
import json, os, shlex, shutil, subprocess, sys

from . import config, transcript

LAUNCH = "launch.json"
BUILD_DIR = ".build"  # in a run or campaign directory; hidden from the index, which globs them for cells and graphs


def read(path):
    with open(path) as f:
        return json.load(f)


def enabled():
    """Launch mode: [build] mode = "launch" in perflab.toml, or PERFLAB_BUILD_MODE=launch."""
    return (os.environ.get("PERFLAB_BUILD_MODE") or config.get().get("build", "mode")) == "launch"


def under(path, roots):
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def clone(src, dst):
    """A copy of a file or directory; on macOS a clone (APFS copy-on-write), which costs nothing until either changes."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if sys.platform == "darwin" and subprocess.run(["cp", "-cR", src, dst], capture_output=True).returncode == 0:
        return
    if os.path.isdir(src):
        shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copy2(src, dst)


def snapshot(built, dir):
    """`built` (the build's launch.json) with its build outputs copied into <dir>/snapshot."""
    roots = [os.path.realpath(r) for r in built.get("roots", [])]
    snap = os.path.join(dir, "snapshot")
    shutil.rmtree(snap, ignore_errors=True)  # what a build interrupted while it was copied left
    copies, external = {}, []

    def copy(p):
        real = os.path.realpath(p)
        if not under(real, roots) or not os.path.exists(real):
            return p
        if real not in copies:
            copies[real] = os.path.join(snap, f"{len(copies)}-{os.path.basename(real)}")
            clone(real, copies[real])
        return copies[real]

    cp = []
    for p in built["classpath"]:
        if under(os.path.realpath(p), roots):
            if os.path.exists(p):  # an empty output directory (no tests) is not created
                cp.append(copy(p))
        else:
            cp.append(p)
            st = os.stat(p) if os.path.exists(p) else None
            external.append({"path": p, "size": st and st.st_size, "mtime": st and int(st.st_mtime)})
    opts = []
    for o in built.get("javaOptions", []):
        if o.startswith("-D") and "=" in o:
            k, v = o.split("=", 1)
            o = k + "=" + os.pathsep.join(copy(x) for x in v.split(os.pathsep))
        opts.append(o)
    return {**built, "classpath": cp, "javaOptions": opts, "snapshot": snap, "external": external, "built": built}


def reusable(dir):
    """`dir` holds a snapshot, which `build` reuses."""
    try:
        return "snapshot" in read(os.path.join(dir, LAUNCH))
    except (OSError, ValueError):
        return False


class BuildFailed(SystemExit):
    """The build step failed, or built what `validate` refused. A SystemExit, so a caller that doesn't handle it stops
    with its message."""

    def __init__(self, reason, log):
        super().__init__(f"{reason} (see {log})")
        self.reason, self.log = reason, log


def build(dir, env=None, label=None, validate=None):
    """Runs [build] launch into `dir`, with the variables `env` set, and snapshots it there; the snapshot's launch.json.
    `label` names the build on the index while it runs. `validate(launch.json as built)` says what is wrong with a
    build, or None; a refused build is never snapshotted (raises BuildFailed, as a failed one does).
    An existing snapshot in `dir` is reused (a campaign that resumes measures the build it started with)."""
    from . import jmh
    path = os.path.join(dir, LAUNCH)
    if reusable(dir):
        launch = read(path)
        transcript.say(f"[perflab] build: the snapshot in {dir} ({describe(launch)})")
        return launch
    tpl = config.get().get("build", "launch")
    if not tpl:
        sys.exit("perflab.toml: [build] launch is not set (e.g. launch = \"sbt -batch 'bench/perflabLaunch {out}'\")")
    staging = os.path.join(dir, "build")
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    if env:
        transcript.say("[perflab] build with " + " ".join(f"{k}={v}" for k, v in env.items()))
    rc = jmh.run_build(tpl.replace("{out}", staging), os.path.join(staging, "build.log"), env=env,
                      label=label or os.path.relpath(dir, config.get().campaigns))
    built_f = os.path.join(staging, LAUNCH)
    log = os.path.join(staging, "build.log")
    if rc or not os.path.exists(built_f):
        raise BuildFailed(f"the build step failed (exit {rc})" if rc else f"the build step wrote no {LAUNCH}", log)
    built = read(built_f)
    if validate and (problem := validate(built)):
        raise BuildFailed(problem, log)
    launch = snapshot(built, dir)
    tmp = path + ".tmp"  # whole or not at all: a launch.json is what makes its snapshot reused
    with open(tmp, "w") as f:
        json.dump(launch, f, indent=2)
    os.replace(tmp, path)
    transcript.say(f"[perflab] build: snapshot of {describe(launch)} in {launch['snapshot']}")
    return launch


def describe(launch):
    b = launch.get("build", {})
    return f"{b.get('checkout', '?')} @ {(b.get('commit') or '?')[:10]}" + (" (dirty)" if b.get("dirty") else "")


def command(launch, args_file, java=None):
    """The command that runs JMH's driver from the snapshot, with `java` (default: the build's JDK)."""
    return shlex.join([java or launch["java"], *launch.get("javaOptions", []), "-cp", os.pathsep.join(launch["classpath"]),
                       launch["mainClass"], "@" + args_file])
