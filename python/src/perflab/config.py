"""A project's `perflab.toml`, found from the working directory upward; the project root is the directory holding it.

    [build]
    # runs JMH; {args} is an arguments file (passed as `@file` to perflab's JMH driver, io.github.retronym.perflab.jmh.Main)
    jmh = "sbt --client 'bench/Jmh/run {args}'"
    # which process tree runs the benchmarks, so the load gate does not count it as competing load:
    # "sbt" (the sbt server of this checkout, from project/target/active.json) or "self" (perflab's own children)
    server = "sbt"

    [benchmark]
    default = "CompileBenchmark"      # the benchmark a campaign runs unless its spec names one
    corpus = "corpus"                 # the JMH parameter a campaign's "corpora" set
    variants = "variants"             # the JMH parameter of variants within a fork (Variants.parse)
    jvmArgs = "-Xms4G -Xmx4G -Xss2M"  # given to every run (JMH's -jvmArgsAppend replaces @Fork's)

    [paths]
    runs = "out/perflab/runs"         # perflab run
    campaigns = "out/perflab/ab"      # perflab ab

    [index]
    flags = "^-D"                     # JVM arguments shown as a run's flags

    [agent]
    jar = "path/to/perflab-agent.jar" # for audits

    [async]
    lib = "path/to/libasyncProfiler.dylib"   # default: $ASYNC_PROFILER_LIB, then the usual install locations
    jfrconv = "path/to/jfrconv"              # default: $JFRCONV, then beside lib, then the PATH
    stackdepth = 8192                        # frames per stack; default: async-profiler's 2048
    spans = true                             # the span panel on `bench` graphs (jfrconv --spans)
    span_config = "span-config.json"         # the span panel's groupings (implies spans)

    [analyze]
    phases = "perflab-phases.toml"    # phase table for `perflab analyze`
"""
import os, tomllib

DEFAULTS = {
    "build": {"jmh": "", "server": "self"},
    "benchmark": {"default": "", "corpus": "corpus", "variants": "variants", "jvmArgs": ""},
    "paths": {"runs": "out/perflab/runs", "campaigns": "out/perflab/ab"},
    "index": {"flags": "^-D"},
    "agent": {"jar": ""},
    "async": {"lib": "", "jfrconv": "", "stackdepth": "", "spans": False, "span_config": ""},
    "analyze": {"phases": ""},
}


class Config:
    def __init__(self, root, data):
        self.root = root
        self.data = {k: {**v, **data.get(k, {})} for k, v in DEFAULTS.items()}
        for k, v in data.items():
            self.data.setdefault(k, v)

    def get(self, section, key):
        return self.data.get(section, {}).get(key)

    def path(self, section, key):
        """A configured path, relative to the project root unless absolute; None if unset."""
        v = self.get(section, key)
        return os.path.join(self.root, os.path.expanduser(v)) if v else None

    @property
    def runs(self):
        return self.path("paths", "runs")

    @property
    def campaigns(self):
        return self.path("paths", "campaigns")


def find(start=None):
    d = os.path.abspath(start or os.getcwd())
    while True:
        f = os.path.join(d, "perflab.toml")
        if os.path.exists(f):
            with open(f, "rb") as fh:
                return Config(d, tomllib.load(fh))
        parent = os.path.dirname(d)
        if parent == d:
            return Config(os.path.abspath(start or os.getcwd()), {})
        d = parent


_config = None


def get():
    global _config
    if _config is None:
        _config = find(os.environ.get("PERFLAB_ROOT"))
    return _config
