"""perflab <command> [arguments]

  run        one JMH run under a profile (none, xctrace:<template>, async:<events>, audit:<spec>)
  ab         campaigns: run and report variants over corpora, interleaved and checked
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

Configuration: perflab.toml in the project (see perflab.config). `perflab <command> --help` for a command's options.

  perflab --transcript <file> <command> ...   appends progress and the build's output to <file> as they come
                                              (perflab.transcript), for a caller to follow
"""
import importlib, sys

COMMANDS = {"run": "jmh", "ab": "ab", "trees": "trees", "index": "index", "timeline": "timeline", "regraph": "regraph",
            "profdiff": "profdiff", "inlinetree": "inlinetree", "frameweight": "frameweight", "subtree": "subtree", "analyze": "analyze",
            "auditfold": "auditfold", "loadgate": "loadgate", "site": "site", "serve": "serve", "defcosts": "defcosts"}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--transcript"] and len(argv) > 1:
        from . import transcript
        transcript.setup(argv[1])
        argv = argv[2:]
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    module = importlib.import_module(f".{COMMANDS[argv[0]]}", __package__)
    return module.main(argv[1:]) or 0
