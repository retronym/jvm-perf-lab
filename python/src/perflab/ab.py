"""Campaigns: a benchmark under one profile, over corpora and variants, run round by round with the variants
interleaved, each run checked against the spec.

  perflab ab run    <spec.json> [--dry-run]   runs every missing cell; resumable
  perflab ab report <spec.json>               markdown summary; for async profiles, an index of flame graphs

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
    "historical": "<why>",                               # optional: kept for its results; `run` refuses it
    "description": "Does -Yx help? See [#123](<url>).",  # optional Markdown (a string, or a list of lines): the
    "variantDescriptions": {"U": "uncached, from **#123**"}  # campaign and each variant, in a panel atop its card
  }

Cells run round by round, corpus by corpus, variants interleaved within each, so drift hits every variant alike. Each
run is checked: fresh results, the JVM, every JVM argument of the spec (JMH's -jvmArgsAppend replaces the benchmark's
@Fork(jvmArgsAppend), so every variant is given `jvmArgs`), each variant's `-p` parameters, xctrace counters present,
and for kperf, that samples were not lost.
"""
import atexit, glob, json, os, re, shlex, shutil, subprocess, sys, time

from . import config, jmh, loadgate, specs

JMH_LOCK = os.path.join(os.environ.get("TMPDIR", "/tmp"), "jmh.lock")
MAX_ATTEMPTS = 10


def log(msg):
    print(f"[ab {time.strftime('%H:%M:%S')}] {msg}", flush=True)


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
        self.variants = {"paired": ""} if self.paired else s["variants"]
        self.variant_jmh_args = s.get("variantJmhArgs", {})
        if self.paired:
            spec = "|".join(f"{n}={o}" for n, o in self.paired.items())
            if "," in spec:
                sys.exit("paired: JMH splits parameter values at commas; options cannot contain one")
            # quoted: a variant's options may be several words, and this string is split as a command line
            self.variant_jmh_args = {"paired": "-p " + shlex.quote(f"{cfg.get('benchmark', 'variants')}={spec}")}
        self.loadgate = s.get("loadgate")
        self.gc_log = s.get("gcLog", False)
        self.historical = s.get("historical")
        self.description, self.variant_descriptions = s.get("description"), s.get("variantDescriptions") or {}
        self.out = os.path.join(cfg.campaigns, self.name)

    def cells(self):
        for r in range(1, self.rounds + 1):
            for corpus, iters in self.corpora.items():
                for variant, flags in self.variants.items():
                    yield r, corpus, iters, variant, flags

    def cell_dir(self, corpus, variant, r):
        return os.path.join(self.out, corpus, variant, str(r))

    def command(self, corpus, iters, variant, flags, dest):
        """Writes the cell's arguments file and returns the build command that runs it."""
        extra = []
        if self.gc_log:
            extra.append(f"-Xlog:gc:file={dest}/gc.log:time,uptime")
        # the fork appends its iterations to <dest>/iterations.tsv as they finish (PairedProfiler)
        extra.append(f"-Dperflab.cell={dest}")
        jvm_args = " ".join(x for x in [self.jvm_args, flags, *extra] if x)
        args = (["-jvm", self.jvm] if self.jvm else []) + ["-p", f"{self.corpus_param}={corpus}"]
        args += shlex.split(iters) + shlex.split(self.variant_jmh_args.get(variant, "")) + [self.benchmark]
        return jmh.prepare(dest, self.profile, args, self.kperf, self.lib, jvm_args)


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
        index.build(config.get().campaigns)
    except Exception as e:  # the index is a convenience; never let it stop a campaign
        log(f"  index not rebuilt: {e}")


def wait_until_quiet(spec):
    while jmh_lock_held():
        log("JMH lock held by another run; waiting")
        time.sleep(30)
    if spec.loadgate:
        g = spec.loadgate
        loadgate.wait(loadgate.server_pid(), g.get("maxCores", 1.5), g.get("quietSecs", 30))


def start_load_sampler(spec, path):
    """Competing load every 5 s while a cell runs, into `path`."""
    if os.path.exists(path):
        os.unlink(path)
    if not spec.loadgate:
        return None
    return subprocess.Popen([sys.executable, "-m", "perflab", "loadgate", "sample", str(loadgate.server_pid()), path])


def mean_load(path):
    """Mean competing load in cores over a cell's samples (0 without samples)."""
    try:
        xs = [float(l.split("\t")[1]) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return 0.0
    return sum(xs) / len(xs) if xs else 0.0


def check(spec, dest, started, flags, variant):
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


def run(spec, dry):
    if spec.historical:
        sys.exit(f"{spec.name} is historical, kept for its results; not running it: {spec.historical}")
    cells = list(spec.cells())
    # the campaign keeps its spec: the index orders variants by it, and a report can be rerun from the results alone
    os.makedirs(spec.out, exist_ok=True)
    if os.path.abspath(spec.path) != os.path.abspath(os.path.join(spec.out, "spec.json")):
        shutil.copy(spec.path, os.path.join(spec.out, "spec.json"))
    # the spec version cells are tagged with; `perflab trees` records the user's spec once and passes its id down
    version = os.environ.get(specs.ENV) or specs.record(spec.out, spec.path)
    todo = [c for c in cells if not os.path.exists(os.path.join(spec.cell_dir(c[1], c[3], c[0]), "result.json"))]
    log(f"{spec.name}: {len(cells)} cells, {len(todo)} to run")
    if not dry:
        # the index first: it lists the campaign's cells before any has run, and updates itself as they finish
        from . import serve
        try:
            log(f"index (updates as cells finish): {serve.ensure()}")
        except Exception as e:  # the index is a convenience; never let it stop a campaign
            log(f"index not served: {e}")
    for r, corpus, iters, variant, flags in todo:
        dest = spec.cell_dir(corpus, variant, r)
        cmd = spec.command(corpus, iters, variant, flags, dest)
        if not dry:
            specs.tag(dest, version)
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
            break
        else:
            sys.exit(f"{dest}: no clean run in {MAX_ATTEMPTS} attempts")
        problem = f"build exited with {rc} (see {dest}/build.log)" if rc else check(spec, dest, started, flags, variant)
        if not problem and spec.kperf and spec.profile.startswith("async:cycles"):
            problem = check_samples(spec, dest)
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
        set_running(spec, None)
        s = summary(json.load(open(os.path.join(dest, "result.json")))[0])
        log(f"  {s['ms']:.1f} ± {s['err']:.1f} {s['unit']}" + (f", {s['cyc'] / 1e9:.2f}G cycles/op" if s.get("cyc") else "")
            + (f", other load {load:.2f} cores" if spec.loadgate else ""))


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


def report(spec):
    if spec.paired:
        return report_paired(spec)
    print(f"### {spec.name}\n")
    describe(spec)
    unit = next((summary(json.load(open(f))[0])["unit"] for f in glob.glob(os.path.join(spec.out, "*", "*", "*", "result.json"))), "score")
    print(f"| {spec.corpus_param} | variant | {unit} (per round) | mean | Δ | instructions/op (per round) | Δ | cycles/op | Δ | IPC | alloc/op | GC time |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for corpus in spec.corpora:
        base = None
        for variant in spec.variants:
            rs = []
            for r in range(1, spec.rounds + 1):
                f = os.path.join(spec.cell_dir(corpus, variant, r), "result.json")
                if os.path.exists(f):
                    rs.append(summary(json.load(open(f))[0]))
            if not rs:
                continue
            row = {k: mean(s[k] for s in rs) for k in ("ms", "cyc", "ipc", "alloc", "gc", "inst")}
            base = base or row
            pct = lambda k: f"{100 * (row[k] / base[k] - 1):+.1f}%" if row[k] and base[k] and row is not base else ""
            fmt = lambda x, f: f.format(x) if x is not None else "–"
            per = " / ".join(f"{s['ms']:.4g} ± {s['err']:.2g}" for s in rs)
            insts = " / ".join(f"{s['inst'] / 1e9:.3f}G" for s in rs if s.get("inst"))
            print(f"| {corpus} | {variant} | {per} | {row['ms']:.4g} | {pct('ms')} | {insts} | {pct('inst')} | {fmt(row['cyc'] and row['cyc'] / 1e9, '{:.2f}G')} | "
                  f"{pct('cyc')} | {fmt(row['ipc'], '{:.2f}')} | {fmt(row['alloc'] and row['alloc'] / 1e6, '{:.0f} MB')} | "
                  f"{fmt(row['gc'] and row['gc'] / 1e3, '{:.1f} s')} |")
    if "async" in spec.profile:
        print("\n" + graphs(spec))


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
        run(spec, "--dry-run" in argv)
    else:
        report(spec)
    return 0
