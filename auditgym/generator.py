"""Episode generator: seed + config (+ optional host secret) -> Episode.

Order of construction (case section 02): consistent hidden company history ->
documents and clean books -> errors as booking overrides with a recorded
causal change -> erroneous books -> public records, answer key, provenance.
Every candidate episode is then verified independently (verify.py); a
candidate that fails is discarded and the next attempt is drawn from a
derived seed, so the result stays deterministic. Rejected attempts are listed
in provenance.json and counted by `check`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from . import CONFIG_VERSION, SCHEMA_VERSION, __version__
from .books import BooksError, post
from .config import ConfigError, resolve
from .episode import Episode
from .history import HistoryBuilder, SampleRetry
from .inject import RetryAttempt, derive_issues, make_overrides, plan_errors
from .io import canonical_json
from .render import Renderer, diff_records
from .rng import Rng

GENERATOR_VERSION = __version__
MAX_ATTEMPTS = 16


class GenerationError(RuntimeError):
    pass


@dataclass
class Generated:
    episode: Episode
    clean: Episode
    attempts: int
    rejected: list = field(default_factory=list)
    rejected_checks: list = field(default_factory=list)  # [{"attempt": n, "failed_checks": [verify check names]}], not in provenance
    verification: dict | None = None


def _base_text(seed, config: dict, secret: str | None) -> str:
    # "twin" is excluded so that a twin shares the whole hidden history with its source episode
    stream_cfg = {k: v for k, v in config.items() if k != "twin"}
    return f"auditgym|{GENERATOR_VERSION}|{seed}|{canonical_json(stream_cfg)}|{secret or ''}"


def episode_id_for(seed, config: dict, secret: str | None = None) -> str:
    tag = "|twin" if config.get("twin") else ""
    digest = hashlib.sha256((_base_text(seed, config, secret) + tag + "|episode_id").encode("utf-8")).hexdigest()
    return "ep_" + digest[:16]


def build_once(seed, config: dict, cfg: dict, rng: Rng, attempt: int, secret: str | None) -> Generated:
    b = HistoryBuilder(rng.fork("history"), cfg)
    b.build_entities()
    b.build_regular()
    b.build_distractors()
    b.choose_holidays()
    plan = plan_errors(b, cfg)
    b.protected_dates |= plan.protected_dates
    b.protected_dates |= {b.h.p_last_date, b.h.next_first_date}
    b.build_fx()
    clean_books = post(b.h)
    target_rows = cfg["counts"]["target_rows"]
    b.fill_misc(max(0, target_rows - len(clean_books.lines) - 2 * len(plan.extra_invoices)))
    clean_books = post(b.h)
    if b.lift_opening_bank(clean_books.lines):  # clean ledgers never overdraw the bank
        clean_books = post(b.h)
    overrides = make_overrides(b, plan)
    books = post(b.h, overrides)
    issues = derive_issues(b, plan, books)

    idents = [ln.ident for ln in clean_books.lines] + [ln.ident for ln in books.lines]
    renderer = Renderer(b.h, cfg, rng.fork("render"), books.invoices, idents)
    episode_id = episode_id_for(seed, config, secret)
    clean_invoices = {k: v for k, v in books.invoices.items() if k in b.h.invoices}
    tables_clean = {
        "ledger": renderer.ledger(clean_books),
        "invoices": renderer.invoices(clean_invoices),
        "payments": renderer.payments(),
        "fx": renderer.fx(),
    }
    tables = {
        "ledger": renderer.ledger(books),
        "invoices": renderer.invoices(books.invoices),
        "payments": tables_clean["payments"],
        "fx": tables_clean["fx"],
    }
    policy = renderer.policy()
    truth = renderer.truth(episode_id, issues, books.invoices)
    ops = diff_records(tables_clean, tables)
    injections = []
    for n, iss in enumerate(issues, start=1):
        it = iss["item"]
        data = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in it.data.items()}
        injections.append({
            "issue_id": f"iss_{n:02d}",
            "type": it.type,
            "variant": it.variant,
            "scenario": it.scenario,
            "targets": {role: (renderer.inv_id.get(key) or renderer.pay_id.get(key)) for role, key in it.targets.items()},
            "change": data,
        })
    distractors = []
    for d in b.h.distractors:
        distractors.append({"kind": d["kind"],
                            "ids": [renderer.inv_id.get(k) or renderer.pay_id.get(k) for k in d["keys"]]})
    manifest = renderer.manifest(episode_id, tables["ledger"], tables["invoices"], tables["payments"], tables["fx"])
    clean_manifest = renderer.manifest(episode_id, tables_clean["ledger"], tables_clean["invoices"],
                                       tables_clean["payments"], tables_clean["fx"])
    from .verify import records_digest

    clean_records_digest = records_digest(tables_clean["ledger"], tables_clean["invoices"], tables_clean["payments"])
    episode = Episode(manifest=manifest, policy=policy, **tables, truth=truth)
    clean = Episode(manifest=clean_manifest, policy=policy, **tables_clean,
                    truth={"schema_version": SCHEMA_VERSION, "episode_id": episode_id, "issues": [],
                           "id_aliases": truth["id_aliases"]})
    episode.provenance = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "config_version": CONFIG_VERSION,
        "seed": str(seed),
        "secret_used": bool(secret),
        "config": json.loads(canonical_json(config)),
        "resolved_config": cfg,
        "attempt": attempt,
        "history": {
            "company": b.h.company,
            "customers": len(b.customers),
            "suppliers": len(b.suppliers),
            "invoices": len(b.h.invoices),
            "payments": len(b.h.payments),
            "misc_journals": len(b.h.misc),
            "holidays": [d.isoformat() for d in b.h.holidays],
        },
        "injections": injections,
        "distractors": distractors,
        "ops": ops,
        "clean_digest": clean.public_digest(),
        "clean_records_digest": clean_records_digest,
        "final_digest": episode.public_digest(),
    }
    clean.provenance = {"schema_version": SCHEMA_VERSION, "clean_twin_of": episode_id}
    return Generated(episode=episode, clean=clean, attempts=attempt + 1)


def generate_episode(seed, config: dict | None = None, secret: str | None = None, verify: bool = True,
                     max_attempts: int = MAX_ATTEMPTS) -> Generated:
    config = dict(config or {})
    rng0 = Rng(_base_text(seed, config, secret))
    cfg = resolve(config, rng0.fork("config"))
    rejected, rejected_checks = [], []
    for attempt in range(max_attempts):
        rng = rng0.fork(f"attempt:{attempt}")
        try:
            gen = build_once(seed, config, cfg, rng, attempt, secret)
        except (SampleRetry, BooksError) as exc:
            rejected.append({"attempt": attempt, "reason": str(exc)[:200]})
            rejected_checks.append({"attempt": attempt, "failed_checks": []})
            continue
        if verify:
            from .verify import verify_generated

            report = verify_generated(gen.episode, gen.clean)
            if not report["ok"]:
                rejected.append({"attempt": attempt, "reason": "verification failed: " + "; ".join(report["failures"][:3])[:300]})
                rejected_checks.append({"attempt": attempt, "failed_checks": [n for n, v in report["checks"].items() if v != "pass"]})
                continue
            gen.verification = report
        gen.rejected = rejected
        gen.rejected_checks = rejected_checks
        gen.episode.provenance["rejected_attempts"] = rejected
        gen.episode.provenance["final_digest"] = gen.episode.public_digest()
        return gen
    raise GenerationError(f"no valid episode after {max_attempts} attempts: {rejected[-3:]}")


__all__ = ["generate_episode", "GenerationError", "ConfigError", "episode_id_for"]
