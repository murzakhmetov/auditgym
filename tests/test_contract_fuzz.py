"""Contract fuzzer and two-way agreement between the published schemas and the environment.

3,000 actions in-process and 300 raw lines through AgentProcess, all seeded with Rng("auditgym-fuzz-v1").
After every call the invariants below must hold; the same seed must replay byte for byte; and an action is
schema-valid exactly when the environment raises no structural error.

Structural error codes: bad_args, unknown_action, unknown_table, invalid_submission.
Semantic codes are exceptions: a schema-valid action may still return unknown_id, bad_cursor, calc_error
(the 200-token limit, empty or malformed expressions, division by zero) or, for submit, invalid_submission
because episode_id is not the current episode (a JSON Schema cannot know it).
"""

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from auditgym import calculator, protocol
from auditgym import io as aio
from auditgym import schema_files as sf
from auditgym import schemas
from auditgym.env import AuditEnv
from auditgym.episode import load_episode
from auditgym.rng import Rng
from auditgym.task import build_task
from tests import fuzz_policies as fz
from tests import same_user_start, same_user_stop
from tests.test_env import episode
from tests.test_matcher import GOOD

ROOT = Path(__file__).resolve().parent.parent
EPISODES = sorted(p for split in ("train", "dev") for p in (ROOT / "episodes" / split).glob("*") if (p / "public").exists())
STRUCTURAL = {"bad_args", "unknown_action", "unknown_table", "invalid_submission"}
IN_PROCESS_ACTIONS = 3000
PIPED_EPISODES = 3
PIPED_LINES = 100
MAX_STEPS = 100


def make_ctx(ep) -> dict:
    truth = ep.truth
    grader_ids = [i["issue_id"] for i in truth["issues"]] + [e for i in truth["issues"] for s in i["evidence_sets"] for e in s][:20]
    grader_ids += list(truth.get("id_aliases", {}))[:10]
    return {
        "episode_id": ep.episode_id,
        "ids": {t: [ep.record_key(t, r) for r in ep.table(t)] for t in schemas.TABLES},
        "docs": [r["doc_id"] for t in ("invoices", "payments") for r in ep.table(t)],
        "grader_ids": grader_ids or ["iss_01"],
        "sizes": {t: len(ep.table(t)) for t in schemas.TABLES},
    }


def unwrap(action):
    """The environment's own alias rule, restated: {"action", "args": {...}} means {"action", **args}."""
    if isinstance(action, dict) and set(action) == {"action", "args"} and isinstance(action["args"], dict) \
            and "action" not in action["args"]:
        return {"action": action["action"], **action["args"]}
    return action


def expected_structural(action, episode_id) -> bool:
    """True when the published schema says the action is malformed (or a submission names the wrong episode)."""
    if sf.validate(action, sf.ACTION_JSON_SCHEMA):
        return True
    flat = unwrap(action)
    if isinstance(flat, dict) and flat.get("action") == "submit":
        return flat["findings"]["episode_id"] != episode_id  # semantic exception: the schema cannot know it
    return False


def short(value, n=120) -> str:
    try:
        return repr(value)[:n]
    except Exception:  # RecursionError on deeply nested input
        return f"<{type(value).__name__} that cannot be printed>"


def long_strings(value, out=None, depth=0):
    out = [] if out is None else out
    if isinstance(value, str):
        if len(value) > 64:
            out.append(value)
    elif isinstance(value, dict) and depth < 8:
        for k, v in value.items():
            long_strings(k, out, depth + 1)
            long_strings(v, out, depth + 1)
    elif isinstance(value, list) and depth < 8:
        for v in value:
            long_strings(v, out, depth + 1)
    return out


class Checker:
    """Per-call invariants. Violations and agreement problems are collected as strings, never raised."""

    def __init__(self):
        self.violations: list = []
        self.disagreements: list = []
        self.codes: Counter = Counter()
        self.events: Counter = Counter()

    def v(self, label, msg):
        self.violations.append(f"{label}: {msg}")

    def check_live(self, label, action, obs, flags, prev_remaining, episode_id, mode):
        reward, terminated, truncated = flags
        err = obs.get("error") if isinstance(obs, dict) else None
        if not isinstance(obs, dict) or set(obs) != {"result", "error", "remaining_steps"}:
            self.v(label, f"observation keys {sorted(obs) if isinstance(obs, dict) else type(obs)}")
            return
        code = err["code"] if err else None
        self.codes[code] += 1
        if code == "internal_error":
            self.v(label, f"internal_error for {short(action, 80)}")
        if err is not None:
            if set(err) != {"code", "message"} or not isinstance(err["message"], str):
                self.v(label, f"error shape {err!r}"[:200])
            elif len(err["message"]) > 200:
                self.v(label, f"message of {len(err['message'])} characters")
            if obs["result"] is not None:
                self.v(label, "result and error both set")
            if len(json.dumps(obs, ensure_ascii=True)) > 600:
                self.v(label, "error observation is large")
            for s in long_strings(action):
                if s[:65] in err["message"]:
                    self.v(label, "message echoes more than 64 characters of the input")
                    break
        elif obs["result"] is None:
            self.v(label, "neither result nor error")
        if obs["remaining_steps"] != prev_remaining - 1:
            self.v(label, f"remaining_steps {prev_remaining} -> {obs['remaining_steps']}")
        if terminated and truncated:
            self.v(label, "terminated and truncated are both true")
        if mode == "eval" and reward != 0.0:
            self.v(label, "eval mode returned a reward")
        if reward != 0.0 and not (terminated or truncated):
            self.v(label, "non-zero reward before the end")
        if code == "time_limit":
            self.v(label, "unexpected time_limit")
        exp = expected_structural(action, episode_id)  # two-way, on every live step including the last one
        if exp != (code in STRUCTURAL):
            self.disagreements.append(f"{label}: schema says structural={exp}, env code={code}, action={short(action)}")


def run_in_process(n: int = IN_PROCESS_ACTIONS):
    """Returns (checker, digest, stats). Deterministic: every random choice comes from Rng('auditgym-fuzz-v1')."""
    ep = episode()
    ctx = make_ctx(ep)
    rng = Rng(fz.MASTER).fork("inproc")
    envs = {"train": AuditEnv(mode="train"), "eval": AuditEnv(mode="eval")}
    chk, h, stats = Checker(), hashlib.sha256(), Counter()
    i, epi = 0, 0
    while i < n:
        epi += 1
        mode = "train" if epi % 2 else "eval"
        env = envs[mode]
        allow_submit = epi % 4 in (1, 2)             # epochs 0 and 3 mod 4 run into the step limit (one train, one eval)
        env.reset(config={"episode": ep})
        prev = MAX_STEPS
        while i < n:
            action = fz.gen_action(rng, ctx, allow_submit=allow_submit)
            label = f"#{i}"
            obs, reward, term, trunc, info = env.step(action)
            i += 1
            chk.check_live(label, action, obs, (reward, term, trunc), prev, ep.episode_id, mode)
            prev = obs["remaining_steps"]
            h.update(json.dumps([obs, reward, term, trunc, info.get("final")], sort_keys=True, ensure_ascii=True).encode())
            if env.steps != MAX_STEPS - prev:
                chk.v(label, "env.steps disagrees with remaining_steps")
            if term or trunc:
                break
        if not env.done:
            continue
        rep = env.grader_report()
        status = rep["status"]
        stats[status] += 1
        stats[f"{mode}:{status}"] += 1
        if status == "step_limit":
            if not (trunc and not term and env.steps == MAX_STEPS):
                chk.v(f"ep{epi}", f"step limit flags term={term} trunc={trunc} steps={env.steps}")
            if rep["n_findings"] != 0 or rep["tp"] != 0 or rep["fp"] != 0:
                chk.v(f"ep{epi}", "truncated episode did not record an empty answer")
        elif status in ("submitted", "invalid_submission"):
            if trunc or not term:
                chk.v(f"ep{epi}", f"submit ended with term={term} trunc={trunc}")
            if (status == "invalid_submission") != (not rep["valid"]) or (status == "invalid_submission" and rep["reward"] != -1):
                chk.v(f"ep{epi}", "invalid_submission, valid flag and reward -1 disagree")
        else:
            chk.v(f"ep{epi}", f"unexpected final status {status}")
        if mode == "train" and reward != rep["reward"]:
            chk.v(f"ep{epi}", "terminal reward differs from the grader report")
        # after the end: the same refusal every time and the grader report never changes
        before = copy.deepcopy(rep)
        for j in range(3):
            if i >= n:
                break
            action = fz.gen_action(rng, ctx, allow_submit=True)
            obs, r2, t2, u2, _ = env.step(action)
            i += 1
            stats["after_end"] += 1
            if obs["error"] is None or obs["error"]["code"] != "episode_finished" or obs["result"] is not None:
                chk.v(f"#{i - 1}", f"after the end: {obs!r}"[:160])
            if r2 != 0.0 or (t2, u2) != (term, trunc) or obs["remaining_steps"] != prev:
                chk.v(f"#{i - 1}", "after the end: flags, reward or budget changed")
            if env.grader_report() != before:
                chk.v(f"#{i - 1}", "after the end: the grader report changed")
            h.update(json.dumps([obs, r2, t2, u2], sort_keys=True).encode())
    return chk, h.hexdigest(), stats


def setUpModule():
    same_user_start(__name__)  # the piped child imports tests.* from the repo root: same user


def tearDownModule():
    same_user_stop(__name__)


def run_piped():
    """300 raw lines through AgentProcess (3 episodes of 100). Returns (checker, digest, count)."""
    ep = episode()
    chk, h, total = Checker(), hashlib.sha256(), 0
    real_popen = subprocess.Popen
    for idx in range(PIPED_EPISODES):
        lines = fz.raw_lines(idx, PIPED_LINES, ep.episode_id)  # the child builds the same list
        recs: list = []

        def popen(cmd, **kw):
            if kw.get("env") is not None:  # the protocol may stage the child's import path; the fuzz policy needs the project root
                kw["env"] = dict(kw["env"], PYTHONPATH=str(ROOT))
            return real_popen([sys.executable, "-m", "tests.fuzz_policies", str(idx), str(PIPED_LINES)], **kw)

        env = AuditEnv(mode="train")
        with mock.patch.object(protocol.subprocess, "Popen", popen):
            res = protocol.run_episode_isolated(env, {"config": {"episode": ep}}, "tests.fuzz_policies:raw", on_step=recs.append)
        steps = [r for r in recs if r["step"] >= 1]
        if res["agent_error"]:
            chk.v(f"piped{idx}", f"agent error {res['agent_error']}")
        if len(steps) != PIPED_LINES:
            chk.v(f"piped{idx}", f"{len(steps)} steps for {PIPED_LINES} lines")
        prev = MAX_STEPS
        for k, (rec, (kind, text)) in enumerate(zip(steps, lines)):
            label = f"piped{idx}#{k}"
            if rec["observation"]["error"] and rec["observation"]["error"]["code"] in ("agent_exited", "time_limit"):
                chk.v(label, "run stopped early")
                break
            # The protocol decides what is malformed (size, depth and JSON limits may change); ask it, and check the
            # observation rather than the shape of the recorded action.
            expect = protocol.parse_agent_line(text)[0]
            if expect == "malformed":
                err = rec["observation"]["error"]
                if not err or err["code"] != "unknown_action":
                    chk.v(label, "a malformed line did not give unknown_action")
            elif kind == "ok" and expect == "action" and rec["action"] != json.loads(text)["action"]:
                chk.v(label, "the action changed on the way through the pipe")
            chk.check_live(label, rec["action"], rec["observation"], (rec["reward"], rec["terminated"], rec["truncated"]),
                           prev, ep.episode_id, "train")
            prev = rec["observation"]["remaining_steps"]
            h.update(json.dumps([rec["observation"], rec["reward"], rec["terminated"], rec["truncated"]], sort_keys=True).encode())
            total += 1
        rep = res["grade"]
        if idx < 2:
            if not (rep["status"] == "step_limit" and rep["n_findings"] == 0 and steps[-1]["truncated"] and not steps[-1]["terminated"]):
                chk.v(f"piped{idx}", f"step 100 did not truncate with an empty answer: {rep['status']}")
        elif rep["status"] != "submitted" or not steps[-1]["terminated"]:
            chk.v(f"piped{idx}", f"final valid submit gave {rep['status']}")
    return chk, h.hexdigest(), total


class ContractFuzz(unittest.TestCase):
    maxDiff = None

    def test_fuzz_contract(self):
        chk, digest, stats = run_in_process()
        chk2, digest2, _ = run_in_process()
        self.assertEqual(digest, digest2, "the same seed must replay byte for byte")
        pchk, pdigest, piped = run_piped()
        pchk2, pdigest2, _ = run_piped()
        self.assertEqual(pdigest, pdigest2, "the piped part must replay byte for byte")
        violations = chk.violations + pchk.violations
        disagreements = chk.disagreements + pchk.disagreements
        self.assertEqual(violations[:5], [])
        self.assertEqual(disagreements[:5], [])
        # the fuzzer must actually reach the interesting corners
        codes = chk.codes + pchk.codes
        for code in ("bad_args", "unknown_action", "unknown_table", "unknown_id", "bad_cursor", "calc_error",
                     "invalid_submission", None):
            self.assertGreater(codes[code], 0, f"fuzzer never produced {code}")
        self.assertGreater(stats["step_limit"], 0)
        self.assertGreater(stats["submitted"], 0)
        self.assertGreater(stats["invalid_submission"], 0)
        for key in ("train:submitted", "eval:submitted", "train:invalid_submission", "eval:invalid_submission",
                    "train:step_limit", "eval:step_limit"):
            self.assertGreater(stats[key], 0, f"no episode ended as {key}")
        self.assertGreater(stats["after_end"], 0)
        self.assertEqual(piped, PIPED_EPISODES * PIPED_LINES)
        print(f"fuzz: {IN_PROCESS_ACTIONS} in-process + {piped} piped, {len(violations)} invariant violations, "
              f"{len(disagreements)} schema/env disagreements")


class Agreement(unittest.TestCase):
    def test_whitespace_id_rejected_by_schema(self):
        for blank in fz.WS_IDS:
            for field in ("affected_ids", "evidence_ids"):
                f = dict(GOOD[0], **{field: [blank]})
                sub = {"episode_id": "ep_x", "findings": [f]}
                self.assertTrue(sf.validate(sub, sf.SUBMISSION_JSON_SCHEMA), repr(blank))
                self.assertTrue(schemas.validate_submission(sub, "ep_x"), repr(blank))
        env = AuditEnv()
        env.reset(config={"episode": episode()})
        f = dict(GOOD[0], affected_ids=[" "])
        obs, reward, term, _, _ = env.step({"action": "submit", "findings": {"episode_id": env.episode.episode_id, "findings": [f]}})
        self.assertEqual(obs["error"]["code"], "invalid_submission")
        self.assertEqual(reward, -1.0)

    def test_every_python_whitespace_character_is_blank_in_both(self):
        import re
        pat = re.compile(sf.SUBMISSION_JSON_SCHEMA["properties"]["findings"]["items"]["properties"]["affected_ids"]["items"]["pattern"])
        cur = re.compile(sf.SUBMISSION_JSON_SCHEMA["properties"]["findings"]["items"]["properties"]["currency"]["pattern"])
        ws = [chr(c) for c in range(0x110000) if chr(c).isspace()]
        self.assertEqual(len(ws), 29)
        for ch in ws:
            self.assertIsNone(pat.search(ch), hex(ord(ch)))
            self.assertIsNotNone(cur.match(ch + "USD" + ch), hex(ord(ch)))
            self.assertTrue(schemas.validate_submission({"episode_id": "e", "findings": [dict(GOOD[0], affected_ids=[ch])]}, "e"))
            self.assertEqual(schemas.validate_submission({"episode_id": "e", "findings": [dict(GOOD[0], currency=ch + "EUR" + ch)]}, "e"), [])
        self.assertIsNotNone(pat.search("x"))
        self.assertIsNone(cur.match("﻿USD"))
        self.assertTrue(schemas.validate_submission({"episode_id": "e", "findings": [dict(GOOD[0], currency="﻿USD")]}, "e"))

    def test_integral_floats_are_integers_in_schema_and_env(self):
        self.assertEqual(sf.validate({"action": "list_records", "table": "fx", "limit": 1.0}, sf.ACTION_JSON_SCHEMA), [])
        self.assertTrue(sf.validate({"action": "list_records", "table": "fx", "limit": 1.5}, sf.ACTION_JSON_SCHEMA))
        env = AuditEnv()
        env.reset(config={"episode": episode()})
        for lim in (1.0, 1e1, 50.0):
            obs, *_ = env.step({"action": "list_records", "table": "fx", "limit": lim})
            self.assertIsNone(obs["error"], lim)
        for lim in (1.5, float("nan"), float("inf"), True, 0.0, 51.0):
            obs, *_ = env.step({"action": "list_records", "table": "fx", "limit": lim})
            self.assertEqual(obs["error"]["code"], "bad_args", lim)
        f = dict(GOOD[0], claimed_amount_minor=1500.0)
        sub = {"episode_id": env.episode.episode_id, "findings": [f]}
        self.assertEqual(sf.validate(sub, sf.SUBMISSION_JSON_SCHEMA), [])
        obs, reward, *_ = env.step({"action": "submit", "findings": sub})
        self.assertIsNone(obs["error"])

    def test_hostile_keys_do_not_raise(self):
        class Boom:
            def __str__(self):
                raise ValueError("boom")
        key = ()
        for _ in range(5000):
            key = (key,)
        for k in (Boom(), key):
            env = AuditEnv()
            env.reset(config={"episode": episode()})
            obs, *_ = env.step({"action": "calculator", "expression": "1", k: 1})
            self.assertEqual(obs["error"]["code"], "bad_args")
            obs, *_ = env.step({"action": "submit", "findings": {"episode_id": env.episode.episode_id, "findings": []}, k: 1})
            self.assertEqual(obs["error"]["code"], "invalid_submission")

    def test_alias_is_in_the_action_schema(self):
        env = AuditEnv()
        env.reset(config={"episode": episode()})
        for action in ({"action": "list_records", "args": {"table": "fx", "limit": 3}},
                       {"action": "get_document", "args": {"doc_id": env.episode.invoices[0]["doc_id"]}},
                       {"action": "calculator", "args": {"expression": "1+1"}}):
            self.assertEqual(sf.validate(action, sf.ACTION_JSON_SCHEMA), [], action)
            obs, *_ = env.step(action)
            self.assertIsNone(obs["error"], action)
        for action in ({"action": "list_records", "args": {"table": "fx", "x": 1}},
                       {"action": "list_records", "args": {"action": "calculator"}},
                       {"action": "list_records", "args": {}},
                       {"action": "list_records", "table": "fx", "args": {}}):
            self.assertTrue(sf.validate(action, sf.ACTION_JSON_SCHEMA), action)
            obs, *_ = env.step(action)
            self.assertIn(obs["error"]["code"], STRUCTURAL, action)

    def test_calculator_limit_is_published(self):
        self.assertEqual(schemas.MAX_EXPRESSION_CHARS, calculator.MAX_LENGTH)
        self.assertEqual(schemas.MAX_EXPRESSION_TOKENS, calculator.MAX_TOKENS)
        task = build_task(episode(), 100, "train")
        text = task["actions"]["calculator"]["expression"]
        self.assertIn(str(calculator.MAX_LENGTH), text)
        self.assertIn(str(calculator.MAX_TOKENS), text)
        branch = next(b for b in schemas.ACTION_JSON_SCHEMA["oneOf"] if b["properties"]["action"].get("const") == "calculator")
        expr = branch["properties"]["expression"]
        self.assertEqual(expr["maxLength"], 256)
        self.assertIn("200 tokens", expr["description"])
        env = AuditEnv()
        env.reset(config={"episode": episode()})
        ok, *_ = env.step({"action": "calculator", "expression": "1" + "+1" * 99})       # 199 tokens
        self.assertEqual(ok["result"]["value"], "100")
        long, *_ = env.step({"action": "calculator", "expression": "1" + "+1" * 100})    # 201 tokens
        self.assertEqual(long["error"]["code"], "calc_error")
        long, *_ = env.step({"action": "calculator", "expression": "1" * 257})
        self.assertEqual(long["error"]["code"], "bad_args")

    def test_reset_options(self):
        ep = episode()
        env = AuditEnv()
        obs, info = env.reset(options={"config": {"episode": ep}, "unrelated": 1})
        self.assertEqual(info["episode_id"], ep.episode_id)
        obs2, _ = env.reset(config={"episode": ep}, options={"config": {"episode_dir": "does/not/exist"}, "x": [1]})
        self.assertEqual(json.dumps(obs, sort_keys=True), json.dumps(obs2, sort_keys=True))  # explicit config wins
        for junk in (None, {}, {"seed": 5}, {"config": None}, {"config": 7}, 5, "x", [1, 2]):
            o, i = env.reset(config={"episode": ep}, options=junk)
            self.assertEqual(i["episode_id"], ep.episode_id)
        with self.assertRaises(ValueError):
            env.reset(options={"config": None})  # nothing to load: the existing error, not a silent no-op

    def test_deep_and_odd_inputs_never_raise(self):
        env = AuditEnv()
        env.reset(config={"episode": episode()})
        for bad in (fz.nest(5000), {"action": fz.nest(5000)}, {"action": "get_record", "table": fz.nest(5000)},
                    {"action": "get_record", "table": "ledger", "id": fz.nest(5000)}, {"action": "\ud800"}, {"action": "x" * 10_000}):
            obs, *_ = env.step(bad)
            self.assertIn(obs["error"]["code"], STRUCTURAL)
            self.assertLessEqual(len(obs["error"]["message"]), 200)


class SchemaFiles(unittest.TestCase):
    def test_committed_schema_files_equal_generated_ones(self):
        folder = ROOT / "schemas"
        self.assertEqual(sorted(p.name for p in folder.glob("*.json")), sorted(sf.ALL))
        for name, schema in sf.ALL.items():
            doc = {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
            self.assertEqual((folder / name).read_bytes(), aio.dumps_pretty(doc).encode("utf-8"), name)

    def test_policy_and_provenance_files_validate(self):
        self.assertEqual(len(EPISODES), 20)
        for d in EPISODES:
            policy = json.loads((d / "public" / "policy.json").read_text(encoding="utf-8"))
            prov = json.loads((d / "grader" / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(sf.validate(policy, sf.POLICY)[:3], [], d.name)
            self.assertEqual(sf.validate(prov, sf.PROVENANCE)[:3], [], d.name)
            self.assertEqual(load_episode(d).policy, policy)

    def test_provenance_schema_tolerates_extra_keys_but_not_missing_ones(self):
        d = EPISODES[0]
        prov = json.loads((d / "grader" / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(sf.validate(dict(prov, new_key={"a": 1}), sf.PROVENANCE), [])
        broken = {k: v for k, v in prov.items() if k != "final_digest"}
        self.assertTrue(sf.validate(broken, sf.PROVENANCE))


if __name__ == "__main__":
    unittest.main()
