#!/usr/bin/env bash
# Prepares a Zinc 2.x build (sbt/zinc develop, published with `sbt --ivy <ivy home> publishLocal`) for the benchmark under
# the label <label>: copies Zinc's jars into out/cp/zinc-<label>/ (a snapshot, so a later publish doesn't change what a
# campaign measures) and lists them in out/cp/zinc-<label>.txt, puts the published compiler-bridge_2.13 at
# out/bridge/bridge-<label>-<scala>.jar for each Scala version, and compiles the driver against those jars into
# out/cp/driver-<label>/ (the lab's own driver is compiled against Zinc 1.12.1's API, which 2.x changed).
# Usage: prepare-zinc-dev.sh <label> <ivy home> [zinc version] -- [scala versions]   (default: 2.0.0-M9-SNAPSHOT -- 2.13.18)
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
label=$1; ivy=$(cd "$2" && pwd); shift 2
zincv=2.0.0-M9-SNAPSHOT; scalas=()
if [ $# -gt 0 ] && [ "$1" != -- ]; then zincv=$1; shift; fi
if [ $# -gt 0 ] && [ "$1" = -- ]; then shift; scalas=("$@"); fi
[ ${#scalas[@]} -gt 0 ] || scalas=(2.13.18)
repo="ivy:file://$ivy/local/[organisation]/[module]/[revision]/[type]s/[artifact](-[classifier]).[ext]"
cp=$here/out/cp
snap=$cp/zinc-$label
rm -rf "$snap" "$cp/driver-$label"
mkdir -p "$snap" "$cp/driver-$label" "$here/out/bridge"
coursier fetch -r "$repo" "org.scala-sbt:zinc_3:$zincv" | while read -r j; do
  cp "$j" "$snap/"
  echo "$snap/$(basename "$j")"
done > "$cp/zinc-$label.txt"
bridge=$(coursier fetch -r "$repo" --intransitive "org.scala-sbt:compiler-bridge_2.13:$zincv")
for v in "${scalas[@]}"; do cp "$bridge" "$here/out/bridge/bridge-$label-$v.jar"; done
javac --release 21 -nowarn -cp "$(paste -sd: "$cp/zinc-$label.txt")" -d "$cp/driver-$label" \
  "$here/src/main/java/zincdirect/driver/Driver.java"
ls "$cp/driver-$label/zincdirect/driver" | wc -l
wc -l "$cp/zinc-$label.txt"
