import os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from perflab import jvmevents


def rows(d):
    lines = open(os.path.join(d, "jvm-events.tsv")).read().splitlines()
    assert lines[0].split("\t") == jvmevents.HEADER
    return [l.split("\t") for l in lines[1:]]


class FromLogsTest(unittest.TestCase):
    def cell(self, files):
        d = tempfile.mkdtemp()
        for name, text in files.items():
            with open(os.path.join(d, name), "w") as f:
                f.write(text)
        return d

    SP = ('Safepoint "G1CollectForAllocation", Time since last: 270289209 ns, Reaching safepoint: 3250 ns, '
          'At safepoint: 5373416 ns, Leaving safepoint: 10792 ns, Total: 5387458 ns, Threads: 0 runnable, 22 total\n')

    def test_safepoint_with_wall_clock(self):
        d = self.cell({"safepoint.log": "[2026-11-15T20:00:00.000+1000][0.492s] " + self.SP})
        [(kind, s, e, what)] = rows(d) if jvmevents.from_logs(d) else []
        end = jvmevents.wall("2026-11-15T20:00:00.000+1000")
        self.assertEqual(kind, "vmop")
        self.assertAlmostEqual(float(e), end, places=3)
        self.assertAlmostEqual(float(s), end - 5.387458, places=3)
        self.assertEqual(what, "G1CollectForAllocation (reaching 3 µs, at 5373 µs)")

    def test_safepoint_uptime_only_takes_the_gc_logs_clock(self):
        # the fork's GC log says uptime 0.005 s is 19:59:37.515: the JVM started at .510
        d = self.cell({"safepoint.log": "[0.492s] " + self.SP,
                       "gc.log": "[2026-11-15T19:59:37.515+1000][0.005s] Using G1\n"})
        jvmevents.from_logs(d)
        [(_, _, e, _)] = rows(d)
        self.assertAlmostEqual(float(e), jvmevents.wall("2026-11-15T19:59:37.510+1000") + 492, places=3)

    def test_safepoint_uptime_only_without_gc_log_is_skipped(self):
        d = self.cell({"safepoint.log": "[0.492s] " + self.SP})
        jvmevents.from_logs(d)
        self.assertEqual(rows(d), [])

    def test_jit_events(self):
        d = self.cell({"jit-events-42.tsv": "epoch_ms\tkind\ttier\tosr\tcompile_ms\tmethod\n"
                                            "1000\tcompile\t3\t0\t0.500\ta.B.c\n"
                                            "2000\tcompile\t4\t1\t12.000\ta.B.d\n"
                                            "3000\tdeopt\t4\t0\t0.000\ta.B.d\n"})
        jvmevents.from_logs(d)
        self.assertEqual([r[0] for r in rows(d)], ["c1", "c2", "deopt"])
        c2 = rows(d)[1]
        self.assertEqual((float(c2[1]), float(c2[2]), c2[3]), (1988.0, 2000.0, "a.B.d (tier 4, OSR)"))

    def test_refresh_prefers_nothing_without_sources(self):
        d = self.cell({})
        jvmevents.refresh(d)
        self.assertFalse(os.path.exists(os.path.join(d, "jvm-events.tsv")))


if __name__ == "__main__":
    unittest.main()
