"""Seeded action generators for the contract fuzzer (tests/test_contract_fuzz.py).

All randomness comes from auditgym.rng.Rng seeded with "auditgym-fuzz-v1", so a run replays byte for byte.

Two uses:
  * gen_action(): Python objects for in-process env.step() calls (may hold lone surrogates, NaN, very deep nesting).
  * raw_lines() and main(): the policy side of the piped part. Run as
        python -m tests.fuzz_policies INDEX COUNT
    it answers every observation with the next raw text line, bypassing auditgym.agent, so malformed JSON,
    oversized lines and well-formed but invalid actions reach AgentProcess exactly as a broken policy would send them.
"""

from __future__ import annotations

import json
import sys

from auditgym import FINDING_TYPES
from auditgym.rng import Rng

MASTER = "auditgym-fuzz-v1"
TABLES = ("ledger", "invoices", "payments", "fx")
ACTION_NAMES = ("list_records", "get_record", "get_document", "calculator")
DEFAULT_CTX = {
    "episode_id": "ep_0000000000000000",
    "ids": {"ledger": ["gl_0"], "invoices": ["inv_0"], "payments": ["pay_0"], "fx": ["2025-01-02:USD:EUR"]},
    "docs": ["doc_0"],
    "grader_ids": ["iss_01", "iss_99"],
    "sizes": {"ledger": 300, "invoices": 30, "payments": 30, "fx": 100},
}
WS_IDS = (" ", "\t", "\n", " ", "　", "\x1c", "   ")
LONG = "A" * 10_000
CALC_VALID = ("1+2", "(1+2)*3/4", "1/3", "-5", "2*3*4", ".5+.5", "100.25*3", "((((1))))", "7-9")
CALC_EDGE = (
    "1/0", "2**8", "", "   ", "1 2", "()", "--1", "5.", ".", "1e5", "٣+1", "²", "abc", "1+",
    "1" + "+1" * 100,            # 201 tokens
    "1" + "+1" * 99,             # 199 tokens
    "1" + "+1" * 99 + "+",       # 200 tokens, incomplete
    "(" * 40 + "1" + ")" * 40,    # nesting 41
    "9" * 255,                   # 255 digits, out of range
    "0." + "1" * 250,
    "9" * 10_000, "0." + "1" * 10_000, "1+" * 200 + "1",
    "9" * 31, "9" * 30, "-" * 255 + "1",
)


def nest(depth: int):
    x = []
    for _ in range(depth):
        x = [x]
    return x


def _extra_key(rng: Rng, raw: bool, plain: tuple):
    """A key to add to an object. In-process runs also use non-string keys (impossible in JSON, possible for a Python caller)."""
    if not raw and rng.randbelow(3) == 0:
        return rng.choice((1, None, (1, 2), 2.5, True, -7))
    return rng.choice(plain)


def _wrong_value(rng: Rng, deep_max: int, raw: bool):
    pool = [None, True, False, 0, 1, -1, 7, 2**80, -(2**80), 1.5, 0.0, "", " ", "x", LONG, [], {}, [[]], [1, 2], {"a": 1},
            "٣", "Ledger", "LEDGER", "ledger ", "1", "01", "-1", "999999", "1" * 7, "1.5", " 1", ["ledger"], {"table": "ledger"},
            nest(5), nest(min(deep_max, 300))]
    if not raw:
        pool += ["\ud800", "x\udfffy", float("nan"), float("inf"), nest(min(deep_max, 5000)), "\ud800" * 100]
    return pool[rng.randbelow(len(pool))]


def _valid_action(rng: Rng, ctx: dict) -> dict:
    kind = rng.randbelow(4)
    table = rng.choice(TABLES)
    if kind == 0:
        a = {"action": "list_records", "table": table}
        if rng.randbelow(2):
            a["limit"] = rng.randint(1, 50)
        if rng.randbelow(2):
            a["cursor"] = None if rng.randbelow(2) else str(rng.randint(0, ctx["sizes"][table]))
        return a
    if kind == 1:
        return {"action": "get_record", "table": table, "id": rng.choice(ctx["ids"][table])}
    if kind == 2:
        return {"action": "get_document", "doc_id": rng.choice(ctx["docs"])}
    return {"action": "calculator", "expression": rng.choice(CALC_VALID)}


def _all_ids(ctx: dict) -> list:
    return [i for t in TABLES for i in ctx["ids"][t]] + ctx["docs"]


def _id_pool(rng: Rng, ctx: dict) -> str:
    r = rng.randbelow(5)
    if r == 0:
        return rng.choice(ctx["grader_ids"])
    if r == 1:
        return rng.choice(WS_IDS)
    if r == 2:
        return "x" * rng.choice((63, 64, 65, 200))
    return rng.choice(_all_ids(ctx))


def _mutate(rng: Rng, a: dict, ctx: dict, deep_max: int, raw: bool, allow_submit: bool) -> object:
    op = rng.randbelow(13)
    a = dict(a)
    if op == 0:                                   # type confusion on one key
        k = rng.choice(sorted(a))
        a[k] = _wrong_value(rng, deep_max, raw)
    elif op == 1 and len(a) > 1:                  # missing key
        del a[rng.choice(sorted(a))]
    elif op == 2:                                 # extra key
        a[_extra_key(rng, raw, ("args", "extra", "cursor", "limit", "table", "id", "findings", "", "action2"))] = _wrong_value(rng, deep_max, raw)
        if not raw and rng.randbelow(4) == 0:
            a["x"] = 0                                # mixed str and non-str keys in one object
    elif op == 3:                                 # alias form, valid or mutated
        name = a.get("action")
        inner = {k: v for k, v in a.items() if k != "action"}
        a = {"action": name, "args": inner}
        if rng.randbelow(3) == 0:
            a[rng.choice(("args", "action"))] = _wrong_value(rng, deep_max, raw)
        elif rng.randbelow(4) == 0:
            a["args"] = dict(inner, action="calculator")
    elif op == 4:                                 # other action name
        names = ACTION_NAMES + (("submit",) if allow_submit else ()) + ("LIST_RECORDS", "list_records ", "reset", "", "step", "__malformed__")
        a["action"] = rng.choice(names)
    elif op == 5:                                 # limit edge values
        a = {"action": "list_records", "table": rng.choice(TABLES),
             "limit": rng.choice((0, 1, 50, 51, -1, 2**80, True, 1.0, "5", None, 49.5))}
    elif op == 6:                                 # cursor edge values, forged or stale
        size = ctx["sizes"][rng.choice(TABLES)]
        a = {"action": "list_records", "table": rng.choice(TABLES),
             "cursor": rng.choice((str(size), str(size + 1), "0", "00", "-1", "abc", "٣", " 1", "1 ", "1.0", "9" * 6, "9" * 7,
                                   "9" * 5000, "", "None", 5, True, ["1"], str(rng.randint(0, 300)))),
             "limit": rng.choice((1, 50))}
    elif op == 7:                                 # id from the wrong table, or from grader files
        t, other = rng.choice(TABLES), rng.choice(TABLES)
        a = {"action": "get_record", "table": t, "id": rng.choice(ctx["ids"][other] + ctx["grader_ids"] + ctx["docs"])}
    elif op == 8:                                 # strings: long, whitespace, surrogate
        key = rng.choice(("table", "id", "doc_id", "expression", "cursor"))
        pool = [LONG, " ", " ", "x" * 65, "x" * 10_000]
        if not raw:
            pool += ["\ud800", "id\udc00"]
        a = {"action": {"table": "list_records", "id": "get_record", "doc_id": "get_document",
                        "expression": "calculator", "cursor": "list_records"}[key], key: rng.choice(pool)}
        if key in ("id",):
            a["table"] = "ledger"
        if key == "cursor":
            a["table"] = "fx"
    elif op == 9:                                 # deep nesting where a scalar belongs
        a = {"action": rng.choice(("get_record", "get_document", "list_records", "calculator")),
             rng.choice(("table", "id", "doc_id", "expression", "cursor", "limit")): nest(rng.choice((10, 100, deep_max)))}
    elif op == 10:                                # calculator edge cases
        a = {"action": "calculator", "expression": rng.choice(CALC_EDGE)}
    elif op == 11:                                # id lookups with odd ids
        t = rng.choice(TABLES)
        a = {"action": "get_record", "table": t, "id": _id_pool(rng, ctx)}
        if rng.randbelow(2):
            a = {"action": "get_document", "doc_id": a["id"]}
    else:                                         # non-object actions
        return rng.choice((None, [], "list_records", 7, True, [a], "", 1.5, [[]], nest(50)))
    return a


def _finding(rng: Rng, ctx: dict) -> dict:
    return {"type": rng.choice(FINDING_TYPES), "affected_ids": [rng.choice(_all_ids(ctx))],
            "claimed_amount_minor": rng.randint(0, 10**9), "currency": "EUR",
            "evidence_ids": [rng.choice(_all_ids(ctx)) for _ in range(rng.randint(0, 3))], "explanation": "fuzz"}


def gen_submission(rng: Rng, ctx: dict, raw: bool = False) -> dict:
    """A submit action: valid about a third of the time, otherwise broken in one way."""
    findings = [_finding(rng, ctx) for _ in range(rng.randint(0, 3))]
    sub = {"episode_id": ctx["episode_id"], "findings": findings}
    op = rng.randbelow(16)
    f0 = findings[0] if findings else None
    if op == 0:
        sub["findings"] = [_finding(rng, ctx) for _ in range(31)]
    elif op == 1:
        sub["findings"] = [_finding(rng, ctx) for _ in range(30)]       # exactly at the limit: valid
    elif op == 2 and f0:
        f0["evidence_ids"] = [rng.choice(_all_ids(ctx)) for _ in range(11)]
    elif op == 3 and f0:
        f0["evidence_ids"] = [rng.choice(_all_ids(ctx)) for _ in range(10)]   # at the limit: valid
    elif op == 4 and f0:
        f0["explanation"] = "e" * rng.choice((1000, 1001, 1002))
    elif op == 5 and f0:
        f0[rng.choice(("affected_ids", "evidence_ids"))] = [rng.choice(WS_IDS)]
    elif op == 6 and f0:
        f0["affected_ids"] = [rng.choice(WS_IDS), "ok"]
    elif op == 7:
        sub["episode_id"] = rng.choice(("", "ep_wrong", ctx["episode_id"] + " ", ctx["episode_id"].upper(), 5, None))
    elif op == 8 and f0:
        f0[rng.choice(("claimed_amount_minor", "currency", "type", "explanation", "affected_ids"))] = _wrong_value(rng, 50, True)
    elif op == 9 and f0:
        f0["claimed_amount_minor"] = rng.choice((-1, 0, 10**15, 10**15 + 1, 2**80, True, 1.0, "5"))
    elif op == 10 and f0:
        f0["currency"] = rng.choice(("usd", " USD ", "US", "USDX", "US1", "USD\n", "ＵＳＤ", "", "EUR ", "E U"))
    elif op == 11 and f0:
        del f0[rng.choice(sorted(f0))]
    elif op == 12 and f0:
        f0[_extra_key(rng, raw, ("extra",))] = 1
    elif op == 13:
        sub[_extra_key(rng, raw, ("extra",))] = 1
        if not raw and rng.randbelow(2):
            sub["z"] = 1
    elif op == 14:
        sub["findings"] = rng.choice((None, {}, "x", 5, [None], [[]], ["x"]))
    elif op == 15 and f0:
        f0["affected_ids"] = ["x" * rng.choice((64, 65)), "​"]
    action = {"action": "submit", "findings": sub}
    r = rng.randbelow(8)
    if r == 0:
        action = {"action": "submit", "args": {"findings": sub}}
    elif r == 1:
        action[_extra_key(rng, raw, ("extra",))] = 1
        if not raw and rng.randbelow(2):
            action["y"] = 1
    elif r == 2:
        action = {"action": "submit"}
    elif r == 3:
        action = {"action": "submit", "findings": rng.choice((None, [], "x", 3))}
    return action


def gen_action(rng: Rng, ctx: dict, allow_submit: bool = True, deep_max: int = 5000, raw: bool = False):
    """One fuzz action: valid calls mixed with every kind of mutation. Never 'submit' unless allow_submit."""
    roll = rng.randbelow(100)
    if roll < 30:
        return _valid_action(rng, ctx)
    if allow_submit and roll >= 96:
        return gen_submission(rng, ctx, raw)
    return _mutate(rng, _valid_action(rng, ctx), ctx, deep_max, raw, allow_submit)


# ------------------------------------------------------------------ raw lines (piped part)
def _malformed_line(rng: Rng, which: int) -> str:
    deep = "[" * 100_000
    forms = (
        "not json", "{", "", "   ", "[]", "null", "42", '"action"', '{"type":"observation"}', '{"type":"action"}',
        '{"action":{"action":"list_records","table":"fx"}}', '{"type":"action","action":NaN}',
        '{"type":"action","action":{"action":"\\ud800"}}', '{"type":"action","action":Infinity}',
        '{"type":"action","action":' + deep, '{"type":"action","action":{"limit":' + "1" * 5000 + "}}",
        '{"type":"action","action":' + "[" * 5000 + "]" * 5000 + "}",
        '{"type":"action","action":{"action":"calculator","expression":"1+1"}',
        "{'type':'action'}", '{"type":"action","action":{"action":"list_records","table":"fx"}} trailing',
        "\x00", '{"type":"action","action":"\\udc00"}',
    )
    if which == 7:
        return "x" * 2_100_000          # longer than the host's line limit
    return forms[which % len(forms)] if which != 8 else forms[rng.randbelow(len(forms))]


def raw_lines(index: int, count: int, episode_id: str, ctx: dict | None = None) -> list:
    """[(kind, text)] with kind 'ok' (a well-formed action message) or 'malformed' (host must flag it).

    Index 2 ends with a valid empty submission; the others never submit, so they run into the step limit."""
    rng = Rng(MASTER).fork("raw").fork(str(index))
    ctx = dict(ctx or DEFAULT_CTX, episode_id=episode_id)
    lines = []
    big_done = False
    for i in range(count):
        if index == 2 and i == count - 1:
            lines.append(("ok", json.dumps({"type": "action", "action": {"action": "submit", "findings": {"episode_id": episode_id, "findings": []}}})))
            continue
        if rng.randbelow(100) < 22:
            which = rng.randbelow(30)
            if which == 7 and (big_done or index != 1):
                which = 8
            big_done = big_done or which == 7
            lines.append(("malformed", _malformed_line(rng, which)))
        else:
            action = gen_action(rng, ctx, allow_submit=False, deep_max=300, raw=True)
            lines.append(("ok", json.dumps({"type": "action", "action": action}, allow_nan=False)))
    return lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    index, count = int(argv[0]), int(argv[1])
    lines = None
    pos = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("type") == "end":
            break
        if msg.get("type") != "observation":
            continue
        if lines is None:
            episode_id = msg["observation"]["task"]["episode_id"]
            lines = raw_lines(index, count, episode_id)
        if msg.get("terminated") or msg.get("truncated"):
            continue
        if pos >= len(lines):
            text = json.dumps({"type": "action", "action": {"action": "submit", "findings": {"episode_id": episode_id, "findings": []}}})
        else:
            text = lines[pos][1]
            pos += 1
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
