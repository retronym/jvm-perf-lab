"""A transcript for a caller waiting on perflab: `perflab --transcript <file> <command> ...` appends perflab's progress
lines (cells, loadgate waits) and the build's output as it comes (the build tool compiling, JMH's iterations) to
<file>, so the caller can follow it (`tail -f`) through the steps before any result exists. Commands that run perflab
again (`trees` runs `ab run` in each checkout) pass it on through the environment.
"""
import os, re, time

ENV = "PERFLAB_TRANSCRIPT"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def setup(path):
    path = os.path.abspath(path)
    os.environ[ENV] = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write(f"--- perflab {time.strftime('%Y-%m-%d %H:%M:%S')} (pid {os.getpid()}, {os.getcwd()})")


def write(line):
    path = os.environ.get(ENV)
    if path:
        with open(path, "a") as f:
            f.write(line + "\n")


def say(msg):
    """Prints a progress line and appends it to the transcript."""
    print(msg, flush=True)
    write(msg)


def build_line(line):
    """A line of the build's output, without terminal control sequences, indented under perflab's own lines."""
    line = ANSI.sub("", line).rstrip("\r\n")
    if line.strip():
        write("  | " + line)


def follow(path, done, prefix="  > "):
    """Appends the lines of `path` (JMH's -o log, which JMH writes instead of its stdout) as they are written, until
    the event `done` is set; a thread's target. Nothing without a transcript."""
    if not os.environ.get(ENV):
        return
    f = None
    while True:
        finished = done.is_set()  # read what is there once more after the writer has exited
        if f is None and os.path.exists(path):
            f = open(path, errors="replace")
        for line in (f or ()):
            line = line.rstrip("\r\n")
            if line.strip():
                write(prefix + line)
        if finished:
            break
        done.wait(1)
    if f:
        f.close()
