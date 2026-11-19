"""Template for plugging your own policy (an organizer baseline, a scripted agent,
or an LLM wrapper) into auditgym's isolated runner.

A policy is any class with `act(observation, reward, info) -> action`. It runs
in the child process and sees observations only. Run it with:

    python -m auditgym run --episodes episodes/dev --policies examples.custom_policy:FirstPagePolicy --out runs/custom

A module outside this repository can be loaded with --policy-path DIR.
"""

from __future__ import annotations


class FirstPagePolicy:
    """Reads the first ledger page, then submits an empty answer."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.episode_id = None

    def act(self, observation: dict, reward: float = 0.0, info: dict | None = None) -> dict:
        if "task" in observation:  # reset observation: task, manifest, policy, remaining_steps
            self.episode_id = observation["manifest"]["episode_id"]
            return {"action": "list_records", "table": "ledger", "cursor": None, "limit": 50}
        # later observations: result, error, remaining_steps
        return {"action": "submit", "findings": {"episode_id": self.episode_id, "findings": []}}
