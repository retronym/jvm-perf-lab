"""AOT caches (Project Leyden, JEP 483/514/515) for a campaign's forks.

A variant whose JVM flags contain `{aot}` runs from an AOT cache: perflab trains one per build, corpus and cache index
with a JMH fork of its own (`-XX:AOTCacheOutput`), keeps it in <campaign>/.aot/<build>/<corpus>/<k>/, and replaces
`{aot}` in the variant's flags with `-XX:AOTMode=on -XX:AOTCache=<cache>` (plus `-Xlog:aot` into the cell), so a fork
that cannot use its cache fails instead of quietly running cold.

    "aot": {"train": "-wi 8 -i 5",   # JMH arguments for the training fork, after the corpus's (default: none)
            "caches": 3}             # caches per build and corpus (default 1); round r uses cache (r-1) % caches + 1

Each training directory keeps the training fork's jmh.log and result.json (its score labels the cache) and aot.json
(the cache's size and sha256, the load during training). Each cell that used a cache gets an aot.json naming it.

The cache needs the fork's class path to be JARs (the JVM refuses directories): a campaign with `{aot}` runs in launch
mode, with the snapshot's class path directories jarred (launch.jar_dirs). It is valid only for the JDK, class path
and module options it was trained with; perflab trains with the campaign's `jvmArgs` and nothing of the variant's but
`{aot}`, so variant flags must not change module options (`--add-modules`, `-javaagent`, JFR).
"""
import hashlib, json, os, time

PLACEHOLDER = "{aot}"
DIR = ".aot"
INFO = "aot.json"
CACHE = "cache.aot"


def uses(spec):
    return any(PLACEHOLDER in (f or "") for f in spec.variants.values())


def options(spec):
    return spec.aot or {}


def caches(spec):
    return int(options(spec).get("caches", 1))


def index(spec, r):
    return (r - 1) % caches(spec) + 1


def build_key(spec, variant):
    return variant if spec.builds.get(variant) is not None else "default"


def train_dir(spec, variant, corpus, r):
    return os.path.join(spec.out, DIR, build_key(spec, variant), corpus, str(index(spec, r)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def trained(tdir):
    return os.path.exists(os.path.join(tdir, CACHE)) and os.path.exists(os.path.join(tdir, INFO))


def expand(flags, tdir, dest):
    """The variant's flags with `{aot}` replaced by the options that use the cache in `tdir`, logging into `dest`."""
    use = f"-XX:AOTMode=on -XX:AOTCache={os.path.join(tdir, CACHE)} -Xlog:aot:file={os.path.join(dest, 'aot.log')}"
    return flags.replace(PLACEHOLDER, use)


def train(spec, corpus, iters, variant, r, built, run_fork, log):
    """Trains the cache for this cell's build, corpus and index unless it exists; its directory.
    `run_fork(cmd, dest)` runs a JMH command like a cell and returns (exit code, mean other load)."""
    tdir = train_dir(spec, variant, corpus, r)
    if trained(tdir):
        return tdir
    os.makedirs(tdir, exist_ok=True)
    cache = os.path.join(tdir, CACHE)
    for f in (cache, cache + ".config"):
        if os.path.exists(f):
            os.unlink(f)
    train_iters = " ".join(x for x in [iters, options(spec).get("train", "")] if x)
    cmd = spec.command(corpus, train_iters, None, f"-XX:AOTCacheOutput={cache}", tdir, built)
    log(f"training AOT cache {os.path.relpath(tdir, spec.out)} ({train_iters})")
    started = time.time()
    rc, load = run_fork(cmd, tdir)
    if rc or not os.path.exists(cache):
        raise SystemExit(f"{tdir}: the training fork " + (f"exited with {rc}" if rc else "wrote no cache") + " (see build.log, jmh.log)")
    score = None
    try:
        res = json.load(open(os.path.join(tdir, "result.json")))[0]["primaryMetric"]
        score = {"score": res["score"], "error": res["scoreError"], "unit": res["scoreUnit"],
                 "iterations": [x for fork in res.get("rawData", []) for x in fork]}
    except (OSError, ValueError, LookupError):
        pass
    info = {"cache": cache, "size": os.path.getsize(cache), "sha256": sha256(cache), "index": index(spec, r),
            "build": build_key(spec, variant), "corpus": corpus, "trainArgs": train_iters, "jvm": spec.jvm,
            "started": started, "seconds": time.time() - started, "otherLoad": load, "training": score}
    with open(os.path.join(tdir, INFO), "w") as f:
        json.dump(info, f, indent=2)
    log(f"  cache {info['size'] / 1e6:.0f} MB" + (f", training fork {score['score']:.1f} {score['unit']}" if score else ""))
    return tdir


def check(tdir, dest):
    """Whether the cell's fork used the cache: None, or what is wrong. Records the cache in <dest>/aot.json."""
    try:
        text = open(os.path.join(dest, "aot.log"), errors="replace").read()
    except OSError:
        return "no aot.log: the fork was not given -Xlog:aot"
    if "Using AOT-linked classes: true" not in text:
        return "the fork did not use its AOT cache (see aot.log)"
    info = json.load(open(os.path.join(tdir, INFO)))
    with open(os.path.join(dest, INFO), "w") as f:
        json.dump({k: info[k] for k in ("cache", "sha256", "index", "build", "corpus", "training") if k in info}, f, indent=2)
    return None
