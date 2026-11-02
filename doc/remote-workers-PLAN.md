# Plan: remote workers

Design: [remote-workers.md](remote-workers.md). Setting up a worker: [worker-setup.md](worker-setup.md).

## Steps

1. DONE `testbed.py`: this machine's testbed; `<cell>/testbed.json` from `ab run`; `"testbed"` in a spec; a campaign's statistics (index, api, branch view) count only its testbed's cells ("foreign" otherwise); `ab run` refuses another testbed's campaign and sets a foreign cell aside before measuring it again.
2. DONE Queue: a job's testbed (from its spec, at submit), the local worker takes its own only; claim, heartbeat, lease expiry (requeue, or cancelled if a cancel was asked), finish; pause and cancel over the heartbeat. Worker endpoints under `/api/workers/`, the token on every request, any Host.
3. DONE Sources: the coordinator resolves checkouts (refusing dirty ones, at submit and at claim) and the harness (HEAD and diff) at claim (`remote.py`); bundles of what the remotes lack, or the whole history; the worker's mirrors, worktrees per commit, and the harness worktree with the diff (`worker.py`).
4. DONE Path and JDK mapping (`worker.toml` [paths] and [jdks], SDKMAN and /Library/Java by release file); inputs the worker lacks copied from the coordinator (only paths the spec names, under its home).
5. DONE Results: unit tarballs up (cells, `.void/`, top-level files), each replacing the coordinator's whole; finished cells down at start (and a cell the coordinator voided is measured again); reindex.
6. DONE End to end on the M4 laptop (zMacBook-Air, testbed `m4`, over `ssh -R 127.0.0.1:8691:127.0.0.1:8690`): `m4-smoke`, the scala3 lab's base and tip of batch-84 (unpushed commits as bundles, the dotc corpus copied, GraalVM 25), both cells on the coordinator. It found two things now fixed: the builds' JDK must be the coordinator's (JAVA_HOME mapped), and a worktree built with another JDK loses its build outputs first.
7. DONE Docs: [worker-setup.md](worker-setup.md), README's Remote workers section; `mise run kperf:install` (the kperf helper as a launchd daemon).
10. DONE Variance baseline of testbed m4 (`m4-aa-graal25`, stopped after round 2): fork-to-fork sd 0.38% dotc, 0.45% scalaz under the hill-climbing harness on GraalVM 25 (the M5's harness-aa-graal25: 3.5%, 3.8%).
9. DONE The tunnel (`mise run tunnel:install`) and the worker (`mise run worker:install`) as launchd agents.
11. DONE Workers on the queue page: a card with this machine and each remote worker (testbed, hardware, online or offline, its job and running cell), every job saying where it runs; the table kept across restarts (`workers.json`).
12. DONE A remote job's live view (`mirror.py`): the heartbeat carries what changed of the worker's `running.json`, `loadgate.json`, `build.json` and the running cell's timeline files, written into `<campaigns>/.live/<worker>/`; the index and the queue page draw its fork timeline, load gate and build from there, saying which machine.
8. DONE kperf on the M4: `m4-kperf-smoke` (async cycles and instructions through the helper daemon) under a 1.5-core gate, once the load gate stopped counting `asprof-kperf` as other load.

Tests: test_remote.py (the queue's leases, mapping, and a worker process running a campaign of two builds, one an unpushed commit, with the harness's uncommitted change); test_mirror.py (the live mirror's deltas, a replaced file, a coordinator that lost the mirror, the budget, paths).

## Future work

- A dedicated user account on a worker machine for the worker (and its launchd agents), logged in with nothing else: no login items, iCloud, Siri, widgets or sync clients of the everyday account, which the load gate otherwise voids cells for (the M4's A/A lost three attempts to Siri, contactsd and calendar widgets).

- Raw xctrace traces (`*.trace`, `*.counters.xml`, 50–80 MB a fork) are uploaded with their cell, and the worker sits paused at the cell boundary meanwhile; the coordinator may not need them.
- Branch campaigns (and their profiles) on a worker: the range resolved on the coordinator, its commits shipped as for builds.
- Listening on a LAN interface (TLS) instead of an SSH tunnel.
- Worker-side storage cleanup (its snapshots and worktrees).
- A launch-mode snapshot is reused by variant whatever JDK built it (here and on the coordinator); key it by the build's JDK too.
