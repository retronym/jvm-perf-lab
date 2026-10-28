"""Serves the index of campaigns and runs over HTTP on 127.0.0.1 and prints its URL; the page updates itself as results
arrive.

  perflab serve [--port <port>] [--stop]

Builds the index, then starts a server in the background for the directory holding both <campaigns> and <runs>, unless
one this command started is still serving it, so it can be run any number of times and always prints the same URL. The
port is [index] port in perflab.toml, else one derived from the project's path (8700-8799), so each checkout keeps its
own address. `perflab run` and `perflab ab run` do this before they start. While `perflab server` runs, it serves the
project instead: the URL printed is the project's index there (/p/<project>/...), and no server is started here.
"""
import argparse, hashlib, json, os, signal, socket, subprocess, sys, time

from . import config

STATE = ".serve.json"
SERVER = "perflab.httpd"  # the server module, recorded in the state so a server of another kind is replaced


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
        # as http.server binds: a port whose last server just exited still has connections in TIME_WAIT
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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


def doc_root(campaigns, runs):
    """What the server serves: the closest directory holding both the campaigns and the runs, which the index links."""
    return os.path.commonpath([campaigns, runs]) if runs else campaigns


def ensure(root=None, port=None):
    """The index's URL, starting a server if none is serving it. `root` is the campaigns directory (default: the
    project's); the index and the server's state live there."""
    root = os.path.abspath(root or config.get().campaigns)
    runs = config.get().runs
    serve = doc_root(root, os.path.abspath(runs) if runs else None)
    os.makedirs(root, exist_ok=True)
    from . import index
    index.build(root)
    url = on_server(root)
    if url:
        return url
    rel = os.path.relpath(root, serve)
    url = lambda p: f"http://127.0.0.1:{p}/" + ("index.html" if rel == "." else f"{rel}/index.html")
    st = _state(root)
    if st and _alive(st.get("pid")) and _listening(st["port"]) and (port is None or port == st["port"]):
        if st.get("root") == serve and st.get("server") == SERVER:
            return url(st["port"])
        # an older server (for the campaigns alone, or plain http.server without charsets): replaced on its port, so
        # the URL stays the same
        os.kill(st["pid"], signal.SIGTERM)
        for _ in range(50):
            if _free(st["port"]):
                break
            time.sleep(0.1)
        port = port or st["port"]
    want = port or default_port(root)
    for p in [want] + ([] if port else list(range(want + 1, want + 50))):
        if _free(p):
            break
    else:
        sys.exit(f"perflab serve: port {want} is in use")
    # the server imports this package, wherever it was imported from (an install, or PYTHONPATH=python/src)
    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([pkg, *filter(None, [os.environ.get("PYTHONPATH")])])}
    proc = subprocess.Popen([sys.executable, "-m", SERVER, str(p), serve], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    json.dump({"pid": proc.pid, "port": p, "root": serve, "server": SERVER}, open(os.path.join(root, STATE), "w"))
    for _ in range(50):
        if _listening(p):
            break
        time.sleep(0.1)
    return url(p)


def on_server(root):
    """The project's index on the running `perflab server` (/p/<project>/...), registering the project, if a server
    runs and `root` is the project's campaigns; else None."""
    from . import server
    url = server.running()
    if not url or os.path.realpath(root) != os.path.realpath(config.get().campaigns):
        return None
    try:
        p = server.api("POST", "/api/projects", {"root": config.get().root}, url)
    except Exception:  # an older server, or one that went away: serve it here
        return None
    return url.rstrip("/") + p["index"]


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
