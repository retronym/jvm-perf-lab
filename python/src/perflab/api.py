"""perflab's API: campaigns, cells, branch history, comparisons, profiles and their diffs as JSON, and the actions an
agent takes on them (void a cell, rerun a campaign, submit and control jobs). One module, three transports:

  HTTP   `perflab server`: GET /api/v1/<function>?<params> for reads, POST /api/v1/<function> {params} for actions
         (token in X-Perflab-Token); GET /api/v1 is the index, /api/v1/openapi.json the OpenAPI 3.1 document, /api/v1/docs
         the reference page
  MCP    `perflab mcp`: every function a tool (perflab.mcp), with these schemas as its input and output schemas
  CLI    `perflab api <function> [--<param> <value>]...`, `perflab api --list`, `perflab api --schema <name>`

Every function returns a JSON object whose "schema" names its schema in SCHEMAS (JSON Schema 2020-12, every field
described, units included) and whose "version" is API_VERSION; over HTTP an error is {"error": {"code", "message",
"details"?}} with the HTTP status of its code (ERRORS), and the same object is the CLI's output and an MCP tool's error.

Reads work on a project's files, without a server: `project` is a server project id, a project root (a directory with
perflab.toml), or omitted (the project of the working directory; on the server, the only registered project). Actions
change what the server owns (its queue, the cells a job may be running), so they run in the server: called from MCP or
the CLI, they are POSTed to it, and with no server running they fail with code "no_server".
"""
import contextlib, datetime, glob, inspect, json, math, os, re, shutil, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request

from . import ab, branchview, config, index, loadgate, metrics, server as srv, storage

API_VERSION = 1
VOID_DIR = ".void"
VOID_NOTE = "void.txt"  # the reason, as text
VOID_JSON = "void.json"  # {reason, voided, from}
STATES = ("done", "running", "failed", "interrupted", "pending", "unbuildable", "void")
VERDICTS = ("better", "worse", "flat", "na")
ERRORS = {"bad_request": 400, "forbidden": 403, "not_found": 404, "conflict": 409, "no_server": 503, "internal": 500}


class ApiError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details

    @property
    def status(self):
        return ERRORS.get(self.code, 500)

    def body(self):
        return {"error": {"code": self.code, "message": self.message, **({"details": self.details} if self.details is not None else {})}}


# ---- schemas: JSON Schema 2020-12, one registry; OpenAPI and MCP are generated from it

SCHEMAS = {}
REF = "#/$defs/"


def ref(name):
    return {"$ref": REF + name}


def T(t, d, **kw):
    return {"type": t, "description": d, **kw}


def S(d, **kw): return T("string", d, **kw)
def I(d, **kw): return T("integer", d, **kw)
def N(d, **kw): return T("number", d, **kw)
def B(d, **kw): return T("boolean", d, **kw)


def null(s):
    """`s` or null."""
    t = s.get("type")
    if t and "$ref" not in s:
        return {**s, "type": [t, "null"] if isinstance(t, str) else [*t, "null"]}
    return {"anyOf": [s, {"type": "null"}], **({"description": s["description"]} if "description" in s else {})}


def A(items, d, **kw):
    return {"type": "array", "items": items, "description": d, **kw}


def M(values, d):
    """A map from names to `values`."""
    return {"type": "object", "additionalProperties": values, "description": d}


def O(d, props, optional=(), extra=False):
    """An object of `props`, every one required but those in `optional`."""
    return {"type": "object", "description": d, "properties": props, "required": [k for k in props if k not in optional],
            "additionalProperties": extra}


def define(name, d, props, optional=(), extra=False, top=False):
    """A schema in SCHEMAS; a `top` one is a response, with "schema" and "version"."""
    if top:
        props = {"schema": {"const": name, "type": "string", "description": "This object's schema: #/components/schemas/" + name},
                 "version": {"const": API_VERSION, "type": "integer", "description": "The API version"}, **props}
    SCHEMAS[name] = O(d, props, optional, extra)
    return name


def envelope(name, **body):
    return {"schema": name, "version": API_VERSION, **body}


URL = null(S("A path on the perflab server (prefix it with the server's URL, http://127.0.0.1:8690); null when the file is "
             "not served (outside the campaigns and runs, or under a directory whose name starts with a dot)"))
PATH = S("An absolute path on this machine")
WHEN = null(N("Seconds since the epoch"))
PROJECT_P = S("The project: a server project id (see projects), or a project root directory (with perflab.toml); omitted, "
              "the project of the working directory (on the server: the only registered project)")
CAMPAIGN_P = S("The campaign's name: its directory under the project's campaigns directory")
METRIC_KEY = S("A metric's key (see `metrics`): score, cycles, instructions, ipc, alloc, ev:<event>, ev:<event>/kinst, "
               "ev:<event>/cycles, td:<slot>, cyc%:<group>, ipc:<group>, cycles:all, instructions:all, ipc:all")

define("Error", "An error: the body of every non-2xx response, and of an MCP tool result with isError", {
    "error": O("What went wrong", {
        "code": S("Machine-readable: bad_request (400), forbidden (403), not_found (404), conflict (409; the state does not "
                  "allow it, e.g. voiding the running cell), no_server (503; an action needs `perflab server`), internal (500)",
                  enum=list(ERRORS)),
        "message": S("For a human or an LLM: what failed and, where there is one, what to do instead"),
        "details": {"description": "More about it, e.g. the names that were valid"}}, optional=("details",))})

define("Project", "A perflab project: a directory with perflab.toml, and where its campaigns and runs are", {
    "id": S("Its id on the server (the `project` parameter takes it)"),
    "name": S("Its directory's name"),
    "root": PATH,
    "campaigns": S("Its campaigns directory (`perflab ab`): <campaigns>/<campaign>/<corpus>/<variant>/<round>/ are the cells"),
    "runs": null(S("Its runs directory (`perflab run`)")),
    "registered": B("Whether the server knows it (a registered project's files are served under /p/<id>/)"),
    "index": URL})
define("Projects", "The projects the server has registered, and the working directory's", {
    "projects": A(ref("Project"), "Registered ones by name, then the working directory's if it is not one of them")}, top=True)

PROGRESS = O("How many of the campaign's planned cells are where", {
    "planned": I("Cells the spec plans: rounds × corpora × variants (a branch campaign's variants are its commits)"),
    "done": I("Cells with a result"), "running": I("Cells running now (or with a partial result.json while running)"),
    "failed": I("Cells whose run failed (failed.txt; a branch campaign records why and goes on)"),
    "interrupted": I("Cells with an empty or partial result.json and no run: `ab run` runs them again"),
    "unbuildable": I("Planned cells of commits that did not build (skipped until --retry-unbuildable)"),
    "void": I("Cells voided (moved to <campaign>/.void/, see voids); not counted as done")})
BYTES = O("Storage by tier, in allocated bytes (perflab.storage)", {
    "results": I("result.json, iterations.tsv, logs, timelines: kept"), "profiles": I("Recordings and rendered graphs"),
    "builds": I("Launch-mode snapshots and the campaign's worktree: rebuildable"), "total": I("All three")})
JOB_REF = O("A job of the server's queue that runs this campaign", {"id": I("The job's id"),
            "state": S("Its state", enum=list(srv.STATES)), "argv": A(S("argument"), "`perflab <argv>`")})

define("CampaignSummary", "One campaign, as campaigns lists it", {
    "name": S("Its name"),
    "kind": S("plain: variants of JVM flags or builds; paired: variants alternating within forks; branch: a commit range, "
              "a variant per commit (see branch); profile: a branch campaign's profiles (<branch>.profile)",
              enum=["plain", "paired", "branch", "profile"]),
    "benchmark": null(S("The JMH benchmark")), "profile": S("The profiler of every cell: none, xctrace:<template>, async:<events>"),
    "rounds": I("Rounds: each round runs every corpus and variant once"),
    "corpora": A(S("corpus"), "The corpora (the benchmark's corpus @Param), in the spec's order"),
    "variants": A(S("variant"), "The variants in the spec's order (the first is the baseline); a branch campaign's commits "
                  "oldest first, by short sha"),
    "description": null(S("The spec's description (Markdown)")),
    "progress": PROGRESS,
    "status": S("running (a cell runs, or a job of the queue is running it), finished (every planned cell has a result), "
                "partial (some do), empty (none yet)", enum=["running", "finished", "partial", "empty"]),
    "updated": WHEN, "updatedIso": null(S("`updated` in ISO 8601, local time")),
    "bytes": null({**BYTES, "description": "Storage by tier (only with storage=true: it walks every file)"}),
    "profileOf": null(S("For a profile campaign: the branch campaign it profiles")),
    "profiles": null(S("For a branch campaign: its profile campaign, when it has one")),
    "jobs": A(JOB_REF, "Queued, running or paused jobs of the server that run this campaign"),
    "url": URL})
define("Campaigns", "The campaigns of a project, newest first", {
    "project": ref("Project"), "campaigns": A(ref("CampaignSummary"), "Newest first (by `updated`)")}, top=True)

define("Delta", "A change against another variant or commit: Welch's t on the forks' means, at 99.9%", {
    "pct": N("Δ in percent of the other's mean: 100 × (this / other − 1)"),
    "halfWidth": null(N("Half-width of Δ's 99.9% confidence interval, in percentage points (Welch–Satterthwaite df); null "
                        "without a spread on either side")),
    "verdict": S("better: lower, significantly (|pct| > halfWidth; perflab counts lower as better for every metric, even "
                 "IPC); worse: higher, significantly; flat: not significant, or no spread; na: the other's value is about "
                 "zero, so a percent change means nothing", enum=list(VERDICTS)),
    "against": S("The variant (or commit) this is against"),
    "pooled": B("Whether either side has one fork and borrowed the campaign's pooled spread")})
define("Stat", "One metric of one variant (or commit) on one corpus, over its forks. The unit of variation is the fork: "
       "each fork of each round counts once, as the mean of its measurement iterations", {
    "mean": null(N("Mean over the forks, in the metric's unit (see the metric's label: e.g. ms/op for the score, bytes per "
                   "op for alloc, events per op for counts, a ratio for IPC, percent for pct)")),
    "sd": null(N("Standard deviation of the forks' means (the pooled one for a single fork); null without a spread")),
    "ci": null(N("Half-width of the mean's 99.9% confidence interval: t(df) × sd / √n")),
    "n": I("Forks"), "df": null(N("Degrees of freedom of sd (n − 1, or the pool's)")),
    "pooled": B("One fork: sd is the fork-to-fork relative sd pooled over the corpus's variants with two or more"),
    "shown": S("The mean as the index shows it, with its unit (e.g. 5.25 s, 1.2 GB)"),
    "ciShown": S("The CI half-width as the index shows it ('' without one)"),
    "delta": null({**ref("Delta"), "description": "Δ against the baseline (campaign, compare) or the previous measured commit (branch)"})},
    optional=("delta",))
define("MetricInfo", "A metric the cells recorded (perflab.metrics.of)", {
    "key": METRIC_KEY, "label": S("Its label, with its unit: e.g. ms/op, cycles/op, alloc/op (bytes), IPC, JIT % of cycles"),
    "kind": S("score: the benchmark's primary score (its unit in the label); count: events per op; alloc: bytes per op; "
              "ratio: a ratio (IPC, events per 1,000 instructions); pct: percent", enum=["score", "count", "alloc", "ratio", "pct"]),
    "main": B("Whether the index's summary table shows it (the others are in its pivot and chart)")})
define("SummaryRow", "One corpus × variant of a campaign's summary", {
    "corpus": S("The corpus"), "variant": S("The variant"), "rounds": I("Rounds with a result"),
    "forks": I("Forks over those rounds"),
    "metrics": M(ref("Stat"), "By metric key: its value over forks, with Δ against the baseline"),
    "card": M(O("The index card's own numbers: over rounds, not forks", {
        "mean": null(N("Mean over rounds")), "sd": null(N("sd over rounds (null with one)")),
        "pct": null(N("Δ% against the baseline")), "spread": null(N("Spread of Δ in percentage points, from both sides' sd over rounds")),
        "verdict": S("As Delta.verdict, against the spread", enum=list(VERDICTS) + [""])}), "By metric key, as the index card shows them")})
LINKS = O("Pages of the campaign on the server", {
    "card": URL, "spec": URL, "report": URL,
    "timelines": A(O("A cell's timeline", {"corpus": S("corpus"), "variant": S("variant"), "round": I("round"), "url": URL}),
                   "Every cell's timeline (each fork from JVM start to exit)"),
    "graphs": A(ref("Graph"), "Flame graphs of the profiled cells"),
    "diffs": A(ref("DiffRef"), "profdiff outputs (differential flame graphs) of pairs of cells")})
define("VariantInfo", "A variant of a campaign", {
    "name": S("Its name (a branch campaign's: the commit's short sha)"),
    "description": null(S("variantDescriptions (Markdown), or the commit's subject")),
    "flags": S("JVM flags it adds to jvmArgs"), "jmhArgs": S("JMH arguments it adds (variantJmhArgs)"),
    "build": null(O("Its own build, in launch mode", {"checkout": null(S("The checkout it builds")),
                                                      "commit": null(S("The commit (a branch campaign's)"))})),
    "baseline": B("Whether Δ is against it (the first variant)")})
define("Campaign", "One campaign in full: its spec, variants, corpora and summary, and links to its pages", {
    "campaign": ref("CampaignSummary"),
    "spec": {"type": "object", "description": "The campaign's spec.json, as `perflab ab run` documents it"},
    "variantInfo": A(ref("VariantInfo"), "The variants, in order"),
    "corpusInfo": A(O("A corpus", {"name": S("Its name"), "jmhArgs": S("Its JMH arguments")}), "The corpora"),
    "baseline": null(S("The variant Δ is against")),
    "perUnit": null(S("The spec's perUnit: counts, allocation and the score are per this aux counter's unit, not per op")),
    "metrics": A(ref("MetricInfo"), "The metrics the cells recorded, the score first"),
    "summary": A(ref("SummaryRow"), "Per corpus and variant (rows of variants with a result)"),
    "links": LINKS}, top=True)

define("CellSummary", "One cell: a variant's run on a corpus in a round, <campaign>/<corpus>/<variant>/<round>/", {
    "corpus": S("The corpus"), "variant": S("The variant"), "round": I("The round, from 1"),
    "state": S("done: has a result; running: running now; failed: its run failed (why); interrupted: an empty or partial "
               "result.json, run again by a resume; pending: not run yet; unbuildable: its commit did not build; void: "
               "voided (moved to .void)", enum=list(STATES)),
    "score": null(N("JMH's score, in `unit`")), "error": null(N("JMH's score error (99.9%), in `unit`")),
    "unit": null(S("The score's unit, e.g. ms/op")),
    "finished": WHEN, "why": null(S("Why it failed, or why it was voided")),
    "voidId": null(S("For a void cell: its id for unvoid (<corpus>/<variant>/<round>-<timestamp>)")),
    "path": null(PATH), "url": URL, "timeline": URL})
define("Cells", "A campaign's cells, planned ones included", {
    "campaign": S("The campaign"), "cells": A(ref("CellSummary"), "By round, corpus and variant order")}, top=True)

FILE = O("A file", {"name": S("Its path relative to the cell"), "bytes": I("Its size"), "path": PATH, "url": URL})
define("Graph", "A rendered flame graph", {"corpus": null(S("corpus")), "variant": null(S("variant")), "round": null(I("round")),
                                           "event": S("The event: cpu, alloc, wall, lock, cycles, ..."),
                                           "kind": S("The graph kind: bench, reverse, classify, threads, ..."), "url": URL,
                                           "path": PATH}, optional=("corpus", "variant", "round"))
define("Cell", "One cell in full: its result, every metric and sample, its iterations, load, GC, profile and logs", {
    "cell": ref("CellSummary"),
    "result": null(O("The essentials of JMH's result.json", {
        "benchmark": S("The benchmark method"), "mode": S("JMH mode: avgt, thrpt, ss, sample"),
        "score": N("The score, in unit"), "error": null(N("Its error (99.9%)")), "unit": S("e.g. ms/op"),
        "params": M(S("value"), "The @Params"), "jvm": null(S("The JVM")), "jvmArgs": A(S("arg"), "The fork's JVM arguments"),
        "jdkVersion": null(S("JDK version")), "vmName": null(S("VM name")), "vmVersion": null(S("VM version")),
        "forks": null(I("Forks")), "warmupIterations": null(I("Warmup iterations per fork")), "warmupTime": null(S("Per warmup iteration")),
        "measurementIterations": null(I("Measurement iterations per fork")), "measurementTime": null(S("Per measurement iteration"))})),
    "metrics": A(O("A metric's value in this cell", {"key": METRIC_KEY, "label": S("Label with unit"),
                                                      "kind": S("As MetricInfo.kind"), "value": N("JMH's value: the mean over the cell's forks")}),
                 "Every metric perflab.metrics.of derives from the result"),
    "raw": M(A(A(N("x"), "One fork's measurement iterations"), "Per fork"),
             "By metric key, for metrics with per-iteration samples (rawData): each fork's measurement iterations, in the metric's unit"),
    "iterations": A({"type": "object", "description": "A row of iterations.tsv: index, kind (startup, warmup, measure), "
                     "variant, start_ms and end_ms (epoch ms), score, ops, gc_ms, pid, unit, alloc_bytes (numbers where they parse)"},
                    "Every iteration of every fork as the fork logged it (iterations.tsv)"),
    "load": null(O("Competing load per measurement iteration (the load gate)", {
        "source": S("load.json (the gate's record) or load.tsv (computed now)", enum=["load.json", "load.tsv"]),
        "maxCores": null(N("The gate's limit, in cores")),
        "disturbed": A(I("index"), "Measurement iterations over the limit"),
        "iterations": A({"type": "object", "description": "index, start and end (epoch s), score, cores (the highest sample "
                         "overlapping it, in cores of other processes), top (the processes)"}, "Per measurement iteration")})),
    "gc": O("Garbage collection", {"metrics": M(O("A gc.* secondary metric", {"score": null(N("value")), "unit": S("unit")}),
                                                "JMH's -prof gc metrics: gc.alloc.rate (MB/sec), gc.alloc.rate.norm (B/op), gc.count, gc.time (ms)"),
                                   "log": null(FILE)}),
    "profile": O("The cell's profile", {"profiler": S("profile.txt: none, xctrace:<template>, async:<events>"),
                                        "recordings": A(FILE, "Recordings: .jfr, .trace"),
                                        "graphs": A(ref("Graph"), "Rendered flame graphs"),
                                        "hwEvents": M(N("events per op"), "An async kperf profile's events per op on the benchmark threads")}),
    "logs": M(O("A log", {**FILE["properties"], "tail": null(S("Its last `tail` lines (with tail > 0)"))}),
              "build.log (the build tool's output), jmh.log (JMH's), gc.log"),
    "files": A(FILE, "Every file of the cell"),
    "specVersion": null(S("The spec version it ran under (<campaign>/specs/<version>.json)")),
    "void": null(O("Why it was voided", {"reason": S("reason"), "voided": WHEN}))}, top=True)

define("BranchCell", "A commit on one corpus", {
    "state": S("As CellSummary.state, for the commit's cells together", enum=list(STATES)),
    "rounds": I("Rounds with a result"), "forks": I("Forks over them"), "why": null(S("Why its run failed")),
    "metrics": M(ref("Stat"), "By metric key; delta is against `previous`"),
    "previous": null(S("The previous commit with a result on this corpus, Δ's base")),
    "raw": M(A(A(N("x"), "fork"), "forks"), "With raw=true: by metric key, each fork's measurement iterations")},
    optional=("raw",))
define("BranchCommit", "A commit of a branch campaign", {
    "index": I("Its position in history, from 0 (the base)"), "sha": S("Full sha"), "short": S("Short sha"),
    "variant": S("Its variant (the campaign's name for it)"), "subject": S("Commit subject"), "author": S("Author"),
    "date": S("Commit date, ISO 8601"),
    "merged": A(O("A commit a merge brought in", {"sha": S("sha"), "subject": S("subject")}), "For a first-parent merge: the commits it brought in"),
    "unbuildable": null(O("It did not build", {"reason": S("Why"), "log": URL})),
    "corpora": M(ref("BranchCell"), "By corpus; a corpus it has no cells on is absent"),
    "profiled": A(S("corpus"), "Corpora with a profile of it in the profile campaign")})
define("Branch", "A branch campaign's history: commits oldest first, per corpus each metric's mean, CI and Δ against the "
       "previous measured commit (the data of the index's history view, perflab.branchview)", {
    "campaign": S("The campaign"), "range": S("The git range, base..tip"), "checkout": null(S("The repository")),
    "corpora": A(S("corpus"), "Corpora with results, then the spec's others"), "perUnit": null(S("As Campaign.perUnit")),
    "metrics": A(O("A metric", {"key": METRIC_KEY, "label": S("Label with unit"), "kind": S("As MetricInfo.kind")}), "The metrics, the score first"),
    "commits": A(ref("BranchCommit"), "Oldest first"),
    "profile": null(S("The profile campaign (see profiles)")),
    "diffs": A(ref("DiffRef"), "Diffs of pairs of commits")}, top=True)
define("Change", "A significant step between neighbouring measured commits", {
    "corpus": S("corpus"), "metric": METRIC_KEY, "variant": S("The commit's variant"), "sha": S("Its sha"),
    "subject": S("Its subject"), "index": I("Its position in history"), "previous": S("The previous measured commit's variant"),
    "mean": null(N("Its mean")), "previousMean": null(N("The previous one's mean")), "shown": S("Its mean, shown"),
    "delta": ref("Delta")})
define("Changes", "The commits whose Δ against the previous measured commit is significant at 99.9%, largest |Δ| first", {
    "campaign": S("The campaign"), "metric": METRIC_KEY, "changes": A(ref("Change"), "Largest |Δ| first"),
    "untested": A(O("A step that could not be tested", {"corpus": S("corpus"), "variant": S("The commit's variant"),
                                                       "previous": S("The previous measured commit"), "pct": null(N("Its Δ%"))}),
                  "Steps with no spread on either side (one fork each and nothing to pool): no verdict either way, largest |Δ| first")}, top=True)
SIDE = O("One side of a comparison", {"mean": null(N("Mean over forks")), "ci": null(N("99.9% CI half-width")), "n": I("Forks"),
                                      "shown": S("Mean, shown")})
define("Compare", "Two variants (or commits) of a campaign: every metric's Δ of b against a, per corpus", {
    "campaign": S("The campaign"), "a": S("Variant a, the base"), "b": S("Variant b"),
    "corpora": A(O("One corpus", {"corpus": S("corpus"), "metrics": A(O("One metric", {
        "key": METRIC_KEY, "label": S("Label with unit"), "kind": S("As MetricInfo.kind"), "a": SIDE, "b": SIDE,
        "delta": null({**ref("Delta"), "description": "Δ of b against a; null when a's mean is zero"})}), "Metrics both have")}), "Corpora both have results on"),
    "diffs": A(ref("DiffRef"), "profdiff outputs of this pair (see diff)")}, top=True)
define("DiffRef", "A profdiff output: differential flame graphs of two cells", {
    "name": S("Its directory's name, without diff-"), "campaign": S("The campaign it is in"),
    "a": null(S("Variant a, when known")), "b": null(S("Variant b")), "corpus": null(S("corpus, when known")),
    "url": URL, "path": PATH})
define("Profiles", "A campaign's profiled cells and their diffs (for a branch campaign: those of its profile campaign too)", {
    "campaign": S("The campaign"), "graphs": A(ref("Graph"), "Flame graphs of every profiled cell"),
    "diffs": A(ref("DiffRef"), "Diffs")}, top=True)
define("Diff", "The profdiff outputs of a pair: per event its pages and the table of methods whose self time per op changed most", {
    "campaign": S("The campaign"), "a": S("a"), "b": S("b"),
    "diffs": A(O("One profdiff output directory", {**SCHEMAS["DiffRef"]["properties"], "events": A(O("One event", {
        "event": S("cpu, alloc, cycles, ..."),
        "pages": M(URL, "a: a's graph, diff: the differential graph a → b, inverse: b → a, b: b's graph"),
        "summary": null(S("The table's first line: the event per op of a and b and Δ")),
        "rows": A(O("A method", {"delta": null(N("Δ of self events per op, b − a")), "a": null(N("a's self events per op")),
                                 "b": null(N("b's")), "pctOfTotal": null(N("Δ as % of a's total")), "method": S("The method"),
                                 "shown": S("The row as profdiff printed it")}),
                  "Biggest decreases, then biggest increases (table-<event>.md)"),
        "table": null(S("table-<event>.md, as text"))}), "Events diffed")}), "One per corpus diffed")}, top=True)

define("Void", "A voided cell", {"id": S("Its id for unvoid: <corpus>/<variant>/<round>-<timestamp>"), "corpus": S("corpus"),
                                 "variant": S("variant"), "round": I("round"), "reason": S("Why it was voided"), "voided": WHEN,
                                 "path": PATH, "restorable": B("Whether unvoid can put it back (its place is free)")})
define("Voids", "A campaign's voided cells", {"campaign": S("The campaign"), "voids": A(ref("Void"), "Newest first")}, top=True)
define("Voided", "A cell, voided: moved out of the campaign so that a resume runs it again", {
    "campaign": S("The campaign"), "void": ref("Void"), "from": PATH}, top=True)
define("Unvoided", "A voided cell, put back", {"campaign": S("The campaign"), "cell": ref("CellSummary"), "from": PATH}, top=True)
define("Job", "A job of the server's queue: a perflab command line", {
    "id": I("Its id"), "project": S("Its project's id"), "argv": A(S("arg"), "`perflab <argv>`"), "cwd": S("Where it runs"),
    "state": S("queued, running, paused, done, failed, cancelled", enum=list(srv.STATES)), "priority": I("Higher runs first"),
    "created": WHEN, "started": WHEN, "ended": WHEN, "rc": null(I("Exit status")), "note": null(S("Why it failed to start, etc.")),
    "position": null(I("Its place in the queue, from 1, while queued")), "url": URL, "transcript": null(S("Its transcript file")),
    "control": null(S("A pending control request: pause or cancel")), "envKeys": A(S("name"), "Its environment's names")},
    optional=("position", "url", "control", "envKeys", "transcript", "note"), extra=True)
define("Jobs", "The server's queue: running and paused, then queued in order, then finished (newest first)", {
    "jobs": A(ref("Job"), "Jobs")}, top=True)
define("JobResult", "A job", {"job": ref("Job")}, top=True)
define("Transcript", "A job's transcript", {"id": I("The job"), "text": S("Its transcript (or its last `tail` lines)")}, top=True)
define("Rerun", "A resume of a campaign (`perflab ab run <campaign>/spec.json`) on the server's queue, queued once", {
    "campaign": S("The campaign"), "argv": A(S("arg"), "What the job runs"), "job": ref("Job"),
    "deduped": B("True when an equivalent job was already queued: `job` is that one, nothing was added"),
    "running": null({**ref("Job"), "description": "The campaign's job running now, if any: the new one runs after it"})}, top=True)
define("ApiIndex", "The API, self-described: every function with its parameters and result", {
    "openapi": S("The OpenAPI 3.1 document's path"), "docs": S("The reference page's path"),
    "conventions": M(S("text"), "How responses, errors, parameters and links work"),
    "functions": A(O("A function (an HTTP route, an MCP tool, `perflab api <name>`)", {
        "name": S("Its name"), "kind": S("read (GET, no token, works without a server) or action (POST with X-Perflab-Token; "
                                         "needs the server)", enum=["read", "action"]),
        "method": S("GET or POST", enum=["GET", "POST"]), "path": S("The route"), "summary": S("What it does"),
        "params": A(O("A parameter", {"name": S("name"), "type": S("JSON type"), "required": B("required"),
                                      "description": S("What it means"), "default": {"description": "Default"}},
                      optional=("default",)), "Query parameters (GET) or JSON body fields (POST)"),
        "result": S("The response's schema (#/components/schemas/<name>)")}), "Every function")}, top=True)


def _examples():
    """Each response schema's example (api_examples.json, written by `python3 tests/test_api.py --write-examples` from
    the tests' fixtures)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_examples.json")) as f:
            ex = json.load(f)
    except (OSError, ValueError):
        return
    for name, x in ex.items():
        if name in SCHEMAS:
            SCHEMAS[name]["examples"] = [x]


_examples()


# ---- functions: a registry, from which the transports are built

FUNCTIONS = {}


class Fn:
    def __init__(self, f, kind, result, params, summary):
        self.f, self.name, self.kind, self.result, self.params, self.summary = f, f.__name__.rstrip("_"), kind, result, params, summary
        sig = inspect.signature(f)
        self.required = [k for k, p in sig.parameters.items() if p.default is inspect.Parameter.empty and not k.startswith("_")]
        self.defaults = {k: p.default for k, p in sig.parameters.items() if p.default is not inspect.Parameter.empty and not k.startswith("_")}
        self.description = inspect.cleandoc(f.__doc__ or summary)

    def input_schema(self):
        props = {k: {**s, **({"default": self.defaults[k]} if self.defaults.get(k) is not None else {})} for k, s in self.params.items()}
        return {"type": "object", "properties": props, "required": self.required, "additionalProperties": False}

    @property
    def method(self):
        return "GET" if self.kind == "read" else "POST"

    @property
    def path(self):
        return f"/api/v1/{self.name}"


def endpoint(kind, result, summary, **params):
    def wrap(f):
        FUNCTIONS[f.__name__.rstrip("_")] = Fn(f, kind, result, params, summary)
        return f
    return wrap


# ---- projects

_cfg_lock = threading.RLock()
DEFAULT_ROOT = None  # the project of an omitted `project` (MCP, CLI: the working directory's); None on the server


def _registered():
    """The server's registered projects, read from its database (no server needed); [] without one."""
    db = os.path.join(srv.home(), "jobs.sqlite")
    if not os.path.exists(db):
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            return [srv._project(dict(r)) for r in con.execute("SELECT * FROM projects ORDER BY name")]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def _project_of_root(root, registered=None):
    root = os.path.realpath(root)
    if not os.path.exists(os.path.join(root, "perflab.toml")):
        raise ApiError("not_found", f"no perflab.toml in {root}: not a perflab project")
    reg = {p["root"]: p for p in (registered if registered is not None else _registered())}
    if root in reg:
        return {**reg[root], "registered": True}
    cfg = config.find(root)
    p = srv._project({"id": srv.project_id(root), "root": root, "name": os.path.basename(root), "campaigns": cfg.campaigns, "runs": cfg.runs})
    return {**p, "registered": False}


def resolve(project=None, registered_only=False):
    """The project `project` names (see PROJECT_P), as the server's _project has it, with "registered"."""
    reg = _registered()
    if project is None or project == "":
        if DEFAULT_ROOT:
            return _project_of_root(config.find(DEFAULT_ROOT).root, reg)
        if len(reg) == 1:
            return {**reg[0], "registered": True}
        raise ApiError("bad_request", "which project? pass `project` (an id from projects)", {"projects": [p["id"] for p in reg]})
    for p in reg:
        if project == p["id"]:
            return {**p, "registered": True}
    if os.sep in project or os.path.isdir(project):
        p = _project_of_root(project, reg)
        if registered_only and not p["registered"]:
            raise ApiError("forbidden", f"{project} is not a project the server has registered; use its id", {"projects": [p["id"] for p in reg]})
        return p
    raise ApiError("not_found", f"no project {project!r}", {"projects": [p["id"] for p in reg]})


@contextlib.contextmanager
def _config(p):
    """perflab's modules read the project's perflab.toml through config.get(): this project's, while in the block."""
    with _cfg_lock:
        before = config._config
        config._config = config.find(p["root"])
        try:
            yield config._config
        finally:
            config._config = before


def _url(p, path):
    """The server path of `path`, None when it is not served (or the server does not know the project)."""
    if not path or not p.get("registered"):
        return None
    path = os.path.abspath(path)
    for prefix, d in p["mounts"]:
        if path == d or path.startswith(d + os.sep):
            rel = os.path.relpath(path, p["serveRoot"])
            if any(s.startswith(".") for s in rel.split(os.sep)):
                return None
            return f"/p/{p['id']}/" + urllib.parse.quote(rel.replace(os.sep, "/"))
    return None


def _public_project(p):
    return {"id": p["id"], "name": p["name"], "root": p["root"], "campaigns": p["campaigns"], "runs": p.get("runs"),
            "registered": bool(p.get("registered")), "index": p.get("index") if p.get("registered") else None}


@endpoint("read", "Projects", "The projects the server knows, and the working directory's")
def projects():
    """Every project registered with the perflab server, and the project of the working directory (MCP, CLI). A project's
    `id` is what the other functions' `project` parameter takes."""
    reg = _registered()
    out = [{**p, "registered": True} for p in reg]
    if DEFAULT_ROOT:
        try:
            here = _project_of_root(config.find(DEFAULT_ROOT).root, reg)
            if not here["registered"]:
                out.append(here)
        except ApiError:
            pass
    return envelope("Projects", projects=[_public_project(p) for p in out])


# ---- campaigns

NAME = re.compile(r"^[^/\\.][^/\\]*$")


def _segment(what, x):
    if not isinstance(x, str) or not NAME.match(x) or x in ("..",):
        raise ApiError("bad_request", f"{what} {x!r}: a plain name (no '/', not starting with '.')")
    return x


def _camp_dir(p, name):
    _segment("campaign", name)
    root = os.path.realpath(p["campaigns"])
    d = os.path.realpath(os.path.join(root, name))
    if os.path.dirname(d) != root or not os.path.isdir(d):
        names = sorted(n for n in os.listdir(root) if not n.startswith(".") and os.path.isdir(os.path.join(root, n))) if os.path.isdir(root) else []
        raise ApiError("not_found", f"no campaign {name!r} in {p['campaigns']}", {"campaigns": names})
    return d


def _json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _kind(d, spec):
    if os.path.exists(os.path.join(d, branchview.BRANCH_NAME)) or spec.get("branch"):
        return "branch"
    if spec.get("profileOf"):
        return "profile"
    return "paired" if spec.get("paired") else "plain"


def _plan(d, spec):
    """(variants in order, corpora in order, rounds, {variant: commit}) the spec plans."""
    corpora = list(spec.get("corpora") or [])
    rounds = int(spec.get("rounds", 2) or 0)
    commits = {}
    if os.path.exists(os.path.join(d, branchview.BRANCH_NAME)):
        b = _json(os.path.join(d, branchview.BRANCH_NAME), {})
        cs = sorted(b.get("commits", []), key=lambda c: c.get("index", 0))
        variants = [c.get("variant") or c["short"] for c in cs]
        commits = {c.get("variant") or c["short"]: c for c in cs}
    elif spec.get("paired"):
        variants = ["paired"]
    else:
        variants = list(spec.get("variants") or {}) or list(spec.get("builds") or {})
    return variants, corpora, rounds, commits


def _round_dirs(d, corpus, variant):
    return sorted((c for c in glob.glob(os.path.join(d, corpus, variant, "*")) if os.path.isdir(c) and os.path.basename(c).isdigit()),
                  key=lambda c: int(os.path.basename(c)))


def _running_cell(p):
    r = _json(os.path.join(p["campaigns"], ab.RUNNING_NAME))
    if r and r.get("cell"):
        return os.path.realpath(os.path.join(p["campaigns"], r["cell"]))
    return None


def _cell_state(cell, running, unbuildable=False):
    if ab.done(cell):
        return "done"
    if running and os.path.realpath(cell) == running:
        return "running"
    if os.path.exists(os.path.join(cell, ab.FAILED)):
        return "failed"
    if os.path.exists(os.path.join(cell, "result.json")):
        return "interrupted"
    return "unbuildable" if unbuildable else "pending"


def _jobs_rows(where="1=1", args=()):
    db = os.path.join(srv.home(), "jobs.sqlite")
    if not os.path.exists(db):
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            return [srv._job(dict(r)) for r in con.execute(f"SELECT * FROM jobs WHERE {where}", args)]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def job_campaign(argv, cwd, campaigns):
    """The campaign a job's argv runs (`ab run <spec>`, `branch profile|diff <spec | name>`), or None."""
    if len(argv) < 3:
        return None
    if argv[:2] == ["ab", "run"] or argv[:2] in (["branch", "profile"], ["branch", "diff"]):
        a = next((x for x in argv[2:] if not x.startswith("-")), None)
        if a is None:
            return None
        f = os.path.join(cwd or "", a)
        name = (_json(f, {}) or {}).get("name") if os.path.isfile(f) else a
        if not name and os.path.isfile(f):
            name = os.path.splitext(os.path.basename(a))[0]
        if argv[0] == "branch" and name:  # profiles and diffs go to the branch campaign's profile campaign
            return name + branchview.PROFILE_SUFFIX
        return name
    return None


def _active_jobs(p):
    out = {}
    for j in _jobs_rows("state IN ('queued','running','paused') AND project=?", (p["id"],)):
        name = job_campaign(j["argv"], j["cwd"], p["campaigns"])
        if name:
            out.setdefault(name, []).append(j)
    return out


def _iso(t):
    return datetime.datetime.fromtimestamp(t).isoformat(timespec="seconds") if t else None


def _summary(p, d, running, jobs, with_storage=False):
    name = os.path.basename(d)
    spec = _json(os.path.join(d, "spec.json"), {}) or {}
    kind = _kind(d, spec)
    variants, corpora, rounds, commits = _plan(d, spec)
    unb = branchview.unbuildable(d, d) if kind == "branch" else {}
    prog = dict.fromkeys(("done", "running", "failed", "interrupted", "unbuildable", "void"), 0)
    prog["planned"] = rounds * len(corpora) * len(variants)
    newest = 0.0
    for corpus in corpora:
        for v in variants:
            have = {int(os.path.basename(c)): c for c in _round_dirs(d, corpus, v)}
            for r in range(1, rounds + 1):
                c = have.get(r)
                st = _cell_state(c, running, v in unb) if c else ("unbuildable" if v in unb else "pending")
                if st != "pending":
                    prog[st] += 1
                if st == "done":
                    newest = max(newest, os.path.getmtime(os.path.join(c, "result.json")))
    prog["void"] = len(_void_dirs(d))
    names = [j for j in jobs.get(name, [])]
    live = (_json(os.path.join(p["campaigns"], ab.RUNNING_NAME), {}) or {}).get("campaign") == name
    status = ("running" if live or prog["running"] or any(j["state"] in srv.ACTIVE for j in names)
              else "finished" if prog["planned"] and prog["done"] >= prog["planned"] else "partial" if prog["done"] else "empty")
    updated = newest or os.path.getmtime(d)
    by = None
    if with_storage:
        by = dict.fromkeys(storage.TIERS, 0)
        for _, _, t, _, b, _ in storage.walk(d, set()):
            by[t] += b
        by["total"] = sum(by.values())
    desc = spec.get("description")
    prof = d + branchview.PROFILE_SUFFIX
    return {"name": name, "kind": kind, "benchmark": spec.get("benchmark"), "profile": _profile_str(spec),
            "rounds": rounds, "corpora": corpora, "variants": variants,
            "description": "\n".join(desc) if isinstance(desc, list) else desc, "progress": prog, "status": status,
            "updated": updated, "updatedIso": _iso(updated), "bytes": by, "profileOf": spec.get("profileOf"),
            "profiles": os.path.basename(prof) if kind == "branch" and os.path.isdir(prof) else None,
            "jobs": [{"id": j["id"], "state": j["state"], "argv": j["argv"]} for j in names],
            "url": (p["index"] + "#c-" + urllib.parse.quote(name)) if p.get("registered") else None}


def _profile_str(spec):
    pr = spec.get("profile", "none")
    if isinstance(pr, dict):
        return f"xctrace:{pr['xctrace']}" if "xctrace" in pr else f"async:{pr['async']}" if "async" in pr else "none"
    return pr or "none"


def _campaign_dirs(p):
    root = p["campaigns"]
    if not root or not os.path.isdir(root):
        return []
    return [os.path.join(root, n) for n in sorted(os.listdir(root))
            if not n.startswith(".") and os.path.isdir(os.path.join(root, n))
            and (os.path.exists(os.path.join(root, n, "spec.json")) or os.path.exists(os.path.join(root, n, branchview.BRANCH_NAME)))]


@endpoint("read", "Campaigns", "A project's campaigns: kind, plan, progress and status", project=PROJECT_P,
          storage=B("Also count each campaign's bytes by tier (walks every file: slow for campaigns with builds)"))
def campaigns(project=None, storage=False):
    """A project's campaigns, newest first: each one's kind (plain, paired, branch, profile), its corpora and variants,
    how many of its planned cells have results (and how many failed, are running or were voided), whether it is running,
    finished or partial, when it last changed, and the queue's jobs that run it."""
    p = resolve(project)
    with _config(p):
        running, jobs = _running_cell(p), _active_jobs(p)
        out = [_summary(p, d, running, jobs, storage) for d in _campaign_dirs(p)]
    out.sort(key=lambda c: -(c["updated"] or 0))
    return envelope("Campaigns", project=_public_project(p), campaigns=out)


# ---- per-variant statistics over forks: branchview's method (and its helpers), for any campaign

def _results(d, corpus, variant):
    out = []
    for c in _round_dirs(d, corpus, variant):
        r = branchview.load_cell(c)
        if isinstance(r, dict):
            out.append((r, c))
    return out


def _forks(rs, per_unit):
    """Per metric, the forks' means (a metric without rawData: each round's value), and the metrics' (label, kind, main)."""
    of = [metrics.of(r, per_unit, metrics.cached_hw_events(c)) for r, c in rs]
    cols, us = {}, {}
    for ms in of:
        for k, label, kind, main, _ in ms:
            cols.setdefault(k, (k, label, kind, main))
    for k in cols:
        forks = [f for (r, _) in rs for f in branchview.raw_of(r, k, metrics.units_per_op(r, per_unit) if per_unit else 1.0) if f]
        us[k] = [sum(f) / len(f) for f in forks] or [x for ms in of for kk, _, _, _, x in ms if kk == k and branchview.fin(x) is not None]
    return us, cols


def _stats(per_v, per_unit):
    """{variant: (forks' means by metric, cols)} -> {variant: {metric: Stat}}, the pooled sd for one of few forks (metrics.fork_spread)."""
    stat = {v: {k: (*metrics.stats(xs), len(xs)) for k, xs in us.items() if xs} for v, (us, _) in per_v.items()}
    keys = {k for st in stat.values() for k in st}
    pool = {k: metrics.pooled_rel_sd([(st[k][0], st[k][1], st[k][2] - 1) for st in stat.values() if k in st]) for k in keys}
    out = {}
    for v, (us, cols) in per_v.items():
        out[v] = {}
        for k, (mean, sd, n) in stat[v].items():
            kind = cols[k][2]
            sd, df, pooled = metrics.fork_spread(mean, sd, n, pool[k])
            ci = None if sd is None else metrics.t999(df) * sd / n ** 0.5
            f = branchview.fin
            out[v][k] = {"mean": f(mean), "sd": f(sd), "ci": f(ci), "n": n, "df": f(df),
                         "pooled": pooled, "shown": metrics.fmt(kind, mean),
                         "ciShown": "" if ci is None else branchview.ci_shown(kind, ci, mean),
                         "_ok": metrics.delta_ok(mean, kind, per_unit)}
    return out


def _delta(a, b, against):
    """Stat b against Stat a: a Delta, or None."""
    d, half, _ = metrics.welch((a["mean"], a["sd"], a["n"], a["df"]), (b["mean"], b["sd"], b["n"], b["df"]))
    if d is None:
        return None
    return {"pct": branchview.fin(d), "halfWidth": branchview.fin(half), "verdict": index.verdict(d, half, a["_ok"]),
            "against": against, "pooled": a["pooled"] or b["pooled"]}


def _public_stat(s):
    return {k: v for k, v in s.items() if not k.startswith("_")}


def _corpus_stats(d, corpus, variants, per_unit):
    per_v, rounds = {}, {}
    for v in variants:
        rs = _results(d, corpus, v)
        if rs:
            per_v[v] = _forks(rs, per_unit)
            rounds[v] = rs
    return per_v, rounds, _stats(per_v, per_unit)


def _ordered_corpora(d, spec):
    named = list(spec.get("corpora") or [])
    on_disk = sorted(os.path.basename(x.rstrip("/")) for x in glob.glob(os.path.join(d, "*/")) if not os.path.basename(x.rstrip("/")).startswith(("diff-", ".", "specs")))
    return named + [c for c in on_disk if c not in named and glob.glob(os.path.join(d, c, "*", "*", "result.json"))]


def _variant_ref(d, spec, ref_):
    """The variant `ref_` names: a variant, or for a branch campaign a unique sha prefix (4+ characters)."""
    variants, _, _, commits = _plan(d, spec)
    on_disk = {os.path.basename(v) for v in glob.glob(os.path.join(d, "*", "*")) if os.path.isdir(v)}
    if ref_ in variants or ref_ in on_disk:
        return ref_
    hits = [v for v, c in commits.items() if len(ref_) >= 4 and c["sha"].startswith(ref_.lower())]
    if len(hits) == 1:
        return hits[0]
    raise ApiError("not_found" if not hits else "bad_request", f"{ref_!r}: {'ambiguous' if hits else 'no such variant or commit'}",
                   {"variants": variants})


@endpoint("read", "Campaign", "One campaign: spec, variants, corpora, summary per corpus × variant × metric, links",
          project=PROJECT_P, campaign=CAMPAIGN_P)
def campaign(campaign, project=None):
    """One campaign in full. `summary` has, per corpus and variant, every metric the cells recorded (score, cycles,
    instructions, IPC, alloc, PMU counters, thread groups' shares) as mean ± 99.9% CI over forks, with Δ against the
    baseline (the first variant) by Welch's t and a verdict (better, worse, flat, na); `card` has the index card's
    own numbers (over rounds). `links` are the server's pages: the card, cell timelines, flame graphs, diffs."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        summ = _summary(p, d, _running_cell(p), _active_jobs(p))
        variants, _, rounds, commits = _plan(d, spec)
        corpora = _ordered_corpora(d, spec)
        per_unit = spec.get("perUnit")
        cols, rows = {}, []
        for corpus in corpora:
            per_v, rs, st = _corpus_stats(d, corpus, variants, per_unit)
            for v in per_v:
                for k, c in per_v[v][1].items():
                    cols.setdefault(k, c)
            names = [v for v in variants if v in per_v]
            if not names:
                continue
            _, idx = metrics.summarise({v: [metrics.of(r, per_unit, metrics.cached_hw_events(c)) for r, c in rs[v]] for v in names}, per_unit)
            b = names[0]
            for v in names:
                ms = {}
                for k, s in st[v].items():
                    x = _public_stat(s)
                    if v != b and k in st[b]:
                        x["delta"] = _delta(st[b][k], s, b)
                    ms[k] = x
                rr = {}
                for k, (mean, sd, dd, spread, ok) in idx[v].items():
                    f = branchview.fin
                    rr[k] = {"mean": f(mean), "sd": f(sd), "pct": f(dd), "spread": f(spread),
                             "verdict": "" if dd is None else index.verdict(dd, spread, ok)}
                rows.append({"corpus": corpus, "variant": v, "rounds": len(rs[v]), "forks": max((len(u) for u in per_v[v][0].values()), default=0),
                             "metrics": ms, "card": rr})
        vinfo = []
        vd = spec.get("variantDescriptions") or {}
        builds = spec.get("builds") or {}
        for v in variants:
            c = commits.get(v)
            b = builds.get(v)
            vinfo.append({"name": v, "description": vd.get(v) or (c or {}).get("subject"),
                          "flags": (spec.get("variants") or {}).get(v, "") if isinstance(spec.get("variants"), dict) else "",
                          "jmhArgs": (spec.get("variantJmhArgs") or {}).get(v, ""),
                          "build": {"checkout": (spec.get("branch") or {}).get("checkout") if c else (b or {}).get("checkout"),
                                    "commit": c["sha"] if c else None} if c or b else None,
                          "baseline": v == (variants[0] if variants else None)})
        corp = spec.get("corpora") or {}
        links = _links(p, d, spec)
    return envelope("Campaign", campaign=summ, spec=spec, variantInfo=vinfo,
                    corpusInfo=[{"name": c, "jmhArgs": corp.get(c, "") if isinstance(corp, dict) else ""} for c in corpora],
                    baseline=variants[0] if variants else None, perUnit=per_unit,
                    metrics=[{"key": k, "label": l, "kind": kd, "main": m} for k, l, kd, m in cols.values()],
                    summary=rows, links=links)


def _links(p, d, spec):
    name = os.path.basename(d)
    tl = []
    for corpus in _ordered_corpora(d, spec):
        for vd in sorted(glob.glob(os.path.join(d, corpus, "*"))):
            for c in _round_dirs(d, corpus, os.path.basename(vd)):
                if os.path.exists(os.path.join(c, "timeline.html")):
                    tl.append({"corpus": corpus, "variant": os.path.basename(vd), "round": int(os.path.basename(c)),
                               "url": _url(p, os.path.join(c, "timeline.html"))})
    report = os.path.join(d, "report.html")
    return {"card": (p["index"] + "#c-" + urllib.parse.quote(name)) if p.get("registered") else None,
            "spec": _url(p, os.path.join(d, "spec.json")), "report": _url(p, report) if os.path.exists(report) else None,
            "timelines": tl, "graphs": _graphs(p, d), "diffs": _diff_refs(p, d)}


def _graphs(p, d):
    out = []
    for c in sorted(glob.glob(os.path.join(d, "*", "*", "*"))):
        if not (os.path.isdir(c) and os.path.basename(c).isdigit()) or not _async(c):
            continue
        corpus, variant, rnd = c.split(os.sep)[-3:]
        for ev, kind, path in _cell_graphs(c):
            out.append({"corpus": corpus, "variant": variant, "round": int(rnd), "event": ev, "kind": kind, "url": _url(p, path), "path": path})
    return out


def _async(cell):
    try:
        return open(os.path.join(cell, "profile.txt")).read().startswith("async")
    except OSError:
        return False


def _cell_graphs(cell):
    """[(event, kind, path)] of a profiled cell's rendered graphs (branchview.graph_links, as absolute paths)."""
    return [(ev, kind, os.path.normpath(os.path.join(cell, href))) for ev, kind, href in branchview.graph_links(cell, cell)]


def _diff_refs(p, d):
    out = []
    for dd in sorted(glob.glob(os.path.join(d, "diff-*/"))):
        dd = dd.rstrip("/")
        pair = _json(os.path.join(dd, "pair.json"), {}) or {}
        name = os.path.basename(dd).removeprefix("diff-")
        a, b = pair.get("a"), pair.get("b")
        if not a:
            variants = {os.path.basename(v) for v in glob.glob(os.path.join(d, "*", "*")) if os.path.isdir(v)}
            forms = {f: v for v in variants for f in (v, v[:7])}
            hit = [(forms[name[:i]], forms[name[i + 1:]]) for i, ch in enumerate(name) if ch == "-" and name[:i] in forms and name[i + 1:] in forms]
            a, b = hit[0] if hit else (None, None)
        page = os.path.join(dd, "compare.html")
        out.append({"name": name, "campaign": os.path.basename(d), "a": a, "b": b, "corpus": pair.get("corpus"),
                    "url": _url(p, page if os.path.exists(page) else dd), "path": dd})
    return out


# ---- cells

def _void_dirs(d):
    return sorted(glob.glob(os.path.join(d, VOID_DIR, "*", "*", "*")))


def _void_info(d, vd):
    corpus, variant, leaf = os.path.relpath(vd, os.path.join(d, VOID_DIR)).split(os.sep)
    rnd, _, stamp = leaf.partition("-")
    meta = _json(os.path.join(vd, VOID_JSON), {}) or {}
    try:
        reason = meta.get("reason") or open(os.path.join(vd, VOID_NOTE)).read().strip()
    except OSError:
        reason = ""
    voided = meta.get("voided")
    if voided is None:
        try:
            voided = time.mktime(time.strptime(stamp, "%Y%m%d-%H%M%S"))
        except ValueError:
            voided = os.path.getmtime(vd)
    return {"id": f"{corpus}/{variant}/{leaf}", "corpus": corpus, "variant": variant, "round": int(rnd) if rnd.isdigit() else 0,
            "reason": reason, "voided": voided, "path": vd, "restorable": not os.path.exists(os.path.join(d, corpus, variant, rnd))}


def _cell_summary(p, d, corpus, variant, rnd, cell, running, unb):
    st = _cell_state(cell, running, variant in unb) if cell and os.path.isdir(cell) else ("unbuildable" if variant in unb else "pending")
    out = {"corpus": corpus, "variant": variant, "round": rnd, "state": st, "score": None, "error": None, "unit": None,
           "finished": None, "why": None, "voidId": None, "path": cell if cell and os.path.isdir(cell) else None,
           "url": None, "timeline": None}
    if out["path"]:
        out["url"] = _url(p, cell)
        if os.path.exists(os.path.join(cell, "timeline.html")):
            out["timeline"] = _url(p, os.path.join(cell, "timeline.html"))
    if st == "done":
        r = branchview.load_cell(cell)
        pm = r["primaryMetric"]
        out.update(score=branchview.fin(pm.get("score")), unit=pm.get("scoreUnit"), finished=os.path.getmtime(os.path.join(cell, "result.json")),
                   error=branchview.fin(pm["scoreError"]) if isinstance(pm.get("scoreError"), (int, float)) else None)
    elif st == "failed":
        try:
            out["why"] = open(os.path.join(cell, ab.FAILED)).read().strip()
        except OSError:
            pass
    elif st == "unbuildable":
        out["why"] = unb[variant]["reason"]
    return out


@endpoint("read", "Cells", "A campaign's cells (planned, done, running, failed, void), filtered",
          project=PROJECT_P, campaign=CAMPAIGN_P, corpus=S("Only this corpus"), variant=S("Only this variant (or a commit's sha prefix)"),
          round=I("Only this round", minimum=1), state=S("Only cells in this state", enum=list(STATES)))
def cells(campaign, project=None, corpus=None, variant=None, round=None, state=None):
    """A campaign's cells: every planned one (rounds × corpora × variants) and any other on disk, in its state, with
    its score, and the voided ones (state void, with why and voidId). Filter by corpus, variant, round and state."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        if variant:
            variant = _variant_ref(d, spec, variant)
        variants, corpora, rounds, _ = _plan(d, spec)
        corpora = corpora + [c for c in _ordered_corpora(d, spec) if c not in corpora]
        unb = branchview.unbuildable(d, d)
        running = _running_cell(p)
        out = []
        keys = set()
        for corpus_ in corpora:
            vs = variants + sorted(os.path.basename(v) for v in glob.glob(os.path.join(d, corpus_, "*"))
                                   if os.path.isdir(v) and os.path.basename(v) not in variants)
            for v in vs:
                have = {int(os.path.basename(c)): c for c in _round_dirs(d, corpus_, v)}
                for r in sorted(set(range(1, rounds + 1)) | set(have) if v in variants else set(have)):
                    keys.add((r, corpora.index(corpus_), vs.index(v)))
                    out.append(((r, corpora.index(corpus_), vs.index(v)), _cell_summary(p, d, corpus_, v, r, have.get(r), running, unb)))
        for vd in _void_dirs(d):
            info = _void_info(d, vd)
            c = {"corpus": info["corpus"], "variant": info["variant"], "round": info["round"], "state": "void",
                 "score": None, "error": None, "unit": None, "finished": None, "why": info["reason"], "voidId": info["id"],
                 "path": vd, "url": None, "timeline": None}
            r = branchview.load_cell(vd)
            if isinstance(r, dict):
                c.update(score=branchview.fin(r["primaryMetric"].get("score")), unit=r["primaryMetric"].get("scoreUnit"))
            out.append(((c["round"], corpora.index(c["corpus"]) if c["corpus"] in corpora else 99, 1e9), c))
    out = [c for _, c in sorted(out, key=lambda x: x[0])]
    out = [c for c in out if (corpus is None or c["corpus"] == corpus) and (variant is None or c["variant"] == variant)
           and (round is None or c["round"] == round) and (state is None or c["state"] == state)]
    return envelope("Cells", campaign=campaign, cells=out)


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return int(v) if v.is_integer() and "." not in str(x) and "e" not in str(x).lower() else v


def _file(p, path, cell):
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    return {"name": os.path.relpath(path, cell), "bytes": size, "path": path, "url": _url(p, path)}


@endpoint("read", "Cell", "One cell in full: result, metrics, raw samples, iterations, load, GC, profile, logs",
          project=PROJECT_P, campaign=CAMPAIGN_P, corpus=S("The corpus"), variant=S("The variant (or a commit's sha prefix)"),
          round=I("The round", minimum=1), tail=I("Include the last `tail` lines of each log", minimum=0))
def cell(campaign, corpus, variant, round, project=None, tail=0):
    """One cell in full: JMH's result (score, error, unit, params, JVM and its arguments), every metric perflab
    derives, each fork's measurement iterations per metric (raw), iterations.tsv's rows (warmup and measurement, with
    start and end times, GC time and allocation), the competing load over each measurement iteration, GC metrics,
    the profile's recordings and flame graphs, its logs (with `tail`, their last lines), and every file."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        variant = _variant_ref(d, spec, _segment("variant", variant))
        _segment("corpus", corpus)
        c = os.path.join(d, corpus, variant, str(int(round)))
        if not os.path.isdir(c):
            raise ApiError("not_found", f"{campaign}: no cell {corpus}/{variant}/{round} (see cells)")
        summ = _cell_summary(p, d, corpus, variant, int(round), c, _running_cell(p), branchview.unbuildable(d, d))
        r = branchview.load_cell(c)
        res, ms, raw = None, [], {}
        per_unit = spec.get("perUnit")
        if isinstance(r, dict):
            pm = r["primaryMetric"]
            res = {"benchmark": r.get("benchmark", ""), "mode": r.get("mode", ""), "score": pm["score"],
                   "error": pm["scoreError"] if isinstance(pm.get("scoreError"), (int, float)) and math.isfinite(pm["scoreError"]) else None,
                   "unit": pm.get("scoreUnit", ""), "params": {k: str(v) for k, v in (r.get("params") or {}).items()},
                   "jvm": r.get("jvm"), "jvmArgs": r.get("jvmArgs") or [], "jdkVersion": r.get("jdkVersion"),
                   "vmName": r.get("vmName"), "vmVersion": r.get("vmVersion"), "forks": r.get("forks"),
                   "warmupIterations": r.get("warmupIterations"), "warmupTime": r.get("warmupTime"),
                   "measurementIterations": r.get("measurementIterations"), "measurementTime": r.get("measurementTime")}
            hw = metrics.cached_hw_events(c)
            for k, label, kind, _, x in metrics.of(r, per_unit, hw):
                if branchview.fin(x) is not None:
                    ms.append({"key": k, "label": label, "kind": kind, "value": x})
                forks = branchview.raw_of(r, k, metrics.units_per_op(r, per_unit) if per_unit else 1.0)
                if any(forks):
                    raw[k] = forks
            gcm = {k: {"score": branchview.fin(v.get("score")) if isinstance(v.get("score"), (int, float)) else None, "unit": v.get("scoreUnit", "")}
                   for k, v in (r.get("secondaryMetrics") or {}).items() if k.startswith("gc.")}
        else:
            gcm, hw = {}, metrics.cached_hw_events(c)
        its = []
        tsv = os.path.join(c, "iterations.tsv")
        if os.path.exists(tsv):
            rows = open(tsv).read().splitlines()
            head = rows[0].split("\t") if rows else []
            its = [{k: _num(v) for k, v in zip(head, row.split("\t")) if v != ""} for row in rows[1:] if row]
        load = None
        lj = _json(os.path.join(c, ab.LOAD_CHECK))
        if lj:
            load = {"source": "load.json", "maxCores": lj.get("maxCores"), "disturbed": lj.get("disturbed") or [], "iterations": lj.get("iterations") or []}
        elif os.path.exists(os.path.join(c, "load.tsv")):
            lim = (spec.get("loadgate") or {}).get("maxCores")
            pi = loadgate.per_iteration(os.path.join(c, "load.tsv"), tsv)
            load = {"source": "load.tsv", "maxCores": lim, "iterations": pi,
                    "disturbed": [i["index"] for i in pi if lim is not None and i["cores"] is not None and i["cores"] > lim]}
        files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(c) for f in fs)
        try:
            profiler = open(os.path.join(c, "profile.txt")).read().strip()
        except OSError:
            profiler = "none"
        logs = {}
        for name in ("build.log", "jmh.log", "gc.log"):
            f = os.path.join(c, name)
            if os.path.exists(f):
                logs[name] = {**_file(p, f, c), "tail": srv._tail(f, int(tail)) if tail else None}
        void = None
        prof = {"profiler": profiler, "recordings": [_file(p, f, c) for f in files if f.endswith((".jfr", ".trace"))],
                "graphs": [{"event": ev, "kind": k, "url": _url(p, path), "path": path} for ev, k, path in _cell_graphs(c)] if _async(c) else [],
                "hwEvents": hw}
    return envelope("Cell", cell=summ, result=res, metrics=ms, raw=raw, iterations=its, load=load,
                    gc={"metrics": gcm, "log": _file(p, os.path.join(c, "gc.log"), c) if os.path.exists(os.path.join(c, "gc.log")) else None},
                    profile=prof, logs=logs, files=[_file(p, f, c) for f in files],
                    specVersion=(open(os.path.join(c, "spec.version")).read().strip() or None) if os.path.exists(os.path.join(c, "spec.version")) else None,
                    void=void)


# ---- branch campaigns

def _branch_dir(p, name):
    d = _camp_dir(p, name)
    if not os.path.exists(os.path.join(d, branchview.BRANCH_NAME)):
        raise ApiError("bad_request", f"{name} is not a branch campaign (it has no branch.json)")
    return d


def _view(p, d):
    return branchview.branch_view(d, p["serveRoot"])


@endpoint("read", "Branch", "A branch campaign's history: commits oldest first, per corpus each metric's mean, CI and Δ vs the previous commit",
          project=PROJECT_P, campaign=CAMPAIGN_P, raw=B("Include every fork's measurement iterations per metric (large)"))
def branch(campaign, project=None, raw=False):
    """A branch campaign commit by commit, oldest first (the index's history view, perflab.branchview): per commit its
    sha, subject, the commits a merge brought in, whether it built, and per corpus each metric's mean ± 99.9% CI over
    forks with Δ against the previous measured commit (Welch's t; verdict better, worse, flat or na). For the
    significant steps alone, use changes."""
    p = resolve(project)
    with _config(p):
        d = _branch_dir(p, campaign)
        v = _view(p, d)
        b = _json(os.path.join(d, branchview.BRANCH_NAME), {})
        prof = v.get("profile") or {}
        profiled = {}
        for corpus, cs in (prof.get("cells") or {}).items():
            for var, x in cs.items():
                if x.get("state") == "done":
                    profiled.setdefault(var, []).append(corpus)
        metric = {m["k"]: m for m in v["metrics"]}
        commits = []
        unb = v["unbuildable"]
        for c in sorted(v["commits"], key=lambda c: c["index"]):
            corp = {}
            for corpus in v["corpora"]:
                x = (v["cells"].get(corpus) or {}).get(c["v"])
                if x is None:
                    continue
                bc = {"state": x["state"], "rounds": x.get("rounds", 0), "forks": x.get("forks", 0), "why": x.get("why"),
                      "metrics": {}, "previous": x.get("prev")}
                for k, m in (x.get("m") or {}).items():
                    s = {"mean": m[0], "sd": m[1], "ci": m[2], "n": m[4], "df": m[5], "pooled": bool(m[6]),
                         "shown": x["s"][k][0], "ciShown": x["s"][k][1]}
                    dd = (x.get("d") or {}).get(k)
                    s["delta"] = {"pct": dd[0], "halfWidth": dd[1], "verdict": dd[2], "against": x["prev"], "pooled": bool(dd[3])} if dd else None
                    bc["metrics"][k] = s
                if raw:
                    bc["raw"] = x.get("raw") or {}
                corp[corpus] = bc
            u = unb.get(c["v"])
            commits.append({"index": c["index"], "sha": c["sha"], "short": c["short"], "variant": c["v"], "subject": c["subject"],
                            "author": c["author"], "date": c["date"], "merged": [{"sha": m.get("sha", ""), "subject": m.get("subject", "")} for m in c["merged"]],
                            "unbuildable": {"reason": u["reason"], "log": _url(p, os.path.normpath(os.path.join(p["serveRoot"], u["log"])))} if u else None,
                            "corpora": corp, "profiled": profiled.get(c["v"], [])})
        diffs = _diff_refs(p, d) + (_diff_refs(p, d + branchview.PROFILE_SUFFIX) if os.path.isdir(d + branchview.PROFILE_SUFFIX) else [])
    return envelope("Branch", campaign=campaign, range=v.get("range", ""), checkout=b.get("checkout"), corpora=v["corpora"],
                    perUnit=v.get("perUnit"), metrics=[{"key": m["k"], "label": m["h"], "kind": m["kind"]} for m in metric.values()],
                    commits=commits, profile=prof.get("campaign"), diffs=diffs)


@endpoint("read", "Changes", "The commits of a branch campaign whose Δ vs the previous measured commit is significant, largest first",
          project=PROJECT_P, campaign=CAMPAIGN_P, metric=METRIC_KEY, corpus=S("Only this corpus"))
def changes(campaign, project=None, metric="score", corpus=None):
    """The steps of a branch campaign: commits whose `metric` moved against the previous measured commit by more than
    the 99.9% CI of the difference (verdict better or worse), on each corpus (or `corpus`), sorted by |Δ|, largest
    first. A commit with one fork uses the pooled spread (delta.pooled)."""
    b = branch(campaign, project)
    out, untested = [], []
    for c in b["commits"]:
        for corp, x in c["corpora"].items():
            if corpus and corp != corpus:
                continue
            s = x["metrics"].get(metric)
            if s and s.get("delta") and s["delta"]["halfWidth"] is None and s["delta"]["verdict"] != "na":
                untested.append({"corpus": corp, "variant": c["variant"], "previous": x["previous"], "pct": s["delta"]["pct"]})
            if not s or not s.get("delta") or s["delta"]["verdict"] not in ("better", "worse"):
                continue
            prev = next(cc for cc in b["commits"] if cc["variant"] == x["previous"])
            out.append({"corpus": corp, "metric": metric, "variant": c["variant"], "sha": c["sha"], "subject": c["subject"],
                        "index": c["index"], "previous": x["previous"], "mean": s["mean"],
                        "previousMean": prev["corpora"][corp]["metrics"][metric]["mean"], "shown": s["shown"], "delta": s["delta"]})
    out.sort(key=lambda c: -abs(c["delta"]["pct"] or 0))
    untested.sort(key=lambda c: -abs(c["pct"] or 0))
    return envelope("Changes", campaign=campaign, metric=metric, changes=out, untested=untested)


@endpoint("read", "Compare", "Two variants or commits of a campaign: every metric's Δ ± CI and verdict, per corpus",
          project=PROJECT_P, campaign=CAMPAIGN_P, a=S("The base: a variant (or a commit's sha prefix)"),
          b=S("The other: a variant (or a commit's sha prefix)"), corpus=S("Only this corpus"))
def compare(campaign, a, b, project=None, corpus=None):
    """Variant (or commit) b against a: per corpus both have results on, every metric both recorded, each side's mean
    ± 99.9% CI over forks and Δ of b against a by Welch's t, with its verdict. The pair's profile diffs, if any."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        a, b = _variant_ref(d, spec, a), _variant_ref(d, spec, b)
        variants, _, _, _ = _plan(d, spec)
        out = []
        for corp in _ordered_corpora(d, spec):
            if corpus and corp != corpus:
                continue
            # the pool is over the corpus's variants, as in the campaign's summary and the branch view
            per_v, _, st = _corpus_stats(d, corp, list(dict.fromkeys([*variants, a, b])), spec.get("perUnit"))
            if a not in st or b not in st:
                continue
            ms = []
            for k, (key, label, kind, _) in per_v[a][1].items():
                if k not in st[a] or k not in st[b]:
                    continue
                sa, sb = st[a][k], st[b][k]
                side = lambda s: {"mean": s["mean"], "ci": s["ci"], "n": s["n"], "shown": s["shown"]}
                ms.append({"key": k, "label": label, "kind": kind, "a": side(sa), "b": side(sb), "delta": _delta(sa, sb, a)})
            out.append({"corpus": corp, "metrics": ms})
        diffs = [x for x in _all_diffs(p, d) if {x["a"], x["b"]} == {a, b}]
    return envelope("Compare", campaign=campaign, a=a, b=b, corpora=out, diffs=diffs)


def _all_diffs(p, d):
    pd = d + branchview.PROFILE_SUFFIX
    return _diff_refs(p, d) + (_diff_refs(p, pd) if os.path.isdir(pd) else [])


@endpoint("read", "Profiles", "A campaign's flame graphs and profile diffs (a branch campaign's profile campaign included)",
          project=PROJECT_P, campaign=CAMPAIGN_P)
def profiles(campaign, project=None):
    """Every rendered flame graph of the campaign's profiled cells (async-profiler), and its diffs (profdiff outputs).
    For a branch campaign, those of its profile campaign (<name>.profile) too, where its commits are profiled apart
    from their measurement."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        gs = _graphs(p, d)
        pd = d + branchview.PROFILE_SUFFIX
        if os.path.isdir(pd):
            gs += _graphs(p, pd)
    return envelope("Profiles", campaign=campaign, graphs=gs, diffs=_all_diffs(p, d))


SI = {"k": 1e3, "M": 1e6, "G": 1e9}


def _si(x):
    x = x.strip()
    try:
        return float(x[:-1]) * SI[x[-1]] if x and x[-1] in SI else float(x)
    except ValueError:
        return None


TABLE_ROW = re.compile(r"^\| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| `(.*)` \|$")


def _table(path):
    try:
        text = open(path).read()
    except OSError:
        return None, [], None
    rows = []
    for line in text.splitlines():
        m = TABLE_ROW.match(line)
        if m:
            rows.append({"delta": _si(m.group(1)), "a": _si(m.group(2)), "b": _si(m.group(3)),
                         "pctOfTotal": _si(m.group(4).rstrip("%")), "method": m.group(5), "shown": line})
    return text.splitlines()[0] if text else None, rows, text


@endpoint("read", "Diff", "The profdiff outputs of a pair: per event its pages and the methods whose self time per op changed most",
          project=PROJECT_P, campaign=CAMPAIGN_P, a=S("Variant (or commit) a"), b=S("Variant (or commit) b"), corpus=S("Only this corpus"))
def diff(campaign, a, b, project=None, corpus=None):
    """The existing profdiff outputs of variants (or commits) a and b, in either order: per event (cpu, alloc,
    cycles, ...) the URLs of a's graph, the differential graph a → b, its inverse and b's graph, and the table of the
    methods whose self samples (or events) per op decreased and increased most. None yet: for a branch campaign,
    submit `branch profile <campaign> <a> <b> --diff`."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        a, b = _variant_ref(d, spec, a), _variant_ref(d, spec, b)
        out = []
        for x in _all_diffs(p, d):
            if {x["a"], x["b"]} != {a, b} or (corpus and x["corpus"] and x["corpus"] != corpus):
                continue
            evs = []
            for f in sorted(glob.glob(os.path.join(x["path"], "diff-*.html"))):
                if f.endswith("-inverse.html"):
                    continue
                ev = os.path.basename(f)[len("diff-"):-len(".html")]
                summary, rows, text = _table(os.path.join(x["path"], f"table-{ev}.md"))
                pages = {view: _url(p, os.path.join(x["path"], name.format(event=ev)))
                         for view, name in (("a", "a-{event}.html"), ("diff", "diff-{event}.html"), ("inverse", "diff-{event}-inverse.html"), ("b", "b-{event}.html"))
                         if os.path.exists(os.path.join(x["path"], name.format(event=ev)))}
                evs.append({"event": ev, "pages": pages, "summary": summary, "rows": rows, "table": text})
            out.append({**x, "events": evs})
    if not out:
        raise ApiError("not_found", f"{campaign}: no diff of {a} and {b}", {"submit": ["branch", "profile", campaign, a, b, "--diff"]})
    return envelope("Diff", campaign=campaign, a=a, b=b, diffs=out)


# ---- voids

@endpoint("read", "Voids", "A campaign's voided cells", project=PROJECT_P, campaign=CAMPAIGN_P)
def voids(campaign, project=None):
    """The cells voided out of a campaign (<campaign>/.void/<corpus>/<variant>/<round>-<timestamp>/), newest first, with
    why, and whether unvoid can put each back."""
    p = resolve(project)
    d = _camp_dir(p, campaign)
    vs = sorted((_void_info(d, v) for v in _void_dirs(d)), key=lambda v: -(v["voided"] or 0))
    return envelope("Voids", campaign=campaign, voids=vs)


@endpoint("action", "Voided", "Void a cell: move it to <campaign>/.void/ with a reason, so that a resume runs it again",
          project=PROJECT_P, campaign=CAMPAIGN_P, corpus=S("The corpus"), variant=S("The variant (or a commit's sha prefix)"),
          round=I("The round", minimum=1), reason=S("Why: kept in void.txt, shown by voids", minLength=1))
def void(campaign, corpus, variant, round, reason, project=None, _server=None):
    """Void a cell whose result should not count (disturbed by other load, a broken build, ...): it moves to
    <campaign>/.void/<corpus>/<variant>/<round>-<timestamp>/ with void.txt (the reason), out of the summary, the branch
    view and the progress count. Then `rerun` queues a resume that runs it again. Refuses the running cell. Undo with
    unvoid."""
    p = resolve(project, registered_only=False)
    with _config(p):
        d = _camp_dir(p, campaign)
        spec = _json(os.path.join(d, "spec.json"), {}) or {}
        variant = _variant_ref(d, spec, _segment("variant", variant))
        _segment("corpus", corpus)
        rnd = int(round)
        c = os.path.join(d, corpus, variant, str(rnd))
        if not os.path.isdir(c) or os.path.islink(c):
            raise ApiError("not_found", f"{campaign}: no cell {corpus}/{variant}/{rnd}")
        if os.path.realpath(os.path.dirname(os.path.dirname(os.path.dirname(c)))) != os.path.realpath(d):
            raise ApiError("forbidden", "not a cell of the campaign")
        if not any(os.path.exists(os.path.join(c, f)) for f in ("result.json", ab.FAILED, "build.log", "jmh.log", "spec.version")):
            raise ApiError("bad_request", f"{c} is not a cell (no result.json, failed.txt or logs)")
        running = _running_cell(p)
        if running and os.path.realpath(c) == running:
            raise ApiError("conflict", f"{corpus}/{variant}/{rnd} is running: void it once it has finished")
        if not reason or not str(reason).strip():
            raise ApiError("bad_request", "a reason is required")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(d, VOID_DIR, corpus, variant, f"{rnd}-{stamp}")
        while os.path.exists(dest):
            dest += "x"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.rename(c, dest)
        with open(os.path.join(dest, VOID_NOTE), "w") as f:
            f.write(str(reason).strip() + "\n")
        with open(os.path.join(dest, VOID_JSON), "w") as f:
            json.dump({"reason": str(reason).strip(), "voided": time.time(), "from": c}, f)
        for x in (os.path.join(d, corpus, variant), os.path.join(d, corpus)):  # leave no empty variant or corpus behind
            with contextlib.suppress(OSError):
                if not os.listdir(x):
                    os.rmdir(x)
    _reindex(p)
    return envelope("Voided", campaign=campaign, void=_void_info(d, dest), **{"from": c})


@endpoint("action", "Unvoided", "Put a voided cell back where it was", project=PROJECT_P, campaign=CAMPAIGN_P,
          id=S("The void's id (see voids): <corpus>/<variant>/<round>-<timestamp>"))
def unvoid(campaign, id, project=None, _server=None):
    """Undo a void: the cell moves back to <campaign>/<corpus>/<variant>/<round>/, unless that place has a cell again
    (a rerun ran it), when it is refused (conflict)."""
    p = resolve(project)
    with _config(p):
        d = _camp_dir(p, campaign)
        parts = str(id).split("/")
        if len(parts) != 3:
            raise ApiError("bad_request", f"{id!r}: a void id is <corpus>/<variant>/<round>-<timestamp>")
        for x in parts:
            _segment("void id part", x)
        vd = os.path.join(d, VOID_DIR, *parts)
        if not os.path.isdir(vd):
            raise ApiError("not_found", f"{campaign}: no void {id}", {"voids": [v["id"] for v in voids(campaign, p["root"])["voids"]]})
        info = _void_info(d, vd)
        dest = os.path.join(d, info["corpus"], info["variant"], str(info["round"]))
        if os.path.exists(dest):
            raise ApiError("conflict", f"{info['corpus']}/{info['variant']}/{info['round']} has a cell again; void that one first")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.rename(vd, dest)
        for f in (VOID_NOTE, VOID_JSON):
            with contextlib.suppress(OSError):
                os.unlink(os.path.join(dest, f))
        for x in (os.path.dirname(vd), os.path.dirname(os.path.dirname(vd))):
            with contextlib.suppress(OSError):
                if not os.listdir(x):
                    os.rmdir(x)
        summ = _cell_summary(p, d, info["corpus"], info["variant"], info["round"], dest, _running_cell(p), branchview.unbuildable(d, d))
    _reindex(p)
    return envelope("Unvoided", campaign=campaign, cell=summ, **{"from": vd})


def _reindex(p):
    if os.environ.get("PERFLAB_API_NO_REINDEX"):  # tests
        return
    with contextlib.suppress(OSError):
        srv._reindex(p)


# ---- jobs

def _need_server(s):
    if s is None:
        raise ApiError("no_server", "this action needs `perflab server` (start it with `perflab server start`)")
    return s


def _pub(j, s=None):
    out = srv.public(j)
    if s is not None:
        out["url"] = f"/#job-{j['id']}"
    return out


@endpoint("action", "Rerun", "Queue a resume of a campaign (its missing and voided cells) on the server, once",
          project=PROJECT_P, campaign=CAMPAIGN_P)
def rerun(campaign, project=None, _server=None):
    """Queue `perflab ab run <campaign>/spec.json` on the server: a resume, which runs the campaign's cells that have
    no result (pending, interrupted, failed and voided ones; a branch campaign's unbuildable commits stay skipped). Once:
    if a job for this campaign is already queued, that job is returned (deduped) and nothing is added. A running job
    does not count, since it chose its cells when it started; the new one runs after it."""
    s = _need_server(_server)
    p = resolve(project)
    d = _camp_dir(p, campaign)
    spec_f = os.path.join(d, "spec.json")
    if not os.path.exists(spec_f):
        raise ApiError("bad_request", f"{campaign} has no spec.json to resume from")
    argv = ["ab", "run", spec_f]
    with s.q.lock:
        queued = [j for j in s.q.jobs(include_final=False) if j["project"] == p["id"]]
        mine = [j for j in queued if job_campaign(j["argv"], j["cwd"], p["campaigns"]) == campaign]
        running = next((j for j in mine if j["state"] in srv.ACTIVE), None)
        waiting = next((j for j in mine if j["state"] == "queued"), None)
        if waiting:
            return envelope("Rerun", campaign=campaign, argv=waiting["argv"], job=_pub(waiting, s), deduped=True,
                            running=_pub(running, s) if running else None)
        # the environment of the campaign's last job (the toolchain it was submitted with), else the server's
        last = [j for j in s.q.jobs(include_final=True, limit=500)
                if j["project"] == p["id"] and job_campaign(j["argv"], j["cwd"], p["campaigns"]) == campaign]
        env = (last[0]["env"] if last else None) or srv.job_env()
        j = srv.submit_local(s, {"argv": argv, "cwd": p["root"], "env": env}, **_RERUN_RUNNER)
    return envelope("Rerun", campaign=campaign, argv=argv, job=_pub(j, s), deduped=False, running=_pub(running, s) if running else None)


_RERUN_RUNNER = {}  # tests: {"module": a stand-in for perflab}


@endpoint("action", "JobResult", "Queue any perflab command line on the server", project=PROJECT_P,
          argv=A(S("argument"), "`perflab <argv>`, e.g. [\"ab\", \"run\", \"spec.json\"] or [\"branch\", \"profile\", \"<campaign>\", \"<a>\", \"<b>\", \"--diff\"]", minItems=1),
          priority=I("Higher runs first (default 0)"))
def submit(argv, project=None, priority=0, _server=None):
    """Queue `perflab <argv>`, run in the project's root, on the server: the server runs one job at a time. The job's
    environment is the server's toolchain variables."""
    s = _need_server(_server)
    p = resolve(project)
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ApiError("bad_request", "argv must be a non-empty list of strings")
    j = srv.submit_local(s, {"argv": argv, "cwd": p["root"], "env": srv.job_env(), "priority": priority})
    return envelope("JobResult", job=_pub(j, s))


@endpoint("read", "Jobs", "The server's queue", all=B("Include finished jobs (the last 100)"))
def jobs(all=True):
    """The server's jobs: running and paused first, then queued in the order they will run, then (with all) finished
    ones, newest first. Read from the server's database: works while the server is stopped."""
    rows = _jobs_rows("state IN ('running','paused')") + sorted(_jobs_rows("state='queued'"), key=lambda j: (-j["priority"], j["seq"], j["id"]))
    for i, j in enumerate(x for x in rows if x["state"] == "queued"):
        j["position"] = i + 1
    if all:
        rows += sorted(_jobs_rows("state IN ('done','failed','cancelled')"), key=lambda j: (-(j["ended"] or 0), -j["id"]))[:100]
    return envelope("Jobs", jobs=[srv.public(j) for j in rows])


def _job_row(id):
    rows = _jobs_rows("id=?", (int(id),))
    if not rows:
        raise ApiError("not_found", f"no job {id}")
    return rows[0]


@endpoint("read", "JobResult", "One job", id=I("The job's id"))
def job(id):
    """One job of the server's queue: its command line, state, exit status and transcript file."""
    return envelope("JobResult", job=srv.public(_job_row(id)))


@endpoint("read", "Transcript", "A job's transcript (progress, cells, the build's output)", id=I("The job's id"),
          tail=I("Only its last `tail` lines (0: all)", minimum=0))
def transcript(id, tail=200):
    """A job's transcript: what `perflab` said as it ran (cells, load gate waits, results, the build's output)."""
    j = _job_row(id)
    return envelope("Transcript", id=j["id"], text=srv._tail(j["transcript"], int(tail) or None) if j.get("transcript") else "")


def _control(op, s, id, **kw):
    s = _need_server(s)
    try:
        j = (srv.pause(s.q, id) if op == "pause" else srv.resume(s.q, id) if op == "resume" else srv.cancel(s.q, id) if op == "cancel"
             else s.q.set_priority(id, kw["priority"]) if op == "priority" else s.q.move(id, kw["by"]))
    except KeyError:
        raise ApiError("not_found", f"no job {id}") from None
    except srv.Conflict as e:
        raise ApiError("conflict", str(e)) from None
    s.worker.wake.set()
    return envelope("JobResult", job=_pub(j, s))


@endpoint("action", "JobResult", "Pause a running job at its next cell boundary", id=I("The job's id"))
def pause(id, _server=None):
    """Pause a running job: it stops at its next cell boundary (a fork's work is never thrown away) until resume."""
    return _control("pause", _server, id)


@endpoint("action", "JobResult", "Resume a paused job", id=I("The job's id"))
def resume(id, _server=None):
    """Resume a paused job."""
    return _control("resume", _server, id)


@endpoint("action", "JobResult", "Cancel a job: a queued one at once, a running one at its next cell boundary", id=I("The job's id"))
def cancel(id, _server=None):
    """Cancel a job. A queued one is cancelled at once; a running one stops at its next cell boundary, or is sent
    SIGTERM after a grace period. Its results are kept."""
    return _control("cancel", _server, id)


@endpoint("action", "JobResult", "Set a queued job's priority", id=I("The job's id"), priority=I("Higher runs first"))
def set_priority(id, priority, _server=None):
    """Set a queued job's priority: higher runs first."""
    return _control("priority", _server, id, priority=int(priority))


@endpoint("action", "JobResult", "Move a queued job one place earlier or later", id=I("The job's id"),
          by=I("-1: earlier, 1: later", enum=[-1, 1]))
def move(id, by, _server=None):
    """Move a queued job one place earlier (by -1) or later (1) in the queue."""
    return _control("move", _server, id, by=int(by))


# ---- calling, from any transport

def _check_args(fn, args):
    unknown = set(args) - set(fn.params)
    if unknown:
        raise ApiError("bad_request", f"{fn.name}: unknown parameters {sorted(unknown)}", {"params": list(fn.params)})
    missing = [k for k in fn.required if args.get(k) is None]
    if missing:
        raise ApiError("bad_request", f"{fn.name}: missing {missing}", {"params": list(fn.params)})
    errs = validate({k: v for k, v in args.items() if v is not None}, {**fn.input_schema(), "required": []})
    if errs:
        raise ApiError("bad_request", f"{fn.name}: {'; '.join(errs)}")


def coerce(fn, query):
    """Query-string values (strings) as the parameters' types."""
    out = {}
    for k, v in query.items():
        t = (fn.params.get(k) or {}).get("type")
        t = t[0] if isinstance(t, list) else t
        try:
            out[k] = (int(v) if t == "integer" else float(v) if t == "number" else v.lower() in ("1", "true", "yes", "on") if t == "boolean"
                      else json.loads(v) if t == "array" else v)
        except ValueError:
            raise ApiError("bad_request", f"{k}={v!r}: expected {t}") from None
    return out


def call(name, args=None, server=None):
    """Runs function `name` with `args` (a dict); an action without `server` (this process is not the server) is POSTed
    to the running server. Raises ApiError."""
    fn = FUNCTIONS.get(name)
    if fn is None:
        raise ApiError("not_found", f"no function {name!r}", {"functions": sorted(FUNCTIONS)})
    args = dict(args or {})
    _check_args(fn, args)
    if fn.kind == "action" and server is None:
        if "project" in fn.params and not args.get("project"):
            args["project"] = config.find(DEFAULT_ROOT).root if DEFAULT_ROOT else None
        return post(fn.path, {k: v for k, v in args.items() if v is not None})
    try:
        return fn.f(**args, **({"_server": server} if fn.kind == "action" else {}))
    except ApiError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ApiError("internal", f"{type(e).__name__}: {e}") from e
    except SystemExit as e:
        raise ApiError("bad_request", str(e.code)) from None


def post(path, body, url=None):
    """POSTs to the running server's API; its result, or its error as an ApiError."""
    url = url or srv.running()
    if not url:
        raise ApiError("no_server", "this action needs `perflab server` (start it with `perflab server start`); reads work without it")
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Perflab-Token": srv.token(srv.home())})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())["error"]
            raise ApiError(err.get("code", "internal"), err.get("message", ""), err.get("details")) from None
        except (ValueError, KeyError, TypeError):
            raise ApiError("internal", f"server: {e.code} {e.reason}") from None
    except urllib.error.URLError as e:
        raise ApiError("no_server", f"the perflab server at {url} did not answer: {e.reason}") from None


# ---- a JSON Schema validator: the subset these schemas use

def validate(x, schema, defs=None, path="$"):
    """Errors of `x` against `schema` (type, enum, const, properties, required, additionalProperties, items, anyOf,
    minimum, minItems, minLength, $ref into #/$defs/)."""
    defs = SCHEMAS if defs is None else defs
    if "$ref" in schema:
        return validate(x, defs[schema["$ref"].removeprefix(REF)], defs, path)
    errs = []
    if "anyOf" in schema:
        if all(validate(x, s, defs, path) for s in schema["anyOf"]):
            errs.append(f"{path}: matches none of anyOf")
        return errs
    t = schema.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]
        ok = {"object": isinstance(x, dict), "array": isinstance(x, list), "string": isinstance(x, str),
              "integer": isinstance(x, int) and not isinstance(x, bool), "boolean": isinstance(x, bool), "null": x is None,
              "number": isinstance(x, (int, float)) and not isinstance(x, bool)}
        if not any(ok[k] for k in ts):
            return [f"{path}: {type(x).__name__} is not {t}"]
    if "const" in schema and x != schema["const"]:
        errs.append(f"{path}: {x!r} is not {schema['const']!r}")
    if "enum" in schema and x not in schema["enum"]:
        errs.append(f"{path}: {x!r} not in {schema['enum']}")
    if isinstance(x, (int, float)) and not isinstance(x, bool) and "minimum" in schema and x < schema["minimum"]:
        errs.append(f"{path}: {x} < {schema['minimum']}")
    if isinstance(x, str) and len(x) < schema.get("minLength", 0):
        errs.append(f"{path}: shorter than {schema['minLength']}")
    if isinstance(x, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in x:
                errs.append(f"{path}: missing {k}")
        extra = schema.get("additionalProperties", True)
        for k, v in x.items():
            if k in props:
                errs += validate(v, props[k], defs, f"{path}.{k}")
            elif extra is False:
                errs.append(f"{path}: unexpected {k}")
            elif isinstance(extra, dict):
                errs += validate(v, extra, defs, f"{path}.{k}")
    if isinstance(x, list):
        if len(x) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, v in enumerate(x):
                errs += validate(v, schema["items"], defs, f"{path}[{i}]")
    return errs


# ---- self-description: the index, OpenAPI, the reference page, schemas with their dependencies

CONVENTIONS = {
    "responses": "Every response is a JSON object with \"schema\" (its schema's name: #/components/schemas/<schema> in "
                 "openapi.json) and \"version\" (the API version, 1). HTTP responses also link it: Link: <...openapi.json#/components/schemas/<schema>>; rel=\"describedby\".",
    "errors": "A failure is {\"error\": {\"code\", \"message\", \"details\"?}} (#/components/schemas/Error) with the HTTP status of its "
              "code: bad_request 400, forbidden 403, not_found 404, conflict 409, no_server 503, internal 500.",
    "reads": "GET /api/v1/<function>?<param>=<value>: no token; numbers and booleans as text (true/false), arrays as JSON.",
    "actions": "POST /api/v1/<function> with a JSON object of the parameters, header X-Perflab-Token (the server's token, in "
               "~/.perflab/server/token), from the server's own origin only.",
    "project": "Every function on a project takes `project`: a project id (see projects) or its root directory; over HTTP "
               "only registered projects, and omitted only when there is one.",
    "urls": "Fields named url are paths on the server (http://127.0.0.1:8690 by default): the index, timelines, flame graphs.",
    "units": "A metric's unit is in its label (MetricInfo.label): the score in the benchmark's unit (e.g. ms/op), alloc in "
             "bytes per op, counts in events per op (per unit of perUnit when the spec has one), ratios and percents as such.",
    "statistics": "The unit of variation is the fork: a variant's mean, sd and 99.9% CI are over its forks' means; Δ is by "
                  "Welch's t, significant (better or worse) when |pct| > halfWidth.",
}


def index_doc():
    return envelope("ApiIndex", openapi="/api/v1/openapi.json", docs="/api/v1/docs", conventions=CONVENTIONS,
                    functions=[{"name": f.name, "kind": f.kind, "method": f.method, "path": f.path, "summary": f.summary,
                                "params": [{"name": k, "type": _type_name(s), "required": k in f.required, "description": s.get("description", ""),
                                            **({"default": f.defaults[k]} if f.defaults.get(k) is not None else {})}
                                           for k, s in f.params.items()],
                                "result": f.result} for f in FUNCTIONS.values()])


def _type_name(s):
    t = s.get("type", "any")
    return "|".join(t) if isinstance(t, list) else t


def _deps(name, seen=None):
    seen = seen if seen is not None else {}
    if name in seen:
        return seen
    seen[name] = SCHEMAS[name]
    for r in re.findall(r'"\$ref": "#/\$defs/(\w+)"', json.dumps(SCHEMAS[name])):
        _deps(r, seen)
    return seen


def schema_of(name, examples=True):
    """A schema with the definitions it refers to, standalone (JSON Schema 2020-12); without its example, an MCP tool's
    outputSchema (tools/list stays small)."""
    if name not in SCHEMAS:
        raise ApiError("not_found", f"no schema {name!r}", {"schemas": sorted(SCHEMAS)})
    strip = lambda s: s if examples else {k: v for k, v in s.items() if k != "examples"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **strip(SCHEMAS[name]),
            "$defs": {k: strip(v) for k, v in _deps(name).items() if k != name}}


def openapi():
    """The OpenAPI 3.1 document of /api/v1, from SCHEMAS and FUNCTIONS."""
    comp = json.loads(json.dumps(SCHEMAS).replace('"#/$defs/', '"#/components/schemas/'))
    paths = {"/api/v1": {"get": {"operationId": "index", "summary": "This API's index: every function, its parameters and result",
                                 "responses": {"200": _resp("ApiIndex")}}},
             "/api/v1/openapi.json": {"get": {"operationId": "openapi", "summary": "This document",
                                              "responses": {"200": {"description": "OpenAPI 3.1", "content": {"application/json": {"schema": {"type": "object"}}}}}}},
             "/api/v1/docs": {"get": {"operationId": "docs", "summary": "The reference page, from this document",
                                      "responses": {"200": {"description": "HTML", "content": {"text/html": {"schema": {"type": "string"}}}}}}}}
    errors = {str(ERRORS[c]): {"$ref": f"#/components/responses/{c}"} for c in ("bad_request", "not_found", "internal")}
    for f in FUNCTIONS.values():
        params = json.loads(json.dumps(f.input_schema()).replace('"#/$defs/', '"#/components/schemas/'))
        op = {"operationId": f.name, "summary": f.summary, "description": f.description, "tags": [f.kind],
              "responses": {"200": _resp(f.result), **errors}}
        if f.kind == "read":
            op["parameters"] = [{"name": k, "in": "query", "required": k in f.required, "description": s.get("description", ""),
                                 "schema": s} for k, s in params["properties"].items()]
        else:
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": params}}}
            op["security"] = [{"token": []}]
            op["responses"].update({"403": {"$ref": "#/components/responses/forbidden"}, "409": {"$ref": "#/components/responses/conflict"},
                                    "503": {"$ref": "#/components/responses/no_server"}})
        paths[f.path] = {f.method.lower(): op}
    return {"openapi": "3.1.0",
            "info": {"title": "perflab API", "version": str(API_VERSION),
                     "description": (__doc__ or "").split("\n\n")[0] + "\n\n" + "\n\n".join(f"**{k}**: {v}" for k, v in CONVENTIONS.items())},
            "servers": [{"url": "http://127.0.0.1:8690", "description": "perflab server (its default port)"}],
            "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
            "paths": paths,
            "components": {"schemas": comp,
                           "securitySchemes": {"token": {"type": "apiKey", "in": "header", "name": "X-Perflab-Token",
                                                         "description": "The server's token (~/.perflab/server/token); POSTs from the server's own origin only"}},
                           "responses": {c: {"description": f"{c} ({s})", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
                                         for c, s in ERRORS.items()}}}


def _resp(name):
    return {"description": SCHEMAS[name]["description"], "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{name}"}}},
            "links": {}, "headers": {"Link": {"description": "rel=describedby: this response's schema", "schema": {"type": "string"}}}}


def docs_page():
    """The reference page: every function and schema, from the OpenAPI document."""
    import html
    from . import ui
    esc = html.escape
    doc = openapi()

    def type_of(s):
        if "$ref" in s:
            n = s["$ref"].rsplit("/", 1)[-1]
            return f'<a href="#s-{n}">{n}</a>'
        if "anyOf" in s:
            return " | ".join(type_of(x) for x in s["anyOf"])
        t = s.get("type", "any")
        if t == "array" or t == ["array", "null"]:
            return f"array of {type_of(s.get('items', {}))}" + (" | null" if isinstance(t, list) else "")
        if s.get("type") == "object" and isinstance(s.get("additionalProperties"), dict):
            return f"map of {type_of(s['additionalProperties'])}"
        return esc("|".join(t) if isinstance(t, list) else str(t)) + (f" ({esc(', '.join(map(str, s['enum'])))})" if "enum" in s else "")

    def props(s, depth=0):
        rows = []
        for k, v in (s.get("properties") or {}).items():
            req = k in (s.get("required") or [])
            rows.append(f'<tr><td style="padding-left:{10 + 16 * depth}px"><code>{esc(k)}</code>{"" if req else " <span class=k>optional</span>"}</td>'
                        f'<td>{type_of(v)}</td><td>{esc(v.get("description", ""))}</td></tr>')
            inner = v if v.get("type") in ("object", ["object", "null"]) else v.get("items") if isinstance(v.get("items"), dict) and v["items"].get("type") == "object" else None
            if inner and inner.get("properties"):
                rows += props(inner, depth + 1)
        return rows

    fns = []
    for path, ops in doc["paths"].items():
        for method, op in ops.items():
            params = op.get("parameters") or [{"name": k, "required": k in op["requestBody"]["content"]["application/json"]["schema"]["required"],
                                               "description": v.get("description", ""), "schema": v}
                                              for k, v in op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("properties", {}).items()]
            res = op["responses"]["200"]["content"].get("application/json", {}).get("schema", {})
            rows = "".join(f'<tr><td><code>{esc(p["name"])}</code>{"" if p["required"] else " <span class=k>optional</span>"}</td>'
                           f'<td>{type_of(p["schema"])}</td><td>{esc(p["description"])}</td></tr>' for p in params)
            fns.append(f'<section class="card" id="f-{esc(op["operationId"])}"><div class="card-h"><h2><span class="m {method}">{method.upper()}</span> '
                       f'<code>{esc(path)}</code></h2><span class="kind">{esc(", ".join(op.get("tags", [])))}</span></div>'
                       f'<p class="facts">{esc(op.get("description") or op["summary"])}</p>'
                       + (f'<table class="t"><tr><th>{"query" if method == "get" else "body"}</th><th>type</th><th></th></tr>{rows}</table>' if rows else "")
                       + f'<p class="k">Returns {type_of(res) if res else "HTML"}'
                       + (' · needs <code>X-Perflab-Token</code>' if op.get("security") else "") + '</p></section>')
    schemas = "".join(f'<section class="card" id="s-{esc(n)}"><div class="card-h"><h2>{esc(n)}</h2><span class="kind">schema</span></div>'
                      f'<p class="facts">{esc(s.get("description", ""))}</p><table class="t"><tr><th>field</th><th>type</th><th></th></tr>{"".join(props(s))}</table></section>'
                      for n, s in doc["components"]["schemas"].items())
    conv = "".join(f"<li><b>{esc(k)}</b>: {esc(v)}</li>" for k, v in CONVENTIONS.items())
    toc = " · ".join(f'<a href="#f-{f.name}">{f.name}</a>' for f in FUNCTIONS.values())
    css = ("main{max-width:1100px;margin:0 auto;padding:16px 20px 40px} .m{font-size:11px;border-radius:4px;padding:0 5px;color:var(--panel)}"
           " .m.get{background:var(--ok)} .m.post{background:var(--warn)} table.t td{font-size:12.5px}")
    return (ui.HEAD + "<title>perflab API</title>" + ui.style(ui.BASE, css) + "<body>" + ui.masthead("API", "/", slim=False)
            + f'<main><section class="card"><h2>perflab API v{API_VERSION}</h2><p class="facts">{esc(" ".join(doc["info"]["description"].split(chr(10) * 2)[0].split()))}</p>'
            f'<p>Machine-readable: <a href="/api/v1/openapi.json">openapi.json</a> (OpenAPI 3.1) · <a href="/api/v1">the index</a>. '
            f'Also an MCP server (<code>perflab mcp</code>) and a CLI (<code>perflab api</code>).</p><ul>{conv}</ul><p class="k">{toc}</p></section>'
            f'<h2>Functions</h2>{"".join(fns)}<h2>Schemas</h2>{schemas}</main>' + ui.footer() + '</body>')


# ---- for agents: /llms.txt (llmstxt.org) and the perflab skill, as /skill.md

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                     ".claude", "skills", "perflab", "SKILL.md")  # in the jvm-perf-lab checkout this perflab runs from


def skill_md():
    """The perflab skill (how to run, check and report benchmarks), or None outside a jvm-perf-lab checkout."""
    try:
        with open(SKILL, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def llms_txt():
    """/llms.txt: what this server is and where an agent reads on, from FUNCTIONS and CONVENTIONS."""
    fns = lambda kind: "\n".join(f"- [{f.name}]({f.path}): {f.summary}" for f in FUNCTIONS.values() if f.kind == kind)
    conv = "\n".join(f"- **{k}**: {v}" for k, v in CONVENTIONS.items())
    return f"""# perflab server

> A per-user server for perflab (jvm-perf-lab): a queue of JMH benchmark jobs run one at a time, every registered project's results (A/B campaigns, branch campaigns over a commit range, profiles and their diffs), and an API over them for agents.

Read campaign results through the API rather than parsing files or HTML pages. The same functions are an MCP server (`claude mcp add perflab -- perflab mcp`) and a CLI (`perflab api --list`, `perflab api <function> --<param> <value>`). Before running or reporting benchmarks, read the perflab skill.

## Docs

- [perflab skill](/skill.md): how to run, check and report benchmarks with perflab, and which API function answers what
- [API reference](/api/v1/docs): every function, its parameters, and the JSON schema of every response
- [OpenAPI 3.1](/api/v1/openapi.json): the machine-readable API
- [API index](/api/v1): the functions as JSON

## Conventions

{conv}

## Reads (GET, no token)

{fns("read")}

## Actions (POST, X-Perflab-Token; they change what the user is measuring: ask first)

{fns("action")}

## Optional

- [Queue](/): jobs, with pause, resume and cancel
- [Storage](/admin): storage per campaign, with cleanup
"""


# ---- HTTP, for perflab.server's handler

def described_by(schema):
    """The Link header of a response of `schema`."""
    return f'</api/v1/openapi.json#/components/schemas/{schema}>; rel="describedby"'


def http_get(path, query, server):
    """(status, body, content type, schema name) of a GET under /api/v1."""
    if path in ("/api/v1", "/api/v1/"):
        return 200, index_doc(), "application/json", "ApiIndex"
    if path == "/api/v1/openapi.json":
        return 200, openapi(), "application/json", None
    if path == "/api/v1/docs":
        return 200, docs_page(), "text/html; charset=utf-8", None
    m = re.fullmatch(r"/api/v1/schemas/(\w+)", path)
    if m:
        return 200, schema_of(m.group(1)), "application/json", None
    name = path.removeprefix("/api/v1/")
    fn = FUNCTIONS.get(name)
    if fn is None:
        raise ApiError("not_found", f"no function {name!r}: see GET /api/v1", {"functions": sorted(FUNCTIONS)})
    if fn.kind != "read":
        raise ApiError("bad_request", f"{name} is an action: POST it, with X-Perflab-Token")
    args = coerce(fn, query)
    if "project" in fn.params:
        args["project"] = resolve(args.get("project"), registered_only=True)["id"]
    return 200, call(name, args, server), "application/json", fn.result


def http_post(path, body, server):
    name = path.removeprefix("/api/v1/")
    fn = FUNCTIONS.get(name)
    if fn is None:
        raise ApiError("not_found", f"no function {name!r}: see GET /api/v1", {"functions": sorted(FUNCTIONS)})
    if fn.kind != "action":
        raise ApiError("bad_request", f"{name} is a read: GET it")
    if "project" in fn.params:
        pr = body.get("project")
        if pr and (os.sep in pr or os.path.isdir(pr)):  # a root: registered as POST /api/projects would
            try:
                body = {**body, "project": server.q.register(pr)["id"]}
            except ValueError as e:
                raise ApiError("not_found", str(e)) from None
    return 200, call(name, body, server), "application/json", fn.result


# ---- CLI: perflab api

def main(argv):
    """perflab api <function> [--<param> <value>]... | --list | --schema <name> | --openapi   (--root <project>)"""
    global DEFAULT_ROOT
    DEFAULT_ROOT = os.environ.get("PERFLAB_ROOT") or os.getcwd()
    out = lambda x: print(json.dumps(x, indent=2, ensure_ascii=False))
    if "--root" in argv:
        i = argv.index("--root")
        DEFAULT_ROOT = os.path.abspath(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv or argv[0] in ("-h", "--help"):
        print(main.__doc__ + "\n\nFunctions:\n" + "\n".join(f"  {f.name:13} {f.kind:6} {f.summary}" for f in FUNCTIONS.values())
              + "\n\nConventions:\n" + "\n".join(f"  {k}: {v}" for k, v in CONVENTIONS.items()))
        return 0 if argv else 2
    if argv[0] == "--list":
        out(index_doc())
        return 0
    if argv[0] == "--schema":
        try:
            out(schema_of(argv[1]) if len(argv) > 1 else {"schemas": sorted(SCHEMAS)})
        except ApiError as e:
            out(e.body())
            return 1
        return 0
    if argv[0] == "--openapi":
        out(openapi())
        return 0
    name, rest = argv[0], argv[1:]
    fn = FUNCTIONS.get(name)
    try:
        if fn is None:
            raise ApiError("not_found", f"no function {name!r}", {"functions": sorted(FUNCTIONS)})
        query = {}
        while rest:
            k = rest.pop(0)
            if not k.startswith("--"):
                raise ApiError("bad_request", f"{k!r}: expected --<param> <value>", {"params": list(fn.params)})
            k = k[2:].replace("-", "_")
            t = (fn.params.get(k) or {}).get("type")
            if t == "boolean" and (not rest or rest[0].startswith("--")):
                query[k] = "true"
            elif t == "array":
                query.setdefault(k, [])
                query[k] = query[k] + [rest.pop(0)] if rest else query[k]
            else:
                if not rest:
                    raise ApiError("bad_request", f"--{k} needs a value")
                query[k] = rest.pop(0)
        arrays = {k: v for k, v in query.items() if isinstance(v, list)}
        args = {**coerce(fn, {k: v for k, v in query.items() if k not in arrays}), **arrays}
        out(call(name, args))
        return 0
    except ApiError as e:
        out(e.body())
        return 1
