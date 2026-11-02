import json, os, re, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from perflab import asm  # noqa: E402

FIXTURE = os.path.join(HERE, "asm_fixture")  # String::hashCode printed by GraalVM 25.4 (aarch64); b without compressed oops


def asm_fixture(campaigns, name="cap", parent=None):
    """An asm capture: variants a and b, corpus x, round 1, each a fork's vm log split into <cell>/asm."""
    camp = os.path.join(campaigns, name)
    spec = {"name": name, "corpora": {"x": "-f 1 -i 2"}, "variants": {"a": "", "b": "-XX:-UseCompressedOops"}, "rounds": 1,
            "asm": ["java.lang.String::hashCode"]}
    if parent:
        spec["asmOf"] = parent
    os.makedirs(camp)
    json.dump(spec, open(os.path.join(camp, "spec.json"), "w"))
    for v in ("a", "b"):
        d = os.path.join(camp, "x", v, "1")
        os.makedirs(d)
        shutil.copy(os.path.join(FIXTURE, f"{v}.log"), os.path.join(d, "vm-7.log"))
        asm.split(d)
        json.dump([{"jvm": "java", "jvmArgs": [], "primaryMetric": {"score": 1.0, "scoreUnit": "ms/op", "rawData": [[1.0]]}}],
                  open(os.path.join(d, "result.json"), "w"))
    return camp


class AsmTest(unittest.TestCase):
    def setUp(self):
        self.camps = tempfile.mkdtemp()
        self.camp = asm_fixture(self.camps)
        self.cell = os.path.join(self.camp, "x", "a", "1")

    def test_split_writes_each_compilation_and_an_index(self):
        idx = asm.load_index(self.cell)
        self.assertEqual([(c["compiler"], c["level"]) for c in idx], [("c1", 3), ("jvmci", 4)])
        c = idx[1]
        self.assertEqual((c["method"], c["signature"], c["bytes"], c["pid"]), ("java.lang.String::hashCode", "()I", 60, 7))
        self.assertTrue(os.path.exists(os.path.join(self.cell, c["file"])))
        self.assertTrue(os.path.exists(os.path.join(self.cell, "vm-7.log.gz")))
        self.assertFalse(os.path.exists(os.path.join(self.cell, "vm-7.log")))
        self.assertGreater(c["instructions"], 50)

    def test_cell_page(self):
        page = open(os.path.join(self.cell, "asm", "index.html")).read()  # written by split
        self.assertIn("<b>default</b>", page)
        self.assertIn("String::hashCode:2430", page)
        self.assertNotIn("heat from", page)
        before = os.path.getmtime(asm.page_path(self.cell))
        m = "java.lang.String::hashCode"
        asm.save_hot(self.cell, m, {((m, 2430),): 0.75, ((m, 1),): 0.25}, [os.path.join(self.camps, "p", "x", "a", "1")])
        os.utime(os.path.join(self.cell, "asm", "hot.json"), (before + 10, before + 10))
        page = open(asm.ensure_cell_page(self.cell)).read()
        self.assertIn("heat from p/x/a/1, 25% of it at positions", page)
        self.assertIn('style="width:75%"', page)

    def test_default_is_the_last_top_tier(self):
        sel = asm.select(self.cell, "String::hashCode")
        self.assertEqual([c["compiler"] for c in sel.values()], ["jvmci"])
        self.assertEqual(asm.select(self.cell, "hashCode()I"), {})  # a descriptor needs the method's name before it
        self.assertEqual(len(asm.select(self.cell, "String::hashCode()I")), 1)
        self.assertEqual(asm.select(self.cell, "String::length"), {})

    def test_parse_normalises_and_attributes(self):
        comp = next(iter(asm.select(self.cell, "String::hashCode").values()))
        code = asm.code_of(self.cell, comp)
        main = [i for i in code["insns"] if i["section"] == "code"]
        addr = [i["norm"] for i in main if re.search(r"0x[0-9a-f]{6,}", i["norm"])]
        self.assertEqual(addr, [])
        self.assertTrue(any(i["norm"].startswith("b") and " L" in i["norm"] for i in main))  # branch targets as labels
        scoped = [i for i in main if i["scope"]]
        self.assertGreater(len(scoped), len(main) * 0.8)
        self.assertEqual(scoped[0]["scope"][0][0], "java.lang.String::hashCode")
        self.assertEqual(code["totals"]["main"]["insns"], len(main))
        self.assertEqual(code["totals"]["entry"]["insns"], 16)

    def test_kinds(self):
        self.assertEqual(asm.kind("str", "x3, [sp, #0x20]"), {"store", "spill"})
        self.assertEqual(asm.kind("ldp", "x29, x30, [sp, #0x10]"), {"load", "fill"})
        self.assertEqual(asm.kind("ldr", "w0, [x1, #0x1c]"), {"load"})
        self.assertEqual(asm.kind("blr", "x8"), {"call"})
        self.assertEqual(asm.kind("cbz", "w0, #0x12fc11b74"), {"branch"})

    def test_diff(self):
        out = asm.diff(self.camp, "a", "b", "String::hashCode", hot_path=False)
        r = out["methods"][0]
        self.assertEqual(r["signature"], "()I")
        self.assertEqual(sum(g["a"]["insns"] for g in r["groups"]),
                         sum(r["totals"]["a"][k]["insns"] for k in ("main", "entry", "outOfLine")))
        labels = [g["label"] for g in r["groups"]]
        self.assertIn("String::hashCode:2430", labels)
        self.assertTrue(any(not g["same"] for g in r["groups"]))
        self.assertTrue(os.path.exists(out["page"]))
        self.assertTrue(os.path.exists(out["page"][:-5] + ".json"))
        self.assertIn("not a timed one", open(out["page"]).read())

    def test_align_shifts_each_methods_lines(self):
        m, c = "a.B::f", "a.C::g"
        # the patch added a line above f (all of f's lines +1, some coincide with a's) and 28 above g
        ka = [((m, 33),), ((m, 34), (c, 113)), ((m, 38),), ((m, 39), (c, 113))]
        kb = [((m, 34),), ((m, 35), (c, 141)), ((m, 39),), ((m, 40), (c, 141)), ((m, 41),)]
        self.assertEqual(asm.align(ka, kb), [(ka[0], kb[0]), (ka[1], kb[1]), (ka[2], kb[2]), (ka[3], kb[3]), (None, kb[4])])
        same = asm.align([((m, 10),), ((m, 12),)], [((m, 10),), ((m, 13),)])
        self.assertEqual(same, [(((m, 10),), ((m, 10),)), (None, ((m, 13),)), (((m, 12),), None)])

    def test_align_without_line_numbers(self):
        m = "a.B::f"
        ka, kb = [((m, 1), ("a.C::g", None)), ((m, 1), ("a.C::g", 3))], [((m, 2), ("a.C::g", None))]
        self.assertEqual(asm.align(ka, kb), [(ka[0], kb[0]), (ka[1], None)])

    def test_lambda_numbers_ignored(self):
        self.assertEqual(asm.norm_scope_name("a.B$", "$anonfun$39"), asm.norm_scope_name("a.B$", "$anonfun$41"))

    def test_shade_falls_back_to_the_longest_prefix(self):
        m = "a.B::f"
        hot = {((m, 1), ("a.C::g", 2)): 0.5, ((m, 1),): 0.25, ((m, 9),): 0.25}
        self.assertEqual(asm.shade(hot, [((m, 1),)]), {((m, 1),): 0.75, None: 0.25})

    def test_capture_spec(self):
        parent = os.path.join(self.camps, "p.json")
        json.dump({"name": "p", "profile": "async:cycles", "kperf": "/tmp/s", "rounds": 3, "loadgate": {"maxCores": 1},
                   "corpora": {"x": "-f 2 -wi 30 -i 16 -p a=b"}, "variants": {"a": "", "b": "-Dq"}, "testbed": "m4",
                   "builds": {"a": {"checkout": "../a"}, "b": {"checkout": "../b"}}}, open(parent, "w"))
        s = asm.capture_spec(parent, ["a.B::f"])
        self.assertEqual((s["name"], s["asmOf"], s["asm"], s["rounds"], s["testbed"]), ("p-asm", "p", ["a.B::f"], 1, "m4"))
        self.assertEqual(s["corpora"]["x"], "-f 1 -i 2 -wi 30 -p a=b")
        self.assertNotIn("profile", s)
        self.assertNotIn("loadgate", s)
        self.assertEqual(s["builds"], {"a": {"checkout": "../a"}, "b": {"checkout": "../b"}})
        self.assertEqual(asm.capture_spec(parent, ["a.B::f"], on="m5")["testbed"], "m5")

    def test_refuse_timing(self):
        timed = os.path.join(self.camps, "t", "x", "a", "1")
        os.makedirs(timed)
        json.dump({"name": "t"}, open(os.path.join(self.camps, "t", "spec.json"), "w"))
        with self.assertRaises(SystemExit):
            asm.refuse_timing(self.cell, timed)
        asm.refuse_timing(self.cell, os.path.join(self.camp, "x", "b", "1"))

    def test_jvm_flags_keep_the_disassembly_out_of_stdout(self):
        f = asm.jvm_flags(["a.B::f"], "/c")
        self.assertIn("-XX:-DisplayVMOutput", f)
        self.assertIn("-XX:LogFile=/c/vm-%p.log", f)
        self.assertIn("-XX:CompileCommand=print,a.B::f", f)

    def test_hsdis_missing(self):
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, "bin"))
        os.makedirs(os.path.join(home, "lib"))
        open(os.path.join(home, "release"), "w").write('OS_NAME="Darwin"\nOS_ARCH="aarch64"\n')
        java = os.path.join(home, "bin", "java")
        self.assertIn("mise run tools:hsdis", asm.check_hsdis(java))
        open(os.path.join(home, "lib", "hsdis-aarch64.dylib"), "w").close()
        self.assertIsNone(asm.check_hsdis(java))

    def test_stdout_format(self):
        """jmh.log as a fork without LogVMOutput prints it: the same compilations."""
        d = tempfile.mkdtemp()
        text = open(os.path.join(FIXTURE, "a.log")).read()
        body = text[text.index("============================= C1"):text.index("[/Disassembly]") + len("[/Disassembly]")]
        open(os.path.join(d, "jmh.log"), "w").write("# Warmup Iteration 1\n" + body.replace("&apos;", "'") + "\n# Run complete\n")
        idx = asm.split(d, [os.path.join(d, "jmh.log")])
        self.assertEqual([(c["compileId"], c["compiler"], c["level"]) for c in idx], [(2, "c1", 3)])
        self.assertTrue(os.path.exists(os.path.join(d, "jmh.log")))


if __name__ == "__main__":
    unittest.main()
