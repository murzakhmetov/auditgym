"""`python -m auditgym verify DIR --regenerate`: the directory check that equals regeneration from provenance.json.

Without the flag, `verify DIR` accepts some edited copies (a shortened distractor list, a changed variant); with it, the episode
is regenerated from provenance.json (seed, config, generator version) and every public and grader file must match byte for byte.
An episode written with a host secret, or by another generator version, is an explicit skip, not a pass.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D08 = ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"


def verify(directory: Path, *flags):
    return subprocess.run([sys.executable, "-m", "auditgym", "verify", str(directory), *flags], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8", timeout=180)


def regen_line(r):
    lines = [ln for ln in r.stdout.splitlines() if "regenerates_from_provenance" in ln]
    return lines[0] if lines else ""


class RegenerateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "ep"
        shutil.copytree(D08, self.dir)
        self.prov_path = self.dir / "grader" / "provenance.json"
        self.prov = json.loads(self.prov_path.read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def write_prov(self):
        self.prov_path.write_text(json.dumps(self.prov, indent=2) + "\n", encoding="utf-8", newline="\n")

    def test_a_committed_episode_regenerates(self):
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(regen_line(r).startswith("PASS  regenerates_from_provenance"), r.stdout)

    def test_the_flag_is_off_by_default(self):
        r = verify(self.dir)
        self.assertEqual(r.stdout.count("PASS  "), 9)
        self.assertEqual(regen_line(r), "")

    def test_a_shortened_distractor_list_passes_without_the_flag_and_fails_with_it(self):
        self.prov["distractors"] = self.prov["distractors"][:-1]
        self.write_prov()
        self.assertEqual(verify(self.dir).returncode, 0)  # the known gap of the directory mode
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(regen_line(r).startswith("FAIL  regenerates_from_provenance"), r.stdout)
        self.assertIn("grader/provenance.json", regen_line(r))

    def test_an_edited_seed_fails(self):
        self.prov["seed"] = str(int(self.prov["seed"]) + 1)
        self.write_prov()
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(regen_line(r).startswith("FAIL  regenerates_from_provenance"), r.stdout)

    def test_an_edited_truth_variant_fails(self):
        path = self.dir / "grader" / "truth.json"
        truth = json.loads(path.read_text(encoding="utf-8"))
        issue = next(i for i in truth["issues"] if i["type"] == "wrong_period")
        issue["variant"] = "booked_late" if issue["variant"] != "booked_late" else "booked_early"
        path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("grader/truth.json", regen_line(r))

    def test_a_secret_episode_is_an_explicit_skip(self):
        self.prov["secret_used"] = True
        self.write_prov()
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(regen_line(r).startswith("SKIP  regenerates_from_provenance"), r.stdout)
        self.assertIn("host secret", regen_line(r))

    def test_another_generator_version_is_an_explicit_skip(self):
        self.prov["generator_version"] = "0.0.1"
        self.write_prov()
        r = verify(self.dir, "--regenerate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(regen_line(r).startswith("SKIP  regenerates_from_provenance"), r.stdout)
        self.assertIn("0.0.1", regen_line(r))

    def test_json_output_carries_the_check(self):
        r = verify(self.dir, "--regenerate", "--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(r.stdout)["checks"]["regenerates_from_provenance"], "pass")


if __name__ == "__main__":
    unittest.main()
