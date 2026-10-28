"""Campaigns: a benchmark under one profile, over corpora and variants, run round by round with the variants
interleaved, each run checked against the spec.

  perflab ab run    <spec.json> [--dry-run] [--local] [--retry-unbuildable]
                                              runs every missing cell; resumable. On `perflab server`'s queue while
                                              one runs (--local: here). --retry-unbuildable: a branch's commits that
                                              did not build are built again (else their cells are skipped)
  perflab ab report <spec.json> [--per-op]    markdown summary, per "perUnit" if the spec has one (--per-op: per op);
                                              for async profiles, an index of flame graphs

A spec:

  {
    "name": "exp12",                          # cells go to <campaigns>/<name>/<corpus>/<variant>/<round>
    "benchmark": "CompileBenchmark",          # default: [benchmark] default in perflab.toml
    "profile": "xctrace:ipc",                 # as `perflab run --profile`: none, xctrace:<template>, async:<events>
    "kperf": "/tmp/asprof-kperf.sock",        # optional, for async: macOS PMU events through the kperf helper
    "lib": "<libasyncProfiler>",              # optional, for async
    "jvm": "<java>",                          # optional: JMH -jvm for every run (checked against result.json)
    "jvmArgs": "-Xms4G -Xmx4G -Xss2M",        # given to every variant; default: [benchmark] jvmArgs
    "rounds": 2,
    "corpora": {"scalaz": "-wi 10 -i 10 -w 10 -r 10"},   # corpus -> JMH arguments; set as the [benchmark] corpus param
    "variants": {"base": "", "U": "-Dfoo.bar"},          # JVM flags per variant; the first is the report's baseline
    "variantJmhArgs": {"U": "-p scalacOptions=-Yx"},     # optional: JMH arguments per variant (checked)
    "paired": {"base": "-Yx", "fast": ""},               # instead of variants: options per variant, alternating by
                                                         # iteration within each fork (doc/paired-ab.md)
    "loadgate": {"maxCores": 1.5, "quietSecs": 30},      # optional: wait for a quiet machine, rerun noisy cells
    "gcLog": true,                                       # optional: gc.log per cell, for its timeline
    "perUnit": "files",                                  # optional: an aux counter of the benchmark; the summary and
                                                         # report divide every count by its units per op (cycles/file)
    "builds": {"base": {"checkout": "../scala3-base", "env": {"SCALA3_CHECKOUT": "{checkout}"}}, "pr": {...}},
                                                         # optional: a build per variant (launch mode: [build] launch
                                                         # with env set, snapshotted in <campaign>/.build/<variant>);
                                                         # "variants" defaults to their names
    "historical": "<why>",                               # optional: kept for its results; `run` refuses it
    "description": "Does -Yx help? See [#123](<url>).",  # optional Markdown (a string, or a list of lines): the
    "variantDescriptions": {"U": "uncached, from **#123**"}  # campaign and each variant, in a panel atop its card
  }

A branch campaign ("branch", perflab.branch) has its commits as variants. Its profiles are a campaign of their own,
"profileOf" it (written by `perflab branch profile`, perflab.branchprofile), whose variants are the commits profiled so
far and whose builds are the branch campaign's. A commit that does not build is recorded in <campaign>/unbuildable.json
and its cells are skipped, by this run and later ones; the campaign goes on with the other commits. A run with
--retry-unbuildable builds them again.

Cells run round by round, corpus by corpus, variants interleaved within each, so drift hits every variant alike. Each
run is checked: fresh results, the JVM, every JVM argument of the spec (JMH's -jvmArgsAppend replaces the benchmark's
@Fork(jvmArgsAppend), so every variant is given `jvmArgs`), each variant's `-p` parameters, xctrace counters present,
and for kperf, that samples were not lost.

The report and the index's summary show every metric a cell recorded (`metrics`): the score; the benchmark threads'
cycles, instructions and IPC; allocation; each PMU counter of the xctrace template, or each kperf event of an async
profile, per op and per 1,000 instructions or as % of cycles; JIT, GC and other threads' share of cycles and IPC, and
the cycles, instructions and IPC of all threads. With "perUnit" (a JMH @AuxCounters events counter, such as "files"),
every per-op count, allocation and the score are divided by the counter's units per op (its sum over the measurement
iterations over their ops): with variants that do different amounts of work per op, Δ against the first variant
compares the work, not the op. The index's summary toggles between per unit and per op; the report is per unit unless
--per-op.
"""
import atexit, glob, json, os, re, shlex, shutil, subprocess, sys, time

from . import branch, config, jmh, launch, loadgate, metrics, specs, transcript

JMH_LOCK = os.path.join(os.environ.get("TMPDIR", "/tmp"), "jmh.lock")
MAX_ATTEMPTS = 10


def log(msg):
    transcript.say(f"[ab {time.strftime('%H:%M:%S')}] {msg}")


class Spec:
    def __init__(self, path):
        s = json.load(open(path))
        self.path = path
        cfg = config.get()
        self.name = s["name"]
        self.benchmark = s.get("benchmark") or cfg.get("benchmark", "default")
        if not self.benchmark:
            sys.exit(f"{path}: no benchmark (spec \"benchmark\", or [benchmark] default in perflab.toml)")
        p = s.get("profile", "none")
        if isinstance(p, dict):  # {"xctrace": "ipc"} / {"async": "...", "kperf": ..., "lib": ...}
            s = {**p, **s}
            p = f"xctrace:{p['xctrace']}" if "xctrace" in p else f"async:{p['async']}" if "async" in p else "none"
        self.profile = p
        self.kperf, self.lib = s.get("kperf"), s.get("lib")
        self.jvm_args = s.get("jvmArgs", cfg.get("benchmark", "jvmArgs") or "")
        self.jvm = s.get("jvm")
        self.rounds = s.get("rounds", 2)
        self.corpora = s["corpora"]
        self.corpus_param = cfg.get("benchmark", "corpus")
        self.paired = s.get("paired")
        # "builds": {variant: {"checkout": <dir>, "env": {...}}}: each variant its own build, in launch mode
        # (doc/direct-launch.md); "{checkout}" in a value is the checkout's path, relative ones are to the spec's
        here = os.path.dirname(os.path.abspath(path))
        self.builds = {v: {**b, "checkout": os.path.normpath(os.path.join(here, b["checkout"])) if b.get("checkout") else None}
                       for v, b in (s.get("builds") or {}).items()}
        self.out = os.path.join(cfg.campaigns, self.name)
        # "branch": the commits of a range as variants, each its own build (perflab.branch)
        self.branch = s.get("branch")
        self.branch_info = None
        if self.branch:
            if self.builds or self.paired or s.get("variants"):
                sys.exit(f"{path}: \"branch\" makes the variants; it cannot have \"variants\", \"builds\" or \"paired\"")
            self.branch = {**self.branch, "checkout": os.path.normpath(os.path.join(here, self.branch["checkout"]))}
            self.branch_info = branch.load(self.out, self.branch, write=False)
            self.builds = {c["variant"]: {"checkout": self.branch["checkout"], "commit": c} for c in self.branch_info["commits"]}
        # "profileOf": the profiles of a branch campaign's commits (perflab.branchprofile), with its commits and builds
        self.profile_of = s.get("profileOf")
        self.build_out = self.out
        if self.profile_of:
            self.build_out = os.path.join(cfg.campaigns, self.profile_of)
            self.branch_info = json.load(open(os.path.join(self.build_out, branch.BRANCH)))
            of = json.load(open(os.path.join(self.build_out, "spec.json"))).get("branch") or {}
            self.branch = {"checkout": self.branch_info["checkout"], "env": of.get("env") or {}}
            commits = {c["variant"]: c for c in self.branch_info["commits"]}
            self.builds = {v: {"checkout": self.branch["checkout"], "commit": commits[v]} for v in s.get("variants") or {}}
        self.only = None  # the variants to run, of the spec's (`perflab branch profile <sha>...`)
        self.variants = {"paired": ""} if self.paired else s.get("variants") or {v: "" for v in self.builds}
        if self.builds and (self.paired or set(self.builds) != set(self.variants)):
            sys.exit(f"{path}: \"builds\" needs a build for each variant, and cannot be paired")
        self.variant_jmh_args = s.get("variantJmhArgs", {})
        if self.paired:
            spec = "|".join(f"{n}={o}" for n, o in self.paired.items())
            if "," in spec:
                sys.exit("paired: JMH splits parameter values at commas; options cannot contain one")
            # quoted: a variant's options may be several words, and this string is split as a command line
            self.variant_jmh_args = {"paired": "-p " + shlex.quote(f"{cfg.get('benchmark', 'variants')}={spec}")}
        self.loadgate = s.get("loadgate")
        self.gc_log = s.get("gcLog", False)
        self.per_unit = s.get("perUnit")
        self.historical = s.get("historical")
        self.description, self.variant_descriptions = s.get("description"), s.get("variantDescriptions") or {}

    def cells(self):
        if self.branch_info:
            order = [v for v in self.branch_info["order"] if v in self.variants and (self.only is None or v in self.only)]
            for r, corpus, variant in branch.cells(self.rounds, self.corpora, order):
                yield r, corpus, self.corpora[corpus], variant, ""
            return
        for r in range(1, self.rounds + 1):
            for corpus, iters in self.corpora.items():
                for variant, flags in self.variants.items():
                    yield r, corpus, iters, variant, flags

    def cell_dir(self, corpus, variant, r):
        return os.path.join(self.out, corpus, variant, str(r))

    def command(self, corpus, iters, variant, flags, dest, built=None):
        """Writes the cell's arguments file and returns the build command that runs it."""
        extra = []
        if self.gc_log:
            extra.append(f"-Xlog:gc:file={dest}/gc.log:time,uptime")
        # the fork appends its iterations to <dest>/iterations.tsv as they finish (PairedProfiler)
        extra.append(f"-Dperflab.cell={dest}")
        jvm_args = " ".join(x for x in [self.jvm_args, flags, *extra] if x)
        args = (["-jvm", self.jvm] if self.jvm else []) + ["-p", f"{self.corpus_param}={corpus}"]
        args += shlex.split(iters) + shlex.split(self.variant_jmh_args.get(variant, "")) + [self.benchmark]
        return jmh.prepare(dest, self.profile, args, self.kperf, self.lib, jvm_args, built)


def jmh_lock_held():
    return subprocess.run(["lsof", JMH_LOCK], capture_output=True).returncode == 0


RUNNING_NAME = "running.json"


def set_running(spec, dest):
    """<campaigns>/running.json names the cell being run (the index's timeline follows it); the index is rebuilt, so
    the page picks up new cells and results."""
    running = os.path.join(config.get().campaigns, RUNNING_NAME)
    if dest:
        os.makedirs(os.path.dirname(running), exist_ok=True)
        json.dump({"campaign": spec.name, "cell": os.path.relpath(dest, os.path.dirname(running)), "started": time.time()},
                  open(running, "w"))
        atexit.register(lambda: set_running(spec, None))
    elif os.path.exists(running):
        os.unlink(running)
    from . import index
    try:
        index.rebuild(config.get().campaigns)
    except Exception as e:  # the index is a convenience; never let it stop a campaign
        log(f"  index not rebuilt: {e}")


def wait_until_quiet(spec):
    while jmh_lock_held():
        log("JMH lock held by another run; waiting")
        time.sleep(30)
    if spec.loadgate:
        g = spec.loadgate
        loadgate.wait(loadgate.server_pid(), g.get("maxCores", 1.5), g.get("quietSecs", 30))


LOAD_SECS = 2  # a load sample's window: shorter than a measurement iteration, to say which ones a burst hit
LOAD_CHECK = "load.json"  # in a cell: each measurement iteration's competing load, and the gate's verdict


def start_load_sampler(spec, path):
    """Competing load every LOAD_SECS while a cell runs, into `path`."""
    if os.path.exists(path):
        os.unlink(path)
    if not spec.loadgate:
        return None
    return subprocess.Popen([sys.executable, "-m", "perflab", "loadgate", "sample", str(loadgate.server_pid()), path, str(LOAD_SECS)])


def load_check(spec, dest):
    """The measurement iterations that ran while other load was over the gate's maxCores (the mean over a cell hides a
    burst that hits two of its iterations), recorded in <cell>/load.json; [] when none did, or without a gate."""
    if not spec.loadgate:
        return []
    its = loadgate.per_iteration(os.path.join(dest, "load.tsv"), os.path.join(dest, "iterations.tsv"))
    limit = spec.loadgate.get("maxCores", 1.5)
    hit = [i for i in its if i["cores"] is not None and i["cores"] > limit]
    with open(os.path.join(dest, LOAD_CHECK), "w") as f:
        json.dump({"maxCores": limit, "iterations": its, "disturbed": [i["index"] for i in hit]}, f)
    return hit


def mean_load(path):
    """Mean competing load in cores over a cell's samples (0 without samples)."""
    try:
        xs = [float(l.split("\t")[1]) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return 0.0
    return sum(xs) / len(xs) if xs else 0.0


def check(spec, dest, started, flags, variant, built=None):
    """The run produced fresh results, with the JVM arguments and benchmark parameters the spec asked for."""
    res = os.path.join(dest, "result.json")
    if not os.path.exists(res) or os.path.getmtime(res) < started:
        return "no fresh result.json (see build.log)"
    rs = json.load(open(res))
    if not rs:
        return "empty result.json"
    if spec.profile.startswith("xctrace") and not any(k.startswith("xctrace.") for k in rs[0]["secondaryMetrics"]):
        return "no xctrace counters in result.json (see jmh.log)"
    if spec.jvm and os.path.realpath(rs[0]["jvm"]) != os.path.realpath(spec.jvm):
        return f"ran on {rs[0]['jvm']}, not {spec.jvm}"
    args = rs[0]["jvmArgs"]
    for a in (spec.jvm_args + " " + flags).split():
        if a not in args:
            return f"JVM argument {a} missing from the run's jvmArgs: {args}"
    words = shlex.split(spec.variant_jmh_args.get(variant, ""))
    for flag, kv in zip(words, words[1:]):
        if flag == "-p" and "=" in kv:
            name, value = kv.split("=", 1)
            got = rs[0].get("params", {}).get(name)
            if got != value:
                return f"parameter {name}: the run had {got!r}, not {value!r}"
    # in launch mode, the fork ran from this variant's snapshot: its options that name the snapshot reached the fork
    for o in (built or {}).get("javaOptions", []):
        if built["snapshot"] in o and o not in args:
            return f"the fork did not run from {built['snapshot']}: {o} missing from its jvmArgs"
    # a later -Xmx/-Xms/-Xss wins; make sure it is ours
    for opt in ("-Xmx", "-Xms", "-Xss"):
        ours = [a for a in spec.jvm_args.split() if a.startswith(opt)]
        last = [a for a in args if a.startswith(opt)][-1:]
        if ours and last != ours[-1:]:
            return f"{opt}: the run used {last}, not {ours[-1]}"
    return None


def check_samples(spec, dest):
    """A kperf recording can come back nearly empty (samples lost in the helper): the benchmark threads must show at
    least 0.5 GHz worth of cycles per op."""
    from . import profdiff
    r = profdiff.load(dest, "cycles", jmh.jfrconv(jmh.async_lib(spec.lib)), dest, "check")
    os.unlink(r["collapsed"])
    cycles = r["total"] / r["ops"]
    if cycles < 0.5e6 * r["score"]:
        return f"only {cycles / 1e9:.2f}G cycles/op sampled on the benchmark threads at {r['score']:.0f} ms/op: lost samples?"
    return None


def run(spec, dry, retry_unbuildable=False):
    if spec.historical:
        sys.exit(f"{spec.name} is historical, kept for its results; not running it: {spec.historical}")
    cells = list(spec.cells())
    # the campaign keeps its spec: the index orders variants by it, and a report can be rerun from the results alone
    os.makedirs(spec.out, exist_ok=True)
    if os.path.abspath(spec.path) != os.path.abspath(os.path.join(spec.out, "spec.json")):
        shutil.copy(spec.path, os.path.join(spec.out, "spec.json"))
    # the spec version cells are tagged with; `perflab trees` records the user's spec once and passes its id down
    version = os.environ.get(specs.ENV) or specs.record(spec.out, spec.path)
    todo = [c for c in cells if not done(spec.cell_dir(c[1], c[3], c[0]))]
    log(f"{spec.name}: {len(cells)} cells, {len(todo)} to run")
    if not dry:
        # the index first: it lists the campaign's cells before any has run, and updates itself as they finish
        from . import serve
        try:
            log(f"index (updates as cells finish): {serve.ensure()}")
        except Exception as e:  # the index is a convenience; never let it stop a campaign
            log(f"index not served: {e}")
    # launch mode: the campaign's build, or each variant's, made once and kept, so every cell (and a resumed campaign)
    # measures the same build
    built = {}
    if spec.builds:  # builds are snapshots: launch mode, for this campaign (and a dry run shows it)
        os.environ["PERFLAB_BUILD_MODE"] = "launch"
    if spec.branch_info and not dry and not spec.profile_of:
        branch.save(spec.out, spec.branch_info)
    if launch.enabled() and todo and not dry and not spec.branch_info:  # a branch builds each commit before its first cell
        for v in dict.fromkeys(c[3] for c in todo):
            b = spec.builds.get(v)
            if b is None:
                built[v] = built.get(None) or launch.build(os.path.join(spec.out, launch.BUILD_DIR), label=spec.name)
                built[None] = built[v]
            else:
                env = {k: str(x).replace("{checkout}", b["checkout"] or "") for k, x in (b.get("env") or {}).items()}
                log(f"build of {v}: {b['checkout'] or ''}")
                built[v] = launch.build(os.path.join(spec.out, launch.BUILD_DIR, v), env,
                                        label=f"{spec.name}: {v} ({b['checkout'] or ''})")
    # a branch's commits that did not build: their cells are skipped (until a run with --retry-unbuildable)
    unbuildable = branch.unbuildable(spec.build_out) if spec.branch_info and not retry_unbuildable else {}
    skipped, failed = {}, []
    for r, corpus, iters, variant, flags in todo:
        dest = spec.cell_dir(corpus, variant, r)
        if variant in unbuildable:
            if variant not in skipped:
                skipped[variant] = unbuildable[variant]["reason"]
                log(f"{variant}: its cells are skipped, it did not build ({skipped[variant]})")
            continue
        if os.environ.get("PERFLAB_CONTROL") and not dry:  # under perflab server: pause or cancel between cells
            from . import control
            control.checkpoint()
        if spec.branch_info and variant not in built and not dry:
            built[variant] = build_commit(spec, spec.builds[variant]["commit"])
            if built[variant] is None:
                unbuildable[variant] = branch.unbuildable(spec.build_out)[variant]
                skipped[variant] = unbuildable[variant]["reason"]
                continue
        cmd = spec.command(corpus, iters, variant, flags, dest, built.get(variant))
        if not dry:
            specs.tag(dest, version)
            if os.path.exists(os.path.join(dest, FAILED)):
                os.unlink(os.path.join(dest, FAILED))
        if dry:
            print(f"{dest}:\n  {cmd}")
            continue
        for attempt in range(1, MAX_ATTEMPTS + 1):
            wait_until_quiet(spec)
            log(f"round {r} {corpus} {variant}" + (f" (attempt {attempt})" if attempt > 1 else ""))
            set_running(spec, dest)
            started = time.time()
            load_tsv = os.path.join(dest, "load.tsv")
            sampler = start_load_sampler(spec, load_tsv)
            try:
                rc = jmh.run_build(cmd, os.path.join(dest, "build.log"))
            finally:
                if sampler:
                    sampler.terminate()
                    sampler.wait()
            # another JMH run took the lock between wait_until_quiet and our JMH starting: JMH exits before logging
            jmh_log = os.path.join(dest, "jmh.log")
            if rc and jmh_lock_held() and (not os.path.exists(jmh_log) or os.path.getsize(jmh_log) == 0):
                log("  JMH did not start, another run holds the JMH lock; retrying")
                continue
            load = mean_load(load_tsv)
            if not rc and spec.loadgate and load > spec.loadgate.get("maxCores", 1.5):
                log(f"  other load averaged {load:.1f} cores during the run; rerunning")
                continue
            hit = [] if rc else load_check(spec, dest)
            if hit:
                worst = max(hit, key=lambda i: i["cores"])
                log(f"  other load over {spec.loadgate.get('maxCores', 1.5)} cores during measurement iteration"
                    f"{'s' if len(hit) > 1 else ''} {', '.join(str(i['index']) for i in hit)} (up to {worst['cores']:.1f}: {worst['top']}); rerunning")
                continue
            break
        else:
            sys.exit(f"{dest}: no clean run in {MAX_ATTEMPTS} attempts")
        problem = f"build exited with {rc} (see {dest}/build.log)" if rc else check(spec, dest, started, flags, variant, built.get(variant))
        if not problem and spec.kperf and spec.profile.startswith("async:cycles"):
            problem = check_samples(spec, dest)
        if problem and spec.branch_info:
            # a commit whose run fails is a result of the branch, not the end of the campaign: recorded in the cell (the
            # view shows it), the other cells run, and a resume tries it again
            with open(os.path.join(dest, FAILED), "w") as f:
                f.write(problem + "\n")
            set_running(spec, None)
            log(f"  failed: {problem}")
            failed.append(f"{os.path.relpath(dest, spec.out)}: {problem}")
            continue
        if problem:
            sys.exit(f"{dest}: {problem}")
        # the xctrace profiler names its files after the trace; the timeline reads them by fixed names
        for kind in ("timeline", "iterations", "threads"):
            ext = "txt" if kind == "threads" else "tsv"
            for f in glob.glob(os.path.join(dest, f"*.{kind}.{ext}")):
                if kind != "iterations" or not os.path.exists(os.path.join(dest, "iterations.tsv")):
                    shutil.copy(f, os.path.join(dest, f"{kind}.{ext}"))
        if os.path.exists(os.path.join(dest, "iterations.tsv")):
            from . import timeline
            timeline.write(dest)
        jmh.finish(dest, spec.profile, spec.lib)
        if spec.kperf:
            metrics.hw_events(dest, spec.profile, jmh.jfrconv(jmh.async_lib(spec.lib)))  # for the index's summary
        set_running(spec, None)
        s = summary(json.load(open(os.path.join(dest, "result.json")))[0])
        log(f"  {s['ms']:.1f} ± {s['err']:.1f} {s['unit']}" + (f", {s['cyc'] / 1e9:.2f}G cycles/op" if s.get("cyc") else "")
            + (f", other load {load:.2f} cores" if spec.loadgate else ""))
    if skipped:
        log(f"{spec.name}: {len(skipped)} commit{'s' if len(skipped) > 1 else ''} did not build, {'their' if len(skipped) > 1 else 'its'} cells skipped: "
            + ", ".join(f"{v} ({why})" for v, why in skipped.items())
            + f"; build logs in {os.path.join(spec.build_out, branch.FAILED_LOGS)}; `perflab ab run <spec> --retry-unbuildable` tries again")
    if failed:
        sys.exit(f"{spec.name}: {len(failed)} cell{'s' if len(failed) > 1 else ''} failed (a resume runs them again):\n  " + "\n  ".join(failed))


FAILED = "failed.txt"  # in a branch campaign's cell whose run failed: why


def done(dest):
    """A cell has a result: an interrupted one can leave an empty or truncated result.json, and is run again."""
    try:
        with open(os.path.join(dest, "result.json")) as f:
            r = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(r, list) and len(r) > 0


def build_commit(spec, commit):
    """A branch commit's launch-mode build, in <campaign>/.build/<key>: checked out into the campaign's worktree and
    built there, unless a build with the same key (tree, variables, build command, harness) is already kept, or the
    commit's recorded one (branch.recorded_key). A profile campaign has its branch campaign's builds and worktree
    (`build_out`).
    None when the commit does not build (or builds something else than its tree, or a dirty one): it is recorded in
    <campaign>/unbuildable.json, with its build.log, and nothing of it is kept in .build."""
    tpl = branch.template()
    probe = branch.env_for(spec.branch, os.path.join(spec.build_out, branch.WORKTREE))
    if getattr(spec, "harness", None) is None:  # once a run: the project and JDK don't change under it
        spec.harness = branch.harness(probe)
    key, warning = branch.recorded_key(spec.build_out, commit, probe, tpl, spec.harness)
    if warning and not getattr(spec, "harness_warned", False):
        log(f"  warning: {warning}")
        spec.harness_warned = True
    dir = os.path.join(spec.build_out, launch.BUILD_DIR, key)

    def validate(built):  # the build says what it built (launch.json's "build"): the commit's tree, clean
        b = built.get("build") or {}
        if b.get("dirty"):
            return "the build was of a dirty checkout"
        if b.get("commit"):
            p = subprocess.run(["git", "-C", spec.branch["checkout"], "rev-parse", f"{b['commit']}^{{tree}}"],
                               capture_output=True, text=True)
            if p.returncode or p.stdout.strip() != commit["tree"]:
                return f"built {b['commit'][:10]}, whose tree is not {commit['short']}'s"
        return None
    reuse = launch.reusable(dir)
    if reuse and (problem := validate(launch.read(os.path.join(dir, launch.LAUNCH)))):
        log(f"  the snapshot in {dir} is not {commit['short']}'s ({problem}); building it again")
        shutil.rmtree(dir, ignore_errors=True)
        reuse = False
        key = branch.build_key(commit, probe, tpl, spec.harness)
        dir = os.path.join(spec.build_out, launch.BUILD_DIR, key)
    wt = None
    if not reuse:
        wt = branch.checkout(spec.build_out, spec.branch_info, commit, clean=not spec.branch.get("incremental"))
        log(f"build of {commit['short']} {commit['subject'][:60]}")
    try:
        built = launch.build(dir, branch.env_for(spec.branch, wt) if wt else probe,
                             label=f"{spec.name}: {commit['short']} {commit['subject'][:60]}", validate=validate)
    except launch.BuildFailed as e:
        branch.set_unbuildable(spec.build_out, commit["variant"], e.reason, e.log)
        shutil.rmtree(dir, ignore_errors=True)  # never a snapshot to reuse: a resume (with --retry-unbuildable) builds it again
        log(f"  {commit['short']} did not build: {e.reason} (see {os.path.join(spec.build_out, branch.FAILED_LOGS, commit['variant'] + '.log')})")
        return None
    branch.set_unbuildable(spec.build_out, commit["variant"])
    branch.record_key(spec.build_out, commit, key)
    return built


def summary(r):
    m, p = r.get("secondaryMetrics", {}), r["primaryMetric"]
    get = lambda k: m[k]["score"] if k in m else None
    return {"ms": p["score"], "err": p["scoreError"] if isinstance(p.get("scoreError"), (int, float)) else float("nan"),  # JMH writes "NaN" for too few iterations
            "unit": p.get("scoreUnit", ""), "alloc": get("gc.alloc.rate.norm"), "gc": get("gc.time"),
            "cyc": get("xctrace.CORE_ACTIVE_CYCLE"), "ipc": get("xctrace.IPC.bench"), "inst": get("xctrace.INST_ALL")}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


PAIRED_METRICS = [("score", "paired.{}", 1, "{:.4g}"), ("score excl. GC", "paired.gcFree.{}", 1, "{:.4g}"),
                  ("instructions/op", "xctrace.INST_ALL.{}", 1e9, "{:.3f}G"),
                  ("cycles/op", "xctrace.CORE_ACTIVE_CYCLE.{}", 1e9, "{:.3f}G"),
                  ("alloc/op", "paired.alloc.{}", 1e6, "{:.1f}MB")]


def paired_metric(cells, key):
    """A metric of a paired campaign over its forks, each fork a cell's secondaryMetrics: the mean of `key`, and its
    paired difference against the baseline per fork (`key.delta%`) with that fork's median difference, or None."""
    vals = [c[key]["score"] for c in cells if key in c]
    ds = [c[key + ".delta%"]["score"] for c in cells if key + ".delta%" in c]
    meds = [c[key + ".delta%.median"]["score"] for c in cells if key + ".delta%.median" in c]
    return mean(vals), ds, meds if len(meds) == len(ds) else None


def delta_summary(ds):
    """The mean of per-fork paired differences, with their spread over forks."""
    d = mean(ds)
    sd = (sum((x - d) ** 2 for x in ds) / (len(ds) - 1)) ** 0.5 if len(ds) > 1 else 0.0
    return f"{d:+.2f}% ± {sd:.2f}"


def describe(spec):
    """The spec's "description" and "variantDescriptions", as Markdown above the report's tables."""
    from .index import md_text
    if spec.description:
        print(md_text(spec.description) + "\n")
    for v, d in spec.variant_descriptions.items():
        print(f"- **{v}**: {md_text(d)}")
    if spec.variant_descriptions:
        print()


def report_paired(spec):
    """One row per corpus and variant: its mean per fork, and the paired difference against the first variant (the
    mean within each fork, then the mean and spread of those over forks); then each fork's own difference, with that
    fork's median, in a table of its own. No percent change where the values are about zero."""
    from . import ui
    names = list(spec.paired)
    print(f"### {spec.name} (paired within forks: {', '.join(names)})\n")
    describe(spec)
    print(f"| {spec.corpus_param} | variant | forks | " + " | ".join(f"{m} | Δ (paired)" for m, *_ in PAIRED_METRICS) + " |")
    print("|---|---|---|" + "---|---|" * len(PAIRED_METRICS))
    per_fork = []
    for corpus in spec.corpora:
        cells = []
        for r in range(1, spec.rounds + 1):
            f = os.path.join(spec.cell_dir(corpus, "paired", r), "result.json")
            try:
                cells.append(json.load(open(f))[0].get("secondaryMetrics", {}))
            except (OSError, ValueError, IndexError):
                pass  # not run, or still running: JMH writes result.json when the fork ends
        if not cells:
            continue
        for v in names:
            tds = []
            for label, key, scale, fmt in PAIRED_METRICS:
                kind = ui.kind_of(label)
                m, ds, meds = paired_metric(cells, key.format(v))
                b, _, _ = paired_metric(cells, key.format(names[0]))
                show = ui.size if kind == "alloc" else ui.si if kind == "count" else ui.num
                tds.append((show(m) or "0") if m is not None else "–")
                if ds and ui.delta_ok(b, kind) and ui.delta_ok(m, kind):
                    tds.append(delta_summary(ds))
                    per_fork.append((corpus, v, label, " · ".join(f"{x:+.2f}%" + (f" (median {md:+.2f}%)" if meds else "")
                                                                  for x, md in zip(ds, meds or ds))))
                else:
                    tds.append("–" if ds else "")
            print(f"| {corpus} | {v} | {len(cells)} | " + " | ".join(tds) + " |")
    if per_fork:
        print(f"\nΔ per fork against {names[0]}: each fork's mean difference over its iteration pairs (and their median).\n")
        print(f"| {spec.corpus_param} | variant | metric | per fork |\n|---|---|---|---|")
        for row in per_fork:
            print("| " + " | ".join(row) + " |")


def report(spec, per_op=False):
    """Per corpus, a row per metric (`metrics`) and a column per variant: the mean over rounds and Δ against the first
    variant, ± the spread over rounds; the score of each round and the GC time beneath."""
    if spec.paired:
        return report_paired(spec)
    print(f"### {spec.name}\n")
    describe(spec)
    if per_op:
        spec.per_unit = None
    jfrconv = jmh.jfrconv(jmh.async_lib(spec.lib)) if spec.kperf else None
    for corpus in spec.corpora:
        results = {}
        for variant in spec.variants:
            for r in range(1, spec.rounds + 1):
                cell = spec.cell_dir(corpus, variant, r)
                try:
                    res = json.load(open(os.path.join(cell, "result.json")))[0]
                except (OSError, ValueError, IndexError):
                    continue  # not run, or still running: JMH writes result.json when the fork ends
                results.setdefault(variant, []).append((res, metrics.hw_events(cell, spec.profile, jfrconv) if jfrconv else {}))
        if not results:
            continue
        cols, st = metrics.summarise({v: [metrics.of(res, spec.per_unit, hw) for res, hw in rs] for v, rs in results.items()}, spec.per_unit)
        names = list(results)
        missing = [v for v, rs in results.items() for res, _ in rs if spec.per_unit and metrics.units_per_op(res, spec.per_unit) is None]
        print(f"#### {spec.corpus_param} {corpus}\n")
        if spec.per_unit:
            per = {v: mean(metrics.units_per_op(res, spec.per_unit) for res, _ in rs) for v, rs in results.items()}
            print(f"Per {metrics.unit_name(spec.per_unit)}: per-op values divided by `{spec.per_unit}` per op ("
                  + ", ".join(f"{v} {per[v]:.4g}" for v in names if per[v]) + ")."
                  + (f" **No `{spec.per_unit}` counter in {', '.join(sorted(set(missing)))}.**" if missing else "") + "\n")
        print("| metric | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
        rounds = lambda v: " / ".join(f"{res['primaryMetric']['score']:.4g}" for res, _ in results[v])
        print(f"| {results[names[0]][0][0]['primaryMetric'].get('scoreUnit', 'score')} per round | " + " | ".join(rounds(v) for v in names) + " |")
        for k, label, kind, _ in cols:
            tds = []
            for v in names:
                if k not in st[v]:
                    tds.append("–"); continue
                m, sd, d, spread, ok = st[v][k]
                text = metrics.fmt(kind, m) + (f" ± {100 * sd / m:.1f}%" if sd is not None and m else "")
                if d is not None:
                    text += f" ({d:+.1f}%" + (f" ± {spread:.1f}" if spread is not None else "") + ")" if ok else " (–)"
                tds.append(text)
            print(f"| {label} | " + " | ".join(tds) + " |")
        gc = {v: mean(res["secondaryMetrics"].get("gc.time", {}).get("score") for res, _ in results[v]) for v in names}
        if any(gc.values()):
            print("| GC time | " + " | ".join(f"{gc[v] / 1e3:.1f} s" if gc[v] is not None else "–" for v in names) + " |")
        print()
    if "async" in spec.profile:
        print(graphs(spec))


EVENT_GRAPHS = ["bench", "reverse", "bench-classify", "reverse-classify", "threads", "classify"]


def graphs(spec):
    """For async runs: every flame graph of every cell (re)rendered by regraph, and <campaign>/index.html linking them."""
    from . import regraph
    events = [label for label, _ in regraph.events_of(spec.profile, bool(spec.kperf))]
    cells = []
    for corpus in spec.corpora:
        for variant, flags in spec.variants.items():
            for r in range(1, spec.rounds + 1):
                cell = spec.cell_dir(corpus, variant, r)
                if os.path.exists(os.path.join(cell, "result.json")):
                    cells.append((corpus, variant, flags, r, cell, cell))
    regraph.regraph([c[5] for c in cells], jmh.jfrconv(jmh.async_lib(spec.lib)))
    rows, unit = [], "score"
    for corpus, variant, flags, r, cell, prof in cells:
        jfr = (glob.glob(os.path.join(prof, "**", "*.jfr"), recursive=True) or [None])[0]
        if jfr is None:
            continue
        tds = []
        for label in events:
            links = [f'<a href="{os.path.relpath(regraph.graph_path(jfr, label, k), spec.out)}">{k}</a>'
                     for k in regraph.KINDS if os.path.exists(regraph.graph_path(jfr, label, k))]
            tds.append("<td>" + " · ".join(links) + "</td>")
        s = summary(json.load(open(os.path.join(cell, "result.json")))[0])
        unit = s["unit"] or unit
        rows.append(f"<tr><th>{corpus}</th><th title=\"{flags}\">{variant} #{r}</th><td>{s['ms']:.0f} ± {s['err']:.0f}</td>{''.join(tds)}</tr>")
    events = [e.removeprefix("hw-") for e in events]
    page = f"""<!doctype html><meta charset="utf-8"><title>{spec.name} flame graphs</title>
<style>:root{{--bg:#f6f7f9;--fg:#1d232b;--muted:#5d6875;--line:#dde2e8;--link:#2f6fb2}}
@media (prefers-color-scheme: dark){{:root{{--bg:#14181d;--fg:#e3e8ee;--muted:#94a0ad;--line:#2c333c;--link:#6ea8e6;color-scheme:dark}}}}
body{{background:var(--bg);color:var(--fg);font:13px/1.5 -apple-system,system-ui,sans-serif;margin:20px}} a{{color:var(--link)}}
table{{border-collapse:collapse}} td,th{{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}} .k{{color:var(--muted)}}</style>
<h1>{spec.name}</h1>
<p class="k">{spec.benchmark}, profile {spec.profile}, JVM arguments for every variant: {spec.jvm_args}.
Variants: {"; ".join(f"{v}: {f or '(none)'}" for v, f in spec.variants.items())}.<br>
bench: benchmark threads · reverse: by leaf · *-classify: benchmark threads, jfrconv --classify · threads: all threads · classify: all threads by category</p>
<table><tr><th>{spec.corpus_param}</th><th>variant</th><th>{unit}</th>{''.join(f'<th>{e}</th>' for e in events)}</tr>{''.join(rows)}</table>"""
    index = os.path.join(spec.out, "index.html")
    os.makedirs(spec.out, exist_ok=True)
    open(index, "w").write(page)
    return f"Flame graphs: {index}"


def main(argv):
    if len(argv) < 2 or argv[0] not in ("run", "report"):
        sys.exit(__doc__)
    spec = Spec(argv[1])
    if argv[0] == "run":
        run(spec, "--dry-run" in argv, retry_unbuildable="--retry-unbuildable" in argv)
    else:
        report(spec, "--per-op" in argv)
    return 0
