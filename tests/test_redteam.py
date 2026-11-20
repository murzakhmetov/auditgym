"""Hostile policies against the host: bounded memory, no desynchronisation, no hang, tree cleanup,
code integrity, crash grading. Probes are sized in megabytes so that unfixed code fails an assertion
instead of exhausting the machine. Timing probes with wide margins only; the strict ones live in
`python -m auditgym.redteam`.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

from auditgym import protocol
from tests import same_user_start, same_user_stop
from auditgym.env import AuditEnv
from auditgym.redteam import run_hostile as _run_hostile, write_policy  # noqa: F401
from tests.test_env import episode

ROOT = Path(__file__).resolve().parent.parent


def setUpModule():
    same_user_start(__name__)


def tearDownModule():
    same_user_stop(__name__)
PEAK_LIMIT = 8 * 1024 * 1024


def run_hostile(base, time_limit_s=20.0, ep=None, mode="eval", trace=False, **attrs):
    return _run_hostile(base, time_limit_s, ep or episode(), mode, trace, **attrs)


class BoundedChannel(unittest.TestCase):
    def test_unterminated_32mb_line_is_bounded(self):
        res, rec, peak, _ = run_hostile("NoNewlineFlood", trace=True, MB=32)
        self.assertLess(peak, PEAK_LIMIT, f"host peak {peak} bytes")
        self.assertEqual(rec[1]["observation"]["error"]["code"], "unknown_action")
        self.assertEqual(set(rec[1]["action"]), {"invalid_action"})
        self.assertEqual(rec[1]["action"]["invalid_action"], "x" * protocol.ECHO_CHARS)
        self.assertEqual(res["grade"]["status"], "submitted")
        self.assertTrue(res["grade"]["valid"])
        self.assertIsNone(res["agent_error"])

    def test_stderr_flood_is_bounded(self):
        res, rec, peak, tail = run_hostile("StderrFlood", trace=True, MB=16)
        self.assertLess(peak, PEAK_LIMIT, f"host peak {peak} bytes")
        self.assertLessEqual(len(tail), protocol.STDERR_TAIL)
        self.assertEqual(res["grade"]["status"], "submitted")
        self.assertIsNone(res["agent_error"])

    def test_stray_print_cannot_desynchronise_the_protocol(self):
        res, rec, _, tail = run_hostile("StrayPrint")
        self.assertEqual(rec[1]["action"]["action"], "list_records")
        self.assertEqual(len(rec[1]["observation"]["result"]["rows"]), 1)
        self.assertEqual(rec[2]["action"]["action"], "submit")
        self.assertEqual([r["observation"]["error"] and r["observation"]["error"]["code"] for r in rec[1:]], [None, None])
        self.assertIn("debug: thinking about", tail)
        self.assertEqual(res["grade"]["status"], "submitted")

    def test_garbage_line_costs_one_step_and_is_echoed_bounded(self):
        res, rec, _, _ = run_hostile("GarbageFirst")
        self.assertEqual(rec[1]["action"], {"invalid_action": "this is not json"})
        self.assertEqual(rec[1]["observation"]["error"]["code"], "unknown_action")
        self.assertEqual(rec[1]["observation"]["remaining_steps"], 99)
        self.assertEqual(res["grade"]["status"], "submitted")

class CrashGrading(unittest.TestCase):
    def check_invalid(self, res):
        g = res["grade"]
        self.assertEqual(g["status"], "agent_exited")
        self.assertFalse(g["valid"])
        self.assertEqual(g["reward"], -1.0)
        self.assertFalse(g["closed"])
        self.assertIsNotNone(res["agent_error"])

    def test_crash_on_a_clean_ledger_is_not_an_empty_answer(self):
        from auditgym.generator import generate_episode

        clean = generate_episode(7, {"size": "small", "errors": {}}).episode
        self.assertEqual(clean.truth["issues"], [])
        for base in ("Crash", "ExitNow"):
            res, _, _, _ = run_hostile(base, ep=clean)
            self.check_invalid(res)
        env = AuditEnv(mode="eval")
        res = protocol.run_episode_isolated(env, {"config": {"episode": clean}}, "nosuchmodule_xyz:Policy")
        self.check_invalid(res)
        self.assertIn("cannot load policy", res["agent_error"])

    def test_time_limit_and_step_limit_stay_empty_answers(self):
        env = AuditEnv(mode="eval", max_steps=1)
        env.reset(config={"episode": episode()})
        env.step({"action": "calculator", "expression": "1+1"})
        g = env.grader_report()
        self.assertEqual((g["status"], g["valid"], g["n_findings"]), ("step_limit", True, 0))


def same_level():
    """Windows: the policy child keeps the host's integrity level, so it can still write the grader files and the
    digest check (not the Low-integrity write refusal) is what these tests measure. The refusal itself is
    asserted in tests/test_windows_hardening.py. Elsewhere a no-op."""
    return mock.patch.object(protocol, "LOWER_INTEGRITY", False)


class CodeIntegrity(unittest.TestCase):
    def test_policy_that_edits_grader_code_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for d in ("auditgym", "configs", "schemas", "examples"):
                shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            target = str(root / "auditgym" / "reward.py")
            self.assertTrue(os.path.exists(target))
            with mock.patch.object(protocol, "PROJECT_ROOT", root), same_level():
                res, _, _, _ = run_hostile("CodeEditor", TARGET=target)
            self.assertIn("reward.py", res["agent_error"])
            self.assertIn("grader code changed", res["agent_error"])
            self.assertEqual(res["grade"]["reward"], -1.0)
            self.assertFalse(res["grade"]["valid"])
            self.assertEqual(res["grade"]["status"], "agent_error")

    def test_digest_covers_code_configs_and_schemas(self):
        d = protocol.code_digest()
        self.assertIn("auditgym/protocol.py", d)
        self.assertIn("configs/splits.json", d)
        self.assertTrue(any(k.startswith("schemas/") for k in d))
        self.assertEqual(protocol.changed_files(d, dict(d, **{"auditgym/new.py": "x"})), ["auditgym/new.py"])

    def test_digest_covers_bytecode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for d in ("auditgym", "configs", "schemas"):
                shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (root / "auditgym" / "__pycache__").mkdir()
            pyc = root / "auditgym" / "__pycache__" / "reward.cpython-311.pyc"
            pyc.write_bytes(b"one")
            before = protocol.code_digest(root)
            self.assertIn("auditgym/__pycache__/reward.cpython-311.pyc", before)
            pyc.write_bytes(b"two")
            self.assertEqual(protocol.changed_files(before, protocol.code_digest(root)),
                             ["auditgym/__pycache__/reward.cpython-311.pyc"])

    def test_planted_pyc_fails_the_run_and_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for d in ("auditgym", "configs", "schemas", "examples"):
                shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            target = str(root / "auditgym" / "reward.py")
            with mock.patch.object(protocol, "PROJECT_ROOT", root), same_level():
                res, _, _, _ = run_hostile("PycPlanter", TARGET=target)
            self.assertIn("grader code changed", res["agent_error"] or "")
            self.assertIn("__pycache__", res["agent_error"])
            self.assertEqual(res["grade"]["reward"], -1.0)
            self.assertEqual(res["grade"]["status"], "agent_error")
            cache = root / "auditgym" / "__pycache__"
            self.assertEqual(list(cache.glob("reward*.pyc")) if cache.exists() else [], [])

    def test_untouched_run_has_no_integrity_error(self):
        res, _, _, _ = run_hostile("StrayPrint")
        self.assertIsNone(res["agent_error"])


class ChildImportPath(unittest.TestCase):
    def test_child_cannot_import_grader_side_modules_or_see_the_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "hostile_policy.py").write_text(
                "import os\n"
                "from examples.hostile.policies import _Base, _submit\n"
                "class P(_Base):\n"
                "    def step(self, observation):\n"
                f"        root = {str(ROOT)!r}\n"
                "        if root.lower() in os.environ.get('PYTHONPATH', '').lower():\n"
                "            raise RuntimeError('repo root is on the child import path')\n"
                "        import importlib\n"
                "        for name in ('auditgym.grader', 'auditgym.policies.oracle', 'auditgym.generator',\n"
                "                     'auditgym.episode', 'auditgym.env', 'auditgym.verify', 'auditgym.reward'):\n"
                "            try:\n"
                "                importlib.import_module(name)\n"
                "            except ImportError:\n"
                "                continue\n"
                "            raise RuntimeError('importable in the child: ' + name)\n"
                "        return _submit(self.episode_id)\n", encoding="utf-8")
            env = AuditEnv(mode="eval")
            res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, "hostile_policy:P", policy_path=tmp)
        self.assertIsNone(res["agent_error"], res["agent_error"])
        self.assertEqual(res["grade"]["status"], "submitted")

    def test_in_repo_policy_outside_examples_still_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            for d in ("auditgym", "configs", "schemas", "examples"):
                shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (root / "mypol_pkg").mkdir()
            (root / "mypol_pkg" / "__init__.py").write_text("", encoding="utf-8")
            shutil.copy(ROOT / "examples" / "custom_policy.py", root / "mypol_pkg" / "inner.py")
            shutil.copy(ROOT / "examples" / "custom_policy.py", root / "mypol_top.py")
            with mock.patch.object(protocol, "PROJECT_ROOT", root):
                for name in ("mypol_top:FirstPagePolicy", "mypol_pkg.inner:FirstPagePolicy"):
                    env = AuditEnv(mode="eval")
                    res = protocol.run_episode_isolated(env, {"config": {"episode": episode()}}, name)
                    self.assertIsNone(res["agent_error"], (name, res["agent_error"]))
                    self.assertEqual(res["grade"]["status"], "submitted")

    def test_staged_tree_has_only_agent_side_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            protocol.stage_agent_code(Path(tmp))
            names = {p.name for p in Path(tmp, "auditgym").rglob("*.py")}
        for banned in ("grader.py", "oracle.py", "generator.py", "episode.py", "env.py", "reward.py", "matcher.py",
                       "verify.py", "inject.py", "history.py", "runner.py", "protocol.py"):
            self.assertNotIn(banned, names)
        self.assertIn("auditor.py", names)

    def test_staged_tree_leaks_no_repository_path_even_with_host_bytecode(self):
        import compileall

        with tempfile.TemporaryDirectory() as tmp:
            host = Path(tmp) / "host"
            shutil.copytree(ROOT / "auditgym", host / "auditgym", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "examples", host / "examples", ignore=shutil.ignore_patterns("__pycache__"))
            with mock.patch.object(sys, "dont_write_bytecode", False):
                compileall.compile_dir(str(host), quiet=2, force=True)
            self.assertTrue(list(host.rglob("*.pyc")))
            stage = Path(tmp) / "stage"
            with mock.patch.object(protocol, "PROJECT_ROOT", host):
                protocol.stage_agent_code(stage, "examples.custom_policy:FirstPagePolicy")
            self.assertEqual(list(stage.rglob("*.pyc")), [])
            for path in stage.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    self.assertNotIn(str(host).encode(), data, path.name)
                    self.assertNotIn(str(ROOT).encode(), data, path.name)

    def test_non_submit_action_over_2kb_is_malformed(self):
        line = json.dumps({"type": "action", "action": {"action": "get_record", "pad": "{}" * 1500}})
        self.assertEqual(protocol.parse_agent_line(line)[0], "malformed")
        ok = json.dumps({"type": "action", "action": {"action": "get_record", "table": "invoices", "id": "x"}})
        self.assertEqual(protocol.parse_agent_line(ok)[0], "action")


class ParserBounds(unittest.TestCase):
    """Same answers with PYTHONINTMAXSTRDIGITS=0 (the integer-digit limit off). Tested on Python 3.11 only."""

    CASES = {
        "deep_1000": '{"type":"action","action":' + "[" * 1000 + "]" * 1000 + "}",
        "deep_33": '{"type":"action","action":' + "[" * 33 + "]" * 33 + "}",
        "deep_10": '{"type":"action","action":' + "[" * 10 + "]" * 10 + "}",
        "huge_int": '{"type":"action","action":' + "9" * 5000 + "}",
        "int_41": '{"type":"action","action":' + "9" * 41 + "}",
        "int_16": '{"type":"action","action":' + "9" * 16 + "}",
        "big_float": '{"type":"action","action":1e999}',
        "many_lists": '{"type":"action","action":[' + "[]," * 499_000 + "[]]}",
        "big_calc": '{"type":"action","action":{"action":"calculator","expression":"' + "1+" * 20_000 + '1"}}',
        "big_submit": '{"type":"action","action":{"action":"submit","findings":{"episode_id":"x","findings":[]},"pad":"'
                      + "p" * 100_000 + '"}}',
    }
    EXPECT = {"deep_1000": "malformed", "deep_33": "malformed", "deep_10": "action", "huge_int": "malformed",
              "int_41": "malformed", "int_16": "action", "big_float": "malformed", "many_lists": "malformed",
              "big_calc": "malformed", "big_submit": "action"}

    def kinds(self) -> dict:
        return {k: protocol.parse_agent_line(v)[0] for k, v in self.CASES.items()}

    def test_limits_are_explicit(self):
        self.assertEqual(self.kinds(), self.EXPECT)

    def test_same_answers_with_unlimited_int_digits_and_a_huge_recursion_limit(self):
        code = ("import sys,json;sys.setrecursionlimit(200000)\n"
                "from tests.test_redteam import ParserBounds as P\n"
                "print(json.dumps(P().kinds(), sort_keys=True))\n")
        env = dict(os.environ, PYTHONINTMAXSTRDIGITS="0", PYTHONPATH=str(ROOT))
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[-500:])
        self.assertEqual(json.loads(out.stdout), self.EXPECT)

    def test_malformed_echo_is_bounded(self):
        kind, echo = protocol.parse_agent_line("x" * 10_000)
        self.assertEqual((kind, len(echo)), ("malformed", protocol.ECHO_CHARS))


class HostSecretHygiene(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows only: the run removes --secret-env from the process environment "
                         "block; on Linux, AgentProcess hardening is tested in tests/test_linux_hardening.py "
                         "(not readable for a non-root child without CAP_SYS_PTRACE); the run --secret-env "
                         "path is measured by python -m auditgym.redteam --parent")
    def test_secret_env_is_not_in_the_parent_environment_of_the_policy(self):
        from auditgym.redteam import secret_env_probe

        # the child stays at the host's integrity level here: this measures that `run` itself removed the variable
        # from its environment block (the Low-integrity child of the default run cannot read the block at all)
        res = secret_env_probe("AUDITGYM_TEST_SOMEVAR", lower=False)
        self.assertTrue(res["readable"], "the probe could not read the parent's environment, so it proves nothing")
        self.assertFalse(res["found_in_parent"])
        self.assertFalse(res["in_own_environment"])

    @unittest.skipUnless(os.name == "nt", "Windows only: integrity levels")
    def test_secret_env_default_run_child_is_refused_the_parent_memory(self):
        from auditgym.redteam import secret_env_probe

        res = secret_env_probe("AUDITGYM_TEST_SOMEVAR2")
        self.assertTrue(res["integrity"].startswith("lowered"), res["integrity"])
        self.assertFalse(res["readable"])
        self.assertFalse(res["found_in_parent"])
        self.assertIn("error 5", res["why"])


if __name__ == "__main__":
    unittest.main()
