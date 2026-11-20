"""Process isolation: the environment and grader stay in the host process; the
policy runs in a separate child process and talks JSON lines over stdio.

host -> agent: {"type": "observation", "observation": ..., "reward": ..., "terminated": ..., "truncated": ..., "info": ...}
               {"type": "end"}
agent -> host: {"type": "action", "action": <any JSON value>}

The child gets an empty temporary working directory, a minimal environment
(no seeds, no secret, no paths to episode or grader files) and only the
observations. Its import path holds a staged copy of the agent-side modules
(the oracle, grader, generator and episode code are not on its import path) plus the
repository's examples/ policies. No host .pyc file is staged: compiled files carry the
absolute source path (co_filename). It cannot reset the environment or change its
mode. The channel is bounded in every direction:
  * reads use a thread with a deadline (pipes cannot be polled with select on Windows)
    and read at most MAX_LINE bytes per line; longer lines are discarded in 64 KB
    chunks up to the next newline and count as malformed; at most QUEUE_LINES raw lines
    (MAX_LINE bytes each, kept as bytes and decoded only when read) wait in the host, so the
    queue holds at most about QUEUE_LINES * MAX_LINE bytes; stderr is read in chunks and only a short tail is kept;
  * writes go through a writer thread with a deadline, so an agent that stops
    reading cannot stall the host past the episode time limit;
  * no line before the episode time limit -> the episode is truncated (time_limit),
    an empty answer is recorded;
  * the child exits or cannot be written to -> the run reports an agent error and the
    episode is graded as an invalid submission (reward -1, closed false), not as an
    empty answer: a crash must never beat a real answer on a clean ledger;
  * a line that is not a well-formed action message (bad JSON, too deep, too many nodes,
    too many digits, too large, unencodable text) -> a bounded `unknown_action` error
    that consumes a step; the trajectory keeps {"invalid_action": first 256 chars};
    exception: when the line starts like a submit (looks_like_submit: the "action" key with the
    value "submit" as the first member) the episode ends at once as invalid_submission, reward -1,
    as it does in process for the limits listed here (numbers, depth, nodes, size, and text that
    does not encode to UTF-8, which schemas.validate_submission rejects in process and in grade
    too); the trajectory keeps {"action": "submit", "findings": null, "invalid_action": first 256
    chars}. A replay matches in status, reward and observations, not in the grade's error text.
    Residual: a malformed submit whose "action" key is not the first member is still an
    unknown_action step;
  * any other JSON value as the action, null included, goes to env.step(), which
    returns a bounded error for anything that is not a valid action;
  * the processes the host tracks are killed when the run ends (process group on POSIX,
    Job Object on Windows) and the host hashes every file under auditgym/ (bytecode in
    __pycache__ included), configs/*.json and schemas/*.json before and after: a change is
    an agent error and changed bytecode is deleted.
Separate user: when the host runs as root (euid 0), AUDITGYM_AGENT_USER names an unprivileged account
and the platform is POSIX (the official Docker image), the child runs as that account (uid, gid, no
supplementary groups, umask 077), its working directory belongs to it, and close() kills every process
of that uid. It then cannot read the host's /proc/<pid>/environ, root-owned 0600 files or the grader
directories (written with umask 077), and cannot write to the root-owned package. If the switch is not
possible (Windows, not root, no CAP_SETUID/CAP_CHOWN) the child runs as the host's user and one warning
line is printed to stderr, once per process; nothing crashes. Strict mode (opt-in): with the environment
variable AUDITGYM_REQUIRE_AGENT_USER=1 that fallback is an error instead (AgentUserRequired).
Limitations: a child running as the same OS user is not a sandbox. It can read files it can
guess the path of, and (outside a container) its parent's command line and environment, where
--secret-env values live (on Windows through the parent's process memory; on Linux harden_host() makes
the host non-dumpable, which blocks /proc/<pid>/environ and /proc/<pid>/mem for a child without
CAP_SYS_PTRACE and not root, while /proc/<pid>/cmdline stays readable; measured by
`python -m auditgym.redteam --parent`; the command line `run` removes the --secret-env variable
from its own environment block right after reading it, see __main__._secret_from_env). Only tracked
processes are killed: a process that leaves the group or job (setsid, start_new_session,
WMI Win32_Process.Create) survives and can edit files later; only a container or a separate
OS user contains that. Outside the digest: examples/**/*.py (staged into later children),
tests/**, and site-packages .pth / usercustomize files.
"""

from __future__ import annotations

import hashlib
import json
import errno
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import io as aio
from .policies import is_external

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_LINE = 2_000_000          # bytes of one agent line (newline excluded)
MAX_DEPTH = 32                # JSON nesting depth of an action message
MAX_NODES = 100_000           # separators plus containers in one line (a valid submission has under 40 000)
MAX_NUMBER_CHARS = 40         # characters of one integer literal (valid amounts have at most 16 digits)
MAX_FLOAT_CHARS = 64
MAX_NONSUBMIT_CHARS = 2_048   # a non-submit action is under 1 KB; larger ones are not stored
ECHO_CHARS = 256              # bounded echo of an invalid action in the trajectory
CHUNK = 65_536
QUEUE_LINES = 4               # raw lines (bytes) queued in the host: at most about 4 * MAX_LINE
STDERR_TAIL = 2000
STDERR_KEEP = 8 * STDERR_TAIL
WRITE_TIMEOUT_S = 10.0
CLOSE_GRACE_S = 2.0

STAGED_MODULES = ("__init__.py", "agent.py", "auditor.py", "money.py", "schemas.py", "timeutil.py",
                  "policies/__init__.py", "policies/auditor_policy.py", "policies/common.py",
                  "policies/flag_all.py", "policies/random_policy.py", "policies/recon.py")


# ----------------------------------------------------------------- host hardening
PR_SET_DUMPABLE = 4
PR_GET_DUMPABLE = 3
HARDEN_STATUS = "not tried"   # why the last harden_host() call did or did not apply, for diagnostics
_HARDENED = False


def harden_host() -> bool:
    """On Linux make the host process non-dumpable, once per process. Returns True when it is in effect.

    prctl(PR_SET_DUMPABLE, 0) makes the kernel refuse /proc/<pid>/environ, /proc/<pid>/mem and ptrace
    on the host to a process of the same uid that has no CAP_SYS_PTRACE, so a same-user policy child can
    no longer read the --secret-env value that lives in the start-up environment block. It does not
    block: a child with CAP_SYS_PTRACE or running as root; /proc/<pid>/cmdline, which stays readable (a
    file path on the command line is visible); files the same user can read; Windows and macOS, where
    nothing is done. The policy child is started with execve, which resets its own dumpability, so it
    is unaffected. A non-dumpable non-root process cannot read its own 0400 /proc/self files (the
    package reads none). Never raises: a missing libc or prctl, or an error return, only sets
    HARDEN_STATUS and leaves the host as it was."""
    global _HARDENED, HARDEN_STATUS
    if _HARDENED:
        return True
    if not sys.platform.startswith("linux"):
        HARDEN_STATUS = "skipped: not Linux"
        return False
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        libc.prctl.restype = ctypes.c_int
        if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
            HARDEN_STATUS = "prctl(PR_SET_DUMPABLE) failed: " + os.strerror(ctypes.get_errno())
            return False
        if libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
            HARDEN_STATUS = "prctl(PR_SET_DUMPABLE) returned 0 but the process is still dumpable"
            return False
    except Exception as exc:  # no libc, no prctl symbol, ctypes missing: stay as before
        HARDEN_STATUS = f"unavailable: {type(exc).__name__}: {exc}"
        return False
    _HARDENED = True
    HARDEN_STATUS = "applied: PR_SET_DUMPABLE 0"
    return True


# ----------------------------------------------------------------- child setup
def _child_env(extra_path: str | None = None, stage: str | None = None) -> dict:
    keep = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    base = str(Path(stage).resolve()) if stage else str(PROJECT_ROOT)
    env["PYTHONPATH"] = base + (os.pathsep + str(Path(extra_path).resolve()) if extra_path else "")
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _copy_source(src: Path, dst: Path) -> None:
    """Copy one source file. Host .pyc files are never copied: their co_filename holds the
    absolute repository path, which would hand the child the repository root."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def stage_agent_code(dest: Path, policy: str | None = None) -> Path:
    """Copy only the agent-side modules under `dest`; return `dest`.

    For a module:Class policy the repository's examples/ and the policy's own top-level module or
    package (when it lives in the repository) are staged too, as *.py files only. The staged tree
    is the child's import root: the oracle, grader, generator, episode and verifier modules are not
    in it, and the repository root is not on the child's path. Limitation: an in-repo policy that
    imports another in-repo top-level package, or an auditgym module outside STAGED_MODULES, fails
    to load (an agent error); put such code under --policy-path instead."""
    pkg = PROJECT_ROOT / "auditgym"
    for rel in STAGED_MODULES:
        src = pkg / rel
        if src.exists():
            _copy_source(src, dest / "auditgym" / rel)
    if policy and is_external(policy):
        top = policy.split(":")[0].split(".")[0]
        for name in dict.fromkeys(("examples", top)):
            if name == "auditgym":
                continue
            folder, single = PROJECT_ROOT / name, PROJECT_ROOT / f"{name}.py"
            if folder.is_dir():
                for src in folder.rglob("*.py"):
                    _copy_source(src, dest / name / src.relative_to(folder))
            elif single.is_file():
                _copy_source(single, dest / single.name)
    return dest


# --------------------------------------------------------------- code integrity
def code_digest(root: Path | None = None) -> dict:
    """{relative path: sha256} of every file under auditgym/ (bytecode included), configs/*.json
    and schemas/*.json. Compiled files count: a planted .pyc with a matching header would be
    loaded in place of the source by every later Python process. auditgym/viewer/ is left out:
    the offline viewer (template, graph engine, builder) is never imported by the environment,
    the grader or an agent, and editing it during a run must not fail the run."""
    root = Path(root) if root else PROJECT_ROOT
    pkg = root / "auditgym"
    files = {p for p in pkg.rglob("*") if p.is_file() and p.relative_to(pkg).parts[0] != "viewer"}
    files |= set((root / "configs").glob("*.json")) | set((root / "schemas").glob("*.json"))
    out = {}
    for path in sorted(files):
        rel = path.relative_to(root).as_posix()
        try:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            out[rel] = "unreadable"
    return out


def refresh_bytecode(root: Path | None = None) -> None:
    """Make auditgym/__pycache__ complete and current (only when this process writes bytecode), so a
    legitimate lazy compile during a run is not mistaken for tampering. Best effort."""
    if sys.dont_write_bytecode:
        return
    root = Path(root) if root else PROJECT_ROOT
    try:
        import compileall
        compileall.compile_dir(str(root / "auditgym"), quiet=2)
    except Exception:
        pass


def purge_changed_bytecode(root: Path | None, changed: list) -> None:
    """Delete changed or planted compiled files so they cannot poison later processes."""
    root = Path(root) if root else PROJECT_ROOT
    for rel in changed:
        if "/__pycache__/" in rel or rel.endswith((".pyc", ".pyo")):
            try:
                (root / rel).unlink()
            except OSError:
                pass


def changed_files(before: dict, after: dict) -> list:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


# ------------------------------------------------------------------ line parsing
def _parse_int(text: str) -> int:
    if len(text) > MAX_NUMBER_CHARS:
        raise ValueError("integer literal too long")
    return int(text)


def _parse_float(text: str) -> float:
    if len(text) > MAX_FLOAT_CHARS:
        raise ValueError("number literal too long")
    return float(text)


def _parse_constant(text: str):
    raise ValueError("NaN and Infinity are not JSON")


def _shape_ok(value) -> bool:
    """Depth and node bounds, checked without recursion (identical on every Python version)."""
    stack = [(value, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            return False
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
    return True


_SUBMIT_START = re.compile(
    r'\s*\{\s*(?:"type"\s*:\s*"action"\s*,\s*"action"\s*:\s*\{\s*)?"action"\s*:\s*"submit"\s*[,}]')


def looks_like_submit(echo) -> bool:
    """True when a malformed line starts like a submit: optional whitespace, an opening brace, the "action" key
    with the value "submit" as the first member (inside the {"type": "action", "action": ...} envelope the
    first member of the inner object), whitespace tolerated. Only the echo (the first ECHO_CHARS characters)
    is read. Residual: a malformed submit whose "action" key is not the first member, or that starts any other
    way, is not recognised and stays an unknown_action step."""
    return isinstance(echo, str) and _SUBMIT_START.match(echo) is not None


def parse_agent_line(line) -> tuple:
    """('eof'|'malformed'|'action', action | echo). Never raises.

    For 'malformed' the second item is the first ECHO_CHARS characters of the line (or None).
    Limits are explicit, so the result does not depend on the interpreter's recursion limit,
    its C decoder, or PYTHONINTMAXSTRDIGITS."""
    if line is None:
        return "eof", None
    if not isinstance(line, str):
        return "malformed", None
    echo = line[:ECHO_CHARS].rstrip("\r\n")
    if len(line) > MAX_LINE:
        return "malformed", echo
    if line.count("[") + line.count("{") + line.count(",") > MAX_NODES:
        return "malformed", echo
    try:
        msg = json.loads(line, parse_int=_parse_int, parse_float=_parse_float, parse_constant=_parse_constant)
    except Exception:  # JSONDecodeError, RecursionError (deep nesting), ValueError (long numbers)
        return "malformed", echo
    if not _shape_ok(msg):
        return "malformed", echo
    if not isinstance(msg, dict) or msg.get("type") != "action" or "action" not in msg:
        return "malformed", echo
    action = msg["action"]
    if len(line) > MAX_NONSUBMIT_CHARS and not (isinstance(action, dict) and action.get("action") == "submit"):
        return "malformed", echo
    try:
        json.dumps(action, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except Exception:  # lone surrogates, NaN/Infinity, and other non-JSON content
        return "malformed", echo
    return "action", action


# --------------------------------------------------------- process-tree control
class _WinJob:
    """A Windows Job Object that kills every process in it when terminated or closed."""

    def __init__(self, proc):
        self.handle = None
        self._k32 = None
        try:
            import ctypes
            from ctypes import wintypes

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class Basic(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class IoCounters(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in ("ro", "wo", "oo", "rb", "wb", "ob")]

            class Extended(ctypes.Structure):
                _fields_ = [("Basic", Basic), ("Io", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]

            k32.CreateJobObjectW.restype = wintypes.HANDLE
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            job = k32.CreateJobObjectW(None, None)
            if not job:
                return
            info = Extended()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
            ok = ok and k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle)))
            if not ok:
                k32.CloseHandle(job)
                return
            self.handle, self._k32 = job, k32
        except Exception:
            self.handle = None

    def kill(self) -> bool:
        if self.handle is None:
            return False
        try:
            self._k32.TerminateJobObject(self.handle, 1)
            self._k32.CloseHandle(self.handle)
        except Exception:
            return False
        finally:
            self.handle = None
        return True


def _uid_pids(uid: int) -> list:
    pids = []
    try:
        names = os.listdir("/proc")
    except OSError:
        return pids
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/status", encoding="ascii", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        state = re.search(r"^State:\s*(\S)", text, re.M)
        real = re.search(r"^Uid:\s*(\d+)", text, re.M)
        if real and int(real.group(1)) == uid and not (state and state.group(1) in "ZX"):
            pids.append(int(name))
    return pids


def kill_uid(uid: int, gid: int | None = None) -> bool:
    """SIGKILL every process of `uid` (needs root). Returns True when none is left.

    A helper started as that uid calls kill(-1), which signals all of its processes atomically, so a
    fork loop cannot grow back between two scans. The /proc scan is only a check and a fallback."""
    for _ in range(5):
        if not _uid_pids(uid):
            return True
        try:
            subprocess.run([sys.executable, "-c", "import os,signal;os.kill(-1,signal.SIGKILL)"],
                           user=uid, group=gid if gid is not None else uid, extra_groups=[], env={}, cwd="/",
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
        for pid in _uid_pids(uid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.05)
    return not _uid_pids(uid)


_SWITCHED = False  # a user switch has worked in this process: never fall back to the host user silently
_WARNED = False
REQUIRE_ENV = "AUDITGYM_REQUIRE_AGENT_USER"


class AgentUserRequired(RuntimeError):
    """Strict mode (AUDITGYM_REQUIRE_AGENT_USER=1) and the policy cannot run as the separate agent user.

    Not an OSError on purpose: run_episode_isolated turns OSError into a graded agent error, and this must stop the run."""


def require_agent_user() -> bool:
    """True when AUDITGYM_REQUIRE_AGENT_USER is exactly 1: the fallback to the host user is then an error."""
    return os.environ.get(REQUIRE_ENV, "").strip() == "1"


def _warn_same_user(reason: str) -> None:
    global _WARNED
    if require_agent_user():
        raise AgentUserRequired(f"{REQUIRE_ENV}=1 but the policy cannot run as a separate user: {reason}")
    if _WARNED or not os.environ.get("AUDITGYM_AGENT_USER", "").strip():
        return  # nobody asked for a separate user: nothing to warn about
    _WARNED = True
    print(f"auditgym: warning: policy runs as the host user ({reason}); "
          "the official image run as root with default capabilities uses a separate policy user", file=sys.stderr)


def _proc_listable() -> bool:
    """True when /proc can be listed: without it kill_uid cannot see the agent's processes."""
    try:
        os.listdir("/proc")
    except OSError:
        return False
    return True


def _no_switch_reason() -> str:
    """Why aio.agent_identity() found no account to switch to."""
    if not os.environ.get("AUDITGYM_AGENT_USER", "").strip():
        return "AUDITGYM_AGENT_USER is not set"
    if os.name != "posix":
        return "this platform cannot switch user"
    if os.geteuid() != 0:
        return "not running as root"
    if aio.agent_identity() is not None:
        return "/proc cannot be listed, so leftover agent processes could not be killed"
    return "AUDITGYM_AGENT_USER names no existing non-root account"


def _chown_tree(root: str, uid: int, gid: int) -> None:
    os.chown(root, uid, gid)
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            os.chown(os.path.join(base, name), uid, gid, follow_symlinks=False)


def _kill_tree(proc, job) -> None:
    """Kill the child and everything it started, even when the direct child already exited."""
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # the child leads its own session and group
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        killed = job.kill() if job is not None else False
        if not killed and proc.poll() is None:
            try:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
    try:
        proc.kill()
    except OSError:
        pass


class AgentProcess:
    """A policy running in a child process.

    Raises AgentUserRequired instead of falling back to the host user when AUDITGYM_REQUIRE_AGENT_USER=1."""

    def _same_user(self, reason: str) -> None:
        """Warn once that the policy runs as the host user; in strict mode raise (and drop the temporary directory)."""
        try:
            _warn_same_user(reason)
        except AgentUserRequired:
            self._tmp.cleanup()
            raise

    def __init__(self, policy: str, policy_seed: int = 0, policy_path: str | None = None):
        harden_host()
        self._tmp = tempfile.TemporaryDirectory(prefix="auditgym_agent_", ignore_cleanup_errors=True)
        self.write_timeout_s = WRITE_TIMEOUT_S
        self.write_timed_out = False
        self.abandon = False  # set by the host when the agent timed out: skip the polite shutdown
        stage = stage_agent_code(Path(self._tmp.name) / "code", policy)
        global _SWITCHED
        self._agent_uid = self._agent_gid = None
        ident = aio.agent_identity()
        if ident is not None and not _proc_listable():
            ident = None
        if ident is not None:
            if not _SWITCHED and _uid_pids(ident[1]):
                self._same_user(f"account {ident[0]} already has processes; use a dedicated account, one run per container")
                ident = None
            elif _SWITCHED and not kill_uid(ident[1], ident[2]):
                self._tmp.cleanup()
                raise OSError(f"processes of uid {ident[1]} survived the previous episode")
        if ident is not None:
            try:
                _chown_tree(self._tmp.name, ident[1], ident[2])
            except OSError as exc:
                if not isinstance(exc, PermissionError) and exc.errno != errno.EINVAL:
                    self._tmp.cleanup()
                    raise
                if _SWITCHED:
                    self._tmp.cleanup()
                    raise
                self._same_user(f"chown refused: {exc.strerror or exc}")
                ident = None
        if ident is None:
            self._same_user(_no_switch_reason())
        cmd = [sys.executable, "-m", "auditgym.agent", "--policy", policy, "--policy-seed", str(int(policy_seed))]
        kw = {"start_new_session": True} if os.name == "posix" else {}
        popen = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self._tmp.name,
                     env=_child_env(policy_path, stage=str(stage)), **kw)
        if ident is not None:
            try:
                self.proc = subprocess.Popen(cmd, user=ident[1], group=ident[2], extra_groups=[], umask=0o077, **popen)
                self._agent_uid, self._agent_gid = ident[1], ident[2]
                _SWITCHED = True
            except PermissionError as exc:  # setuid refused (capability dropped): same user, tmp back to the host
                if _SWITCHED:
                    self._tmp.cleanup()
                    raise
                self._same_user(f"setuid refused: {exc.strerror or exc}")
                try:
                    _chown_tree(self._tmp.name, os.geteuid(), os.getegid())
                except OSError:
                    pass
                ident = None
            except OSError:  # EAGAIN, ENOMEM, EMFILE ...: an error, never a silent switch to the host user
                self._tmp.cleanup()
                raise
        if ident is None:
            self.proc = subprocess.Popen(cmd, **popen)
        self._job = _WinJob(self.proc) if os.name == "nt" else None
        self._stop = threading.Event()
        self._eof = False
        self._exit_seen = None
        self._lines: queue.Queue = queue.Queue(maxsize=QUEUE_LINES)
        self._wq: queue.Queue = queue.Queue()
        self._err = b""
        self._threads = [threading.Thread(target=f, daemon=True)
                         for f in (self._read_loop, self._read_err, self._write_loop)]
        for t in self._threads:
            t.start()

    # -- bounded readers --------------------------------------------------
    def _put(self, item) -> bool:
        while not self._stop.is_set():
            try:
                self._lines.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    def _read_loop(self) -> None:
        out = self.proc.stdout
        try:
            while True:
                chunk = out.readline(MAX_LINE + 1)
                if not chunk:
                    break
                if len(chunk) > MAX_LINE and not chunk.endswith(b"\n"):
                    head = chunk[: 4 * ECHO_CHARS].decode("utf-8", "replace")
                    del chunk
                    while True:  # discard the rest of the line, 64 KB at a time
                        more = out.readline(CHUNK)
                        if not more or more.endswith(b"\n"):
                            break
                    item = ("oversize", head)
                else:
                    item = ("line", bytes(chunk))
                if not self._put(item):
                    return
        except (OSError, ValueError):
            pass
        self._put(("eof", None))

    def _read_err(self) -> None:
        err = self.proc.stderr
        try:
            while True:
                chunk = err.read1(CHUNK)
                if not chunk:
                    break
                self._err = (self._err + chunk)[-STDERR_KEEP:]
        except (OSError, ValueError):
            pass

    def stderr_tail(self) -> str:
        return self._err.decode("utf-8", "replace")[-STDERR_TAIL:]

    # -- writer with a deadline ------------------------------------------
    def _write_loop(self) -> None:
        stdin = self.proc.stdin
        while True:
            item = self._wq.get()
            if item is None:
                return
            data, done, result = item
            try:
                stdin.write(data)
                stdin.flush()
                result.append(True)
            except (BrokenPipeError, OSError, ValueError):
                result.append(False)
            done.set()

    def send(self, message: dict) -> bool:
        """Write one message within self.write_timeout_s. False if the pipe is broken or the
        agent did not take the data in time (then write_timed_out is True)."""
        if self.write_timed_out:
            return False
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8", "replace")
        done, result = threading.Event(), []
        self._wq.put((data, done, result))
        if not done.wait(max(0.01, self.write_timeout_s)):
            self.write_timed_out = True
            return False
        return bool(result and result[0])

    def receive(self, timeout_s: float) -> tuple:
        """('timeout'|'eof'|'malformed'|'action', action | echo)."""
        if self._eof:
            return "eof", None
        deadline = time.monotonic() + max(0.001, timeout_s)
        while True:
            remaining = deadline - time.monotonic()
            try:
                kind, payload = self._lines.get(timeout=max(0.001, min(0.25, remaining)))
            except queue.Empty:
                if self.proc.poll() is not None:
                    # the child is gone; a grandchild may still hold the pipe open, so do not wait for EOF
                    now = time.monotonic()
                    if self._exit_seen is None:
                        self._exit_seen = now
                    elif now - self._exit_seen > 0.3:
                        self._eof = True
                        return "eof", None
                if remaining <= 0:
                    return "timeout", None
                continue
            if kind == "eof":
                self._eof = True
                return "eof", None
            if kind == "oversize":
                return "malformed", payload.rstrip("\r\n")[:ECHO_CHARS]
            return parse_agent_line(payload.decode("utf-8", "replace"))

    def close(self) -> None:
        try:
            if self.proc.poll() is None and not self.abandon:
                self.write_timeout_s = 1.0
                if self.send({"type": "end"}):  # an agent that cannot even be told to stop is killed at once
                    try:
                        self.proc.wait(timeout=CLOSE_GRACE_S)
                    except subprocess.TimeoutExpired:
                        pass
        finally:
            _kill_tree(self.proc, self._job)
            if self._agent_uid is not None:
                kill_uid(self._agent_uid, self._agent_gid)
            self._stop.set()
            self._wq.put(None)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for t in self._threads:
                t.join(timeout=2)
            if not any(t.is_alive() for t in self._threads):
                for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                    try:
                        stream.close()
                    except (OSError, ValueError):
                        pass
            self._cleanup_tmp()

    def _cleanup_tmp(self) -> None:
        for _ in range(10):  # a killed process may still hold its working directory for a moment
            try:
                self._tmp.cleanup()
            except Exception:
                pass
            if not os.path.exists(self._tmp.name):
                return
            time.sleep(0.1)
            shutil.rmtree(self._tmp.name, ignore_errors=True)


def run_episode_isolated(env, reset_kwargs: dict, policy: str, policy_seed: int = 0, on_step=None,
                         policy_path: str | None = None) -> dict:
    """Drive one episode with the env here and the policy in a child process.

    on_step(record) receives every agent-visible transition (step 0 = reset).
    Returns {"grade", "agent_time_s", "agent_error"}; agent_error is None unless the child
    process exited before the episode ended or the grader code changed during the run. Both are
    graded as an invalid submission (reward -1).
    """
    obs, info = env.reset(**reset_kwargs)
    refresh_bytecode()
    before = code_digest()
    try:
        agent = AgentProcess(policy, policy_seed, policy_path)
    except OSError as exc:
        message = f"agent process could not be started: {exc.strerror or exc}"
        env.force_agent_error("agent_error", message)
        return {"grade": env.grader_report(), "agent_time_s": 0.0, "agent_error": message}
    agent_time = 0.0
    agent_error = None
    reward, terminated, truncated = 0.0, False, False

    def exit_message() -> str:
        try:
            code = agent.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            code = None
        tail = agent.stderr_tail().strip().splitlines()
        return f"agent process exited with code {code}" + (f": {tail[-1][:300]}" if tail else "")

    def record_stop(code: str, message: str) -> None:
        if on_step:
            on_step({"step": env.steps, "action": None,
                     "observation": {"result": None, "error": {"code": code, "message": message},
                                     "remaining_steps": max(0, env.max_steps - env.steps)},
                     "reward": 0.0, "terminated": False, "truncated": True})

    def stop(reason: str, code: str, message: str) -> None:
        agent.abandon = True
        env.force_stop(reason)
        record_stop(code, message)

    def crash() -> str:
        message = exit_message()
        env.force_agent_error("agent_exited", message)
        record_stop("agent_exited", "The agent process stopped; the run is graded as an invalid submission.")
        return message

    try:
        if on_step:
            on_step({"step": 0, "action": None, "observation": obs, "reward": 0.0, "terminated": False, "truncated": False})
        while True:
            over = terminated or truncated
            agent.write_timeout_s = 2.0 if over else max(0.05, env.time_limit_s - env.elapsed_s())
            if not agent.send({"type": "observation", "observation": obs, "reward": reward,
                               "terminated": terminated, "truncated": truncated, "info": info}):
                if not over:
                    if getattr(agent, "write_timed_out", False):
                        stop("time_limit", "time_limit", "The agent did not read its input in time; an empty answer was recorded.")
                    else:
                        agent_error = crash()
                break
            if over:
                break
            remaining = env.time_limit_s - env.elapsed_s()
            t0 = time.monotonic()
            kind, action = agent.receive(timeout_s=remaining)
            agent_time += time.monotonic() - t0
            if kind == "timeout":
                stop("time_limit", "time_limit", "No action before the time limit; an empty answer was recorded.")
                break
            if kind == "eof":
                agent_error = crash()
                break
            recorded = action
            if kind == "malformed":
                echo = action if isinstance(action, str) else ""
                recorded = {"invalid_action": echo[:ECHO_CHARS]}
                action = {"action": "__malformed__"}
                if looks_like_submit(echo):  # same as in process: an invalid submit ends the episode (reward -1)
                    action = {"action": "submit", "findings": None}
                    recorded = {**action, "invalid_action": echo[:ECHO_CHARS]}  # same status, reward and observations on replay
            obs, reward, terminated, truncated, info = env.step(action)
            if on_step:
                on_step({"step": env.steps, "action": recorded, "observation": obs, "reward": reward,
                         "terminated": terminated, "truncated": truncated})
    finally:
        agent.close()
    changed = changed_files(before, code_digest())
    if changed:
        purge_changed_bytecode(None, changed)
        agent_error = "grader code changed during the agent run: " + ", ".join(changed[:5])
        env.force_agent_error("agent_error", agent_error)
    return {"grade": env.grader_report(), "agent_time_s": agent_time, "agent_error": agent_error}
