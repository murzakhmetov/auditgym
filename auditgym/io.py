"""Deterministic file I/O: UTF-8, LF line endings, fixed key order."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

LEDGER_COLUMNS = (
    "row_id",
    "timestamp",
    "account",
    "debit_minor",
    "credit_minor",
    "currency",
    "entity_id",
    "invoice_id",
    "payment_id",
)
FX_COLUMNS = ("date", "source_currency", "target_currency", "rate")
LEDGER_INT_FIELDS = ("debit_minor", "credit_minor")
LEDGER_NULLABLE = ("entity_id", "invoice_id", "payment_id")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dumps_pretty(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path: Path, obj) -> None:
    write_text(path, dumps_pretty(obj))


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def jsonl_text(rows, ascii_only: bool = False) -> str:
    return "".join(json.dumps(r, ensure_ascii=ascii_only, separators=(",", ":")) + "\n" for r in rows)


def write_jsonl(path: Path, rows, ascii_only: bool = False) -> None:
    """ascii_only=True escapes every non-ASCII character, including lone surrogates an agent may send."""
    write_text(path, jsonl_text(rows, ascii_only))


def read_jsonl(path: Path) -> list:
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def csv_text(columns, rows) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in columns])
    return buf.getvalue()


def write_csv(path: Path, columns, rows) -> None:
    write_text(path, csv_text(columns, rows))


def parse_ledger_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != LEDGER_COLUMNS:
        raise ValueError("ledger.csv header mismatch")
    rows = []
    for raw in reader:
        row = {}
        for c in LEDGER_COLUMNS:
            v = raw[c]
            if c in LEDGER_INT_FIELDS:
                row[c] = int(v)
            elif c in LEDGER_NULLABLE:
                row[c] = v if v != "" else None
            else:
                row[c] = v
        rows.append(row)
    return rows


def parse_fx_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != FX_COLUMNS:
        raise ValueError("fx.csv header mismatch")
    return [{c: raw[c] for c in FX_COLUMNS} for raw in reader]


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def fx_id(row: dict) -> str:
    return f"{row['date']}:{row['source_currency']}:{row['target_currency']}"
