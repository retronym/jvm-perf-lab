"""The control contract between `perflab server` and a job it runs: the runner calls `checkpoint()` where stopping is
free (between cells), and the server steers it through a file.

The server sets PERFLAB_CONTROL=<job dir>/control for the job. The file holds a word:
  pause    the runner writes <control>.ack containing `paused`, then waits, polling every 2 s, until the word changes
  cancel   the runner exits with status 130 (the server also sends SIGTERM after a grace period, for a runner between checkpoints)
  absent   carry on; a paused runner removes its ack and resumes
Without PERFLAB_CONTROL (a command run from a terminal), `checkpoint()` does nothing.
"""
import os, sys, time

from . import transcript

ENV = "PERFLAB_CONTROL"
POLL_ENV = "PERFLAB_CONTROL_POLL"  # seconds between reads while paused (tests shorten it)
PAUSE, CANCEL, PAUSED = "pause", "cancel", "paused"


def path():
    return os.environ.get(ENV) or None


def ack_path(control):
    return control + ".ack"


def read(control):
    """The word in the control file, or None."""
    try:
        with open(control) as f:
            return f.read().strip() or None
    except OSError:
        return None


def write(control, word):
    """The server's side: `word` (pause, cancel), or None to clear it."""
    if word is None:
        try:
            os.unlink(control)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(control), exist_ok=True)
    with open(control + ".tmp", "w") as f:
        f.write(word + "\n")
    os.replace(control + ".tmp", control)


def acked(control):
    """Whether the runner says it is paused."""
    return read(ack_path(control)) == PAUSED


def _ack(control, on):
    a = ack_path(control)
    if on:
        with open(a + ".tmp", "w") as f:
            f.write(PAUSED + "\n")
        os.replace(a + ".tmp", a)
    else:
        try:
            os.unlink(a)
        except FileNotFoundError:
            pass


CANCELLED = 130  # the exit status of a cancelled job, as for SIGINT


def _cancelled():
    transcript.say("[perflab] cancelled by the server")
    sys.exit(CANCELLED)


def checkpoint():
    """Called by a runner where it may stop: returns at once unless the server asked to pause (then blocks until it
    resumes) or to cancel (then exits)."""
    control = path()
    if not control:
        return
    word = read(control)
    if word == CANCEL:
        _cancelled()
    if word != PAUSE:
        return
    _ack(control, True)
    transcript.say("[perflab] paused by the server; waiting to resume")
    poll = float(os.environ.get(POLL_ENV) or 2)
    try:
        while True:
            time.sleep(poll)
            word = read(control)
            if word == CANCEL:
                _cancelled()
            if word != PAUSE:
                break
    finally:
        _ack(control, False)
    transcript.say("[perflab] resumed")
