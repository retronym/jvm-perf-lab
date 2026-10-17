import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import analyze, auditfold, config, defcosts, index, jmh, regraph, timeline, trees  # noqa: E402


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
