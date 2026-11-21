"""CLI robustness: bad input exits 2 with one `error:` line, closed-run warnings, run metadata,
per-episode random seeding, and the stress helpers. Most cases call main() in-process (fast);
one case runs the real command line to check there is no traceback."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from auditgym import __main__ as cli_mod
from auditgym import config as cfgmod
from auditgym import protocol
from auditgym import stress
from auditgym.episode import EpisodeFormatError, load_episode
from auditgym.runner import run_one
from auditgym.splits import load_split_episodes

ROOT = Path(__file__).resolve().parent.parent


def cli(*args, env_extra=None):
    """In-process main(); returns (rc, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    env = dict(env_extra or {})
    with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli_mod.main(list(args))
    return rc, out.getvalue(), err.getvalue()


class BadInput(unittest.TestCase):
    def assert_clean_error(self, res):
        rc, _out, err = res
        self.assertEqual(rc, 2, err)
        self.assertNotIn("Traceback", err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("error:"), lines[0])
        return lines[0]

    def gen(self, d, *extra, cfg=None):
        args = ["generate", "--seed", "1", "--out", str(Path(d) / "x"), *extra]
        if cfg is not None:
            args += ["--config", cfg]
        return cli(*args)

    def test_real_command_line_has_no_traceback(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-m", "auditgym", "generate", "--seed", "1", "--config",
                                json.dumps({"period": "2025-10", "interacting": ["boundary_fx_payment"],
                                           "variants": {"wrong_fx_rate": ["utc_date"]}}),
                                "--out", str(Path(d) / "x")], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                               env=env, timeout=120)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len([ln for ln in r.stderr.splitlines() if ln.strip()]), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("error:"), r.stderr)

    def test_infeasible_config(self):
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(self.gen(d, cfg=json.dumps({"period": "2025-10", "interacting": ["boundary_fx_payment"],
                                           "variants": {"wrong_fx_rate": ["utc_date"]}})))

    def test_config_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(self.gen(d, cfg="{not json"))
            self.assert_clean_error(self.gen(d, cfg='{"colour": 1}'))
            for bad in ("5", "[]", "null", '"x"', "examples/config_no_such.json"):  # not inline JSON objects: read as paths
                self.assertIn("config file", self.assert_clean_error(self.gen(d, cfg=bad)), bad)
            f = Path(d) / "c.json"
            f.write_text("[]", encoding="utf-8")
            self.assertIn("JSON object", self.assert_clean_error(self.gen(d, cfg=str(f))))
            self.assertEqual(cli_mod._load_config('{"k": "' + "a" * 400 + '"}'), {"k": "a" * 400})  # long inline JSON is not a path

    def test_missing_directories_and_files(self):
        self.assert_clean_error(cli("verify", str(ROOT / "no_such_episode_dir")))
        with tempfile.TemporaryDirectory() as d:
            self.assert_clean_error(cli("transform", "--in", str(Path(d) / "nope"), "--out", str(Path(d) / "o")))
            self.assert_clean_error(cli("grade", "--episode", str(Path(d) / "nope"), "--findings", str(Path(d) / "f.json")))
            self.assert_clean_error(cli("run", "--episodes", str(Path(d) / "nope"), "--out", str(Path(d) / "o")))

    def test_unset_secret_variable_is_an_error(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ):
            os.environ.pop("AUDITGYM_TEST_NO_SUCH_SECRET", None)
            self.assert_clean_error(self.gen(d, "--secret-env", "AUDITGYM_TEST_NO_SUCH_SECRET"))

    def test_bad_numbers(self):
        self.assert_clean_error(cli("stress", "--n", "-1"))
        self.assert_clean_error(cli("budget", "--budgets", "20,x"))
        self.assert_clean_error(cli("budget", "--budgets", "0"))
        self.assert_clean_error(cli("budget", "--budgets", "1000"))

    def test_max_steps_out_of_range_is_an_error(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            for bad in ("0", "1000", "-5"):
                with self.subTest(bad):
                    line = self.assert_clean_error(cli("run", "--episodes", ep, "--policies", "random", "--max-steps", bad,
                                                       "--out", str(Path(d) / "o")))
                    self.assertIn("--max-steps", line)
            self.assertFalse((Path(d) / "o").exists())

    def test_grade_steps_out_of_range_is_an_error(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text("{}", encoding="utf-8")
            for bad in ("101", "1000", "-1"):
                with self.subTest(bad):
                    line = self.assert_clean_error(cli("grade", "--episode", ep, "--findings", str(f), "--steps", bad))
                    self.assertIn("--steps", line)
            for good in ("0", "100"):
                with self.subTest(good):
                    self.assertEqual(cli("grade", "--episode", ep, "--findings", str(f), "--steps", good)[0], 0)

    def test_grade_json_null_is_an_invalid_submission(self):
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text("null", encoding="utf-8")
            rc, out, err = cli("grade", "--episode", str(ep), "--findings", str(f))
        self.assertEqual(rc, 0, err)
        report = json.loads(out)
        self.assertEqual(report["status"], "invalid_submission")
        self.assertEqual(report["reward"], -1)
        self.assertIn("submission must be a JSON object", report["errors"])

    def test_grade_with_a_huge_integer_is_an_invalid_submission(self):
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        eid = load_episode(ep).episode_id
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text('{"episode_id": "%s", "findings": [{"type": "duplicate_payment", "affected_ids": ["x"], '
                         '"claimed_amount_minor": %s, "currency": "JPY"}]}' % (eid, "9" * 5000), encoding="utf-8")
            rc, out, err = cli("grade", "--episode", str(ep), "--findings", str(f))
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        rep = json.loads(out)
        self.assertEqual(rep["reward"], -1)
        self.assertNotEqual(rep["status"], "submitted")

    def test_grade_with_deep_nesting_is_an_invalid_submission(self):
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        eid = load_episode(ep).episode_id
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f.json"
            f.write_text('{"episode_id": "%s", "findings": %s%s}' % (eid, "[" * 100000, "]" * 100000), encoding="utf-8")
            rc, out, err = cli("grade", "--episode", str(ep), "--findings", str(f))
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(out)["reward"], -1)

    def test_seed_must_be_an_integer(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            cli_mod.main(["generate", "--seed", "foo", "--out", str(Path(d) / "x")])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("--seed", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_bad_seeds_files(self):
        cases = {"no seed": {"episodes": [{"name": "no seed"}]},
                 "string seed": {"episodes": [{"seed": "closed-01"}]},
                 "bool seed": {"episodes": [{"seed": True}]},
                 "float seed": {"episodes": [{"seed": 1.5}]},
                 "list seed": {"episodes": [{"seed": [1, 2]}]},
                 "config not object": {"episodes": [{"seed": 1, "config": 5}]},
                 "duplicate names": {"episodes": [{"seed": 1, "name": "a"}, {"seed": 2, "name": "a"}]},
                 "empty": {"episodes": []}}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.json"
            for label, spec in cases.items():
                f.write_text(json.dumps(spec), encoding="utf-8")
                with self.subTest(label):
                    self.assert_clean_error(cli("run", "--seeds-file", str(f), "--no-secret", "--policies", "flag_all", "--out", str(Path(d) / "o")))

    def test_secret_env_needs_seeds_file(self):
        with tempfile.TemporaryDirectory() as d:
            res = cli("run", "--episodes", str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"), "--policies", "flag_all",
                      "--secret-env", "AUDITGYM_TEST_SECRET", "--out", str(Path(d) / "o"), env_extra={"AUDITGYM_TEST_SECRET": "x"})
            self.assertIn("--seeds-file", self.assert_clean_error(res))

    def test_internal_errors_keep_their_traceback(self):
        """Only input errors become exit 2: a ValueError raised inside a run is a bug and propagates."""
        with tempfile.TemporaryDirectory() as d, mock.patch("auditgym.runner.run_many", side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                cli("run", "--episodes", str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"), "--policies", "flag_all",
                    "--out", str(Path(d) / "o"))


class StrictAgentUser(unittest.TestCase):
    """AUDITGYM_REQUIRE_AGENT_USER=1 with no separate policy user possible (forced by an empty AUDITGYM_AGENT_USER,
    so the result is the same on Windows, macOS, CI and inside the image)."""

    ENV = {"AUDITGYM_REQUIRE_AGENT_USER": "1", "AUDITGYM_AGENT_USER": ""}

    def assert_strict_error(self, rc, err):
        self.assertEqual(rc, 2, err)
        self.assertNotIn("Traceback", err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("error: AUDITGYM_REQUIRE_AGENT_USER=1"), lines[0])
        self.assertIn("AUDITGYM_AGENT_USER is not set", lines[0])

    def test_check_run_and_demo_exit_2_before_any_report(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o"
            cases = (["check", "--out", str(out)],
                     ["run", "--episodes", ep, "--policies", "random,oracle", "--out", str(out)],
                     ["demo"],
                     ["budget", "--out", str(out)],
                     ["viewer", "--out", str(out)])
            for argv in cases:
                with self.subTest(argv[0]):
                    rc, stdout, err = cli(*argv, env_extra=self.ENV)
                    self.assert_strict_error(rc, err)
                    self.assertEqual(stdout, "")
                    self.assertFalse(out.exists())

    def test_in_process_and_oracle_runs_need_no_child(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            for extra in (["--policies", "oracle"], ["--policies", "random", "--in-process"]):
                with self.subTest(extra):
                    rc, _out, err = cli("run", "--episodes", ep, "--out", str(Path(d) / "o"), *extra, env_extra=self.ENV)
                    self.assertEqual(rc, 0, err)

    def test_custom_policy_in_process_is_refused_but_built_in_is_not(self):
        ep = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o"
            rc, stdout, err = cli("run", "--episodes", ep, "--policies", "random,examples.custom_policy:FirstPagePolicy",
                                  "--in-process", "--out", str(out), env_extra=self.ENV)
            self.assertEqual(rc, 2, err)
            lines = [ln for ln in err.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, err)
            self.assertTrue(lines[0].startswith("error: AUDITGYM_REQUIRE_AGENT_USER=1"), lines[0])
            self.assertIn("--in-process", lines[0])
            self.assertIn("examples.custom_policy:FirstPagePolicy", lines[0])
            self.assertEqual(stdout, "")
            self.assertFalse(out.exists())
            rc, _o, err = cli("run", "--episodes", ep, "--policies", "random", "--in-process", "--out", str(out),
                              env_extra=self.ENV)
            self.assertEqual(rc, 0, err)

    def test_only_the_value_1_turns_strict_mode_on(self):
        for value, expected in (("1", True), (" 1 ", True), ("", False), ("0", False), ("true", False)):
            with self.subTest(value), mock.patch.dict(os.environ, {"AUDITGYM_REQUIRE_AGENT_USER": value}):
                self.assertEqual(protocol.require_agent_user(), expected)

    def test_agent_process_raises_a_dedicated_exception(self):
        with mock.patch.dict(os.environ, self.ENV), self.assertRaises(protocol.AgentUserRequired):
            protocol.AgentProcess("recon", 0)
        self.assertFalse(issubclass(protocol.AgentUserRequired, OSError))


class CustomPolicyInProcess(unittest.TestCase):
    """--policy-path reaches the in-process runner; a custom policy next to a seeds file, a secret or an answer key is refused unless --allow-same-user.
    These are the non-strict behaviours: strict mode refuses a custom policy in process (StrictAgentUser), and CI runs
    the whole suite once with AUDITGYM_REQUIRE_AGENT_USER=1 set, so every call here switches it off."""

    EP = str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
    NONSTRICT = {"AUDITGYM_REQUIRE_AGENT_USER": ""}

    def test_policy_path_works_in_process(self):
        with tempfile.TemporaryDirectory() as d:
            source = ["class P:",
                      "    def act(self, observation, reward=0.0, info=None):",
                      "        return {'action': 'submit', 'findings': {'episode_id': 'x', 'findings': []}}"]
            Path(d, "inproc_policy_mod.py").write_text("\n".join(source) + "\n", encoding="utf-8")
            out = Path(d) / "o"
            rc, _o, err = cli("run", "--episodes", self.EP, "--policies", "inproc_policy_mod:P", "--policy-path", d,
                              "--in-process", "--out", str(out), env_extra=self.NONSTRICT)
            self.assertEqual(rc, 0, err)
            self.assertNotIn("Traceback", err)
            grades = [json.loads(ln) for ln in (out / "grades.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([g["policy"] for g in grades], ["inproc_policy_mod:P"])
        self.assertNotIn(str(Path(d).resolve()), sys.path)

    def run_custom(self, d, *extra, env_extra=None):
        return cli("run", "--policies", "examples.custom_policy:FirstPagePolicy", "--in-process", "--out",
                   str(Path(d) / "o"), *extra, env_extra={**self.NONSTRICT, **(env_extra or {})})

    def test_closed_runs_refuse_a_same_user_custom_policy_unless_allowed(self):
        seeds = str(ROOT / "examples" / "closed_seeds_example.json")
        secret = {"AUDITGYM_TEST_SECRET_W": "warn-test-secret"}
        with tempfile.TemporaryDirectory() as d:
            rc, _o, err = self.run_custom(d, "--seeds-file", seeds, "--secret-env", "AUDITGYM_TEST_SECRET_W",
                                          env_extra=secret)
            self.assertEqual(rc, 2, err)
            lines = [ln for ln in err.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, err)
            # the advice names what works on this host: where the child can switch to the separate policy user (the
            # official image), dropping --in-process; elsewhere, running it in the official image
            switch = protocol._can_switch_user()
            advice = "drop --in-process" if switch else "official image"
            for word in ("error: custom policy", "host's user", "closed episodes", advice, "--allow-same-user"):
                self.assertIn(word, lines[0])
            self.assertFalse((Path(d) / "o").exists(), "a refused run writes nothing")
            rc, _o, err = self.run_custom(d, "--seeds-file", seeds, "--secret-env", "AUDITGYM_TEST_SECRET_W",
                                          "--allow-same-user", env_extra=secret)
            self.assertEqual(rc, 0, err)
            lines = [ln for ln in err.splitlines() if "custom policy" in ln]
            self.assertEqual(len(lines), 1, err)
            self.assertTrue(lines[0].startswith("WARNING:"), lines[0])
            for word in ("host's user", "closed episodes", "--allow-same-user", "seeds file"):
                self.assertIn(word, lines[0])
            self.assertNotIn("warn-test-secret", err)
            meta = json.loads((Path(d) / "o" / "meta.json").read_text(encoding="utf-8"))
            self.assertIs(meta["allow_same_user"], True)

    def test_next_to_answer_keys_outside_the_open_splits_the_run_is_refused_unless_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            closed = Path(d) / "closed_ep"
            shutil.copytree(self.EP, closed)
            rc, _o, err = self.run_custom(d, "--episodes", str(closed))
            self.assertEqual(rc, 2, err)
            lines = [ln for ln in err.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, err)
            for word in ("error: custom policy", "host's user", "answer keys", "grader", "--allow-same-user"):
                self.assertIn(word, lines[0])
            self.assertFalse((Path(d) / "o").exists(), "a refused run writes nothing")
            rc, _o, err = self.run_custom(d, "--episodes", str(closed), "--allow-same-user")
            self.assertEqual(rc, 0, err)
            lines = [ln for ln in err.splitlines() if "custom policy" in ln]
            self.assertEqual(len(lines), 1, err)
            self.assertTrue(lines[0].startswith("WARNING:"), lines[0])
            for word in ("host's user", "answer keys", "grader", "--allow-same-user"):
                self.assertIn(word, lines[0])
            meta = json.loads((Path(d) / "o" / "meta.json").read_text(encoding="utf-8"))
            self.assertIs(meta["allow_same_user"], True)

    def test_jurors_probe_a_policy_that_globs_for_truth_json(self):
        """The jurors' probe: a custom policy on a freshly generated episode (outside the open splits) that globs for
        truth.json and submits from it. Refused before it starts; with --allow-same-user it scores a perfect reward,
        which is why the override is recorded."""
        probe = ["import glob, json, os",
                 "class Thief:",
                 "    def __init__(self, seed=0):",
                 "        self.truth = None",
                 "    def act(self, observation, reward=0.0, info=None):",
                 "        here = os.path.dirname(os.path.abspath(__file__))",
                 "        path = glob.glob(os.path.join(here, '**', 'truth.json'), recursive=True)[0]",
                 "        truth = json.load(open(path, encoding='utf-8'))",
                 "        findings = [{'type': t['type'], 'affected_ids': t['affected_ids'],",
                 "                     'claimed_amount_minor': t['expected_amount_minor'], 'currency': t['currency'],",
                 "                     'evidence_ids': t['evidence_sets'][0], 'explanation': ''} for t in truth['issues']]",
                 "        return {'action': 'submit', 'findings': {'episode_id': truth['episode_id'], 'findings': findings}}"]
        with tempfile.TemporaryDirectory() as d:
            Path(d, "probe_thief_mod.py").write_text("\n".join(probe) + "\n", encoding="utf-8")
            ep = Path(d) / "closed" / "e1"
            rc, _o, err = cli("generate", "--seed", "987654321987", "--config", str(ROOT / "examples" / "config_mixed.json"),
                              "--out", str(ep))
            self.assertEqual(rc, 0, err)
            args = ("run", "--episodes", str(Path(d) / "closed"), "--policies", "probe_thief_mod:Thief", "--policy-path", d,
                    "--in-process", "--out", str(Path(d) / "o"))
            rc, _o, err = cli(*args, env_extra=self.NONSTRICT)
            self.assertEqual(rc, 2, err)
            self.assertEqual(len([ln for ln in err.splitlines() if ln.strip()]), 1, err)
            self.assertTrue(err.startswith("error:"), err)
            self.assertFalse((Path(d) / "o").exists())
            rc, _o, err = cli(*args, "--allow-same-user", env_extra=self.NONSTRICT)
            self.assertEqual(rc, 0, err)
            meta = json.loads((Path(d) / "o" / "meta.json").read_text(encoding="utf-8"))
            self.assertIs(meta["allow_same_user"], True)
            grades = [json.loads(ln) for ln in (Path(d) / "o" / "grades.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(grades), 1)
            self.assertGreater(grades[0]["n_issues"], 0)
            self.assertEqual((grades[0]["tp"], grades[0]["fp"], grades[0]["fn"]), (grades[0]["n_issues"], 0, 0),
                             "the override is what lets the policy read the key")

    def test_switching_needs_the_capabilities_not_only_an_account_and_proc(self):
        status = "Name:\tx\nCapEff:\t{:016x}\n"
        need = (1 << 0) | (1 << 6) | (1 << 7)  # CAP_CHOWN, CAP_SETGID, CAP_SETUID
        cases = ((need, True), (0, False), (need & ~(1 << 7), False), (need & ~(1 << 0), False),
                 (need & ~(1 << 6), False), ((1 << 41) | need, True))
        for eff, expected in cases:
            with self.subTest(eff=hex(eff)), mock.patch.object(protocol.os, "name", "posix"), \
                    mock.patch("builtins.open", mock.mock_open(read_data=status.format(eff))):
                self.assertIs(protocol._caps_allow_switch(), expected)
        with mock.patch.object(protocol.os, "name", "posix"), mock.patch("builtins.open", side_effect=OSError):
            self.assertIs(protocol._caps_allow_switch(), False)
        with mock.patch.object(protocol.os, "name", "posix"), \
                mock.patch("builtins.open", mock.mock_open(read_data="Name:\tx\n")):  # no CapEff line: fail closed
            self.assertIs(protocol._caps_allow_switch(), False)
        with mock.patch.object(protocol.os, "name", "nt"):
            self.assertIs(protocol._caps_allow_switch(), False)
        ident = ("agent", 10001, 10001)
        for caps, expected in ((True, True), (False, False)):
            with mock.patch.object(protocol.aio, "agent_identity", return_value=ident), \
                    mock.patch.object(protocol, "_proc_listable", return_value=True), \
                    mock.patch.object(protocol, "_caps_allow_switch", return_value=caps):
                self.assertIs(protocol._can_switch_user(), expected)
        with mock.patch.object(protocol.aio, "agent_identity", return_value=None), \
                mock.patch.object(protocol, "_proc_listable", return_value=True), \
                mock.patch.object(protocol, "_caps_allow_switch", return_value=True):
            self.assertIs(protocol._can_switch_user(), False)
        with mock.patch.object(protocol.aio, "agent_identity", return_value=ident), \
                mock.patch.object(protocol, "_proc_listable", return_value=False), \
                mock.patch.object(protocol, "_caps_allow_switch", return_value=True):  # /proc not listable
            self.assertIs(protocol._can_switch_user(), False)

    def test_a_cap_dropped_root_does_not_skip_the_guard(self):
        """An account and a listable /proc but no CAP_SETUID: the child would fall back to the host's user, so the
        guard must not return early, and its advice names the official image."""
        with tempfile.TemporaryDirectory() as d:
            closed = Path(d) / "closed_ep"
            shutil.copytree(self.EP, closed)
            with mock.patch.object(protocol.aio, "agent_identity", return_value=("agent", 10001, 10001)), \
                    mock.patch.object(protocol, "_proc_listable", return_value=True), \
                    mock.patch.object(protocol, "_caps_allow_switch", return_value=False):
                rc, _o, err = cli("run", "--episodes", str(closed), "--policies",
                                  "examples.custom_policy:FirstPagePolicy", "--out", str(Path(d) / "o"),
                                  env_extra=self.NONSTRICT)
            self.assertEqual(rc, 2, err)
            self.assertIn("official image", err)
            self.assertFalse((Path(d) / "o").exists())

    def test_only_the_committed_open_splits_are_exempt(self):
        from auditgym import protocol

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for split in ("train", "hidden"):
                shutil.copytree(self.EP, root / "episodes" / split / "ep")
            shutil.copytree(self.EP, root / "episodes" / "train" / "new_ep")  # under an open split, but not committed
            (root / "episodes" / "index.json").write_text(
                json.dumps({"episodes": [{"split": "train", "name": "ep"}]}), encoding="utf-8")
            with mock.patch.object(protocol, "PROJECT_ROOT", root):
                rc, _o, err = self.run_custom(d, "--episodes", str(root / "episodes" / "train" / "new_ep"))
                self.assertEqual(rc, 2, err)
                self.assertIn("answer keys", err)  # a new folder under episodes/train is not a committed episode
                rc, _o, err = self.run_custom(d, "--episodes", str(root / "episodes" / "train" / "ep"))
                self.assertEqual(rc, 0, err)
                self.assertNotIn("error:", err)  # an open split: public by design, so a warning and no refusal
                self.assertIn("public answer keys of the open splits", err)
                rc, _o, err = self.run_custom(d, "--episodes", str(root / "episodes" / "hidden" / "ep"))
                self.assertEqual(rc, 2, err)
                self.assertIn("answer keys", err)  # a closed folder under episodes/ is refused

    def test_a_same_user_custom_policy_on_the_open_splits_gets_one_warning_and_a_meta_key(self):
        from auditgym import protocol

        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "proj"
            shutil.copytree(self.EP, root / "episodes" / "train" / "ep")
            shutil.copytree(self.EP, root / "episodes" / "train" / "ep2")
            (root / "episodes" / "index.json").write_text(json.dumps({"episodes": [
                {"split": "train", "name": "ep"}, {"split": "train", "name": "ep2"}]}), encoding="utf-8")
            with mock.patch.object(protocol, "PROJECT_ROOT", root):
                rc, _o, err = self.run_custom(d, "--episodes", str(root / "episodes" / "train"))
                self.assertEqual(rc, 0, err)
                lines = [ln for ln in err.splitlines() if "custom policy" in ln]
                self.assertEqual(len(lines), 1, err)
                self.assertTrue(lines[0].startswith("WARNING: custom policy "), lines[0])
                self.assertIn("runs as the host's user next to the public answer keys of the open splits (", lines[0])
                self.assertIn("/grader and 1 more): it can read them; fine for training, never for evaluation", lines[0])
                meta = json.loads((Path(d) / "o" / "meta.json").read_text(encoding="utf-8"))
                self.assertIs(meta["open_answer_keys_readable"], True)
                self.assertIs(meta["allow_same_user"], False)
                self.assertFalse(protocol._NO_SAME_USER_EXTERNAL)
                self.assertFalse(protocol._SAME_USER_ALLOWED_CLOSED)
                # a built-in policy: no line, key false
                rc, _o, err = cli("run", "--policies", "recon", "--in-process", "--episodes",
                                  str(root / "episodes" / "train" / "ep"), "--out", str(Path(d) / "o2"), env_extra=self.NONSTRICT)
                self.assertEqual(rc, 0, err)
                self.assertNotIn("WARNING", err)
                meta = json.loads((Path(d) / "o2" / "meta.json").read_text(encoding="utf-8"))
                self.assertIs(meta["open_answer_keys_readable"], False)

    def test_no_open_split_warning_when_the_policy_runs_as_the_separate_user(self):
        from auditgym import protocol

        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "proj"
            shutil.copytree(self.EP, root / "episodes" / "train" / "ep")
            (root / "episodes" / "index.json").write_text(
                json.dumps({"episodes": [{"split": "train", "name": "ep"}]}), encoding="utf-8")
            import types
            args = types.SimpleNamespace(in_process=False, seeds_file=None, secret_env=None, allow_same_user=False)
            with mock.patch.object(protocol, "PROJECT_ROOT", root),                     mock.patch.object(protocol, "_can_switch_user", return_value=True),                     mock.patch.object(protocol, "require_agent_user", return_value=False),                     contextlib.redirect_stderr(io.StringIO()) as err:
                cli_mod._custom_policy_guard(["examples.custom_policy:FirstPagePolicy"], args,
                                             [root / "episodes" / "train" / "ep"])
            self.assertEqual(err.getvalue(), "")
            self.assertFalse(protocol._NO_SAME_USER_EXTERNAL)
            self.assertFalse(hasattr(args, "open_answer_keys_readable"))

    def test_a_built_in_policy_never_sees_the_policy_path(self):
        """A file named like a standard-library module in --policy-path must not run for a built-in policy."""
        with tempfile.TemporaryDirectory() as d:
            marker = str(Path(d) / "marker")
            Path(d, "random.py").write_text(f"open({marker!r}, 'w').write('ran')\nraise SystemExit(0)\n", encoding="utf-8")
            for extra in ((), ("--in-process",)):
                with self.subTest(extra=extra):
                    rc, _o, err = cli("run", "--episodes", self.EP, "--policies", "random", "--policy-path", d, *extra,
                                      "--out", str(Path(d) / "o"), env_extra=self.NONSTRICT)
                    self.assertEqual(rc, 0, err)
                    self.assertFalse((Path(d) / "marker").exists(), "the shadowing module ran")

    def test_no_warning_for_open_runs_and_built_in_policies(self):
        seeds = str(ROOT / "examples" / "closed_seeds_example.json")
        with tempfile.TemporaryDirectory() as d:
            rc, _o, err = self.run_custom(d, "--episodes", self.EP)
            self.assertEqual(rc, 0, err)
            self.assertNotIn("error:", err)  # the committed open split warns (no refusal); see the open-split test
            self.assertEqual(len([ln for ln in err.splitlines() if "custom policy" in ln]), 1, err)
            rc, _o, err = cli("run", "--seeds-file", seeds, "--no-secret", "--policies", "flag_all", "--in-process",
                              "--out", str(Path(d) / "o2"), env_extra=self.NONSTRICT)
            self.assertEqual(rc, 0, err)
            self.assertNotIn("custom policy", err)


class ClosedRun(unittest.TestCase):
    def run_seeds(self, d, seeds, env_extra=None, *extra):
        f = Path(d) / "s.json"
        f.write_text(json.dumps({"split": "t", "episodes": [{"name": f"e{s}", "seed": s, "config": {"size": "small"}}
                                                             for s in seeds]}), encoding="utf-8")
        out = Path(d) / "out"
        res = cli("run", "--seeds-file", str(f), "--policies", "flag_all", "--in-process", "--out", str(out), *extra,
                  env_extra=env_extra)
        return res, out

    def test_small_seed_warns_and_runs(self):
        with tempfile.TemporaryDirectory() as d:
            (rc, _o, err), out = self.run_seeds(d, [7], None, "--no-secret")
            self.assertEqual(rc, 0, err)
            self.assertIn("WARNING", err)
            meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
            self.assertIs(meta["secret_used"], False)
            self.assertIs(meta["no_secret"], True)  # the opt-out is recorded
            self.assertEqual(meta["min_seed_bits"], 3)
            for key in ("auditgym_version", "generator_version", "config_version", "schema_version", "grade_version",
                        "python", "platform", "mode", "isolated", "policy_seed", "max_steps", "command"):
                self.assertIn(key, meta)
            first = json.loads((out / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(sorted(first), sorted(["run_id", "split", "policy", "episode_id", "step", "action",
                                                    "observation", "reward", "terminated", "truncated"]))

    def test_seeds_file_without_a_secret_is_refused_unless_no_secret_is_given(self):
        """Juror probe: a 13-bit seed in a closed run is recoverable from the episode_id, so the run needs a secret
        or an explicit opt-out; run and check both refuse with one error line and write nothing."""
        with tempfile.TemporaryDirectory() as d:
            (rc, _o, err), out = self.run_seeds(d, [7])
            self.assertEqual(rc, 2, err)
            lines = [ln for ln in err.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, err)
            self.assertTrue(lines[0].startswith("error:"), lines[0])
            for word in ("--secret-env", "--no-secret", "episode_id"):
                self.assertIn(word, lines[0])
            self.assertFalse(out.exists())
            (rc, _o, err), out = self.run_seeds(d, [7], {"AUDITGYM_TEST_SECRET": "x"}, "--no-secret", "--secret-env",
                                                "AUDITGYM_TEST_SECRET")
            self.assertEqual(rc, 2, err)
            self.assertIn("contradict", err)
            (rc, _o, err), out = self.run_seeds(d, [6602239917354212077], {"AUDITGYM_TEST_SECRET": "x"}, "--secret-env",
                                                "AUDITGYM_TEST_SECRET")
            self.assertEqual(rc, 0, err)
            self.assertIs(json.loads((out / "meta.json").read_text(encoding="utf-8"))["no_secret"], False)
            res = cli("run", "--episodes", str(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"), "--policies",
                      "flag_all", "--in-process", "--no-secret", "--out", str(Path(d) / "o3"))
            self.assertEqual(res[0], 2, res[2])
            self.assertIn("--seeds-file", res[2])
        from auditgym import check as check_mod

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.json"
            f.write_text(json.dumps({"split": "t", "episodes": [{"name": "e", "seed": 7, "config": {"size": "small"}}]}),
                         encoding="utf-8")
            for extra, word in (([], "--no-secret"), (["--no-secret", "--secret-env", "X"], "contradict")):
                e = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(e):
                    rc = check_mod.main(["--seeds-file", str(f), "--out", str(Path(d) / "o"), *extra])
                lines = [ln for ln in e.getvalue().splitlines() if ln.strip()]
                self.assertEqual((rc, len(lines)), (2, 1), e.getvalue())
                self.assertIn(word, lines[0])
                self.assertFalse((Path(d) / "o").exists())
            e = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(e):
                rc = check_mod.main(["--no-secret", "--out", str(Path(d) / "o")])
            self.assertEqual(rc, 2)
            self.assertIn("--no-secret needs --seeds-file", e.getvalue())

    def test_secret_and_large_seed_no_warning_and_secret_not_recorded(self):
        secret = "s3cret-value-for-test-9f2c"
        with tempfile.TemporaryDirectory() as d:
            (rc, _o, err), out = self.run_seeds(d, [6602239917354212077], {"AUDITGYM_TEST_SECRET": secret},
                                                "--secret-env", "AUDITGYM_TEST_SECRET")
            self.assertEqual(rc, 0, err)
            self.assertNotIn("WARNING", err)
            text = (out / "meta.json").read_text(encoding="utf-8")
            self.assertNotIn(secret, text)
            meta = json.loads(text)
            self.assertIs(meta["secret_used"], True)
            self.assertGreaterEqual(meta["min_seed_bits"], 40)

    # a period whose last day falls on a weekend cannot host boundary_fx_payment when the rate error is limited to utc_date
    INFEASIBLE = {"name": "c_refused", "seed": 6602239917354212077,
                  "config": {"period": "2026-01", "interacting": ["boundary_fx_payment"], "variants": {"wrong_fx_rate": ["utc_date"]}}}
    FEASIBLE = {"name": "c_ok", "seed": 6602239917354212077, "config": {"size": "small", "period": "2026-05"}}

    def seeds_file(self, d, entries):
        f = Path(d) / "refuse.json"
        f.write_text(json.dumps({"split": "t", "episodes": entries}), encoding="utf-8")
        return str(f)

    def test_run_skips_a_refused_entry_and_records_it(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            rc, _o, err = cli("run", "--seeds-file", self.seeds_file(d, [self.INFEASIBLE, self.FEASIBLE]), "--no-secret", "--policies",
                              "flag_all", "--in-process", "--out", str(out))
            self.assertEqual(rc, 0, err)
            self.assertIn("WARNING: entry c_refused refused, ConfigError: boundary_fx_payment", err)
            meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["episodes"], 1)
            self.assertEqual([r["name"] for r in meta["refused_entries"]], ["c_refused"])
            rc, _o, err = cli("run", "--seeds-file", self.seeds_file(d, [self.INFEASIBLE]), "--no-secret", "--policies", "flag_all",
                              "--in-process", "--out", str(Path(d) / "out2"))
            self.assertEqual(rc, 2, err)
            self.assertIn("error: no entry of the seeds file can be generated; c_refused: ConfigError", err)

    def test_check_names_a_refused_entry_and_checks_the_rest(self):
        from auditgym import check as check_mod

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = check_mod.main(["--seeds-file", self.seeds_file(d, [self.INFEASIBLE, self.FEASIBLE]), "--no-secret", "--out", str(out)])
            self.assertEqual(rc, 0, o.getvalue()[-1500:] + e.getvalue())
            text = o.getvalue()
            self.assertIn("(2 entries: 1 generated, 1 refused, secret: no, --no-secret)", text)
            self.assertIn("[SKIP] c_refused: generated from its seed and config - refused, ConfigError: boundary_fx_payment", text)
            self.assertIn("C_data", [ln for ln in text.splitlines() if ln.startswith("summary:")][0])
            self.assertTrue((out / "report.md").is_file())
            self.assertIn("1 refused", (out / "report.md").read_text(encoding="utf-8"))
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = check_mod.main(["--seeds-file", self.seeds_file(d, [self.INFEASIBLE]), "--no-secret", "--out", str(Path(d) / "o2")])
            self.assertEqual(rc, 2)
            lines = [ln for ln in e.getvalue().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, lines)
            self.assertTrue(lines[0].startswith("error: no entry of the seeds file can be generated; c_refused"), lines)

    def test_refused_entries_add_one_kind_and_no_seed_warning(self):
        from auditgym import check as check_mod

        def kinds(entries, d, tag):
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = check_mod.main(["--seeds-file", self.seeds_file(d, entries), "--no-secret", "--out", str(Path(d) / tag)])
            self.assertEqual(rc, 0, o.getvalue()[-800:] + e.getvalue())
            line = [ln for ln in o.getvalue().splitlines() if ln.startswith("summary:")][0]
            return line.rsplit("of ", 1)[1], e.getvalue()

        small_refused = dict(self.INFEASIBLE, name="c_small", seed=7)  # a small seed that is never generated
        with tempfile.TemporaryDirectory() as d:
            one, _ = kinds([self.INFEASIBLE, self.FEASIBLE], d, "o1")
            two, err = kinds([self.INFEASIBLE, dict(self.INFEASIBLE, name="c_other"), small_refused, self.FEASIBLE], d, "o2")
            self.assertEqual(one, two)  # the coverage count does not grow with the number of refused entries
            self.assertNotIn("small seeds", err)  # only generated entries count for the seed warning

    def test_closed_run_kinds_do_not_count_the_split_label(self):
        """The B_replay checks of a closed run are labelled <split label>/<policy>; like train/<policy> and
        dev/<policy> in the full check they are one kind, not one per policy."""
        from auditgym import check as check_mod

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = check_mod.main(["--seeds-file", self.seeds_file(d, [self.FEASIBLE]), "--no-secret", "--out", str(out)])
            self.assertEqual(rc, 0, o.getvalue()[-800:] + e.getvalue())
            line = [ln for ln in o.getvalue().splitlines() if ln.startswith("summary:")][0]
            printed = int(line.rsplit("of ", 1)[1].split(" ")[0])
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
            checks = [c["check"] for cs in report["sections"].values() for c in cs]
            replay = [c["check"] for c in report["sections"]["B_replay"]]
            self.assertEqual(len(replay), len(check_mod.REPLAY_POLICIES))
            self.assertTrue(all(c.startswith("t/") for c in replay), replay)  # the seeds file's split label is "t"
            without_label = len({check_mod.check_kind(c, ["c_ok"]) for c in checks})
            self.assertEqual(without_label - printed, len(check_mod.REPLAY_POLICIES) - 1)

    def test_allow_same_user_is_recorded_only_when_it_took_effect(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            rc, _o, err = cli("run", "--seeds-file", self.seeds_file(d, [self.FEASIBLE]), "--no-secret", "--policies", "flag_all",
                              "--in-process", "--allow-same-user", "--out", str(out))
            self.assertEqual(rc, 0, err)
            self.assertIs(json.loads((out / "meta.json").read_text(encoding="utf-8"))["allow_same_user"], False)

    def test_warning_boundary_is_two_to_the_40(self):
        warn = cli_mod._small_seed_warning
        self.assertIsNotNone(warn(cli_mod._seed_bits(2 ** 40 - 1), None))
        self.assertIsNone(warn(cli_mod._seed_bits(2 ** 40), None))
        self.assertIsNone(warn(cli_mod._seed_bits(2 ** 62 + 1), None))
        self.assertIsNone(warn(cli_mod._seed_bits(7), "a-secret"))  # a host secret makes small seeds safe


class BrokenAnswerKey(unittest.TestCase):
    SRC = ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"

    def broken_copy(self, d, truth_text):
        dst = Path(d) / "ep"
        shutil.copytree(self.SRC, dst)
        (dst / "grader" / "truth.json").write_text(truth_text, encoding="utf-8")
        return dst

    def one_error_line(self, res, path):
        rc, out, err = res
        self.assertEqual(rc, 2, (out, err))
        self.assertNotIn("Traceback", err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, err)
        self.assertTrue(lines[0].startswith("error:"), lines[0])
        self.assertIn("truth.json", lines[0])
        self.assertIn(str(path), lines[0])

    def test_bad_keys_exit_two_on_every_command(self):
        truth = load_episode(self.SRC).truth
        issue = dict(truth["issues"][0])
        del issue["issue_id"]
        bad = {"empty object": "{}", "issues not a list": '{"issues": "nope"}', "not an object": "[]",
               "issue without issue_id": json.dumps({**truth, "issues": [issue]})}
        for name, text in bad.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                ep = self.broken_copy(d, text)
                f = Path(d) / "f.json"
                f.write_text('{"episode_id": "x", "findings": []}', encoding="utf-8")
                out = str(Path(d) / "out")
                self.one_error_line(cli("run", "--episodes", str(ep), "--policies", "silent", "--in-process", "--out", out), ep / "grader" / "truth.json")
                self.one_error_line(cli("grade", "--episode", str(ep), "--findings", str(f)), ep / "grader" / "truth.json")
                self.one_error_line(cli("verify", str(ep)), ep / "grader" / "truth.json")
                self.one_error_line(cli("transform", "--in", str(ep), "--out", str(Path(d) / "t")), ep / "grader" / "truth.json")

    def test_unreadable_or_foreign_or_odd_keys_exit_two(self):
        truth = load_episode(self.SRC).truth
        other = load_episode(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy").truth
        bad = {"not json": "{not json", "other episode": json.dumps(other),
               "list alias": json.dumps({**truth, "id_aliases": {"X1": ["a"]}}),
               "empty alias": json.dumps({**truth, "id_aliases": {"X1": ""}})}
        for name, text in bad.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                ep = self.broken_copy(d, text)
                self.one_error_line(cli("verify", str(ep)), ep / "grader" / "truth.json")

    def test_viewer_and_budget_map_format_errors_to_exit_two(self):
        def boom(_args):
            raise EpisodeFormatError("x/grader/truth.json is not a valid answer key: $: missing issues")

        for command in ("cmd_viewer", "cmd_budget"):
            with self.subTest(command), mock.patch.object(cli_mod, command, boom):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = cli_mod.main(["viewer" if command == "cmd_viewer" else "budget"])
                self.assertEqual(rc, 2)
                self.assertEqual(err.getvalue().splitlines(), ["error: x/grader/truth.json is not a valid answer key: $: missing issues"])

    def test_committed_episodes_load_and_verify(self):
        from auditgym.verify import verify_generated

        for split in ("train", "dev"):
            for d in sorted((ROOT / "episodes" / split).iterdir()):
                if (d / "public").exists():
                    self.assertTrue(verify_generated(load_episode(d))["ok"], d.name)

    def test_public_load_ignores_the_key(self):
        with tempfile.TemporaryDirectory() as d:
            ep = self.broken_copy(d, "{}")
            self.assertEqual(load_episode(ep, with_grader=False).truth, {})


class BrokenPublicOrGraderFiles(unittest.TestCase):
    """A bad manifest or bad JSON is one error line naming the file and exit 2 on every loader."""
    SRC = ROOT / "episodes" / "dev" / "d08_both_interacting_kzt"

    def check_all_loaders(self, d, ep, name):
        f = Path(d) / "f.json"
        f.write_text('{"episode_id": "x", "findings": []}', encoding="utf-8")
        runs = [cli("verify", str(ep)),
                cli("run", "--episodes", str(ep), "--policies", "silent", "--in-process", "--out", str(Path(d) / "out")),
                cli("grade", "--episode", str(ep), "--findings", str(f)),
                cli("transform", "--in", str(ep), "--out", str(Path(d) / "t"))]
        for rc, out, err in runs:
            self.assertEqual(rc, 2, (out, err))
            lines = [ln for ln in err.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, err)
            self.assertTrue(lines[0].startswith("error:"), lines[0])
            self.assertIn(name, lines[0])

    def test_manifest_without_episode_id_or_not_an_object(self):
        for label, text in {"no episode_id": '{"schema_version": "1"}', "list": "[]", "non-string id": '{"episode_id": 5}'}.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as d:
                ep = Path(d) / "ep"
                shutil.copytree(self.SRC, ep)
                (ep / "public" / "manifest.json").write_text(text, encoding="utf-8")
                self.check_all_loaders(d, ep, "manifest.json")

    def test_invalid_json_names_the_file(self):
        for rel in ("grader/provenance.json", "public/policy.json", "public/manifest.json"):
            with self.subTest(rel), tempfile.TemporaryDirectory() as d:
                ep = Path(d) / "ep"
                shutil.copytree(self.SRC, ep)
                (ep / rel).write_text("{not json", encoding="utf-8")
                self.check_all_loaders(d, ep, Path(rel).name)

    def test_invalid_jsonl_names_the_file(self):
        for name in ("invoices.jsonl", "payments.jsonl"):
            for label, text in {"bad line": "{not json\n", "deep nesting": "[" * 200000}.items():
                with self.subTest(name=name, case=label), tempfile.TemporaryDirectory() as d:
                    ep = Path(d) / "ep"
                    shutil.copytree(self.SRC, ep)
                    (ep / "public" / name).write_text(text, encoding="utf-8")
                    self.check_all_loaders(d, ep, name)

    def test_deeply_nested_truth_is_a_format_error(self):
        with tempfile.TemporaryDirectory() as d:
            ep = Path(d) / "ep"
            shutil.copytree(self.SRC, ep)
            (ep / "grader" / "truth.json").write_text("[" * 200000, encoding="utf-8")
            with self.assertRaises(EpisodeFormatError) as cm:
                load_episode(ep)
            self.assertIn("truth.json", str(cm.exception))
            self.check_all_loaders(d, ep, "truth.json")


class RandomPolicySeeding(unittest.TestCase):
    def test_one_stream_per_episode(self):
        eps = load_split_episodes(("dev",))
        steps = []
        for _split, _name, ep in eps:
            traj, g = run_one(ep, "random", split="dev", mode="eval", isolated=False, policy_seed=0)
            steps.append(g["inspection_steps"])
        self.assertGreaterEqual(len(set(steps)), 3, steps)

    def test_deterministic_for_same_episode(self):
        ep = load_episode(ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy")
        a = run_one(ep, "random", isolated=False)[0]
        b = run_one(ep, "random", isolated=False)[0]
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        c = run_one(ep, "random", isolated=False, policy_seed=1)[0]
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))


class StressHelpers(unittest.TestCase):
    def test_seventeen_valid_extremes(self):
        ex = stress.extreme_configs()
        self.assertEqual(len(ex), 17)
        for _name, _seed, cfg in ex:
            cfgmod.validate(cfg)

    def test_random_configs_valid_and_reproducible(self):
        a = stress.random_configs(40)
        self.assertEqual(a, stress.random_configs(40))
        for _name, _seed, cfg in a:
            cfgmod.validate(cfg)

    def test_tiny_stress_run_writes_report(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(stress, "extreme_configs", lambda: []):
            self.assertEqual(stress.run_stress(1, Path(d), quiet=True, trace=False), 0)
            text = (Path(d) / "report.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# auditgym stress run"))
            self.assertIn("verify failed", text)


class CanSwitchUserTests(unittest.TestCase):
    """A root host with AUDITGYM_AGENT_USER set but without CAP_SETUID, CAP_SETGID or CAP_CHOWN (docker --cap-drop ALL)
    has an identity, yet the policy child falls back to the host's user. The guard must treat that as same-user."""

    IDENT = ("agent", 1000, 1000)

    def test_guard_refuses_a_closed_run_when_the_child_cannot_switch(self):
        import argparse

        args = argparse.Namespace(in_process=False, seeds_file="seeds.json", secret_env=None, allow_same_user=False)
        policy = "examples.custom_policy:FirstPagePolicy"
        env = {k: v for k, v in os.environ.items() if k != protocol.REQUIRE_ENV}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(protocol, "_can_switch_user", return_value=False):
                with self.assertRaises(cli_mod.InputError) as ctx:
                    cli_mod._custom_policy_guard([policy], args)
                self.assertIn("official image", str(ctx.exception))
                self.assertNotIn("drop --in-process", str(ctx.exception))
            with mock.patch.object(protocol, "_can_switch_user", return_value=True):
                cli_mod._custom_policy_guard([policy], args)  # the child runs as the policy user: no refusal
                args.in_process = True
                with self.assertRaises(cli_mod.InputError) as ctx:
                    cli_mod._custom_policy_guard([policy], args)
                self.assertIn("drop --in-process", str(ctx.exception))

    def test_closed_run_refuses_the_host_user_fallback_when_the_account_already_has_processes(self):
        # the guard predicts a switch (identity, /proc, capabilities) but AgentProcess would fall back to the host user
        # because the policy account already has processes: on a closed run that is an error, not a warning
        import argparse

        args = argparse.Namespace(in_process=False, seeds_file="seeds.json", secret_env=None, allow_same_user=False)
        env = {k: v for k, v in os.environ.items() if k != protocol.REQUIRE_ENV}
        env["AUDITGYM_AGENT_USER"] = "agent"
        started = []
        self.addCleanup(protocol.forbid_same_user_for_custom, False)
        self.addCleanup(protocol.allow_same_user_fallback, False)
        with mock.patch.dict(os.environ, env, clear=True),                 mock.patch.object(protocol.aio, "agent_identity", return_value=self.IDENT),                 mock.patch.object(protocol, "_proc_listable", return_value=True),                 mock.patch.object(protocol, "_caps_allow_switch", return_value=True),                 mock.patch.object(protocol, "_uid_pids", return_value=[4242]),                 mock.patch.object(protocol, "_SWITCHED", False), mock.patch.object(protocol, "_WARNED", False),                 mock.patch.object(protocol.subprocess, "Popen", side_effect=lambda *a, **k: started.append(1)):
            cli_mod._custom_policy_guard(["examples.custom_policy:FirstPagePolicy"], args)  # predicted switch: passes
            with self.assertRaises(protocol.AgentUserRequired) as ctx:
                protocol.AgentProcess("examples.custom_policy:FirstPagePolicy")
            self.assertIn("--allow-same-user", str(ctx.exception))
            self.assertEqual(started, [])  # no child was started as the host user
            # a built-in policy on the same run is not affected (the fallback only warns)
            stub = mock.Mock(_policy_name="silent")
            try:
                protocol.AgentProcess._same_user(stub, "test")
            except protocol.AgentUserRequired:
                self.fail("built-in policies keep the warning")
            # with --allow-same-user the flag is not set
            args.allow_same_user = True
            cli_mod._custom_policy_guard(["examples.custom_policy:FirstPagePolicy"], args)
            self.assertFalse(protocol._NO_SAME_USER_EXTERNAL)

    def test_allow_same_user_is_recorded_when_the_child_falls_back_to_the_host_user(self):
        # the guard predicted a switch; AgentProcess then fell back (account has processes, chown or setuid refused):
        # with --allow-same-user the run goes on as the host user and meta.json says so; without it nothing is written
        seeds = self.seeds_file_for_run()
        policy = "examples.custom_policy:FirstPagePolicy"
        real_popen = subprocess.Popen
        ep = ROOT / "episodes" / "dev" / "d01_clean_repeats_jpy"
        for data, fallback, allow in [(dt, fb, al) for dt in ("seeds", "keys") for fb in ("pids", "chown", "setuid")
                                      for al in (False, True)]:
            if True:
                with self.subTest(data=data, fallback=fallback, allow=allow), tempfile.TemporaryDirectory() as d:
                    out = Path(d) / "run"
                    if data == "keys":  # an answer-key directory outside the committed open episodes
                        shutil.copytree(ep, Path(d) / "keys_ep")
                    started = []

                    def popen(cmd, *a, **k):
                        as_user = k.pop("user", None)
                        for key in ("group", "extra_groups", "umask", "start_new_session"):
                            k.pop(key, None)
                        if as_user is not None and fallback == "setuid":
                            raise PermissionError(1, "Operation not permitted")
                        started.append("agent" if as_user is not None else "host")
                        return real_popen(cmd, *a, **k)

                    def chown(*a, **k):
                        if fallback == "chown":
                            raise PermissionError(1, "Operation not permitted")

                    env = {k: v for k, v in os.environ.items() if k != protocol.REQUIRE_ENV}
                    env["AUDITGYM_AGENT_USER"] = "agent"
                    data_args = (["--seeds-file", seeds, "--no-secret"] if data == "seeds"
                                 else ["--episodes", str(Path(d) / "keys_ep")])
                    argv = ["run", *data_args, "--policies", policy, "--out", str(out), "--max-steps", "3"]
                    if allow:
                        argv.append("--allow-same-user")
                    err = io.StringIO()
                    with contextlib.ExitStack() as st:
                        st.enter_context(mock.patch.dict(os.environ, env, clear=True))
                        st.enter_context(mock.patch.object(protocol.aio, "agent_identity", return_value=self.IDENT))
                        st.enter_context(mock.patch.object(protocol.aio, "private_files", contextlib.nullcontext))
                        st.enter_context(mock.patch.object(protocol, "_proc_listable", return_value=True))
                        st.enter_context(mock.patch.object(protocol, "_caps_allow_switch", return_value=True))
                        st.enter_context(mock.patch.object(protocol, "_uid_pids", return_value=[4242] if fallback == "pids" else []))
                        st.enter_context(mock.patch.object(protocol, "kill_uid", return_value=True))
                        st.enter_context(mock.patch.object(protocol, "_chown_tree", side_effect=chown))
                        st.enter_context(mock.patch.object(protocol, "_SWITCHED", False))
                        st.enter_context(mock.patch.object(protocol, "_WARNED", False))
                        st.enter_context(mock.patch.object(protocol.subprocess, "Popen", side_effect=popen))
                        st.enter_context(mock.patch.object(os, "geteuid", return_value=0, create=True))
                        st.enter_context(mock.patch.object(os, "getegid", return_value=0, create=True))
                        st.enter_context(contextlib.redirect_stderr(err))
                        st.enter_context(contextlib.redirect_stdout(io.StringIO()))
                        code = cli_mod.main(argv)
                    self.assertFalse(protocol._NO_SAME_USER_EXTERNAL)
                    self.assertFalse(protocol._SAME_USER_ALLOWED_CLOSED)
                    if allow:
                        self.assertEqual(code, 0, err.getvalue())
                        self.assertEqual(set(started), {"host"})
                        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
                        self.assertIs(meta["allow_same_user"], True)
                        self.assertIn("--allow-same-user", err.getvalue())
                        self.assertEqual(err.getvalue().count("WARNING: custom policy"), 1, err.getvalue())
                        if data == "keys":
                            self.assertIn("answer keys", err.getvalue())
                            self.assertNotIn("seeds file", err.getvalue())
                    else:
                        if data == "keys":
                            self.assertIn("answer keys", err.getvalue())
                        self.assertEqual(code, 2, err.getvalue())
                        self.assertEqual(started, [])
                        self.assertFalse(out.exists(), "a refused run writes nothing")

    def seeds_file_for_run(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = Path(d) / "seeds.json"
        f.write_text(json.dumps({"split": "t", "episodes": [{"name": "c_ok", "seed": 6602239917354212077,
                                                             "config": {"size": "small", "period": "2026-05"}}]}), encoding="utf-8")
        return str(f)

    def test_guard_is_the_helper_not_the_bare_identity(self):
        # identity and /proc present, capabilities gone: the same refusal as for a host without an identity
        import argparse

        args = argparse.Namespace(in_process=False, seeds_file="seeds.json", secret_env=None, allow_same_user=False)
        env = {k: v for k, v in os.environ.items() if k != protocol.REQUIRE_ENV}
        with mock.patch.dict(os.environ, env, clear=True),                 mock.patch.object(protocol.aio, "agent_identity", return_value=self.IDENT),                 mock.patch.object(protocol, "_proc_listable", return_value=True),                 mock.patch.object(protocol, "_caps_allow_switch", return_value=False):
            with self.assertRaises(cli_mod.InputError):
                cli_mod._custom_policy_guard(["examples.custom_policy:FirstPagePolicy"], args)


if __name__ == "__main__":
    unittest.main()
