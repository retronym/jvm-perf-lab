import json, os, re, shutil, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`, even when run alone
os.environ["PERFLAB_API_NO_REINDEX"] = "1"
from perflab import ab, api, branchview, config, control, server  # noqa: E402
from test_branchview import SHAS, fixture, result  # noqa: E402
from test_branchprofile import fake_profile_cell, stub_profdiff  # noqa: E402

V = [s[:10] for s in SHAS]
TABLE = """cpu per op (benchmark threads): a 1.2k, b 1.0k, -16.7%  (ms/op a 10, b 8; ops a 3, b 3; a = base/1, b = tip/1)

self cpu per op, biggest decreases then increases (b − a):

| Δ | a | b | Δ of a's total | method |
|---|---|---|---|---|
| -150 | 300 | 150 | -12.50% | `a.B.slow` |
| … | | | | |
| +10 | 5 | 15 | +0.83% | `a.B.fast` |
"""


def project_dir():
    d = os.path.realpath(tempfile.mkdtemp())
    with open(os.path.join(d, "perflab.toml"), "w") as f:
        f.write('[build]\njmh = "x"\n')
    config._config = config.find(d)
    return d


def plain_fixture(campaigns, name="plain"):
    """A plain campaign: base and tip over corpus a, two rounds of two forks; tip 20% faster; a profiled cell of each
    in round 1 and their profdiff; an empty result.json (interrupted) in round 2 of corpus b."""
    camp = os.path.join(campaigns, name)
    os.makedirs(camp)
    json.dump({"name": name, "benchmark": "B", "rounds": 2, "corpora": {"a": "-i 3", "b": "-i 3"}, "variants": {"base": "", "tip": "-Dx=1"},
               "variantDescriptions": {"tip": "the **fast** one"}, "description": ["Is tip faster?"]}, open(os.path.join(camp, "spec.json"), "w"))
    forks = lambda x: [[x, x + 0.1, x - 0.1], [x + 0.2, x + 0.1, x + 0.3]]
    alloc = lambda x: [[x, x], [x, x + 1]]
    for v, x in (("base", 10.0), ("tip", 8.0)):
        for r in (1, 2):
            d = os.path.join(camp, "a", v, str(r))
            if r == 1:
                fake_profile_cell(d)  # a profile too: its recording and graphs
            os.makedirs(d, exist_ok=True)
            json.dump([result("a", forks(x + 0.05 * r), alloc(1e6))], open(os.path.join(d, "result.json"), "w"))
            open(os.path.join(d, "iterations.tsv"), "w").write(
                "index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\tpid\tunit\talloc_bytes\n"
                "0\twarmup\t\t1000\t2000\t11.0\t1\t\t7\tms/op\t\n1\tmeasure\t\t2000\t3000\t10.0\t1\t3\t7\tms/op\t1000\n")
            open(os.path.join(d, "load.tsv"), "w").write("2.5\t2.0\tjava 2.0\t2\n")
            open(os.path.join(d, "jmh.log"), "w").write("one\ntwo\nthree\n")
            open(os.path.join(d, "timeline.html"), "w").write("<html>")
    dd = os.path.join(camp, "diff-base-tip")
    os.makedirs(dd)
    stub_profdiff([])(["--event", "cpu", "x", "y", dd])
    open(os.path.join(dd, "table-cpu.md"), "w").write(TABLE)
    os.makedirs(os.path.join(camp, "b", "base", "2"))
    open(os.path.join(camp, "b", "base", "2", "result.json"), "w").close()
    return camp


def profile_fixture(camp):
    prof = camp + ".profile"
    os.makedirs(prof)
    json.dump({"name": os.path.basename(prof), "profileOf": os.path.basename(camp), "rounds": 1, "corpora": {"a": ""},
               "variants": {V[3]: "", V[4]: ""}, "profile": "async:cpu,alloc"}, open(os.path.join(prof, "spec.json"), "w"))
    fake_profile_cell(os.path.join(prof, "a", V[3], "1"))
    fake_profile_cell(os.path.join(prof, "a", V[4], "1"))
    d = os.path.join(prof, f"diff-a-{V[3]}-{V[4]}")
    os.makedirs(d)
    stub_profdiff([])(["--event", "cpu", "x", "y", d])
    json.dump({"a": V[3], "b": V[4], "corpus": "a"}, open(os.path.join(d, "pair.json"), "w"))
    return prof


class Fixture:
    def setUp(self):
        self.root = project_dir()
        api.DEFAULT_ROOT = self.root
        self.camps = config.get().campaigns
        self.br = fixture(self.camps)
        self.prof = profile_fixture(self.br)
        self.plain = plain_fixture(self.camps)

    def tearDown(self):
        api.DEFAULT_ROOT = None

    def valid(self, out):
        self.assertIn(out["schema"], api.SCHEMAS)
        self.assertEqual(out["version"], api.API_VERSION)
        errs = api.validate(out, api.ref(out["schema"]))
        self.assertEqual(errs, [], out["schema"])
        return out


def every_read(t):
    """(name, args) of a call of every read function on the fixtures."""
    return [("projects", {}), ("campaigns", {}), ("campaigns", {"storage": True}), ("campaign", {"campaign": "plain"}),
            ("campaign", {"campaign": "br"}), ("campaign", {"campaign": "br.profile"}), ("cells", {"campaign": "br"}),
            ("cells", {"campaign": "plain", "state": "interrupted"}),
            ("cell", {"campaign": "plain", "corpus": "a", "variant": "base", "round": 1, "tail": 2}),
            ("cell", {"campaign": "br", "corpus": "b", "variant": V[2], "round": 1}),
            ("branch", {"campaign": "br", "raw": True}), ("changes", {"campaign": "br"}), ("changes", {"campaign": "br", "metric": "alloc"}),
            ("compare", {"campaign": "plain", "a": "base", "b": "tip"}), ("compare", {"campaign": "br", "a": V[3], "b": "eeee"}),
            ("profiles", {"campaign": "plain"}), ("profiles", {"campaign": "br"}),
            ("diff", {"campaign": "plain", "a": "base", "b": "tip"}), ("diff", {"campaign": "br", "a": V[4], "b": V[3]}),
            ("voids", {"campaign": "br"}), ("jobs", {})]


class ReadTest(Fixture, unittest.TestCase):
    def test_every_read_matches_its_schema(self):
        for name, args in every_read(self):
            with self.subTest(name=name, args=args):
                self.valid(api.call(name, args))
        self.assertEqual({n for n, _ in every_read(self)} | {"job", "transcript"},
                         {f.name for f in api.FUNCTIONS.values() if f.kind == "read"})

    def test_campaigns(self):
        cs = {c["name"]: c for c in api.campaigns()["campaigns"]}
        self.assertEqual(set(cs), {"br", "br.profile", "plain"})
        self.assertEqual((cs["br"]["kind"], cs["br.profile"]["kind"], cs["plain"]["kind"]), ("branch", "profile", "plain"))
        self.assertEqual(cs["br"]["variants"], V)
        self.assertEqual(cs["br"]["profiles"], "br.profile")
        # 2 rounds × 2 corpora × 5 commits; done: 7 on a, 2 on b; the running one on b (an empty result.json, no
        # running.json) is interrupted
        self.assertEqual(cs["br"]["progress"], {"planned": 20, "done": 9, "running": 0, "failed": 0, "interrupted": 1,
                                                "unbuildable": 0, "void": 0})
        self.assertEqual(cs["br"]["status"], "partial")
        self.assertEqual(cs["plain"]["progress"]["planned"], 8)
        self.assertIsNone(cs["plain"]["bytes"])
        self.assertEqual(cs["plain"]["description"], "Is tip faster?")
        with_bytes = {c["name"]: c for c in api.campaigns(storage=True)["campaigns"]}
        self.assertGreater(with_bytes["plain"]["bytes"]["profiles"], 0)

    def test_running_cell_and_status(self):
        json.dump({"campaign": "br", "cell": f"br/b/{V[2]}/1"}, open(os.path.join(self.camps, ab.RUNNING_NAME), "w"))
        c = next(c for c in api.campaigns()["campaigns"] if c["name"] == "br")
        self.assertEqual((c["status"], c["progress"]["running"], c["progress"]["interrupted"]), ("running", 1, 0))
        [cell] = api.cells("br", corpus="b", variant=V[2], round=1)["cells"]
        self.assertEqual(cell["state"], "running")

    def test_plain_summary_over_forks_with_welch_delta(self):
        c = self.valid(api.campaign("plain"))
        self.assertEqual(c["baseline"], "base")
        rows = {(r["corpus"], r["variant"]): r for r in c["summary"]}
        self.assertEqual(set(rows), {("a", "base"), ("a", "tip")})
        tip = rows[("a", "tip")]
        self.assertEqual((tip["rounds"], tip["forks"]), (2, 4))
        s = tip["metrics"]["score"]
        self.assertEqual(s["n"], 4)
        self.assertNotIn("delta", rows[("a", "base")]["metrics"]["score"])
        self.assertEqual((s["delta"]["against"], s["delta"]["verdict"]), ("base", "better"))
        self.assertAlmostEqual(s["delta"]["pct"], 100 * (s["mean"] / rows[("a", "base")]["metrics"]["score"]["mean"] - 1))
        self.assertLess(s["delta"]["pct"] + s["delta"]["halfWidth"], 0)
        self.assertAlmostEqual(tip["card"]["score"]["pct"], s["delta"]["pct"])  # the same means, over rounds
        self.assertEqual([v["name"] for v in c["variantInfo"]], ["base", "tip"])
        self.assertEqual(c["variantInfo"][1]["flags"], "-Dx=1")
        self.assertEqual(c["metrics"][0]["key"], "score")
        self.assertEqual(len(c["links"]["timelines"]), 4)
        self.assertEqual({(g["variant"], g["event"]) for g in c["links"]["graphs"]}, {("base", "cpu"), ("base", "alloc"), ("tip", "cpu"), ("tip", "alloc")})
        [d] = c["links"]["diffs"]
        self.assertEqual((d["a"], d["b"]), ("base", "tip"))

    def test_the_stats_are_the_branch_views(self):
        bv = branchview.branch_view(self.br)
        b = self.valid(api.branch("br"))
        self.assertEqual([c["variant"] for c in b["commits"]], V)
        n = 0
        for c in b["commits"]:
            for corpus, x in c["corpora"].items():
                m = bv["cells"][corpus][c["variant"]]
                self.assertEqual(x["state"], m["state"])
                for k, s in x["metrics"].items():
                    self.assertEqual([s["mean"], s["sd"], s["ci"], s["n"], s["df"]], [m["m"][k][i] for i in (0, 1, 2, 4, 5)])
                    if k in m["d"]:
                        self.assertEqual([s["delta"]["pct"], s["delta"]["halfWidth"], s["delta"]["verdict"]], m["d"][k][:3])
                        n += 1
        self.assertGreater(n, 3)
        # and the campaign's own summary (Δ against the base) agrees on the means and CIs, pool included
        rows = {(r["corpus"], r["variant"]): r for r in api.campaign("br")["summary"]}
        for (corpus, v), r in rows.items():
            for k, s in r["metrics"].items():
                self.assertAlmostEqual(s["mean"], bv["cells"][corpus][v]["m"][k][0])
                self.assertEqual(s["ci"] is None, bv["cells"][corpus][v]["m"][k][2] is None)

    def test_branch_commits_oldest_first(self):
        b = api.branch("br")
        self.assertEqual([c["index"] for c in b["commits"]], [0, 1, 2, 3, 4])
        self.assertEqual(len(b["commits"][3]["merged"]), 2)
        self.assertEqual(b["commits"][4]["corpora"]["a"]["previous"], V[3])
        self.assertNotIn("raw", b["commits"][0]["corpora"]["a"])
        self.assertEqual(b["commits"][3]["profiled"], ["a"])
        self.assertEqual(api.branch("br", raw=True)["commits"][0]["corpora"]["a"]["raw"]["score"][0], [10.0, 10.1, 9.9])
        with self.assertRaises(api.ApiError) as e:
            api.branch("plain")
        self.assertEqual(e.exception.code, "bad_request")

    def test_changes_are_the_significant_steps(self):
        b = api.branch("br")
        want = {(corpus, c["variant"]) for c in b["commits"] for corpus, x in c["corpora"].items()
                if ((x["metrics"].get("score") or {}).get("delta") or {}).get("verdict") in ("better", "worse")}
        ch = api.changes("br")
        self.assertEqual({(c["corpus"], c["variant"]) for c in ch["changes"]}, want)
        self.assertIn(("a", V[4]), want)  # 20% faster than its predecessor, over 4 forks each
        pcts = [abs(c["delta"]["pct"]) for c in ch["changes"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))
        # corpus b: one fork per commit and nothing to pool, so its step is untested, not flat
        self.assertIn(("b", V[1]), {(u["corpus"], u["variant"]) for u in ch["untested"]})
        self.assertEqual(api.changes("br", corpus="b")["changes"], [])

    def test_compare_by_sha_prefix(self):
        c = api.compare("br", V[3], SHAS[4][:6])
        self.assertEqual((c["a"], c["b"]), (V[3], V[4]))
        [a] = [x for x in c["corpora"] if x["corpus"] == "a"]
        s = next(m for m in a["metrics"] if m["key"] == "score")
        self.assertEqual(s["delta"]["verdict"], "better")
        self.assertEqual(len(c["diffs"]), 2)  # the profile campaign's, and one made by hand in the campaign
        with self.assertRaises(api.ApiError) as e:
            api.compare("br", V[3], "zzzz")
        self.assertEqual(e.exception.code, "not_found")

    def test_cells_filters_and_states(self):
        cs = api.cells("br")["cells"]
        self.assertEqual(len([c for c in cs if c["state"] != "void"]), 20)
        self.assertEqual({c["state"] for c in cs}, {"done", "pending", "interrupted"})
        done = api.cells("br", corpus="a", state="done")["cells"]
        self.assertEqual(len(done), 7)
        self.assertEqual([c["round"] for c in api.cells("br", variant=SHAS[0][:5], corpus="a")["cells"]], [1, 2])
        self.assertTrue(all(c["round"] == 2 for c in api.cells("plain", round=2)["cells"]))

    def test_cell_in_full(self):
        c = api.cell("plain", "a", "base", 1, tail=2)
        self.assertEqual(c["result"]["unit"], "ms/op")
        self.assertEqual([[round(x, 6) for x in f] for f in c["raw"]["score"]], [[10.05, 10.15, 9.95], [10.25, 10.15, 10.35]])
        self.assertEqual([i["kind"] for i in c["iterations"]], ["warmup", "measure"])
        self.assertEqual(c["iterations"][1]["gc_ms"], 3)
        self.assertEqual(c["load"]["source"], "load.tsv")
        self.assertEqual(c["load"]["iterations"][0]["cores"], 2.0)
        self.assertEqual(c["logs"]["jmh.log"]["tail"], "two\nthree\n")
        self.assertEqual({g["event"] for g in c["profile"]["graphs"]}, {"cpu", "alloc"})
        self.assertEqual(c["gc"]["metrics"]["gc.alloc.rate.norm"]["unit"], "B/op")
        self.assertIsNone(c["cell"]["url"])  # not registered: nothing is served
        with self.assertRaises(api.ApiError):
            api.cell("plain", "a", "base", 9)
        with self.assertRaises(api.ApiError) as e:
            api.cell("plain", "..", "base", 1)
        self.assertEqual(e.exception.code, "bad_request")

    def test_diff_tables(self):
        d = api.diff("plain", "tip", "base")
        [x] = d["diffs"]
        [ev] = x["events"]
        self.assertEqual(ev["event"], "cpu")
        self.assertEqual(set(ev["pages"]), {"a", "diff", "inverse", "b"})
        self.assertEqual([r["method"] for r in ev["rows"]], ["a.B.slow", "a.B.fast"])
        self.assertEqual((ev["rows"][0]["delta"], ev["rows"][0]["pctOfTotal"]), (-150.0, -12.5))
        self.assertTrue(ev["summary"].startswith("cpu per op"))
        self.assertIn("a", [x["corpus"] for x in api.diff("br", V[3], V[4])["diffs"]])
        with self.assertRaises(api.ApiError) as e:
            api.diff("br", V[0], V[1])
        self.assertIn("submit", e.exception.details)

    def test_unknown_names_list_what_there_is(self):
        with self.assertRaises(api.ApiError) as e:
            api.campaign("nope")
        self.assertEqual(e.exception.details["campaigns"], ["br", "br.profile", "plain"])
        with self.assertRaises(api.ApiError) as e:
            api.call("campaign", {"campaign": "br", "bogus": 1})
        self.assertEqual(e.exception.code, "bad_request")
        with self.assertRaises(api.ApiError) as e:
            api.call("cell", {"campaign": "br", "corpus": "a", "variant": V[0], "round": "1"})  # not coerced: a type error
        self.assertEqual(e.exception.code, "bad_request")

    def test_an_action_without_a_server(self):
        with self.assertRaises(api.ApiError) as e:
            api.call("void", {"campaign": "br", "corpus": "a", "variant": V[0], "round": 1, "reason": "x"})
        self.assertEqual(e.exception.code, "no_server")
        self.assertEqual(e.exception.status, 503)

    def test_cli_prints_json(self):
        env = {**os.environ, "PYTHONPATH": SRC}
        run = lambda *a: subprocess.run([sys.executable, "-m", "perflab", "api", "--root", self.root, *a], capture_output=True, text=True, env=env)
        p = run("cells", "--campaign", "plain", "--round", "2", "--state", "done")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual({c["variant"] for c in json.loads(p.stdout)["cells"]}, {"base", "tip"})
        p = run("branch", "--campaign", "br", "--raw")
        self.assertIn("raw", json.loads(p.stdout)["commits"][0]["corpora"]["a"])
        p = run("campaign", "--campaign", "nope")
        self.assertEqual((p.returncode, json.loads(p.stdout)["error"]["code"]), (1, "not_found"))
        self.assertEqual(json.loads(run("--schema", "Stat").stdout)["properties"]["n"]["type"], "integer")
        self.assertIn("campaign", {f["name"] for f in json.loads(run("--list").stdout)["functions"]})


class SchemaTest(unittest.TestCase):
    def test_every_field_is_described(self):
        def walk(s, path):
            if isinstance(s, dict):
                for k, v in (s.get("properties") or {}).items():
                    self.assertTrue(v.get("description") or "$ref" in v, f"{path}.{k}")
                    walk(v, f"{path}.{k}")
                for k in ("items", "additionalProperties"):
                    if isinstance(s.get(k), dict):
                        walk(s[k], f"{path}[{k}]")
                for x in s.get("anyOf", []):
                    walk(x, path)
        for n, s in api.SCHEMAS.items():
            self.assertTrue(s.get("description"), n)
            walk(s, n)
        for f in api.FUNCTIONS.values():
            self.assertIn(f.result, api.SCHEMAS)
            for k, s in f.params.items():
                self.assertTrue(s.get("description"), f"{f.name}({k})")

    def test_examples_match_their_schemas(self):
        tops = [n for n, s in api.SCHEMAS.items() if "schema" in s["properties"]]
        for n in tops:
            with self.subTest(schema=n):
                self.assertTrue(api.SCHEMAS[n].get("examples"), f"{n} has no example")
                for x in api.SCHEMAS[n]["examples"]:
                    self.assertEqual(api.validate(x, api.ref(n)), [])

    def test_openapi_refs_resolve(self):
        doc = json.loads(json.dumps(api.openapi()))
        self.assertEqual(doc["openapi"], "3.1.0")

        def resolve(r):
            node = doc
            for part in r.removeprefix("#/").split("/"):
                node = node[part]
            return node
        refs = re.findall(r'"\$ref": "([^"]+)"', json.dumps(doc))
        self.assertGreater(len(refs), 50)
        for r in set(refs):
            self.assertTrue(r.startswith("#/"), r)
            resolve(r)
        self.assertNotIn("$defs", json.dumps(doc["components"]))
        ops = [op for p in doc["paths"].values() for op in p.values()]
        self.assertEqual(len({op["operationId"] for op in ops}), len(ops))
        for f in api.FUNCTIONS.values():
            op = doc["paths"][f.path][f.method.lower()]
            self.assertIn("200", op["responses"])
            self.assertEqual(f.kind == "action", "security" in op)

    def test_schema_of_is_standalone(self):
        s = api.schema_of("Campaign")
        refs = set(re.findall(r'"#/\$defs/(\w+)"', json.dumps(s)))
        self.assertTrue(refs)
        self.assertTrue(refs <= set(s["$defs"]))

    def test_docs_page(self):
        page = api.docs_page()
        self.assertIn('id="f-campaign"', page)
        self.assertIn('id="s-Stat"', page)


def free_server(test):
    home = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, home, True)
    old = os.environ["PERFLAB_SERVER_HOME"]
    os.environ["PERFLAB_SERVER_HOME"] = home  # where the api reads the queue and the projects
    test.addCleanup(os.environ.__setitem__, "PERFLAB_SERVER_HOME", old)
    s = server.Server(home, port=0, grace=1).start()

    def stop():
        for j in s.q.jobs():
            if j["pid"] and j["state"] in server.ACTIVE:
                server.Worker._signal(j["pid"], 9)
        s.stop()
    test.addCleanup(stop)
    return s


class HttpTest(Fixture, unittest.TestCase):
    """The API on a test server (its own home and an ephemeral port), its jobs perflab_fakejob."""

    def setUp(self):
        super().setUp()
        self.srv = free_server(self)
        self.pid = self.srv.q.register(self.root)["id"]
        api._RERUN_RUNNER["module"] = "perflab_fakejob"
        self.addCleanup(api._RERUN_RUNNER.clear)
        self.env = {"PYTHONPATH": os.pathsep.join([HERE, os.path.abspath(SRC)]), control.POLL_ENV: "0.1"}

    def http(self, method, path, body=None, token=True):
        h = {"Content-Type": "application/json", **({"X-Perflab-Token": self.srv.token} if token else {})}
        req = urllib.request.Request(self.srv.url.rstrip("/") + path, method=method, headers=h,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                text = r.read().decode()
                return r.status, json.loads(text) if "json" in r.headers.get("Content-Type", "") else text, r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), e.headers

    def test_reads_over_http(self):
        code, idx, h = self.http("GET", "/api/v1")
        self.assertEqual((code, idx["schema"]), (200, "ApiIndex"))
        self.assertIn("ApiIndex", h["Link"])
        self.assertEqual({f["name"] for f in idx["functions"]}, set(api.FUNCTIONS))
        code, c, h = self.http("GET", f"/api/v1/campaign?project={self.pid}&campaign=plain")
        self.assertEqual(code, 200)
        self.assertEqual(h["Link"], '</api/v1/openapi.json#/components/schemas/Campaign>; rel="describedby"')
        self.assertEqual(c["links"]["card"], f"/p/{self.pid}/ab/index.html#c-plain")
        code, cell, _ = self.http("GET", f"/api/v1/cell?campaign=plain&corpus=a&variant=base&round=1")  # the only project
        self.assertEqual(code, 200, cell)
        self.assertEqual(cell["cell"]["timeline"], f"/p/{self.pid}/ab/plain/a/base/1/timeline.html")
        code, page, _ = self.http("GET", cell["cell"]["timeline"])
        self.assertEqual(code, 200)
        code, err, h = self.http("GET", "/api/v1/campaign?campaign=nope")
        self.assertEqual((code, err["error"]["code"]), (404, "not_found"))
        self.assertIn("Error", h["Link"])
        code, err, _ = self.http("GET", f"/api/v1/campaigns?project={tempfile.mkdtemp()}")
        self.assertEqual(code, 404)
        code, err, _ = self.http("GET", "/api/v1/void")
        self.assertEqual(code, 400)
        code, doc, _ = self.http("GET", "/api/v1/openapi.json")
        self.assertEqual(doc["openapi"], "3.1.0")
        code, html, _ = self.http("GET", "/api/v1/docs")
        self.assertIn("perflab API", html)
        code, s, _ = self.http("GET", "/api/v1/schemas/Cell")
        self.assertEqual(s["$defs"]["CellSummary"]["type"], "object")
        self.assertEqual(self.http("GET", "/api/jobs")[0], 200)  # the old API stays

    def test_llms_txt_and_skill(self):
        code, txt, h = self.http("GET", "/llms.txt")
        self.assertEqual(code, 200)
        self.assertTrue(txt.startswith("# perflab server\n\n> "))
        for link in ("(/skill.md)", "(/api/v1/docs)", "(/api/v1/openapi.json)", "(/api/v1/changes)", "(/api/v1/void)"):
            self.assertIn(link, txt)
        self.assertLess(txt.index("(/api/v1/changes)"), txt.index("## Actions"))
        self.assertGreater(txt.index("(/api/v1/void)"), txt.index("## Actions"))
        code, md, _ = self.http("GET", "/skill.md")
        self.assertEqual((code, md.startswith("---")), (200, True))
        self.assertIn("perflab api", md)
        for page in ("/", "/admin", "/api/v1/docs"):
            self.assertIn('href="/llms.txt"', self.http("GET", page)[1], page)

    def test_void_unvoid_and_rerun_once(self):
        body = {"project": self.pid, "campaign": "br", "corpus": "a", "variant": V[4], "round": 2, "reason": "load over 2 cores"}
        self.assertEqual(self.http("POST", "/api/v1/void", body, token=False)[0], 403)
        # the running cell is refused
        json.dump({"campaign": "br", "cell": f"br/a/{V[4]}/2"}, open(os.path.join(self.camps, ab.RUNNING_NAME), "w"))
        code, err, _ = self.http("POST", "/api/v1/void", body)
        self.assertEqual((code, err["error"]["code"]), (409, "conflict"))
        os.unlink(os.path.join(self.camps, ab.RUNNING_NAME))
        for bad, want in (({"variant": "../plain"}, 400), ({"campaign": "../x"}, 400), ({"round": 7}, 404), ({"reason": ""}, 400)):
            code, err, _ = self.http("POST", "/api/v1/void", {**body, **bad})
            self.assertEqual(code, want, (bad, err))
        os.makedirs(os.path.join(self.br, "a", V[2], "1"))  # a directory, not a cell
        self.assertEqual(self.http("POST", "/api/v1/void", {**body, "variant": V[2], "round": 1})[0], 400)
        code, v, _ = self.http("POST", "/api/v1/void", body)
        self.assertEqual(code, 200, v)
        self.assertEqual(v["schema"], "Voided")
        self.assertFalse(os.path.exists(os.path.join(self.br, "a", V[4], "2")))
        self.assertTrue(v["void"]["path"].startswith(os.path.join(self.br, ".void", "a", V[4], "2-")))
        self.assertEqual(open(os.path.join(v["void"]["path"], "void.txt")).read(), "load over 2 cores\n")
        cs = api.cells("br", corpus="a", variant=V[4])["cells"]
        self.assertEqual(sorted(c["state"] for c in cs), ["done", "pending", "void"])
        self.assertEqual(next(c for c in api.campaigns()["campaigns"] if c["name"] == "br")["progress"]["void"], 1)
        self.assertEqual(api.voids("br")["voids"][0]["reason"], "load over 2 cores")
        # the branch view no longer sees it
        self.assertEqual(api.branch("br")["commits"][4]["corpora"]["a"]["rounds"], 1)

        # rerun, deduped against a queued job
        blocker = server.submit_local(self.srv, {"argv": ["cells", "200", "0.1"], "cwd": self.root, "env": self.env}, module="perflab_fakejob")
        wait = time.time() + 20
        while self.srv.q.get(blocker["id"])["state"] != "running" and time.time() < wait:
            time.sleep(0.1)
        code, r1, _ = self.http("POST", "/api/v1/rerun", {"project": self.pid, "campaign": "br"})
        self.assertEqual(code, 200, r1)
        self.assertEqual((r1["deduped"], r1["argv"]), (False, ["ab", "run", os.path.join(self.br, "spec.json")]))
        code, r2, _ = self.http("POST", "/api/v1/rerun", {"project": self.root, "campaign": "br"})  # by root: the same project
        self.assertEqual((r2["deduped"], r2["job"]["id"]), (True, r1["job"]["id"]))
        self.assertEqual(len([j for j in self.srv.q.queued()]), 1)
        self.assertIsNone(r2["running"])  # the blocker runs no campaign
        self.assertEqual(api.validate(r2, api.ref("Rerun")), [])
        c = next(c for c in api.campaigns()["campaigns"] if c["name"] == "br")
        self.assertEqual([j["id"] for j in c["jobs"]], [r1["job"]["id"]])
        # job reads and control
        self.assertEqual(api.job(r1["job"]["id"])["job"]["state"], "queued")
        code, j, _ = self.http("POST", "/api/v1/cancel", {"id": r1["job"]["id"]})
        self.assertEqual((code, j["job"]["state"]), (200, "cancelled"))
        code, err, _ = self.http("POST", "/api/v1/pause", {"id": r1["job"]["id"]})
        self.assertEqual(code, 409)
        wait = time.time() + 20
        while "cell" not in api.transcript(blocker["id"])["text"] and time.time() < wait:
            time.sleep(0.1)
        self.assertIn("cell 0", api.transcript(blocker["id"])["text"])
        self.http("POST", "/api/v1/cancel", {"id": blocker["id"]})

        # unvoid
        code, u, _ = self.http("POST", "/api/v1/unvoid", {"project": self.pid, "campaign": "br", "id": v["void"]["id"]})
        self.assertEqual((code, u["cell"]["state"]), (200, "done"))
        self.assertFalse(os.path.exists(os.path.join(self.br, "a", V[4], "2", "void.txt")))
        self.assertEqual(api.voids("br")["voids"], [])
        code, err, _ = self.http("POST", "/api/v1/unvoid", {"project": self.pid, "campaign": "br", "id": v["void"]["id"]})
        self.assertEqual(code, 404)

    def test_unvoid_refuses_a_rerun_cell(self):
        v = api.call("void", {"campaign": "plain", "corpus": "a", "variant": "tip", "round": 2, "reason": "x"}, server=self.srv)
        os.makedirs(os.path.join(self.plain, "a", "tip", "2"))
        with self.assertRaises(api.ApiError) as e:
            api.call("unvoid", {"campaign": "plain", "id": v["void"]["id"]}, server=self.srv)
        self.assertEqual(e.exception.code, "conflict")

    def test_actions_from_a_client_go_to_the_server(self):
        url = self.srv.url
        old = server.running
        server.running = lambda: url
        self.addCleanup(setattr, server, "running", old)
        v = api.call("void", {"campaign": "plain", "corpus": "a", "variant": "tip", "round": 2, "reason": "by the client"})
        self.assertEqual(v["schema"], "Voided")
        with self.assertRaises(api.ApiError) as e:
            api.call("void", {"campaign": "plain", "corpus": "a", "variant": "tip", "round": 2, "reason": "again"})
        self.assertEqual(e.exception.code, "not_found")


class SpecCopyTest(unittest.TestCase):
    """`ab run <campaign>/spec.json` (what rerun queues) resolves a relative checkout as the original spec did."""

    def test_relative_checkout_in_the_campaigns_copy(self):
        from test_branch import repo_with_history
        root = project_dir()
        repo = os.path.join(root, "..", os.path.basename(root) + "-repo")
        os.makedirs(repo)
        self.addCleanup(shutil.rmtree, repo, True)
        base, _ = repo_with_history(repo)
        spec_f = os.path.join(root, "s.json")
        json.dump({"name": "rel", "benchmark": "B", "corpora": {"x": ""},
                   "branch": {"checkout": "../" + os.path.basename(repo), "range": f"{base}..main"}}, open(spec_f, "w"))
        want = os.path.realpath(repo)
        self.assertEqual(os.path.realpath(ab.Spec(spec_f).branch["checkout"]), want)
        out = os.path.join(config.get().campaigns, "rel")
        os.makedirs(out)
        shutil.copy(spec_f, os.path.join(out, "spec.json"))
        open(os.path.join(out, ab.SOURCE), "w").write(spec_f + "\n")
        self.assertEqual(os.path.realpath(ab.Spec(os.path.join(out, "spec.json")).branch["checkout"]), want)
        # a copy from before spec.source: branch.json's checkout
        os.unlink(os.path.join(out, ab.SOURCE))
        json.dump({"checkout": want}, open(os.path.join(out, "branch.json"), "w"))
        import perflab.branch as br
        old = br.load
        br.load = lambda out_, b, write=True: {"commits": [], "order": [], "checkout": b["checkout"]}
        self.addCleanup(setattr, br, "load", old)
        self.assertEqual(os.path.realpath(ab.Spec(os.path.join(out, "spec.json")).branch["checkout"]), want)


# ---- the schemas' examples, from these fixtures: python3 test_api.py --write-examples

def trim(x, depth=0):
    if isinstance(x, list):
        return [trim(v, depth + 1) for v in x[:2]]
    if isinstance(x, dict):
        return {k: trim(v, depth + 1) for k, v in x.items()}
    if isinstance(x, str) and len(x) > 400:
        return x[:400]
    return x


def write_examples():
    t = type("T", (Fixture,), {})()
    t.setUp()
    s = free_server(unittest.TestCase())
    s.q.register(t.root)
    api._RERUN_RUNNER["module"] = "perflab_fakejob"
    ex = {}
    for name, args in every_read(t):
        out = api.call(name, args)
        ex.setdefault(out["schema"], out)
    ex["ApiIndex"] = api.index_doc()
    v = api.call("void", {"campaign": "br", "corpus": "a", "variant": V[4], "round": 2, "reason": "other load up to 2.1 cores over iterations 3, 4"}, server=s)
    ex["Voided"] = v
    ex["Voids"] = api.voids("br")
    ex["Unvoided"] = api.call("unvoid", {"campaign": "br", "id": v["void"]["id"]}, server=s)
    r = api.call("rerun", {"campaign": "br"}, server=s)
    ex["Rerun"] = r
    ex["JobResult"] = api.job(r["job"]["id"])
    ex["Jobs"] = api.jobs()
    ex["Transcript"] = {"schema": "Transcript", "version": api.API_VERSION, "id": r["job"]["id"], "text": "[ab 10:12:22] br: 20 cells, 11 to run\n"}
    api.call("cancel", {"id": r["job"]["id"]}, server=s)
    s.stop()
    text = json.dumps({k: trim(x) for k, x in sorted(ex.items())}, indent=1, ensure_ascii=False)
    text = text.replace(t.root, "/Users/me/lab").replace(server.home(), "/Users/me/.perflab/server").replace(server.project_id(t.root), "lab-3f2a1c").replace(os.path.basename(t.root), "lab")
    text = re.sub(r"/(private/)?var/folders/[^\"]*?/T/tmp\w+", "/tmp/perflab-server", text)
    open(os.path.join(SRC, "perflab", "api_examples.json"), "w").write(text + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-examples"]:
        write_examples()
    else:
        unittest.main()
