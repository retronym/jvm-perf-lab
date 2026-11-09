"""One JMH run of a project's benchmarks under a profile, through the build command in `perflab.toml`.

  perflab run [--profile <profile>] [--out <dir>] [--dry-run] [--local] -- <jmh arguments>

While `perflab server` runs, the run goes to its queue and is followed here (Ctrl-C detaches); `--local` runs it here.

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
import argparse, glob, json, os, shlex, shutil, signal, subprocess, sys, threading, time

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
JIT_JFC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perflab-jit.jfc")
# a spec's "jitRecording": not .jfr, which every reader of an async profile's recording would take for it
JIT_RECORDING = "jit-*.jitrec"


def jit_recording(out):
    """The JVM argument that records the JIT over a whole fork (perflab-jit.jfc) in <out>/jit-<pid>.jitrec."""
    return f"-XX:StartFlightRecording:settings={JIT_JFC},filename={os.path.join(out, 'jit-%p.jitrec')}"


LAB = object()  # jfrsync's setting: the lab's ([async] jfrsync)


def jfrsync(setting=LAB, out_dir=None):
    """async-profiler's jfrsync setting: the JDK events to record with its own, in the same .jfr; None for none.
    `setting` is a campaign's (its spec's "jfrsync"), else the lab's `[async] jfrsync`: true for perflab.jfc, false
    for none, a .jfc (relative to the project root), a predefined JFR profile (default, profile), or events to add,
    `+jdk.A+jdk.B#threshold=0 ms` (`,` also separates them): the lab's .jfc (perflab.jfc unless it names one) with
    those enabled too, written to <out_dir>/jfrsync.jfc. async-profiler's own `+` list would record those events
    alone, without perflab.jfc's (the timeline's lanes)."""
    cfg = config.get()
    v = cfg.get("async", "jfrsync") if setting is LAB else setting
    if v is True:
        return PERFLAB_JFC
    if not v:
        return None
    v = str(v).strip()
    if v.startswith("+"):
        base = jfrsync() if setting is not LAB else PERFLAB_JFC
        return merge_jfc(base if base and base.endswith(".jfc") else PERFLAB_JFC, added_events(v),
                         os.path.join(out_dir or ".", "jfrsync.jfc"))
    if v.endswith(".jfc"):
        return os.path.join(cfg.root, os.path.expanduser(v))
    return v


def added_events(v):
    """`+jdk.A+jdk.B#threshold=0 ms` (or with `,`) -> [(event, {setting: value})], each enabled."""
    out = []
    for item in [x.strip() for x in v.replace(",", "+").split("+") if x.strip()]:
        name, *settings = item.split("#")
        kv = {"enabled": "true"}
        for st in settings:
            k, _, val = st.partition("=")
            kv[k.strip()] = val.strip()
        out.append((name.strip(), kv))
    return out


def merge_jfc(base, events, dest):
    """`base` with `events` ([(name, {setting: value})]) enabled, as `dest`; written only when it changes, so that a
    running campaign's cells all see the same file."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(base)
    root = tree.getroot()
    byname = {e.get("name"): e for e in root.iter("event")}
    for name, settings in events:
        e = byname.get(name)
        if e is None:
            e = ET.SubElement(root, "event", name=name)
            byname[name] = e
        for k, val in settings.items():
            st = next((x for x in e.iter("setting") if x.get("name") == k), None)
            if st is None:
                st = ET.SubElement(e, "setting", name=k)
            st.text = val
    text = ET.tostring(root, encoding="unicode")
    head = f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- {os.path.basename(base)} with {", ".join(n for n, _ in events)} (perflab: jfrsync) -->\n'
    text = head + text + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    if not os.path.exists(dest) or open(dest).read() != text:
        with open(dest + ".tmp", "w") as f:
            f.write(text)
        os.replace(dest + ".tmp", dest)
    return os.path.abspath(dest)


def async_events(spec, kperf=False):
    """`cpu,alloc` -> JMH async options; a `+`-joined list is one multi-event (kperf) session. A kperf event with no
    period gets perflab's default for it (`kperf.DEFAULT_PERIODS`), not async-profiler's."""
    from . import kperf as kp
    opts = []
    for e in [e for e in spec.split(",") if e]:
        if e == "alloc":
            opts.append("alloc=512k")
        elif e == "lock":
            opts.append("lock=1ms")
        elif e == "cpu":
            opts.append("event=cpu;interval=1000000")
        elif "+" in e:
            opts.append(f"event={kp.with_periods(e)}")
        elif "@" in e:
            name, interval = e.split("@", 1)
            opts.append(f"event={name};interval={interval}")
        elif kperf:
            opts.append(f"event={e};interval={kp.default_period(e)}")
        else:
            opts.append(f"event={e}")
    return opts


def profile_args(profile, out, kperf=None, lib=None, sync=LAB):
    """(JMH arguments, JVM arguments to prepend) for a profile, writing into `out`; `sync`: the resolved jfrsync
    (jfrsync()), else the lab's."""
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
        if sync is LAB:
            sync = jfrsync(LAB, out)
        if sync:
            raw.append(f"jfrsync={sync}")
        opts.append("rawCommand=" + ",".join(raw))
        return ["-prof", "async:" + ";".join(opts + async_events(arg or "cpu", bool(kperf)))], jvm
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
    if built is not None or launch.enabled():
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
JFRSYNC = "jfrsync.json"  # <cell>/jfrsync.json: the jfrsync the run was given, and what its recording has of what it added
OUTPUTS = ["jmh.log", JFRSYNC, JIT_RECORDING, "jit.json", "result.json", "report.md", "audit-*.json", "**/*.jfr", "**/*.html", "**/*.regraph", "*.trace", "*.trace.*",
           "iterations.tsv", "timeline.tsv", "gc.log", "gc.log.*", "gc-*.log", "run.json"]


def java_feature(java):
    """The feature release (25) of the JDK of `java`, from its home's `release` file; None if it cannot be read."""
    try:
        home = os.path.dirname(os.path.dirname(os.path.realpath(java)))
        with open(os.path.join(home, "release")) as f:
            v = next(l.split("=", 1)[1].strip().strip('"') for l in f if l.startswith("JAVA_VERSION="))
        parts = v.split(".")
        return int(parts[1] if parts[0] == "1" else parts[0])
    except (OSError, StopIteration, ValueError, IndexError, TypeError):
        return None


def quiet_jdk_warnings(java, jvm_args=""):
    """The options that keep a fork on `java` from warning about what JMH and the benchmarks do: sun.misc.Unsafe's
    memory access (JMH's Utils; JDK 23+) and restricted methods of unnamed modules (the Linker; JDK 22+). Neither changes
    what runs, only the warning. Only for a JDK known by its release file (an option an older one does not know stops
    it), and not when the arguments set them already."""
    v = java_feature(java) if java else None
    out = []
    if v and v >= 22 and "--enable-native-access" not in (jvm_args or ""):
        out.append("--enable-native-access=ALL-UNNAMED")
    if v and v >= 23 and "--sun-misc-unsafe-memory-access" not in (jvm_args or ""):
        out.append("--sun-misc-unsafe-memory-access=allow")
    return " ".join(out)


def prepare(out, profile, jmh_args, kperf=None, lib=None, jvm_append=None, built=None, sync=LAB):
    """Writes <out>/jmh.args for this run and returns the build command that runs it."""
    os.makedirs(out, exist_ok=True)
    import shutil
    for pattern in OUTPUTS:
        for f in glob.glob(os.path.join(out, pattern), recursive=True):
            shutil.rmtree(f) if os.path.isdir(f) else os.unlink(f)
    if profile.startswith("async") and sync is LAB:
        sync = jfrsync(LAB, out)
    prof, prepend = profile_args(profile, out, kperf, lib, sync)
    args = ["-o", os.path.join(out, "jmh.log"), "-rf", "json", "-rff", os.path.join(out, "result.json"), *prof]
    if prepend:
        args += ["-jvmArgsPrepend", " ".join(prepend)]
    quiet = quiet_jdk_warnings(jmh_args[jmh_args.index("-jvm") + 1] if "-jvm" in jmh_args[:-1] else None, jvm_append)
    jvm_append = " ".join(x for x in [quiet, jvm_append] if x)
    if jvm_append:
        args += ["-jvmArgsAppend", jvm_append]
    args += jmh_args
    path = os.path.join(out, "jmh.args")
    write_args(path, args)
    with open(os.path.join(out, "profile.txt"), "w") as f:
        f.write(profile + "\n")
    if profile.startswith("async"):
        with open(os.path.join(out, JFRSYNC), "w") as f:
            json.dump({"jfrsync": sync}, f)
            f.write("\n")
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


BUILD_STATE = "build.json"  # in <campaigns> while a build step runs, for the index's build panel


def run_build(cmd, log_path, every=None, tick=None, env=None, label=None):
    """Runs the build, logging to `log_path` and, line by line as it comes, to the transcript, followed by JMH's log
    beside it; calls `tick` every `every` seconds while it runs. `env`: variables set for it. With a `label`, the index
    shows it as a build in progress (<campaigns>/build.json: the label, the command and the log's last lines)."""
    from . import loadgate
    root = config.get().root
    transcript.say(f"[perflab] command: {brief(cmd)}\n[perflab] its log: {log_path}")
    state = label and {"pid": os.getpid(), "label": label, "cmd": brief(cmd), "log": os.path.relpath(os.path.abspath(log_path), os.path.dirname(loadgate.state_path(BUILD_STATE))),
                       "started": time.time(), "updated": time.time(), "lines": 0, "tail": []}
    if state:  # a campaign's build (<campaigns>/<campaign>/.build/...): its card on the index shows it building
        rel = os.path.relpath(os.path.abspath(log_path), os.path.abspath(config.get().campaigns))
        state["campaign"] = None if rel.startswith("..") else rel.split(os.sep)[0]

    def show():
        state["updated"] = time.time()
        loadgate.publish(state, BUILD_STATE)

    with open(log_path, "w") as log:
        log.write(f"$ {cmd}\n")
        proc = subprocess.Popen(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1, env={**os.environ, **env} if env else None,
                                start_new_session=True)  # its own process group, so stop() reaches what it starts

        def stop():
            """perflab is exiting early (SIGTERM, Ctrl-C, an error): the build and the JVMs it started go with it,
            rather than running on, unwatched, with perflab waiting on them."""
            if proc.poll() is not None:
                return
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                    proc.wait(timeout=10)
                    return
                except ProcessLookupError:
                    return
                except subprocess.TimeoutExpired:
                    pass

        def copy():
            for line in proc.stdout:
                log.write(line)
                log.flush()
                transcript.build_line(line)
                if state:
                    state["lines"] += 1
                    state["tail"] = (state["tail"] + [transcript.ANSI.sub("", line).rstrip()])[-15:]
                    if time.time() - state["updated"] > 1:
                        show()

        done = threading.Event()
        threads = [threading.Thread(target=copy, daemon=True),
                   threading.Thread(target=transcript.follow, args=(os.path.join(os.path.dirname(log_path), "jmh.log"), done), daemon=True)]
        for t in threads:
            t.start()
        # a build can be silent for minutes (a large compile): a heartbeat tells the index it is still running
        beat = 5 if state else None
        next_tick = time.time() + every if every else None
        try:
            if state:
                show()
            while True:
                try:
                    return proc.wait(timeout=min(x for x in (beat, every) if x) if beat or every else None)
                except subprocess.TimeoutExpired:
                    if state:
                        show()
                    if next_tick and time.time() >= next_tick:
                        tick()
                        next_tick = time.time() + every
        finally:
            stop()
            done.set()
            for t in threads:
                t.join(timeout=5)
            proc.stdout.close()
            if state:
                loadgate.publish(None, BUILD_STATE)


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
        index.rebuild(config.get().campaigns)
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
