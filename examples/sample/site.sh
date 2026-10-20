#!/usr/bin/env bash
# Runs the sample's benchmarks under every profile this machine supports, its campaigns, then builds out/site.
# xctrace profiles need Xcode on Apple Silicon; kperf profiles need the asprof-kperf helper on /tmp/asprof-kperf.sock
# (sudo tools/build/async-profiler/build/bin/asprof-kperf -s /tmp/asprof-kperf.sock).
set -euo pipefail
cd "$(dirname "$0")"
p() { python3 -m perflab "$@"; }
# `perflab run --out <dir> ...`, unless <dir> already has results (so an interrupted build resumes)
run() { local out=$2; [ -s "$out/result.json" ] && { echo "have $out"; return; }; p run "$@" || echo "FAILED: $out (see $out/build.log)"; }
short="-wi 3 -i 5 -w 1 -r 1"
xctrace=false; DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}" xcrun -f xctrace >/dev/null 2>&1 && xctrace=true
kperf=""; [ -S /tmp/asprof-kperf.sock ] && kperf=/tmp/asprof-kperf.sock

# runs: one benchmark and setting per run, under each profile; kperf records cycles and the miss event the benchmark is about
declare -a benches=(
  "wordcount|cache-misses|-p size=100000 -p map=hash WordCountBenchmark"
  "wordcount-tree|cache-misses|-p size=100000 -p map=tree WordCountBenchmark"
  "memory-chase|cache-misses|-p layout=shuffled MemoryBenchmark"
  "memory-sequential|cache-misses|-p layout=sequential MemoryBenchmark"
  "branch-random|branch-misses|-p data=random BranchBenchmark"
  "branch-sorted|branch-misses|-p data=sorted BranchBenchmark"
)
for b in "${benches[@]}"; do
  IFS='|' read -r name miss args <<< "$b"
  run --out "out/runs/$name-async" --profile async:cpu,alloc -- $short $args
  if $xctrace; then
    run --out "out/runs/$name-xctrace-ipc" --profile xctrace:ipc -- $short $args
  fi
  if [ -n "$kperf" ]; then
    run --out "out/runs/$name-kperf" --profile "async:cycles+$miss" --kperf "$kperf" -- $short $args
  fi
done
# wall clock (for CPU-bound benchmarks it matches cpu, so one is enough)
run --out out/runs/wordcount-wall --profile async:wall -- $short -p size=100000 -p map=hash WordCountBenchmark
# several forks: the timeline shows each JVM from start to exit
run --out out/runs/wordcount-3-forks --profile none -- -f 3 $short -p size=100000 -p map=hash WordCountBenchmark
if $xctrace; then
  run --out out/runs/wordcount-2-forks-xctrace-ipc --profile xctrace:ipc -- -f 2 $short -p size=100000 -p map=hash WordCountBenchmark
fi
if [ -n "$kperf" ]; then
  run --out out/runs/memory-paired-kperf --profile "async:cycles+cache-misses" --kperf "$kperf" -- -p "variants=sequential=sequential|shuffled=shuffled" -wi 4 -i 6 -w 1 -r 1 MemoryBenchmark
  run --out out/runs/branch-paired-kperf --profile "async:cycles+branch-misses" --kperf "$kperf" -- -p "variants=sorted=sorted|random=random" -wi 4 -i 6 -w 1 -r 1 BranchBenchmark
fi
run --out out/runs/audit-normalize --profile audit:campaigns/normalize.audit -- -wi 1 -i 1 -w 1 -r 1 WordCountBenchmark

# campaigns
p ab run campaigns/gc.json
p ab run campaigns/maps.json
p ab run campaigns/maps-async.json
p profdiff --event cpu out/campaigns/maps-async/100000/hash/1 out/campaigns/maps-async/100000/tree/1 out/campaigns/maps-async/diff-hash-vs-tree-cpu
p profdiff --event alloc out/campaigns/maps-async/100000/hash/1 out/campaigns/maps-async/100000/tree/1 out/campaigns/maps-async/diff-hash-vs-tree-alloc
if $xctrace; then
  p ab run campaigns/maps-counters.json
  p ab run campaigns/memory-paired.json
  p ab run campaigns/branch-paired.json
fi
for c in campaigns/*.json; do
  d="out/campaigns/$(basename "$c" .json)"
  [ -d "$d" ] && p ab report "$c" > "$d/report.md"
done

p site out/site --title "sample results" --intro-file site-intro.html \
  --footer 'Built from <a href="https://github.com/retronym/jvm-perf-lab/tree/main/examples/sample">examples/sample</a> by <code>mise run site</code> on an Apple Silicon Mac.'
