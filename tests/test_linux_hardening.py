"""Linux host hardening: a same-user policy child must not read the host's /proc/<pid>/environ.

The measuring tests run only on Linux, where prctl(PR_SET_DUMPABLE, 0) exists; the CI ubuntu job is what proves them.
They skip the negative assertion (never the positive control) for a child that has CAP_SYS_PTRACE or runs as root,
since the kernel allows that child to read the file whatever the host does.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auditgym import protocol, redteam
from tests import same_user_start, same_user_stop

ROOT = Path(__file__).resolve().parent.parent
LINUX = sys.platform.startswith("linux")
CAP_SYS_PTRACE_BIT = 19
MARKER = "AUDITGYM_REDTEAM_SECRET"

PARENT_SCRIPT = """
import json, os, subprocess, sys
if sys.argv[1] == "harden":
    from auditgym import protocol
    protocol.harden_host()
child = ("import os\\n"
         "try:\\n"
         "    data = open('/proc/%d/environ' % os.getppid(), 'rb').read()\\n"
         "    print('readable', b'" + sys.argv[2] + "=' in data)\\n"
         "except PermissionError:\\n"
         "    print('denied')\\n"
         "except OSError as exc:\\n"
         "    print('error', exc.errno)\\n")
out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=60)
print(json.dumps(out.stdout.split() + [out.stderr[-200:]]))
"""


def setUpModule():
    same_user_start(__name__)


def tearDownModule():
    same_user_stop(__name__)


def ptrace_exemption():
    """Why this process may read another same-uid process's environ whatever the host does, or None."""
    if os.geteuid() == 0:
        return "the child runs as root, which can read /proc/<pid>/environ regardless of dumpability"
    try:
        status = Path("/proc/self/status").read_text(encoding="ascii")
    except OSError as exc:
        return f"cannot read /proc/self/status to check CapEff: {exc}"
    for line in status.splitlines():
        if line.startswith("CapEff:"):
            if int(line.split()[1], 16) >> CAP_SYS_PTRACE_BIT & 1:
                return "the child has CAP_SYS_PTRACE (bit 19 of CapEff)"
            return None
    return "no CapEff line in /proc/self/status"


@unittest.skipUnless(LINUX, "Linux only: prctl(PR_SET_DUMPABLE) and /proc/<pid>/environ exist only there; "
                     "Windows and macOS are not hardened and keep their documented limitation")
class ParentEnvironment(unittest.TestCase):
    def parent_run(self, mode: str) -> list:
        env = dict(os.environ, **{MARKER: "redteam-marker-not-a-secret"})
        p = subprocess.run([sys.executable, "-c", PARENT_SCRIPT, mode, MARKER], capture_output=True, text=True,
                           timeout=120, cwd=str(ROOT), env=env)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_unhardened_parent_is_readable_and_hardened_parent_is_not(self):
        plain = self.parent_run("plain")
        self.assertEqual(plain[:2], ["readable", "True"], f"positive control failed, the probe proves nothing: {plain}")
        reason = ptrace_exemption()
        if reason:
            self.skipTest(reason)
        self.assertEqual(self.parent_run("harden")[0], "denied")

    def test_hardening_is_reported_as_applied(self):
        self.assertTrue(protocol.harden_host(), protocol.HARDEN_STATUS)
        self.assertTrue(protocol.harden_host())
        self.assertTrue(protocol.HARDEN_STATUS.startswith("applied"), protocol.HARDEN_STATUS)


@unittest.skipUnless(LINUX, "Linux only: the policy child reads /proc/<ppid>/environ of the host")
class ThroughTheHarness(unittest.TestCase):
    def test_policy_child_of_the_real_harness_cannot_read_the_host_environment(self):
        with tempfile.TemporaryDirectory(prefix="auditgym_harden_") as tmp:
            os.chmod(tmp, 0o755)
            policy = Path(tmp, "peekparent.py")
            policy.write_text(redteam.PEEK_POLICY, encoding="utf-8")
            os.chmod(policy, 0o644)
            env = dict(os.environ, **{MARKER: "redteam-marker-not-a-secret"})
            p = subprocess.run([sys.executable, "-c", redteam.PEEK_HOST, tmp], capture_output=True, text=True,
                               timeout=120, cwd=str(ROOT), env=env)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(out["kind"], "action", out)
        self.assertFalse(out["separate_user"], "the child must be the host's own user for this measurement")
        res = out["result"]
        reason = ptrace_exemption()
        if reason:
            self.skipTest(reason)
        self.assertFalse(res["readable"])
        self.assertFalse(res["found_in_parent"])
        self.assertFalse(res["in_own_environment"])


class NeverRaises(unittest.TestCase):
    """Runs everywhere: every failure of the hardening call is a status string, never an exception."""

    def fresh(self):
        return mock.patch.multiple(protocol, _HARDENED=False, HARDEN_STATUS="not tried")

    def test_other_platforms_do_nothing(self):
        with self.fresh(), mock.patch.object(sys, "platform", "win32"):
            self.assertFalse(protocol.harden_host())
            self.assertIn("not Linux", protocol.HARDEN_STATUS)

    def test_missing_libc_is_recorded(self):
        import ctypes

        with self.fresh(), mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(ctypes, "CDLL", side_effect=OSError("no libc")):
            self.assertFalse(protocol.harden_host())
            self.assertIn("unavailable", protocol.HARDEN_STATUS)
            self.assertIn("no libc", protocol.HARDEN_STATUS)

    def test_a_prctl_error_is_recorded(self):
        import ctypes

        libc = mock.MagicMock()
        libc.prctl.return_value = -1
        with self.fresh(), mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(ctypes, "CDLL", return_value=libc):
            self.assertFalse(protocol.harden_host())
            self.assertIn("failed", protocol.HARDEN_STATUS)


if __name__ == "__main__":
    unittest.main()
