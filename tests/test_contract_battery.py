"""The in-process contract battery passes on a committed episode and fails on a broken environment."""

import time
import unittest
from unittest import mock

from auditgym import env as env_module
from auditgym.contract_battery import contract_battery
from auditgym.episode import load_episode
from auditgym.policies import SilentPolicy, make_policy
from auditgym.splits import EPISODES_DIR

EP_DIR = EPISODES_DIR / "dev" / "d03_duplicates_gbp"


class ContractBattery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ep = load_episode(EP_DIR)

    def test_passes_on_a_committed_episode_and_is_fast(self):
        t0 = time.monotonic()
        results = contract_battery(self.ep)
        self.assertLess(time.monotonic() - t0, 3.0)
        self.assertGreaterEqual(len(results), 18)
        self.assertEqual([r for r in results if not r[1]], [])
        self.assertEqual(len({label for label, _ok, _d in results}), len(results))

    def test_an_episode_with_an_empty_table_passes_every_check(self):
        from auditgym.generator import generate_episode

        ep = generate_episode(6602239917354212077, {"foreign_currencies": []}).episode
        self.assertEqual(ep.table("fx"), [])
        results = contract_battery(ep)
        self.assertEqual(len(results), 20)
        self.assertEqual([r for r in results if not r[1]], [])

    def test_an_empty_sample_of_observations_does_not_validate_vacuously(self):
        with mock.patch("auditgym.contract_battery._observations", return_value=[]):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("sampled observations" in label for label in failed), failed)

    def test_a_broken_page_size_fails_a_named_check(self):
        def greedy(self, action):
            rows = self._episode.table(action["table"])
            return {"table": action["table"], "rows": rows, "next_cursor": None, "total": len(rows)}, None

        with mock.patch.object(env_module.AuditEnv, "_list_records", greedy):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("page" in label for label in failed), failed)

    def test_an_environment_that_leaks_reward_fails(self):
        real = env_module.AuditEnv._reward_out
        with mock.patch.object(env_module.AuditEnv, "_reward_out", lambda self: self._final["reward"] if self._done else real(self)):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("eval mode" in label for label in failed), failed)

    def test_an_environment_that_raises_fails_instead_of_crashing(self):
        with mock.patch.object(env_module.AuditEnv, "step", side_effect=TypeError("boom")):
            results = contract_battery(self.ep)
        failed = [label for label, ok, _d in results if not ok]
        self.assertTrue(any("ran to the end" in label for label in failed), failed)

    def test_a_cursor_that_ignores_its_value_fails(self):
        state = {"n": 0}
        real = env_module.AuditEnv._list_records

        def drifting(self, action):
            if action.get("cursor") is not None:
                state["n"] += 1
                action = {**action, "cursor": str(state["n"] * 50)}
            return real(self, action)

        with mock.patch.object(env_module.AuditEnv, "_list_records", drifting):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("cursor is stable" in label for label in failed), failed)

    def test_pages_with_duplicates_and_gaps_fail(self):
        real = env_module.AuditEnv._list_records

        def shuffled(self, action):
            res, err = real(self, action)
            if res and res["rows"] and action.get("cursor") is not None:
                res = {**res, "rows": res["rows"][:-1] + res["rows"][:1]}
            return res, err

        with mock.patch.object(env_module.AuditEnv, "_list_records", shuffled):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("paging reaches every row" in label for label in failed), failed)

    def test_truncation_one_step_early_fails(self):
        real = env_module.AuditEnv.step

        def early(self, action):
            out = real(self, action)
            if self._steps == self.max_steps - 1 and not self._done:
                self._finish(submission=None, truncated=True, reason="step_limit")
            return out

        with mock.patch.object(env_module.AuditEnv, "step", early):
            failed = [label for label, ok, _d in contract_battery(self.ep) if not ok]
        self.assertTrue(any("(not before)" in label for label in failed), failed)


class SilentBaseline(unittest.TestCase):
    def test_submits_nothing_on_the_first_action(self):
        policy = make_policy("silent")
        self.assertIsInstance(policy, SilentPolicy)
        action = policy.act({"manifest": {"episode_id": "ep_x"}, "task": {}, "policy": {}, "remaining_steps": 100})
        self.assertEqual(action, {"action": "submit", "findings": {"episode_id": "ep_x", "findings": []}})


class CoverageLine(unittest.TestCase):
    """The report's 'N named checks of K kinds' must not count an organizer's episode names as kinds."""

    def test_episode_names_of_the_run_are_not_kinds(self):
        from auditgym.check import check_kind

        names = ["tz_Asia/Kathmandu", "tz_UTC", "large_twelve"]
        labels = [f"{n} verifies (12 issues, 1 attempt(s))" for n in names]
        labels += [f"{n}: same seed and config regenerate identical records and answer key" for n in names]
        self.assertEqual(len({check_kind(x, names) for x in labels}), 2)
        self.assertEqual(len({check_kind(x) for x in labels}), 6)  # without the names every episode looks new

    def test_public_names_and_ids_are_generalised(self):
        from auditgym.check import check_kind

        self.assertEqual(check_kind("ep_99b4722e2dd40466: an unknown ID gives a bounded error"),
                         check_kind("ep_0123456789abcdef: an unknown ID gives a bounded error"))
        self.assertEqual(check_kind("h02_dupes {'permute_seed': 11}: oracle answer and reward preserved"),
                         check_kind("h13_fx {'remap_seed': 3}: oracle answer and reward preserved"))
        self.assertNotEqual(check_kind("x: amount ladder"), check_kind("x: type shotgun"))


if __name__ == "__main__":
    unittest.main()
