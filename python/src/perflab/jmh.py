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
command at `;`. Output: <out>/jmh.log, result.json, the profile's files (async's .jfr also holds the JDK's own events
of the measured window, GC, safepoints, JIT and so on, as perflab.jfc selects: `[async] jfrsync`), and timeline.html
(every fork's JVM start, iterations, GC pauses and exit on one wall-clock axis, plus PMU counter lanes with xctrace, and
VM operation and JIT lanes from the JDK's events with async);
afterwards flame graphs for async, a merged report for audits. The run is on the index (`perflab serve`, whose URL it prints first) as it goes: <out>/run.json holds
its status.
"""
import argparse, glob, json, os, shlex, shutil, subprocess, sys, threading, time

from . import config, launch, transcript

# retronym/async-profiler's integration branch as built by `mise run tools:async-profiler` (kperf events, jfrconv --spans
# and its flame graph UI), ahead of a stock install
LAB_ASYNC = os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3, "tools", "build", "async-profiler", "build")
ASYNC_LIBS = [os.path.join(LAB_ASYNC, "lib", "libasyncProfiler.dylib"), os.path.join(LAB_ASYNC, "lib", "libasyncProfiler.so"),
              "/opt/homebrew/lib/libasyncProfiler.dylib", "/usr/local/lib/libasyncProfiler.dylib",
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


PERFLAB_JFC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perflab.jfc")


def jfrsync():
    """async-profiler's jfrsync setting: the JDK events to record with its own, in the same .jfr; None for none."""
    cfg = config.get()
    v = cfg.get("async", "jfrsync")
    if v is True:
        return PERFLAB_JFC
    if not v:
        return None
    # a .jfc relative to the project root, else a predefined JFR profile (default, profile) or a +event list
    return cfg.path("async", "jfrsync") if v.endswith(".jfc") else v


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
            raw = [f"kperf={kperf}"]
            jvm = ["-XX:+UnlockDiagnosticVMOptions", "-XX:+DebugNonSafepoints", "-XX:+PreserveFramePointer"]
        else:
            # native frames through the VM, vtable/itable receivers, compile tasks; JMH's cstack option lacks `vm`
            raw = ["cstack=vm", "features=mixed+vtable+comptask"]
        # deep recursion (e.g. a compiler's typer) overflows async-profiler's default of 2048 frames, truncating stacks;
        # JMH's option parser has no stackdepth, so it goes in the raw command
        depth = config.get().get("async", "stackdepth")
        if depth:
            raw.append(f"jstackdepth={depth}")
        sync = jfrsync()
        if sync:
            raw.append(f"jfrsync={sync}")
        opts.append("rawCommand=" + ",".join(raw))
        return ["-prof", "async:" + ";".join(opts + async_events(arg or "cpu"))], jvm
    if kind == "audit":
        jar = config.get().path("agent", "jar")
        if not jar or not os.path.exists(jar):
            sys.exit("audit: [agent] jar in perflab.toml is not set or missing")
        spec = os.path.abspath(arg)
        return [], [f"-javaagent:{jar}=spec={spec},out={os.path.join(out, 'audit-{pid}.json')}"]
    sys.exit(f"unknown profile {profile!r}")


def jmh_command(args_file, built=None):
    """The command that runs JMH with `args_file`: [build] jmh, or in launch mode, `java` from the build's snapshot
    `built` (launch.build), with the JDK the arguments name by -jvm, else the build's."""
    if launch.enabled():
        if built is None:  # a dry run: the build step has not run
            return f"[launch mode] {config.get().get('build', 'launch')}; then java <the snapshot's options and classpath> <main> @{args_file}"
        with open(args_file) as f:
            args = f.read().splitlines()
        java = args[args.index("-jvm") + 1] if "-jvm" in args[:-1] else None
        return launch.command(built, args_file, java)
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
           "iterations.tsv", "timeline.tsv", "gc.log", "gc-*.log", "run.json"]


def prepare(out, profile, jmh_args, kperf=None, lib=None, jvm_append=None, built=None):
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
    return jmh_command(path, built)


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


def brief(cmd):
    """A command for the transcript: a classpath as its number of entries (the whole command is atop its log)."""
    try:
        words = shlex.split(cmd)
    except ValueError:
        return cmd
    for i, w in enumerate(words[:-1]):
        if w in ("-cp", "-classpath", "--class-path"):
            words[i + 1] = f"<{len(words[i + 1].split(os.pathsep))} entries>"
    return shlex.join(words) if len(words) > 1 else cmd


def run_build(cmd, log_path, every=None, tick=None):
    """Runs the build, logging to `log_path` and, line by line as it comes, to the transcript, followed by JMH's log
    beside it; calls `tick` every `every` seconds while it runs."""
    root = config.get().root
    transcript.say(f"[perflab] command: {brief(cmd)}\n[perflab] its log: {log_path}")
    with open(log_path, "w") as log:
        log.write(f"$ {cmd}\n")
        proc = subprocess.Popen(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1)

        def copy():
            for line in proc.stdout:
                log.write(line)
                log.flush()
                transcript.build_line(line)

        done = threading.Event()
        threads = [threading.Thread(target=copy, daemon=True),
                   threading.Thread(target=transcript.follow, args=(os.path.join(os.path.dirname(log_path), "jmh.log"), done), daemon=True)]
        for t in threads:
            t.start()
        try:
            while True:
                try:
                    return proc.wait(timeout=every)
                except subprocess.TimeoutExpired:
                    tick()
        finally:
            done.set()
            for t in threads:
                t.join(timeout=5)


def mark(out, status, **kw):
    """<out>/run.json: the run's status for the index (running, with perflab's pid; finished; failed, with the exit
    code), and while it runs <campaigns>/running.json names it, so the index's timeline follows it. Then the index is
    rebuilt."""
    from . import ab
    with open(os.path.join(out, "run.json"), "w") as f:
        json.dump({"status": status, "pid": os.getpid(), "time": time.time(), **kw}, f)
    campaigns = config.get().campaigns
    running = os.path.join(campaigns, ab.RUNNING_NAME)
    cell = os.path.relpath(out, campaigns)
    try:
        if status == "running":
            os.makedirs(campaigns, exist_ok=True)
            json.dump({"run": os.path.basename(out), "cell": cell, "started": time.time()}, open(running, "w"))
        elif json.load(open(running)).get("cell") == cell:
            os.unlink(running)
    except (OSError, ValueError):
        pass
    refresh_index()


def refresh_index():
    from . import index
    try:
        index.build(config.get().campaigns)
    except Exception as e:  # the index is a convenience; never let it stop a run
        print(f"[perflab] index not rebuilt: {e}", flush=True)


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
    if launch.enabled() and not x.dry_run:
        # the run's own snapshot of the build, made after `prepare` cleared the run's outputs
        build_dir = os.path.join(out, launch.BUILD_DIR)  # hidden: the index globs a run for its graphs
        shutil.rmtree(build_dir, ignore_errors=True)
        cmd = jmh_command(os.path.join(out, "jmh.args"), launch.build(build_dir))
    if x.dry_run:
        print(cmd)
        print(open(os.path.join(out, "jmh.args")).read(), end="")
        return 0
    from . import serve
    mark(out, "running")
    try:
        transcript.say(f"[perflab] index (updates as the run goes): {serve.ensure()}")
    except Exception as e:  # the index is a convenience; never let it stop a run
        transcript.say(f"[perflab] index not served: {e}")
    transcript.say(f"[perflab] output: {out}")
    try:
        rc = run_build(cmd, os.path.join(out, "build.log"), every=10, tick=refresh_index)
        if rc == 0:
            finish(out, x.profile, x.lib)
    except BaseException:
        mark(out, "interrupted")
        raise
    mark(out, "finished" if rc == 0 else "failed", rc=rc)
    transcript.say(f"[perflab] {'done' if rc == 0 else f'build exited with {rc}, see build.log'}: {out}")
    return rc
