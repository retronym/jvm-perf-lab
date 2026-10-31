"""The source line of a frame `Class.method:line` in the build a campaign's variant ran: the checkout and commit its
build recorded (<campaign>/.build/<variant>/launch.json), read with `git show <commit>:<file>` (the working tree when
the build was dirty). The file is found by the JVM's convention, `<package>/<top-level class>.scala` (or `.java`), so
a class in a file of another name has no text.
"""
import json, os, subprocess


class Source:
    def __init__(self, checkout, commit=None):
        self.checkout, self.commit = checkout, commit
        self._files, self._text = None, {}

    def files(self):
        if self._files is None:
            try:
                args = ["ls-tree", "-r", "--name-only", self.commit] if self.commit else ["ls-files"]
                out = subprocess.run(["git", "-C", self.checkout, *args], capture_output=True, text=True, timeout=60).stdout
            except (OSError, subprocess.SubprocessError):
                out = ""
            self._files = [f for f in out.splitlines() if f.endswith((".scala", ".java"))]
        return self._files

    def file_of(self, cls):
        """The file of `cls` (`dotty/tools/dotc/core/Types$NamedType`), or None."""
        pkg, _, top = cls.rpartition("/")
        top = top.split("$")[0]
        if not top:
            return None
        files = self.files()
        for ext in (".scala", ".java"):
            want = f"/{pkg}/{top}{ext}" if pkg else f"/{top}{ext}"
            hits = [f for f in files if ("/" + f).endswith(want)]
            if hits:
                return min(hits, key=len)
        return None

    def lines(self, path):
        if path not in self._text:
            try:
                if self.commit:
                    r = subprocess.run(["git", "-C", self.checkout, "show", f"{self.commit}:{path}"], capture_output=True, text=True, timeout=60)
                    text = r.stdout if r.returncode == 0 else ""
                else:
                    text = open(os.path.join(self.checkout, path), errors="replace").read()
            except (OSError, subprocess.SubprocessError):
                text = ""
            self._text[path] = text.splitlines()
        return self._text[path]

    def line(self, method, n):
        """The text of line `n` of `method` (`Class.method`), stripped, or None."""
        cls = method.rpartition(".")[0]
        f = self.file_of(cls) if cls else None
        if not f:
            return None
        ls = self.lines(f)
        return ls[n - 1].strip() if 0 < n <= len(ls) else None


def of_variant(campaign_dir, variant):
    """The Source of a campaign variant's build, or None when it recorded none."""
    try:
        b = json.load(open(os.path.join(campaign_dir, ".build", variant, "launch.json"))).get("build") or {}
    except (OSError, ValueError):
        return None
    if not b.get("checkout") or not os.path.isdir(b["checkout"]):
        return None
    return Source(b["checkout"], None if b.get("dirty") or not b.get("commit") else b["commit"])
