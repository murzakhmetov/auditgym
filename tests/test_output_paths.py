"""An output path that cannot be written is one `error:` line and exit code 2, not a Python traceback."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T03 = ROOT / "episodes" / "train" / "t03_duplicate"


def run(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")  # the OS error text may be localized
    return subprocess.run([sys.executable, "-m", "auditgym", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=180)


class OutputPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.blocker = Path(self._tmp.name) / "a_file"
        self.blocker.write_text("not a directory\n", encoding="utf-8", newline="\n")
        self.under_file = self.blocker / "out"  # a directory below a regular file cannot be created

    def tearDown(self):
        self._tmp.cleanup()

    def assert_error_line(self, r):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        # a host that is not root may print a "policy runs as the host user" warning first: exactly one error line is the contract
        errors = [ln for ln in r.stderr.splitlines() if ln.startswith("error:")]
        self.assertEqual(len(errors), 1, r.stderr)

    def test_transform_out_is_an_existing_file(self):
        self.assert_error_line(run("transform", "--in", str(T03), "--out", str(self.blocker), "--remap-seed", "7"))

    def test_transform_out_below_a_file(self):
        self.assert_error_line(run("transform", "--in", str(T03), "--out", str(self.under_file), "--remap-seed", "7"))

    def test_schemas_out_is_an_existing_file(self):
        self.assert_error_line(run("schemas", "--out", str(self.blocker)))

    def test_schemas_out_below_a_file(self):
        self.assert_error_line(run("schemas", "--out", str(self.under_file)))

    def test_generate_out_is_an_existing_file(self):
        self.assert_error_line(run("generate", "--seed", "5", "--config", '{"size": "small"}', "--out", str(self.blocker)))

    def test_viewer_out_below_a_file(self):
        self.assert_error_line(run("viewer", "--out", str(self.under_file)))


if __name__ == "__main__":
    unittest.main()
