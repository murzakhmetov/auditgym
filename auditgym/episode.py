"""In-memory episode: public records plus grader-only files.

`Episode.public` is everything an agent may see through tools. `truth` and
`provenance` are grader-only and never cross the tool interface.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from . import io as aio

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
        for name, text in self.grader_texts().items():
            aio.write_text(directory / "grader" / name, text)

    def public_copy(self) -> "Episode":
        return Episode(
            manifest=copy.deepcopy(self.manifest),
            policy=copy.deepcopy(self.policy),
            ledger=copy.deepcopy(self.ledger),
            invoices=copy.deepcopy(self.invoices),
            payments=copy.deepcopy(self.payments),
            fx=copy.deepcopy(self.fx),
        )


def load_episode(directory: Path, with_grader: bool = True) -> Episode:
    directory = Path(directory)
    pub = directory / "public"
    ep = Episode(
        manifest=aio.read_json(pub / "manifest.json"),
        policy=aio.read_json(pub / "policy.json"),
        ledger=aio.parse_ledger_csv(aio.read_text(pub / "ledger.csv")),
        invoices=aio.read_jsonl(pub / "invoices.jsonl"),
        payments=aio.read_jsonl(pub / "payments.jsonl"),
        fx=aio.parse_fx_csv(aio.read_text(pub / "fx.csv")),
    )
    if with_grader:
        grader = directory / "grader"
        ep.truth = aio.read_json(grader / "truth.json")
        ep.provenance = aio.read_json(grader / "provenance.json") if (grader / "provenance.json").exists() else {}
    return ep
