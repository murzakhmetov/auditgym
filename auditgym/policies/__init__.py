"""Baseline policy adapters.

Agent-side (may run in the isolated child process): random, recon, flag_all, auditor.
Grader-side only: oracle (reads the answer key; never runs in the agent process).

External policies plug in as "module.path:ClassName": any class with
`act(observation, reward, info) -> action`, constructed with `seed=` when its
constructor accepts it. Use --policy-path DIR for modules outside this repository.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from importlib.machinery import PathFinder
from pathlib import Path

AGENT_POLICIES = ("random", "recon", "flag_all", "auditor")
GRADER_POLICIES = ("oracle",)
BASELINES = ("random", "recon", "flag_all", "oracle")
_EXTERNAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$")


class PolicyError(ValueError):
    pass


def is_external(name: str) -> bool:
    return bool(_EXTERNAL.match(name or ""))


def validate_policy_name(name: str, policy_path: str | None = None) -> None:
    """Raise PolicyError unless `name` is a built-in policy or an importable module:Class.
    The module is located but not executed."""
    if name in AGENT_POLICIES or name in GRADER_POLICIES:
        return
    if not is_external(name):
        raise PolicyError(f"unknown policy {name!r}; use one of {', '.join(AGENT_POLICIES + GRADER_POLICIES)} "
                          "or module.path:ClassName")
    module = name.split(":")[0]
    search = [str(Path(__file__).resolve().parents[2])] + ([str(Path(policy_path).resolve())] if policy_path else []) + sys.path
    parts = module.split(".")
    found = True
    for i in range(len(parts)):
        try:
            spec = PathFinder.find_spec(".".join(parts[: i + 1]), search)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            found = False
            break
        search = list(spec.submodule_search_locations or [])
        if i < len(parts) - 1 and not search:
            found = False
            break
    if not found:
        raise PolicyError(f"policy module {module!r} not found" + (f" (also searched {policy_path})" if policy_path else ""))


def make_policy(name: str, seed: int = 0, truth: dict | None = None):
    if name == "random":
        from .random_policy import RandomPolicy

        return RandomPolicy(seed=seed)
    if name == "flag_all":
        from .flag_all import FlagAllPolicy

        return FlagAllPolicy()
    if name == "recon":
        from .recon import ReconPolicy

        return ReconPolicy()
    if name == "auditor":
        from .auditor_policy import AuditorPolicy

        return AuditorPolicy()
    if name == "oracle":
        if truth is None:
            raise PolicyError("the oracle needs the answer key and runs grader-side only")
        from .oracle import OraclePolicy

        return OraclePolicy(truth)
    if is_external(name):
        module_name, cls_name = name.split(":")
        cls = getattr(importlib.import_module(module_name), cls_name, None)
        if cls is None or not callable(cls):
            raise PolicyError(f"{name!r}: class {cls_name!r} not found")
        try:
            accepts_seed = "seed" in inspect.signature(cls).parameters
        except (TypeError, ValueError):
            accepts_seed = False
        policy = cls(seed=seed) if accepts_seed else cls()
        if not callable(getattr(policy, "act", None)):
            raise PolicyError(f"{name!r} has no act(observation, reward, info) method")
        return policy
    raise PolicyError(f"unknown policy {name!r}")
