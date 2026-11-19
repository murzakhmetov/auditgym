"""Child-process entry point: `python -m auditgym.agent --policy NAME`.

Reads observations from stdin, writes actions to the protocol channel. NAME is a built-in
agent-side policy (random, recon, flag_all, auditor) or "module.path:ClassName".
The oracle needs the answer key and is refused here: it runs grader-side.

Protocol channel: before the policy is loaded, the real stdout is duplicated to a private
descriptor (not inherited by the policy's own subprocesses) and fd 1 / sys.stdout are
pointed at stderr. A stray print() in a policy, or a library writing to stdout, therefore
lands in the host's bounded stderr tail and cannot shift the line-by-line protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .policies import GRADER_POLICIES, PolicyError, make_policy

PROTOCOL_OUT = None  # binary writer on the private protocol descriptor (set by main)


def _claim_protocol_channel():
    try:
        sys.stdout.flush()
    except Exception:
        pass
    fd = os.dup(1)  # non-inheritable duplicate of the pipe to the host
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    if os.name == "nt":  # processes started with default handles must not inherit the protocol pipe either
        try:
            import ctypes
            import msvcrt

            ctypes.windll.kernel32.SetStdHandle(-11, msvcrt.get_osfhandle(2))
        except Exception:
            pass
    return os.fdopen(fd, "wb")


def main(argv=None) -> int:
    global PROTOCOL_OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--policy-seed", type=int, default=0)
    args = parser.parse_args(argv)
    if args.policy in GRADER_POLICIES:
        print("the oracle runs grader-side only", file=sys.stderr)
        return 2
    out = PROTOCOL_OUT = _claim_protocol_channel()
    if __name__ == "__main__":
        sys.modules.setdefault("auditgym.agent", sys.modules[__name__])  # `import auditgym.agent` sees PROTOCOL_OUT
    try:
        policy = make_policy(args.policy, seed=args.policy_seed)
    except (PolicyError, ImportError, AttributeError) as exc:
        print(f"cannot load policy: {exc}", file=sys.stderr)
        return 2
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("type") == "end":
            break
        if msg.get("type") != "observation":
            continue
        if msg.get("terminated") or msg.get("truncated"):
            continue
        action = policy.act(msg["observation"], msg.get("reward", 0.0), msg.get("info", {}))
        out.write((json.dumps({"type": "action", "action": action}, ensure_ascii=True) + "\n").encode("ascii"))
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
