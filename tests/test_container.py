"""Container-only isolation tests: the policy child runs as a separate unprivileged user.

They run inside the official image (root host, AUDITGYM_AGENT_USER=agent):
  docker run --rm --network none --cpus 2 --memory 4g auditgym python -m unittest tests.test_container -v
Everywhere else (Windows, macOS, CI without the image, a non-root user, dropped capabilities) every
test is SKIPPED, because the switch to the agent user is not possible there and the code falls back
to the same user. Strict mode (AUDITGYM_REQUIRE_AGENT_USER=1) turns that fallback into an error; its error
path is tested in tests/test_cli.py, its success path here.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from auditgym import __main__ as cli_mod
from auditgym import io as aio
from auditgym import protocol

IDENT = aio.agent_identity()
ROOT = protocol.PROJECT_ROOT


def can_switch() -> bool:
    """True only when this process can really start a child as the agent user."""
    if IDENT is None:
        return False
    ap = None
    try:
        ap = protocol.AgentProcess("recon", 0)
        return ap._agent_uid == IDENT[1]
    except Exception:
        return False
    finally:
        if ap is not None:
            ap.close()


READY = can_switch()

PROBE = '''
import json, os, subprocess, sys

def readable(path):
    try:
        with open(path, "rb") as fh:
            fh.read(1)
        return True
    except OSError:
        return False

def listable(path):
    try:
        return bool(os.listdir(path))
    except OSError:
        return False

def writable(path):
    try:
        with open(path, "w") as fh:
            fh.write("x")
        os.unlink(path)
        return True
    except OSError:
        return False

class Probe:
    def __init__(self, seed=0):
        pass

    def act(self, observation, reward=0.0, info=None):
        cfg = json.load(open(os.path.join(os.path.dirname(__file__), "cfg.json")))
        out = {"action": "probe", "euid": os.geteuid(), "egid": os.getegid(), "groups": os.getgroups(),
               "environ": readable("/proc/%d/environ" % os.getppid()),
               "cmdline": readable("/proc/%d/cmdline" % os.getppid()),
               "seeds": readable(cfg["seeds"]), "grader_dir": readable(cfg["grader"]),
               "grader_list": listable(os.path.dirname(cfg["grader"])),
               "pkg_write": writable(cfg["package_file"]), "app_read": readable(cfg["app_file"]),
               "cwd_write": writable("probe.tmp")}
        if cfg.get("spawn"):
            subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out["spawned"] = True
        return out
'''


@unittest.skipUnless(READY, "container-only: needs a root host with AUDITGYM_AGENT_USER set and setuid allowed")
class SeparateUser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="auditgym_ct_")  # 0700 root, like the host's own files
        os.chmod(cls.tmp, 0o711)  # traversable, so the agent can reach its policy; every file below is protected itself
        cls.policy_dir = Path(cls.tmp, "policy")
        cls.policy_dir.mkdir()
        cls.seeds = Path(cls.tmp, "seeds.json")
        cls.seeds.write_text('{"seeds": [1, 2, 3]}', encoding="utf-8")
        os.chmod(cls.seeds, 0o600)
        ep = Path(cls.tmp, "episode")
        (ep / "public").mkdir(parents=True)
        os.chmod(ep, 0o755)
        with aio.private_files():  # the same path the host uses to write grader files
            aio.write_text(ep / "grader" / "truth.json", '{"issues": []}')
        cls.grader = ep / "grader" / "truth.json"
        cls.package_file = ROOT / "auditgym" / "planted_by_agent.txt"
        (cls.policy_dir / "cprobe.py").write_text(PROBE, encoding="utf-8")
        os.chmod(cls.policy_dir, 0o755)  # the agent must be able to import its own policy

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        try:
            cls.package_file.unlink()
        except OSError:
            pass

    def probe(self, spawn=False) -> dict:
        cfg = {"seeds": str(self.seeds), "grader": str(self.grader), "package_file": str(self.package_file),
               "app_file": str(ROOT / "auditgym" / "protocol.py"), "spawn": spawn}
        cfg_path = self.policy_dir / "cfg.json"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        os.chmod(cfg_path, 0o644)
        ap = protocol.AgentProcess("cprobe:Probe", 0, policy_path=str(self.policy_dir))
        try:
            self.assertEqual(ap._agent_uid, IDENT[1])
            self.assertTrue(ap.send({"type": "observation", "observation": {}, "reward": 0.0,
                                     "terminated": False, "truncated": False, "info": {}}))
            kind, res = ap.receive(30)
            self.assertEqual(kind, "action", ap.stderr_tail())
            self.res_uid = ap._agent_uid
        finally:
            ap.close()
        return res

    def test_child_is_the_agent_user(self):
        res = self.probe()
        self.assertEqual((res["euid"], res["egid"], res["groups"]), (IDENT[1], IDENT[2], []))
        self.assertTrue(res["cwd_write"])

    def test_agent_cannot_read_the_parent_environment(self):
        res = self.probe()
        self.assertFalse(res["environ"])

    def test_agent_cannot_read_a_root_owned_0600_seeds_file(self):
        self.assertEqual(oct(self.seeds.stat().st_mode & 0o777), "0o600")
        self.assertFalse(self.probe()["seeds"])

    def test_agent_cannot_read_a_grader_directory_the_host_wrote(self):
        self.assertEqual(self.grader.parent.stat().st_mode & 0o077, 0)
        self.assertEqual(self.grader.stat().st_mode & 0o077, 0)
        res = self.probe()
        self.assertFalse(res["grader_dir"])
        self.assertFalse(res["grader_list"])

    def test_agent_cannot_write_to_the_package(self):
        res = self.probe()
        self.assertFalse(res["pkg_write"])
        self.assertFalse(self.package_file.exists())

    def test_agent_cannot_read_the_app_tree(self):
        self.assertFalse(self.probe()["app_read"])

    def test_strict_mode_starts_the_child_as_the_agent_user(self):
        """AUDITGYM_REQUIRE_AGENT_USER=1 changes nothing where the switch works: same user, no error."""
        with mock.patch.dict(os.environ, {"AUDITGYM_REQUIRE_AGENT_USER": "1"}):
            cli_mod._require_agent_user()  # the pre-flight of check, run, demo and budget
            ap = protocol.AgentProcess("recon", 0)
        try:
            self.assertEqual(ap._agent_uid, IDENT[1])
            status = Path("/proc", str(ap.proc.pid), "status").read_text(encoding="ascii")
            self.assertRegex(status, r"(?m)^Uid:\s+%d\s+%d" % (IDENT[1], IDENT[1]))
        finally:
            ap.close()

    def test_close_kills_every_process_of_the_agent_uid(self):
        res = self.probe(spawn=True)
        self.assertTrue(res["spawned"])
        deadline = time.monotonic() + 5
        while protocol._uid_pids(IDENT[1]) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(protocol._uid_pids(IDENT[1]), [])


class Fallback(unittest.TestCase):
    """Runs everywhere: without the switch the policy still runs, as the host's user."""

    def test_policy_runs_in_any_environment(self):
        ap = protocol.AgentProcess("recon", 0)
        try:
            self.assertTrue(ap.send({"type": "end"}))
            ap.proc.wait(timeout=20)
            self.assertEqual(ap.proc.returncode, 0, ap.stderr_tail())
        finally:
            ap.close()


if __name__ == "__main__":
    unittest.main()
