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
MAX_CURRENCY_CHARS = 8  # the 3-letter code plus whitespace around it
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
MAX_EXPRESSION_CHARS = 256  # calculator.MAX_LENGTH
MAX_EXPRESSION_TOKENS = 200  # calculator.MAX_TOKENS


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def coerce_int(value):
    """JSON Schema treats 5.0 and 1e1 as integers; return the int for such floats, else the value unchanged."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def safe_str(key) -> str:
    """Text for a dict key that may be any in-process object (never raises, even for hostile objects)."""
    if isinstance(key, str):
        return key
    try:
        return str(key)
    except BaseException:  # includes RecursionError and a raising __str__
        return f"<{type(key).__name__}>"


def coerce_submission(obj):
    """Copy of a submission with integral floats in claimed_amount_minor turned into ints. Other shapes pass through."""
    if not isinstance(obj, dict) or not isinstance(obj.get("findings"), list):
        return obj
    out = dict(obj)
    out["findings"] = [
        {**f, "claimed_amount_minor": coerce_int(f["claimed_amount_minor"])}
        if isinstance(f, dict) and "claimed_amount_minor" in f else f
        for f in obj["findings"]
    ]
    return out


def _utf8(text: str) -> bool:
    """False for text that cannot be written as UTF-8 (a lone surrogate). The isolated child's action line is
    rejected for the same reason, so in process, in the child and in grade such a submission is invalid alike."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


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
        elif not _utf8(item):
            errors.append(f"{prefix}.{field}[{j}] is not valid UTF-8 text (a lone surrogate)")


def validate_submission(obj, episode_id: str | None) -> list[str]:
    """Return a list of structural errors; empty list means valid."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["submission must be a JSON object"]
    extra = sorted(map(safe_str, set(obj) - set(SUBMISSION_KEYS)))  # keys are strings in JSON; stay safe for in-process callers
    if extra:
        errors.append(f"unknown top-level keys: {', '.join(extra)[:120]}")
    if "episode_id" not in obj or not isinstance(obj.get("episode_id"), str):
        errors.append("episode_id must be a string")
    elif not _utf8(obj["episode_id"]):
        errors.append("episode_id is not valid UTF-8 text (a lone surrogate)")
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
        extra_f = sorted(map(safe_str, set(f) - set(FINDING_KEYS)))
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
            if not isinstance(cur, str) or len(cur) > MAX_CURRENCY_CHARS or not _CURRENCY_RE.match(cur.strip()):
                errors.append(f"{prefix}.currency must be a 3-letter currency code "
                              f"(at most {MAX_CURRENCY_CHARS} characters with surrounding whitespace)")
        if "explanation" in f:
            exp = f["explanation"]
            if not isinstance(exp, str):
                errors.append(f"{prefix}.explanation must be a string")
            elif len(exp) > MAX_EXPLANATION_CHARS:
                errors.append(f"{prefix}.explanation is longer than {MAX_EXPLANATION_CHARS} characters")
            elif not _utf8(exp):
                errors.append(f"{prefix}.explanation is not valid UTF-8 text (a lone surrogate)")
    return errors


# A finding ID must contain a non-whitespace character: validate_submission() rejects blank IDs.
# The class lists the 29 characters str.isspace() accepts: JSON Schema (ECMA-262) \s and \S differ from str.strip().
WS_CLASS = r"\t\n\v\f\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000"
ID_ITEM = {"type": "string", "minLength": 1, "maxLength": MAX_ID_CHARS, "pattern": "[^" + WS_CLASS + "]"}

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
                        "items": ID_ITEM,
                    },
                    "claimed_amount_minor": {"type": "integer", "minimum": 0, "maximum": MAX_AMOUNT_MINOR},
                    "currency": {"type": "string", "maxLength": MAX_CURRENCY_CHARS, "pattern": "^[" + WS_CLASS + "]*[A-Za-z]{3}[" + WS_CLASS + "]*$"},
                    "evidence_ids": {
                        "type": "array",
                        "maxItems": MAX_EVIDENCE_IDS,
                        "items": ID_ITEM,
                    },
                    "explanation": {"type": "string", "maxLength": MAX_EXPLANATION_CHARS},
                },
            },
        },
    },
}

_PLAIN_ACTION_BRANCHES = [
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
            "properties": {
                "action": {"const": "calculator"},
                "expression": {
                    "type": "string",
                    "maxLength": MAX_EXPRESSION_CHARS,
                    "description": f"At most {MAX_EXPRESSION_CHARS} characters and at most {MAX_EXPRESSION_TOKENS} tokens "
                                   "(numbers, + - * / and parentheses each count as one token).",
                },
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "findings"],
            "properties": {"action": {"const": "submit"}, "findings": {"$ref": "findings.schema.json"}},
        },
]


def _alias_branch(branch: dict) -> dict:
    """{"action": NAME, "args": {...}}: the environment unwraps it into the plain form."""
    props = dict(branch["properties"])
    name = props.pop("action")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "args"],
        "properties": {
            "action": name,
            "args": {
                "type": "object",
                "additionalProperties": False,
                "required": [k for k in branch["required"] if k != "action"],
                "properties": props,
            },
        },
    }


ACTION_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "auditgym/action.schema.json",
    "title": "auditgym action",
    "description": "Plain form {action, ...args} or the accepted alias {action, args: {...}}. Semantic errors "
                   "(unknown_id, bad_cursor, calc_error, a submission episode_id that is not the current one) "
                   "are not structural: a schema-valid action may still return them.",
    "oneOf": _PLAIN_ACTION_BRANCHES + [_alias_branch(b) for b in _PLAIN_ACTION_BRANCHES],
}
