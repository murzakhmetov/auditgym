"""Published structural rules for submissions and actions.

`validate_submission` decides whether findings.json is structurally valid.
An invalid structure ends the episode with reward -1 (see grader.py).
The JSON Schema documents in `schemas/` mirror these rules for other languages.
"""

from __future__ import annotations

import re

from . import FINDING_TYPES

MAX_FINDINGS = 30
MAX_EVIDENCE_IDS = 10
MAX_AFFECTED_IDS = 10
MAX_EXPLANATION_CHARS = 1000
MAX_ID_CHARS = 64
MAX_AMOUNT_MINOR = 10**15

FINDING_KEYS = (
    "type",
    "affected_ids",
    "claimed_amount_minor",
    "currency",
    "evidence_ids",
    "explanation",
)
SUBMISSION_KEYS = ("episode_id", "findings")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")

TABLES = ("ledger", "invoices", "payments", "fx")
ACTIONS = ("list_records", "get_record", "get_document", "calculator", "submit")
MAX_PAGE = 50


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_id_list(value, field: str, max_items: int, min_items: int, errors: list[str], prefix: str) -> None:
    if not isinstance(value, list):
        errors.append(f"{prefix}.{field} must be a list")
        return
    if len(value) < min_items:
        errors.append(f"{prefix}.{field} needs at least {min_items} item(s)")
    if len(value) > max_items:
        errors.append(f"{prefix}.{field} has more than {max_items} items")
    for j, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.{field}[{j}] must be a non-empty string")
        elif len(item) > MAX_ID_CHARS:
            errors.append(f"{prefix}.{field}[{j}] is longer than {MAX_ID_CHARS} characters")


def validate_submission(obj, episode_id: str | None) -> list[str]:
    """Return a list of structural errors; empty list means valid."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["submission must be a JSON object"]
    extra = sorted(set(obj) - set(SUBMISSION_KEYS))
    if extra:
        errors.append(f"unknown top-level keys: {', '.join(extra)[:120]}")
    if "episode_id" not in obj or not isinstance(obj.get("episode_id"), str):
        errors.append("episode_id must be a string")
    elif episode_id is not None and obj["episode_id"] != episode_id:
        errors.append("episode_id does not match the current episode")
    findings = obj.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        return errors
    if len(findings) > MAX_FINDINGS:
        errors.append(f"more than {MAX_FINDINGS} findings")
    for i, f in enumerate(findings[: MAX_FINDINGS + 1]):
        prefix = f"findings[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = [k for k in FINDING_KEYS if k not in f]
        if missing:
            errors.append(f"{prefix} missing keys: {', '.join(missing)}")
        extra_f = sorted(set(f) - set(FINDING_KEYS))
        if extra_f:
            errors.append(f"{prefix} unknown keys: {', '.join(extra_f)[:120]}")
        if "type" in f and f["type"] not in FINDING_TYPES:
            errors.append(f"{prefix}.type must be one of {', '.join(FINDING_TYPES)}")
        if "affected_ids" in f:
            _check_id_list(f["affected_ids"], "affected_ids", MAX_AFFECTED_IDS, 1, errors, prefix)
        if "evidence_ids" in f:
            _check_id_list(f["evidence_ids"], "evidence_ids", MAX_EVIDENCE_IDS, 0, errors, prefix)
        if "claimed_amount_minor" in f:
            amt = f["claimed_amount_minor"]
            if not _is_int(amt) or amt < 0 or amt > MAX_AMOUNT_MINOR:
                errors.append(f"{prefix}.claimed_amount_minor must be an integer in [0, {MAX_AMOUNT_MINOR}]")
        if "currency" in f:
            cur = f["currency"]
            if not isinstance(cur, str) or not _CURRENCY_RE.match(cur.strip()):
                errors.append(f"{prefix}.currency must be a 3-letter currency code")
        if "explanation" in f:
            exp = f["explanation"]
            if not isinstance(exp, str):
                errors.append(f"{prefix}.explanation must be a string")
            elif len(exp) > MAX_EXPLANATION_CHARS:
                errors.append(f"{prefix}.explanation is longer than {MAX_EXPLANATION_CHARS} characters")
    return errors


SUBMISSION_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "auditgym/findings.schema.json",
    "title": "auditgym findings.json",
    "type": "object",
    "additionalProperties": False,
    "required": list(SUBMISSION_KEYS),
    "properties": {
        "episode_id": {"type": "string"},
        "findings": {
            "type": "array",
            "maxItems": MAX_FINDINGS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(FINDING_KEYS),
                "properties": {
                    "type": {"enum": list(FINDING_TYPES)},
                    "affected_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_AFFECTED_IDS,
                        "items": {"type": "string", "minLength": 1, "maxLength": MAX_ID_CHARS},
                    },
                    "claimed_amount_minor": {"type": "integer", "minimum": 0, "maximum": MAX_AMOUNT_MINOR},
                    "currency": {"type": "string", "pattern": "^\\s*[A-Za-z]{3}\\s*$"},
                    "evidence_ids": {
                        "type": "array",
                        "maxItems": MAX_EVIDENCE_IDS,
                        "items": {"type": "string", "minLength": 1, "maxLength": MAX_ID_CHARS},
                    },
                    "explanation": {"type": "string", "maxLength": MAX_EXPLANATION_CHARS},
                },
            },
        },
    },
}

ACTION_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "auditgym/action.schema.json",
    "title": "auditgym action",
    "oneOf": [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "table"],
            "properties": {
                "action": {"const": "list_records"},
                "table": {"enum": list(TABLES)},
                "cursor": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "table", "id"],
            "properties": {
                "action": {"const": "get_record"},
                "table": {"enum": list(TABLES)},
                "id": {"type": "string"},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "doc_id"],
            "properties": {"action": {"const": "get_document"}, "doc_id": {"type": "string"}},
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "expression"],
            "properties": {"action": {"const": "calculator"}, "expression": {"type": "string", "maxLength": 256}},
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "findings"],
            "properties": {"action": {"const": "submit"}, "findings": {"$ref": "findings.schema.json"}},
        },
    ],
}
