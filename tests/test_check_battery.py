"""The distractor attack battery: attacks follow the published rules, are true positives on real issues, and a
matcher that is wrong in any one criterion is caught."""

import copy
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

    def test_an_episode_without_distractors_passes(self):
        ep = copy.copy(self.clean)
        ep.provenance = dict(ep.provenance, distractors=[])
        lines = cb.clean_battery(ep)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0][1])
        self.assertEqual(len(lines[0]), 3)

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


if __name__ == "__main__":
    unittest.main()
