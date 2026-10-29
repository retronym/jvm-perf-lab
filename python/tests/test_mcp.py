import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
os.environ["PERFLAB_SERVER_HOME"] = tempfile.mkdtemp()  # never a real `perflab server`, even when run alone
from perflab import api, config, mcp  # noqa: E402
from test_api import Fixture, V  # noqa: E402


class McpProcessTest(Fixture, unittest.TestCase):
    """`perflab mcp` over a pipe, as a client (Claude Code) runs it: newline-delimited JSON-RPC on stdio."""

    def setUp(self):
        super().setUp()
        env = {**os.environ, "PYTHONPATH": SRC, "PERFLAB_SERVER_HOME": tempfile.mkdtemp()}
        self.p = subprocess.Popen([sys.executable, "-m", "perflab", "mcp", "--root", self.root], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        self.addCleanup(self.close)
        self.n = 0

    def close(self):
        self.p.stdin.close()
        self.p.wait(10)
        self.p.stdout.close()
        self.p.stderr.close()

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        if notify:
            return None
        r = json.loads(self.p.stdout.readline())
        self.assertEqual((r["jsonrpc"], r["id"]), ("2.0", self.n))
        return r

    def test_handshake_list_and_call(self):
        r = self.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
        res = r["result"]
        self.assertEqual(res["protocolVersion"], "2025-06-18")
        self.assertEqual(res["serverInfo"]["name"], "perflab")
        self.assertIn("tools", res["capabilities"])
        self.assertTrue(res["instructions"])
        self.send("notifications/initialized", notify=True)  # no response
        tools = {t["name"]: t for t in self.send("tools/list")["result"]["tools"]}
        self.assertEqual(set(tools), set(api.FUNCTIONS))
        t = tools["campaign"]
        self.assertEqual(t["inputSchema"]["required"], ["campaign"])
        self.assertEqual(t["inputSchema"]["type"], "object")
        self.assertEqual(t["outputSchema"]["type"], "object")
        self.assertTrue(t["annotations"]["readOnlyHint"])
        self.assertFalse(tools["void"]["annotations"]["readOnlyHint"])
        self.assertIn("perflab server", tools["void"]["description"])

        r = self.send("tools/call", {"name": "changes", "arguments": {"campaign": "br"}})["result"]
        self.assertFalse(r["isError"])
        out = r["structuredContent"]
        self.assertEqual(json.loads(r["content"][0]["text"]), out)
        self.assertEqual(api.validate(out, tools["changes"]["outputSchema"], tools["changes"]["outputSchema"]["$defs"]), [])
        self.assertIn(V[4], [c["variant"] for c in out["changes"]])

        r = self.send("tools/call", {"name": "campaign", "arguments": {"campaign": "nope"}})["result"]
        self.assertTrue(r["isError"])
        self.assertEqual(json.loads(r["content"][0]["text"])["error"]["code"], "not_found")
        r = self.send("tools/call", {"name": "void", "arguments": {"campaign": "br", "corpus": "a", "variant": V[0], "round": 1, "reason": "x"}})["result"]
        self.assertEqual((r["isError"], json.loads(r["content"][0]["text"])["error"]["code"]), (True, "no_server"))
        self.assertTrue(os.path.isdir(os.path.join(self.br, "a", V[0], "1")))

        self.assertEqual(self.send("ping")["result"], {})
        self.assertEqual(self.send("bogus/method")["error"]["code"], -32601)
        rs = self.send("resources/list")["result"]["resources"]
        self.assertIn("perflab://api/openapi.json", [x["uri"] for x in rs])
        doc = json.loads(self.send("resources/read", {"uri": "perflab://api/openapi.json"})["result"]["contents"][0]["text"])
        self.assertEqual(doc["openapi"], "3.1.0")


class McpUnitTest(unittest.TestCase):
    def test_an_unknown_protocol_version_gets_ours(self):
        r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(r["result"]["protocolVersion"], mcp.PROTOCOL)

    def test_parse_error_and_batch(self):
        import io
        out = io.StringIO()
        mcp.serve(io.StringIO('not json\n[{"jsonrpc":"2.0","id":7,"method":"ping"},{"jsonrpc":"2.0","method":"notifications/x"}]\n'), out)
        a, b = [json.loads(l) for l in out.getvalue().splitlines()]
        self.assertEqual(a["error"]["code"], -32700)
        self.assertEqual(b, [{"jsonrpc": "2.0", "id": 7, "result": {}}])

    def test_every_tool_is_described_with_its_result(self):
        for t in mcp.tools():
            self.assertIn("Returns " + api.FUNCTIONS[t["name"]].result, t["description"])
            self.assertEqual(t["outputSchema"]["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
