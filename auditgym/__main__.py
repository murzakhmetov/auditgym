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
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import io as aio


def _load_config(arg: str | None) -> dict:
    if not arg:
        return {}
    p = Path(arg)
    if p.exists():
        return aio.read_json(p)
    return json.loads(arg)


def cmd_check(args) -> int:
    from .check import main

    return main()


def cmd_build_splits(args) -> int:
    from .splits import write_splits

    index = write_splits()
    for e in index:
        print(f"{e['split']}/{e['name']}: {e['episode_id']} issues={e['issues']} rows={e['ledger_rows']} docs={e['documents']}")
    return 0


def cmd_generate(args) -> int:
    from .generator import generate_episode

    secret = os.environ.get(args.secret_env) if args.secret_env else None
    gen = generate_episode(args.seed, _load_config(args.config), secret=secret)
    gen.episode.write(Path(args.out))
    print(json.dumps({"episode_id": gen.episode.episode_id, "issues": len(gen.episode.truth["issues"]),
                      "attempts": gen.attempts, "out": str(args.out)}))
    return 0


def cmd_verify(args) -> int:
    from .episode import load_episode
    from .verify import verify_generated

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

    episodes = []
    for d in args.episodes or []:
        d = Path(d)
        if (d / "public").exists():
            episodes.append(("adhoc", d.name, load_episode(d)))
        else:
            for sub in sorted(p for p in d.iterdir() if (p / "public").exists()):
                episodes.append((d.name, sub.name, load_episode(sub)))
    if args.seeds_file:
        spec = aio.read_json(Path(args.seeds_file))
        secret = os.environ.get(args.secret_env) if args.secret_env else None
        for e in spec["episodes"]:
            gen = generate_episode(e["seed"], e.get("config", {}), secret=secret)
            episodes.append((spec.get("split", "closed"), e.get("name", gen.episode.episode_id), gen.episode))
    from .policies import PolicyError, validate_policy_name

    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    try:
        for p in policies:
            validate_policy_name(p, args.policy_path)
    except PolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not episodes:
        print("error: no episodes given (use --episodes or --seeds-file)", file=sys.stderr)
        return 2
    traj, grades = run_many(episodes, policies, mode=args.mode, isolated=not args.in_process,
                            max_steps=args.max_steps, policy_seed=args.policy_seed, policy_path=args.policy_path)
    out = Path(args.out)
    aio.write_jsonl(out / "trajectories.jsonl", traj, ascii_only=True)
    aio.write_jsonl(out / "grades.jsonl", grades, ascii_only=True)
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

    ep = load_episode(Path(args.episode))
    sub = aio.read_json(Path(args.findings))
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

    ep = load_episode(Path(args.inp))
    t = transform_episode(ep, permute_seed=args.permute_seed, remap_seed=args.remap_seed, ts_repr=args.ts_repr)
    t.write(Path(args.out))
    print(json.dumps({"from": ep.episode_id, "to": t.episode_id, "out": str(args.out)}))
    return 0


def cmd_demo(args) -> int:
    from .episode import load_episode
    from .runner import run_one
    from .splits import EPISODES_DIR

    d = Path(args.episode) if args.episode else EPISODES_DIR / "dev" / "d08_both_interacting_kzt"
    ep = load_episode(d)
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

    out = build(Path(args.out))
    print(f"wrote {out}")
    return 0


def cmd_schemas(args) -> int:
    from .schema_files import write_schemas

    for p in write_schemas(Path(args.out)):
        print(p)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditgym", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("build-splits").set_defaults(func=cmd_build_splits)
    g = sub.add_parser("generate")
    g.add_argument("--seed", required=True)
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
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
