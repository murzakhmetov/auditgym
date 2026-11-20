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


if __name__ == "__main__":
    unittest.main()
