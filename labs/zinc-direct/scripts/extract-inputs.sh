#!/usr/bin/env bash
# Extracts a Pekko project's compile inputs from sbt into out/inputs/<project>: sources.txt, classpath.txt, scalac.txt,
# javac.txt (README.md). Works on a clone-on-write copy of the pristine checkout (out/pekko, from labs/zinc's
# out/pekko or $PEKKO_CHECKOUT) with labs/zinc's overlay, which the sources and the classpath's class directories then
# live in. A project with sibling dependencies (stream needs actor) must be compiled there first: `compile=1`.
# Usage: extract-inputs.sh <project> [compile]
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
proj=$1
src=${PEKKO_CHECKOUT:-$here/../zinc/out/pekko}
ws=$here/out/pekko
if [ ! -d "$ws" ]; then /bin/cp -cR "$src" "$ws" 2>/dev/null || cp -R "$src" "$ws"; cp -R "$here/../zinc/overlay/." "$ws"; fi
log=$here/out/extract-$proj.log
cmds=('set every targetSystemJdk := true' '++2.13.18!')
[ "${2:-}" = compile ] && cmds+=("$proj/compile")
cmds+=("export $proj/Compile/fullClasspath" "show $proj/Compile/scalacOptions" "show $proj/Compile/javacOptions" "show $proj/Compile/sources")
[ -n "${REUSE_LOG:-}" ] || (cd "$ws" && sbt -batch -Dsbt.color=false -Dsbt.supershell=false "${cmds[@]}" > "$log" 2>&1)
out=$here/out/inputs/$proj
mkdir -p "$out"
python3 -I - "$log" "$out" "$ws/$proj" <<'PY'
import sys, re
log, out, projdir = sys.argv[1:4]
lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
ci = max(i for i, l in enumerate(lines) if l.startswith("/") and ":" in l)   # export prints the classpath bare
cp = [e for e in lines[ci].split(":") if e]
secs, cur = [], []
for l in lines[ci + 1:]:
    if l.startswith("[success]"):
        secs.append(cur); cur = []
    elif l.startswith("[info] * "):
        cur.append(l[len("[info] * "):])
scalac, javac, sources = secs[:3]
# the project's own output is Zinc's to manage; dependency projects' class directories stay (compiled by `compile`)
own = projdir + "/target/"
cp = [e for e in cp if not e.startswith(own)]
w = lambda n, xs: open(f"{out}/{n}", "w").write("\n".join(xs) + "\n")
w("classpath.txt", cp); w("scalac.txt", scalac); w("javac.txt", javac); w("sources.txt", sources)
print(f"{len(sources)} sources, {len(cp)} classpath entries, {len(scalac)} scalac options, {len(javac)} javac options")
PY
