"""Strict red-team probes, outside `python -m auditgym check`:  python -m auditgym.redteam

Same hostile policies as tests/test_redteam.py (examples/hostile/policies.py; run_hostile lives here), with larger
sizes and tighter timing margins that would make a shared CI runner flaky. Run it from the
repository root. Exit code 0 only if every probe holds. It also measures what a child
process of the same OS user can read about its parent (reported, never claimed as blocked).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from unittest import mock

from . import protocol
from .env import AuditEnv
from .generator import generate_episode

MB = 1024 * 1024
_CFG = {"size": "small", "errors": {"duplicate_invoice": 1, "wrong_fx_rate": 1}}
_EPISODE: list = []


def default_episode():
    if not _EPISODE:
        _EPISODE.append(generate_episode(101, _CFG).episode)
    return _EPISODE[0]


def write_policy(tmp: str, base: str, **attrs) -> str:
    """A module `hostile_policy` in tmp with class P(base) carrying the given class attributes."""
    body = f"from examples.hostile.policies import {base}\n\n\nclass P({base}):\n"
    body += "".join(f"    {k} = {v!r}\n" for k, v in attrs.items()) or "    pass\n"
    Path(tmp, "hostile_policy.py").write_text(body, encoding="utf-8")
    return "hostile_policy:P"


class _TailSpy(protocol.AgentProcess):
    tails: list = []

    def close(self):
        super().close()
        type(self).tails.append(self.stderr_tail())


def run_hostile(base: str, time_limit_s: float = 20.0, ep=None, mode: str = "eval", trace: bool = False, **attrs):
    """Run hostile policy `base` (examples/hostile/policies.py) with class attributes `attrs`.
    Returns (result, records, peak_bytes, stderr_tail)."""
    records = []
    _TailSpy.tails = []
    with tempfile.TemporaryDirectory() as tmp:
        name = write_policy(tmp, base, **attrs)
        env = AuditEnv(mode=mode, time_limit_s=time_limit_s)
        ep = ep or default_episode()
        peak = 0
        if trace:
            tracemalloc.start()
            tracemalloc.reset_peak()
        try:
            with mock.patch.object(protocol, "AgentProcess", _TailSpy):
                res = protocol.run_episode_isolated(env, {"config": {"episode": ep}}, name, 0,
                                                    on_step=records.append, policy_path=tmp)
        finally:
            if trace:
                peak = tracemalloc.get_traced_memory()[1]
                tracemalloc.stop()
    return res, records, peak, (_TailSpy.tails[0] if _TailSpy.tails else "")


def _probes():
    rows = []

    def probe(name, fn):
        t0 = time.monotonic()
        try:
            ok, detail = fn()
        except Exception as exc:  # a probe that crashes is a failed probe
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        rows.append((name, ok, time.monotonic() - t0, detail))

    def flood(base, mb, limit_mb=8, **kw):
        def run():
            res, rec, peak, tail = run_hostile(base, trace=True, MB=mb, **kw)
            return peak < limit_mb * MB and res["agent_error"] is None, f"host peak {peak / MB:.2f} MB, status {res['grade']['status']}"
        return run

    probe("256 MB without a newline on stdout", flood("NoNewlineFlood", 256))
    probe("256 MB on stderr", flood("StderrFlood", 256))

    def line_flood():
        res, rec, peak, _ = run_hostile("LineFlood", time_limit_s=5.0, trace=True, LINES=2_000_000)
        return peak < 8 * MB and res["agent_error"] is None, f"host peak {peak / MB:.2f} MB, status {res['grade']['status']}"

    probe("2 000 000 short lines", line_flood)

    def stop_reading():
        t0 = time.monotonic()
        res, _, _, _ = run_hostile("SlowReader", time_limit_s=2.0, SLEEP=120.0)
        took = time.monotonic() - t0
        return res["grade"]["status"] == "time_limit" and took < 4.0, f"time_limit after {took:.2f} s (limit 2.0 s)"

    probe("agent that stops reading stdin", stop_reading)

    def bad_lines():
        res, _, peak, _ = run_hostile("BadLinesNoRead", time_limit_s=3.0, trace=True)
        limit = (protocol.QUEUE_LINES + 4) * protocol.MAX_LINE
        return (peak < limit and res["agent_error"] is None,
                f"host peak {peak / MB:.1f} MB (limit {limit / MB:.0f} MB), status {res['grade']['status']}")

    probe("300 lines of 2 MB invalid UTF-8, agent never reads", bad_lines)

    def grandchild():
        with tempfile.TemporaryDirectory() as d:
            beat = os.path.join(d, "hb.txt")
            run_hostile("Grandchild", HEARTBEAT=beat)
            a = Path(beat).read_text()
            time.sleep(1.0)
            b = Path(beat).read_text()
            time.sleep(1.0)
            c = Path(beat).read_text()
            return a != "" and b == c, "heartbeat frozen after close()"

    probe("grandchild killed with the agent", grandchild)
    return rows


PARENT_PROBE = r"""
import os, subprocess, sys
ppid = os.getppid()
out = {}
if os.name == "nt":
    cmd = ["powershell", "-NoProfile", "-Command",
           "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % ppid]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    out["command_line"] = r.stdout.strip()[:200]
else:
    try:
        out["command_line"] = open("/proc/%d/cmdline" % ppid, "rb").read().replace(b"\0", b" ").decode()[:200]
    except OSError as exc:
        out["command_line"] = ""
    try:
        out["environ_bytes"] = len(open("/proc/%d/environ" % ppid, "rb").read())
    except OSError:
        out["environ_bytes"] = 0
print(out)
"""


def parent_visibility() -> str:
    marker = "auditgym-redteam-marker"
    p = subprocess.run([sys.executable, "-c", PARENT_PROBE, marker], capture_output=True, text=True, timeout=60)
    return p.stdout.strip() or p.stderr.strip()[-300:]


def main(argv=None) -> int:
    rows = _probes()
    width = max(len(r[0]) for r in rows)
    ok = True
    for name, passed, secs, detail in rows:
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name.ljust(width)}  {secs:5.1f} s  {detail}")
    print("parent process visibility from a child of the same user (limitation, not blocked):")
    print("  " + parent_visibility())
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
