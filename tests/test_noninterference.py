"""Noninterference: the agent's whole view (observation, reward, terminated, truncated, info)
is byte-identical when only grader-side files change.

Variants of the answer key (all schema-valid): shuffled issues with altered amounts and
evidence, another episode's truth under this episode_id, and an empty key without
provenance. The same policies run in-process and through the isolated child process.
Eval mode must match at every step; train mode up to the terminal step.
"""

import copy
import dataclasses
import json
import random
import tempfile
import unittest
from pathlib import Path

from auditgym import io as aio
from auditgym import protocol
from auditgym.env import AuditEnv
from auditgym.episode import load_episode
from auditgym.policies import make_policy
from auditgym.schema_files import TRUTH, validate
from examples.hostile.policies import IdProbe

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"t07": "train/t07_boundary_fx_payment", "d04": "dev/d04_unallocated_missing_eur",
         "d08": "dev/d08_both_interacting_kzt"}
_EPISODES: dict = {}


def load(key: str):
    if key not in _EPISODES:
        _EPISODES[key] = load_episode(ROOT / "episodes" / NAMES[key])
    return _EPISODES[key]


def target_ids(ep) -> list:
    ids = set()
    for issue in ep.truth["issues"]:
        ids.update(issue["affected_ids"])
        for es in issue["evidence_sets"]:
            ids.update(es)
    for k, v in ep.truth["id_aliases"].items():
        ids.update((k, v))
    return sorted(ids)


def probe_for(ep):
    return type("Probe", (IdProbe,), {"TARGETS": tuple(target_ids(ep))})()


def variants(ep, other) -> dict:
    """Grader-only variants of `ep`. The public part is shared and untouched."""
    shuffled = copy.deepcopy(ep.truth)
    random.Random(7).shuffle(shuffled["issues"])
    for i, issue in enumerate(shuffled["issues"]):
        issue["expected_amount_minor"] += 12345 + i
        issue["evidence_sets"] = [list(reversed(es)) + [f"GHOST-{i}"] if len(es) < 10 else es
                                  for es in issue["evidence_sets"]]
        issue["explanation"] = "altered " + issue["explanation"]
    shuffled["id_aliases"] = dict(reversed(list(shuffled["id_aliases"].items())))
    foreign = copy.deepcopy(other.truth)
    foreign["episode_id"] = ep.episode_id
    empty = {"schema_version": ep.truth["schema_version"], "episode_id": ep.episode_id, "issues": [], "id_aliases": {}}
    out = {
        "shuffled_altered": dataclasses.replace(ep, truth=shuffled),
        "foreign_truth": dataclasses.replace(ep, truth=foreign, provenance=copy.deepcopy(other.provenance)),
        "empty_key": dataclasses.replace(ep, truth=empty, provenance={}),
    }
    for name, v in out.items():
        errors = validate(v.truth, TRUTH)
        assert not errors, (name, errors)
    return out


def canon(obj) -> str:
    return aio.canonical_json(obj)


def play_in_process(ep, policy, mode: str) -> list:
    """Transitions (obs, reward, terminated, truncated, info); the reset observation comes first."""
    env = AuditEnv(mode=mode)
    obs, info = env.reset(config={"episode": ep})
    log = [(obs, 0.0, False, False, info)]
    reward = 0.0
    while True:
        action = policy.act(obs, reward, info)
        obs, reward, terminated, truncated, info = env.step(action)
        log.append((obs, reward, terminated, truncated, info))
        if terminated or truncated:
            return log


class _SpyAgent(protocol.AgentProcess):
    sent: list = []

    def send(self, message, *a, **k):
        if message.get("type") == "observation":
            type(self).sent.append((message["observation"], message["reward"], message["terminated"],
                                    message["truncated"], message["info"]))
        return super().send(message, *a, **k)


def play_isolated(ep, policy: str, mode: str, policy_path=None) -> list:
    """Exactly what the child process was sent, message by message."""
    _SpyAgent.sent = []
    real = protocol.AgentProcess
    protocol.AgentProcess = _SpyAgent
    try:
        env = AuditEnv(mode=mode)
        res = protocol.run_episode_isolated(env, {"config": {"episode": ep}}, policy, 0, policy_path=policy_path)
    finally:
        protocol.AgentProcess = real
    assert res["agent_error"] is None, res["agent_error"]
    return list(_SpyAgent.sent)


def view(log, mode: str) -> list:
    log = list(log)
    if mode == "train":
        log = log[:-1]  # the terminal step may carry the reward and the final counts
    return [canon(t) for t in log]


class NoninterferenceTests(unittest.TestCase):
    def test_grader_variants_do_not_change_any_observation(self):
        replays = 0
        for key in NAMES:
            ep = load(key)
            vs = variants(ep, load("d04" if key != "d04" else "t07"))
            makers = {"random0": lambda: make_policy("random", seed=0), "random1": lambda: make_policy("random", seed=1),
                      "recon": lambda: make_policy("recon"), "auditor": lambda: make_policy("auditor"),
                      "probe": lambda ep=ep: probe_for(ep)}
            for pname, mk in makers.items():
                for mode in ("eval", "train"):
                    base = play_in_process(ep, mk(), mode)
                    for vname, v in vs.items():
                        got = play_in_process(v, mk(), mode)
                        replays += 1
                        self.assertEqual(view(base, mode), view(got, mode), (key, pname, mode, vname))
                        if mode == "eval":
                            self.assertEqual(canon(base), canon(got), (key, pname, vname))  # incl. the terminal step
        self.assertGreaterEqual(replays, 36)

    def test_variants_actually_change_the_grader(self):
        def report(e):
            env = AuditEnv(mode="eval")
            env.reset(config={"episode": e})
            env.step({"action": "submit", "findings": {"episode_id": e.episode_id, "findings": []}})
            return json.dumps(env.grader_report(), sort_keys=True, default=str)

        for key in NAMES:
            ep = load(key)
            base = report(ep)
            vs = variants(ep, load("d04" if key != "d04" else "t07"))
            self.assertTrue(any(report(v) != base for v in vs.values()), key)

    def test_probe_learns_nothing_from_the_answer_key_ids(self):
        ep = load("d08")
        self.assertGreater(len(target_ids(ep)), 10)
        log = play_in_process(ep, probe_for(ep), "eval")
        self.assertTrue(all(t[1] == 0.0 for t in log))
        self.assertNotIn("iss_", json.dumps([t[0] for t in log]))

    def test_isolated_child_view_is_independent_of_the_answer_key(self):
        ep = load("d08")
        vs = variants(ep, load("t07"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "probe_mod.py").write_text(
                "from examples.hostile.policies import IdProbe\n"
                f"class Probe(IdProbe):\n    TARGETS = {tuple(target_ids(ep))!r}\n", encoding="utf-8")
            for pol, path, inproc in (("auditor", None, make_policy("auditor")),
                                      ("probe_mod:Probe", tmp, probe_for(ep))):
                base = play_isolated(ep, pol, "eval", path)
                self.assertEqual(view(base, "eval"), view(play_in_process(ep, inproc, "eval"), "eval"), pol)
                for vname, v in ("shuffled_altered", vs["shuffled_altered"]),:  # one variant keeps the test fast
                    got = play_isolated(v, pol, "eval", path)
                    self.assertEqual(view(base, "eval"), view(got, "eval"), (pol, vname))
        # train mode: identical up to the terminal step for the child as well
        base = play_isolated(ep, "recon", "train")
        got = play_isolated(vs["empty_key"], "recon", "train")
        self.assertEqual(view(base, "train"), view(got, "train"))


if __name__ == "__main__":
    unittest.main()
