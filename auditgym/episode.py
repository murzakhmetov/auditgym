"""In-memory episode: public records plus grader-only files.

`Episode.public` is everything an agent may see through tools. `truth` and
`provenance` are grader-only and never cross the tool interface.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from . import io as aio
from . import schema_files

PUBLIC_FILES = ("manifest.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json")
GRADER_FILES = ("truth.json", "provenance.json")
TABLE_KEYS = {"ledger": "row_id", "invoices": "invoice_id", "payments": "payment_id", "fx": None}


@dataclass
class Episode:
    manifest: dict
    policy: dict
    ledger: list
    invoices: list
    payments: list
    fx: list
    truth: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    @property
    def episode_id(self) -> str:
        return self.manifest["episode_id"]

    def table(self, name: str) -> list:
        return {"ledger": self.ledger, "invoices": self.invoices, "payments": self.payments, "fx": self.fx}[name]

    @staticmethod
    def record_key(table: str, record: dict) -> str:
        if table == "fx":
            return aio.fx_id(record)
        return record[TABLE_KEYS[table]]

    def public_texts(self) -> dict:
        """Exact file contents of the public part (deterministic)."""
        return {
            "manifest.json": aio.dumps_pretty(self.manifest),
            "ledger.csv": aio.csv_text(aio.LEDGER_COLUMNS, self.ledger),
            "invoices.jsonl": aio.jsonl_text(self.invoices),
            "payments.jsonl": aio.jsonl_text(self.payments),
            "fx.csv": aio.csv_text(aio.FX_COLUMNS, self.fx),
            "policy.json": aio.dumps_pretty(self.policy),
        }

    def grader_texts(self) -> dict:
        return {
            "truth.json": aio.dumps_pretty(self.truth),
            "provenance.json": aio.dumps_pretty(self.provenance),
        }

    def public_digest(self) -> str:
        texts = self.public_texts()
        return aio.sha256_text("".join(f"{name}\n{texts[name]}" for name in PUBLIC_FILES))

    def write(self, directory: Path) -> None:
        directory = Path(directory)
        for name, text in self.public_texts().items():
            aio.write_text(directory / "public" / name, text)
        with aio.private_files():  # 0700 / 0600 when the policy runs as another user (container)
            for name, text in self.grader_texts().items():
                aio.write_text(directory / "grader" / name, text)
            if aio.agent_identity() is not None:  # an existing folder may hold old 0644 files: force private modes
                (directory / "grader").chmod(0o700)
                for name in self.grader_texts():
                    (directory / "grader" / name).chmod(0o600)

    def public_copy(self) -> "Episode":
        return Episode(
            manifest=copy.deepcopy(self.manifest),
            policy=copy.deepcopy(self.policy),
            ledger=copy.deepcopy(self.ledger),
            invoices=copy.deepcopy(self.invoices),
            payments=copy.deepcopy(self.payments),
            fx=copy.deepcopy(self.fx),
        )


class EpisodeFormatError(ValueError):
    """An episode directory holds a file that breaks its published format."""


def _read_json_file(path: Path):
    """aio.read_json that names the file on bad JSON (a deeply nested file is bad JSON too)."""
    try:
        return aio.read_json(path)
    except (ValueError, RecursionError) as exc:
        raise EpisodeFormatError(f"{path} is not valid JSON: {exc}") from exc


def _read_jsonl_file(path: Path) -> list:
    try:
        return aio.read_jsonl(path)
    except (ValueError, RecursionError) as exc:
        raise EpisodeFormatError(f"{path} is not valid JSON lines: {exc}") from exc


def _checked_truth(path: Path):
    """Read grader/truth.json and check it against the published schema; name the file and the first errors."""
    truth = _read_json_file(path)
    errors = schema_files.validate(truth, schema_files.TRUTH)
    if errors:
        more = f" (+{len(errors) - 3} more)" if len(errors) > 3 else ""
        raise EpisodeFormatError(f"{path} is not a valid answer key: " + "; ".join(errors[:3]) + more)
    aliases = truth.get("id_aliases", {})
    if not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in aliases.items()):
        raise EpisodeFormatError(f"{path} is not a valid answer key: id_aliases must map non-empty strings to non-empty strings")
    return truth


def load_episode(directory: Path, with_grader: bool = True) -> Episode:
    directory = Path(directory)
    pub = directory / "public"
    manifest = _read_json_file(pub / "manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("episode_id"), str):
        raise EpisodeFormatError(f"{pub / 'manifest.json'} must be a JSON object with a string episode_id")
    ep = Episode(
        manifest=manifest,
        policy=_read_json_file(pub / "policy.json"),
        ledger=aio.parse_ledger_csv(aio.read_text(pub / "ledger.csv")),
        invoices=_read_jsonl_file(pub / "invoices.jsonl"),
        payments=_read_jsonl_file(pub / "payments.jsonl"),
        fx=aio.parse_fx_csv(aio.read_text(pub / "fx.csv")),
    )
    if with_grader:
        grader = directory / "grader"
        ep.truth = _checked_truth(grader / "truth.json")
        if ep.truth["episode_id"] != ep.manifest["episode_id"]:
            raise EpisodeFormatError(f"{grader / 'truth.json'} belongs to episode {ep.truth['episode_id']}, "
                                     f"not {ep.manifest['episode_id']}")
        ep.provenance = _read_json_file(grader / "provenance.json") if (grader / "provenance.json").exists() else {}
    return ep
