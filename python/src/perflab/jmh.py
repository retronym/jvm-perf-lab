"""One JMH run of a project's benchmarks under a profile, through the build command in `perflab.toml`.

  perflab run [--profile <profile>] [--out <dir>] [--dry-run] -- <jmh arguments>

Profiles:
  none                       JMH and the driver's default profilers only
  xctrace:<template>         Apple PMU counters (XctraceProfiler); <template>: ipc, frontend, mem-l1d (bundled), a path,
                             or an Instruments template such as "CPU Counters"
  async:<events>             async-profiler, recording JFR; <events> comma-separated: cpu, wall, alloc, lock, or an
                             async-profiler event, optionally <event>@<interval>; on macOS with a kperf helper,
                             several PMU events in one session joined by `+` (cycles+cache-misses@10000)
  audit:<spec>               the caller-audit agent with the probes of <spec>

Options for async: --kperf <socket> (macOS PMU events through a running asprof-kperf helper), --lib <libasyncProfiler>.

The arguments go to the build in a file, as `@file`, so no profiler option is ever typed into a tool that splits a
command at `;`. Output: <out>/jmh.log, result.json, the profile's files, and timeline.html (every fork's JVM start, iterations, GC
pauses and exit on one wall-clock axis, plus PMU counter lanes with xctrace); afterwards flame graphs for async, a merged
report for audits.
"""
import argparse, glob, os, shlex, subprocess, sys, time

from . import config

ASYNC_LIBS = ["/opt/homebrew/lib/libasyncProfiler.dylib", "/usr/local/lib/libasyncProfiler.dylib",
              "/usr/local/lib/libasyncProfiler.so", "/usr/lib/libasyncProfiler.so"]
XCTRACE = "io.github.retronym.perflab.xctrace.XctraceProfiler"


def async_lib(explicit=None):
    cfg = config.get()
    for c in [explicit, cfg.path("async", "lib"), os.environ.get("ASYNC_PROFILER_LIB"), *ASYNC_LIBS]:
        if c and os.path.exists(c):
            return c
    return None


def jfrconv(lib=None):
    cfg = config.get()
    beside = os.path.join(os.path.dirname(os.path.dirname(lib)), "bin", "jfrconv") if lib else None
    for c in [cfg.path("async", "jfrconv"), os.environ.get("JFRCONV"), beside]:
        if c and os.path.exists(c):
            return c
    return "jfrconv"


def async_events(spec):
    """`cpu,alloc` -> JMH async options; a `+`-joined list is one multi-event (kperf) session."""
    opts = []
    for e in [e for e in spec.split(",") if e]:
        if e == "alloc":
            opts.append("alloc=512k")
        elif e == "lock":
            opts.append("lock=1ms")
        elif e == "cpu":
            opts.append("event=cpu;interval=1000000")
        elif "+" in e:
            opts.append(f"event={e}")
        elif "@" in e:
            name, interval = e.split("@", 1)
            opts.append(f"event={name};interval={interval}")
        else:
            opts.append(f"event={e}")
    return opts


def profile_args(profile, out, kperf=None, lib=None):
    """(JMH arguments, JVM arguments to prepend) for a profile, writing into `out`."""
    kind, _, arg = profile.partition(":")
    if kind == "none":
        return [], []
    if kind == "xctrace":
        return ["-prof", f"{XCTRACE}:template={arg or 'ipc'};dir={out}"], []
    if kind == "async":
        lib = async_lib(lib)
        opts = [f"output=jfr", f"dir={out}"] + ([f"libPath={lib}"] if lib else [])
        jvm = []
        if kperf:
            # PMU events through the asprof-kperf helper: the kernel walks stacks by frame pointer
            opts.append(f"rawCommand=kperf={kperf}")
            jvm = ["-XX:+UnlockDiagnosticVMOptions", "-XX:+DebugNonSafepoints", "-XX:+PreserveFramePointer"]
        else:
            # native frames through the VM, vtable/itable receivers, compile tasks; JMH's cstack option lacks `vm`
            opts.append("rawCommand=cstack=vm,features=mixed+vtable+comptask")
        return ["-prof", "async:" + ";".join(opts + async_events(arg or "cpu"))], jvm
    if kind == "audit":
        jar = config.get().path("agent", "jar")
        if not jar or not os.path.exists(jar):
            sys.exit("audit: [agent] jar in perflab.toml is not set or missing")
        spec = os.path.abspath(arg)
        return [], [f"-javaagent:{jar}=spec={spec},out={os.path.join(out, 'audit-{pid}.json')}"]
    sys.exit(f"unknown profile {profile!r}")


def jmh_command(args_file):
    tpl = config.get().get("build", "jmh")
    if not tpl:
        sys.exit("perflab.toml: [build] jmh is not set (e.g. jmh = \"sbt --client 'bench/Jmh/run {args}'\")")
    return tpl.replace("{args}", "@" + args_file)


def write_args(path, args):
    """One argument per line, as the driver's `@file` expects (no quoting)."""
    with open(path, "w") as f:
        f.write("\n".join(args) + "\n")


# what a run writes into its directory: cleared before the next run there, so nothing stale is merged into its results
OUTPUTS = ["jmh.log", "result.json", "report.md", "audit-*.json", "**/*.jfr", "**/*.html", "**/*.regraph", "*.trace", "*.trace.*",
           "iterations.tsv", "timeline.tsv", "gc.log", "gc-*.log"]


def prepare(out, profile, jmh_args, kperf=None, lib=None, jvm_append=None):
    """Writes <out>/jmh.args for this run and returns the build command that runs it."""
    os.makedirs(out, exist_ok=True)
    import shutil
    for pattern in OUTPUTS:
        for f in glob.glob(os.path.join(out, pattern), recursive=True):
            shutil.rmtree(f) if os.path.isdir(f) else os.unlink(f)
    prof, prepend = profile_args(profile, out, kperf, lib)
    args = ["-o", os.path.join(out, "jmh.log"), "-rf", "json", "-rff", os.path.join(out, "result.json"), *prof]
    if prepend:
        args += ["-jvmArgsPrepend", " ".join(prepend)]
    if jvm_append:
        args += ["-jvmArgsAppend", jvm_append]
    args += jmh_args
    path = os.path.join(out, "jmh.args")
    write_args(path, args)
    with open(os.path.join(out, "profile.txt"), "w") as f:
        f.write(profile + "\n")
    return jmh_command(path)


def finish(out, profile, lib=None):
    """Post-processing: flame graphs for async, the merged report for audits."""
    kind, _, arg = profile.partition(":")
    from . import timeline
    if os.path.exists(os.path.join(out, "iterations.tsv")):
        timeline.write(out)
    if kind == "async":
        from . import regraph
        regraph.regraph([out], jfrconv(async_lib(lib)))
    elif kind == "audit":
        reports = sorted(glob.glob(os.path.join(out, "audit-*.json")))
        if reports:
            from . import auditfold
            with open(os.path.join(out, "report.md"), "w") as f:
                auditfold.main(reports, out=f)


def run_build(cmd, log_path):
    root = config.get().root
    with open(log_path, "w") as log:
        return subprocess.run(cmd, shell=True, cwd=root, stdout=log, stderr=subprocess.STDOUT).returncode


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="none")
    ap.add_argument("--out")
    ap.add_argument("--kperf")
    ap.add_argument("--lib")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("jmh", nargs=argparse.REMAINDER)
    x = ap.parse_args(argv)
    jmh_args = x.jmh[1:] if x.jmh[:1] == ["--"] else x.jmh
    name = x.profile.replace(":", "-").replace("/", "_").replace(",", "-")
    out = os.path.abspath(x.out or os.path.join(config.get().runs, f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"))
    # every fork appends its iterations to <out>/iterations.tsv (PairedProfiler) and logs GC to <out>/gc-<pid>.log: the timeline
    timeline_args = f"-Dperflab.cell={out} -Xlog:gc:file={out}/gc-%p.log:time,uptime"
    jvm_args = " ".join(a for a in [config.get().get("benchmark", "jvmArgs"), timeline_args] if a)
    cmd = prepare(out, x.profile, jmh_args, x.kperf, x.lib, jvm_args)
    if x.dry_run:
        print(cmd)
        print(open(os.path.join(out, "jmh.args")).read(), end="")
        return 0
    print(f"[perflab] {cmd}\n[perflab] output: {out}", flush=True)
    rc = run_build(cmd, os.path.join(out, "build.log"))
    if rc == 0:
        finish(out, x.profile, x.lib)
    print(f"[perflab] {'done' if rc == 0 else f'build exited with {rc}, see build.log'}: {out}")
    return rc
