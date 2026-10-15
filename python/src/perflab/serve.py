"""Serves the campaigns' index over HTTP on 127.0.0.1 and prints its URL; the page updates itself as results arrive.

  perflab serve [--port <port>] [--stop]

Builds the index, then starts a server for <campaigns> in the background, unless one this command started is still
running there, so it can be run any number of times and always prints the same URL. The port is [index] port in
perflab.toml, else one derived from the project's path (8700-8799), so each checkout keeps its own address.
`perflab ab run` does this before its first cell.
"""
import argparse, hashlib, json, os, signal, socket, subprocess, sys

from . import config

STATE = ".serve.json"


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def _listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _free(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _state(root):
    try:
        return json.load(open(os.path.join(root, STATE)))
    except (OSError, ValueError):
        return None


def default_port(root):
    configured = config.get().get("index", "port")
    if configured:
        return int(configured)
    return 8700 + int(hashlib.sha1(os.path.realpath(root).encode()).hexdigest(), 16) % 100


def ensure(root=None, port=None):
    """The index's URL, starting a server for `root` (default: the campaigns directory) if none is running."""
    root = os.path.abspath(root or config.get().campaigns)
    os.makedirs(root, exist_ok=True)
    from . import index
    index.build(root)
    st = _state(root)
    if st and _alive(st.get("pid")) and _listening(st["port"]) and (port is None or port == st["port"]):
        return f"http://127.0.0.1:{st['port']}/index.html"
    want = port or default_port(root)
    for p in [want] + ([] if port else list(range(want + 1, want + 50))):
        if _free(p):
            break
    else:
        sys.exit(f"perflab serve: port {want} is in use")
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "--directory", root],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    json.dump({"pid": proc.pid, "port": p}, open(os.path.join(root, STATE), "w"))
    for _ in range(50):
        if _listening(p):
            break
        import time
        time.sleep(0.1)
    return f"http://127.0.0.1:{p}/index.html"


def stop(root=None):
    root = os.path.abspath(root or config.get().campaigns)
    st = _state(root)
    if st and _alive(st.get("pid")):
        os.kill(st["pid"], signal.SIGTERM)
    if os.path.exists(os.path.join(root, STATE)):
        os.unlink(os.path.join(root, STATE))


def main(argv):
    ap = argparse.ArgumentParser(prog="perflab serve", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int)
    ap.add_argument("--stop", action="store_true")
    x = ap.parse_args(argv)
    if x.stop:
        stop()
        return 0
    print(ensure(port=x.port))
    return 0
