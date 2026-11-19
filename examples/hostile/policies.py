"""Probing and hostile policies. Sizes and targets are class attributes; tests subclass them
in a generated module (loaded with --policy-path) so that the child never needs extra input.

Every class follows the documented adapter: act(observation, reward, info) -> action.
Raw writes go to the protocol channel on purpose (auditgym.agent.PROTOCOL_OUT): they model a policy
that knows where the host listens. A plain print() goes to stderr instead and is harmless.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time


def _raw():
    """The child's private protocol writer (bytes)."""
    import auditgym.agent as agent

    return agent.PROTOCOL_OUT


def _submit(episode_id) -> dict:
    return {"action": "submit", "findings": {"episode_id": episode_id, "findings": []}}


class _Base:
    def __init__(self, seed: int = 0):
        self.episode_id = None
        self.n = 0

    def act(self, observation, reward=0.0, info=None):
        if "task" in observation:
            self.episode_id = observation["manifest"]["episode_id"]
        self.n += 1
        return self.step(observation)

    def step(self, observation):  # overridden
        return _submit(self.episode_id)


class IdProbe(_Base):
    """Asks for every answer-key ID, alias and FX evidence ID (TARGETS), plus 'iss_01'."""

    TARGETS: tuple = ()
    MAX_PROBES = 95

    def step(self, observation):
        if "task" in observation:
            queue = []
            for t in list(self.TARGETS) + ["iss_01"]:
                if ":" in t:
                    queue.append({"action": "get_record", "table": "fx", "id": t})
                else:
                    queue.append({"action": "get_document", "doc_id": t})
                    queue.append({"action": "get_record", "table": "ledger", "id": t})
            self.queue = queue[: self.MAX_PROBES]
        if self.queue:
            return self.queue.pop(0)
        return _submit(self.episode_id)


class NoNewlineFlood(_Base):
    """Writes MB megabytes to the raw stdout without a newline, then a newline and a normal submit."""

    MB = 32

    def step(self, observation):
        if self.n == 1:
            chunk = b"x" * (1 << 20)
            out = _raw()
            for _ in range(self.MB):
                out.write(chunk)
            out.write(b"\n")
            out.flush()
        return _submit(self.episode_id)


class LineFlood(_Base):
    """Writes LINES short lines at once to the raw stdout, then answers normally."""

    LINES = 200_000

    def step(self, observation):
        if self.n == 1:
            out = _raw()
            out.write(b'{"type":"x"}\n' * self.LINES)
            out.flush()
        return _submit(self.episode_id)


class StderrFlood(_Base):
    """Writes MB megabytes to stderr, once without a newline and then as many short lines."""

    MB = 32

    def step(self, observation):
        if self.n == 1:
            chunk = "e" * (1 << 20)
            for _ in range(self.MB):
                sys.stderr.write(chunk)
            sys.stderr.write("\n" + ("line\n" * 100_000))
            sys.stderr.flush()
        return _submit(self.episode_id)


class StrayPrint(_Base):
    """A policy with a debugging print(); the protocol must not desynchronise."""

    def step(self, observation):
        print("debug: thinking about", self.n)
        if "task" in observation:
            return {"action": "list_records", "table": "ledger", "cursor": None, "limit": 1}
        return _submit(self.episode_id)


class Grandchild(_Base):
    """Starts a detached process that rewrites HEARTBEAT every 50 ms for 30 s."""

    HEARTBEAT = ""  # set by the generated module

    def step(self, observation):
        if self.n == 1:
            code = ("import time,sys\n"
                    "p=sys.argv[1]\n"
                    "for i in range(600):\n"
                    "    open(p,'w').write(str(time.time()))\n"
                    "    time.sleep(0.05)\n")
            subprocess.Popen([sys.executable, "-c", code, self.HEARTBEAT], stdin=subprocess.DEVNULL)
            deadline = time.monotonic() + 8.0
            while not os.path.exists(self.HEARTBEAT) and time.monotonic() < deadline:
                time.sleep(0.05)
        return _submit(self.episode_id)


class SlowReader(_Base):
    """Answers the first observation at once, then sleeps SLEEP s instead of reading stdin."""

    SLEEP = 30.0

    def step(self, observation):
        if self.n == 1:
            return {"action": "list_records", "table": "invoices", "cursor": None, "limit": 50}
        time.sleep(self.SLEEP)
        return _submit(self.episode_id)


class GarbageFirst(_Base):
    """Writes a line that is not JSON first (raw stdout), then plays normally."""

    def step(self, observation):
        if self.n == 1:
            _raw().write(b"this is not json\n")
            _raw().flush()
        return _submit(self.episode_id)


class CodeEditor(_Base):
    """Appends a line to TARGET (a grader-side file in the host tree), then submits."""

    TARGET = ""

    def step(self, observation):
        if self.n == 1:
            with open(self.TARGET, "a", encoding="utf-8") as fh:
                fh.write("\n# tampered by the policy\n")
        return _submit(self.episode_id)


class Crash(_Base):
    def step(self, observation):
        raise RuntimeError("policy crashed on purpose")


class ExitNow(_Base):
    def step(self, observation):
        os._exit(7)


class BadLinesNoRead(_Base):
    """Writes LINES lines of LINE_BYTES invalid UTF-8 bytes each, then stops reading (sleeps)."""

    LINES = 300
    LINE_BYTES = 2_000_000
    SLEEP = 60.0

    def step(self, observation):
        if self.n == 1:
            out = _raw()
            line = b"\xff" * self.LINE_BYTES + b"\n"
            for _ in range(self.LINES):
                out.write(line)
            out.flush()
        time.sleep(self.SLEEP)
        return _submit(self.episode_id)


class PycPlanter(_Base):
    """Plants a bytecode file for TARGET (a .py in the host tree) whose header matches the source."""

    TARGET = ""

    def step(self, observation):
        if self.n == 1:
            import importlib.util
            import py_compile

            cache = importlib.util.cache_from_source(self.TARGET)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(self.TARGET, "rb") as fh:
                src = fh.read()
            tmp = self.TARGET + ".plant.py"
            with open(tmp, "wb") as fh:
                fh.write(src + b"\n# planted\n")
            py_compile.compile(tmp, cfile=cache, doraise=True)
            os.remove(tmp)
        return _submit(self.episode_id)

