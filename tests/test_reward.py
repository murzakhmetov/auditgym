import unittest

from auditgym.matcher import match
from auditgym.reward import experimental_reward, terminal_reward
from tests.test_matcher import GOOD, ISSUES, finding


def reward_for(findings, issues, steps):
    r = match(findings, issues)
    return terminal_reward(r.tp, r.fp, r.fn, steps)


class RewardFormulaTests(unittest.TestCase):
    def test_formula_points(self):
        self.assertEqual(terminal_reward(2, 0, 0, 0), 1.0)
        self.assertAlmostEqual(terminal_reward(2, 0, 0, 10), 0.98, places=12)
        self.assertEqual(terminal_reward(0, 0, 2, 0), -1.0)
        self.assertEqual(terminal_reward(0, 5, 2, 99), -1.0)  # clipped
        self.assertAlmostEqual(terminal_reward(2, 1, 0, 14), 0.572, places=12)  # F1 = 0.8

    def test_reward_is_exactly_reproducible(self):
        self.assertEqual(terminal_reward(3, 1, 1, 37), terminal_reward(3, 1, 1, 37))


class RewardPropertyTests(unittest.TestCase):
    """The five properties required by the case, section 05."""

    def test_correct_answer_beats_silence_on_erroneous_ledger(self):
        self.assertGreater(reward_for(GOOD, ISSUES, 60), reward_for([], ISSUES, 0))

    def test_silence_beats_false_accusation_on_clean_ledger(self):
        silence = reward_for([], [], 40)
        accusation = reward_for(GOOD[:1], [], 0)
        self.assertGreater(silence, accusation)
        self.assertAlmostEqual(silence, 0.92, places=12)
        self.assertEqual(accusation, -1.0)

    def test_duplicates_gain_nothing(self):
        base = reward_for(GOOD, ISSUES, 20)
        with_dupes = reward_for(GOOD + GOOD + GOOD, ISSUES, 20)
        self.assertLess(with_dupes, base)

    def test_flag_everything_scores_poorly(self):
        spam = []
        types = ["duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"]
        for n in range(30):
            spam.append(finding(types[n % 4], [f"ROW-{n}"], 0, "EUR", [f"ROW-{n}"]))
        self.assertEqual(reward_for(spam, ISSUES, 5), -1.0)
        # Even when the spam happens to include the two true findings, precision collapses.
        spam_with_truth = GOOD + spam[:28]
        self.assertLess(reward_for(spam_with_truth, ISSUES, 5), -0.7)

    def test_saving_steps_only_slightly_separates_equal_answers(self):
        fast = reward_for(GOOD, ISSUES, 10)
        slow = reward_for(GOOD, ISSUES, 40)
        one_miss = reward_for(GOOD[:1], ISSUES, 10)
        self.assertGreater(fast, slow)
        self.assertAlmostEqual(fast - slow, 0.06, places=12)
        self.assertGreater(slow - one_miss, 5 * (fast - slow))


class ExperimentalRewardTests(unittest.TestCase):
    def test_exact_answer_gets_full_soft_credit(self):
        r = experimental_reward(GOOD, ISSUES, 0)
        self.assertEqual(r["soft_f1"], 1.0)
        self.assertEqual(r["reward"], 1.0)

    def test_partial_credit_is_below_full_and_spam_is_not_profitable(self):
        partial = [dict(GOOD[0], evidence_ids=["D1"]), dict(GOOD[1], claimed_amount_minor=1)]
        r_partial = experimental_reward(partial, ISSUES, 0)
        self.assertLess(r_partial["soft_f1"], 1.0)
        self.assertGreater(r_partial["soft_f1"], 0.0)
        spam = partial + [dict(GOOD[0], evidence_ids=[f"E{i}"]) for i in range(10)]
        self.assertLess(experimental_reward(spam, ISSUES, 0)["soft_f1"], r_partial["soft_f1"])

    def test_issues_sharing_type_and_ids_get_optimal_credit_in_any_order(self):
        # Two issues with the same type and affected_ids, amounts 1000 and 1002 (tolerance 2). Finding f_both
        # (1001) fits both issues; f_a (999) fits only "a". A greedy pass that serves "a" first takes f_both and
        # leaves "b" with partial credit (soft F1 0.875). The assignment is one-to-one by maximum total weight,
        # so this exact answer scores 1 whatever the finding order.
        base = dict(ISSUES[0], tolerance_minor=2)
        a = dict(base, issue_id="a", expected_amount_minor=1000)
        b = dict(base, issue_id="b", expected_amount_minor=1002)
        f_both = dict(GOOD[0], claimed_amount_minor=1001, currency=base["currency"])
        f_a = dict(GOOD[0], claimed_amount_minor=999, currency=base["currency"])
        for order in ([f_both, f_a], [f_a, f_both]):
            r = experimental_reward(order, [a, b], 0)
            self.assertEqual(r["soft_f1"], 1.0)
            self.assertEqual(r["credit_per_issue"], {"a": 1.0, "b": 1.0})


if __name__ == "__main__":
    unittest.main()
