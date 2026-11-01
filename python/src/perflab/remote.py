"""The coordinator's side of remote workers (doc/remote-workers.md; the worker's is perflab.worker).

A job of another testbed is `ab run <spec>`. When a worker claims it, `prepare` resolves what the worker needs into
<job dir>/remote.json, the job's payload: the spec as the coordinator has it, the spec version its cells are tagged
with, the harness (the project's repository at HEAD and its uncommitted diff), each build's checkout as a commit with
its repository's remotes, the JDK the spec names (its `release` file), and the coordinator's home and repository paths,
for the worker to map. `bundle` makes a git bundle of a commit for a worker that cannot fetch it, `finished_cells` the
campaign's finished cells (their results only) for it to resume from, and `receive` puts a unit the worker uploads (a
cell, a voided attempt, the campaign's top-level files) in place.
"""
import io, json, os, re, shutil, subprocess, tarfile, tempfile, time

from . import ab, config, specs, testbed

PAYLOAD = "remote.json"  # in the job's directory
# the campaign's top-level files that are the coordinator's own: the worker's copies name the worker's paths
OWN = {"spec.json", ab.SOURCE, "jfrsync.jfc", "index.html", ab.RUNNING_NAME}
CELL_UNIT = re.compile(r"[^./][^/]*/[^/]+/\d+")
VOID_UNIT = re.compile(r"\.void/[^./][^/]*/[^/]+/[^/]+")
# what a finished cell contributes to a resume: its result, and what says it is the campaign's and of which version
RESUME_FILES = ("result.json", testbed.CELL_FILE, specs.CELL_FILE)


def git(d, *args, check=True, binary=False):
    p = subprocess.run(["git", "-C", d, *args], capture_output=True, text=not binary)
    if check and p.returncode:
        err = p.stderr if not binary else p.stderr.decode(errors="replace")
        raise ValueError(f"git {' '.join(args)} in {d}: {err.strip()}")
    return p.stdout.strip() if not binary else p.stdout


def remotes(d):
    """{name: url} of the repository's remotes."""
    out = {}
    for line in git(d, "remote", "-v", check=False).splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out.setdefault(parts[0], parts[1])
    return out


def repo_key(d, rs):
    """A name for the repository on the worker (its mirror's): the origin's (or the first remote's) basename, else the
    repository's directory's, with a hash of where it comes from."""
    import hashlib
    url = rs.get("origin") or next(iter(rs.values()), None)
    common = os.path.realpath(os.path.join(d, git(d, "rev-parse", "--git-common-dir")))
    src = url or common
    base = os.path.basename(src.rstrip("/")).removesuffix(".git") or "repo"
    if base == ".git" or not url:
        base = os.path.basename(os.path.dirname(common)) if os.path.basename(common) == ".git" else base
    return re.sub(r"[^A-Za-z0-9_.-]", "-", base) + "-" + hashlib.sha1(src.encode()).hexdigest()[:6]


def source(checkout, what):
    """A clean checkout as a commit: {checkout, commit, tree, key, remotes}; ValueError for a dirty one or no checkout."""
    if not os.path.isdir(checkout):
        raise ValueError(f"{what}: no checkout at {checkout}")
    try:
        commit = git(checkout, "rev-parse", "HEAD")
    except ValueError:
        raise ValueError(f"{what}: {checkout} is not a git checkout") from None
    dirty = git(checkout, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise ValueError(f"{what}: {checkout} has uncommitted changes, which a worker could not build; commit them "
                         f"(a measured tree should be a commit): {dirty.splitlines()[0]}…")
    rs = remotes(checkout)
    return {"checkout": checkout, "commit": commit, "tree": git(checkout, "rev-parse", "HEAD^{tree}"), "key": repo_key(checkout, rs), "remotes": rs}


def harness(root):
    """The project's repository: {top, rel (the project in it), commit, diff (uncommitted, of tracked files), key, remotes}."""
    try:
        top = git(root, "rev-parse", "--show-toplevel")
    except ValueError:
        raise ValueError(f"the project {root} is not in a git repository, which a worker needs to check it out") from None
    rs = remotes(top)
    return {"top": top, "rel": os.path.relpath(root, top), "commit": git(top, "rev-parse", "HEAD"),
            "diff": git(top, "diff", "HEAD", "--binary", binary=True).decode(errors="surrogateescape"),
            "key": repo_key(top, rs), "remotes": rs}


def jdk(java):
    """A `java` as the worker matches it: its path and its JDK's `release` file ({JAVA_VERSION, IMPLEMENTOR, ...})."""
    home = os.path.dirname(os.path.dirname(os.path.realpath(java)))
    rel = {}
    try:
        with open(os.path.join(home, "release")) as f:
            for line in f:
                k, eq, v = line.strip().partition("=")
                if eq:
                    rel[k] = v.strip().strip('"')
    except OSError:
        pass
    return {"path": java, "home": home, "release": rel}


def _spec(argv, cwd):
    path = next((a for a in argv if a.endswith(".json")), None)
    if argv[:2] != ["ab", "run"] or path is None:
        raise ValueError("a job on another testbed is `ab run <spec.json>`")
    path = os.path.abspath(os.path.join(cwd, path))
    with open(path) as f:
        return path, json.load(f)


def check(argv, cwd, project):
    """What the worker needs, resolved (without the harness's diff); ValueError for what it could not run."""
    path, spec = _spec(argv, cwd)
    if spec.get("branch") or spec.get("profileOf"):
        raise ValueError("a branch campaign (or its profiles) runs on this machine only, for now: no \"testbed\"")
    cfg = config.find(project["root"])
    out = os.path.join(cfg.campaigns, spec["name"])
    here = ab.spec_dir(path, out)
    sources = {}
    for v, b in (spec.get("builds") or {}).items():
        if b.get("checkout"):
            sources[v] = source(os.path.normpath(os.path.join(here, b["checkout"])), f"build {v}")
    if spec.get("jvm") and not os.path.exists(spec["jvm"]):
        raise ValueError(f"jvm {spec['jvm']} is not there: the worker matches the JDK by its release file")
    return path, spec, out, sources


def prepare(job, project):
    """The job's payload for a worker, written to <job dir>/remote.json; the campaign gets its spec, as `ab run` gives
    it, so that the index lists the campaign and its plan."""
    path, spec, out, sources = check(job["argv"], job["cwd"], project)
    os.makedirs(out, exist_ok=True)
    if not ab.is_copy(path, out):
        shutil.copy(path, os.path.join(out, "spec.json"))
        with open(os.path.join(out, ab.SOURCE), "w") as f:
            f.write(path + "\n")
    payload = {"job": job["id"], "argv": job["argv"], "spec": spec, "specVersion": specs.record(out, path),
               "campaign": spec["name"], "testbed": job["testbed"], "harness": harness(project["root"]),
               "sources": sources, "jvm": jdk(spec["jvm"]) if spec.get("jvm") else None,
               "home": os.path.expanduser("~"), "prepared": time.time()}
    with open(os.path.join(job["dir"], PAYLOAD + ".tmp"), "w") as f:
        json.dump(payload, f)
    os.replace(os.path.join(job["dir"], PAYLOAD + ".tmp"), os.path.join(job["dir"], PAYLOAD))
    return payload


def payload(job):
    with open(os.path.join(job["dir"], PAYLOAD)) as f:
        return json.load(f)


def campaign_dir(job, project):
    return os.path.join(config.find(project["root"]).campaigns, payload(job)["campaign"])


def bundle(job, name, full=False):
    """A git bundle (a temporary file's path) of the commit of source `name` (a variant, or "harness"): of what the
    repository's remotes do not already have, unless `full` (its whole history), or the remotes have all of it."""
    p = payload(job)
    src = p["harness"] if name == "harness" else p["sources"].get(name)
    if not src:
        raise KeyError(name)
    repo = src.get("checkout") or src["top"]
    sha = src["commit"]
    ref = f"refs/perflab/bundle/{sha}"
    fd, out = tempfile.mkstemp(prefix="perflab-", suffix=".bundle")
    os.close(fd)
    git(repo, "update-ref", ref, sha)  # a bundle carries refs, not bare commits
    try:
        r = None
        if not full:
            r = subprocess.run(["git", "-C", repo, "bundle", "create", "-q", out, ref, "--not", "--remotes"], capture_output=True, text=True)
        if full or r.returncode:  # also when the remotes have it all ("empty bundle"): the worker could not fetch it
            git(repo, "bundle", "create", "-q", out, ref)
    finally:
        git(repo, "update-ref", "-d", ref, check=False)
    return out


def finished_cells(job, project):
    """A tar.gz of the campaign's finished cells of the job's testbed (RESUME_FILES of each), for the worker to resume from."""
    d = campaign_dir(job, project)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if os.path.isdir(d):
            for corpus in sorted(os.listdir(d)):
                if corpus.startswith(".") or not os.path.isdir(os.path.join(d, corpus)):
                    continue
                for variant in sorted(os.listdir(os.path.join(d, corpus))):
                    vd = os.path.join(d, corpus, variant)
                    if not os.path.isdir(vd):
                        continue
                    for r in sorted(os.listdir(vd)):
                        cell = os.path.join(vd, r)
                        if r.isdigit() and ab.done(cell) and testbed.of_cell(cell) == job["testbed"]:
                            for f in RESUME_FILES:
                                if os.path.exists(os.path.join(cell, f)):
                                    tar.add(os.path.join(cell, f), f"{corpus}/{variant}/{r}/{f}")
    return buf.getvalue()


PATH_IN = re.compile(r"(?:^|(?<=[\s:=,'\"]))(/[^\s:,'\"]+)")


def input_paths(spec):
    """The absolute paths the spec's JVM arguments, profiler library and JMH arguments name: its inputs."""
    texts = [spec.get(k) for k in ("jvmArgs", "lib")]
    texts += list((spec.get("corpora") or {}).values()) + list((spec.get("variants") or {}).values())
    texts += list((spec.get("variantJmhArgs") or {}).values())
    return sorted({p.rstrip("/") for t in texts if isinstance(t, str) for p in PATH_IN.findall(t)})


def input_tar(job, path):
    """A tar.gz of an input the job's spec names (a file or a directory, its basename at the root), for a worker that
    lacks it; only a path the spec names, under this machine's home, is sent."""
    p = payload(job)
    home = os.path.realpath(os.path.expanduser("~"))
    real = os.path.realpath(path)
    if path not in input_paths(p["spec"]):
        raise ValueError(f"{path} is not an input of the job's spec")
    if not (real.startswith(home + os.sep)) or any(seg.startswith(".") and seg not in (".m2", ".ivy2", ".sbt", ".cache")
                                                  for seg in os.path.relpath(real, home).split(os.sep)[:1]):
        raise ValueError(f"{path} is not under the coordinator's home (or is in a hidden directory there)")
    if not (os.path.isfile(real) or os.path.isdir(real)):
        raise KeyError(path)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(real, os.path.basename(path))
    return buf.getvalue()


def unit_ok(unit):
    return unit == "." or bool(CELL_UNIT.fullmatch(unit) or VOID_UNIT.fullmatch(unit))


def receive(job, project, unit, stream, length):
    """Puts the unit (a cell `<corpus>/<variant>/<round>`, a voided attempt `.void/...`, or "." for the campaign's
    top-level files) the worker sends as a tar.gz of `length` bytes from `stream` in the campaign. A cell or voided
    attempt replaces the one there whole; top-level files are put one by one, never the coordinator's OWN."""
    if not unit_ok(unit):
        raise ValueError(f"not a unit of a campaign: {unit!r}")
    d = campaign_dir(job, project)
    os.makedirs(d, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".incoming-", dir=d)
    try:
        blob = os.path.join(tmp, ".tar.gz")
        with open(blob, "wb") as f:
            left = length
            while left > 0:
                chunk = stream.read(min(left, 1 << 20))
                if not chunk:
                    raise ValueError(f"the upload ended {left} bytes short")
                f.write(chunk)
                left -= len(chunk)
        new = os.path.join(tmp, "unit")
        os.makedirs(new)
        with tarfile.open(blob) as tar:
            tar.extractall(new, filter="data")  # nothing outside it, no links out, no devices
        if unit == ".":
            for name in os.listdir(new):
                src = os.path.join(new, name)
                if name in OWN or name.startswith(".") or not os.path.isfile(src):
                    continue
                os.replace(src, os.path.join(d, name))
            return []
        dest = os.path.join(d, unit)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        old = None
        if os.path.exists(dest):
            old = os.path.join(tmp, "old")
            os.replace(dest, old)
        os.replace(new, dest)
        return [dest]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
