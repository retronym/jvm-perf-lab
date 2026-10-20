"""The index's HTTP server: http.server's, with `charset=utf-8` on text types, so that reports (`report.md`, logs,
TSV) with non-ASCII characters (Δ, ±, µ) read correctly in a browser, as GitHub Pages serves them.

  python -m perflab.httpd <port> <directory>
"""
import functools, http.server, sys

TEXT = ("text/", "application/json", "application/javascript")


class Handler(http.server.SimpleHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return f"{t}; charset=utf-8" if t.startswith(TEXT) and "charset" not in t else t

    def log_message(self, *args):
        pass


def main(argv):
    port, directory = int(argv[0]), argv[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=directory))
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
