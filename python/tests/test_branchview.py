import json, os, re, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`, even when run alone
from perflab import branchview, config, index, metrics  # noqa: E402

SHAS = ["a" * 40, "b" * 40, "c" * 40, "d" * 40, "e" * 40]


def result(corpus, scores, allocs):
    """A JMH result.json entry: forks of measurement iterations of the score and of gc.alloc.rate.norm."""
    flat = [x for f in scores for x in f]
    aflat = [x for f in allocs for x in f]
    mean = sum(flat) / len(flat)
    return {"benchmark": "b.Bench.compile", "mode": "avgt", "jvmArgs": [], "params": {"corpus": corpus},
            "primaryMetric": {"score": mean, "scoreError": 0.1, "scoreUnit": "ms/op", "rawData": scores},
            "secondaryMetrics": {"gc.alloc.rate.norm": {"score": sum(aflat) / len(aflat), "scoreUnit": "B/op", "rawData": allocs}}}


def fixture(campaigns, name="br"):
    """A branch campaign of five commits (the fourth a merge of two), corpora a and b, some cells missing, one running."""
    camp = os.path.join(campaigns, name)
    os.makedirs(camp)
    commits = [{"sha": s, "short": s[:10], "variant": s[:10], "tree": "t" + s[:5], "parents": [SHAS[i - 1]] if i else [],
                "subject": f"Commit number {i}", "author": "Jason Zaugg", "date": f"2026-10-2{i}T10:00:00+02:00", "index": i,
                "merged": [{"sha": "f" * 40, "subject": "Inner one"}, {"sha": "9" * 40, "subject": "Inner two"}] if i == 3 else []}
               for i, s in enumerate(SHAS)]
    json.dump({"checkout": "/repo", "range": "base..tip", "firstParent": True, "base": SHAS[0], "tip": SHAS[-1], "commits": commits,
               "order": [c["variant"] for c in commits]}, open(os.path.join(camp, "branch.json"), "w"))
    json.dump({"name": name, "rounds": 2, "corpora": ["a", "b"], "variants": {c["variant"]: "" for c in commits}},
              open(os.path.join(camp, "spec.json"), "w"))
    def cell(corpus, i, rnd, r):
        d = os.path.join(camp, corpus, SHAS[i][:10], str(rnd))
        os.makedirs(d)
        with open(os.path.join(d, "result.json"), "w") as f:
            if r is not None:
                json.dump([r], f)
    # corpus a, two forks a round: commits 0, 3 and 4 over two rounds, 1 one round of one fork, 2 unmeasured; 4 is 20%
    # faster than 3. A fork's iterations average to x, its second fork's to x + 0.2.
    base = lambda x: [[x, x + 0.1, x - 0.1], [x + 0.2, x + 0.1, x + 0.3]]
    alloc = lambda x: [[x, x], [x, x + 1]]
    cell("a", 0, 1, result("a", base(10.0), alloc(1e6)))
    cell("a", 0, 2, result("a", base(10.1), alloc(1e6)))
    cell("a", 1, 1, result("a", base(10.0)[:1], alloc(1e6)[:1]))
    cell("a", 3, 1, result("a", base(10.0), alloc(9e5)))
    cell("a", 3, 2, result("a", base(10.0), alloc(9e5)))
    cell("a", 4, 1, result("a", base(8.0), alloc(9e5)))
    cell("a", 4, 2, result("a", base(8.1), alloc(9e5)))
    # corpus b: one fork per commit, so nothing to pool
    cell("b", 0, 1, result("b", base(5.0)[:1], alloc(2e6)[:1]))
    cell("b", 1, 1, result("b", base(5.5)[:1], alloc(2e6)[:1]))
    cell("b", 2, 1, None)  # running: JMH writes result.json when the fork ends
    # a profdiff of two of its commits
    os.makedirs(os.path.join(camp, f"diff-{SHAS[3][:10]}-{SHAS[4][:10]}"))
    open(os.path.join(camp, f"diff-{SHAS[3][:10]}-{SHAS[4][:10]}", "compare.html"), "w").close()
    return camp


class Project:
    def __init__(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, "perflab.toml"), "w") as f:
            f.write('[build]\njmh = "x"\n')
        config._config = config.find(self.dir)


class CiTest(unittest.TestCase):
    def test_t_table(self):
        self.assertAlmostEqual(metrics.t999(1), 636.62)
        self.assertAlmostEqual(metrics.t999(10), 4.587)
        self.assertTrue(4.587 > metrics.t999(11) > 4.318)
        self.assertAlmostEqual(metrics.t999(10 ** 9), 3.291, places=2)

    def test_ci_of_samples(self):
        mean, h = metrics.ci999([1.0, 2.0, 3.0])
        self.assertEqual(mean, 2.0)
        self.assertAlmostEqual(h, 31.599 * 1.0 / 3 ** 0.5)
        self.assertEqual(metrics.ci999([1.0]), (1.0, None))

    def test_welch_by_hand(self):
        # va = 1/4, vb = 4/4; df = 1.25^2 / (0.25^2/3 + 1/3) = 4.4118; t999 between 4 (8.610) and 5 (6.869), in 1/df
        d, half, df = metrics.welch((10.0, 1.0, 4, 3), (12.0, 2.0, 4, 3))
        self.assertAlmostEqual(d, 20.0)
        self.assertAlmostEqual(df, 1.5625 / (0.0625 / 3 + 1 / 3))
        t = 8.610 + (1 / 4 - 1 / df) / (1 / 4 - 1 / 5) * (6.869 - 8.610)
        self.assertAlmostEqual(half, 100 * t * 1.25 ** 0.5 / 10)
        self.assertAlmostEqual(half, 87.18, places=1)  # not significant: |20| < 87
        self.assertEqual(metrics.welch((10.0, None, 1, None), (12.0, 1.0, 4, 3))[1:], (None, None))
        # a one-sided pool (df 9) against a commit's own forks
        d, half, df = metrics.welch((10.0, 0.1, 1, 9), (9.0, 0.1, 4, 3))
        va, vb = 0.01, 0.0025
        self.assertAlmostEqual(df, (va + vb) ** 2 / (va ** 2 / 9 + vb ** 2 / 3))
        self.assertAlmostEqual(half, 100 * metrics.t999(df) * (va + vb) ** 0.5 / 10)

    def test_pooled_rel_sd(self):
        r, df = metrics.pooled_rel_sd([(10.0, 1.0, 3), (20.0, 4.0, 1), (5.0, None, 0), (7.0, 0.0, 0)])
        self.assertEqual(df, 4)
        self.assertAlmostEqual(r, ((3 * 0.01 + 1 * 0.04) / 4) ** 0.5)
        self.assertEqual(metrics.pooled_rel_sd([(5.0, None, 0)]), (None, 0))


class BranchViewTest(unittest.TestCase):
    def setUp(self):
        Project()
        self.camp = fixture(config.get().campaigns)
        self.v = [s[:10] for s in SHAS]

    def test_no_branch_json_no_view(self):
        os.remove(os.path.join(self.camp, "branch.json"))
        self.assertIsNone(branchview.branch_view(self.camp))

    def test_commits_newest_first_with_merges(self):
        d = branchview.branch_view(self.camp)
        self.assertEqual([c["v"] for c in d["commits"]], self.v[::-1])
        self.assertEqual([c["index"] for c in d["commits"]], [4, 3, 2, 1, 0])
        self.assertEqual(len(d["commits"][1]["merged"]), 2)
        self.assertEqual(d["commits"][0]["shown"], "Sat 24 Oct 2026")
        self.assertEqual(d["corpora"], ["a", "b"])
        self.assertEqual(d["metrics"][0]["k"], "score")
        self.assertIn("alloc", [m["k"] for m in d["metrics"]])
        self.assertEqual(d["diffs"], [{"name": f"{self.v[3]}-{self.v[4]}", "href": f"diff-{self.v[3]}-{self.v[4]}/compare.html",
                                       "a": self.v[3], "b": self.v[4]}])

    def test_cells_are_over_forks(self):
        a = branchview.branch_view(self.camp)["cells"]["a"]
        self.assertNotIn(self.v[2], a)  # unmeasured
        c0 = a[self.v[0]]
        self.assertEqual((c0["state"], c0["rounds"], c0["forks"]), ("done", 2, 4))
        # the forks' means: 10.0, 10.2 (round 1) and 10.1, 10.3 (round 2)
        mean, sd, ci, ok, n, df, pooled = c0["m"]["score"]
        self.assertAlmostEqual(mean, 10.15)
        self.assertAlmostEqual(sd, (0.05 / 3) ** 0.5)  # deviations .15, .05, .05, .15
        self.assertEqual((n, df, pooled), (4, 3, False))
        self.assertAlmostEqual(ci, 12.924 * (0.05 / 3) ** 0.5 / 2)
        self.assertTrue(ok)
        self.assertEqual(len(c0["raw"]["score"]), 4)  # every iteration kept, by fork
        self.assertEqual(len(c0["raw"]["alloc"]), 4)
        self.assertEqual(c0["s"]["score"][0], "10.15")
        b = branchview.branch_view(self.camp)["cells"]["b"]
        self.assertEqual(b[self.v[2]], {"state": "running", "rd": [{"round": 1, "state": "running", "links": {}}]})

    def test_one_fork_takes_the_pooled_spread(self):
        a = branchview.branch_view(self.camp)["cells"]["a"]
        mean, sd, ci, _, n, df, pooled = a[self.v[1]]["m"]["score"]
        # relative variances of commits 0, 3 and 4, each with 3 df, pooled
        r2 = ((0.05 / 3) / 10.15 ** 2 + (0.04 / 3) / 10.1 ** 2 + (0.05 / 3) / 8.15 ** 2) / 3
        self.assertEqual((mean, n, df, pooled), (10.0, 1, 9, True))
        self.assertAlmostEqual(sd, 10.0 * r2 ** 0.5)
        self.assertAlmostEqual(ci, metrics.t999(9) * 10.0 * r2 ** 0.5)
        self.assertNotEqual(a[self.v[1]]["s"]["score"][1], "")

    def test_one_fork_and_nothing_to_pool_has_no_spread(self):
        b = branchview.branch_view(self.camp)["cells"]["b"]
        self.assertEqual(b[self.v[0]]["m"]["score"][1:3], [None, None])
        self.assertEqual(b[self.v[0]]["s"]["score"][1], "")
        d, half, verdict, _ = b[self.v[1]]["d"]["score"]
        self.assertAlmostEqual(d, 10.0)
        self.assertEqual((half, verdict), (None, "flat"))  # uncoloured: no spread yet

    def test_delta_is_welch_over_fork_means(self):
        a = branchview.branch_view(self.camp)["cells"]["a"]
        self.assertIsNone(a[self.v[0]]["prev"])
        self.assertEqual(a[self.v[0]]["d"], {})
        self.assertEqual(a[self.v[3]]["prev"], self.v[1])  # skipping the unmeasured commit
        # 4 against 3: forks 8.0, 8.2, 8.1, 8.3 against 10.0, 10.2, 10.0, 10.2
        va, vb = (0.04 / 3) / 4, (0.05 / 3) / 4
        df = (va + vb) ** 2 / (va ** 2 / 3 + vb ** 2 / 3)
        d, half, verdict, pooled = a[self.v[4]]["d"]["score"]
        self.assertAlmostEqual(d, 100 * (8.15 / 10.1 - 1))
        self.assertAlmostEqual(half, 100 * metrics.t999(df) * (va + vb) ** 0.5 / 10.1)
        self.assertAlmostEqual(df, 5.927, places=3)
        self.assertEqual((verdict, pooled), ("better", False))
        # 3 against 1, one fork with the pooled sd and its 9 df
        sd1 = a[self.v[1]]["m"]["score"][1]
        va, vb = sd1 ** 2, (0.04 / 3) / 4
        df = (va + vb) ** 2 / (va ** 2 / 9 + vb ** 2 / 3)
        d, half, verdict, pooled = a[self.v[3]]["d"]["score"]
        self.assertAlmostEqual(d, 1.0)
        self.assertAlmostEqual(half, 100 * metrics.t999(df) * (va + vb) ** 0.5 / 10.0)
        self.assertEqual((verdict, pooled), ("flat", True))
        self.assertAlmostEqual(a[self.v[3]]["d"]["alloc"][0], -10.0, places=3)

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_page_computes_the_same_deltas(self):
        out = page_deltas(self, branchview.branch_view(self.camp)["cells"])
        self.assertIn("a|" + self.v[4] + "|score", out)


def page_deltas(t, cells):
    """Check that the page's `welch` (as the comparison panel uses it) gives each cell's Δ column; the page's Δs."""
    js = branchview.STATS_JS + (f"const cells = {json.dumps(cells)};\nconst out = {{}};\n"
                                "for (const [c, vs] of Object.entries(cells)) for (const [v, x] of Object.entries(vs))\n"
                                "  for (const k of Object.keys(x.d || {})) out[c + '|' + v + '|' + k] = BH_STATS.welch(vs[(x.pv || {})[k] || x.prev].m[k], x.m[k]);\n"
                                "console.log(JSON.stringify(out));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    t.assertEqual(r.returncode, 0, r.stderr)
    out = json.loads(r.stdout)
    expected = {f"{c}|{v}|{k}": d for c, vs in cells.items() for v, x in vs.items() for k, d in x.get("d", {}).items()}
    t.assertEqual(out.keys(), expected.keys())
    for key, (d, half, verdict, pooled) in expected.items():
        jd, jhalf, jverdict, jpooled = out[key]
        t.assertAlmostEqual(jd, d, msg=key)
        t.assertEqual(jhalf is None, half is None, key)
        if half is not None:
            t.assertAlmostEqual(jhalf, half, msg=key)
        t.assertEqual((jverdict, jpooled), (verdict, pooled), key)
    return out


def iterations(cell, forks, t0=1_000_000):
    """An iterations.tsv for a cell of `forks` forks, each a warmup then its measurement iterations (as many as
    rawData's), every iteration 1 s, the index running on over the forks as JMH's do; [(index, start, end)] of the
    measurement iterations."""
    rows, out, i, t = ["index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\tpid\tunit\talloc_bytes"], [], 0, t0 * 1000
    for f, n in enumerate(forks):
        for kind in ["warmup"] + ["measure"] * n:
            rows.append(f"{i}\t{kind}\t\t{t}\t{t + 1000}\t1.0\t1\t\t{100 + f}\tms/op\t")
            if kind == "measure":
                out.append((i, t / 1000, t / 1000 + 1))
            i, t = i + 1, t + 1000
    open(os.path.join(cell, "iterations.tsv"), "w").write("\n".join(rows) + "\n")
    return out


class WithinForkTest(unittest.TestCase):
    """Each fork's 99.9% CI over its own iterations, and how it compares with the spread between forks."""
    def setUp(self):
        Project()
        self.camp = fixture(config.get().campaigns)
        self.v = [s[:10] for s in SHAS]
        self.d = branchview.branch_view(self.camp)

    def test_within_by_hand(self):
        # x, x + .1, x - .1: sd .1 over 3 iterations, t999(2) = 31.599
        h, se = branchview.within([10.0, 10.1, 9.9])
        self.assertAlmostEqual(se, 0.1 / 3 ** 0.5)
        self.assertAlmostEqual(h, 31.599 * 0.1 / 3 ** 0.5)
        self.assertEqual(branchview.within([1.0]), (None, None))

    def test_one_fork_and_nothing_pooled_has_its_within_ci(self):
        b0 = self.d["cells"]["b"][self.v[0]]
        self.assertIsNone(b0["m"]["score"][2])  # no interval over forks
        ciw, ratio, shown = b0["w"]["score"]
        self.assertAlmostEqual(ciw, 31.599 * 0.1 / 3 ** 0.5)  # 1.824
        self.assertIsNone(ratio)  # nothing between forks to compare with
        self.assertEqual(shown, "2")  # to the score's decimals, as its mean "5" is shown
        self.assertEqual(b0["wf"]["score"], [1.82])
        # and it never colours a Δ: commit 1's against it stays uncoloured
        self.assertEqual(self.d["cells"]["b"][self.v[1]]["d"]["score"][1:3], [None, "flat"])

    def test_between_within_ratio(self):
        c0 = self.d["cells"]["a"][self.v[0]]
        # forks' means 10.0, 10.2, 10.1, 10.3 (sd √(.05/3)); every fork's iterations have sd .1 over 3: se .1/√3
        ciw, ratio, _ = c0["w"]["score"]
        self.assertAlmostEqual(ratio, (0.05 / 3) ** 0.5 / (0.1 / 3 ** 0.5))  # √.05/.1 = 2.236
        self.assertAlmostEqual(ciw, 31.599 * 0.1 / 3 ** 0.5)  # every fork's the same: their root mean square
        self.assertEqual(len(c0["wf"]["score"]), 4)
        # one fork, with the pooled sd: the ratio is against the pooled spread
        a1 = self.d["cells"]["a"][self.v[1]]
        self.assertAlmostEqual(a1["w"]["score"][1], a1["m"]["score"][1] / (0.1 / 3 ** 0.5))

    def test_rounds_list_their_forks(self):
        rd = self.d["cells"]["a"][self.v[0]]["rd"]
        self.assertEqual([(r["round"], r["state"]) for r in rd], [(1, "done"), (2, "done")])
        self.assertEqual([f["mean"] for f in rd[0]["forks"]], [10.0, 10.2])
        self.assertEqual(rd[0]["forks"][0], {"mean": 10.0, "ci": 1.82, "n": 3})


class LoadTest(unittest.TestCase):
    """Competing load per measurement iteration: from load.json, else from load.tsv; on the chart's dots and the cells."""
    def setUp(self):
        Project()
        self.camp = fixture(config.get().campaigns)
        self.v = [s[:10] for s in SHAS]

    def cell(self, i, rnd, corpus="a"):
        return os.path.join(self.camp, corpus, self.v[i], str(rnd))

    def test_the_constants_are_abs(self):
        from perflab import ab
        self.assertEqual(branchview.LOAD_CHECK, ab.LOAD_CHECK)

    def test_load_json(self):
        cell = self.cell(0, 1)
        its = iterations(cell, [3, 3])  # indices 1-3 (fork 1) and 5-7 (fork 2)
        json.dump({"maxCores": 1.5, "iterations": [{"index": i, "start": a, "end": b, "score": 1.0, "cores": 2.4 if i == 6 else 0.3,
                                                    "top": "java 2.2" if i == 6 else ""} for i, a, b in its],
                   "disturbed": [6]}, open(os.path.join(cell, "load.json"), "w"))
        x = branchview.branch_view(self.camp)["cells"]["a"][self.v[0]]
        r1 = x["rd"][0]
        self.assertEqual(r1["disturbed"], [{"i": 6, "fork": 2, "j": 2, "cores": 2.4, "top": "java 2.2"}])
        self.assertEqual((r1["load"], r1["maxCores"]), (2.4, 1.5))
        self.assertEqual(x["hot"], [[1, 1]])  # round 1's second fork, its second iteration
        self.assertNotIn("disturbed", x["rd"][1])
        self.assertNotIn("load", x["rd"][1])

    def test_load_tsv_of_an_older_cell(self):
        # round 2 of commit 4: its forks are the third and fourth of the commit's raw
        cell = self.cell(4, 2)
        its = iterations(cell, [3, 3])
        end = its[2][2]  # the last iteration of the first fork, index 3
        # samples of 5 s without the window column (as before it), and one of 2 s with it; the spec has no maxCores: 1.5
        open(os.path.join(cell, "load.tsv"), "w").write(f"{its[0][2]:.1f}\t0.40\tWindowServer 0.2\n{end:.1f}\t1.90\tjava 1.7, Python 0.1\n"
                                                         f"{its[5][2]:.1f}\t0.20\tx 0.1\t2\n")
        mc, rows, dist = branchview.cell_load(cell, 1.5)
        self.assertEqual(mc, 1.5)
        # the 5 s sample ending with index 3 covers 1-3 (and the warmup); the 2 s one the last iteration only
        self.assertEqual([r["index"] for r in rows], [1, 2, 3, 5, 6, 7])
        self.assertEqual(dist, [1, 2, 3])
        x = branchview.branch_view(self.camp)["cells"]["a"][self.v[4]]
        r2 = x["rd"][1]
        self.assertEqual([(z["i"], z["fork"], z["j"], z["cores"]) for z in r2["disturbed"]], [(1, 1, 1, 1.9), (2, 1, 2, 1.9), (3, 1, 3, 1.9)])
        self.assertEqual(r2["disturbed"][0]["top"], "java 1.7, Python 0.1")
        self.assertEqual(x["hot"], [[2, 0], [2, 1], [2, 2]])
        # the spec's own limit
        spec = json.load(open(os.path.join(self.camp, "spec.json")))
        json.dump({**spec, "loadgate": {"maxCores": 2.0}}, open(os.path.join(self.camp, "spec.json"), "w"))
        self.assertNotIn("hot", branchview.branch_view(self.camp)["cells"]["a"][self.v[4]])

    def test_iterations_by_order_when_the_pids_do_not_match(self):
        cell = self.cell(0, 1)
        iterations(cell, [6])  # one pid for what rawData has as two forks of 3
        self.assertEqual(branchview.iteration_forks(cell, [3, 3]), {1: (0, 0), 2: (0, 1), 3: (0, 2), 4: (1, 0), 5: (1, 1), 6: (1, 2)})
        self.assertEqual(branchview.iteration_forks(cell, [3, 2]), {})  # neither matches: none placed


class VoidTest(unittest.TestCase):
    """Voided cells, under <campaign>/.void/: listed with their reason, counted for nothing."""
    def setUp(self):
        Project()
        self.camps = config.get().campaigns
        self.camp = fixture(self.camps)
        self.v = [s[:10] for s in SHAS]

    def void(self, corpus, i, rnd, why, scores):
        d = os.path.join(self.camp, ".void", corpus, self.v[i], f"{rnd}-20261029-095244")
        os.makedirs(d)
        json.dump([result(corpus, scores, [[1.0] * len(f) for f in scores])], open(os.path.join(d, "result.json"), "w"))
        open(os.path.join(d, "void.txt"), "w").write(why + "\n")
        open(os.path.join(d, "jmh.log"), "w").write("log")
        return d

    def test_listed_and_excluded(self):
        before = branchview.branch_view(self.camp)["cells"]["a"][self.v[0]]["m"]["score"]
        self.void("a", 0, 1, "other load up to 1.6 cores over iterations 17 and 18", [[50.0, 50.0]])
        self.void("a", 2, 1, "disturbed by other load", [[50.0, 50.0]])
        d = branchview.branch_view(self.camp, self.camps)
        self.assertNotIn(".void", d["corpora"])
        a0 = d["cells"]["a"][self.v[0]]
        self.assertEqual(a0["m"]["score"], before)  # its 50s count for nothing
        self.assertEqual(a0["rounds"], 2)
        self.assertEqual(a0["void"], [{"round": 1, "when": "Thu 29 Oct 09:52", "why": "other load up to 1.6 cores over iterations 17 and 18",
                                       "links": {"jmh": f"br/.void/a/{self.v[0]}/1-20261029-095244/jmh.log"}}])
        # an unmeasured commit with only a voided cell: a cell of its own, with no score
        a2 = d["cells"]["a"][self.v[2]]
        self.assertEqual((a2["state"], a2["void"][0]["why"]), ("none", "disturbed by other load"))
        self.assertNotIn("m", a2)
        self.assertEqual(d["cells"]["a"][self.v[3]]["prev"], self.v[1])  # still skipped as unmeasured

    def test_popover_data_of_a_round(self):
        cell = os.path.join(self.camp, "a", self.v[0], "1")
        for f in ("timeline.html", "jmh.log", "build.log"):
            open(os.path.join(cell, f), "w").write("x")
        failed = os.path.join(self.camp, "b", self.v[3], "1")
        os.makedirs(failed)
        open(os.path.join(failed, "failed.txt"), "w").write("JMH exited with 1\n")
        d = branchview.branch_view(self.camp, self.camps)
        r1 = d["cells"]["a"][self.v[0]]["rd"][0]
        self.assertEqual(r1["links"], {"timeline": f"br/a/{self.v[0]}/1/timeline.html", "jmh": f"br/a/{self.v[0]}/1/jmh.log",
                                       "build": f"br/a/{self.v[0]}/1/build.log"})
        f = d["cells"]["b"][self.v[3]]
        self.assertEqual((f["state"], f["rd"]), ("failed", [{"round": 1, "state": "failed", "why": "JMH exited with 1", "links": {}}]))

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_page_renders_the_popover(self):
        self.void("a", 0, 1, "disturbed <by> load", [[50.0, 50.0]])
        cell = os.path.join(self.camp, "a", self.v[0], "1")
        open(os.path.join(cell, "timeline.html"), "w").write("x")
        its = iterations(cell, [3, 3])
        json.dump({"maxCores": 1.5, "iterations": [{"index": i, "start": a, "end": b, "score": 1.0, "cores": 2.4 if i == 6 else 0.3, "top": "java 2.2"}
                                                   for i, a, b in its], "disturbed": [6]}, open(os.path.join(cell, "load.json"), "w"))
        # round 2: two neighbours of a fork disturbed, shown as one run
        cell2 = os.path.join(self.camp, "a", self.v[0], "2")
        its = iterations(cell2, [3, 3])
        json.dump({"maxCores": 1.5, "iterations": [{"index": i, "start": a, "end": b, "score": 1.0, "cores": {1: 1.7, 2: 2.1}.get(i, 0.2),
                                                    "top": "java" if i == 2 else "x"} for i, a, b in its], "disturbed": [1, 2]},
                  open(os.path.join(cell2, "load.json"), "w"))
        d = branchview.branch_view(self.camp, self.camps)
        out = page_popover(self, d, self.v[0])
        self.assertIn("iterations 1–2 (fork 1, measurements 1–2): up to 2.1 cores <span class=\"k\">java</span>", out["0"])
        for server in ("0", "1"):
            h = out[server]
            self.assertIn("voided: <span class=\"why\">disturbed &lt;by&gt; load</span>", h)
            self.assertIn('data-lb="timeline"', h)
            self.assertIn("iteration 6 (fork 2, measurement 2): 2.4 cores", h)
            self.assertIn("fork 2: <b>10.2</b> <span class=\"pm\">± 1.8</span>", h)  # round 1's, ± within it (1.82)
            self.assertEqual(h.count("<li"), 3)  # two rounds and the voided one
        self.assertNotIn("data-bvopen", out["0"])
        self.assertEqual(out["1"].count("data-bvopen"), 2)  # a Void & rerun per round, on the server
        self.assertIn("Served by <code>perflab server</code>", out["0"])


def page_popover(t, d, v):
    """The page's popover for `v` on corpus a, off the server and on it: {"0": html, "1": html}, in node with a stub DOM."""
    stub = ("globalThis.document = {querySelector: () => null, querySelectorAll: () => [], addEventListener() {}};"
            "globalThis.addEventListener = () => {}; globalThis.location = {pathname: '/', search: ''};\n")
    js = stub + branchview.JS + (f"\nconst d = {json.dumps(d)};\n"
                                 f"console.log(JSON.stringify({{0: BH.popover(d, 'br', 'a', {json.dumps(v)}, false), 1: BH.popover(d, 'br', 'a', {json.dumps(v)}, true)}}));")
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    t.assertEqual(r.returncode, 0, r.stderr)
    return json.loads(r.stdout)


def add_xctrace(cell, cycles, profile="xctrace:ipc"):
    """Give a cell's result an xctrace profile's counters, per fork as its score's rawData: cycles, instructions at an
    IPC of 2, IPC, and an L1D miss counter with its per-kinst form; and the profile it ran under."""
    f = os.path.join(cell, "result.json")
    [r] = json.load(open(f))
    raw = [[cycles * (1 + 0.01 * j) for _ in fork] for j, fork in enumerate(r["primaryMetric"]["rawData"])]
    mean = lambda raw: sum(x for f in raw for x in f) / sum(len(f) for f in raw)
    ins = [[2 * x for x in f] for f in raw]
    r["secondaryMetrics"].update({
        "xctrace.CORE_ACTIVE_CYCLE": {"score": mean(raw), "scoreUnit": "#/op", "rawData": raw},
        "xctrace.INST_ALL": {"score": mean(ins), "scoreUnit": "#/op", "rawData": ins},
        "xctrace.IPC.bench": {"score": 2.0, "scoreUnit": "insts/cycle"},
        "xctrace.L1D_CACHE_MISS_LD": {"score": cycles / 1000, "scoreUnit": "#/op"},
        "xctrace.L1D_CACHE_MISS_LD/kinst": {"score": 0.5, "scoreUnit": "#/kinst"}})
    json.dump([r], open(f, "w"))
    open(os.path.join(cell, "profile.txt"), "w").write(profile + "\n")


class ProfiledCampaignTest(unittest.TestCase):
    """A branch campaign measured under a profile: its cells' counters are metrics of the view, and an async profile's
    flame graphs are linked from its rows."""
    def setUp(self):
        Project()
        self.camps = config.get().campaigns
        self.camp = fixture(self.camps)
        self.v = [s[:10] for s in SHAS]
        for i, rnd, cyc in [(0, 1, 1e9), (0, 2, 1e9), (3, 1, 1.1e9), (3, 2, 1.1e9), (4, 1, 9e8), (4, 2, 9e8)]:
            add_xctrace(os.path.join(self.camp, "a", self.v[i], str(rnd)), cyc)

    def test_every_metric_of_the_cells_is_in_the_view(self):
        d = branchview.branch_view(self.camp, self.camps)
        keys = [m["k"] for m in d["metrics"]]
        for k in ("score", "cycles", "instructions", "ipc", "alloc", "ev:L1D_CACHE_MISS_LD", "ev:L1D_CACHE_MISS_LD/kinst"):
            self.assertIn(k, keys)
        self.assertFalse([m for m in d["metrics"] if m.get("src")])  # none from a profile pass: there is none
        a = d["cells"]["a"]
        c3, c4 = a[self.v[3]], a[self.v[4]]
        self.assertEqual(c3["m"]["cycles"][4], 4)  # over forks, from rawData
        self.assertEqual(len(c3["raw"]["cycles"]), 4)
        self.assertEqual(c3["m"]["ipc"][4], 2)  # no rawData: a value per round
        # commit 1 has no counters: 3's Δ of cycles is against 0, the latest commit with them
        self.assertEqual(c3["prev"], self.v[1])
        self.assertEqual(c3["pv"]["cycles"], self.v[0])
        self.assertAlmostEqual(c3["d"]["cycles"][0], 10.0, places=6)
        self.assertNotIn("pv", c4)
        self.assertAlmostEqual(c4["d"]["cycles"][0], 100 * (9 / 11 - 1), places=6)
        self.assertEqual(c4["d"]["cycles"][2], "better")
        self.assertNotIn("graphs", c3)  # xctrace: no flame graphs
        if shutil.which("node"):
            self.assertIn(f"a|{self.v[3]}|cycles", page_deltas(self, d["cells"]))

    def test_an_async_campaign_links_its_cells_graphs(self):
        for rnd in (1, 2):
            cell = os.path.join(self.camp, "a", self.v[4], str(rnd))
            open(os.path.join(cell, "profile.txt"), "w").write("async:cpu,alloc\n")
            open(os.path.join(cell, "rec.jfr"), "w").write("jfr")
            for ev in ("cpu", "alloc"):
                open(os.path.join(cell, f"rec-{ev}.html"), "w").write("<html>")
        g = branchview.branch_view(self.camp, self.camps)["cells"]["a"][self.v[4]]["graphs"]
        self.assertEqual(g[0], ["cpu #1", "bench", f"br/a/{self.v[4]}/1/rec-cpu.html"])
        self.assertEqual([x[0] for x in g], ["cpu #1", "alloc #1", "cpu #2", "alloc #2"])


class BranchIndexTest(unittest.TestCase):
    def setUp(self):
        Project()
        self.camps = config.get().campaigns
        fixture(self.camps)

    def page(self):
        return open(index.build(self.camps)).read()

    def test_branch_card_has_its_history(self):
        page = self.page()
        self.assertIn('<div class="bh" data-campaign="br">', page)
        blob = re.search(r'<div class="bh" data-campaign="br">.*?<script type="application/json">(.*?)</script>', page, re.S).group(1)
        self.assertEqual(len(json.loads(blob)["commits"]), 5)
        # the history is the first of the summary's views, and the one shown first
        card = page[page.index('id="c-br"'):]
        self.assertLess(card.index('data-sv="history"'), card.index('data-sv="table"'))
        self.assertLess(card.index('class="sv-hist"'), card.index('class="summ"'))

    def test_a_branch_campaign_shows_before_any_cell(self):
        shutil.rmtree(os.path.join(self.camps, "br", "a"))
        shutil.rmtree(os.path.join(self.camps, "br", "b"))
        self.assertIn('data-campaign="br"', self.page())

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_scripts_parse(self):
        page = self.page()
        for i, js in enumerate(re.findall(r"<script>(.*?)</script>", page, re.S)):
            f = os.path.join(config.get().root, f"s{i}.js")
            open(f, "w").write(js)
            r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
