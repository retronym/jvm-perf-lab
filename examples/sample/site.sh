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
hw="cycles+instructions+cache-misses+branch-misses"

# runs: one benchmark and setting per run, under each profile
declare -a benches=(
  "wordcount|-p size=100000 -p map=hash WordCountBenchmark"
  "wordcount-tree|-p size=100000 -p map=tree WordCountBenchmark"
  "memory-chase|-p layout=shuffled MemoryBenchmark"
  "memory-sequential|-p layout=sequential MemoryBenchmark"
  "branch-random|-p data=random BranchBenchmark"
  "branch-sorted|-p data=sorted BranchBenchmark"
)
for b in "${benches[@]}"; do
  name=${b%%|*}; args=${b#*|}
  run --out "out/runs/$name-async" --profile async:cpu,alloc -- $short $args
  run --out "out/runs/$name-wall" --profile async:wall -- $short $args
  if $xctrace; then
    for t in ipc frontend mem-l1d; do run --out "out/runs/$name-xctrace-$t" --profile "xctrace:$t" -- $short $args; done
    run --out "out/runs/$name-xctrace-cpu-counters" --profile "xctrace:CPU Counters" -- $short $args
  fi
  if [ -n "$kperf" ]; then
    run --out "out/runs/$name-kperf" --profile "async:$hw" --kperf "$kperf" -- $short $args
  fi
done
if [ -n "$kperf" ]; then
  run --out out/runs/memory-paired-kperf --profile "async:$hw" --kperf "$kperf" -- -p "variants=sequential=sequential|shuffled=shuffled" -wi 4 -i 6 -w 1 -r 1 MemoryBenchmark
  run --out out/runs/branch-paired-kperf --profile "async:$hw" --kperf "$kperf" -- -p "variants=sorted=sorted|random=random" -wi 4 -i 6 -w 1 -r 1 BranchBenchmark
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

p site out/site --title "jvm-perf-lab sample" --intro 'Results of <a href="https://github.com/retronym/jvm-perf-lab/tree/main/examples/sample">examples/sample</a>, built with <code>mise run site</code>: three JMH benchmarks (word counting in different maps, an array walk in order and as a pointer chase, a branch on sorted and random data) under async-profiler (cpu, alloc, wall) and a caller audit, and Apple PMU counters two ways: <code>-xctrace-</code> runs give counts per op on the benchmark thread (perflab&#39;s XctraceProfiler), <code>-kperf</code> runs give flame graphs per PMU event (async-profiler kperf events). <a href="https://github.com/retronym/jvm-perf-lab/blob/main/doc/pmu-counters.md">Which to use when</a>.'
