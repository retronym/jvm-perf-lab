"""`perflab mcp`: perflab.api as a Model Context Protocol server on stdio, for agents (Claude Code:
`claude mcp add perflab -- perflab mcp`, run from the project; or `perflab mcp --root <project>`).

  perflab mcp [--root <project>]

Every api function is a tool, with its parameters' schema as the tool's inputSchema and its result's as its
outputSchema; a call returns the result as structuredContent and as JSON text. Reads work on the project's files
with no server running; actions (void, unvoid, rerun, submit, pause, resume, cancel, set_priority, move) are POSTed
to the running `perflab server`, and fail without one.

The transport is MCP's stdio one: JSON-RPC 2.0 messages, one per line, on stdin and stdout (logs go to stderr).
Requests: initialize, ping, tools/list, tools/call, resources/list (the API's conventions and OpenAPI document),
resources/read; notifications are accepted and ignored.
"""
import json, os, sys, traceback

from . import api

PROTOCOL = "2025-06-18"
SUPPORTED = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "perflab runs JMH benchmarks as campaigns: variants (JVM flags, builds, or a branch's commits) over corpora, round by "
    "round; each run is a cell <campaign>/<corpus>/<variant>/<round>. Start with `campaigns`, then `campaign` (its summary: "
    "every metric's mean ± 99.9% CI over forks, Δ vs the baseline, verdict better/worse/flat/na) or, for a branch campaign, "
    "`branch` and `changes` (the commits that moved a metric significantly). `cell` has a run's raw samples, iterations, "
    "load, GC and logs; `compare` any two variants or commits; `profiles` and `diff` flame graphs and the methods whose "
    "time changed. A disturbed cell can be voided (`void`, with a reason) and run again (`rerun`): actions need "
    "`perflab server`. Lower counts as better for every metric. URLs are paths on the server: http://127.0.0.1:8690, or the name a local proxy "
    "gives it (https://perflab.localhost with `portless alias perflab 8690`).")
RESOURCES = {"perflab://api/conventions": ("conventions", "How responses, errors, units and statistics work", lambda: api.CONVENTIONS),
             "perflab://api/openapi.json": ("openapi", "The HTTP API's OpenAPI 3.1 document (the same functions and schemas)", api.openapi)}


def tools():
    out = []
    for f in api.FUNCTIONS.values():
        out.append({"name": f.name, "title": f.summary, "description": f.description + _fields(f.result)
                    + ("" if f.kind == "read" else "\n\nAn action: needs a running `perflab server`."),
                    "inputSchema": f.input_schema(),
                    "outputSchema": api.schema_of(f.result, examples=False),
                    "annotations": {"readOnlyHint": f.kind == "read", "destructiveHint": f.name in ("void", "cancel"),
                                    "idempotentHint": f.kind == "read" or f.name == "rerun", "openWorldHint": False}})
    return out


def _fields(name):
    """The result's top-level fields, for the description (the outputSchema has the rest)."""
    props = api.SCHEMAS[name]["properties"]
    return "\n\nReturns " + name + ": " + "; ".join(f"{k}: {v.get('description', '')}" for k, v in props.items() if k not in ("schema", "version"))


def handle(msg):
    """The response to one JSON-RPC message, None for a notification."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:  # notifications/initialized, notifications/cancelled, ...
        return None
    try:
        if method == "initialize":
            v = params.get("protocolVersion")
            return _ok(mid, {"protocolVersion": v if v in SUPPORTED else PROTOCOL,
                             "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
                             "serverInfo": {"name": "perflab", "title": "perflab", "version": "0.1.0"},
                             "instructions": INSTRUCTIONS})
        if method == "ping":
            return _ok(mid, {})
        if method == "tools/list":
            return _ok(mid, {"tools": tools()})
        if method == "tools/call":
            return _ok(mid, call(params.get("name"), params.get("arguments") or {}))
        if method == "resources/list":
            return _ok(mid, {"resources": [{"uri": u, "name": n, "description": d, "mimeType": "application/json"} for u, (n, d, _) in RESOURCES.items()]})
        if method == "resources/read":
            r = RESOURCES.get(params.get("uri"))
            if r is None:
                return _err(mid, -32602, f"no resource {params.get('uri')!r}")
            return _ok(mid, {"contents": [{"uri": params["uri"], "mimeType": "application/json", "text": json.dumps(r[2](), indent=1)}]})
        return _err(mid, -32601, f"method not found: {method}")
    except Exception as e:  # a bug: the client gets an error, the server goes on
        traceback.print_exc(file=sys.stderr)
        return _err(mid, -32603, f"{type(e).__name__}: {e}")


def call(name, args):
    """A tools/call result: the function's result as structuredContent and text, or its error with isError."""
    if name not in api.FUNCTIONS:
        return _tool_error(api.ApiError("not_found", f"no tool {name!r}", {"tools": sorted(api.FUNCTIONS)}))
    try:
        out = api.call(name, args)
    except api.ApiError as e:
        return _tool_error(e)
    return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "structuredContent": out, "isError": False}


def _tool_error(e):
    return {"content": [{"type": "text", "text": json.dumps(e.body(), ensure_ascii=False)}], "isError": True}


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(inp=None, out=None):
    inp, out = inp or sys.stdin, out or sys.stdout
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = _err(None, -32700, "parse error")
        else:
            if isinstance(msg, list):  # a batch (2025-03-26)
                resp = [r for r in (handle(m) for m in msg if isinstance(m, dict)) if r is not None] or None
            elif isinstance(msg, dict):
                resp = handle(msg) if "method" in msg else None  # a response to us: we send no requests
            else:
                resp = _err(None, -32600, "invalid request")
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    root = os.environ.get("PERFLAB_ROOT") or os.getcwd()
    if argv[:1] == ["--root"] and len(argv) > 1:
        root = os.path.abspath(argv[1])
    api.DEFAULT_ROOT = root
    serve()
    return 0
