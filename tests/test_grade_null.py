"""`python -m auditgym grade` on a findings file that holds JSON null (or another non-object) is an invalid submission, not a traceback."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T03 = ROOT / "episodes" / "train" / "t03_duplicate"


def grade(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "f.json"
        path.write_text(text, encoding="utf-8", newline="\n")
        return subprocess.run([sys.executable, "-m", "auditgym", "grade", "--episode", str(T03), "--findings", str(path)],
                              cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=120)


class GradeNonObjectTests(unittest.TestCase):
    def test_json_null_is_an_invalid_submission(self):
        r = grade("null\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        rep = json.loads(r.stdout)
        self.assertEqual(rep["status"], "invalid_submission")
        self.assertEqual(rep["reward"], -1.0)
        self.assertEqual(rep["errors"], ["submission must be a JSON object"])

    def test_other_non_objects_are_invalid_submissions(self):
        for text in ("[]", "3", '"x"', "true"):
            with self.subTest(text=text):
                r = grade(text)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["status"], "invalid_submission")

    def test_text_that_is_not_json_still_names_the_file(self):
        r = grade("{not json")
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = json.loads(r.stdout)
        self.assertEqual(rep["status"], "invalid_submission")
        self.assertIn("is not valid JSON", rep["errors"][0])


if __name__ == "__main__":
    unittest.main()
