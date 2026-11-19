"""Published JSON Schemas (draft 2020-12 subset) and a tiny stdlib validator.

`python -m auditgym schemas` writes them to schemas/. tests/test_schemas.py
validates every committed record, answer key and trajectory against them, so
the documents stay in sync with the code.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import FINDING_TYPES
from . import io as aio
from .schemas import ACTION_JSON_SCHEMA, SUBMISSION_JSON_SCHEMA

ID = {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[^:\\s]+$"}
NULLABLE_ID = {"type": ["string", "null"], "maxLength": 64}
TS = {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(Z|[+-]\\d{2}:\\d{2})$"}
CCY = {"type": "string", "pattern": "^[A-Z]{3}$"}
MINOR = {"type": "integer", "minimum": 0}

LEDGER_ROW = {
    "$id": "auditgym/ledger_row.schema.json", "type": "object", "additionalProperties": False,
    "required": ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency", "entity_id", "invoice_id", "payment_id"],
    "properties": {"row_id": ID, "timestamp": TS, "account": {"type": "string", "pattern": "^\\d{4}$"},
                   "debit_minor": MINOR, "credit_minor": MINOR, "currency": CCY,
                   "entity_id": NULLABLE_ID, "invoice_id": NULLABLE_ID, "payment_id": NULLABLE_ID},
}
INVOICE = {
    "$id": "auditgym/invoice.schema.json", "type": "object", "additionalProperties": False,
    "required": ["doc_id", "invoice_id", "kind", "entity_id", "issued_at", "due_at", "currency", "total_minor", "line_items"],
    "properties": {
        "doc_id": ID, "invoice_id": ID, "kind": {"enum": ["sales", "purchase"]}, "entity_id": ID,
        "issued_at": TS, "due_at": TS, "currency": CCY, "total_minor": MINOR,
        "line_items": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["line_no", "description", "quantity", "unit_price_minor", "amount_minor", "ref"],
            "properties": {"line_no": {"type": "integer", "minimum": 1}, "description": {"type": "string"},
                           "quantity": {"type": "integer", "minimum": 1}, "unit_price_minor": MINOR,
                           "amount_minor": MINOR, "ref": {"type": "string"}}}},
    },
}
PAYMENT = {
    "$id": "auditgym/payment.schema.json", "type": "object", "additionalProperties": False,
    "required": ["doc_id", "payment_id", "kind", "entity_id", "timestamp", "currency", "amount_minor", "invoice_refs", "bank_ref"],
    "properties": {
        "doc_id": ID, "payment_id": ID, "kind": {"enum": ["receipt", "disbursement", "refund"]},
        "entity_id": NULLABLE_ID, "timestamp": TS, "currency": CCY, "amount_minor": {"type": "integer", "minimum": 1},
        "invoice_refs": {"type": ["array", "null"], "items": ID}, "bank_ref": {"type": "string"},
    },
}
FX_ROW = {
    "$id": "auditgym/fx_row.schema.json", "type": "object", "additionalProperties": False,
    "required": ["date", "source_currency", "target_currency", "rate"],
    "properties": {"date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"}, "source_currency": CCY,
                   "target_currency": CCY, "rate": {"type": "string", "pattern": "^\\d+\\.\\d+$"}},
}
MANIFEST = {
    "$id": "auditgym/manifest.schema.json", "type": "object",
    "required": ["schema_version", "generator_version", "episode_id", "base_currency", "currency_exponents", "period_start",
                 "period_end", "ledger_extract_end", "timezone", "record_counts", "document_counts", "rounding"],
    "properties": {"schema_version": {"type": "string"}, "episode_id": {"type": "string", "pattern": "^ep_[0-9a-f]{16}$"},
                   "base_currency": CCY, "period_start": TS, "period_end": TS, "ledger_extract_end": TS,
                   "record_counts": {"type": "object", "required": ["ledger", "invoices", "payments", "fx"]}},
}
TRUTH = {
    "$id": "auditgym/truth.schema.json", "type": "object", "required": ["schema_version", "episode_id", "issues", "id_aliases"],
    "properties": {
        "issues": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["issue_id", "type", "variant", "scenario", "affected_ids", "expected_amount_minor", "currency",
                         "tolerance_minor", "evidence_sets", "explanation"],
            "properties": {"issue_id": {"type": "string", "pattern": "^iss_\\d{2}$"}, "type": {"enum": list(FINDING_TYPES)},
                           "variant": {"type": "string"}, "scenario": {"type": "string"},
                           "affected_ids": {"type": "array", "minItems": 1, "items": ID},
                           "expected_amount_minor": MINOR, "currency": CCY, "tolerance_minor": MINOR,
                           "evidence_sets": {"type": "array", "minItems": 1, "items": {"type": "array", "minItems": 2, "maxItems": 10,
                                                                                         "items": {"type": "string"}}},
                           "explanation": {"type": "string"}}}},
        "id_aliases": {"type": "object"},
    },
}
OBSERVATION = {
    "$id": "auditgym/observation.schema.json",
    "oneOf": [
        {"type": "object", "additionalProperties": False, "required": ["task", "manifest", "policy", "remaining_steps"],
         "properties": {"task": {"type": "object"}, "manifest": {"type": "object"}, "policy": {"type": "object"},
                        "remaining_steps": {"type": "integer", "minimum": 0, "maximum": 100}}},
        {"type": "object", "additionalProperties": False, "required": ["result", "error", "remaining_steps"],
         "properties": {"result": {"type": ["object", "null"]},
                        "error": {"oneOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
                                                                 "required": ["code", "message"],
                                                                 "properties": {"code": {"type": "string"},
                                                                                "message": {"type": "string", "maxLength": 200}}}]},
                        "remaining_steps": {"type": "integer", "minimum": 0, "maximum": 100}}},
    ],
}
TRAJECTORY_RECORD = {
    "$id": "auditgym/trajectory_record.schema.json", "type": "object",
    "required": ["episode_id", "step", "action", "observation", "reward", "terminated", "truncated"],
    "properties": {"episode_id": {"type": "string"}, "step": {"type": "integer", "minimum": 0, "maximum": 100},
                   "action": {"type": ["object", "string", "null"]}, "observation": {"type": "object"},
                   "reward": {"type": "number", "minimum": -1, "maximum": 1}, "terminated": {"type": "boolean"},
                   "truncated": {"type": "boolean"}},
}

POLICY = {
    "$id": "auditgym/policy.schema.json", "type": "object",
    "required": ["schema_version", "base_currency", "timezone", "utc_offset_schedule", "local_time_rule", "reporting_period",
                 "ledger_extract", "fx", "currency_exponents", "rounding", "posting_rules", "journal_grouping",
                 "duplicate_rule", "accounts", "nulls"],
    "properties": {
        "schema_version": {"type": "string"}, "base_currency": CCY, "timezone": {"type": "string", "minLength": 1},
        "utc_offset_schedule": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["from_utc", "offset"],
            "properties": {"from_utc": TS, "offset": {"type": "string", "pattern": r"^[+-]\d{2}:\d{2}$"}}}},
        "reporting_period": {"type": "object", "required": ["start", "end", "end_is_exclusive", "rule"],
                             "properties": {"start": TS, "end": TS, "end_is_exclusive": {"type": "boolean"}, "rule": {"type": "string"}}},
        "ledger_extract": {"type": "object", "required": ["start", "end", "rule"],
                           "properties": {"start": TS, "end": TS, "rule": {"type": "string"}}},
        "fx": {"type": "object", "required": ["quote", "pair_used", "date_rule", "publication_calendar", "conversion", "rounding"]},
        "currency_exponents": {"type": "object"},
        "rounding": {"type": "object", "required": ["mode"], "properties": {"mode": {"enum": ["half_up", "half_even"]}}},
        "posting_rules": {"type": "object"},
        "accounts": {"type": "object"},
    },
}
# Extra keys are allowed on purpose: provenance is grader-side metadata that later versions may extend.
PROVENANCE = {
    "$id": "auditgym/provenance.schema.json", "type": "object",
    "required": ["schema_version", "generator_version", "seed", "secret_used", "config", "resolved_config", "attempt",
                 "clean_digest", "final_digest", "injections", "ops"],
    "properties": {
        "schema_version": {"type": "string"}, "generator_version": {"type": "string"}, "seed": {"type": "string"},
        "secret_used": {"type": "boolean"}, "config": {"type": "object"}, "resolved_config": {"type": "object"},
        "attempt": {"type": "integer", "minimum": 0},
        "clean_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "final_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "injections": {"type": "array", "items": {"type": "object", "required": ["issue_id", "type"]}},
        "ops": {"type": "array", "items": {"type": "object", "required": ["op"]}},
    },
}

ALL = {
    "ledger_row.schema.json": LEDGER_ROW,
    "invoice.schema.json": INVOICE,
    "payment.schema.json": PAYMENT,
    "fx_row.schema.json": FX_ROW,
    "manifest.schema.json": MANIFEST,
    "truth.schema.json": TRUTH,
    "findings.schema.json": SUBMISSION_JSON_SCHEMA,
    "action.schema.json": ACTION_JSON_SCHEMA,
    "observation.schema.json": OBSERVATION,
    "trajectory_record.schema.json": TRAJECTORY_RECORD,
    "policy.schema.json": POLICY,
    "provenance.schema.json": PROVENANCE,
}


def write_schemas(out: Path) -> list:
    paths = []
    for name, schema in ALL.items():
        doc = {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
        aio.write_json(Path(out) / name, doc)
        paths.append(str(Path(out) / name))
    return paths


_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _type_ok(value, t) -> bool:
    if t == "integer":  # JSON Schema: 5.0 is an integer too
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def validate(value, schema: dict, path: str = "$", refs: dict | None = None) -> list:
    """Validate against the schema subset used here. Returns error strings."""
    refs = refs if refs is not None else {s.get("$id", "").split("/")[-1]: s for s in ALL.values()}
    if "$ref" in schema:
        return validate(value, refs[schema["$ref"]], path, refs)
    errs = []
    if "oneOf" in schema:
        n_ok = sum(1 for s in schema["oneOf"] if not validate(value, s, path, refs))
        return [] if n_ok == 1 else [f"{path}: matches {n_ok} alternatives of oneOf"]
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: expected {types}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: not in enum")
    if "const" in schema and value != schema["const"]:
        errs.append(f"{path}: const mismatch")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10**9):
            errs.append(f"{path}: length")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{path}: pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: above maximum")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10**9):
            errs.append(f"{path}: item count")
        if "items" in schema:
            for i, v in enumerate(value):
                errs += validate(v, schema["items"], f"{path}[{i}]", refs)
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: missing {k}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errs.append(f"{path}: unexpected {k}")
        for k, sub in props.items():
            if k in value:
                errs += validate(value[k], sub, f"{path}.{k}", refs)
    return errs
ACTION_JSON_SCHEMA_ALIAS = ACTION_JSON_SCHEMA
