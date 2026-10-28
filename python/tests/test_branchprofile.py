import json, os, re, shutil, subprocess, sys, tempfile, time, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`, even when run alone
from perflab import ab, branch, branchprofile, branchview, config, index, jmh, launch  # noqa: E402
from test_branch import git, repo_with_history  # noqa: E402
from test_branchview import SHAS, Project as ViewProject, fixture, result  # noqa: E402
from test_perflab import Project  # noqa: E402


def fake_profile_cell(d, corpus="a"):
    """A profile cell: its result, its profile, a recording and its bench graphs."""
    os.makedirs(d, exist_ok=True)
    json.dump([result(corpus, [[10.0, 10.1]], [[1e6, 1e6]])], open(os.path.join(d, "result.json"), "w"))
    open(os.path.join(d, "profile.txt"), "w").write("async:cpu,alloc\n")
    open(os.path.join(d, "rec.jfr"), "w").write("jfr")
    for ev in ("cpu", "alloc"):
        open(os.path.join(d, f"rec-{ev}.html"), "w").write("<html>")


def stub_profdiff(calls):
    """profdiff's outputs for an event, as profdiff and compare.write would name them."""
    def run(argv):
        ev, a, b, out = argv[1], argv[-3], argv[-2], argv[-1]
        calls.append((ev, a, b))
        for f in (f"a-{ev}.html", f"diff-{ev}.html", f"diff-{ev}-inverse.html", f"b-{ev}.html", "compare.html"):
            open(os.path.join(out, f), "w").write("<html>")
    return run


class ProfileCampaignTest(unittest.TestCase):
    """`perflab branch profile` over a real (tiny) branch, the JMH runs stubbed as test_branch does."""
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.base, self.tip = repo_with_history(self.repo)
        self.p = Project('[build]\njmh = "true {args}"\nlaunch = "python3 build.py {out}"\n[benchmark]\ncorpus = "c"\n')
        with open(os.path.join(self.p.dir, "build.py"), "w") as f:
            f.write("import json, os, subprocess, sys\n"
                    "co = os.environ['CO']\n"
                    "sha = subprocess.run(['git', '-C', co, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()\n"
                    "out = os.path.join(sys.argv[1], 'classes'); os.makedirs(out, exist_ok=True); open(out + '/A.class', 'w').write(sha)\n"
                    "json.dump({'mainClass': 'M', 'java': 'java', 'roots': [out], 'classpath': [out],"
                    " 'build': {'checkout': co, 'commit': sha, 'dirty': False}}, open(os.path.join(sys.argv[1], 'launch.json'), 'w'))\n")
        os.chdir(self.p.dir)
        self.addCleanup(os.environ.pop, "PERFLAB_BUILD_MODE", None)
        self.spec_f = os.path.join(self.p.dir, "s.json")
        with open(self.spec_f, "w") as f:
            json.dump({"name": "br", "benchmark": "B", "rounds": 1, "corpora": {"x": "-i 9", "y": ""}, "jvmArgs": "-Xmx1G",
                       "branch": {"checkout": self.repo, "range": f"{self.base}..main", "env": {"CO": "{checkout}"}},
                       "profiles": {"jmhArgs": "-i 2"}}, f)
        self.events = []
        orig = jmh.run_build

        def stub(cmd, log, *a, **k):
            if "build.py" in cmd:
                self.events.append(("build", None))
                return orig(cmd, log, *a, **k)
            self.events.append(("cell", os.path.dirname(log), cmd))
            fake_profile_cell(os.path.dirname(log), "x")
            return 0
        for mod, name, value in [(jmh, "run_build", stub), (ab, "check", lambda *a, **k: None),
                                 (jmh, "finish", lambda *a, **k: None), (index, "rebuild", lambda *a, **k: None),
                                 (ab, "set_running", lambda *a, **k: None)]:
            self.addCleanup(setattr, mod, name, getattr(mod, name))
            setattr(mod, name, value)
        self.calls = []
        self.addCleanup(setattr, branchprofile, "run_profdiff", branchprofile.run_profdiff)
        branchprofile.run_profdiff = stub_profdiff(self.calls)

    def measure(self, n):
        """The branch campaign's first `n` cells, so their commits are built."""
        spec = ab.Spec(self.spec_f)
        cells = list(spec.cells())[:n]
        spec.cells = lambda: iter(cells)
        ab.run(spec, False)
        return spec

    def test_profiles_reuse_the_branch_campaigns_builds(self):
        spec = self.measure(1)  # builds the base
        b = spec.branch_info
        base, tip = b["commits"][0]["variant"], b["commits"][-1]["variant"]
        self.events.clear()
        self.assertEqual(branchprofile.main(["profile", self.spec_f, self.base[:8], "main"]), 0)
        # the base is built already; only the tip is built, into the branch campaign's builds
        self.assertEqual([e[0] for e in self.events], ["cell", "build", "cell"])
        out = os.path.join(config.get().campaigns, "br.profile")
        self.assertEqual([os.path.relpath(e[1], out) for e in self.events if e[0] == "cell"], [f"x/{base}/1", f"x/{tip}/1"])
        args = open(os.path.join(self.events[0][1], "jmh.args")).read().split("\n")
        self.assertIn("-i\n2", "\n".join(args))  # the profiles' JMH arguments
        self.assertTrue(any(a.startswith("async:") and "event=cpu" in a for a in args), args)
        builds = os.listdir(os.path.join(spec.out, launch.BUILD_DIR))
        self.assertEqual(len(builds), 2)
        self.assertFalse(os.path.exists(os.path.join(out, launch.BUILD_DIR)))
        self.assertFalse(os.path.exists(os.path.join(out, branch.BRANCH)))  # it is not a branch campaign itself
        ps = json.load(open(os.path.join(out, "spec.json")))
        self.assertEqual((ps["profileOf"], ps["profile"], ps["rounds"], ps["corpora"], ps["jvmArgs"]),
                         ("br", "async:cpu,alloc", 1, {"x": "-i 2"}, "-Xmx1G"))
        self.assertEqual(list(ps["variants"]), [base, tip])
        # more commits add to the campaign; those done are not run again
        self.events.clear()
        mid = b["commits"][1]["variant"]
        branchprofile.main(["profile", self.spec_f, mid, base])
        self.assertEqual([os.path.relpath(e[1], out) for e in self.events if e[0] == "cell"], [f"x/{mid}/1"])
        self.assertEqual(list(json.load(open(os.path.join(out, "spec.json")))["variants"]), [base, mid, tip])

    def test_diff_cached_by_its_pair_of_cells(self):
        # before the branch campaign has run: `profile` resolves its range
        branchprofile.main(["profile", self.spec_f, self.base, self.tip, "--diff"])
        b = json.load(open(os.path.join(config.get().campaigns, "br", branch.BRANCH)))
        base, tip = b["commits"][0]["variant"], b["commits"][-1]["variant"]
        out = os.path.join(config.get().campaigns, "br.profile")
        d = os.path.join(out, f"diff-x-{base}-{tip}")
        self.assertEqual(sorted(c[0] for c in self.calls), ["alloc", "cpu"])
        pair = json.load(open(os.path.join(d, "pair.json")))
        self.assertEqual((pair["a"], pair["b"], pair["corpus"], pair["cells"]), (base, tip, "x", [f"x/{base}/1", f"x/{tip}/1"]))
        # again, by the campaign's name: cached
        self.calls.clear()
        self.assertEqual(branchprofile.main(["diff", "br", base, tip]), 0)
        self.assertEqual(self.calls, [])
        # a new recording of one of them: diffed again
        jfr = os.path.join(out, "x", tip, "1", "rec.jfr")
        os.utime(jfr, (time.time() + 5, time.time() + 5))
        branchprofile.main(["diff", "br", base, tip])
        self.assertEqual(len(self.calls), 2)
        self.calls.clear()
        branchprofile.main(["diff", "br", base, tip, "--force"])
        self.assertEqual(len(self.calls), 2)
        # an unprofiled commit: nothing to diff
        mid = b["commits"][1]["variant"]
        self.assertEqual(branchprofile.main(["diff", "br", base, mid]), 1)

    def test_commits_by_prefix_or_ref(self):
        b = branch.resolve(self.repo, f"{self.base}..main")
        self.assertEqual(branchprofile.find_commit(b, self.tip[:6])["sha"], self.tip)
        self.assertEqual(branchprofile.find_commit(b, "main")["sha"], self.tip)
        self.assertEqual(branchprofile.find_commit(b, "main~1")["subject"], "Merge feature")
        with self.assertRaises(SystemExit):
            branchprofile.find_commit(b, "feature~1")  # f1: not first-parent


class ProfileSpecTest(unittest.TestCase):
    def setUp(self):
        Project("")
        self.b = {"commits": [{"variant": v, "index": i, "subject": f"s{i}"} for i, v in enumerate("pqr")]}

    def test_defaults(self):
        s = {"name": "n", "corpora": {"a": "-i 5", "b": ""}, "jvmArgs": "-Xmx1G", "branch": {}}
        ps = branchprofile.profile_spec(s, self.b, ["r", "p", "r"])
        self.assertEqual((ps["name"], ps["profileOf"], ps["profile"], ps["rounds"], ps["corpora"]),
                         ("n.profile", "n", "async:cpu,alloc", 1, {"a": "-i 5"}))
        self.assertEqual(list(ps["variants"]), ["p", "r"])  # history order
        self.assertEqual(ps["variantDescriptions"], {"p": "s0", "r": "s2"})
        self.assertNotIn("kperf", ps)

    def test_settings(self):
        s = {"name": "n", "corpora": {"a": "-i 5", "b": ""}, "branch": {},
             "profiles": {"profile": "async:wall", "corpora": ["b", "c"], "jmhArgs": {"c": "-i 1"}, "rounds": 2}}
        ps = branchprofile.profile_spec(s, self.b, [])
        self.assertEqual((ps["profile"], ps["rounds"], ps["corpora"]), ("async:wall", 2, {"b": "", "c": "-i 1"}))
        with self.assertRaises(SystemExit):
            branchprofile.profile_spec({**s, "profiles": {"corpora": ["z"]}}, self.b, [])


class ProfileViewTest(unittest.TestCase):
    def setUp(self):
        ViewProject()
        self.camps = config.get().campaigns
        self.camp = fixture(self.camps)
        self.v = [s[:10] for s in SHAS]
        self.prof = self.camp + ".profile"
        os.makedirs(self.prof)
        json.dump({"name": "br.profile", "profileOf": "br", "rounds": 1, "corpora": {"a": ""}, "variants": {self.v[3]: "", self.v[4]: ""}},
                  open(os.path.join(self.prof, "spec.json"), "w"))
        fake_profile_cell(os.path.join(self.prof, "a", self.v[3], "1"))
        fake_profile_cell(os.path.join(self.prof, "a", self.v[4], "1"))
        os.makedirs(os.path.join(self.prof, "a", self.v[1], "1"))
        open(os.path.join(self.prof, "a", self.v[1], "1", "result.json"), "w").close()  # running
        d = os.path.join(self.prof, f"diff-a-{self.v[3]}-{self.v[4]}")
        os.makedirs(d)
        stub_profdiff([])(["--event", "cpu", "x", "y", d])
        json.dump({"a": self.v[3], "b": self.v[4], "corpus": "a"}, open(os.path.join(d, "pair.json"), "w"))

    def test_profile_cells_and_diffs(self):
        p = branchview.branch_view(self.camp, self.camps)["profile"]
        self.assertEqual((p["campaign"], p["corpora"]), ("br.profile", ["a"]))
        cells = p["cells"]["a"]
        self.assertEqual(cells[self.v[1]], {"state": "running", "graphs": []})
        self.assertEqual(cells[self.v[3]]["graphs"], [["cpu", "bench", f"br.profile/a/{self.v[3]}/1/rec-cpu.html"],
                                                      ["alloc", "bench", f"br.profile/a/{self.v[3]}/1/rec-alloc.html"]])
        [d] = p["diffs"]
        self.assertEqual((d["a"], d["b"], d["corpus"], d["href"]), (self.v[3], self.v[4], "a", f"br.profile/diff-a-{self.v[3]}-{self.v[4]}/compare.html"))
        self.assertEqual([s[0] for s in d["events"][0]["slots"]], ["a", "diff", "inverse", "b"])

    def test_no_profile_campaign(self):
        shutil.rmtree(self.prof)
        self.assertIsNone(branchview.branch_view(self.camp, self.camps)["profile"])

    def test_hand_made_diffs_match_exactly(self):
        os.makedirs(os.path.join(self.camp, f"diff-x{self.v[3]}-{self.v[4]}"))
        open(os.path.join(self.camp, f"diff-x{self.v[3]}-{self.v[4]}", "compare.html"), "w").close()
        os.makedirs(os.path.join(self.camp, f"diff-{self.v[0][:7]}-{self.v[2][:7]}"))
        open(os.path.join(self.camp, f"diff-{self.v[0][:7]}-{self.v[2][:7]}", "compare.html"), "w").close()
        ds = {d["name"]: (d["a"], d["b"]) for d in branchview.branch_view(self.camp, self.camps)["diffs"]}
        self.assertEqual(ds[f"x{self.v[3]}-{self.v[4]}"], (None, None))
        self.assertEqual(ds[f"{self.v[0][:7]}-{self.v[2][:7]}"], (self.v[0], self.v[2]))
        self.assertEqual(ds[f"{self.v[3]}-{self.v[4]}"], (self.v[3], self.v[4]))

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_scripts_parse(self):
        page = open(index.build(self.camps)).read()
        self.assertIn('id="c-br.profile"', page)  # its own card, beside the branch campaign's
        blob = re.search(r'<div class="bh" data-campaign="br">.*?<script type="application/json">(.*?)</script>', page, re.S).group(1)
        self.assertEqual(json.loads(blob)["profile"]["campaign"], "br.profile")
        for i, js in enumerate(re.findall(r"<script>(.*?)</script>", page, re.S)):
            f = os.path.join(config.get().root, f"s{i}.js")
            open(f, "w").write(js)
            r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
