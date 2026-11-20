"""Windows host hardening: a policy child at Low integrity cannot read its parent's process memory.

The child lowers its own token to Low integrity (S-1-16-4096) before any policy code loads (auditgym/agent.py);
Windows mandatory integrity control then refuses PROCESS_VM_READ on the Medium-integrity host. The tests go through
the real harness (protocol.AgentProcess). The positive control runs the same probe with the lowering switched off
and must find the host variable, so the negative assertion cannot pass because the probe was blind.
They skip off Windows; Linux is covered by tests/test_linux_hardening.py.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from auditgym import protocol, redteam

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = os.name == "nt"

# The host side: a separate process whose environment holds the variable from its start; it starts the policy
# through protocol.AgentProcess and prints the first action. argv: policy directory, module:Class, mode.
HOST = r"""
import json, os, sys
from auditgym import protocol
if sys.argv[3] == "control":
    protocol.LOWER_INTEGRITY = False
ap = protocol.AgentProcess(sys.argv[2], 0, policy_path=sys.argv[1])
try:
    ap.send({"type": "observation", "observation": {}, "reward": 0.0, "terminated": False, "truncated": False,
             "info": {}})
    kind, res = ap.receive(60)
    print(json.dumps({"kind": kind, "host_pid": os.getpid(), "result": res, "stderr": ap.stderr_tail()[-400:]}))
finally:
    ap.close()
"""

# Writes where a policy may need to: its working directory, a subdirectory, tempfile, and a grandchild process.
WRITE_POLICY = r'''
import os, subprocess, sys, tempfile


class Probe:
    def __init__(self, seed=0):
        pass

    def act(self, observation, reward=0.0, info=None):
        out = {"action": "probe"}
        try:
            with open("note.txt", "w", encoding="utf-8") as fh:
                fh.write("hello")
            os.mkdir("sub")
            with open(os.path.join("sub", "b.txt"), "w", encoding="utf-8") as fh:
                fh.write("again")
            with open("note.txt", encoding="utf-8") as fh:
                out["cwd_write"] = fh.read() == "hello"
            os.remove("note.txt")
            with tempfile.NamedTemporaryFile("w", delete=True) as tmp:
                tmp.write("x")
            out["tempfile"] = True
            same = lambda a, b: os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
            out["temp_is_cwd"] = (same(os.environ["TEMP"], os.getcwd()) and same(os.environ["TMP"], os.getcwd())
                                  and same(tempfile.gettempdir(), os.getcwd()))
            r = subprocess.run([sys.executable, "-c", "print(40 + 2)"], capture_output=True, text=True, timeout=30)
            out["grandchild"] = r.stdout.strip()
        except Exception as exc:
            out["error"] = type(exc).__name__ + ": " + str(exc)
        out["cwd"] = os.getcwd()
        out["integrity"] = str(getattr(sys.modules.get("auditgym.agent"), "INTEGRITY_STATUS", "unknown"))
        return out
'''


def run_policy(source: str, klass_module: str, mode: str, env_extra=None) -> dict:
    with tempfile.TemporaryDirectory(prefix="auditgym_winhard_") as tmp:
        Path(tmp, klass_module + ".py").write_text(source, encoding="utf-8")
        env = dict(os.environ, **(env_extra or {}))
        p = subprocess.run([sys.executable, "-c", HOST, tmp, klass_module + ":Probe", mode], capture_output=True,
                           text=True, timeout=120, cwd=str(ROOT), env=env)
        try:
            out = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise AssertionError("host failed: " + (p.stderr.strip()[-400:] or p.stdout.strip()[-400:]))
    if out.get("kind") != "action" or not isinstance(out.get("result"), dict):
        raise AssertionError(f"no probe action: {out}")
    return dict(out["result"], host_pid=out["host_pid"])


@unittest.skipUnless(WINDOWS, "Windows only: integrity levels")
class LowIntegrityChild(unittest.TestCase):
    ENV = {"AUDITGYM_REDTEAM_SECRET": "redteam-marker-not-a-secret"}

    def test_positive_control_child_reads_the_parent_environment(self):
        res = run_policy(redteam.PEEK_POLICY, "peekparent", "control", self.ENV)
        self.assertTrue(res["readable"], res)
        self.assertTrue(res["found_in_parent"], "the control must find the host variable, or the probe is blind")
        self.assertFalse(res["in_own_environment"])
        self.assertTrue(res["integrity"].startswith("off"), res["integrity"])

    def test_low_integrity_child_cannot_read_the_parent_environment(self):
        res = run_policy(redteam.PEEK_POLICY, "peekparent", "harness", self.ENV)
        self.assertTrue(res["integrity"].startswith("lowered"), res["integrity"])
        self.assertFalse(res["readable"], res)
        self.assertFalse(res["found_in_parent"])
        self.assertIn("error 5", res["why"], "expected ERROR_ACCESS_DENIED from OpenProcess, not another failure")
        self.assertEqual(res["ppid"], res["host_pid"], "the probe must have targeted the host, not a launcher")

    def test_policy_still_writes_in_its_working_directory(self):
        res = run_policy(WRITE_POLICY, "writer", "harness")
        self.assertNotIn("error", res, res)
        self.assertTrue(res["integrity"].startswith("lowered"), res["integrity"])
        self.assertTrue(res["cwd_write"])
        self.assertTrue(res["tempfile"])
        self.assertTrue(res["temp_is_cwd"], "TEMP/TMP must point at the Low-labelled working directory")
        self.assertEqual(res["grandchild"], "42")
        self.assertTrue(res["cwd"].endswith("work"), res["cwd"])

    def test_staged_code_is_not_writable_by_the_low_integrity_child(self):
        source = ("import os, sys\n"
                  "class Probe:\n"
                  "    def __init__(self, seed=0): pass\n"
                  "    def act(self, observation, reward=0.0, info=None):\n"
                  "        agent = sys.modules['auditgym.agent'].__file__\n"
                  "        try:\n"
                  "            open(agent, 'a').close()\n"
                  "            wrote = True\n"
                  "        except OSError:\n"
                  "            wrote = False\n"
                  "        return {'action': 'probe', 'wrote_staged_code': wrote}\n")
        res = run_policy(source, "stagedwriter", "harness")
        self.assertFalse(res["wrote_staged_code"])

    def test_low_integrity_child_cannot_edit_or_plant_grader_files(self):
        # CodeEditor and PycPlanter (examples/hostile) write into a copy of the repository the host made at Medium;
        # at Low both writes are refused, so the files stay as they were (the digest check is covered, with the
        # level kept, in tests/test_redteam.py)
        import shutil
        from unittest import mock

        from tests.test_env import episode

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for d in ("auditgym", "configs", "schemas", "examples"):
                shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            target = root / "auditgym" / "reward.py"
            before = target.read_bytes()
            with mock.patch.object(protocol, "PROJECT_ROOT", root):
                protocol.refresh_bytecode()  # the host itself may compile the copy: not the child's doing
                digest = protocol.code_digest(root)
            for base in ("CodeEditor", "PycPlanter"):
                with mock.patch.object(protocol, "PROJECT_ROOT", root):
                    res, _, _, _ = redteam.run_hostile(base, 20.0, episode(), "eval", False, TARGET=str(target))
                self.assertIn("PermissionError", res["agent_error"] or "", base)
                self.assertFalse(res["grade"]["valid"], base)  # the policy died on the refused write
            self.assertEqual(target.read_bytes(), before)
            with mock.patch.object(protocol, "PROJECT_ROOT", root):
                self.assertEqual(protocol.code_digest(root), digest, "nothing may be planted or changed")

    def test_failed_label_falls_back_to_the_host_level(self):
        # if the working directory cannot be labelled Low the child must not be lowered (it would lose its cwd)
        from unittest import mock

        with mock.patch.object(protocol, "_label_low", return_value=False):
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, "writer.py").write_text(WRITE_POLICY, encoding="utf-8")
                ap = protocol.AgentProcess("writer:Probe", 0, policy_path=tmp)
                try:
                    ap.send({"type": "observation", "observation": {}, "reward": 0.0, "terminated": False,
                             "truncated": False, "info": {}})
                    kind, res = ap.receive(60)
                finally:
                    ap.close()
        self.assertEqual(kind, "action")
        self.assertTrue(res["integrity"].startswith("off: label failed"), res["integrity"])
        self.assertTrue(res["cwd_write"])

    def test_policy_path_code_does_not_run_before_the_token_is_lowered(self):
        # a sitecustomize.py and a module shadowing argparse (agent.py imports it first) in the policy directory
        # would run at the host's level if the directory were on PYTHONPATH from interpreter start
        shadow = ("import builtins, importlib, os, sys\n"
                  "builtins.EARLY_RAN = 'argparse'\n"
                  "here = os.path.dirname(os.path.abspath(__file__))\n"
                  "sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != here]\n"
                  "del sys.modules['argparse']\n"
                  "real = importlib.import_module('argparse')\n"
                  "sys.modules['argparse'] = real\n"
                  "globals().update(real.__dict__)\n")
        probe = ("import builtins, sys\n"
                 "class Probe:\n"
                 "    def __init__(self, seed=0): pass\n"
                 "    def act(self, observation, reward=0.0, info=None):\n"
                 "        agent = sys.modules.get('auditgym.agent')\n"
                 "        return {'action': 'probe', 'early': str(getattr(builtins, 'EARLY_RAN', None)),\n"
                 "                'site': 'sitecustomize' in sys.modules,\n"
                 "                'integrity': str(getattr(agent, 'INTEGRITY_STATUS', ''))}\n")
        with tempfile.TemporaryDirectory(prefix="auditgym_winhard_") as tmp:
            Path(tmp, "sitecustomize.py").write_text("import builtins\nbuiltins.EARLY_RAN = 'sitecustomize'\n",
                                                     encoding="utf-8")
            Path(tmp, "argparse.py").write_text(shadow, encoding="utf-8")
            # ctypes is imported by _lower_integrity itself: a shadow on the path before that runs at Medium
            Path(tmp, "ctypes.py").write_text(shadow.replace("argparse", "ctypes"), encoding="utf-8")
            Path(tmp, "lateprobe.py").write_text(probe, encoding="utf-8")
            p = subprocess.run([sys.executable, "-c", HOST, tmp, "lateprobe:Probe", "harness"], capture_output=True,
                               text=True, timeout=120, cwd=str(ROOT))
            out = json.loads(p.stdout.strip().splitlines()[-1])
        res = out["result"]
        self.assertTrue(res["integrity"].startswith("lowered"), out)
        self.assertEqual(res["early"], "None", "policy-directory code ran before the token was lowered")
        self.assertFalse(res["site"])

    def test_policy_directory_follows_the_staged_code_on_sys_path(self):
        # colorsys is a stdlib module agent.py has not imported: the policy's copy must win in the lowered child,
        # as it does in process (the directory goes in right after the staged code, not at the end of sys.path)
        probe = ("class Probe:\n"
                 "    def __init__(self, seed=0): pass\n"
                 "    def act(self, observation, reward=0.0, info=None):\n"
                 "        import colorsys\n"
                 "        return {'action': 'probe', 'mark': str(getattr(colorsys, 'MARK', 'stdlib colorsys'))}\n")
        with tempfile.TemporaryDirectory(prefix="auditgym_winhard_") as tmp:
            Path(tmp, "colorsys.py").write_text("MARK = 'policy-directory colorsys'\n", encoding="utf-8")
            Path(tmp, "pathprobe.py").write_text(probe, encoding="utf-8")
            p = subprocess.run([sys.executable, "-c", HOST, tmp, "pathprobe:Probe", "harness"], capture_output=True,
                               text=True, timeout=120, cwd=str(ROOT))
            out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(out["result"]["mark"], "policy-directory colorsys", out)

    def test_multiprocessing_pool_works_in_the_low_integrity_child(self):
        # the child's own process object is relabelled Low too, so DuplicateHandle on itself still works
        source = ("import multiprocessing, sys\n"
                  "def square(x):\n"
                  "    return x * x\n"
                  "class Probe:\n"
                  "    def __init__(self, seed=0): pass\n"
                  "    def act(self, observation, reward=0.0, info=None):\n"
                  "        agent = sys.modules.get('auditgym.agent')\n"
                  "        out = {'action': 'probe', 'integrity': str(getattr(agent, 'INTEGRITY_STATUS', ''))}\n"
                  "        try:\n"
                  "            with multiprocessing.Pool(2) as pool:\n"
                  "                out['pool'] = pool.map(square, [1, 2, 3])\n"
                  "        except Exception as exc:\n"
                  "            out['error'] = type(exc).__name__ + ': ' + str(exc)\n"
                  "        return out\n")
        res = run_policy(source, "poolpolicy", "harness")
        self.assertTrue(res["integrity"].startswith("lowered"), res["integrity"])
        self.assertNotIn("error", res, res)
        self.assertEqual(res["pool"], [1, 4, 9])


@unittest.skipUnless(WINDOWS, "Windows only: integrity levels")
class ReportShape(unittest.TestCase):
    def test_ci_excerpt_keeps_the_windows_report_lines(self):
        from tools import ci_excerpt

        import contextlib
        import io
        from unittest import mock

        low = ("same user as the host: child at Low integrity, the parent's environment is not readable "
               "(OpenProcess(PROCESS_VM_READ) error 5)")
        plain = ("same user as the host: child at the host's integrity level (off: control run), "
                 "parent's environment readable, host variable found there (absent in the child's own environment)")
        buf = io.StringIO()
        with mock.patch.object(redteam, "parent_visibility", return_value=low), \
                mock.patch.object(redteam, "parent_secret_visibility",
                                  side_effect=lambda harden=True: low if harden else plain), \
                mock.patch.object(redteam, "secret_env_visibility", return_value="--secret-env: probe"), \
                contextlib.redirect_stdout(buf):
            redteam.print_parent_report()
        lines = buf.getvalue().splitlines()
        self.assertTrue(any(x.startswith("  host hardening: Windows") for x in lines), lines)
        self.assertTrue(any(x.startswith("  control with host hardening off: ") for x in lines), lines)
        raw = [f"job\tstep\t2026-01-01T00:00:00.0000000Z {line}\n" for line in lines]
        kept = [k.split(" | ", 2)[2] for k in ci_excerpt.excerpt(raw, "1", "abc")[3:]]
        self.assertEqual(kept, lines[1:], "ci_excerpt dropped a printed report line")

    def test_host_hardening_line_shows_the_switch(self):
        import contextlib
        import io
        from unittest import mock

        def report():
            buf = io.StringIO()
            with mock.patch.object(redteam, "parent_visibility", return_value="x"), \
                    mock.patch.object(redteam, "parent_secret_visibility", return_value="x"), \
                    mock.patch.object(redteam, "secret_env_visibility", return_value="x"), \
                    contextlib.redirect_stdout(buf):
                redteam.print_parent_report()
            return buf.getvalue()

        self.assertIn("lowers its own token to Low integrity", report())
        with mock.patch.object(protocol, "LOWER_INTEGRITY", False):
            self.assertIn("lowering off", report())


@unittest.skipUnless(WINDOWS, "Windows only: process snapshot")
class ParentPid(unittest.TestCase):
    def test_ppid_fallback_asks_the_process_itself(self):
        from unittest import mock

        ns = {}
        exec(compile(redteam.PEEK_POLICY, "peekparent.py", "exec"), ns)  # _ppid lives in the probe policy's source
        expected = os.getppid()
        self.assertEqual(ns["_ppid"](), expected)
        with mock.patch("os.getppid", side_effect=FileNotFoundError(2, "WinError 18")):
            self.assertEqual(ns["_ppid"](), expected)


if __name__ == "__main__":
    unittest.main()
