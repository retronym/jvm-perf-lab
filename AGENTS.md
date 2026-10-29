# Notes for coding agents

## Benchmark runs: share the index first

Before starting any campaign or run, give the user the URL of the live index, so they can watch results arrive:

```bash
perflab serve
```

It builds the index, starts a server for the checkout's campaigns and runs if none is running, and prints the URL (the same one every time for a checkout). `perflab run` and `perflab ab run` do the same before they start and log the URL as `index (updates ...): ...`; if you start one directly, pass that line on. Never start another HTTP server for results: everything is on this one.

While a `perflab server` runs (`perflab server status`), `perflab serve` prints the project's page on it instead (`http://127.0.0.1:8690/p/<project>/...`), and `perflab run` and `perflab ab run` become jobs on its queue: they print the job's URL on the queue page and the index URL, then follow the job (Ctrl-C detaches; the job runs on). Give the user both URLs. `--local` runs a command in the foreground instead.

The page keeps itself current: `perflab ab run` rebuilds the index around every cell, `perflab run` every 10 s while it runs, the page refetches its tables every 10 s, and its timeline follows the running fork every 5 s. Each campaign shows how many of its planned cells have results, each run its status (running, finished, failed, interrupted). There is nothing to regenerate when a campaign or run finishes, so don't tell the user you will.

## Reading results: the API

Read campaign results through perflab's API, not by parsing result.json or the index: `perflab mcp` (register it with `claude mcp add perflab -- perflab mcp`), or `perflab api --list` and `perflab api <function> --<param> <value>` for JSON on the command line. It works without a server; its actions (void a cell, rerun a campaign, job control) need `perflab server`. The perflab skill (`.claude/skills/perflab/SKILL.md`, section 7) says which function answers what.

## Commits

Say in the commit message that the change was made with an LLM. Do not add `Co-Authored-By` or "Generated with" trailers.
