"""The distractor attack battery: attacks follow the published rules, are true positives on real issues, and a
matcher that is wrong in any one criterion is caught."""

import contextlib
import copy
import io
import unittest
from pathlib import Path
from unittest import mock

from auditgym import check_battery as cb
from auditgym import matcher
from auditgym.episode import load_episode
from auditgym.matcher import CRITERIA, match

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("legit_repeat", "recurring", "split_payment", "multi_invoice_payment", "underpayment",
         "overpayment_refund", "null_ref_receipt", "boundary_doc", "midnight_fx", "weekend_fx", "twin_legit_repeat")


def _episodes() -> list:
    return [load_episode(d) for split in ("train", "dev") for d in sorted((ROOT / "episodes" / split).iterdir()) if d.is_dir()]


def _real_attack(ep, issue):
    """The battery's constructor for the issue's type, applied to the records of the real issue."""
    recs = [cb._index(ep)[i] for i in issue["affected_ids"]]
    kind = issue["type"]
    if kind == "duplicate_invoice":
        return cb.duplicate_attack(ep, *recs)
    if kind == "unallocated_payment":
        return cb.unallocated_attack(ep, next(r for r in recs if "payment_id" in r), next(r for r in recs if "invoice_id" in r))
    if kind == "wrong_period":
        return cb.period_attack(ep, recs[0])
    return cb.fx_attack(ep, recs[0], cb.policy_base(ep, recs[0]))


def _lines(ep) -> list:
    return cb.reward_battery(ep) if ep.truth["issues"] else cb.clean_battery(ep)


def _ignoring(criterion):
    """A matcher that does not check one criterion."""
    real = matcher.failed_criteria
    return lambda nf, ni: [c for c in real(nf, ni) if c != criterion]


class DistractorAttacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eps = _episodes()
        cls.clean = next(e for e in cls.eps if not e.truth["issues"] and e.provenance["distractors"])
        cls.dirty = next(e for e in cls.eps if e.truth["issues"] and e.provenance["distractors"])

    def test_every_present_kind_has_an_attack(self):
        for ep in self.eps:
            present = {d["kind"] for d in ep.provenance["distractors"]}
            attacks = cb.distractor_attacks(ep)
            for kind in present & set(KINDS):
                self.assertTrue(attacks.get(kind), f"{ep.episode_id}: no attack for {kind}")

    def test_attacks_follow_the_published_rules(self):
        for ep in self.eps:
            idx = cb._index(ep)
            docs = {d["doc_id"] for d in ep.invoices + ep.payments}
            rows = {r["row_id"] for r in ep.ledger}
            for kind, attacks in cb.distractor_attacks(ep).items():
                for f in attacks:
                    self.assertEqual(f["currency"], ep.manifest["base_currency"])
                    self.assertTrue(all(i in idx for i in f["affected_ids"]))
                    self.assertLessEqual(len(f["evidence_ids"]), 10)
                    self.assertGreaterEqual(f["claimed_amount_minor"], 0)
                    cited = set(f["evidence_ids"])
                    self.assertGreaterEqual(len(cited & docs), len(f["affected_ids"]))
                    self.assertTrue(cited & rows, f"{ep.episode_id} {kind}: no posting row cited")
                    if f["type"] == "duplicate_invoice":
                        self.assertGreaterEqual(len(cited & rows), 2)
                    if f["type"] == "wrong_fx_rate":
                        self.assertTrue(any(c.count(":") == 2 for c in cited), "no fx record cited")

    def test_a_payment_at_the_boundary_is_the_accused_document(self):
        seen = 0
        for ep in self.eps:
            idx = cb._index(ep)
            for dis in ep.provenance["distractors"]:
                if dis["kind"] in ("boundary_doc", "midnight_fx") and any("payment_id" in idx[i] for i in dis["ids"]):
                    seen += 1
                    f = cb._attack_for(ep, dis["kind"], [idx[i] for i in dis["ids"]])
                    if f:
                        self.assertTrue(any("payment_id" in idx[i] for i in f["affected_ids"]))
        self.assertGreater(seen, 0)

    def test_every_constructor_is_a_true_positive_on_the_records_of_a_real_issue(self):
        seen = set()
        for ep in self.eps:
            for issue in ep.truth["issues"]:
                f = _real_attack(ep, issue)
                res = match([f], [issue], ep.truth.get("id_aliases"))
                self.assertEqual(res.tp, 1, f"{ep.episode_id} {issue['issue_id']} {issue['type']}: {res.unmatched}")
                seen.add(issue["type"])
        self.assertEqual(len(seen), 4)

    def test_batteries_pass_on_every_committed_episode(self):
        for ep in self.eps:
            for label, ok, detail, *_ in _lines(ep):
                self.assertTrue(ok, f"{label}: {detail}")

    def test_an_episode_without_distractors_is_skipped_not_passed(self):
        ep = copy.copy(self.clean)
        ep.provenance = dict(ep.provenance, distractors=[])
        lines = cb.clean_battery(ep)
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0]), 4)
        self.assertTrue(lines[0][1] and lines[0][3])

    def test_an_error_episode_without_distractors_has_one_skipped_distractor_line(self):
        from auditgym.config import DISTRACTORS
        from auditgym.generator import generate_episode

        config = {"errors": {"duplicate_invoice": 1, "unallocated_payment": 1, "wrong_fx_rate": 1, "wrong_period": 1},
                  "distractors": {k: 0 for k in DISTRACTORS}}
        ep = generate_episode(6602239917354212077, config).episode
        self.assertTrue(ep.truth["issues"])
        self.assertEqual(ep.provenance["distractors"], [])
        rows = [r for r in cb.reward_battery(ep) if r[0].endswith(": distractor accusations")]
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(len(rows[0]), 4)
        self.assertTrue(rows[0][1] and rows[0][3])

    def test_the_check_reports_a_skipped_clean_line_as_skipped(self):
        from auditgym import check

        ep = copy.copy(self.clean)
        ep.provenance = dict(ep.provenance, distractors=[])
        rep = check.Report()
        with mock.patch.object(check, "reward_battery", return_value=[]), contextlib.redirect_stdout(io.StringIO()):
            check.live_reward_properties(rep, ep)
        rows = [r for r in rep.sections["C_reward"] if r["check"].endswith(": distractor accusations")]
        self.assertEqual(len(rows), 1, rep.sections["C_reward"])
        self.assertIs(rows[0].get("skipped"), True)
        self.assertTrue(rows[0]["ok"])

    def test_a_matcher_ignoring_one_criterion_fails_both_batteries(self):
        for criterion in CRITERIA:
            with mock.patch.object(matcher, "failed_criteria", _ignoring(criterion)):
                for ep in (self.clean, self.dirty):
                    self.assertTrue(any(not l[1] for l in _lines(ep) if "accusation" in l[0]), f"{criterion} on {ep.episode_id}")

    def test_a_matcher_accepting_distractor_records_fails_instead_of_skipping(self):
        idx = cb._index(self.dirty)
        distractor_ids = {cb._public_id(idx[i]) for d in self.dirty.provenance["distractors"] for i in d["ids"]}
        real = matcher.failed_criteria
        accept = lambda nf, ni: [] if set(nf.ids) <= distractor_ids else real(nf, ni)
        with mock.patch.object(matcher, "failed_criteria", accept):
            lines = [l for l in cb.reward_battery(self.dirty) if "accusation" in l[0]]
        self.assertTrue(lines)
        self.assertTrue(any(not l[1] and len(l) == 3 for l in lines))


class CheckMainEntry(unittest.TestCase):
    """python -m auditgym.check runs the same pre-flight and secret handling as the auditgym check command."""

    def _seeds(self, d):
        f = Path(d) / "seeds.json"
        f.write_text('{"split": "t", "episodes": [{"name": "a", "seed": 6602239917354212077, "config": {}}]}', encoding="utf-8")
        return str(f)

    def test_strict_mode_without_an_agent_user_is_one_error_line_and_no_output_directory(self):
        import io
        import os
        import tempfile
        from contextlib import redirect_stderr

        from auditgym import check, protocol

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            err = io.StringIO()
            refuse = mock.Mock(side_effect=protocol.AgentUserRequired("AUDITGYM_REQUIRE_AGENT_USER=1 but no agent user"))
            with (mock.patch.dict(os.environ, {"AUDITGYM_REQUIRE_AGENT_USER": "1"}),
                  mock.patch.object(protocol, "AgentProcess", refuse),
                  mock.patch.object(check, "generate_episode") as gen,
                  redirect_stderr(err)):
                rc = check.main(["--seeds-file", self._seeds(d), "--no-secret", "--out", str(out)])
            self.assertEqual(rc, 2)
            lines = [ln for ln in err.getvalue().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, lines)
            self.assertTrue(lines[0].startswith("error: AUDITGYM_REQUIRE_AGENT_USER=1"), lines)
            gen.assert_not_called()
            self.assertFalse(out.exists())

    def test_the_secret_leaves_the_environment_but_the_check_still_uses_it(self):
        import os
        import tempfile

        from auditgym import check

        class Stop(Exception):
            pass

        seen = {}
        real = check.generate_episode

        def spy(seed, cfg, secret=None):
            seen["secret"], seen["in_env"] = secret, "AUDITGYM_TEST_SECRET" in os.environ
            return real(seed, cfg, secret=secret)

        with (tempfile.TemporaryDirectory() as d,
              mock.patch.dict(os.environ, {"AUDITGYM_TEST_SECRET": "host-secret-xyz"}),
              mock.patch.object(check, "generate_episode", spy),
              mock.patch.object(check, "section_hidden_like", side_effect=Stop),
              contextlib.redirect_stdout(io.StringIO())):
            with self.assertRaises(Stop):
                check.main(["--seeds-file", self._seeds(d), "--secret-env", "AUDITGYM_TEST_SECRET", "--out", str(Path(d) / "o")])
            self.assertIsNone(os.environ.get("AUDITGYM_TEST_SECRET"))
        self.assertEqual(seen, {"secret": "host-secret-xyz", "in_env": False})


class SweepCodeStamp(unittest.TestCase):
    def test_summary_files_carry_the_same_stamp_on_two_writes(self):
        import importlib.util
        import json
        import tempfile

        from auditgym.check import code_stamp, stamp_line

        spec = importlib.util.spec_from_file_location("organizer_sweep_under_test", ROOT / "tools" / "organizer_sweep.py")
        sweep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sweep)
        texts = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                sweep._write_summaries(Path(tmp), [], [], [], [], 50)
                texts.append(((Path(tmp) / "summary.json").read_text(encoding="utf-8"),
                              (Path(tmp) / "summary.md").read_text(encoding="utf-8")))
        self.assertEqual(texts[0], texts[1])
        stamp = json.loads(texts[0][0])["code"]
        self.assertEqual(stamp, code_stamp())
        self.assertIn("- code: " + stamp_line(stamp), texts[0][1])
        self.assertEqual(set(stamp), {"code_sha256", "code_files", "python", "platform"})


if __name__ == "__main__":
    unittest.main()
