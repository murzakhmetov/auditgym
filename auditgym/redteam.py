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
            protocol._label_low(d)  # Windows: the Low-integrity child writes the heartbeat here (no-op elsewhere)
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
    # PowerShell writes piped output in the console's OEM code page; the ANSI default garbles non-ASCII paths
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="oem", errors="replace", timeout=30)
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
    env = dict(os.environ, PYTHONIOENCODING="utf-8")  # the child writes stdout and stderr as UTF-8 on any console code page
    p = subprocess.run([sys.executable, "-c", PARENT_PROBE, marker], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=60)
    out, err = p.stdout.strip(), p.stderr.strip()
    return out or err[-300:]


# A policy that looks for a host variable in its parent's environment: on Windows by reading the parent's
# process memory (PEB -> RTL_USER_PROCESS_PARAMETERS.Environment, 64-bit offsets), elsewhere through
# /proc/<ppid>/environ. It reports booleans only, never the value.
PEEK_POLICY = r'''
import os
import sys

NAME = "AUDITGYM_REDTEAM_SECRET"


def _windows_parent_env(pid):
    import ctypes
    from ctypes import wintypes
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.OpenProcess(0x0400 | 0x0010, False, pid)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    if not handle:
        WHY.append("OpenProcess(PROCESS_VM_READ) error %d" % ctypes.get_last_error())  # 5 = access denied
        return None
    try:
        class PBI(ctypes.Structure):
            _fields_ = [("ExitStatus", ctypes.c_long), ("PebBaseAddress", ctypes.c_void_p),
                        ("AffinityMask", ctypes.c_void_p), ("BasePriority", ctypes.c_long),
                        ("UniqueProcessId", ctypes.c_void_p), ("InheritedFrom", ctypes.c_void_p)]
        pbi = PBI()
        if ntdll.NtQueryInformationProcess(handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
            return None

        def read(addr, n):
            buf = ctypes.create_string_buffer(n)
            got = ctypes.c_size_t()
            ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
            return buf.raw[: got.value] if ok else b""

        params = int.from_bytes(read(pbi.PebBaseAddress + 0x20, 8), "little")
        env_addr = int.from_bytes(read(params + 0x80, 8), "little")
        env_size = int.from_bytes(read(params + 0x3F0, 8), "little")
        return read(env_addr, min(env_size or 32768, 1 << 20)).decode("utf-16-le", "replace")
    finally:
        k32.CloseHandle(handle)


def _ppid():
    try:
        return os.getppid()
    except OSError:  # Windows at Low integrity: no process snapshot (WinError 18); ask the process itself instead
        import ctypes
        ntdll = ctypes.WinDLL("ntdll")
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        ntdll.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong,
                                                    ctypes.c_void_p]
        buf = (ctypes.c_size_t * 6)()
        if ntdll.NtQueryInformationProcess(k32.GetCurrentProcess(), 0, buf, ctypes.sizeof(buf), None) != 0:
            raise
        return buf[5]  # InheritedFromUniqueProcessId


def parent_environment():
    try:
        ppid = _ppid()
    except Exception as exc:
        WHY.append("parent pid unknown: %s" % exc)
        return None
    PPID.append(ppid)
    if os.name == "nt":
        try:
            return _windows_parent_env(ppid)
        except Exception as exc:
            WHY.append("%s: %s" % (type(exc).__name__, exc))
            return None
    try:
        with open("/proc/%d/environ" % ppid, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except FileNotFoundError:
        NO_PROC.append(True)  # no /proc here (macOS): nothing was measured
        return None
    except OSError:
        return None


NO_PROC = []
WHY = []  # why the parent was not readable (Windows)
PPID = []  # the parent pid this probe tried to open


class Probe:
    def __init__(self, seed=0):
        self.episode_id = None
        self.probed = False

    def act(self, observation, reward=0.0, info=None):
        if isinstance(observation, dict) and isinstance(observation.get("manifest"), dict):
            self.episode_id = observation["manifest"].get("episode_id")
        if self.probed:  # a closed run needs an answer: the second action ends the episode
            return {"action": "submit", "findings": {"episode_id": self.episode_id, "findings": []}}
        self.probed = True
        text = parent_environment()
        agent = sys.modules.get("auditgym.agent")
        return {"action": "probe", "readable": text is not None, "no_proc": bool(NO_PROC),
                "why": "; ".join(WHY), "ppid": PPID[0] if PPID else None, "integrity": str(getattr(agent, "INTEGRITY_STATUS", "unknown")),
                "found_in_parent": bool(text) and (NAME + "=") in text, "in_own_environment": NAME in os.environ}
'''

# The host side: a separate process whose environment holds the variable from its start (as a shell would set
# AUDITGYM_SECRET before `--secret-env`), which starts the policy through the real harness (protocol.AgentProcess).
PEEK_HOST = r"""
import json, sys
from auditgym import protocol
if len(sys.argv) > 2 and sys.argv[2] == "plain":  # control: the host stays dumpable
    protocol.harden_host = lambda: False
    protocol.LOWER_INTEGRITY = False  # Windows: the child stays at the host's integrity level
ap =protocol.AgentProcess("peekparent:Probe", 0, policy_path=sys.argv[1])
try:
    ap.send({"type": "observation", "observation": {}, "reward": 0.0, "terminated": False, "truncated": False,
             "info": {}})
    kind, res = ap.receive(60)
    print(json.dumps({"kind": kind, "result": res, "separate_user": ap._agent_uid is not None}))
finally:
    ap.close()
"""


def peek_policy_source(name: str) -> str:
    """PEEK_POLICY looking for the variable `name` instead of the default."""
    return PEEK_POLICY.replace('NAME = "AUDITGYM_REDTEAM_SECRET"', f"NAME = {name!r}")


def secret_env_probe(name: str = "AUDITGYM_REDTEAM_SECRET_ENV", timeout_s: float = 300.0, lower: bool = True) -> dict:
    """Run `python -m auditgym run --seeds-file examples/closed_seeds_example.json --secret-env NAME` in a subprocess
    that has NAME set, with a probe policy that looks for NAME in its parent's environment (lower=False: on
    Windows the child stays at the host's integrity level, the control that shows the probe can read). Returns the
    probe's first reported action (readable, found_in_parent, in_own_environment); raises RuntimeError if the run failed."""
    import json

    with tempfile.TemporaryDirectory(prefix="auditgym_secret_probe_") as tmp:
        os.chmod(tmp, 0o755)  # in the image the policy runs as another uid and must reach its module
        Path(tmp, "peekparent.py").write_text(peek_policy_source(name), encoding="utf-8")
        out = Path(tmp, "out")
        cmd = [sys.executable, "-m", "auditgym", "run", "--seeds-file",
               str(protocol.PROJECT_ROOT / "examples" / "closed_seeds_example.json"), "--secret-env", name,
               "--policies", "peekparent:Probe", "--policy-path", tmp, "--out", str(out)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(protocol.PROJECT_ROOT),
                           env=dict(os.environ, **{name: "redteam-marker-not-a-secret"},
                                    **({} if lower else {protocol.NO_LOWER_ENV: "1"})))
        try:
            lines = Path(out, "trajectories.jsonl").read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            action = json.loads(line).get("action")
            if isinstance(action, dict) and action.get("action") == "probe":
                return action
    raise RuntimeError(f"run exited {p.returncode} without a probe result: {p.stderr.strip()[-300:]}")


def secret_env_visibility() -> str:
    """Can a policy child find the --secret-env variable in its parent's environment after `run` read it?"""
    try:
        res = secret_env_probe()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        return f"--secret-env probe failed: {exc}"
    if res.get("no_proc"):
        return "--secret-env: not measured on this platform (no /proc)"
    if not res.get("readable"):
        why = f" ({res['why']})" if res.get("why") else ""
        return f"--secret-env: the parent's environment is not readable{why}"
    found = "found" if res.get("found_in_parent") else "not found"
    return f"--secret-env: parent's environment readable, secret variable {found} there"


def parent_secret_visibility(harden: bool = True) -> str:
    """Can a policy child started by the harness find a variable of the host's environment?
    harden=False keeps the host dumpable: the control that shows the probe can read at all."""
    import json

    with tempfile.TemporaryDirectory(prefix="auditgym_peek_") as tmp:
        os.chmod(tmp, 0o755)  # in the image the policy runs as another uid and must reach its module
        Path(tmp, "peekparent.py").write_text(PEEK_POLICY, encoding="utf-8")
        env = dict(os.environ, AUDITGYM_REDTEAM_SECRET="redteam-marker-not-a-secret")
        argv = [sys.executable, "-c", PEEK_HOST, tmp] + ([] if harden else ["plain"])
        p = subprocess.run(argv, capture_output=True, text=True, timeout=120,
                           cwd=str(protocol.PROJECT_ROOT), env=env)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "probe failed: " + (p.stderr.strip()[-300:] or p.stdout.strip()[-300:])
    res = out.get("result") or {}
    if not isinstance(res, dict) or out.get("kind") != "action":
        return f"probe failed: {out}"
    who = "separate policy user" if out.get("separate_user") else "same user as the host"
    note = ""  # Windows: the integrity level goes after the label prefix, so tools/ci_excerpt.py keeps the line
    if os.name == "nt":
        level = str(res.get("integrity", "unknown"))
        note = "child at Low integrity, " if level.startswith("lowered") else f"child at the host's integrity level ({level}), "
    if res.get("no_proc"):
        return f"{who}: {note}not measured on this platform (no /proc)"
    if not res.get("readable"):
        why = f" ({res['why']})" if res.get("why") else ""
        return f"{who}: {note}the parent's environment is not readable{why}"
    found = "found" if res.get("found_in_parent") else "not found"
    own = "present" if res.get("in_own_environment") else "absent"
    return f"{who}: {note}parent's environment readable, host variable {found} there ({own} in the child's own environment)"


def print_parent_report() -> int:
    """Print what a policy child can see of its parent, as measured here (Linux: after harden_host())."""
    protocol.harden_host()
    print("parent process visibility from a policy child (measured):")
    if os.name == "nt":
        print("  host hardening: Windows: no host-side hardening; the policy child lowers its own token to Low integrity")
    else:
        print("  host hardening: " + protocol.HARDEN_STATUS)
    print("  " + parent_visibility())
    print("  " + parent_secret_visibility())
    if sys.platform.startswith("linux") or os.name == "nt":
        print("  control with host hardening off: " + parent_secret_visibility(harden=False))
    print("  " + secret_env_visibility())
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--parent" in argv:  # only the parent-visibility measurement, a few seconds
        return print_parent_report()
    rows = _probes()
    width = max(len(r[0]) for r in rows)
    ok = True
    for name, passed, secs, detail in rows:
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name.ljust(width)}  {secs:5.1f} s  {detail}")
    print_parent_report()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
