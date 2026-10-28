import json, os, re, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
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
    # corpus a: commit 0 and 4 over two rounds, 1 and 3 one round, 2 unmeasured; 4 is 20% faster than 3
    base = lambda x: [[x, x + 0.1, x - 0.1], [x + 0.05, x - 0.05, x]]
    alloc = lambda x: [[x, x], [x, x + 1]]
    cell("a", 0, 1, result("a", base(10.0), alloc(1e6)))
    cell("a", 0, 2, result("a", base(10.1), alloc(1e6)))
    cell("a", 1, 1, result("a", base(10.0), alloc(1e6)))
    cell("a", 3, 1, result("a", base(10.0), alloc(9e5)))
    cell("a", 4, 1, result("a", base(8.0), alloc(9e5)))
    cell("a", 4, 2, result("a", base(8.1), alloc(9e5)))
    cell("b", 0, 1, result("b", base(5.0), alloc(2e6)))
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

    def test_cells_mean_sd_ci_and_raw(self):
        a = branchview.branch_view(self.camp)["cells"]["a"]
        self.assertNotIn(self.v[2], a)  # unmeasured
        c0 = a[self.v[0]]
        self.assertEqual((c0["state"], c0["rounds"]), ("done", 2))
        mean, sd, ci, ok = c0["m"]["score"]
        self.assertAlmostEqual(mean, 10.05)
        self.assertAlmostEqual(sd, metrics.stats([10.0, 10.1])[1])
        samples = [x for r in (10.0, 10.1) for f in [[r, r + 0.1, r - 0.1], [r + 0.05, r - 0.05, r]] for x in f]
        self.assertAlmostEqual(ci, metrics.ci999(samples)[1])
        self.assertTrue(ok)
        self.assertEqual(len(c0["raw"]["score"]), 4)  # two forks of each of two rounds
        self.assertEqual(len(c0["raw"]["alloc"]), 4)
        self.assertIsNone(a[self.v[1]]["m"]["score"][1])  # one round: no sd over rounds
        self.assertEqual(c0["s"]["score"][0], "10.05")
        b = branchview.branch_view(self.camp)["cells"]["b"]
        self.assertEqual(b[self.v[2]], {"state": "running"})

    def test_delta_against_the_previous_measured_commit(self):
        a = branchview.branch_view(self.camp)["cells"]["a"]
        self.assertIsNone(a[self.v[0]]["prev"])
        self.assertEqual(a[self.v[0]]["d"], {})
        self.assertEqual(a[self.v[3]]["prev"], self.v[1])  # skipping the unmeasured commit
        d, spread, verdict = a[self.v[4]]["d"]["score"]
        self.assertAlmostEqual(d, 100 * (8.05 / 10.0 - 1))
        self.assertIsNotNone(spread)  # one round against two: the CIs combined
        self.assertEqual(verdict, "better")
        self.assertEqual(a[self.v[3]]["d"]["score"][2], "flat")
        self.assertAlmostEqual(a[self.v[3]]["d"]["alloc"][0], -10.0, places=3)


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
        self.assertLess(page.index("History"), page.index("Summary"))

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
