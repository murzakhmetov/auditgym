"""Published JSON schemas match the committed data, observations and the submission validator."""

import unittest
from pathlib import Path

import json

from auditgym import FINDING_TYPES, protocol, schemas
from auditgym import schema_files as sf
from auditgym.episode import load_episode
from auditgym.runner import run_one
from auditgym.schemas import validate_submission
from tests.test_matcher import GOOD

ROOT = Path(__file__).resolve().parent.parent
EPISODES = sorted(p for split in ("train", "dev") for p in (ROOT / "episodes" / split).glob("*") if (p / "public").exists())


ASTRAL = chr(0x1F600)  # 12 bytes as a JSON surrogate-pair escape: the worst case for ensure_ascii=True
WORST_WHITESPACE = chr(0x3000)  # accepted around the currency code; 6 bytes escaped


def max_valid_finding():
    """The longest valid finding the child can send, measured in bytes of its ASCII-escaped line."""
    cur = WORST_WHITESPACE * (schemas.MAX_CURRENCY_CHARS - 3) + "USD"
    return {"type": max(FINDING_TYPES, key=len), "affected_ids": [ASTRAL * schemas.MAX_ID_CHARS] * schemas.MAX_AFFECTED_IDS,
            "claimed_amount_minor": schemas.MAX_AMOUNT_MINOR, "currency": cur,
            "evidence_ids": [ASTRAL * schemas.MAX_ID_CHARS] * schemas.MAX_EVIDENCE_IDS,
            "explanation": ASTRAL * schemas.MAX_EXPLANATION_CHARS}


def max_submit_action(episode_id):
    return {"action": "submit", "findings": {"episode_id": episode_id,
                                             "findings": [max_valid_finding() for _ in range(schemas.MAX_FINDINGS)]}}


def max_submit_line(episode_id):
    """The submit line exactly as auditgym/agent.py writes it (newline included)."""
    return json.dumps({"type": "action", "action": max_submit_action(episode_id)}, ensure_ascii=True) + "\n"


class SchemaTests(unittest.TestCase):
    def test_every_valid_submission_fits_the_protocol_line(self):
        ids = {load_episode(d).episode_id for d in EPISODES}
        longest = max(ids, key=len)
        self.assertTrue(longest.startswith("ep_") and len(longest) == 19, longest)
        action = max_submit_action(longest)
        self.assertEqual(validate_submission(action["findings"], longest), [])
        self.assertEqual(sf.validate(action["findings"], sf.SUBMISSION_JSON_SCHEMA), [])
        size = len(max_submit_line(longest).encode("ascii")) - 1  # newline is excluded from MAX_LINE
        # forms that are valid but longer: an integral float amount (coerced to int) and the {"args": ...} alias wrapper
        float_extra = len(repr(float(schemas.MAX_AMOUNT_MINOR))) - len(str(schemas.MAX_AMOUNT_MINOR))
        alias_extra = 10  # measured: {"action":"submit","args":{"findings":...}} against the plain form
        bound = size + float_extra * schemas.MAX_FINDINGS + alias_extra
        self.assertLess(bound, protocol.MAX_LINE)
        self.assertLess(bound, 830000)  # the bound: 828,755 bytes as agent.py serializes it
        # the limit is what keeps it small: 8 characters are valid, 9 are not, in both validators
        for cur, ok in ((WORST_WHITESPACE * 5 + "USD", True), (WORST_WHITESPACE * 6 + "USD", False), (" " * 1000 + "USD", False)):
            case = json.loads(json.dumps(action["findings"]))
            case["findings"][0]["currency"] = cur
            self.assertEqual(validate_submission(case, longest) == [], ok, len(cur))
            self.assertEqual(sf.validate(case, sf.SUBMISSION_JSON_SCHEMA) == [], ok, len(cur))
        self.assertEqual(validate_submission(dict(action["findings"], findings=[dict(action["findings"]["findings"][0], currency=" USD ")]), longest), [])

    def test_published_currency_limit_matches_validator_and_schema(self):
        from auditgym.task import build_task

        item = sf.SUBMISSION_JSON_SCHEMA["properties"]["findings"]["items"]["properties"]["currency"]
        self.assertEqual(item["maxLength"], schemas.MAX_CURRENCY_CHARS)
        task = build_task(load_episode(EPISODES[0]), 40, "tools")
        self.assertEqual(task["limits"]["max_currency_chars"], schemas.MAX_CURRENCY_CHARS)

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
