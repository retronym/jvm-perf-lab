"""A stand-in for a perflab command under `perflab server` (test_server.py): `cells <n> <secs> [rc]` says a line per
"cell" with control.checkpoint() between them, as `ab run` does; `stubborn <n> <secs>` never checks."""
import sys, time

from perflab import control, transcript

argv = sys.argv[1:]
if argv[:1] == ["--transcript"]:
    transcript.setup(argv[1])
    argv = argv[2:]
mode, n, secs = argv[0], int(argv[1]), float(argv[2])
for i in range(n):
    if mode == "cells":
        control.checkpoint()
    transcript.say(f"cell {i}")
    time.sleep(secs)
transcript.say("finished")
sys.exit(int(argv[3]) if len(argv) > 3 else 0)
