"""A stand-in for a lab's [build] launch (test_remote.py): writes <out>/launch.json whose "java" runs fakejmh.py, which
scores the checkout's VERSION."""
import json, os, subprocess, sys

out, co = sys.argv[1], os.environ["FAKE_CHECKOUT"]
here = os.path.dirname(os.path.abspath(__file__))
commit = subprocess.run(["git", "-C", co, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump({"mainClass": "Main", "java": sys.executable, "classpath": [],
           "javaOptions": [os.path.join(here, "fakejmh.py"), f"-Dfake.version={co}/VERSION"], "roots": [],
           "build": {"checkout": co, "commit": commit, "dirty": False}}, open(os.path.join(out, "launch.json"), "w"))
print("built", commit)
