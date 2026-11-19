"""Rewrite the examples that are tied to episode IDs after the splits were regenerated.

    python tools/regen_examples.py          # rewrite examples/findings_t03_correct.json
    python tools/regen_examples.py --check  # only verify that it is current (exit 1 if not)

examples/findings_t03_correct.json is the oracle answer for episodes/train/t03_duplicate, so it changes whenever
the generator output (and with it the episode ID and row IDs) changes. The other files in examples/ hold seeds,
configs or code and carry no episode IDs; the script fails if one of them does.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from auditgym import io as aio  # noqa: E402
from auditgym.episode import load_episode  # noqa: E402
from auditgym.grader import Grader  # noqa: E402
from auditgym.policies.oracle import OraclePolicy  # noqa: E402

EXAMPLE = ROOT / "examples" / "findings_t03_correct.json"
EPISODE = ROOT / "episodes" / "train" / "t03_duplicate"


def main(argv=None) -> int:
    check_only = "--check" in (argv if argv is not None else sys.argv[1:])
    ep = load_episode(EPISODE)
    answer = {"episode_id": ep.episode_id, "findings": OraclePolicy(ep.truth).findings()}
    text = aio.dumps_pretty(answer)
    reward = Grader(ep.truth, ep.episode_id).grade(answer, 14, "submitted")["reward"]
    stale = [p.name for p in sorted((ROOT / "examples").iterdir())
             if p != EXAMPLE and p.suffix in (".json", ".py") and re.search(r"\bep_[0-9a-f]{16}\b", p.read_text(encoding="utf-8"))]
    if stale:
        print("examples with an episode ID that this script does not manage:", ", ".join(stale))
        return 1
    if check_only:
        current = EXAMPLE.exists() and aio.read_text(EXAMPLE) == text
        print(f"{EXAMPLE.name} is {'current' if current else 'STALE'} (episode {ep.episode_id})")
        return 0 if current else 1
    aio.write_text(EXAMPLE, text)
    print(f"wrote {EXAMPLE.relative_to(ROOT)}: episode {ep.episode_id}, {len(answer['findings'])} finding(s), "
          f"reward {reward} at 14 steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
