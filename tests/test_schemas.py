"""Published JSON schemas match the committed data, observations and the submission validator."""

import unittest
from pathlib import Path

from auditgym import schema_files as sf
from auditgym.episode import load_episode
from auditgym.runner import run_one
from auditgym.schemas import validate_submission
from tests.test_matcher import GOOD

ROOT = Path(__file__).resolve().parent.parent
EPISODES = sorted(p for split in ("train", "dev") for p in (ROOT / "episodes" / split).glob("*") if (p / "public").exists())


class SchemaTests(unittest.TestCase):
    def test_committed_records_match_schemas(self):
        self.assertEqual(len(EPISODES), 20)
        for d in EPISODES:
            ep = load_episode(d)
            errs = sf.validate(ep.manifest, sf.MANIFEST) + sf.validate(ep.truth, sf.TRUTH)
            for table, schema in (("ledger", sf.LEDGER_ROW), ("invoices", sf.INVOICE), ("payments", sf.PAYMENT), ("fx", sf.FX_ROW)):
                for r in ep.table(table):
                    errs += sf.validate(r, schema)
            self.assertEqual(errs[:5], [], d.name)

    def test_trajectories_observations_and_actions_match_schemas(self):
        ep = load_episode(EPISODES[0])
        for pol in ("recon", "auditor", "random", "flag_all"):
            traj, _ = run_one(ep, pol, isolated=False)
            for rec in traj:
                self.assertEqual(sf.validate(rec, sf.TRAJECTORY_RECORD), [], pol)
                self.assertEqual(sf.validate(rec["observation"], sf.OBSERVATION), [], pol)
                if rec["action"] is not None and pol in ("recon", "auditor"):
                    self.assertEqual(sf.validate(rec["action"], sf.ACTION_JSON_SCHEMA_ALIAS), [], rec["action"])

    def test_findings_schema_agrees_with_validator(self):
        good = {"episode_id": "ep_x", "findings": GOOD}
        self.assertEqual(sf.validate(good, sf.SUBMISSION_JSON_SCHEMA), [])
        self.assertEqual(validate_submission(good, "ep_x"), [])
        bad = [
            {"episode_id": "ep_x", "findings": [dict(GOOD[0], type="duplicate")]},
            {"episode_id": "ep_x", "findings": [dict(GOOD[0], evidence_ids=[f"E{i}" for i in range(11)])]},
            {"episode_id": "ep_x", "findings": [dict(GOOD[0], explanation="x" * 1001)]},
            {"episode_id": "ep_x", "findings": [dict(GOOD[0], claimed_amount_minor=-5)]},
            {"episode_id": "ep_x", "findings": [GOOD[0]] * 31},
            {"episode_id": "ep_x", "findings": [], "extra": 1},
        ]
        for b in bad:
            self.assertTrue(sf.validate(b, sf.SUBMISSION_JSON_SCHEMA))
            self.assertTrue(validate_submission(b, "ep_x"))

    def test_text_that_is_not_utf8_is_invalid_everywhere(self):
        # JSON Schema cannot say "encodes to UTF-8"; the validator does, so in process, the child and grade agree
        lone = "x" + chr(0xDC00)
        cases = [{"episode_id": "ep_x", "findings": [dict(GOOD[0], explanation=lone)]},
                 {"episode_id": "ep_x", "findings": [dict(GOOD[0], affected_ids=[lone])]},
                 {"episode_id": "ep_x", "findings": [dict(GOOD[0], evidence_ids=[lone])]},
                 {"episode_id": lone, "findings": []}]
        for c in cases:
            errors = validate_submission(c, None)
            self.assertTrue(any("UTF-8" in e for e in errors), errors)
        fine = {"episode_id": "ep_x", "findings": [dict(GOOD[0], explanation="é中 \U0001F600")]}
        self.assertEqual(validate_submission(fine, "ep_x"), [])

    def test_schema_files_are_written(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            paths = sf.write_schemas(Path(tmp))
            self.assertEqual(len(paths), len(sf.ALL))


if __name__ == "__main__":
    unittest.main()
