import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`
from perflab import ab, api, jfrevents, jmh, loadgate  # noqa: E402
from test_perflab import Project  # noqa: E402


class OursTest(unittest.TestCase):
    def test_the_profilers_serving_the_benchmark_are_not_other_load(self):
        procs = {1: (0, 0, "launchd"), 10: (1, 5, "sbt"), 11: (10, 9, "java"), 20: (1, 2, "asprof-kperf"),
                 30: (1, 1, "xctrace"), 40: (1, 3, "WindowServer")}
        mine = loadgate.ours(procs, 10)
        self.assertTrue({10, 11, 20, 30} <= mine)
        self.assertNotIn(40, mine)


class LoadCheckTest(unittest.TestCase):
    """The case that motivated it (perfint-branch, tastyQuery/708df2535c): a burst of 1.6 cores in a cell whose mean was
    0.9, over the two measurement iterations that came out 9% slow."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "iterations.tsv"), "w") as f:
            f.write("index\tkind\tvariant\tstart_ms\tend_ms\tscore\n0\twarmup\t\t1000000\t1004000\t1281\n")
            for i, (a, s) in enumerate([(1010, 720), (1014, 722), (1018, 790), (1022, 785)]):
                f.write(f"{12 + i}\tmeasure\t\t{a * 1000}\t{(a + 3.5) * 1000:.0f}\t{s}\n")
        with open(os.path.join(self.d, "load.tsv"), "w") as f:
            f.write("1005\t0.8\tWindowServer 0.1\n")  # an old 5 s sample, no window column
            for t, c in [(1012, 0.5), (1014, 0.6), (1016, 0.7), (1018, 0.4), (1020, 1.62), (1022, 0.6), (1024, 1.51), (1026, 0.4)]:
                f.write(f"{t}\t{c}\tjava 0.9\t2\n")

    def test_each_iteration_gets_the_highest_sample_over_it(self):
        its = loadgate.per_iteration(os.path.join(self.d, "load.tsv"), os.path.join(self.d, "iterations.tsv"))
        self.assertEqual([i["index"] for i in its], [12, 13, 14, 15])
        self.assertEqual([i["cores"] for i in its], [0.6, 0.7, 1.62, 1.51])
        self.assertEqual(its[2]["top"], "java 0.9")

    def test_a_burst_over_iterations_fails_the_gate_though_the_mean_passes(self):
        spec = type("S", (), {"loadgate": {"maxCores": 1.5}})()
        self.assertLess(ab.mean_load(os.path.join(self.d, "load.tsv")), 1.5)
        hit = ab.load_check(spec, self.d)
        self.assertEqual([i["index"] for i in hit], [14, 15])
        rec = json.load(open(os.path.join(self.d, ab.LOAD_CHECK)))
        self.assertEqual(rec["disturbed"], [14, 15])

    def test_a_disturbed_attempt_is_voided_until_its_rerun(self):
        # left in the cell while the campaign waited to run it again, it read as a result (harness-aa-xbatch dotc/b/1)
        camp = tempfile.mkdtemp()
        spec = type("S", (), {"loadgate": {"maxCores": 1.5}, "out": camp, "cell_dir": lambda s, c, v, r: os.path.join(camp, c, v, str(r))})()
        cell = spec.cell_dir("dotc", "b", 1)
        os.makedirs(cell)
        for f in ("iterations.tsv", "load.tsv"):
            os.rename(os.path.join(self.d, f), os.path.join(cell, f))
        open(os.path.join(cell, "result.json"), "w").write("[]")
        open(os.path.join(cell, "jmh.args"), "w").write("-i 4")
        self.assertTrue(ab.load_check(spec, cell))
        void = ab.set_aside(spec, "dotc", "b", 1, "other load over 1.5 cores during measurement iterations 14, 15 (attempt 1, run again)")
        # the rerun starts from the cell as set up: iterations.tsv and load.tsv are appended to, so kept they would mix
        # the voided attempt's rows into the rerun's (m4-hk-fastpath-typer-kperf-2 scala/hk/1: cycles/op halved)
        self.assertEqual(sorted(os.listdir(cell)), ["jmh.args"])
        self.assertTrue(os.path.exists(os.path.join(void, "iterations.tsv")))
        self.assertTrue(os.path.exists(os.path.join(void, "result.json")))
        self.assertEqual(json.load(open(os.path.join(void, ab.LOAD_CHECK)))["disturbed"], [14, 15])
        info = api._void_info(camp, void)
        self.assertEqual((info["corpus"], info["variant"], info["round"]), ("dotc", "b", 1))
        self.assertIn("iterations 14, 15", info["reason"])

    def test_no_gate_no_check(self):
        self.assertEqual(ab.load_check(type("S", (), {"loadgate": None})(), self.d), [])


HEAD = "index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\tpid\tunit\talloc_bytes\n"


def attempt_rows(pid, measured):
    rows = [f"-1\tstartup\t\t0\t1\t\t\t\t{pid}\tms/op\t\n", f"0\twarmup\t\t1\t2\t5\t1\t\t{pid}\tms/op\t\n"]
    rows += [f"{1 + i}\tmeasure\t\t2\t3\t5\t1\t\t{pid}\tms/op\t\n" for i in range(measured)]
    return "".join(rows) + f"-1\texit\t\t3\t3\t\t\t\t{pid}\tms/op\t\n"


def result(measured):
    return [{"mode": "ss", "primaryMetric": {"score": 5.0, "scoreError": 0.1, "scoreUnit": "ms/op", "rawData": [[5.0] * measured]},
             "secondaryMetrics": {}}]


class VoidedRetryTest(unittest.TestCase):
    """m4-hk-fastpath-typer-kperf-2 scala/hk/1: the loadgate voided attempt 1 and ran the cell again, which kept attempt
    1's iterations.tsv rows, jit-<pid>.jitrec and gc.log.0; the summary divided attempt 2's cycles by both attempts' ops."""

    def test_a_retried_cell_holds_only_its_last_attempt(self):
        p = Project('[build]\njmh = "true {args}"\n[benchmark]\ncorpus = "c"\n')
        os.chdir(p.dir)
        spec_f = os.path.join(p.dir, "s.json")
        json.dump({"name": "vr", "benchmark": "B", "rounds": 1, "corpora": {"x": ""}, "variants": {"a": ""},
                   "loadgate": {"maxCores": 1.5}}, open(spec_f, "w"))
        spec = ab.Spec(spec_f)
        attempts = []

        def run_build(cmd, log, *a, **k):  # what the agent and JMH leave in the cell: appended rows, per-run files
            cell = os.path.dirname(log)
            pid = 100 + len(attempts)
            attempts.append(sorted(os.listdir(cell)))
            tsv = os.path.join(cell, "iterations.tsv")
            head = "" if os.path.exists(tsv) else HEAD
            with open(tsv, "a") as f:
                f.write(head + attempt_rows(pid, 8))
            open(os.path.join(cell, f"jit-{pid}.jitrec"), "w").write("x")
            open(os.path.join(cell, f"gc.log.{len(attempts) - 1}"), "w").write("x")
            open(os.path.join(cell, "load.tsv"), "a").write(f"{pid}\t{2.0 if len(attempts) == 1 else 0.1}\n")
            json.dump(result(8), open(os.path.join(cell, "result.json"), "w"))
            return 0
        loads = iter([2.0, 0.1])  # attempt 1 disturbed, attempt 2 quiet
        for mod, name, value in [(jmh, "run_build", run_build), (ab, "check", lambda *a, **k: None),
                                 (ab, "wait_until_quiet", lambda s: None), (ab, "start_load_sampler", lambda s, p: None),
                                 (ab, "mean_load", lambda p: next(loads)), (ab, "load_check", lambda s, d: [])]:
            self.addCleanup(setattr, mod, name, getattr(mod, name))
            setattr(mod, name, value)
        ab.run(spec, False)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], attempts[1])  # the retry starts from the cell as the first attempt found it
        cell = spec.cell_dir("x", "a", 1)
        files = os.listdir(cell)
        self.assertNotIn("jit-100.jitrec", files)
        self.assertNotIn("gc.log.0", files)
        pids = {l.split("\t")[8] for l in open(os.path.join(cell, "iterations.tsv")).read().splitlines()[1:]}
        self.assertEqual(pids, {"101"})
        self.assertEqual(jfrevents.measured_ops(cell), 8)  # the ops of result.json's 8 iterations
        voids = os.path.join(spec.out, ab.VOID_DIR, "x", "a")
        (void,) = os.listdir(voids)
        self.assertIn("jit-100.jitrec", os.listdir(os.path.join(voids, void)))

    def test_ops_count_only_the_measured_rows_of_the_result(self):
        # a cell retried before set_aside cleared it: the voided attempt's rows come first
        d = tempfile.mkdtemp()
        open(os.path.join(d, "iterations.tsv"), "w").write(HEAD + attempt_rows(8895, 8) + attempt_rows(9295, 8))
        json.dump(result(8), open(os.path.join(d, "result.json"), "w"))
        self.assertEqual(jfrevents.measured_ops(d), 8)
        json.dump(result(16), open(os.path.join(d, "result.json"), "w"))  # two forks' worth: all of them count
        self.assertEqual(jfrevents.measured_ops(d), 16)


if __name__ == "__main__":
    unittest.main()
