"""Child-process entry point: `python -m auditgym.agent --policy NAME`.

Reads observations from stdin, writes actions to stdout. NAME is a built-in
agent-side policy (random, recon, flag_all, auditor) or "module.path:ClassName".
The oracle needs the answer key and is refused here: it runs grader-side.
"""

from __future__ import annotations

import argparse
import json
import sys

from .policies import GRADER_POLICIES, PolicyError, make_policy


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--policy-seed", type=int, default=0)
    args = parser.parse_args(argv)
    if args.policy in GRADER_POLICIES:
        print("the oracle runs grader-side only", file=sys.stderr)
        return 2
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
        sys.stdout.write(json.dumps({"type": "action", "action": action}, ensure_ascii=True) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
