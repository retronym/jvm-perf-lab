# Plan: remote workers

Design: [remote-workers.md](remote-workers.md). Setting up a worker: [worker-setup.md](worker-setup.md).

## Steps

1. DONE `testbed.py`: this machine's testbed; `<cell>/testbed.json` from `ab run`; `"testbed"` in a spec; a campaign's statistics (index, api, branch view) count only its testbed's cells ("foreign" otherwise); `ab run` refuses another testbed's campaign and sets a foreign cell aside before measuring it again.
2. DONE Queue: a job's testbed (from its spec, at submit), the local worker takes its own only; claim, heartbeat, lease expiry (requeue, or cancelled if a cancel was asked), finish; pause and cancel over the heartbeat. Worker endpoints under `/api/workers/`, the token on every request, any Host.
3. DONE Sources: the coordinator resolves checkouts (refusing dirty ones, at submit and at claim) and the harness (HEAD and diff) at claim (`remote.py`); bundles of what the remotes lack, or the whole history; the worker's mirrors, worktrees per commit, and the harness worktree with the diff (`worker.py`).
4. DONE Path and JDK mapping (`worker.toml` [paths] and [jdks], SDKMAN and /Library/Java by release file); inputs the worker lacks copied from the coordinator (only paths the spec names, under its home).
5. DONE Results: unit tarballs up (cells, `.void/`, top-level files), each replacing the coordinator's whole; finished cells down at start (and a cell the coordinator voided is measured again); reindex.
6. TODO End to end with a second worker on this machine (a real scala3 lab campaign), then the M4 laptop.
7. DONE Docs: [worker-setup.md](worker-setup.md).

Tests: test_remote.py (the queue's leases, mapping, and a worker process running a campaign of two builds, one an unpushed commit, with the harness's uncommitted change).

## Future work

- A remote job's running cell (its live timeline) on the coordinator's index; today it shows when it is uploaded.
- Branch campaigns (and their profiles) on a worker: the range resolved on the coordinator, its commits shipped as for builds.
- Listening on a LAN interface (TLS) instead of an SSH tunnel.
- Worker-side storage cleanup (its snapshots and worktrees).
