"""Generate a sample of episodes with the check-set mix and run tools/recompute_keys.py on it and on the 20 committed episodes.

  python tools/recompute_sample.py OUT_DIR [N] [--record DIR]

OUT_DIR must not exist or must be empty. The sample is auditgym.tells.sample_entries(N) (master string auditgym-tells-v1), written
with `python -m auditgym generate`; the recompute itself (tools/recompute_keys.py) never imports auditgym.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    record = None
    args = []
    it = iter(argv)
    for a in it:
        if a == "--record":
            record = next(it)
        else:
            args.append(a)
    if not args:
        print(__doc__)
        return 2
    out = args[0]
    n = int(args[1]) if len(args) > 1 else 60
    if os.path.isdir(out) and os.listdir(out):
        print("error: OUT_DIR is not empty", file=sys.stderr)
        return 2
    sys.path.insert(0, ROOT)
    from auditgym import tells

    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    for name, seed, config in tells.sample_entries(n):
        dest = os.path.join(out, "sample", name)
        r = subprocess.run([sys.executable, "-m", "auditgym", "generate", "--seed", str(seed), "--config", json.dumps(config), "--out", dest],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        if r.returncode:
            print(f"error: generating {name}: {r.stderr.strip()[-200:]}", file=sys.stderr)
            return 2
    cmd = [sys.executable, os.path.join(ROOT, "tools", "recompute_keys.py"), os.path.join(out, "sample"),
           os.path.join(ROOT, "episodes", "train"), os.path.join(ROOT, "episodes", "dev")]
    if record:
        cmd += ["--record", record]
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
