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
    def peek(self, *extra: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="auditgym_harden_") as tmp:
            os.chmod(tmp, 0o755)
            policy = Path(tmp, "peekparent.py")
            policy.write_text(redteam.PEEK_POLICY, encoding="utf-8")
            os.chmod(policy, 0o644)
            env = dict(os.environ, **{MARKER: "redteam-marker-not-a-secret"})
            p = subprocess.run([sys.executable, "-c", redteam.PEEK_HOST, tmp, *extra], capture_output=True,
                               text=True, timeout=120, cwd=str(ROOT), env=env)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(out["kind"], "action", out)
        self.assertFalse(out["separate_user"], "the child must be the host's own user for this measurement")
        return out["result"]

    def test_policy_child_of_the_real_harness_cannot_read_the_host_environment(self):
        control = self.peek("plain")
        self.assertTrue(control["readable"] and control["found_in_parent"],
                        f"positive control failed, the probe proves nothing: {control}")
        reason = ptrace_exemption()
        if reason:
            self.skipTest(reason)
        res = self.peek()
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

    def test_prctl_arguments_and_idempotence(self):
        import ctypes

        libc = mock.MagicMock()
        libc.prctl.side_effect = [0, 0]
        with self.fresh(), mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(ctypes, "CDLL", return_value=libc):
            self.assertTrue(protocol.harden_host())
            self.assertTrue(protocol.harden_host())
            self.assertTrue(protocol.HARDEN_STATUS.startswith("applied"), protocol.HARDEN_STATUS)
        self.assertEqual([c.args for c in libc.prctl.call_args_list], [(4, 0, 0, 0, 0), (3, 0, 0, 0, 0)])

    def test_still_dumpable_is_not_reported_as_applied(self):
        import ctypes

        libc = mock.MagicMock()
        libc.prctl.side_effect = [0, 1]
        with self.fresh(), mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(ctypes, "CDLL", return_value=libc):
            self.assertFalse(protocol.harden_host())
            self.assertIn("still dumpable", protocol.HARDEN_STATUS)

    def test_the_harness_hardens_before_it_starts_the_child(self):
        calls = []

        def popen(*args, **kwargs):
            calls.append("popen")
            raise RuntimeError("stop here")

        cleanups = []
        real_cleanup = tempfile.TemporaryDirectory.cleanup

        def cleanup(tmp):
            cleanups.append(tmp.name)
            real_cleanup(tmp)

        with mock.patch.object(protocol, "harden_host", side_effect=lambda: calls.append("harden")), \
                mock.patch.object(subprocess, "Popen", side_effect=popen), \
                mock.patch.object(tempfile.TemporaryDirectory, "cleanup", cleanup):
            with self.assertRaises(RuntimeError):
                protocol.AgentProcess("recon")
        self.assertEqual(calls[:2], ["harden", "popen"])
        self.assertEqual(len(cleanups), 1, "the staged temporary directory must be removed when the child never starts")


class ReportLines(unittest.TestCase):
    """The CI excerpt keeps every line shape of `python -m auditgym.redteam --parent`."""

    LINES = ["  host hardening: applied: PR_SET_DUMPABLE 0",
             "  same user as the host: the parent's environment is not readable",
             "  separate policy user: the parent's environment is not readable",
             "  same user as the host: parent's environment readable, host variable found there (absent in the child's own environment)",
             "  control with host hardening off: same user as the host: parent's environment readable, host variable found there",
             "  --secret-env: the parent's environment is not readable",
             "  --secret-env: not measured on this platform (no /proc)",
             "  --secret-env probe failed: run exited 1 without a probe result",
             "  probe failed: boom"]

    def test_excerpt_keeps_the_report_lines(self):
        from tools import ci_excerpt

        raw = [f"job\tstep\t2026-01-01T00:00:00.0000000Z {line}\n" for line in self.LINES]
        kept = ci_excerpt.excerpt(raw, "1", "abc")[3:]
        self.assertEqual([k.split(" | ", 2)[2] for k in kept], self.LINES)

    def test_excerpt_labels_each_container_mode_block(self):
        """The real log shape of the step: one group line (`Run set -o pipefail`), the script lines in ANSI codes, then
        for each mode a label echoed by the script and the report. Only the label tells the three blocks apart."""
        from tools import ci_excerpt

        step = "What a policy child sees of its parent in each container mode"
        stamp = "2026-01-01T00:00:00.0000000Z "
        script = ["set -o pipefail",
                  'echo "container mode: default image"',
                  "docker run --rm --network none auditgym python -m auditgym.redteam --parent 2>&1 | tee a.log"]
        msgs = ["##[group]Run set -o pipefail"] + [f"\x1b[36;1m{x}\x1b[0m" for x in script] + ["##[endgroup]"]
        expected = []
        for mode in ("default image", "--user 10001", "--cap-drop ALL"):
            block = [f"container mode: {mode}", self.LINES[0], self.LINES[1]]
            msgs += block
            expected += block
        raw = ["container\t" + step + "\t" + stamp + m + "\n" for m in msgs]
        kept = ci_excerpt.excerpt(raw, "1", "abc")[3:]
        self.assertEqual([k.split(" | ", 2)[2] for k in kept], expected)
        self.assertTrue(all(k.startswith(f"container | {step} | ") for k in kept))

    def test_every_container_redteam_run_is_labelled_in_the_workflow(self):
        text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "check.yml").read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines()]
        runs = [i for i, ln in enumerate(lines) if ln.startswith("docker run") and "auditgym.redteam --parent" in ln]
        self.assertEqual(len(runs), 3)
        for i in runs:
            self.assertTrue(lines[i - 1].startswith('echo "container mode: '), lines[i])

    def probe(self, error: OSError) -> dict:
        space = {"__name__": "peek"}
        exec(redteam.PEEK_POLICY, space)
        with mock.patch.object(os, "name", "posix"), mock.patch("builtins.open", side_effect=error):
            return space["Probe"]().act({})

    def test_a_missing_proc_is_not_reported_as_blocked(self):
        res = self.probe(FileNotFoundError(2, "no /proc"))
        self.assertTrue(res["no_proc"] and not res["readable"])

    def test_a_permission_error_is_reported_as_blocked(self):
        res = self.probe(PermissionError(13, "denied"))
        self.assertFalse(res["no_proc"] or res["readable"])


if __name__ == "__main__":
    unittest.main()
