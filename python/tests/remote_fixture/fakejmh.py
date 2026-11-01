"""A stand-in for JMH (test_remote.py): its score is the built checkout's VERSION plus the number in the file
-Dfake.data= of its JVM arguments names."""
import json, sys

argv = sys.argv[1:]
version = next(a.split("=", 1)[1] for a in argv if a.startswith("-Dfake.version="))
args = open(next(a for a in argv if a.startswith("@"))[1:]).read().splitlines()
get = lambda flag: [args[i + 1] for i, a in enumerate(args) if a == flag]
jvm_args = " ".join(get("-jvmArgsAppend")).split()
data = next(a.split("=", 1)[1] for a in jvm_args if a.startswith("-Dfake.data="))
score = float(open(version).read()) + float(open(data).read())
open(get("-o")[0], "w").write("fake jmh\n")
json.dump([{"benchmark": "fake.B.run", "mode": "avgt", "jvm": sys.executable, "jvmArgs": jvm_args,
            "params": dict(p.split("=", 1) for p in get("-p")),
            "primaryMetric": {"score": score, "scoreError": 0.0, "scoreUnit": "ms/op", "rawData": [[score, score]]},
            "secondaryMetrics": {}}], open(get("-rff")[0], "w"))
