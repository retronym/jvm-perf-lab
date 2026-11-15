import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import metrics, osprobe


def sample(t, pid, cpu_s, ptop, ins, cyc, runnable_s, energy_j, bench_s, busy):
    ru = {k: 0 for k in osprobe.RU_KEEP}
    ru.update(user_time=cpu_s * 1e9, user_ptime=ptop * cpu_s * 1e9, instructions=ins, cycles=cyc, pinstructions=ins, pcycles=ptop * cyc,
              runnable_time=(cpu_s + runnable_s) * 1e9, energy_nj=energy_j * 1e9)
    return {"t": t, "pid": pid, "ru": ru, "th": {"bench": [bench_s * 1e9, 1], "gc": [0.1 * t * 1e9, 4]},
            "cl": {"Super": [busy * t * 100, t * 100], "Performance": [0, t * 100]}}


class OsProbeTest(unittest.TestCase):
    def cell(self, samples, iterations):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, osprobe.OS_JSONL), "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")
        with open(os.path.join(d, "iterations.tsv"), "w") as f:
            f.write("index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\n")
            for i, (kind, a, b, ops) in enumerate(iterations):
                f.write(f"{i}\t{kind}\t\t{a * 1000}\t{b * 1000}\t1\t{ops}\t0\n")
        return d

    def test_groups(self):
        self.assertEqual("bench", osprobe.group("Java: scala.tools.nsc.compilerlab.CompileBenchmark.compile-jmh-worker-1"))
        self.assertEqual("jit", osprobe.group("Java: C2 CompilerThread0"))
        self.assertEqual("gc", osprobe.group("Java: GC Thread#3"))
        self.assertEqual("gc", osprobe.group("Java: G1 Conc#0"))
        self.assertEqual("other", osprobe.group("Java: VM Thread"))

    def test_iterations_interpolate_between_samples(self):
        # one thread busy the whole time, 4 G instructions/s at 4 GHz, 75% on the top tier, runnable 10% of the time
        ss = [sample(t, 7, t, 0.75, 4e9 * t, 4e9 * t, 0.1 * t, 2.0 * t, t, 0.5) for t in [x * 0.5 for x in range(0, 41)]]
        d = self.cell(ss, [("warmup", 1.0, 5.0, 1), ("measure", 5.25, 9.25, 1), ("measure", 10.0, 14.0, 1)])
        o = osprobe.summary(d)
        self.assertEqual(2, o["iterations"])
        self.assertAlmostEqual(8.0, o["cpu_s"], places=6)
        self.assertAlmostEqual(32e9, o["instructions"], delta=1)
        self.assertAlmostEqual(75.0, o["top_tier_time_pct"], places=6)
        self.assertAlmostEqual(75.0, o["top_tier_cycles_pct"], places=6)
        self.assertAlmostEqual(4.0, o["ghz"], places=6)
        self.assertAlmostEqual(10.0, o["runnable_pct"], places=6)
        self.assertAlmostEqual(8.0, o["per_op"]["energy_j"], places=6)
        self.assertAlmostEqual(1.0, o["threads_cores"]["bench"], places=6)
        self.assertAlmostEqual(0.1, o["threads_cores"]["gc"], places=6)
        self.assertAlmostEqual(50.0, o["class_busy_pct"]["Super"], places=6)
        self.assertAlmostEqual(0.0, o["class_busy_pct"]["Performance"], places=6)
        self.assertTrue(os.path.exists(os.path.join(d, osprobe.OS_JSON)))
        keys = {k for k, *_ in metrics.os_metrics(metrics.cached_os(d))}
        self.assertTrue({"os:topTier%", "os:runnable%", "os:GHz", "os:energy", "os:busy:Super", "os:cores:bench"} <= keys)

    def test_an_iteration_outside_the_samples_or_across_forks_is_skipped(self):
        ss = [sample(t, 7, t, 1.0, t, t, 0, 0, t, 1) for t in (0.0, 1.0, 2.0)] + \
             [sample(t, 8, t - 2, 1.0, t, t, 0, 0, t, 1) for t in (3.0, 4.0)]
        d = self.cell(ss, [("measure", 0.5, 1.5, 1), ("measure", 1.5, 3.5, 1), ("measure", 5.0, 6.0, 1)])
        its = osprobe.per_iteration(os.path.join(d, osprobe.OS_JSONL), os.path.join(d, "iterations.tsv"))
        self.assertEqual([0], [i["index"] for i in its])

    def test_no_samples_no_summary(self):
        d = self.cell([], [("measure", 0, 1, 1)])
        self.assertEqual({}, osprobe.summary(d))
        self.assertEqual([], metrics.os_metrics(metrics.cached_os(d)))

    def test_thread_groups_stay_monotonic_when_threads_exit(self):
        tt = osprobe.ThreadTotals()
        seq = [{1: ("jit", 100), 2: ("jit", 50)}, {1: ("jit", 150)}, {1: ("jit", 160), 3: ("jit", 10)}]
        orig = osprobe.threads
        try:
            vals = []
            for now in seq:
                osprobe.threads = lambda pid, now=now: now
                vals.append(tt.update(7)["jit"][0])
        finally:
            osprobe.threads = orig
        self.assertEqual([150, 200, 220], vals)

    @unittest.skipUnless(sys.platform == "darwin", "macOS")
    def test_live_sample_of_this_process(self):
        s = osprobe.sample(os.getpid())
        self.assertGreater(s["ru"]["instructions"], 0)
        self.assertGreater(s["ru"]["user_time"], 0)
        self.assertTrue(s["cl"])
        self.assertTrue(osprobe.core_classes())


if __name__ == "__main__":
    unittest.main()
