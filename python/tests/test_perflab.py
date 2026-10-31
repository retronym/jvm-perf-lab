import collections, json, os, re, shlex, shutil, signal, socket, subprocess, sys, tempfile, time, unittest, urllib.request

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)
# the lab's jfrconv (retronym/async-profiler's integration branch: `mise run tools:async-profiler`)
LAB_JFRCONV = os.environ.get("JFRCONV") or os.path.join(SRC, "..", "..", "tools", "build", "async-profiler", "build", "bin", "jfrconv")
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`: commands run here, not on its queue
from perflab import ab, analyze, jfrevents, auditfold, compare, config, curate, defcosts, index, flamegraph, inlinetree, jmh, kinds, jvmevents, kperf, launch, loadgate, metrics, profdiff, regraph, serve, specs, stacks, timeline, transcript, trees  # noqa: E402


def _ensure_then_stop(root=None, port=None, _ensure=serve.ensure):
    """serve.ensure, with the server it starts for a test's temporary project stopped when the tests end."""
    url = _ensure(root, port)
    import atexit
    atexit.register(serve.stop, os.path.abspath(root or config.get().campaigns))
    return url


serve.ensure = _ensure_then_stop


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


class RegraphSpansTest(unittest.TestCase):
    def test_off_by_default(self):
        Project("")
        self.assertEqual(regraph.span_args(), [])

    def test_span_config_implies_spans(self):
        p = Project('[async]\nspan_config = "spans.json"\n')
        self.assertEqual(regraph.span_args(), ["--spans", "--span-config", os.path.join(p.dir, "spans.json")])

    def test_spans_without_config(self):
        Project("[async]\nspans = true\n")
        self.assertEqual(regraph.span_args(), ["--spans"])


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
        self.assertIn("event=cycles@2000000+cache-misses@10000", prof)  # perflab's default period where none is given
        self.assertIn("rawCommand=kperf=/tmp/k.sock", prof)
        self.assertIn("-XX:+PreserveFramePointer", a[a.index("-jvmArgsPrepend") + 1])
        self.assertEqual(regraph.events_of(out), [("hw-cycles", ["--hw", "cycles"]), ("hw-cache-misses", ["--hw", "cache-misses"])])
        self.assertEqual([l for l, _ in regraph.events_of("async:cpu,alloc")], ["cpu", "alloc"])

    def test_a_single_kperf_event_is_a_hardware_event(self):
        out = os.path.join(self.p.dir, "run")
        jmh.prepare(out, "async:cycles@10000000", ["B"], kperf="/tmp/k.sock", lib="/x/lib.dylib")
        self.assertEqual(regraph.events_of(out), [("hw-cycles", ["--hw", "cycles"])])
        self.assertEqual(regraph.events_of("async:cycles@10000000", kperf=True), [("hw-cycles", ["--hw", "cycles"])])
        jmh.prepare(out, "async:cpu", ["B"], lib="/x/lib.dylib")
        self.assertEqual(regraph.events_of(out), [("cpu", ["--cpu"])])
        jmh.prepare(out, "async:cache-misses", ["B"], kperf="/tmp/k.sock", lib="/x/lib.dylib")
        self.assertIn("event=cache-misses;interval=50000", self.args(out)[self.args(out).index("-prof") + 1])

    def test_async_records_the_jdk_events_by_jfrsync(self):
        out = os.path.join(self.p.dir, "run")
        jmh.prepare(out, "async:cpu", ["B"], lib="/x/lib.dylib")
        a = self.args(out)
        self.assertIn(f",jfrsync={jmh.PERFLAB_JFC};", a[a.index("-prof") + 1])
        self.assertTrue(os.path.exists(jmh.PERFLAB_JFC))
        p = Project('[build]\njmh = "java -jar b.jar {args}"\n[async]\njfrsync = false\n')
        jmh.prepare(os.path.join(p.dir, "run"), "async:cpu", ["B"], lib="/x/lib.dylib")
        self.assertNotIn("jfrsync", open(os.path.join(p.dir, "run", "jmh.args")).read())

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


class JvmEventsTest(unittest.TestCase):
    def test_rows_of_jfr_print_json(self):
        t = "2026-10-20T19:25:17.210995208+10:00"
        m = {"type": {"name": "java/io/BufferedReader"}, "name": "read"}
        comp = {"type": "jdk.Compilation", "values": {"startTime": t, "duration": "PT0.0025S", "compiler": "c2", "compileLevel": 4,
                                                       "method": m, "succeded": True, "isOsr": True, "codeSize": 4496}}
        k, s, e, what = jvmevents.row(comp)
        self.assertEqual((k, round(e - s, 3), what), ("c2", 2.5, "java.io.BufferedReader.read (tier 4, OSR, 4496 B)"))
        self.assertAlmostEqual(s, 1792488317210.995, places=2)
        op = {"type": "jdk.ExecuteVMOperation", "values": {"startTime": t, "duration": "PT1M0.5S", "operation": "G1CollectForAllocation", "safepoint": True}}
        self.assertEqual(jvmevents.row(op)[2] - s, 60500)
        self.assertIsNone(jvmevents.row({"type": "jdk.ExecuteVMOperation", "values": {**op["values"], "safepoint": False}}))
        deopt = {"type": "jdk.Deoptimization", "values": {"startTime": t, "method": m, "reason": "unstable_if", "action": "reinterpret",
                                                           "compiler": "c2", "lineNumber": 467}}
        self.assertEqual(jvmevents.row(deopt)[0::3], ["deopt", "java.io.BufferedReader.read: unstable_if, reinterpret (c2, line 467)"])


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
        self.assertIn('<span class="badge running">running</span>', page)
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
        better = '<span class="d better" title="lower, beyond the spread">'
        self.assertIn(f'<td>fast</td><td>2</td><td>98<br>{better}-2.50% <span class="pm">± 0.71</span></span></td>', page)
        self.assertIn(f'<td>86.5MB<br>{better}-2.81% <span class="pm">± 0.79</span></span></td>', page)
        self.assertIn('<span class="pv">base <b>89.0MB</b></span><span class="pv">fast <b>87.0MB</b></span>', page)
        self.assertIn("<td>fork 1</td>", page)
        self.assertNotIn("1.0MB", page)  # -prof gc mixes the variants

    def test_the_spec_describes_the_campaign_and_its_variants(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        cell = os.path.join(camp, "c", "k", "new", "1")
        os.makedirs(cell)
        open(os.path.join(cell, "result.json"), "w").close()
        json.dump({"name": "c", "rounds": 1, "corpora": {"k": ""}, "variants": {"base": "", "new": "-Dx=1"},
                   "trees": {"base": "../base"}, "variantJmhArgs": {"new": "-p o=-Yy"},
                   "description": ["Does `-Yy` help?", "", "- see [#1](https://e.org/1)"],
                   "variantDescriptions": {"new": "with **#1**"}},
                  open(os.path.join(camp, "c", "spec.json"), "w"))
        page = open(index.build(camp)).read()
        self.assertIn('<div class="about"><p>Does <code>-Yy</code> help?</p><ul><li>see <a href="https://e.org/1">#1</a></li></ul>', page)
        self.assertIn("<tr><th>base</th><td></td><td class=\"k\">checkout <code>../base</code></td></tr>", page)
        self.assertIn("<tr><th>new</th><td><p>with <b>#1</b></p></td><td class=\"k\">JVM flags <code>-Dx=1</code><br>JMH <code>-p o=-Yy</code></td></tr>", page)

    def test_no_panel_without_descriptions(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        os.makedirs(os.path.join(camp, "c", "k", "v", "1"))
        open(os.path.join(camp, "c", "k", "v", "1", "result.json"), "w").close()
        json.dump({"name": "c", "rounds": 1, "corpora": {"k": ""}, "variants": {"v": ""}}, open(os.path.join(camp, "c", "spec.json"), "w"))
        self.assertNotIn('class="about"', open(index.build(camp)).read())

    def test_markdown_inside_code_stays_literal(self):
        self.assertEqual(index.md("`-opt-inline:**,!java.**` and **b**"), "<p><code>-opt-inline:**,!java.**</code> and <b>b</b></p>")

    def test_the_corpus_column_is_named_by_its_parameter(self):
        Project('[build]\njmh = "x"\n[benchmark]\ncorpus = "size"\n')
        camp = config.get().campaigns
        for v in ("a", "b"):
            cell = os.path.join(camp, "c", "10000", v, "1")
            os.makedirs(cell)
            json.dump([{"primaryMetric": {"score": 5.0, "scoreError": 1.0, "scoreUnit": "us/op"}, "params": {"size": "10000"},
                        "jvmArgs": [], "secondaryMetrics": {}}], open(os.path.join(cell, "result.json"), "w"))
        json.dump({"name": "c", "rounds": 1, "corpora": {"10000": ""}, "variants": {"a": "", "b": ""}},
                  open(os.path.join(camp, "c", "spec.json"), "w"))
        page = open(index.build(camp)).read()
        heads = re.findall(r"<th[^>]*>([^<]*)", page)
        self.assertIn("size", heads)
        self.assertNotIn("corpus", heads)


class InlineTreeTest(unittest.TestCase):
    def test_a_stack_splits_into_compilation_units(self):
        u = inlinetree.units(["Main.run_[j];a/A.f_[i];a/B.g_[j];a/C.h_[i] 10", "Main.run_[j];a/A.f_[i] 5",
                              "Main.run_[j];Interp.x;a/C.h_[i] 2", "a/D.k_[1] 1"], inlinetree.shortener(["a"]))
        run, g = u["Main.run [C2]"], u["B.g [C2]"]
        self.assertEqual((run.incl, run.own, dict(run.calls)), (17, 7, {"B.g [C2]": 10}))
        self.assertEqual((run.kids["A.f"].incl, run.kids["A.f"].own), (15, 5))
        self.assertEqual((g.incl, g.own, g.kids["C.h"].own), (10, 10, 10))
        self.assertNotIn("C.h", run.kids)  # an interpreted frame ends the unit; what is inlined above it has no unit
        self.assertEqual(u["D.k [C1]"].own, 1)

    def test_recursion_counts_once_per_sample(self):
        u = inlinetree.units(["T.typed_[j];T.adapt_[i];T.typed_[j];T.adapt_[i];T.typed_[j] 4"])
        t = u["T.typed [C2]"]
        self.assertEqual((t.incl, t.own, dict(t.calls), t.kids["T.adapt"].incl), (4, 4, {"T.typed [C2]": 4}, 4))

    def rows(self):
        units = {"base": inlinetree.units(["R.run_[j];G.g_[i] 30", "R.run_[j] 10"]),
                 "new": inlinetree.units(["R.run_[j];G.g_[j] 20", "R.run_[j];G.g_[i] 5", "R.run_[j] 10"])}
        V, ops = ["base", "new"], {"base": 1, "new": 1}
        return V, inlinetree.build_rows(V, units, ops, inlinetree.top_units(V, "base", units, ops, 5), 0)

    def test_callees_are_marked_by_how_each_build_reaches_them(self):
        V, rows = self.rows()
        run = rows[0]
        g = next(r for r in rows if r.parent == run.id and r.name == "G.g")
        self.assertEqual(g.how, {"base": "inl", "new": "inl+call"})
        self.assertEqual(g.incl, {"base": 30, "new": 25})  # inlined and called together
        unit_g = next(r for r in rows if r.depth == 0 and r.name == "G.g [C2]")
        self.assertEqual((unit_g.how, unit_g.own), ({"base": "", "new": "C2"}, {"base": None, "new": 20}))
        cards = [t for t, _, _ in inlinetree.insights(rows, V, "base", {"base": 40, "new": 35}, "cycles", {})]
        self.assertIn("Inlining flipped", cards)
        self.assertIn("Compile boundaries moved", cards)

    def test_page(self):
        d = tempfile.mkdtemp()
        loaded, cells = {}, {}
        for v, stacks in (("base", "R.run_[j];G.g_[i] 3000000\n"), ("new<x>", "R.run_[j];G.g_[j] 2000000\n")):
            cells[v] = os.path.join(d, v)
            os.makedirs(cells[v])
            json.dump([{"benchmark": "p.B.m", "jvm": "/j/bin/java", "jvmArgs": ["-XX:MaxInlineSize=70"], "primaryMetric": {"score": 5.0, "scoreError": 0.1, "scoreUnit": "ms/op"}}],
                      open(os.path.join(cells[v], "result.json"), "w"))
            open(os.path.join(d, v + ".collapsed"), "w").write(stacks)
            loaded[v] = {"collapsed": os.path.join(d, v + ".collapsed"), "ops": 1, "total": 3e6}
        page = inlinetree.page(["base", "new<x>"], "base", loaded, cells, notes={"G.g": "see `x`"})
        self.assertIn("<b>-XX:MaxInlineSize=70</b>", page)
        self.assertIn('<span class="h inl">inl</span>', page)
        self.assertIn('<span class="h call">call</span>', page)
        self.assertIn("new&lt;x&gt;", page)
        self.assertNotIn("new<x>", page)
        self.assertIn('<div class="notetxt">see <code>x</code></div>', page)
        self.assertIn('<span class="z">—</span>', page)  # base does not reach G.g's own unit

    def test_the_index_links_a_campaigns_inline_trees(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        os.makedirs(os.path.join(camp, "c", "k", "v", "1"))
        open(os.path.join(camp, "c", "k", "v", "1", "result.json"), "w").close()
        json.dump({"name": "c", "rounds": 1, "corpora": {"k": ""}, "variants": {"v": ""}}, open(os.path.join(camp, "c", "spec.json"), "w"))
        open(os.path.join(camp, "c", "inlinetree-cycles.html"), "w").close()
        self.assertIn('<a class="btn" href="c/inlinetree-cycles.html" data-lb="inlinetree|cycles"', open(index.build(camp)).read())


class KperfTest(unittest.TestCase):
    # the helper's lines in a cell's jmh.log: the warmup's session, then the measurement's, one line garbled by the
    # fork's output interleaving with it
    LOG = """# Warmup Iteration   1: [INFO] kperf: cycles (CORE_ACTIVE_CYCLE) every 1000000 on PMC2
[INFO] kperf: cache-misses (L1D_CACHE_MISS_LD_NONSPEC) every 10000 on PMC5, precise PC
# Warmup Iteration  13: [INFO] kperf: cycles: 565820 samples, 0 with precise PC, 0 used as leaf
[INFO] kperf: cache-misses: 1713467 saIteration   1: mples, 1713294 with precise PC, 659568 used as leaf
Iteration  16: [INFO] kperf: cycles: 350472 samples, 0 with precise PC, 0 used as leaf
[INFO] kperf: cache-misses: 968341 samples, 968263 with precise PC, 236829 used as leaf
"""

    def cell(self, root, variant="base", log=LOG):
        d = os.path.join(root, "dotc", variant, "1")
        os.makedirs(d)
        open(os.path.join(d, "jmh.log"), "w").write(log)
        return d

    def test_default_periods(self):
        self.assertEqual(kperf.with_periods("cycles+cache-misses+PL2_CACHE_MISS_LD@10000"),
                         "cycles@2000000+cache-misses@50000+PL2_CACHE_MISS_LD@10000")
        self.assertEqual(kperf.default_period("instructions"), 5_000_000)
        self.assertEqual(kperf.default_period("LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS"), 1_000_000)  # counts cycles
        self.assertEqual(kperf.default_period("L1D_TLB_MISS"), 20_000)

    def test_too_many_samples_warn_with_a_period_that_would_do(self):
        d = tempfile.mkdtemp()
        cell = self.cell(d)
        self.assertEqual(kperf.check(cell), ["cache-misses: 968,341 samples per fork at period 10,000; @100000 would take about 100k"])
        self.assertEqual(json.load(open(os.path.join(cell, kperf.SAMPLES_NAME)))["cycles"], {"samples": 350472, "period": 1000000})
        self.assertEqual(kperf.suggest(2_400_000, 10_000), 200_000)
        self.assertEqual(kperf.check(self.cell(d, "tip", self.LOG.replace("968341", "90000"))), [])
        self.assertEqual(kperf.campaign_warnings(d), kperf.check(cell))  # the worst cell's

    def test_the_index_shows_the_warning(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        cell = self.cell(os.path.join(camp, "c"))
        json.dump(MetricsTest.cell(1, 20e9, 66e9, 16.4, 7.5), open(os.path.join(cell, "result.json"), "w"))
        kperf.check(cell)
        json.dump({"name": "c", "rounds": 1, "corpora": {"dotc": ""}, "variants": {"base": ""}, "benchmark": "B"},
                  open(os.path.join(camp, "c", "spec.json"), "w"))
        self.assertIn("⚠ more kperf samples than needed: cache-misses: 968,341 samples per fork", open(index.build(camp)).read())


class CollapsedTest(unittest.TestCase):
    """Collapsed stacks as jfrconv writes them, with the lines a recording cut short or a full disk leaves."""
    LINES = ["a;b;c 10\n", "\n", "a;b \n", "a;b;c\n", "a;d 5\n", "a;e 1x\n", "x;y;z 2"]

    def test_malformed_lines_are_skipped(self):
        self.assertEqual(list(profdiff.stacks(self.LINES)), [("a;b;c", 10), ("a;d", 5), ("x;y;z", 2)])
        self.assertIsNone(profdiff.parse(" 12"))

    def run_dir(self):
        """A run with a kperf recording, and a jfrconv that writes LINES (with a hidden class and a thread id) where it
        is told to."""
        d = tempfile.mkdtemp()
        open(os.path.join(d, "x.jfr"), "w").close()
        open(os.path.join(d, "profile.txt"), "w").write("async:cycles+cache-misses\n")
        open(os.path.join(d, "jmh.args"), "w").write("rawCommand=kperf=/tmp/k.sock\n")
        json.dump([{"measurementTime": "10 s", "primaryMetric": {"score": 5000.0, "rawData": [[5000.0, 5000.0]]}}],
                  open(os.path.join(d, "result.json"), "w"))
        conv = os.path.join(d, "jfrconv")
        lines = "".join(self.LINES).replace("a;d 5", "[main-jmh-worker-1 tid=37123];F$$Lambda.0x0000f80140b6b0;a;d 5")
        open(conv, "w").write("#!/bin/sh\nfor last; do :; done\nprintf '%s' " + shlex.quote(lines) + " > \"$last\"\n")
        os.chmod(conv, 0o755)
        return d, conv

    def test_load_streams_and_skips_malformed_lines(self):
        d, conv = self.run_dir()
        r = profdiff.load(d, "cache-misses", conv, d, "a")
        self.assertEqual((r["total"], r["skipped"], r["ops"]), (17, 3, 4))
        self.assertEqual(r["self"]["d"], 5)
        self.assertIn("[main-jmh-worker-1];F$$Lambda;a;d 5\n", open(r["collapsed"]).read())
        self.assertIsNone(profdiff.load(d, "cycles", conv, d, "b", keep=False)["collapsed"])
        self.assertFalse(os.path.exists(os.path.join(d, "b-cycles.collapsed")))

    def test_hw_events_leaves_no_collapsed_stacks(self):
        d, conv = self.run_dir()
        before = set(os.listdir(d)) | {metrics.EVENTS_NAME}
        self.assertEqual(metrics.hw_events(d, "async:cycles+cache-misses", conv), {"cycles": 17 / 4, "cache-misses": 17 / 4})
        self.assertEqual(set(os.listdir(d)), before)


PROMOTE = "+jdk.PromoteObjectInNewPLAB+jdk.PromoteObjectOutsidePLAB+jdk.TenuringDistribution"


class JfrsyncTest(unittest.TestCase):
    """A campaign's "jfrsync" instead of the lab's [async] jfrsync; `+event` added to the lab's .jfc."""

    def setUp(self):
        self.p = Project('[build]\njmh = "x {args}"\n')

    def raw(self, out):
        line = next(a for a in open(os.path.join(out, "jmh.args")).read().splitlines() if a.startswith("async:"))
        return dict(kv.split("=", 1) for kv in line.split("rawCommand=", 1)[1].split(";", 1)[0].split(","))

    def test_settings(self):
        self.assertEqual(jmh.jfrsync(), jmh.PERFLAB_JFC)  # the lab's default
        self.assertIsNone(jmh.jfrsync(False))
        self.assertEqual(jmh.jfrsync("my.jfc"), os.path.join(self.p.dir, "my.jfc"))
        self.assertEqual(jmh.jfrsync("profile"), "profile")
        self.assertEqual(jmh.added_events("+jdk.A, +jdk.B#threshold=0 ms"),
                         [("jdk.A", {"enabled": "true"}), ("jdk.B", {"enabled": "true", "threshold": "0 ms"})])

    def test_added_to_perflab_jfc(self):
        out = tempfile.mkdtemp()
        f = jmh.jfrsync(PROMOTE + "+jdk.GarbageCollection#enabled=false", out)
        self.assertEqual(f, os.path.join(out, "jfrsync.jfc"))
        import xml.etree.ElementTree as ET
        ev = {e.get("name"): {st.get("name"): st.text for st in e.iter("setting")} for e in ET.parse(f).getroot().iter("event")}
        base = {e.get("name") for e in ET.parse(jmh.PERFLAB_JFC).getroot().iter("event")}
        self.assertLessEqual(base, set(ev))  # perflab.jfc's events stay
        self.assertEqual(ev["jdk.PromoteObjectInNewPLAB"]["enabled"], "true")
        self.assertEqual(ev["jdk.GarbageCollection"]["enabled"], "false")  # an existing event's setting replaced
        t = os.path.getmtime(f)
        time.sleep(0.01)
        jmh.jfrsync(PROMOTE + "+jdk.GarbageCollection#enabled=false", out)
        self.assertEqual(os.path.getmtime(f), t)  # unchanged: not rewritten under a running campaign

    def test_a_campaign_overrides_the_lab(self):
        spec = os.path.join(self.p.dir, "s.json")
        json.dump({"name": "s", "benchmark": "B", "profile": "async:alloc", "jfrsync": PROMOTE, "corpora": {"c": ""},
                   "variants": {"a": ""}}, open(spec, "w"))
        sp = ab.Spec(spec)
        dest = sp.cell_dir("c", "a", 1)
        sp.command("c", "", "a", "", dest)
        self.assertEqual(self.raw(dest)["jfrsync"], os.path.join(sp.out, "jfrsync.jfc"))
        self.assertEqual(json.load(open(os.path.join(dest, jmh.JFRSYNC))), {"jfrsync": os.path.join(sp.out, "jfrsync.jfc")})
        json.dump({**json.load(open(spec)), "jfrsync": False}, open(spec, "w"))
        ab.Spec(spec).command("c", "", "a", "", dest)
        self.assertNotIn("jfrsync", self.raw(dest))
        json.dump({k: v for k, v in json.load(open(spec)).items() if k != "jfrsync"}, open(spec, "w"))
        ab.Spec(spec).command("c", "", "a", "", dest)
        self.assertEqual(self.raw(dest)["jfrsync"], jmh.PERFLAB_JFC)

    @unittest.skipUnless(shutil.which("java"), "no java")
    def test_a_jvm_records_the_merged_jfc_and_the_census_reads_it(self):
        """The merged .jfc is one JFR takes, and G1's promotion events land in the recording."""
        d = tempfile.mkdtemp()
        jfc = jmh.jfrsync(PROMOTE, d)
        src = os.path.join(d, "Promote.java")
        open(src, "w").write("public class Promote { public static void main(String[] a) {\n"
                             "  java.util.ArrayDeque<Object[]> keep = new java.util.ArrayDeque<>();\n"
                             "  for (int i = 0; i < 3_000_000; i++) { keep.add(new Object[8]); if (keep.size() > 200_000) keep.poll(); }\n"
                             "  System.out.println(keep.size()); } }\n")
        cell = os.path.join(d, "cell")
        os.makedirs(cell)
        jfr = os.path.join(cell, "rec.jfr")
        r = subprocess.run(["java", "-XX:+UseG1GC", "-Xmx256m", "-Xmn32m", f"-XX:StartFlightRecording:settings={jfc},filename={jfr}", src],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        counts = jfrevents.count(cell, ["jdk.PromoteObjectInNewPLAB", "jdk.TenuringDistribution", "jdk.GarbageCollection"])
        self.assertGreater(counts["jdk.PromoteObjectInNewPLAB"], 0)
        self.assertGreater(counts["jdk.GarbageCollection"], 0)  # perflab.jfc's own events too
        c = jfrevents.promotion(cell)
        self.assertIn("java.lang.Object[]", [k["class"] for k in c["classes"]])
        self.assertTrue(os.path.exists(os.path.join(cell, jfrevents.CENSUS)))
        self.assertEqual(jfrevents.promotion(cell), c)  # from the cache


class JitRecordingTest(unittest.TestCase):
    """A spec's "jitRecording": the JIT over a whole fork, and jfrevents' summary of it."""

    def test_a_spec_records_the_jit_over_each_fork(self):
        d = tempfile.mkdtemp()
        spec = os.path.join(d, "spec.json")
        json.dump({"name": "j", "benchmark": "B", "profile": "none", "corpora": {"c": ""}, "variants": {"a": ""}, "jitRecording": True},
                  open(spec, "w"))
        sp = ab.Spec(spec)
        dest = sp.cell_dir("c", "a", 1)
        sp.command("c", "", "a", "", dest)
        self.assertIn(jmh.jit_recording(dest), open(os.path.join(dest, "jmh.args")).read())

    @unittest.skipUnless(shutil.which("java"), "no java")
    def test_c2_inlining_decisions_from_a_recording(self):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "Hot.java")
        open(src, "w").write("public class Hot {\n"
                             "  static int small(int x) { return x * 31 + 7; }\n"
                             "  static int big(int x) { int s = x; for (int i = 0; i < 3; i++) { s ^= s << 13; s ^= s >>> 17; s ^= s << 5;"
                             " s += i * x; s = s * 17 + (s >>> 3); s ^= 0x5bd1e995; } return s; }\n"
                             "  static int loop(int n) { int s = 0; for (int i = 0; i < n; i++) s += small(i) + big(i); return s; }\n"
                             "  public static void main(String[] a) { long end = System.nanoTime() + 1_000_000_000L; int s = 0;\n"
                             "    while (System.nanoTime() < end) s += loop(10_000); System.out.println(s); } }\n")
        cell = os.path.join(d, "cell")
        os.makedirs(cell)
        r = subprocess.run(["java", "-XX:FreqInlineSize=30", jmh.jit_recording(cell), src], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        j = jfrevents.jit(cell)
        self.assertEqual((j["source"], j["forks"]), ("fork", 1))
        self.assertGreater(j["tiers"]["4"]["compilations"], 0)
        [loop] = [m for m in j["methods"] if m["method"] == "Hot.loop(I)I"]
        decisions = {x["callee"]: x for x in loop["c2"]["inlining"]}
        self.assertEqual(decisions["Hot.small(I)I"]["inlined"], 1)
        self.assertEqual(decisions["Hot.big(I)I"]["messages"], {"too big": 1})  # beyond FreqInlineSize
        self.assertEqual(jfrevents.jit(cell), j)  # from the cache


class KindsTest(unittest.TestCase):
    """Frame kinds: the flips table, the light curation, the toggle page's tree."""

    st = staticmethod(lambda *lines, ops=1: stacks.of_lines([[l.rsplit(" ", 1)[0], int(l.rsplit(" ", 1)[1])] for l in lines], ops, 1.0))

    def pair(self):
        a = self.st("main_[j];T.find_[j];S.denot_[i] 6", "main_[j];T.find_[j] 4", "main_[j];U.f_[j];S.denot_[i] 2", ops=2)
        b = self.st("main_[j];T.find_[j];S.denot_[j] 7", "main_[j];T.find_[j] 4", "main_[j];U.f_[j];S.denot_[j] 2", ops=2)
        return a, b

    def test_a_method_no_longer_inlined_tops_the_flips(self):
        t = kinds.flips(*self.pair())
        [r] = t["rows"]  # nothing else changed kind
        self.assertEqual(r["method"], "S.denot")
        self.assertEqual((r["a"]["inlined"], r["a"]["real"], r["b"]["inlined"], r["b"]["real"]), (4.0, 0.0, 0.0, 4.5))  # self
        self.assertEqual((r["a"]["inclusiveInlined"], r["b"]["inclusiveReal"]), (4.0, 4.5))
        self.assertEqual((r["selfToReal"], r["inclusiveMoved"], r["reshuffle"]), (4.5, 4.25, False))
        jit = {"methods": [{"c2": {"inlining": [{"caller": "T.find()V", "callee": "S.denot()V", "inlined": 0, "notInlined": 2, "messages": {"too big": 2}}]}}]}
        r = kinds.with_jit(t, {"methods": []}, jit)["rows"][0]
        self.assertEqual(r["jit"], {"a": None, "b": {"inlined": 0, "notInlined": 2, "messages": {"too big": 2}}})
        self.assertEqual(r["sitesFlipped"], 2)
        jit_a = {"methods": [{"c2": {"inlining": [{"caller": "T.find()V", "callee": "S.denot()V", "inlined": 2, "notInlined": 0, "messages": {"inline (hot)": 2}}]}}]}
        jit_b = {"methods": [{"c2": {"inlining": [{"caller": "T.find()V", "callee": "S.denot()V", "inlined": 0, "notInlined": 2, "messages": {"too big": 2}},
                                                  {"caller": "T.find()V", "callee": "S.cheap()V", "inlined": 0, "notInlined": 5, "messages": {"too big": 5}}]}}]}
        t = kinds.with_jit(kinds.flips(*self.pair()), jit_a, jit_b)
        self.assertNotIn("_all", t)
        # by call sites: a callee too cheap to show in the profile still ranks, with no profile figure
        self.assertEqual([(r["method"], r["sitesFlipped"], r["selfToReal"]) for r in t["bySites"]], [("S.cheap", 5, None), ("S.denot", 2, 4.5)])
        self.assertIn("## C2: callees no longer inlined", kinds.table_md("cpu", t, "base", "tip"))
        self.assertIn("too big 2", kinds.table_md("cpu", t, "base", "tip"))

    def test_light_keeps_kinds_and_one_sided_frames(self):
        self.assertEqual(curate.rules_for({}, "light")[1], "light")
        rules = curate.merge(curate.DEFAULTS, curate.LIGHT)  # not the lab's [diff] of whatever config is current
        c = curate.Curator(rules)
        a, b = self.pair()
        ba, _ = c.base(a)
        bb, _ = c.base(b)
        ca, cb = c.aligned(c.shaped(ba), c.shaped(bb))
        self.assertEqual(ca["main_[j];T.find_[j];S.denot_[i]"], 6)
        self.assertEqual(cb["main_[j];U.f_[j];S.denot_[j]"], 2)
        own, incl = c.tables(ba)
        self.assertEqual(own["S.denot"], 8)  # the tables are by method, whatever its kind
        self.assertIn("keep their compilation suffixes", curate.banner(rules))

    def test_the_toggle_tree_lays_out_both_builds_once(self):
        a, b = self.pair()
        ca = collections.Counter({";".join(a.frames[i] for i in s): n for s, n in a.stacks})
        cb = collections.Counter({";".join(b.frames[i] for i in s): n for s, n in b.stacks})
        for by_leaf in (False, True):
            t = kinds.tree(ca, cb, a.ops, b.ops, by_leaf)
            self.assertEqual((t["a"][0], t["b"][0]), (6.0, 6.5))
            for i in range(len(t["depth"])):
                self.assertGreaterEqual(t["slot"][i], max(t["a"][i], t["b"][i]))
        roots = [t["table"][t["names"][i]] for i in range(len(t["depth"])) if t["depth"][i] == 1]
        self.assertEqual(roots, ["S.denot_[i]", "S.denot_[j]", "T.find_[j]"])  # by leaf: a method's kinds side by side
        out = tempfile.mkdtemp()
        kinds.toggle_graphs(MINI_TEMPLATE, os.path.join(out, "a.html"), os.path.join(out, "b.html"), "cpu", "base", "tip", t, True)
        a, b = (open(os.path.join(out, n)).read() for n in ("a.html", "b.html"))
        calls = lambda page: re.findall(r"\nf\([0-9,]+\)", page)
        self.assertEqual(calls(a), calls(b))  # one layout: the same frames at the same places
        self.assertNotEqual(a, b)  # each drawn to its own build's weight (W)
        self.assertIn('" S.denot"', a)  # unpack()'s prefix char, then the name


# the shape of a jfrconv page: its viewer, the frames, its tail
MINI_TEMPLATE = """<!DOCTYPE html><html><head><title>t</title><style>canvas {width: 100%; height: 160px; display: block}</style></head>
<body><h1>t</h1><script>
const levels = Array(10);
function f(key, level, left, width) {}
function unpack(cpool) {}
const cpool = [
'all',
' x'
];
unpack(cpool);

f(3,0,0,10)
u(9,8)

render(levels[0][0]);
</script></body></html>"""


class PerOpGraphsTest(unittest.TestCase):
    """The diffs' flame graphs compare work: each side's counts per op, on one scale."""

    st = staticmethod(lambda *lines, ops=1: stacks.of_lines([[l.rsplit(" ", 1)[0], int(l.rsplit(" ", 1)[1])] for l in lines], ops, 1.0))

    def rendered(self, fn, *args):
        """{name: {stack: count}} of the collapsed files `fn` hands to curate.render, and the k it says."""
        seen = {}
        def fake(jfrconv, out, event, fa, fb, la, lb, by_leaf=False, note="", k=None):
            for name, f in (("a", fa), ("b", fb)):
                seen[name] = dict((l.rsplit(" ", 1)[0], int(l.rsplit(" ", 1)[1])) for l in open(f).read().splitlines())
            seen["k"] = k
        real = curate.render
        curate.render = fake
        try:
            fn(*args)
        finally:
            curate.render = real
        return seen

    def test_two_runs_of_different_lengths_compare_per_op(self):
        # a: 10 ops, 300 samples of main;f; b: 30 ops, 600: per op, b does less (20 vs 30)
        a, b = self.st("main;f 300", ops=10), self.st("main;f 600", ops=30)
        self.assertEqual(profdiff.per_op(10, 30), (3.0, 1.0, 30))
        out = tempfile.mkdtemp()
        seen = self.rendered(curate.raw_diff, out, "cpu", a, b, "a", "b", "jfrconv", 5)
        self.assertEqual((seen["a"], seen["b"], seen["k"]), ({"main;f": 900}, {"main;f": 600}, 30))  # per op × 30: 30 vs 20
        seen = self.rendered(curate.curated_diff, out, "cpu", a, b, "a", "b", "jfrconv", curate.merge(curate.DEFAULTS, curate.LIGHT))
        self.assertEqual((seen["a"], seen["b"]), ({"main;f": 900}, {"main;f": 600}))
        self.assertEqual(profdiff.per_op_title("cpu", 30), "cpu per op (counts for 30 ops)")

    def test_a_collapsed_file_is_rescaled_in_place(self):
        f = os.path.join(tempfile.mkdtemp(), "a.collapsed")
        open(f, "w").write("main;f 3\nmain;g 1\n")
        profdiff.rescale(f, 2.5)
        self.assertEqual(open(f).read(), "main;f 8\nmain;g 2\n")  # rounded, a sample never to 0


class CampaignCardTest(unittest.TestCase):
    """A campaign's summary and cells as one table (index.card_summary): a row per corpus and variant, its cells beneath,
    each value as mean, median and min, and the iterations for the page's hover panel and chart."""

    def rec(self, v, rnd, forks):
        flat = [x for f in forks for x in f]
        r = {"benchmark": "B", "mode": "ss", "primaryMetric": {"score": sum(flat) / len(flat), "scoreError": 1.0, "scoreUnit": "ms/op", "rawData": forks},
             "secondaryMetrics": {}, "jvmArgs": []}
        cell = os.path.join(tempfile.mkdtemp(), v, str(rnd))
        return {"c": "k", "v": v, "round": rnd, "state": "done", "cell": cell, "name": f"#{rnd}", "detail": "", "flags": "",
                "data": (v, r["primaryMetric"]["score"], None, None, None, None, {}, "ms/op", r, cell)}

    def test_one_table_three_statistics_and_the_iterations(self):
        recs = [self.rec("base", 1, [[10.0, 11.0, 12.0, 30.0]]), self.rec("tip", 1, [[9.0, 9.5, 10.0, 10.5]])]
        html = index.card_summary(recs, ["base", "tip"], [("k", v, r) for v in ("base", "tip") for r in (1, 2)])
        self.assertEqual(html.count('<tr class="sr"'), 2)
        self.assertEqual(html.count('<tr class="sub" data-of="0"'), 2)  # base's round 1, and round 2 pending
        self.assertIn('<span class="badge pending">pending</span>', html)
        self.assertIn('hidden><td></td><td>#1', html)  # the cells hidden until their row is expanded
        for stat in ("mean", "median", "min"):
            self.assertIn(f'class="st st-{stat}"', html)
        data = json.loads(re.search(r'<script type="application/json">(.*?)</script>', html).group(1))
        base, tip = data["rows"]
        self.assertEqual(base["m"]["median"][0][1], 11.5)  # pooled iterations: (11 + 12) / 2
        self.assertEqual(tip["m"]["min"][0][1], 9.0)
        self.assertAlmostEqual(tip["m"]["median"][0][3], 100 * (9.75 / 11.5 - 1))
        self.assertEqual(data["cells"][tip["cells"][0]]["raw"]["score"], [[9.0, 9.5, 10.0, 10.5]])

    def test_a_pooled_statistic_and_its_bootstrap_spread(self):
        base, tip = [[10.0, 11.0, 12.0]] * 3, [[9.0, 10.0, 11.0]] * 3
        x, d, spread, ok = metrics.pooled_delta(base, tip, "median")
        self.assertEqual((x, round(d, 2), ok), (10.0, -9.09, True))
        self.assertGreater(spread, 0)
        self.assertEqual(metrics.pooled_delta(base, tip, "median"), (x, d, spread, ok))  # seeded: the page doesn't flicker
        self.assertEqual(metrics.describe([3, 1, 2])["median"], 2)


class FlameGraphTest(unittest.TestCase):
    """perflab's own flame graphs are jfrconv's viewer with other frames (perflab.flamegraph), never a viewer of their own."""

    def test_a_page_keeps_the_viewer_and_replaces_the_frames(self):
        p = flamegraph.page(MINI_TEMPLATE, "a <b>", [("all", 0, 0, 100), ("A.f_[j]", 1, 0, 60), ("B.g_[i]", 2, 10, 50)], "/* overlay */")
        head, tail = flamegraph.split(MINI_TEMPLATE)
        self.assertIn(tail[:tail.rindex("</script>")], p)  # the viewer's tail, then the link to the compare page
        self.assertIn(flamegraph.LINK_MARK, p)
        self.assertEqual(flamegraph.link(p), p)  # once
        self.assertIn("const levels = Array(3)", p)
        self.assertIn("height: 48px", p)
        self.assertIn("<h1>a &lt;b&gt;</h1>", p)
        self.assertIn('const cpool = [\n"all",\n" A.f",\n" B.g"\n];', p)
        self.assertIn("/* overlay */\nf(3,0,0,100)\nf(9,1,0,60)\nf(18,2,10,50)", p)  # name << 3 | type; left from the previous frame's
        with self.assertRaises(flamegraph.TemplateError):
            flamegraph.page("<html></html>", "t", [("all", 0, 0, 1)])

    def test_a_renamed_page_redirects_to_its_widget(self):
        """The first toggle pages' URLs (toggle-<event>[-byleaf].html), handed out before the pairs, still lead there."""
        d = tempfile.mkdtemp()
        for side in "ab":
            for sfx in ("", "-byleaf"):
                open(os.path.join(d, f"toggle-{side}-cpu{sfx}.html"), "w").write("<html></html>")
        open(os.path.join(d, "diff-cpu.html"), "w").write("<html></html>")  # the event
        compare.redirect(os.path.join(d, "toggle-cpu-byleaf.html"), f"compare.html#{compare.pair_id('cpu', True)}")
        self.assertIn('url=compare.html#cpu-pair-byleaf"', open(os.path.join(d, "toggle-cpu-byleaf.html")).read())
        compare.write(d, "base", "tip")
        self.assertIn('id="cpu-pair-byleaf"', open(os.path.join(d, "compare.html")).read())

    def test_no_page_draws_its_own_canvas(self):
        """A flame graph drawn by perflab's own code would drift from the viewer's controls (zoom, search, filters, short
        names, help, the compare page's link): pages draw through flamegraph.page."""
        src = os.path.join(SRC, "perflab")
        own = [f for f in sorted(os.listdir(src)) if f.endswith((".py", ".js")) and "getContext(" in open(os.path.join(src, f)).read()]
        self.assertEqual(own, [])

    @unittest.skipUnless(os.path.exists(LAB_JFRCONV), "no retronym/async-profiler jfrconv (mise run tools:async-profiler)")
    def test_the_toggle_graphs_have_the_standard_controls(self):
        d = tempfile.mkdtemp()
        col = os.path.join(d, "a.collapsed")
        open(col, "w").write("main_[j];T.find_[j];S.denot_[i] 6\nmain_[j];T.find_[j] 4\n")
        template = os.path.join(d, "a.html")
        subprocess.run([LAB_JFRCONV, col, template], check=True, capture_output=True, timeout=120)
        t = kinds.tree(collections.Counter({"main_[j];T.find_[j];S.denot_[i]": 6}), collections.Counter({"main_[j];T.find_[j];S.denot_[j]": 7}), 1, 1)
        kinds.toggle_graphs(open(template).read(), os.path.join(d, "ta.html"), os.path.join(d, "tb.html"), "cpu", "base", "tip", t)
        page = open(os.path.join(d, "ta.html")).read()
        head, _ = flamegraph.split(open(template).read())
        for control in ("id='search'", "id='shortn'", "id='info'", "id='zoomin'", "'wheel'", "function applyFlameState"):
            self.assertIn(control, head)
        code = head[head.index("const levels"):]
        self.assertIn(code[code.index("\n"):], page)  # the viewer's code, unchanged after the frame count


class CurateTest(unittest.TestCase):
    """Each step of a curated diff, on small synthetic collapsed stacks (root first)."""

    @staticmethod
    def st(*lines, ops=1):
        return stacks.of_lines([l.rsplit(" ", 1)[0:1] + [int(l.rsplit(" ", 1)[1])] for l in lines], ops, 1.0)

    def curated(self, a, b, **hints):
        c = curate.Curator(curate.merge(curate.DEFAULTS, hints))
        ba, _ = c.base(a)
        bb, _ = c.base(b)
        return c.aligned(c.shaped(ba), c.shaped(bb))

    def test_names_lose_compilation_suffixes(self):
        a, _ = self.curated(self.st("main;F.f_[j];G.g_[i] 2", "main;F.f_[0];G.g_[j] 3"), self.st("main;G.g 1"), align=False)
        self.assertEqual(a, {"main;F.f;G.g": 5})

    def test_meaningless_frames_are_dropped(self):
        a, _ = self.curated(self.st("main;interpreted;F.f;interpreted 4"), self.st("main;F.f 1"), align=False)
        self.assertEqual(a, {"main;F.f": 4})

    def test_plumbing_folds_into_its_caller_but_stays_as_the_leaf(self):
        a, _ = self.curated(self.st("main;F.f;java/lang/invoke/LambdaForm$MH.invoke;F$$Lambda.apply;G.g 2",
                                    "main;G.g$lzyINIT1;java/lang/invoke/VarHandleGuards.guard_LL_L;java/lang/invoke/VarHandle.getAcquire 3",
                                    "main;scala/X.y;G.g 1"),
                            self.st("main 1"), fold=["^scala/"], align=False)
        self.assertEqual(a, {"main;F.f;G.g": 2, "main;java/lang/invoke/VarHandle.getAcquire": 3, "main;G.g": 1})

    def test_recursion_keeps_the_outermost_frame(self):
        a, _ = self.curated(self.st("main;T.typed;T.adapt;T.typed;T.adapt;T.typed;L.leaf 1", "main;T.typed;T.adapt;T.typed 2"), self.st("main 1"), align=False)
        self.assertEqual(a, {"main;T.typed;T.adapt;L.leaf": 1, "main;T.typed;T.adapt;T.typed": 2})
        a, _ = self.curated(self.st("main;T.typed;T.typed;L.leaf 1"), self.st("main 1"), recursion=False, align=False)
        self.assertEqual(a, {"main;T.typed;T.typed;L.leaf": 1})

    def test_frames_one_build_lacks_are_dropped_above_the_leaf(self):
        a, b = self.curated(self.st("main;Phase.run;Typer.typed;S.denot 5"),
                            self.st("main;Phase.run;Phase.$anonfun$15;Typer.typed;S.infoAfterCompletion;S.denot 7",
                                    "main;Phase.run;Phase.$anonfun$15;Typer.typed;S.infoAfterCompletion 1"))
        self.assertEqual(a, {"main;Phase.run;Typer.typed;S.denot": 5})
        self.assertEqual(b, {"main;Phase.run;Typer.typed;S.denot": 7, "main;Phase.run;Typer.typed;S.infoAfterCompletion": 1})
        self.assertEqual(self.curated(self.st("main;X.x;L 1"), self.st("main;L 1"), align=False)[0], {"main;X.x;L": 1})

    def test_the_anchor_cuts_stacks_above_it_and_leaves_out_the_rest(self):
        c = curate.Curator(curate.merge(curate.DEFAULTS, {"anchor": r"Typer\.typed"}))
        base, outside = c.base(self.st("main;Phase.run;Typer.typed;L 2", "main;GC.collect 3"))
        self.assertEqual(([[c.names[x] for x in g] for g, _ in base], outside), ([["Typer.typed", "L"]], 3))

    def test_owners_groups_and_growth_beyond_the_ratio(self):
        rules = curate.merge(curate.DEFAULTS, {"owner": "dc/", "ownerSkip": ["dc/Ctx."],
                                               "groups": {"denot": r"\.(denot|symbol)$", "caches": r"Cache"}})
        # a: the miss is inlined into widen; b: the same load is a VarHandle getAcquire under denot, through a context accessor
        a = self.st("main;dc/T.typed;dc/F.findRef;dc/N.widen;jdk/Unsafe.get 10", "main;dc/T.typed;dc/O.other 90", ops=2)
        b = self.st("main;dc/T.typed;dc/F.findRef;dc/N.denot;dc/Ctx.period;java/lang/invoke/VarHandle.getAcquire 14",
                    "main;dc/T.typed;dc/F.findRef;dc/M.memberCache 6", "main;dc/T.typed;dc/O.other 90", ops=2)
        c = curate.Curator(rules)
        ba, _ = c.base(a)
        bb, _ = c.base(b)
        (oa, ia), (ob, ib) = c.tables(ba), c.tables(bb)
        self.assertEqual(oa, {"dc/N.widen": 10, "dc/O.other": 90})  # the leaf is no owner, its nearest owner frame is
        self.assertEqual(ob, {"dc/N.denot": 14, "dc/M.memberCache": 6, "dc/O.other": 90})  # dc/Ctx. skipped
        t = curate.summarize(rules, oa, ob, ia, ib, 100, 110, 2, 2)
        self.assertEqual(t["total"], {"a": 50.0, "b": 55.0, "ratio": 1.1})
        g = {r["name"]: (r["delta"], r["members"]) for r in t["groups"]}
        self.assertEqual(g, {"denot": (7.0, 1), "caches": (3.0, 1), "(ungrouped)": (-5.0, 2)})
        top = t["excess"][0]
        self.assertEqual((top["name"], top["a"], top["b"]), ("dc/F.findRef", 5.0, 10.0))
        self.assertAlmostEqual(top["excess"], 10.0 - 5.0 * 1.1)
        self.assertNotIn("dc/N.denot", [r["name"] for r in t["excess"]])  # in one build only: not a growth
        md = curate.table_md("cache-misses", t, "a", "b", rules, 5)
        self.assertIn("| denot | +7 | 0 | 7 | +14.00% | 1 |", md)
        self.assertIn("| +7 | 0 | 7 | +14.00% | `dc/N.denot` |", md)

    def test_rules_merge_from_the_lab_the_spec_a_preset_and_json(self):
        Project('[build]\njmh = "x"\n[diff]\nowner = "dc/"\nfold = ["^scala/"]\n[diff.groups]\nd = "denot"\n')
        spec = {"diff": {"fold": ["^x/"], "groups": {"c": "Cache"}, "presets": {"typer": {"anchor": "Typer"}}}}
        r, name = curate.rules_for(spec, "typer")
        self.assertEqual((name, r["owner"], r["fold"], r["groups"], r["anchor"]), ("typer", "dc/", ["^scala/", "^x/"], {"d": "denot", "c": "Cache"}, "Typer"))
        r, name = curate.rules_for(spec, '{"owner": "x/"}')
        self.assertEqual((r["owner"], name[:8]), ("x/", "curated-"))
        self.assertEqual(curate.rules_for(spec)[1], "curated")
        with self.assertRaises(SystemExit):
            curate.rules_for(spec, "nope")

    def test_the_stack_cache_round_trips(self):
        st = self.st("main;F.f_[j] 3", "main;G.g 2", "main;F.f_[j] 1", ops=4)
        f = os.path.join(tempfile.mkdtemp(), "stacks-cycles.gz")
        stacks.write(f, st)
        back = stacks.read(f)
        self.assertEqual(sorted(back.named()), [(["main", "F.f_[j]"], 4), (["main", "G.g"], 2)])
        self.assertEqual((back.ops, back.total), (4, 6))

    def test_ab_diff_writes_the_raw_and_the_curated_diff(self):
        """End to end, with a stand-in jfrconv that writes the stacks it is given as the 'graph'."""
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        d, conv = CollapsedTest().run_dir()
        conv_graph = os.path.join(d, "jfrconv-graph")
        # converting a recording prints LINES; rendering copies its (last) collapsed input to the output
        open(conv_graph, "w").write("#!/bin/sh\nfor last; do :; done\ncase \"$*\" in *.jfr*) exec " + conv + " \"$@\";; esac\n"
                                     "prev=; for x; do [ \"$x\" = \"$last\" ] || prev=$x; done\ncp \"$prev\" \"$last\"\n")
        os.chmod(conv_graph, 0o755)
        for v in ("base", "tip"):
            shutil.copytree(d, os.path.join(camp, "c", "k", v, "1"))
        json.dump({"name": "c", "corpora": {"k": ""}, "variants": {"base": "", "tip": ""}, "benchmark": "B", "rounds": 1,
                   "diff": {"owner": "a"}}, open(os.path.join(camp, "c", "spec.json"), "w"))
        os.environ["JFRCONV"] = conv_graph
        self.addCleanup(os.environ.pop, "JFRCONV", None)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(curate.main(["c", "base", "tip", "--event", "cache-misses", "--by-leaf"]), 0)
        raw, cur = os.path.join(camp, "c", "diff-base-tip"), os.path.join(camp, "c", "diff-base-tip-curated")
        self.assertTrue(os.path.exists(os.path.join(camp, "c", "k", "base", "1", "stacks-cache-misses.gz")))
        self.assertIn("main-jmh-worker-1", open(os.path.join(raw, "diff-cache-misses.html")).read())
        self.assertEqual(open(os.path.join(cur, "diff-cache-misses.html")).read(), "a;b;c 10\n[main-jmh-worker-1];F$$Lambda;a;d 5\nx;y;z 2\n")
        self.assertTrue(os.path.exists(os.path.join(cur, "diff-cache-misses-byleaf.html")))
        pair = json.load(open(os.path.join(cur, "pair.json")))
        self.assertEqual((pair["curated"], pair["rules"]["owner"], pair["cells"]), ("curated", "a", ["k/base/1", "k/tip/1"]))
        page = open(os.path.join(cur, "compare.html")).read()
        self.assertIn("<p class=note>Curated: names without compilation suffixes", page)
        self.assertIn('data-view="byleaf"', page)
        self.assertEqual(json.load(open(os.path.join(cur, "tables-cache-misses.json")))["total"]["ratio"], 1.0)


class MetricsTest(unittest.TestCase):
    # an xctrace mem-l1d cell, as XctraceProfiler and an aux counter report it: 6 iterations of one op, `files` summed
    @staticmethod
    def cell(files, cyc, ins, stall, jit):
        s = lambda x, u="#": {"score": x, "scoreUnit": u}
        m = {"files": s(files), "gc.alloc.rate.norm": s(5e9, "B/op"), "gc.time": s(700.0, "ms"),
             "xctrace.CORE_ACTIVE_CYCLE": s(cyc, "#/op"), "xctrace.INST_ALL": s(ins, "#/op"), "xctrace.IPC.bench": s(ins / cyc, "insts/clk"),
             "xctrace.L1D_CACHE_MISS_LD_NONSPEC": s(ins / 50, "#/op"), "xctrace.L1D_CACHE_MISS_LD_NONSPEC/kinst": s(20.0, "#/kinst"),
             "xctrace.LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS": s(cyc * stall / 100, "#/op"),
             "xctrace.LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS/cycles": s(stall, "%"),
             "xctrace.cycles%.bench": s(80.0 - jit, "%"), "xctrace.cycles%.jit": s(jit, "%"), "xctrace.cycles%.gc": s(10.0, "%"),
             "xctrace.cycles%.other": s(10.0, "%"), "xctrace.IPC.jit": s(2.5, "insts/clk"), "xctrace.IPC.gc": s(1.5, "insts/clk"),
             "xctrace.IPC.other": s(2.0, "insts/clk")}
        return [{"mode": "avgt", "measurementIterations": 6, "measurementTime": "1 s", "jvmArgs": [], "secondaryMetrics": m,
                 "primaryMetric": {"score": 4000.0, "scoreError": 1.0, "scoreUnit": "ms/op", "rawData": [[4000.0] * 6]}}]

    def test_every_counter_per_op_and_per_unit(self):
        r = self.cell(2922, 20e9, 66e9, 16.4, 7.5)[0]
        per_op = {k: (label, x) for k, label, _, _, x in metrics.of(r)}
        self.assertEqual(per_op["cycles"], ("cycles/op", 20e9))
        self.assertEqual(per_op["ev:LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS/cycles"], ("LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS % of cycles", 16.4))
        self.assertEqual(per_op["ev:L1D_CACHE_MISS_LD_NONSPEC/kinst"][1], 20.0)
        self.assertEqual(per_op["cyc%:jit"], ("JIT % of cycles", 7.5))
        self.assertAlmostEqual(per_op["cycles:all"][1], 20e9 / 0.725)
        per_file = {k: (label, x) for k, label, _, _, x in metrics.of(r, "files")}
        self.assertEqual(per_file["cycles"], ("cycles/file", 20e9 / 487))
        self.assertEqual(per_file["score"], ("ms/file", 4000.0 / 487))
        self.assertEqual(per_file["ipc"], per_op["ipc"])  # ratios stay

    def test_ops_by_iteration_time(self):
        r = self.cell(2922, 20e9, 66e9, 16.4, 7.5)[0]
        self.assertEqual(metrics.ops({**r, "measurementTime": "1 min"}), 6 * 15)
        with self.assertRaises(ValueError):
            metrics.ops({**r, "measurementTime": "1 fortnight"})

    def test_kperf_events_counting_cycles_are_a_share_of_cycles(self):
        self.assertTrue(metrics.counts_cycles("LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS"))
        self.assertFalse(metrics.counts_cycles("L1D_CACHE_MISS_LD_NONSPEC"))
        if os.path.isdir(metrics.KPEP):  # by the description, where the name doesn't say
            self.assertTrue(metrics.counts_cycles("LDST_UNIT_OLD_L1D_CACHE_MISS"))
        r = self.cell(2922, 20e9, 66e9, 16.4, 7.5)[0]
        hw = {"cycles": 2e9, "instructions": 6e9, "L1D_CACHE_MISS_LD_NONSPEC": 1.2e8, "LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS": 5e8}
        r["secondaryMetrics"] = {"files": r["secondaryMetrics"]["files"]}
        got = {k: x for k, _, _, _, x in metrics.of(r, hw=hw)}
        self.assertEqual(got["ev:L1D_CACHE_MISS_LD_NONSPEC/kinst"], 20.0)
        self.assertEqual(got["ev:LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS/cycles"], 25.0)
        self.assertEqual(got["ipc"], 3.0)

    def test_summary_and_report_per_unit_and_per_op(self):
        Project('[build]\njmh = "x"\n')
        camp = config.get().campaigns
        for v, cell in (("shared", self.cell(2922, 20e9, 66e9, 16.4, 7.5)), ("independent", self.cell(4 * 2922, 80e9, 200e9, 27.5, 1.3))):
            d = os.path.join(camp, "c", "k", v, "1")
            os.makedirs(d)
            json.dump(cell, open(os.path.join(d, "result.json"), "w"))
        spec = os.path.join(camp, "c", "spec.json")
        json.dump({"name": "c", "rounds": 1, "corpora": {"k": ""}, "variants": {"shared": "", "independent": ""}, "perUnit": "files", "benchmark": "B"},
                  open(spec, "w"))
        page = open(index.build(camp)).read()
        self.assertIn('<button data-sn="unit" title="divided by the files counter per op" aria-pressed="false">per file</button>', page)
        unit, op = re.findall(r'<div class="summ card-s" data-stat="mean" data-norm="(\w+)">.*?<script type="application/json">(.*?)</script>', page)
        self.assertEqual(unit[0], "unit")
        data = json.loads(re.search(r'data-norm="unit">.*?<script type="application/json">(.*?)</script>', page).group(1))
        self.assertIn({"k": "ev:LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS/cycles", "h": "LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS % of cycles", "kind": "pct"}, data["metrics"])
        cycles = [m["k"] for m in data["metrics"]].index("cycles")
        self.assertEqual(data["rows"][1]["m"]["mean"][cycles][0], "41.1M")  # 80G / 1948: per file, the same cycles at 1.03x
        self.assertAlmostEqual(data["rows"][1]["m"]["mean"][cycles][3], 100 * (80e9 / 1948 / (20e9 / 487) - 1))
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ab.report(ab.Spec(spec))
        self.assertIn("| cycles/file | 41.1M | 41.1M (+0.0%) |", out.getvalue())
        self.assertIn("| LDST_UNIT_WAITING_OLD_L1D_CACHE_MISS % of cycles | 16.4% | 27.5% (+67.7%) |", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ab.report(ab.Spec(spec), per_op=True)
        self.assertIn("| cycles/op | 20G | 80G (+300.0%) |", out.getvalue())


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

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_index_scripts_parse(self):
        Project('[build]\njmh = "x"\n')
        page = open(index.build(config.get().campaigns)).read()
        self.assertIn('<meta name="perflab-code"', page)
        for i, js in enumerate(re.findall(r"<script>(.*?)</script>", page, re.S)):
            f = os.path.join(config.get().root, f"s{i}.js")
            open(f, "w").write(js)
            r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_index_lists_runs_with_scores_and_links(self):
        Project('[build]\njmh = "x"\n[index]\nflags = "^-XX"\n')
        res = [{"benchmark": "a.B.compile", "params": {"corpus": "re2s", "g": g}, "jvmArgs": [],
                "primaryMetric": {"score": 150.0 + int(g), "scoreError": 3.2, "scoreUnit": "ms/op"}} for g in ("0", "4")]
        out = self.run_dir("multi-global", ["-jvm", "/jdk/bin/java", "-p", "corpus=re2s", "B"], result=res,
                           state={"status": "finished", "rc": 0})
        open(os.path.join(out, "jmh.log"), "w").close()
        open(os.path.join(out, "iterations.tsv"), "w").write("index\tkind\n")
        page = open(index.build(config.get().campaigns)).read()
        self.assertIn('<span class="kind">run</span><h2>multi-global</h2><span class="badge finished">finished</span>', page)
        self.assertIn("<code>-p corpus=re2s</code>", page)
        self.assertIn("<code>-XX:+UseG1GC</code>", page)
        self.assertIn('<th class="n">ms/op</th>', page)
        self.assertIn('compile <code>g=4</code></td><td class="n">154 ± 3</td>', page)
        self.assertNotIn("cycles/op", page)  # no column without values
        self.assertIn('<a class="btn" href="../runs/multi-global/jmh.log">jmh.log</a>', page)
        self.assertIn('<optgroup label="runs"><option value="../runs/multi-global/">multi-global</option>', page)


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
            self.assertIn(b'<h2 class="sec" id="campaigns">Campaigns', urllib.request.urlopen(url).read())
            # text is served as UTF-8, as GitHub Pages does: a report's Δ reads as Δ
            with open(os.path.join(camp, "report.md"), "w", encoding="utf-8") as f:
                f.write("| Δ |\n")
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/ab/report.md")
            self.assertEqual(r.headers["Content-Type"], "text/markdown; charset=utf-8")
            self.assertEqual(r.read().decode("utf-8"), "| Δ |\n")
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


class TranscriptTest(unittest.TestCase):
    def setUp(self):
        self.p = Project('[build]\njmh = "x"\n')
        self.path = os.path.join(self.p.dir, "t.txt")
        self.addCleanup(os.environ.pop, transcript.ENV, None)
        transcript.setup(self.path)

    def test_build_output_and_jmh_log_as_they_come(self):
        out = os.path.join(self.p.dir, "run")
        os.makedirs(out)
        # the build prints (with a terminal control sequence), and JMH writes its own log beside build.log
        cmd = "printf '\\033[0Jcompiling\\n'; echo '# Fork: 1 of 1' > run/jmh.log; sleep 1.5; echo done"
        self.assertEqual(jmh.run_build(cmd, os.path.join(out, "build.log")), 0)
        with open(self.path) as f:
            lines = f.read().splitlines()
        self.assertIn("  | compiling", lines)
        self.assertIn("  > # Fork: 1 of 1", lines)
        self.assertIn("  | done", lines)
        with open(os.path.join(out, "build.log")) as f:
            self.assertEqual(f.read(), f"$ {cmd}\n\x1b[0Jcompiling\ndone\n")  # the command atop its log

    def test_a_labelled_build_is_shown_on_the_index_while_it_runs(self):
        out = os.path.join(self.p.dir, "run")
        os.makedirs(out)
        seen = []
        state = loadgate.state_path(jmh.BUILD_STATE)
        tick = lambda: seen.append(json.load(open(state)) if os.path.exists(state) else None)
        self.assertEqual(jmh.run_build("echo compiling; sleep 1.5", os.path.join(out, "build.log"), every=1, tick=tick, label="base"), 0)
        self.assertEqual(seen[0]["label"], "base")
        self.assertEqual(seen[0]["tail"], ["compiling"])
        self.assertEqual(seen[0]["log"], os.path.relpath(os.path.join(out, "build.log"), os.path.dirname(state)))
        self.assertFalse(os.path.exists(state))  # gone when the build ends

    def test_an_interrupted_build_stops_what_it_started(self):
        out = os.path.join(self.p.dir, "run")
        os.makedirs(out)
        pids = os.path.join(out, "pids")

        def interrupt():
            raise SystemExit(143)  # as perflab's SIGTERM handler does
        cmd = f"sleep 60 & echo $$ $! > {pids}; wait"
        t0 = time.time()
        with self.assertRaises(SystemExit):
            jmh.run_build(cmd, os.path.join(out, "build.log"), every=1, tick=interrupt)
        self.assertLess(time.time() - t0, 10)
        for pid in map(int, open(pids).read().split()):  # the shell and its child, both gone
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_follow_waits_for_a_line_to_end(self):
        import threading
        log = os.path.join(self.p.dir, "jmh.log")
        done = threading.Event()
        t = threading.Thread(target=transcript.follow, args=(log, done))
        with open(log, "w") as f:
            f.write("Iteration   1: ")
            f.flush()
            t.start()
            time.sleep(1.5)
            f.write("12.3 ms/op\n")
        done.set()
        t.join()
        with open(self.path) as f:
            self.assertIn("  > Iteration   1: 12.3 ms/op", f.read().splitlines())

    def test_a_failure_is_its_last_line(self):
        import signal
        from perflab import cli
        self.addCleanup(signal.signal, signal.SIGTERM, signal.getsignal(signal.SIGTERM))
        with self.assertRaises(FileNotFoundError):
            cli.main(["ab", "run", os.path.join(self.p.dir, "missing.json")])
        with open(self.path) as f:
            self.assertTrue(f.read().splitlines()[-1].startswith("[perflab] failed: FileNotFoundError"))

    def test_loadgate_wait_is_published_then_removed(self):
        seen = []
        loads = iter([(3.0, "javac 3.0"), (0.5, ""), (0.5, "")])
        orig, loadgate.other_load = loadgate.other_load, lambda root: next(loads)
        self.addCleanup(setattr, loadgate, "other_load", orig)
        orig_publish = loadgate.publish
        loadgate.publish = lambda st: (seen.append(json.loads(json.dumps(st))), orig_publish(st))
        self.addCleanup(setattr, loadgate, "publish", orig_publish)
        loadgate.wait(os.getpid(), limit=1.0, quiet=0)
        self.assertEqual(seen[0]["samples"][0][1:], [3.0, "javac 3.0"])
        self.assertIsNone(seen[-1])
        self.assertFalse(os.path.exists(loadgate.state_path()))
        with open(self.path) as f:
            self.assertIn("waiting: other load 3.0 cores (javac 3.0)", f.read())


class LaunchTest(unittest.TestCase):
    """Launch mode: the build step writes launch.json, perflab snapshots the build and starts JMH itself."""
    def setUp(self):
        self.p = Project('[build]\nmode = "launch"\nlaunch = "python3 build.py {out}"\n')
        d = self.p.dir
        self.roots = os.path.join(d, "checkout")
        os.makedirs(os.path.join(self.roots, "classes"))
        with open(os.path.join(self.roots, "classes", "A.class"), "w") as f:
            f.write("v1")
        with open(os.path.join(self.roots, "lib.jar"), "w") as f:
            f.write("jar")
        self.ext = os.path.join(d, "cache.jar")
        open(self.ext, "w").close()
        launch_json = {"mainClass": "M", "java": "/jdk/bin/java", "roots": [self.roots],
                       "classpath": [os.path.join(self.roots, "classes"), os.path.join(self.roots, "missing"), self.ext],
                       "javaOptions": ["-Xss2m", f"-Dlib={os.path.join(self.roots, 'lib.jar')}{os.pathsep}/elsewhere"],
                       "build": {"checkout": self.roots, "commit": "abcdef1234567", "dirty": False}}
        with open(os.path.join(d, "build.py"), "w") as f:
            f.write("import json, os, sys\n"
                    f"json.dump({launch_json!r}, open(os.path.join(sys.argv[1], 'launch.json'), 'w'))\n")

    def test_snapshot_copies_the_builds_outputs(self):
        built = launch.build(os.path.join(self.p.dir, "c", launch.BUILD_DIR))
        cp = built["classpath"]
        self.assertEqual(len(cp), 2)  # the missing output directory is dropped
        self.assertTrue(cp[0].startswith(built["snapshot"]))
        self.assertEqual(cp[1], self.ext)
        self.assertEqual([e["path"] for e in built["external"]], [self.ext])
        lib = built["javaOptions"][1].split("=", 1)[1].split(os.pathsep)
        self.assertTrue(lib[0].startswith(built["snapshot"]) and lib[1] == "/elsewhere")
        # the snapshot is the build as it was: a later change to the checkout does not reach it
        with open(os.path.join(self.roots, "classes", "A.class"), "w") as f:
            f.write("v2")
        with open(os.path.join(cp[0], "A.class")) as f:
            self.assertEqual(f.read(), "v1")

    def test_a_campaign_reuses_its_snapshot(self):
        d = os.path.join(self.p.dir, "c", launch.BUILD_DIR)
        first = launch.build(d)
        os.unlink(os.path.join(self.p.dir, "build.py"))  # no second build
        self.assertEqual(launch.build(d)["snapshot"], first["snapshot"])

    def test_the_command_starts_the_driver_from_the_snapshot(self):
        built = launch.build(os.path.join(self.p.dir, "r", launch.BUILD_DIR))
        out = os.path.join(self.p.dir, "r")
        cmd = shlex.split(jmh.prepare(out, "none", ["-jvm", "/other/bin/java", "B"], built=built))
        self.assertEqual(cmd[0], "/other/bin/java")  # the JDK the forks use, as -jvm names it
        self.assertEqual(cmd[cmd.index("-cp") + 1], os.pathsep.join(built["classpath"]))
        self.assertEqual(cmd[-2:], ["M", f"@{out}/jmh.args"])
        cmd = shlex.split(jmh.prepare(out, "none", ["B"], built=built))
        self.assertEqual(cmd[0], "/jdk/bin/java")  # else the build's

    def test_the_transcript_counts_a_classpath(self):
        self.assertEqual(jmh.brief(f"java -Xss2m -cp a.jar{os.pathsep}b M @x"), "java -Xss2m -cp '<2 entries>' M @x")
        self.assertEqual(jmh.brief("sbt --client 'b/Jmh/run @x'"), "sbt --client 'b/Jmh/run @x'")

    def test_a_campaign_builds_each_variant_from_its_checkout(self):
        # the build step names the classes after the checkout it was given
        with open(os.path.join(self.p.dir, "build.py"), "w") as f:
            f.write("import json, os, sys\n"
                    "co = os.environ['CO']; os.makedirs(co + '/classes', exist_ok=True)\n"
                    "json.dump({'mainClass': 'M', 'java': 'java', 'roots': [co], 'classpath': [co + '/classes'], 'javaOptions': [f'-Dco={co}/classes']},"
                    " open(os.path.join(sys.argv[1], 'launch.json'), 'w'))\n")
        spec_f = os.path.join(self.p.dir, "s.json")
        with open(spec_f, "w") as f:
            json.dump({"name": "b", "benchmark": "B", "rounds": 1, "corpora": {"c": ""},
                       "builds": {v: {"checkout": v, "env": {"CO": "{checkout}"}} for v in ("base", "pr")}}, f)
        spec = ab.Spec(spec_f)
        self.addCleanup(os.environ.pop, "PERFLAB_BUILD_MODE", None)  # a campaign with builds runs in launch mode
        self.assertEqual(list(spec.variants), ["base", "pr"])
        cmds = {}
        orig, jmh.run_build = jmh.run_build, lambda cmd, log, *a, **k: (cmds.setdefault(log, cmd), orig(cmd, log, *a, **k))[1] \
            if "build.py" in cmd else 1
        self.addCleanup(setattr, jmh, "run_build", orig)
        with self.assertRaises(SystemExit):  # the stubbed cell run fails; the builds are what this checks
            ab.run(spec, False)
        b = launch.read(os.path.join(spec.out, launch.BUILD_DIR, "base", launch.LAUNCH))
        self.assertTrue(b["built"]["classpath"][0].startswith(os.path.join(self.p.dir, "base")))
        self.assertIn(os.path.join(spec.out, launch.BUILD_DIR, "base", "snapshot"), b["classpath"][0])

    def test_the_load_gates_root_is_perflab(self):
        self.assertEqual(loadgate.server_pid(), os.getpid())


if __name__ == "__main__":
    unittest.main()
