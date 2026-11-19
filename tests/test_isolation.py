"""Process isolation: the policy runs in a child process that sees observations only."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auditgym import protocol
from auditgym.__main__ import main as cli_main
from auditgym.env import AuditEnv
from auditgym.runner import run_one
from tests.test_env import episode

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
