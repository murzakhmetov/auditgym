"""Command line: python -m auditgym <command> [options]

  check                      single offline check (tests, data, rewards, reproducibility, leaks)
  build-splits               regenerate episodes/train and episodes/dev from configs/splits.json
  generate                   generate one episode directory from a seed and a config
  verify DIR                 named accounting and answer-key checks for one episode directory
  run                        run policies on episode directories or on seeds (closed run, in memory)
  grade                      grade a findings.json file against an episode directory
  transform                  write a permuted / ID-remapped / re-timestamped copy of an episode
  demo                       scripted demo: the auditor and the recon baseline on one dev episode
  viewer                     build the offline HTML viewer (viewer/index.html)
  schemas                    write the published JSON schemas to schemas/
  stress                     generator stress run: random configs plus extreme ones (runs/stress/report.md)
  budget                     auditor and recon on dev at 20, 50 and 100 steps (runs/budget/summary.md)

Exit codes: 0 ok, 1 a check or verification failed, 2 bad input (one `error:` line on stderr; command-line
syntax errors print the argparse usage first), 3 a run finished but an agent failed. Only the input stage of a
command (config, seeds file, episode directories, secret variable, numbers) is turned into exit 2; a crash inside
a check, an agent policy or the stress loop keeps its traceback and exits 1.

Strict isolation (opt-in): with AUDITGYM_REQUIRE_AGENT_USER=1 a policy that cannot run as the separate agent
user (not root, no AUDITGYM_AGENT_USER, dropped capabilities, Windows, macOS) is an error: check, run, demo, viewer
and budget exit 2 with one `error:` line before the first episode and before any report is written.
`run --in-process` with a custom module:Class policy is refused the same way (it would run foreign code in the
host process); built-in policies in process stay allowed.

--secret-env: run, generate and check read the variable once and remove it from this process's environment block,
so a child reading the parent's environment block no longer finds it. The value itself stays in the host's memory,
which a same-user child can read on Windows; Linux also keeps the start-up copy in /proc/<pid>/environ. Only the
image's separate policy uid protects the secret.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import sys
from pathlib import Path

from . import CONFIG_VERSION, SCHEMA_VERSION, __version__
from . import io as aio

MAX_STEPS = 100  # env.DEFAULT_MAX_STEPS: the largest action budget
MIN_SEED_BITS = 40  # seeds below 2**40 (bit length <= 40) are guessable from public records; see README limitations


class InputError(ValueError):
    """Bad user input: reported as one `error:` line on stderr, exit code 2."""


@contextlib.contextmanager
def _input(broad: bool = False):
    """Turn input-stage failures into InputError. ConfigError and GenerationError always; with broad=True also
    OSError and ValueError (reading and parsing user files). Never wrap a run, a check or the stress loop."""
    from .config import ConfigError
    from .generator import GenerationError

    kinds = (ConfigError, GenerationError) + ((OSError, ValueError) if broad else ())
    try:
        yield
    except InputError:
        raise
    except kinds as exc:
        raise InputError(" ".join(str(exc).split()) or type(exc).__name__) from exc


def _secret_from_env(name: str | None) -> str | None:
    """Read the host secret from the environment variable `name` and remove that one variable from this process's
    environment block, so a child reading the parent's environment block no longer finds it. The value stays in the
    host's memory, which a same-user child can read on Windows; Linux keeps the start-up copy in
    /proc/<pid>/environ. Only the image's separate policy uid protects the secret."""
    if not name:
        return None
    value = os.environ.pop(name, None)
    if not value:
        raise InputError(f"--secret-env {name}: the environment variable is not set or empty")
    return value


def _seed_bits(seed: int) -> int:
    return abs(seed).bit_length()


def _small_seed_warning(min_bits: int | None, secret: str | None) -> str | None:
    if secret is None and min_bits is not None and min_bits <= MIN_SEED_BITS:
        return (f"WARNING: no host secret and a seed of at most {MIN_SEED_BITS} bits ({min_bits}): small seeds can be "
                f"recovered from public records; use 63-bit seeds and --secret-env for closed runs")
    return None


def _load_seeds_file(path: Path) -> tuple:
    """The seeds-file rules live in check.load_seeds_file (integer seeds, object configs, unique names, non-empty)."""
    from .check import load_seeds_file

    try:
        return load_seeds_file(Path(path))
    except ValueError as exc:
        raise InputError(str(exc)) from exc


def _run_meta(args, secret: str | None, min_bits: int | None, n_episodes: int) -> dict:
    from .generator import GENERATOR_VERSION
    from .grader import GRADE_VERSION

    cmd = ["python", "-m", "auditgym", *(args.argv or [])]
    if secret:  # the secret is passed by variable name; scrub it anyway if it ever shows up in the command line
        cmd = [c.replace(secret, "***") for c in cmd]
    return {
        "auditgym_version": __version__,
        "generator_version": GENERATOR_VERSION,
        "config_version": CONFIG_VERSION,
        "schema_version": SCHEMA_VERSION,
        "grade_version": GRADE_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mode": args.mode,
        "isolated": not args.in_process,
        "policies": [p.strip() for p in args.policies.split(",") if p.strip()],
        "policy_seed": args.policy_seed,
        "max_steps": args.max_steps,
        "episodes": n_episodes,
        "secret_used": bool(secret),
        "min_seed_bits": min_bits,
        "command": cmd,
    }


def _load_config(arg: str | None) -> dict:
    """A JSON file path or inline JSON (an argument starting with `{`). Always an object."""
    if not arg:
        return {}
    if arg.lstrip().startswith("{"):
        try:
            cfg = json.loads(arg)
        except ValueError as exc:
            raise InputError(f"--config is not valid JSON: {exc}") from exc
    else:
        try:
            cfg = aio.read_json(Path(arg))
        except FileNotFoundError as exc:
            raise InputError(f"config file not found: {arg} (inline JSON must start with an opening brace)") from exc
        except (OSError, ValueError) as exc:
            raise InputError(f"cannot read config file {arg}: {exc}") from exc
    if not isinstance(cfg, dict):
        raise InputError("config must be a JSON object")
    return cfg


def _custom_policy_guard(policies: list, args) -> None:
    """Custom module:Class policies are foreign code. Strict mode refuses to run them in this process; when they
    run as the host's user next to a seeds file or a host secret, one warning line says what they could read."""
    from . import protocol
    from .policies import is_external

    custom = [p for p in policies if is_external(p)]
    if not custom:
        return
    if args.in_process and protocol.require_agent_user():
        raise InputError(f"{protocol.REQUIRE_ENV}=1 does not allow --in-process with a custom policy "
                         f"({custom[0]}): it would run in the host process; drop --in-process")
    if not (args.seeds_file or args.secret_env) or protocol.require_agent_user():
        return  # strict mode either switches user or refuses later
    if not args.in_process and aio.agent_identity() is not None and protocol._proc_listable():
        return  # the child runs as the separate policy user
    advice = ("drop --in-process" if args.in_process
              else "run it in the official image (separate policy user)")
    print(f"WARNING: custom policy {custom[0]} runs as the host's user while a seeds file or --secret-env is in use: "
          f"it can read the seeds file and the host's environment; {advice} or with {protocol.REQUIRE_ENV}=1",
          file=sys.stderr)


def _require_agent_user() -> None:
    """In strict mode (AUDITGYM_REQUIRE_AGENT_USER=1) start and stop one policy child now, so a host that cannot
    run the policy as the separate agent user fails before the first episode and before any report is written."""
    from . import protocol

    if not protocol.require_agent_user():
        return
    try:
        protocol.AgentProcess("recon", 0).close()
    except protocol.AgentUserRequired as exc:
        raise InputError(str(exc)) from exc


def cmd_check(args) -> int:
    from .check import main

    _require_agent_user()
    argv = []
    for flag, value in (("--seeds-file", args.seeds_file), ("--secret-env", args.secret_env), ("--out", args.out)):
        if value is not None:
            argv += [flag, value]
    if args.keep_runs:
        argv.append("--keep-runs")
    return main(argv)


def cmd_build_splits(args) -> int:
    from .splits import write_splits

    index = write_splits()
    for e in index:
        print(f"{e['split']}/{e['name']}: {e['episode_id']} issues={e['issues']} rows={e['ledger_rows']} docs={e['documents']}")
    return 0


def cmd_generate(args) -> int:
    from .generator import generate_episode

    secret = _secret_from_env(args.secret_env)
    cfg = _load_config(args.config)
    with _input():
        gen = generate_episode(args.seed, cfg, secret=secret)
    gen.episode.write(Path(args.out))
    print(json.dumps({"episode_id": gen.episode.episode_id, "issues": len(gen.episode.truth["issues"]),
                      "attempts": gen.attempts, "out": str(args.out)}))
    return 0


def cmd_verify(args) -> int:
    from .episode import load_episode
    from .verify import verify_generated

    with _input(broad=True):
        ep = load_episode(Path(args.dir))
    rep = verify_generated(ep)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        for name, status in rep["checks"].items():
            print(f"{'PASS' if status == 'pass' else 'FAIL'}  {name}" + ("" if status == "pass" else f": {status[:3]}"))
        for t in ep.truth.get("issues", []):
            print(f"      declared {t['issue_id']} {t['type']} ids={t['affected_ids']} amount={t['expected_amount_minor']} {t['currency']}"
                  f" evidence_sets={len(t['evidence_sets'])}")
    return 0 if rep["ok"] else 1


def cmd_run(args) -> int:
    from .episode import load_episode
    from .generator import generate_episode
    from .report import markdown_table, miss_table, summarize
    from .runner import run_many

    if args.secret_env and not args.seeds_file:
        raise InputError("--secret-env only applies with --seeds-file (the secret is used to generate the episodes)")
    episodes = []
    with _input(broad=True):
        for d in args.episodes or []:
            d = Path(d)
            if (d / "public").exists():
                episodes.append(("adhoc", d.name, load_episode(d)))
            else:
                for sub in sorted(p for p in d.iterdir() if (p / "public").exists()):
                    episodes.append((d.name, sub.name, load_episode(sub)))
    secret = _secret_from_env(args.secret_env)
    min_bits = None
    if args.seeds_file:
        label, entries = _load_seeds_file(Path(args.seeds_file))
        min_bits = min(_seed_bits(e["seed"]) for e in entries)
        warning = _small_seed_warning(min_bits, secret)
        if warning:
            print(warning, file=sys.stderr)
        for e in entries:
            with _input():
                gen = generate_episode(e["seed"], e["config"], secret=secret)
            episodes.append((label, e["name"], gen.episode))
    from .policies import PolicyError, validate_policy_name

    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    try:
        for p in policies:
            validate_policy_name(p, args.policy_path)
    except PolicyError as exc:
        raise InputError(str(exc)) from exc
    if not episodes:
        raise InputError("no episodes given (use --episodes or --seeds-file)")
    if not 1 <= args.max_steps <= MAX_STEPS:
        raise InputError(f"--max-steps must be between 1 and {MAX_STEPS}")
    _custom_policy_guard(policies, args)
    if not args.in_process and any(p != "oracle" for p in policies):
        _require_agent_user()
    traj, grades = run_many(episodes, policies, mode=args.mode, isolated=not args.in_process,
                            max_steps=args.max_steps, policy_seed=args.policy_seed, policy_path=args.policy_path)
    out = Path(args.out)
    aio.write_jsonl(out / "trajectories.jsonl", traj, ascii_only=True)
    aio.write_jsonl(out / "grades.jsonl", grades, ascii_only=True)
    aio.write_json(out / "meta.json", _run_meta(args, secret if args.seeds_file else None, min_bits, len(episodes)))
    summary = summarize(grades)
    aio.write_json(out / "summary.json", summary)
    aio.write_text(out / "summary.md", markdown_table(summary) + "\n" + miss_table(summary))
    print(markdown_table(summary))
    failed = [g for g in grades if g.get("agent_error")]
    for g in failed[:10]:
        print(f"error: {g['policy']} on {g['episode_name']}: {g['agent_error']}", file=sys.stderr)
    return 3 if failed else 0


def cmd_grade(args) -> int:
    from .episode import load_episode
    from .grader import Grader
    from .schemas import validate_submission

    if not 0 <= args.steps <= MAX_STEPS:
        raise InputError(f"--steps must be between 0 and {MAX_STEPS}")
    with _input(broad=True):
        ep = load_episode(Path(args.episode))
        text = Path(args.findings).read_text(encoding="utf-8-sig")  # tolerate a UTF-8 BOM
        try:
            sub = json.loads(text)
        except json.JSONDecodeError as exc:
            sub = None
            errors = [f"{Path(args.findings).name} is not valid JSON: {exc.msg} (line {exc.lineno})"]
        except (ValueError, RecursionError) as exc:  # e.g. a 4300-digit integer or deep nesting: a bad submission
            sub = None
            errors = [f"{Path(args.findings).name} is not valid JSON: {' '.join(str(exc).split())[:120]}"]
    if sub is None:
        rep = Grader(ep.truth, ep.episode_id).grade(None, args.steps, "invalid_submission", invalid_errors=errors)
        print(json.dumps(rep, indent=2))
        return 0
    from .schemas import coerce_submission

    sub = coerce_submission(sub)  # same integral-float coercion as env.step, so both paths grade alike
    errors = validate_submission(sub, ep.episode_id)
    g = Grader(ep.truth, ep.episode_id)
    if errors:
        rep = g.grade(None, args.steps, "invalid_submission", invalid_errors=errors)
    else:
        rep = g.grade(sub, args.steps, "submitted")
    print(json.dumps(rep, indent=2))
    return 0


def cmd_transform(args) -> int:
    from .episode import load_episode
    from .transform import transform_episode

    with _input(broad=True):
        ep = load_episode(Path(args.inp))
    t = transform_episode(ep, permute_seed=args.permute_seed, remap_seed=args.remap_seed, ts_repr=args.ts_repr,
                          rename_seed=args.rename_seed)
    t.write(Path(args.out))
    print(json.dumps({"from": ep.episode_id, "to": t.episode_id, "out": str(args.out)}))
    return 0


def cmd_demo(args) -> int:
    from .episode import load_episode
    from .runner import run_one
    from .splits import EPISODES_DIR

    d = Path(args.episode) if args.episode else EPISODES_DIR / "dev" / "d08_both_interacting_kzt"
    with _input(broad=True):
        ep = load_episode(d)
    _require_agent_user()
    print(f"episode {ep.episode_id}: {ep.manifest['company']['name']}, base {ep.manifest['base_currency']}, "
          f"{ep.manifest['timezone']}, period {ep.manifest['period_start']} .. {ep.manifest['period_end']}")
    print(f"records: {ep.manifest['record_counts']}")
    for pol in ("auditor", "recon"):
        traj, g = run_one(ep, pol, split="demo", mode="eval", isolated=True)
        print(f"\n== {pol} (isolated process, eval mode) ==")
        for rec in traj:
            a = rec["action"]
            if a is None:
                continue
            obs = rec["observation"]
            if a["action"] == "submit":
                print(f"  step {rec['step']:>3}: submit {len(a['findings']['findings'])} findings")
                for f in a["findings"]["findings"]:
                    print(f"             - {f['type']} {f['affected_ids']} {f['claimed_amount_minor']} {f['currency']}")
            else:
                res = obs.get("result") or {}
                print(f"  step {rec['step']:>3}: {a['action']} {a.get('table', '')} cursor={a.get('cursor')} -> "
                      f"{len(res.get('rows') or [])} rows, {obs['remaining_steps']} steps left")
        print(f"  grader (after the run): reward {g['reward']:+.3f}  TP {g['tp']} FP {g['fp']} FN {g['fn']}  "
              f"P {g['precision']:.2f} R {g['recall']:.2f} F1 {g['f1']:.2f}")
        for i in g["issues"]:
            if not i["found"]:
                print(f"    missed {i['issue_id']} {i['type']}: {i['miss_reason']}")
    return 0


def cmd_viewer(args) -> int:
    from .viewer.build import build

    _require_agent_user()
    out = build(Path(args.out))
    print(f"wrote {out}")
    return 0


def cmd_schemas(args) -> int:
    from .schema_files import write_schemas

    for p in write_schemas(Path(args.out)):
        print(p)
    return 0


def cmd_stress(args) -> int:
    from .stress import run_stress

    if args.n < 0:
        raise InputError("--n must be >= 0")
    return run_stress(args.n, Path(args.out))


def cmd_budget(args) -> int:
    from .stress import run_budget

    try:
        budgets = [int(b) for b in args.budgets.split(",")]
    except ValueError as exc:
        raise InputError("--budgets must be comma-separated integers, e.g. 20,50,100") from exc
    if any(not 1 <= b <= MAX_STEPS for b in budgets):
        raise InputError(f"--budgets must be integers between 1 and {MAX_STEPS}")
    _require_agent_user()
    return run_budget(budgets, Path(args.out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditgym", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ck = sub.add_parser("check", help="the single offline check; --seeds-file runs it on organizer episodes")
    ck.add_argument("--seeds-file", help='JSON {"split": "...", "episodes": [{"name", "seed", "config"}]}; sections C, D, E, F run on these episodes')
    ck.add_argument("--secret-env", help="name of an environment variable holding the host secret (with --seeds-file)")
    ck.add_argument("--out", help="output directory (default runs/check, or runs/check_closed with --seeds-file)")
    ck.add_argument("--keep-runs", action="store_true", help="with --seeds-file: also write trajectories and grades (they contain the closed answer key)")
    ck.set_defaults(func=cmd_check)
    sub.add_parser("build-splits").set_defaults(func=cmd_build_splits)
    g = sub.add_parser("generate")
    g.add_argument("--seed", required=True, type=int)
    g.add_argument("--config", help="JSON file or inline JSON")
    g.add_argument("--out", required=True)
    g.add_argument("--secret-env", help="name of an environment variable holding the host secret")
    g.set_defaults(func=cmd_generate)
    v = sub.add_parser("verify")
    v.add_argument("dir")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)
    r = sub.add_parser("run")
    r.add_argument("--episodes", nargs="*", help="episode directories or folders of them")
    r.add_argument("--seeds-file", help='JSON {"split": "...", "episodes": [{"seed": ..., "config": {...}}]}')
    r.add_argument("--secret-env")
    r.add_argument("--policies", default="random,recon,flag_all,oracle")
    r.add_argument("--mode", default="eval", choices=["eval", "train"])
    r.add_argument("--max-steps", type=int, default=100)
    r.add_argument("--policy-seed", type=int, default=0)
    r.add_argument("--in-process", action="store_true", help="run agent policies in this process (open training only)")
    r.add_argument("--policy-path", help="extra import path for module:Class policies outside this repository")
    r.add_argument("--out", required=True)
    r.set_defaults(func=cmd_run)
    gr = sub.add_parser("grade")
    gr.add_argument("--episode", required=True)
    gr.add_argument("--findings", required=True)
    gr.add_argument("--steps", type=int, default=0)
    gr.set_defaults(func=cmd_grade)
    t = sub.add_parser("transform")
    t.add_argument("--in", dest="inp", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--permute-seed", type=int)
    t.add_argument("--remap-seed", type=int)
    t.add_argument("--ts-repr", choices=["utc", "local", "mixed"])
    t.add_argument("--rename-seed", type=int, help="rename the company and the invoice line wording (reference tokens are kept)")
    t.set_defaults(func=cmd_transform)
    d = sub.add_parser("demo")
    d.add_argument("--episode")
    d.set_defaults(func=cmd_demo)
    vw = sub.add_parser("viewer")
    vw.add_argument("--out", default="viewer/index.html")
    vw.set_defaults(func=cmd_viewer)
    sc = sub.add_parser("schemas")
    sc.add_argument("--out", default="schemas")
    sc.set_defaults(func=cmd_schemas)
    st = sub.add_parser("stress", help="generator stress run (not part of check)")
    st.add_argument("--n", type=int, default=300, help="number of random configurations")
    st.add_argument("--out", default="runs/stress")
    st.set_defaults(func=cmd_stress)
    bu = sub.add_parser("budget", help="auditor and recon on dev at several step budgets")
    bu.add_argument("--out", default="runs/budget")
    bu.add_argument("--budgets", default="20,50,100")
    bu.set_defaults(func=cmd_budget)
    args = ap.parse_args(argv)
    args.argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return args.func(args)
    except InputError as exc:
        print(f"error: {str(exc)[:500]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
