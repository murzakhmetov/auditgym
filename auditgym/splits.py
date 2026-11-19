"""Open train/dev splits and the hidden-like check set."""

from __future__ import annotations

from pathlib import Path

from . import io as aio
from .episode import load_episode
from .generator import generate_episode
from .rng import Rng

ROOT = Path(__file__).resolve().parent.parent
SPLITS_FILE = ROOT / "configs" / "splits.json"
EPISODES_DIR = ROOT / "episodes"


def load_splits(path: Path = SPLITS_FILE) -> dict:
    return aio.read_json(path)


def split_entries(names=("train", "dev"), path: Path = SPLITS_FILE) -> list:
    data = load_splits(path)
    return [(split, e) for split in names for e in data[split]]


def generate_split_episodes(names=("train", "dev")) -> list:
    """[(split, name, Generated)] regenerated from configs/splits.json."""
    out = []
    for split, e in split_entries(names):
        out.append((split, e["name"], generate_episode(e["seed"], e["config"])))
    return out


def write_splits(out_dir: Path = EPISODES_DIR, names=("train", "dev")) -> list:
    index = []
    for split, name, gen in generate_split_episodes(names):
        gen.episode.write(Path(out_dir) / split / name)
        index.append({"split": split, "name": name, "episode_id": gen.episode.episode_id,
                      "issues": len(gen.episode.truth["issues"]),
                      "ledger_rows": len(gen.episode.ledger), "documents": len(gen.episode.invoices) + len(gen.episode.payments),
                      "attempts": gen.attempts})
    aio.write_json(Path(out_dir) / "index.json", {"episodes": index})
    return index


def load_split_episodes(names=("train", "dev"), base: Path = EPISODES_DIR) -> list:
    out = []
    for split, e in split_entries(names):
        out.append((split, e["name"], load_episode(Path(base) / split / e["name"])))
    return out


def check_set(master: str = "auditgym-check-v1") -> list:
    """20 hidden-like episodes: 5 clean, 5 with interacting errors, 10 mixed.
    Seeds are 63-bit values derived from a master string; configs are new
    parameter combinations not used in train/dev."""
    rng = Rng(master)
    sizes = ["small", "medium", "large"]
    entries = []
    for i in range(5):
        entries.append({"name": f"h{i + 1:02d}_clean", "seed": rng.next_u64() >> 1, "config": {"size": sizes[i % 3]}})
    inter = [
        {"interacting": ["boundary_fx_payment"]},
        {"interacting": ["fx_invoice_partial_allocation"]},
        {"interacting": ["boundary_fx_payment", "fx_invoice_partial_allocation"]},
        {"interacting": ["boundary_fx_payment"], "errors": {"duplicate_invoice": 1, "unallocated_payment": 1}},
        {"interacting": ["fx_invoice_partial_allocation"], "errors": {"wrong_period": 2}},
    ]
    for i, extra in enumerate(inter):
        entries.append({"name": f"h{i + 6:02d}_interacting", "seed": rng.next_u64() >> 1,
                        "config": {"size": sizes[(i + 1) % 3], **extra}})
    types = ["duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"]
    for i in range(10):
        errors = {t: rng.randint(0, 2) for t in types}
        if not any(errors.values()):
            errors[rng.choice(types)] = 1
        entries.append({"name": f"h{i + 11:02d}_mixed", "seed": rng.next_u64() >> 1,
                        "config": {"size": rng.choice(sizes), "errors": errors}})
    return entries
