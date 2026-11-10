#!/usr/bin/env bash
# Makes out/inputs/<project>-spec from out/inputs/<project> plus a generated source with @specialized classes
# (extra/Specialized.scala, written here): SpecializeTypes then makes a Duplicators typer, a third Analyzer class beside
# Global's and Erasure's, which turns the typechecker's invokeinterface calls through its self type megamorphic
# (scala/scala#11367). Pekko itself uses @specialized so little that the stock compile never sees it.
# Usage: make-specialized.sh <project> [classes]
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
proj=$1
n=${2:-40}
mkdir -p "$here/extra"
python3 -I - "$here/extra/Specialized.scala" "$n" <<'PY'
import sys
out, n = sys.argv[1], int(sys.argv[2])
L = ["package org.apache.pekko.stream.labspec", "", "import scala.annotation.tailrec", ""]
for i in range(n):
    # one specialized parameter (3 variants), and two (9 variants) for every third class
    two = i % 3 == 0
    tps = "@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B" if two else "@specialized(Int, Long, Double) A"
    L += [f"final class Spec{i}[{tps}](val xs: Array[A]" + (", val ys: Array[B]" if two else "") + ") {"]
    for m in range(12):
        L += [
            f"  def fold{m}(z: A)(f: (A, A) => A): A = {{ var acc = z; var i = 0; while (i < xs.length) {{ acc = f(acc, xs(i)); i += 1 }}; acc }}",
            f"  def count{m}(p: A => Boolean): Int = {{ var n = 0; var i = 0; while (i < xs.length) {{ if (p(xs(i))) n += 1; i += 1 }}; n }}",
            f"  def mapInto{m}(out: Array[A])(f: A => A): Unit = {{ var i = 0; while (i < xs.length) {{ out(i) = f(xs(i)); i += 1 }} }}",
            f"  def find{m}(p: A => Boolean): Option[A] = {{ @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }}",
        ]
        if two:
            L += [f"  def zip{m}(f: (A, B) => A): A = {{ var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) {{ acc = f(acc, ys(i)); i += 1 }}; acc }}"]
    L += ["}", ""]
open(out, "w").write("\n".join(L))
PY
src=$here/out/inputs/$proj
dst=$src-spec
rm -rf "$dst"; mkdir -p "$dst"
cp "$src"/{classpath,scalac,javac}.txt "$dst"/
{ cat "$src/sources.txt"; echo "$here/extra/Specialized.scala"; } > "$dst/sources.txt"
echo "$dst: $(wc -l < "$dst/sources.txt") sources"
