"""Process isolation: the environment and grader stay in the host process; the
policy runs in a separate child process and talks JSON lines over stdio.

host -> agent: {"type": "observation", "observation": ..., "reward": ..., "terminated": ..., "truncated": ..., "info": ...}
               {"type": "end"}
agent -> host: {"type": "action", "action": <any JSON value>}

The child gets an empty temporary working directory, a minimal environment
(no seeds, no secret, no paths to episode or grader files) and only the
observations. It cannot reset the environment or change its mode. Reads use
a thread with a deadline (pipes cannot be polled with select on Windows):
  * no line before the episode time limit -> the episode is truncated (time_limit);
  * the child exits -> the episode is truncated (agent_exited) and the run reports an agent error;
  * a line that is not a well-formed action message (bad JSON, too deep, too large,
    unencodable text) -> a bounded `unknown_action` error that consumes a step;
  * any JSON value as the action, null included, goes to env.step(), which returns
    a bounded error for anything that is not a valid action.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_LINE = 2_000_000
STDERR_TAIL = 2000


def _child_env(extra_path: str | None = None) -> dict:
    keep = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + str(Path(extra_path).resolve()) if extra_path else "")
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def parse_agent_line(line) -> tuple:
    """('eof'|'malformed'|'action', action). Never raises."""
    if line is None:
        return "eof", None
    if len(line) > MAX_LINE:
        return "malformed", None
    try:
        msg = json.loads(line)
    except Exception:  # JSONDecodeError, RecursionError (deep nesting), ValueError (huge integers)
        return "malformed", None
    if not isinstance(msg, dict) or msg.get("type") != "action" or "action" not in msg:
        return "malformed", None
    action = msg["action"]
    try:
        json.dumps(action, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except Exception:  # lone surrogates, NaN/Infinity, and other non-JSON content
        return "malformed", None
    return "action", action


class AgentProcess:
    """A policy running in a child process."""

    def __init__(self, policy: str, policy_seed: int = 0, policy_path: str | None = None):
        self._tmp = tempfile.TemporaryDirectory(prefix="auditgym_agent_")
        cmd = [sys.executable, "-m", "auditgym.agent", "--policy", policy, "--policy-seed", str(int(policy_seed))]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._tmp.name,
            env=_child_env(policy_path),
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._lines: queue.Queue = queue.Queue()
        self._stderr: list = []
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._err_reader = threading.Thread(target=self._read_err, daemon=True)
        self._err_reader.start()

    def _read_loop(self) -> None:
        try:
            for line in self.proc.stdout:
                self._lines.put(line)
        except (OSError, ValueError):
            pass
        self._lines.put(None)

    def _read_err(self) -> None:
        try:
            for line in self.proc.stderr:
                self._stderr.append(line)
                if sum(len(x) for x in self._stderr) > 4 * STDERR_TAIL:
                    del self._stderr[: len(self._stderr) // 2]
        except (OSError, ValueError):
            pass

    def stderr_tail(self) -> str:
        return "".join(self._stderr)[-STDERR_TAIL:]

    def send(self, message: dict) -> bool:
        try:
            self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def receive(self, timeout_s: float) -> tuple:
        """('timeout'|'eof'|'malformed'|'action', action)."""
        try:
            line = self._lines.get(timeout=max(0.001, timeout_s))
        except queue.Empty:
            return "timeout", None
        return parse_agent_line(line)

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.send({"type": "end"})
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        finally:
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
            self._tmp.cleanup()


def run_episode_isolated(env, reset_kwargs: dict, policy: str, policy_seed: int = 0, on_step=None,
                         policy_path: str | None = None) -> dict:
    """Drive one episode with the env here and the policy in a child process.

    on_step(record) receives every agent-visible transition (step 0 = reset).
    Returns {"grade", "agent_time_s", "agent_error"}; agent_error is None unless
    the child process exited before the episode ended.
    """
    obs, info = env.reset(**reset_kwargs)
    agent = AgentProcess(policy, policy_seed, policy_path)
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

    def stop(reason: str, code: str, message: str) -> None:
        env.force_stop(reason)
        if on_step:
            on_step({"step": env.steps, "action": None,
                     "observation": {"result": None, "error": {"code": code, "message": message},
                                     "remaining_steps": max(0, env.max_steps - env.steps)},
                     "reward": 0.0, "terminated": False, "truncated": True})

    try:
        if on_step:
            on_step({"step": 0, "action": None, "observation": obs, "reward": 0.0, "terminated": False, "truncated": False})
        while True:
            if not agent.send({"type": "observation", "observation": obs, "reward": reward,
                               "terminated": terminated, "truncated": truncated, "info": info}):
                if not (terminated or truncated):
                    agent_error = exit_message()
                    stop("agent_exited", "agent_exited", "The agent process stopped; an empty answer was recorded.")
                break
            if terminated or truncated:
                break
            remaining = env.time_limit_s - env.elapsed_s()
            t0 = time.monotonic()
            kind, action = agent.receive(timeout_s=remaining)
            agent_time += time.monotonic() - t0
            if kind == "timeout":
                stop("time_limit", "time_limit", "No action before the time limit; an empty answer was recorded.")
                break
            if kind == "eof":
                agent_error = exit_message()
                stop("agent_exited", "agent_exited", "The agent process stopped; an empty answer was recorded.")
                break
            if kind == "malformed":
                action = {"action": "__malformed__"}
            obs, reward, terminated, truncated, info = env.step(action)
            if on_step:
                on_step({"step": env.steps, "action": action, "observation": obs, "reward": reward,
                         "terminated": terminated, "truncated": truncated})
    finally:
        agent.close()
    return {"grade": env.grader_report(), "agent_time_s": agent_time, "agent_error": agent_error}
