import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`
from perflab import ab, loadgate  # noqa: E402


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

    def test_no_gate_no_check(self):
        self.assertEqual(ab.load_check(type("S", (), {"loadgate": None})(), self.d), [])


if __name__ == "__main__":
    unittest.main()
