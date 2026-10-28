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
        self.assertEqual(b[self.v[2]], {"state": "running"})

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
