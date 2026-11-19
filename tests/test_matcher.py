import copy
import unittest

from auditgym.matcher import match
from auditgym.schemas import validate_submission

ISSUES = [
    {
        "issue_id": "iss_01",
        "type": "duplicate_invoice",
        "affected_ids": ["INV-1", "INV-2"],
        "expected_amount_minor": 50000,
        "currency": "EUR",
        "tolerance_minor": 2,
        "evidence_sets": [["D1", "D2", "L1", "L2"], ["D1", "D2", "L3", "L4"]],
    },
    {
        "issue_id": "iss_02",
        "type": "wrong_fx_rate",
        "affected_ids": ["INV-9"],
        "expected_amount_minor": 3177,
        "currency": "EUR",
        "tolerance_minor": 2,
        "evidence_sets": [["D9", "L9", "2026-03-31:USD:EUR"]],
    },
]


def finding(type_, ids, amount, currency, evidence, explanation="x"):
    return {
        "type": type_,
        "affected_ids": ids,
        "claimed_amount_minor": amount,
        "currency": currency,
        "evidence_ids": evidence,
        "explanation": explanation,
    }


GOOD = [
    finding("duplicate_invoice", ["INV-1", "INV-2"], 50000, "EUR", ["D1", "D2", "L1", "L2"]),
    finding("wrong_fx_rate", ["INV-9"], 3177, "EUR", ["D9", "L9", "2026-03-31:USD:EUR"]),
]


class MatcherTests(unittest.TestCase):
    def test_perfect_answer(self):
        r = match(GOOD, ISSUES)
        self.assertEqual((r.tp, r.fp, r.fn), (2, 0, 0))
        self.assertEqual(r.f1, 1.0)

    def test_repeated_finding_is_false_positive(self):
        r = match(GOOD + [copy.deepcopy(GOOD[0])], ISSUES)
        self.assertEqual((r.tp, r.fp, r.fn), (2, 1, 0))
        self.assertEqual(r.unmatched[0]["reason"], "duplicate")

    def test_id_normalization_is_set_based_and_strips(self):
        f = finding("duplicate_invoice", [" INV-2", "INV-1", "INV-1 "], 50000, "eur", ["D1", "D2", "L1", "L2"])
        r = match([f], ISSUES)
        self.assertEqual(r.tp, 1)

    def test_ids_are_case_sensitive(self):
        f = finding("duplicate_invoice", ["inv-1", "INV-2"], 50000, "EUR", ["D1", "D2", "L1", "L2"])
        r = match([f], ISSUES)
        self.assertEqual(r.tp, 0)
        self.assertEqual(r.unmatched[0]["reason"], "affected_ids")

    def test_partial_ids_do_not_match(self):
        f = finding("duplicate_invoice", ["INV-2"], 50000, "EUR", ["D1", "D2", "L1", "L2"])
        self.assertEqual(match([f], ISSUES).tp, 0)

    def test_amount_tolerance_boundary(self):
        ok = finding("wrong_fx_rate", ["INV-9"], 3179, "EUR", ["D9", "L9", "2026-03-31:USD:EUR"])
        bad = finding("wrong_fx_rate", ["INV-9"], 3180, "EUR", ["D9", "L9", "2026-03-31:USD:EUR"])
        self.assertEqual(match([ok], ISSUES).tp, 1)
        r = match([bad], ISSUES)
        self.assertEqual(r.tp, 0)
        self.assertEqual(r.unmatched[0]["reason"], "amount")

    def test_wrong_currency_is_false_positive(self):
        f = finding("wrong_fx_rate", ["INV-9"], 3177, "USD", ["D9", "L9", "2026-03-31:USD:EUR"])
        r = match([f], ISSUES)
        self.assertEqual(r.tp, 0)
        self.assertEqual(r.unmatched[0]["reason"], "currency")

    def test_incomplete_evidence_is_false_positive(self):
        f = finding("wrong_fx_rate", ["INV-9"], 3177, "EUR", ["D9", "L9"])
        r = match([f], ISSUES)
        self.assertEqual(r.tp, 0)
        self.assertEqual(r.unmatched[0]["reason"], "evidence")

    def test_alternative_evidence_set_and_extra_ids(self):
        f = finding("duplicate_invoice", ["INV-1", "INV-2"], 50000, "EUR", ["D1", "D2", "L3", "L4", "NOPE-1"])
        self.assertEqual(match([f], ISSUES).tp, 1)

    def test_guessed_ids_score_nothing(self):
        guesses = [finding("wrong_fx_rate", [f"INV-{n}"], 3177, "EUR", ["D9", "L9", "2026-03-31:USD:EUR"]) for n in range(10, 20)]
        r = match(guesses, ISSUES)
        self.assertEqual((r.tp, r.fp, r.fn), (0, 10, 2))

    def test_empty_key_rules(self):
        self.assertEqual(match([], []).f1, 1.0)
        r = match(GOOD[:1], [])
        self.assertEqual(r.f1, 0.0)
        self.assertEqual(r.unmatched[0]["reason"], "no_issue_in_key")

    def test_empty_answer_on_errors(self):
        r = match([], ISSUES)
        self.assertEqual((r.tp, r.fp, r.fn, r.precision, r.recall, r.f1), (0, 0, 2, 0.0, 0.0, 0.0))

    def test_maximum_matching_beats_greedy(self):
        issues = [
            {"issue_id": "a", "type": "wrong_fx_rate", "affected_ids": ["X"], "expected_amount_minor": 100,
             "currency": "EUR", "tolerance_minor": 2, "evidence_sets": [["E"]]},
            {"issue_id": "b", "type": "wrong_fx_rate", "affected_ids": ["X"], "expected_amount_minor": 103,
             "currency": "EUR", "tolerance_minor": 2, "evidence_sets": [["E"]]},
        ]
        f1 = finding("wrong_fx_rate", ["X"], 101, "EUR", ["E"])  # valid for a and b
        f2 = finding("wrong_fx_rate", ["X"], 99, "EUR", ["E"])  # valid for a only
        r = match([f1, f2], issues)
        self.assertEqual(r.tp, 2)
        self.assertEqual(sorted(r.pairs), [(0, "b"), (1, "a")])


class SubmissionSchemaTests(unittest.TestCase):
    def sub(self, findings):
        return {"episode_id": "ep_x", "findings": findings}

    def test_valid(self):
        self.assertEqual(validate_submission(self.sub(GOOD), "ep_x"), [])
        self.assertEqual(validate_submission(self.sub([]), "ep_x"), [])

    def test_invalid_structures(self):
        bad_cases = [
            None,
            [],
            {"findings": []},
            {"episode_id": "ep_other", "findings": []},
            {"episode_id": "ep_x", "findings": {}},
            {"episode_id": "ep_x", "findings": [], "extra": 1},
            self.sub([GOOD[0]] * 31),
            self.sub([{**GOOD[0], "type": "duplicate"}]),
            self.sub([{**GOOD[0], "affected_ids": []}]),
            self.sub([{**GOOD[0], "affected_ids": "INV-1"}]),
            self.sub([{**GOOD[0], "evidence_ids": [f"E{i}" for i in range(11)]}]),
            self.sub([{**GOOD[0], "explanation": "x" * 1001}]),
            self.sub([{**GOOD[0], "claimed_amount_minor": -1}]),
            self.sub([{**GOOD[0], "claimed_amount_minor": 12.5}]),
            self.sub([{**GOOD[0], "claimed_amount_minor": True}]),
            self.sub([{**GOOD[0], "currency": "EURO"}]),
            self.sub([{k: v for k, v in GOOD[0].items() if k != "evidence_ids"}]),
            self.sub([{**GOOD[0], "confidence": 0.9}]),
            self.sub(["not an object"]),
        ]
        for case in bad_cases:
            with self.subTest(case=str(case)[:80]):
                self.assertTrue(validate_submission(case, "ep_x"))


if __name__ == "__main__":
    unittest.main()
