#!/usr/bin/env python3
"""Copies what the benchmark reads from out/ into a self-contained directory, out/bundles/<name>, for a remote worker.

The list files there (inputs/<project>/*.txt, cp/*.txt) name paths relative to the bundle, which the driver resolves
against it; a spec names the bundle with `-Dzincdirect.out=<its path>` in "jvmArgs", which the worker maps and copies
when it lacks it (doc/remote-workers.md). Usage:

  make-bundle.py <name> --zinc dev-cb --scala 2.13.18 2.13.19-bin-762d80f-SNAPSHOT --projects actor stream
"""
import argparse
import os
import shutil
import sys

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(here, "out")


def lines(p):
    with open(p) as f:
        return [l.strip() for l in f if l.strip()]


def write(p, xs):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write("\n".join(xs) + "\n")


def place(src, rel, bundle):
    """Copies a file or directory to <bundle>/<rel> once; returns rel."""
    dst = os.path.join(bundle, rel)
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    return rel


def under_out(p, prefix, bundle):
    """A path inside the lab's out/ keeps its place; anything else goes to <prefix>/<basename>."""
    rel = os.path.relpath(p, out)
    return place(p, rel if not rel.startswith("..") else os.path.join(prefix, os.path.basename(p)), bundle)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("name")
    a.add_argument("--zinc", nargs="+", required=True)
    a.add_argument("--scala", nargs="+", required=True)
    a.add_argument("--projects", nargs="+", required=True)
    o = a.parse_args()
    bundle = os.path.join(out, "bundles", o.name)
    shutil.rmtree(bundle, ignore_errors=True)
    for z in o.zinc:
        write(os.path.join(bundle, "cp", f"zinc-{z}.txt"),
              [under_out(j, f"cp/zinc-{z}", bundle) for j in lines(os.path.join(out, "cp", f"zinc-{z}.txt"))])
        d = os.path.join(out, "cp", f"driver-{z}")
        if os.path.isdir(d):
            place(d, f"cp/driver-{z}", bundle)
        for v in o.scala:
            b = os.path.join(out, "bridge", f"bridge-{z}-{v}.jar")
            if not os.path.exists(b):
                sys.exit(f"no bridge {b}")
            place(b, f"bridge/bridge-{z}-{v}.jar", bundle)
    for v in o.scala:
        write(os.path.join(bundle, "cp", f"scala-{v}.txt"),
              [under_out(j, f"cp/scala-{v}", bundle) for j in lines(os.path.join(out, "cp", f"scala-{v}.txt"))])
    for p in o.projects:
        src = os.path.join(out, "inputs", p)
        dst = os.path.join(bundle, "inputs", p)
        write(os.path.join(dst, "sources.txt"), [under_out(s, "src", bundle) for s in lines(os.path.join(src, "sources.txt"))])
        write(os.path.join(dst, "classpath.txt"), [under_out(c, "lib", bundle) for c in lines(os.path.join(src, "classpath.txt"))])
        for f in ("scalac.txt", "javac.txt"):
            shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(bundle) for f in fs)
    print(f"{bundle}: {size / 1e6:.0f} MB")


main()
