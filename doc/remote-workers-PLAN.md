# Plan: remote workers

Design: [remote-workers.md](remote-workers.md).

## Steps

1. TODO `testbed.py`: this machine's testbed; `<cell>/testbed.json` from `ab run`; `"testbed"` in a spec; a campaign's statistics (index, api, branch view) count only its testbed's cells; `ab run` refuses another testbed's campaign.
2. TODO Queue: a job's testbed, the local worker takes its own only; claim, heartbeat, lease expiry (requeue), finish; pause and cancel over the heartbeat. Worker endpoints under `/api/workers/`, token on every request.
3. TODO Sources: the coordinator resolves checkouts and the harness at claim; bundles; the worker's mirrors and worktrees, harness worktree with the diff.
4. TODO Path and JDK mapping (`worker.toml`), checked before the job runs.
5. TODO Results: unit tarballs up, finished cells down at start; reindex.
6. TODO End to end with a second worker on this machine, then the M4 laptop.
7. TODO Docs: setting up a worker machine.

## Future work

- Show a remote job's running cell (its live timeline) on the coordinator's index.
- Listening on a LAN interface (TLS) instead of an SSH tunnel.
