import json, os, signal, socket, subprocess, sys, tempfile, time, unittest, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import ab, analyze, auditfold, compare, config, defcosts, index, jmh, regraph, serve, specs, timeline, trees  # noqa: E402


class Project:
    """A temporary project with a perflab.toml, as the current configuration."""
    def __init__(self, toml):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, "perflab.toml"), "w") as f:
            f.write(toml)
        config._config = config.find(self.dir)


class ConfigTest(unittest.TestCase):
    def test_found_upward_with_defaults(self):
        p = Project('[build]\njmh = "java -jar b.jar {args}"\n[benchmark]\ncorpus = "size"\n')
        sub = os.path.join(p.dir, "a", "b")
        os.makedirs(sub)
        c = config.find(sub)
        self.assertEqual(c.root, p.dir)
        self.assertEqual(c.get("benchmark", "corpus"), "size")
        self.assertEqual(c.get("benchmark", "variants"), "variants")
        self.assertEqual(c.campaigns, os.path.join(p.dir, "out/perflab/ab"))


class RunTest(unittest.TestCase):
    def setUp(self):
        self.p = Project('[build]\njmh = "java -jar b.jar {args}"\n[agent]\njar = "agent.jar"\n')
        open(os.path.join(self.p.dir, "agent.jar"), "w").close()

    def args(self, out):
        return open(os.path.join(out, "jmh.args")).read().splitlines()

    def test_arguments_go_through_a_file(self):
        out = os.path.join(self.p.dir, "run")
        cmd = jmh.prepare(out, "xctrace:ipc", ["-p", "size=10", "B"], jvm_append="-Xmx1G")
        self.assertEqual(cmd, f"java -jar b.jar @{out}/jmh.args")
        a = self.args(out)
        self.assertIn(f"io.github.retronym.perflab.xctrace.XctraceProfiler:template=ipc;dir={out}", a)
        self.assertEqual(a[a.index("-jvmArgsAppend") + 1], "-Xmx1G")
        self.assertEqual(a[-3:], ["-p", "size=10", "B"])

    def test_async_events_and_kperf(self):
        out = os.path.join(self.p.dir, "run")
        jmh.prepare(out, "async:cycles+cache-misses@10000", ["B"], kperf="/tmp/k.sock", lib="/x/lib.dylib")
        a = self.args(out)
        prof = a[a.index("-prof") + 1]
        self.assertIn("event=cycles+cache-misses@10000", prof)
        self.assertIn("rawCommand=kperf=/tmp/k.sock", prof)
        self.assertIn("-XX:+PreserveFramePointer", a[a.index("-jvmArgsPrepend") + 1])
        self.assertEqual(regraph.events_of(out), [("hw-cycles", ["--hw", "cycles"]), ("hw-cache-misses", ["--hw", "cache-misses"])])
        self.assertEqual([l for l, _ in regraph.events_of("async:cpu,alloc")], ["cpu", "alloc"])

    def test_audit_puts_the_agent_on_the_fork(self):
        out = os.path.join(self.p.dir, "run")
        jmh.prepare(out, "audit:x.audit", ["B"])
        a = self.args(out)
        self.assertTrue(a[a.index("-jvmArgsPrepend") + 1].startswith(f"-javaagent:{self.p.dir}/agent.jar=spec="))

    def test_stale_outputs_are_cleared(self):
        out = os.path.join(self.p.dir, "run")
        os.makedirs(out)
        for f in ("audit-1.json", "result.json", "notes.txt"):
            open(os.path.join(out, f), "w").close()
        jmh.prepare(out, "none", ["B"])
        self.assertEqual(sorted(os.listdir(out)), ["jmh.args", "notes.txt", "profile.txt"])


class AnalyzeTest(unittest.TestCase):
    def test_phases_named_parts_and_fallbacks(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "phases.toml")
        with open(f, "w") as fh:
            fh.write('[[phase]]\nlabel = "typer"\npattern = "Typer\\\\."\n'
                     '[[phase]]\nlabel = "mega"\npattern = "MegaPhase\\\\."\nsub = "transform/([A-Za-z]+)\\\\."\nsubExclude = ["MegaPhase"]\n'
                     '[[phase]]\nlabel = "other"\npattern = "Phase\\\\.runOn"\nfallback = true\n')
        p = analyze.Phases(f)
        self.assertEqual(p.of(["Run", "Phase.runOn", "Typer.typed"]), "typer")
        self.assertEqual(p.of(["Phase.runOn", "transform/MegaPhase.go", "transform/Erasure.x"]), "mega:Erasure")
        self.assertEqual(p.of(["Phase.runOn", "x"]), "other")
        self.assertEqual(p.of(["main"]), "outside phases")


class AuditFoldTest(unittest.TestCase):
    def test_merges_and_folds(self):
        d = tempfile.mkdtemp()
        reports = []
        for i, n in enumerate((3, 5)):
            r = {"counters": {"fill.copier": n, "fill.other": 1}, "probes": {"filler": {"kind": "sites", "hits": n, "sample": 1, "sites": {
                f"a.B.m:{10 + i} <- c.D.n:3  [from x.Y.z:1 <- p.Q.r:2, Ident]": n}}}}
            reports.append(os.path.join(d, f"audit-{i}.json"))
            json.dump(r, open(reports[-1], "w"))
        import io
        out = io.StringIO()
        auditfold.main(["--by", "method", *reports], out=out)
        text = out.getvalue()
        self.assertIn("| 3 | 5 | 80.0% | `fill.copier` |", text)
        self.assertIn("`a.B.m <- c.D.n  [from x.Y.z <- p.Q.r, Ident]`", text)
        self.assertIn("1 distinct by method", text)


class TimelineTest(unittest.TestCase):
    def test_page_embeds_the_cell(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "iterations.tsv"), "w") as f:
            f.write("index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\n0\twarmup\ta\t1000\t2000\t1.5\t10\t3\n")
        page = open(timeline.write(d)).read()
        self.assertIn("BenchTimeline.parse", page)
        self.assertIn("0\\twarmup\\ta", page)


class DefCostsTest(unittest.TestCase):
    HEAD = "kind\tphase\tsymbol\tfile\tline\tchars\tcalls\tself_us\ttotal_us\tmax_self_us\tself_alloc\n"

    def table(self, rows, head=HEAD):
        fd, path = tempfile.mkstemp(suffix=".tsv")
        self.addCleanup(os.unlink, path)
        with os.fdopen(fd, "w") as f:
            f.write(head + "".join("\t".join(map(str, r)) + "\n" for r in rows))
        return defcosts.load(path)

    def test_histogram_buckets_are_powers_of_two(self):
        self.assertEqual(defcosts.histogram([1, 3, 4, 1000]), [(b, {0: 1, 1: 1, 2: 1, 9: 1}.get(b, 0)) for b in range(10)])
        self.assertEqual(defcosts.histogram([0]), [(0, 1)])
        self.assertEqual(defcosts.histogram([]), [])

    def test_cost_of_a_definition_sums_its_kinds_and_outliers_are_by_size(self):
        rows = [("def", "", f"C.m{i}", "C.scala", i, 100, 1, 100 + i, 100 + i, 100 + i, 0) for i in range(20)]
        # small, but its inferred type took long to complete
        rows += [("def", "", "C.slow", "C.scala", 99, 20, 1, 50, 50, 50, 0), ("complete", "", "C.slow", "C.scala", 99, 0, 1, 50000, 50000, 50000, 0)]
        # phases and units contain definitions; they are not definitions
        rows += [("phase", "typer", "typer", "", "", 0, 1, 90000, 90000, 90000, 0), ("unit", "typer", "C.scala", "C.scala", "", 0, 1, 5000, 5000, 5000, 0)]
        syms = defcosts.by_symbol(self.table(rows))
        self.assertEqual(syms["C.slow"]["self_us"], 50050)
        self.assertNotIn("typer", syms)
        self.assertNotIn("C.scala", syms)
        self.assertEqual([s for _, s, _ in defcosts.size_outliers(syms)], ["C.slow"])

    def test_identical_sizes_and_times_have_no_outliers(self):
        # the median absolute deviation is 0: slightly slower definitions must not all score as outliers
        rows = [("def", "", f"C.m{i}", "", "", 100, 1, 2000, 2000, 2000, 0) for i in range(20)]
        rows += [("def", "", "C.a", "", "", 100, 1, 2100, 2100, 2100, 0)]
        self.assertEqual(defcosts.size_outliers(defcosts.by_symbol(self.table(rows))), [])

    def test_comparison_lists_the_largest_changes(self):
        base = self.table([("def", "", "A.x", "", "", 10, 1, 1000, 1000, 1000, 0), ("def", "", "A.y", "", "", 10, 1, 1000, 1000, 1000, 0),
                           ("def", "", "A.gone", "", "", 10, 1, 3000, 3000, 3000, 0)])
        this = self.table([("def", "", "A.x", "", "", 10, 1, 5000, 5000, 5000, 0), ("def", "", "A.y", "", "", 10, 1, 900, 900, 900, 0)])
        text, page = defcosts.report(this, 5, base)
        changes = text.split("changed against the base")[1].splitlines()[1:]
        self.assertIn("A.x", changes[0])
        self.assertIn("+4.0 ms", changes[0])
        self.assertIn("A.gone", changes[1])
        self.assertIn("-3.0 ms", changes[1])

    def test_old_tables_and_short_rows_load(self):
        old = "kind\tsymbol\tfile\tline\tchars\tcalls\tself_us\ttotal_us\tmax_self_us\tself_alloc\n"
        rows = self.table([("def", "A.x", "A.scala", 1, 10, 1, 5, 5, 5, 0), ("def", "A.y")], head=old)
        self.assertEqual([(r["phase"], r["file"], r["self_us"]) for r in rows], [("", "A.scala", 5), ("", "", 0)])

    def test_names_are_escaped_in_the_page(self):
        _, page = defcosts.report(self.table([("def", "", "Apply.<*>", "", "", 10, 1, 1000, 1000, 1000, 0)]), 5)
        self.assertIn("Apply.&lt;*&gt;", page)
        self.assertNotIn("Apply.<*>", page)


class IndexTest(unittest.TestCase):
    def test_empty_result_json_is_a_running_cell(self):
        p = Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        cell = os.path.join(camp, "c", "corpus", "v", "1")
        os.makedirs(cell)
        open(os.path.join(cell, "result.json"), "w").close()
        json.dump({"name": "c", "rounds": 1, "corpora": ["corpus"], "variants": {"v": ""}}, open(os.path.join(camp, "c", "spec.json"), "w"))
        index.build(camp)
        page = open(os.path.join(camp, "index.html")).read()
        self.assertIn("<i>running</i>", page)
        self.assertIn("0 of 1 cells", page)

    def test_paired_campaign_shows_each_variant_and_its_paired_difference(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        s = lambda x: {"score": x}
        for r, (d, a) in enumerate([(-2.0, 87e6), (-3.0, 86e6)], 1):
            cell = os.path.join(camp, "c", "k", "paired", str(r))
            os.makedirs(cell)
            m = {"paired.base": s(100.0), "paired.fast": s(98.0), "paired.fast.delta%": s(d),
                 "paired.alloc.base": s(89e6), "paired.alloc.fast": s(a), "paired.alloc.fast.delta%": s(100 * (a / 89e6 - 1)),
                 "gc.alloc.rate.norm": s(1e6)}
            json.dump([{"primaryMetric": {"score": 99.0, "scoreError": 1.0}, "jvmArgs": [], "secondaryMetrics": m}],
                      open(os.path.join(cell, "result.json"), "w"))
        json.dump({"name": "c", "rounds": 2, "corpora": {"k": ""}, "paired": {"base": "-Yx", "fast": ""}},
                  open(os.path.join(camp, "c", "spec.json"), "w"))
        page = open(index.build(camp)).read()
        self.assertIn("<td>fast</td><td>2</td><td>98</td><td>-2.50% ± 0.71</td>", page)
        self.assertIn("<td>86.5MB</td><td>-2.81% ± 0.79</td>", page)
        self.assertIn("base 89.0MB · fast 87.0MB", page)
        self.assertNotIn("1.0MB", page)  # -prof gc mixes the variants


class CompareTest(unittest.TestCase):
    def test_a_widget_per_event_with_both_sides_and_both_diffs(self):
        d = tempfile.mkdtemp()
        for name in ("a-cpu.html", "diff-cpu.html", "diff-cpu-inverse.html", "b-cpu.html", "diff-alloc.html"):
            open(os.path.join(d, name), "w").close()
        page = open(compare.write(d, "base/1", "new/1")).read()
        self.assertEqual(page.count('class="w"'), 2)
        self.assertIn('data-view="inverse" title="diff-cpu-inverse.html">DIFF⁻¹</button>', page)
        self.assertIn('<iframe src="diff-cpu.html" data-view="diff">', page)
        self.assertIn('<iframe src="b-cpu.html" data-view="b" class=hidden>', page)
        self.assertNotIn("a-alloc.html", page)
        self.assertIn('<button data-link="event" class="on"', page)  # the graphs' controls are linked within an event
        self.assertIn("flameState", page)


class PairedSpecTest(unittest.TestCase):
    def test_a_variant_of_several_options_stays_one_parameter(self):
        p = Project('[build]\njmh = "x {args}"\n[benchmark]\ndefault = "B"\n')
        path = os.path.join(p.dir, "s.json")
        json.dump({"name": "c", "corpora": {"k": "-wi 1"}, "paired": {"base": "-Ya -Yb", "new": ""}}, open(path, "w"))
        spec = ab.Spec(path)
        dest = os.path.join(p.dir, "cell")
        spec.command("k", "-wi 1", "paired", "", dest)
        args = open(os.path.join(dest, "jmh.args")).read().split("\n")
        self.assertIn("variants=base=-Ya -Yb|new=", args)


class RunIndexTest(unittest.TestCase):
    def run_dir(self, name, args, result=None, state=None):
        out = os.path.join(config.get().runs, name)
        jmh.prepare(out, "none", args, jvm_append="-Xmx1G -XX:+UseG1GC -Dperflab.cell=x")
        if result is not None:
            json.dump(result, open(os.path.join(out, "result.json"), "w"))
        if state:
            json.dump(state, open(os.path.join(out, "run.json"), "w"))
        return out

    def test_args_of_a_run(self):
        Project('[build]\njmh = "x"\n')
        out = self.run_dir("r", ["-jvm", "/jdk/bin/java", "-p", "corpus=re2s", "-p", "g=0,4", "-wi", "16", "-l", "CompileBenchmark"])
        benches, params, opts, jvm, jvm_args = index.run_args(out)
        self.assertEqual(benches, ["CompileBenchmark"])
        self.assertEqual(params, {"corpus": "re2s", "g": "0,4"})
        self.assertEqual(opts, [("-wi", "16")])
        self.assertEqual(jvm, "/jdk/bin/java")
        self.assertIn("-XX:+UseG1GC", jvm_args)

    def test_status_of_a_run(self):
        Project('[build]\njmh = "x"\n')
        ok = [{"benchmark": "a.B.m", "params": {}, "jvmArgs": [], "primaryMetric": {"score": 1.0, "scoreError": 0.1, "scoreUnit": "ms/op"}}]
        dead = 2 ** 22 + 12345  # beyond macOS's and Linux's default pid_max
        cases = {"running": dict(state={"status": "running", "pid": os.getpid()}),
                 "interrupted": dict(state={"status": "running", "pid": dead}),
                 "failed": dict(state={"status": "failed", "rc": 3}),
                 "finished": dict(result=ok, state={"status": "finished", "rc": 0})}
        for want, kw in cases.items():
            self.assertEqual(index.run_status(self.run_dir(want, ["B"], **kw))[0], want)
        legacy = self.run_dir("legacy", ["B"], result=[])
        self.assertEqual(index.run_status(legacy)[0], "running")  # no run.json: running while its files are fresh
        old = time.time() - 2 * index.STALE_SECS
        for f in os.listdir(legacy):
            os.utime(os.path.join(legacy, f), (old, old))
        self.assertEqual(index.run_status(legacy)[0], "failed")

    def test_index_lists_runs_with_scores_and_links(self):
        Project('[build]\njmh = "x"\n[index]\nflags = "^-XX"\n')
        res = [{"benchmark": "a.B.compile", "params": {"corpus": "re2s", "g": g}, "jvmArgs": [],
                "primaryMetric": {"score": 150.0 + int(g), "scoreError": 3.2, "scoreUnit": "ms/op"}} for g in ("0", "4")]
        out = self.run_dir("multi-global", ["-jvm", "/jdk/bin/java", "-p", "corpus=re2s", "B"], result=res,
                           state={"status": "finished", "rc": 0})
        open(os.path.join(out, "jmh.log"), "w").close()
        open(os.path.join(out, "iterations.tsv"), "w").write("index\tkind\n")
        page = open(index.build(config.get().campaigns)).read()
        self.assertIn("run multi-global", page)
        self.assertIn('class="status finished"', page)
        self.assertIn("<code>-p corpus=re2s</code>", page)
        self.assertIn("<code>-XX:+UseG1GC</code>", page)
        self.assertIn("<code>g=4</code></td><td>154 ± 3.2 ms/op", page)
        self.assertIn('<a href="../runs/multi-global/jmh.log">jmh.log</a>', page)
        self.assertIn('<option value="../runs/multi-global/">run · multi-global</option>', page)


class ServeTest(unittest.TestCase):
    def test_one_server_for_campaigns_and_runs(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        Project(f'[build]\njmh = "x"\n[paths]\nruns = "out/lab/runs"\ncampaigns = "out/lab/ab"\n[index]\nport = {port}\n')
        camp = config.get().campaigns
        os.makedirs(camp)
        # an older perflab's server, for the campaigns alone
        old = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", camp],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            json.dump({"pid": old.pid, "port": port}, open(os.path.join(camp, serve.STATE), "w"))
            for _ in range(50):
                if serve._listening(port):
                    break
                time.sleep(0.1)
            url = serve.ensure()
            self.assertEqual(url, f"http://127.0.0.1:{port}/ab/index.html")
            self.assertEqual(old.wait(5), -signal.SIGTERM)
            self.assertEqual(serve.ensure(), url)
            st = json.load(open(os.path.join(camp, serve.STATE)))
            self.assertEqual(st["root"], os.path.dirname(camp))
            self.assertIn(b"Campaigns and runs", urllib.request.urlopen(url).read())
        finally:
            old.kill()
            serve.stop()


class SpecHistoryTest(unittest.TestCase):
    def spec(self, d, name, **kw):
        path = os.path.join(d, name)
        json.dump({"name": "c", "rounds": 3, "corpora": {"k": "-wi 6 -i 6"}, "variants": {"a": "", "b": ""}, **kw}, open(path, "w"))
        return path

    def test_record_reuses_identical_and_snapshots_changes(self):
        d = tempfile.mkdtemp()
        camp = os.path.join(d, "c")
        v1 = specs.record(camp, self.spec(d, "s1.json"))
        self.assertEqual(specs.record(camp, self.spec(d, "s2.json")), v1)
        v2 = specs.record(camp, self.spec(d, "s3.json", rounds=4, corpora={"k": "-wi 2 -i 4"}))
        self.assertNotEqual(v1, v2)
        hist = specs.history(camp)
        self.assertEqual([h[0] for h in hist], [v1, v2])
        self.assertEqual(hist[1][2], ["corpora.k: '-wi 6 -i 6' → '-wi 2 -i 4'", "rounds: 3 → 4"])

    def test_index_lists_versions_and_flags_mixed_cells(self):
        Project('[build]\njmh = "x"\n')
        camp = os.path.join(config.get().campaigns, "c")
        d = tempfile.mkdtemp()
        v1 = specs.record(camp, self.spec(d, "s1.json"))
        v2 = specs.record(camp, self.spec(d, "s2.json", rounds=4))
        for variant, r, v in (("a", 1, v1), ("b", 1, v1), ("a", 2, v2)):
            cell = os.path.join(camp, "k", variant, str(r))
            os.makedirs(cell)
            json.dump([{"primaryMetric": {"score": 1.0, "scoreError": 0.1}, "jvmArgs": []}], open(os.path.join(cell, "result.json"), "w"))
            specs.tag(cell, v)
        json.dump(json.load(open(os.path.join(camp, "specs", v2 + ".json"))), open(os.path.join(camp, "spec.json"), "w"))
        page = open(index.build(config.get().campaigns)).read()
        self.assertIn("Spec versions", page)
        self.assertIn("rounds: 3 → 4", page)
        self.assertIn("2 cells", page)
        self.assertIn("mixed spec versions", page)
        self.assertIn(f"spec {v1}", page)


class TreesTest(unittest.TestCase):
    def test_gather_merges_without_removing(self):
        tmp = tempfile.mkdtemp()
        tree = Project('[build]\njmh = "x"\n').dir
        src = os.path.join(config.find(tree).campaigns, "c", "k", "v", "1")
        os.makedirs(src)
        open(os.path.join(src, "result.json"), "w").write("[]")
        out = os.path.join(tmp, "c")
        keep = os.path.join(out, "k", "v", "0")
        os.makedirs(keep)
        trees.gather({"name": "c"}, {"v": tree}, out)
        self.assertTrue(os.path.exists(os.path.join(out, "k", "v", "1", "result.json")))
        self.assertTrue(os.path.isdir(keep))


if __name__ == "__main__":
    unittest.main()
