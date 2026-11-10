#!/usr/bin/env bash
# Resolves the jars the benchmark loads, one classpath file each under out/cp: zinc-<v>.txt (Zinc and its dependencies),
# bridge-src-<v>.txt (the compiler bridge's sources, which the benchmark compiles per Scala version), scala-<v>.txt.
# Usage: prepare-classpaths.sh [zinc versions] -- [scala versions]   (default: 1.12.1 1.13.0 -- 2.13.18 2.13.19-bin-6101d22-SNAPSHOT)
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
cp=$here/out/cp
mkdir -p "$cp"
zincs=(); scalas=(); cur=zincs
for a in "$@"; do if [ "$a" = -- ]; then cur=scalas; else eval "$cur+=(\"$a\")"; fi; done
[ ${#zincs[@]} -gt 0 ] || zincs=(1.12.1 1.13.0)
[ ${#scalas[@]} -gt 0 ] || scalas=(2.13.18 2.13.19-bin-6101d22-SNAPSHOT)
for v in "${zincs[@]}"; do
  coursier fetch "org.scala-sbt:zinc_2.12:$v" > "$cp/zinc-$v.txt"
  coursier fetch --sources --default=false "org.scala-sbt:compiler-bridge_2.13:$v" > "$cp/bridge-src-$v.txt"
done
for v in "${scalas[@]}"; do
  coursier fetch -r ivy2Local "org.scala-lang:scala-compiler:$v" > "$cp/scala-$v.txt"
done
wc -l "$cp"/*.txt
