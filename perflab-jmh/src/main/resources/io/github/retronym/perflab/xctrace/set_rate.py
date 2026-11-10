"""Make a template that samples at another rate.

  python3 set_rate.py ipc.template.xml ipc-coarse.template.xml 10000

The rate is the timer interval in microseconds (`samplingRate`; bundled templates use 1000, 1 kHz per core). A long,
many-threaded run (a build compiling on every core for minutes) loses events at 1 kHz and exports a trace of a
gigabyte; a longer interval keeps the totals and shrinks the export in proportion.
"""
import plistlib
import sys

src, dst, micros = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(src, "rb") as f:
    outer = plistlib.load(f)
objs = outer["$objects"]
n = 0
for o in objs:
    if isinstance(o, dict) and "NS.keys" in o and "NS.objects" in o:
        keys = [objs[k["CF$UID"]] if isinstance(k, dict) else objs[k] for k in o["NS.keys"]]
        if "samplingRate" in keys:
            o["NS.objects"][keys.index("samplingRate")] = micros
            n += 1
assert n == 1, f"found {n} samplingRate settings"
with open(dst, "wb") as f:
    plistlib.dump(outer, f, fmt=plistlib.FMT_XML)
print("wrote", dst, "at", micros, "us")
