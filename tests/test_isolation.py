"""Process isolation: the policy runs in a child process that sees observations only."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auditgym import protocol
from auditgym.__main__ import main as cli_main
from auditgym.env import AuditEnv
from auditgym.runner import run_one
from tests.test_env import episode
from tests.test_schemas import max_submit_action, max_submit_line, max_valid_finding

ROOT = Path(__file__).resolve().parent.parent


class IsolationTests(unittest.TestCase):
    def test_child_gets_no_seed_secret_or_paths(self):
        env = protocol._child_env()
        self.assertNotIn("AUDITGYM_SECRET", env)
        self.assertEqual(set(env) - {"PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC"},
                         {"PYTHONPATH", "PYTHONHASHSEED", "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE"})
        captured = {}
        real_popen = protocol.subprocess.Popen

        def spy(cmd, **kw):
            captured["cmd"], captured["cwd"] = cmd, kw.get("cwd")
            return real_popen(cmd, **kw)

        with mock.patch.object(protocol.subprocess, "Popen", side_effect=spy):
            agent = protocol.AgentProcess("auditor")
            agent.close()
        joined = " ".join(captured["cmd"])
        self.assertNotIn("seed", joined.replace("--policy-seed", ""))
        self.assertNotIn("episodes", joined)
        self.assertNotIn("grader", joined)
        self.assertIn("auditgym_agent_", captured["cwd"])

    def test_isolated_run_matches_in_process_run(self):
        ep = episode()
        t1, g1 = run_one(ep, "auditor", isolated=True)
        t2, g2 = run_one(ep, "auditor", isolated=False)
        self.assertEqual(json.dumps(t1, sort_keys=True), json.dumps(t2, sort_keys=True))
        self.assertEqual(g1["reward"], g2["reward"])
        self.assertTrue(g1["isolated"])
        self.assertIsNone(g1["agent_error"])

    def test_oracle_never_produces_a_trajectory_and_is_refused_in_the_child(self):
        traj, g = run_one(episode(), "oracle")
        self.assertIsNone(traj)
        self.assertEqual(g["reward"], 1.0)
        env = AuditEnv(mode="eval")
        res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, "oracle")
        self.assertEqual(res["grade"]["status"], "agent_exited")
        self.assertIn("exited with code 2", res["agent_error"])

    def test_external_policy_adapter(self):
        _, g = run_one(episode(), "examples.custom_policy:FirstPagePolicy", isolated=True)
        self.assertIsNone(g["agent_error"])
        self.assertEqual(g["status"], "submitted")
        self.assertEqual(g["inspection_steps"], 1)

    def test_unknown_policy_is_an_error(self):
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            code = cli_main(["run", "--episodes", str(ROOT / "episodes" / "train" / "t01_clean_small"),
                             "--policies", "nosuchpolicy", "--out", tmp])
            self.assertEqual(code, 2)
            code = cli_main(["run", "--episodes", str(ROOT / "episodes" / "train" / "t01_clean_small"),
                             "--policies", "nosuch.module:Policy", "--out", tmp])
            self.assertEqual(code, 2)

    def test_agent_that_stalls_is_truncated(self):
        env = AuditEnv(mode="eval", time_limit_s=1.5)
        with mock.patch.object(protocol, "AgentProcess", _StallingAgent):
            res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, "auditor")
        self.assertEqual(res["grade"]["status"], "time_limit")
        self.assertEqual(res["grade"]["n_findings"], 0)

    def test_agent_that_exits_is_an_agent_error(self):
        env = AuditEnv(mode="eval")
        with mock.patch.object(protocol, "AgentProcess", _ExitingAgent):
            res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, "auditor")
        self.assertEqual(res["grade"]["status"], "agent_exited")
        self.assertIn("code 1", res["agent_error"])

    def test_malformed_and_null_actions_are_bounded_errors(self):
        env = AuditEnv(mode="eval")
        records = []
        with mock.patch.object(protocol, "AgentProcess", _ScriptedAgent):
            res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, "auditor", on_step=records.append)
        self.assertEqual(records[1]["observation"]["error"]["code"], "unknown_action")
        self.assertEqual(records[2]["observation"]["error"]["code"], "bad_args")
        self.assertEqual(records[2]["observation"]["remaining_steps"], 98)
        self.assertEqual(res["grade"]["status"], "submitted")
        self.assertIsNone(res["agent_error"])

    def test_parse_agent_line_never_raises(self):
        deep = '{"type":"action","action":' + "[" * 1000 + "]" * 1000 + "}"
        huge = '{"type":"action","action":' + "9" * 5000 + "}"
        surrogate = '{"type":"action","action":{"action":"submit","findings":{"episode_id":"x","findings":[{"explanation":"\\ud800"}]}}}'
        cases = {
            deep: "malformed", huge: "malformed", surrogate: "malformed", "not json": "malformed",
            '{"type":"hello"}': "malformed", '{"type":"action"}': "malformed", "[1,2]": "malformed",
            '{"type":"action","action":{"action":"calculator","expression":NaN}}': "malformed",
            '{"type":"action","action":Infinity}': "malformed",
            "x" * (protocol.MAX_LINE + 1): "malformed",
        }
        for line, kind in cases.items():
            self.assertEqual(protocol.parse_agent_line(line)[0], kind, line[:40])
        self.assertEqual(protocol.parse_agent_line('{"type":"action","action":null}'), ("action", None))
        self.assertEqual(protocol.parse_agent_line(None), ("eof", None))


SUBMIT_POLICY = """
from examples.hostile.policies import _Base


def finding(**kw):
    f = {"type": "duplicate_invoice", "affected_ids": ["x"], "claimed_amount_minor": 1, "currency": "USD",
         "evidence_ids": [], "explanation": "e"}
    f.update(kw)
    return f


class _Submit(_Base):
    def findings(self):
        return [finding()]

    def step(self, observation):
        return {"action": "submit", "findings": {"episode_id": self.episode_id, "findings": self.findings()}}


class Digits50(_Submit):
    def findings(self):
        return [finding(claimed_amount_minor=10 ** 49)]


class NotANumber(_Submit):
    def findings(self):
        return [finding(claimed_amount_minor=float("nan"))]


class Many(_Submit):
    def findings(self):
        return [finding()] * 20000


class LoneSurrogate(_Submit):
    def findings(self):
        return [finding(explanation="x" + chr(0xD800) + "y")]


class LateKey(_Base):
    def step(self, observation):
        return {"findings": {"episode_id": self.episode_id, "findings": [finding(claimed_amount_minor=10 ** 49)]},
                "action": "submit"}


class Maximal(_Submit):
    def findings(self):
        astral, ws = chr(0x1F600), chr(0x3000)  # the child cannot import tests: this mirrors max_valid_finding()
        return [finding(type="unallocated_payment", affected_ids=[astral * 64] * 10, evidence_ids=[astral * 64] * 10,
                        claimed_amount_minor=10 ** 15, currency=ws * 5 + "USD", explanation=astral * 1000)
                for _ in range(30)]
"""


class MalformedSubmit(unittest.TestCase):
    """A structurally invalid submit ends the episode with reward -1 in process and in the child alike."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        os.chmod(cls._tmp.name, 0o755)  # traversable, so the agent user can reach its policy
        Path(cls._tmp.name, "submit_variants_pol.py").write_text(SUBMIT_POLICY, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_both(self, cls_name):
        ep = episode()
        name = f"submit_variants_pol:{cls_name}"
        iso = run_one(ep, name, isolated=True, policy_path=self._tmp.name)
        proc = run_one(ep, name, isolated=False, policy_path=self._tmp.name)
        return ep, iso, proc

    def test_structurally_invalid_submits_grade_alike(self):
        for cls_name in ("Digits50", "NotANumber", "Many", "LoneSurrogate"):
            with self.subTest(cls_name):
                ep, (traj, g_iso), (_t, g_proc) = self.run_both(cls_name)
                self.assertIsNone(g_iso["agent_error"])
                self.assertEqual((g_iso["status"], g_iso["reward"]), ("invalid_submission", -1.0))
                self.assertEqual((g_proc["status"], g_proc["reward"]), ("invalid_submission", -1.0))
                last = traj[-1]
                self.assertEqual(last["observation"]["error"]["code"], "invalid_submission")
                self.assertTrue(last["terminated"])
                self.assertEqual(last["action"]["action"], "submit")
                self.assertIn("invalid_action", last["action"])
                self.assertLessEqual(len(last["action"]["invalid_action"]), protocol.ECHO_CHARS)

    def test_recorded_trajectory_replays_without_problems(self):
        from auditgym.check_battery import replay_run

        for cls_name in ("Digits50", "NotANumber", "Many", "LoneSurrogate"):
            with self.subTest(cls_name):
                ep, (traj, _g), _ = self.run_both(cls_name)
                self.assertEqual(replay_run(traj, ep), [])

    def test_a_submit_whose_action_key_is_not_first_stays_an_unknown_action(self):
        ep = episode()
        traj, g = run_one(ep, "submit_variants_pol:LateKey", isolated=True, policy_path=self._tmp.name)
        self.assertEqual(traj[1]["observation"]["error"]["code"], "unknown_action")
        self.assertEqual(set(traj[1]["action"]), {"invalid_action"})
        self.assertNotEqual(g["status"], "invalid_submission")

    def test_maximal_valid_submission_is_an_action_and_grades_normally(self):
        ep = episode()
        traj, g_iso = run_one(ep, "submit_variants_pol:Maximal", isolated=True, policy_path=self._tmp.name)
        _t, g_proc = run_one(ep, "submit_variants_pol:Maximal", isolated=False, policy_path=self._tmp.name)
        self.assertEqual((g_iso["status"], g_iso["valid"]), ("submitted", True))
        self.assertEqual((g_iso["status"], g_iso["reward"]), (g_proc["status"], g_proc["reward"]))
        self.assertNotIn("invalid_action", traj[-1]["action"])
        self.assertEqual(len(traj[-1]["action"]["findings"]["findings"]), 30)
        self.assertEqual(traj[-1]["action"]["findings"]["findings"][0], max_valid_finding())
        action = max_submit_action(ep.episode_id)
        line = max_submit_line(ep.episode_id)
        self.assertLess(len(line) - 1, protocol.MAX_LINE)
        self.assertEqual(protocol.parse_agent_line(line), ("action", action))

    def test_submit_start_detection_is_anchored_and_whitespace_tolerant(self):
        yes = ['{"type": "action", "action": {"action": "submit", "findings": NaN}}',
               '  {"type":"action","action":{"action":"submit",',
               '{ "type" : "action" , "action" : { "action" : "submit" }',
               '{"action": "submit", "findings": 1e999999']
        no = ['{"type": "action", "action": {"findings": NaN, "action": "submit"}}',
              '{"type": "action", "action": {"action": "list_records", "note": "submit"}',
              '{"type": "action", "action": {"action": "submitx"}', 'x{"action": "submit"}', "", None, 5]
        for line in yes:
            self.assertTrue(protocol.looks_like_submit(line), line)
        for line in no:
            self.assertFalse(protocol.looks_like_submit(line), line)


class _FakeProc:
    def wait(self, timeout=None):
        return 1


class _StallingAgent:
    def __init__(self, *a, **k):
        self.proc = _FakeProc()

    def send(self, m):
        return True

    def receive(self, timeout_s):
        import time
        time.sleep(min(timeout_s, 2.0))
        return "timeout", None

    def stderr_tail(self):
        return ""

    def close(self):
        pass


class _ExitingAgent(_StallingAgent):
    def receive(self, timeout_s):
        return "eof", None

    def stderr_tail(self):
        return "Traceback ...\nRuntimeError: boom\n"


class _ScriptedAgent(_StallingAgent):
    def __init__(self, *a, **k):
        super().__init__()
        self.n = 0

    def receive(self, timeout_s):
        self.n += 1
        if self.n == 1:
            return "malformed", None
        if self.n == 2:
            return "action", None
        return "action", {"action": "submit", "findings": {"episode_id": episode().episode_id, "findings": []}}


if __name__ == "__main__":
    unittest.main()
