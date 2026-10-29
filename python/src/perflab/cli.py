"""perflab <command> [arguments]

  run        one JMH run under a profile (none, xctrace:<template>, async:<events>, audit:<spec>)
  ab         campaigns: run and report variants over corpora, interleaved and checked
  branch     a branch campaign's profiles and their diffs (`branch profile <spec> [<commit>...]`, `branch diff <spec> <a> <b>`)
  trees      campaigns across checkouts (builds) instead of flags
  index      index.html of the campaigns and runs, with a live timeline of the running fork
  serve      serve the index on 127.0.0.1 and print its URL (idempotent; `run` and `ab run` do it too)
  timeline   timeline.html for one campaign cell
  regraph    flame graphs of async-profiler runs
  profdiff   two async-profiler runs compared per op
  inlinetree JIT compilation units of async-profiler runs: what was inlined where, against a baseline
  frameweight, subtree   weight of frames, and of one frame's subtree, across runs
  analyze    hot methods and phase split of async-profiler runs
  auditfold  merge and fold caller-audit reports
  loadgate   wait for a quiet machine, or sample competing load
  site       a static site of the campaigns and runs, for publishing
  defcosts   cost per definition from a compiler's table (Scala 3 -Yprofile-defs): histograms, outliers, comparison
  server     the per-user perflab server: a queue of jobs run one at a time, its UI and storage admin (start|stop|status)
  submit     queue `perflab <arguments>` on the server and follow it (`perflab submit -- ab run spec.json`)
  jobs       the server's queue
  api        campaigns, cells, branch history, comparisons and profiles as JSON, and void/rerun/jobs (perflab.api):
             `api --list`, `api <function> --<param> <value>...`, `api --schema <name>`
  mcp        perflab.api as an MCP server on stdio, for agents (`claude mcp add perflab -- perflab mcp`)

While `perflab server` runs, `run` and `ab run` go to its queue as `perflab submit` would and follow the job (Ctrl-C
detaches; it runs on); `--local` runs one here instead, as do `--dry-run` and the commands a job runs.

Configuration: perflab.toml in the project (see perflab.config). `perflab <command> --help` for a command's options.

  perflab --transcript <file> <command> ...   appends progress and the build's output to <file> as they come
                                              (perflab.transcript), for a caller to follow
"""
import importlib, os, signal, sys

from . import transcript

COMMANDS = {"run": "jmh", "ab": "ab", "trees": "trees", "index": "index", "timeline": "timeline", "regraph": "regraph",
            "profdiff": "profdiff", "inlinetree": "inlinetree", "frameweight": "frameweight", "subtree": "subtree", "analyze": "analyze",
            "auditfold": "auditfold", "loadgate": "loadgate", "site": "site", "serve": "serve", "defcosts": "defcosts",
            "server": "server", "submit": "server:submit_main", "jobs": "server:jobs_main",
            "branch": "branchprofile", "api": "api", "mcp": "mcp"}
# the commands that become a job of a running `perflab server`: command -> the subcommands that do (None: all)
SUBMITS = {"run": None, "ab": {"run"}, "branch": {"profile", "diff"}}
LOCAL_ENV = "PERFLAB_LOCAL"  # server.LOCAL_ENV


def submits(argv):
    """`argv` without `--local` (before any `--`), and whether it is a command to submit to a running server."""
    if argv[0] not in SUBMITS:
        return argv, False
    end = argv.index("--") if "--" in argv else len(argv)
    head = argv[:end]
    argv = [a for a in head if a != "--local"] + argv[end:]
    sub = SUBMITS[argv[0]]
    return argv, bool(sub is None or argv[1:2] and argv[1] in sub) and not any(a in ("--local", "--dry-run", "-h", "--help") for a in head)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--transcript"] and len(argv) > 1:
        transcript.setup(argv[1])
        argv = argv[2:]
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    # killed (`timeout`, `kill`, ab stopping its load sampler): exit through `finally` and atexit, so the live state a
    # command publishes for the index (running.json, loadgate.json) is cleared
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
    argv, submit = submits(argv)
    if submit and not os.environ.get(LOCAL_ENV):
        from . import server
        rc = server.delegate(argv)
        if rc is not None:
            return rc
    # in the foreground from here on, and so are the perflab commands this one runs (`trees` runs `ab run`)
    os.environ[LOCAL_ENV] = "1"
    name, _, function = COMMANDS[argv[0]].partition(":")
    module = importlib.import_module(f".{name}", __package__)
    try:
        return getattr(module, function or "main")(argv[1:]) or 0
    except SystemExit as e:
        if isinstance(e.code, str):  # sys.exit with a message, not a status
            transcript.failed(e.code)
        raise
    except BaseException as e:
        transcript.failed(f"{type(e).__name__}: {e}")
        raise
