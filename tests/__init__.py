"""Test helpers shared by the modules that model a same-user child."""

import os

_SAVED = {}


def same_user_start(name: str) -> None:
    """Call from setUpModule of a module whose tests plant files in temporary directories or in a
    copy of the repository and expect the policy child to be the same OS user as the host (the
    threat those tests model). Inside the official image the policy would otherwise run as the
    separate `agent` user; that behaviour is tested by tests/test_container.py. Strict mode
    (AUDITGYM_REQUIRE_AGENT_USER=1) is switched off too: it forbids exactly this same-user child."""
    _SAVED[name] = os.environ.pop("AUDITGYM_AGENT_USER", None)
    _SAVED[name + ":strict"] = os.environ.pop("AUDITGYM_REQUIRE_AGENT_USER", None)


def same_user_stop(name: str) -> None:
    value = _SAVED.pop(name, None)
    if value is not None:
        os.environ["AUDITGYM_AGENT_USER"] = value
    strict = _SAVED.pop(name + ":strict", None)
    if strict is not None:
        os.environ["AUDITGYM_REQUIRE_AGENT_USER"] = strict
