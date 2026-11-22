"""judge_adapter.verify_episode: the repository's `verify` on the flat layout that generate_episode writes."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import judge_adapter as ja  # noqa: E402


class VerifyFlatLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name) / "flat"
        ja.generate_episode(4611686018427387905, {"size": "small", "errors": {"wrong_period": 1}}, str(cls.dir))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a_generated_flat_episode_verifies_and_regenerates(self):
        code, out = ja.verify_episode(str(self.dir))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("PASS  "), 9)
        code, out = ja.verify_episode(str(self.dir), regenerate=True)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS  regenerates_from_provenance", out)

    def test_a_changed_amount_fails(self):
        copy = Path(self._tmp.name) / "tampered"
        copy.mkdir()
        for p in self.dir.iterdir():
            (copy / p.name).write_bytes(p.read_bytes())
        truth = json.loads((copy / "truth.json").read_text(encoding="utf-8"))
        truth["issues"][0]["expected_amount_minor"] += 100
        (copy / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")
        code, out = ja.verify_episode(str(copy), regenerate=True)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)

    def test_the_repository_layout_is_passed_through(self):
        code, out = ja.verify_episode(str(ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"))
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
