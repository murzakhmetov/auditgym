"""Child-process entry point: `python -m auditgym.agent --policy NAME`.

Reads observations from stdin, writes actions to the protocol channel. NAME is a built-in
agent-side policy (random, recon, flag_all, auditor) or "module.path:ClassName".
The oracle needs the answer key and is refused here: it runs grader-side.

Protocol channel: before the policy is loaded, the real stdout is duplicated to a private
descriptor (not inherited by the policy's own subprocesses) and fd 1 / sys.stdout are
pointed at stderr. A stray print() in a policy, or a library writing to stdout, therefore
lands in the host's bounded stderr tail and cannot shift the line-by-line protocol.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .policies import GRADER_POLICIES, PolicyError, make_policy

PROTOCOL_OUT = None  # binary writer on the private protocol descriptor (set by main)
INTEGRITY_STATUS = "not attempted"  # what _lower_integrity() did in this child (read by the redteam probe)
NO_LOWER_ENV = "AUDITGYM_NO_LOW_INTEGRITY"  # set by the host: "1" for the redteam control run, else why it could not lower
POLICY_PATH_ENV = "AUDITGYM_POLICY_PATH"  # Windows: the policy directory, added to sys.path only after the token is lowered


def _lower_integrity() -> str:
    """Windows: lower this process's own token to Low integrity (S-1-16-4096) before any policy code loads.

    Mandatory integrity control gives process objects a no-read-up policy: a Low process cannot open a
    Medium process (the host, its shell) with PROCESS_VM_READ, so it cannot read the host's environment block
    or memory. A process may lower its own level and cannot raise it again; its children inherit the token.
    Never raises: returns a status string, "lowered ..." on success, "failed: ..." otherwise (the policy then
    runs as before). The host gives the child's working directory a Low label so writes there keep working. Nothing else is
    writable at Low: the policy directory, the repository and default-labelled directories in the user profile
    (%LOCALAPPDATA%, caches with absolute paths) raise PermissionError, and the episode is graded as an agent error."""
    if os.name != "nt":
        return "not applicable: not Windows"
    off = os.environ.get(NO_LOWER_ENV)
    if off:
        return "off: control run" if off == "1" else "off: " + off
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                            ctypes.POINTER(wintypes.DWORD)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        relabel = _label_own_process(adv, k32)  # while still Medium: afterwards the process could not open itself
        token = wintypes.HANDLE()
        # TOKEN_ADJUST_DEFAULT (0x80) is what SetTokenInformation(TokenIntegrityLevel) needs; TOKEN_QUERY (0x8)
        # lets us read the level back on the same handle (a Low process can no longer open its own token)
        if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0080 | 0x0008, ctypes.byref(token)):
            return f"failed: OpenProcessToken error {ctypes.get_last_error()}"
        try:
            sid = (ctypes.c_ubyte * 12)(1, 1, 0, 0, 0, 0, 0, 16, 0x00, 0x10, 0x00, 0x00)  # S-1-16-4096, Low

            class MandatoryLabel(ctypes.Structure):
                _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

            label = MandatoryLabel(ctypes.cast(sid, ctypes.c_void_p).value, 0x20)  # SE_GROUP_INTEGRITY
            size = ctypes.sizeof(label) + len(sid)
            if not adv.SetTokenInformation(token, 25, ctypes.byref(label), size):  # TokenIntegrityLevel
                return f"failed: SetTokenInformation error {ctypes.get_last_error()}"
            need = wintypes.DWORD()
            buf = ctypes.create_string_buffer(256)
            if adv.GetTokenInformation(token, 25, buf, 256, ctypes.byref(need)):
                sid_ptr = ctypes.c_void_p.from_buffer(buf).value
                adv.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
                adv.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
                adv.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
                adv.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
                count = adv.GetSidSubAuthorityCount(sid_ptr)[0]
                rid = adv.GetSidSubAuthority(sid_ptr, count - 1)[0]
                if rid > 0x1000:
                    return f"failed: the call succeeded but the level reads back as 0x{rid:04x}"
                return f"lowered to Low integrity (RID 0x{rid:04x}){relabel}"
            return f"lowered to Low integrity (not read back){relabel}"
        finally:
            k32.CloseHandle(token)
    except Exception as exc:  # ctypes missing, odd Windows build: the policy runs as before
        return f"failed: {type(exc).__name__}: {exc}"


def _label_own_process(adv, k32) -> str:
    """Give this process object a Low label (SDDL S:(ML;;NW;;;LW)) before the token is lowered. A Low process
    may not open a Medium process with write-type rights, itself included: without this, OpenProcess(PROCESS_DUP_HANDLE,
    own pid) fails and multiprocessing / ProcessPoolExecutor stop working in the policy. Returns "" on success,
    else ", own process not relabelled: <why>" (the child still lowers; only such pools would fail)."""
    import ctypes
    from ctypes import wintypes

    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    adv.GetSecurityDescriptorSacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
                                              ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    adv.SetSecurityInfo.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_void_p]
    adv.SetSecurityInfo.restype = wintypes.DWORD
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    desc = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW("S:(ML;;NW;;;LW)", 1, ctypes.byref(desc), None):
        return f", own process not relabelled: Convert error {ctypes.get_last_error()}"
    try:
        present, defaulted, sacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        if not adv.GetSecurityDescriptorSacl(desc, ctypes.byref(present), ctypes.byref(sacl),
                                             ctypes.byref(defaulted)) or not present.value:
            return ", own process not relabelled: no SACL"
        err = adv.SetSecurityInfo(k32.GetCurrentProcess(), 6, 0x10, None, None, None, sacl)  # SE_KERNEL_OBJECT, LABEL
        return "" if err == 0 else f", own process not relabelled: SetSecurityInfo error {err}"
    finally:
        k32.LocalFree(desc)


def _add_policy_path() -> None:
    """Windows host: the policy directory arrives in POLICY_PATH_ENV, not on PYTHONPATH, so that nothing in it
    (sitecustomize.py, a module shadowing a stdlib name) runs while the child is still at the host's level. It goes
    on sys.path right after the staged code and, for grandchildren (multiprocessing workers), on PYTHONPATH."""
    path = os.environ.get(POLICY_PATH_ENV)
    if not path:
        return
    first = os.environ.get("PYTHONPATH", "")
    staged = first.split(os.pathsep)[0]
    at = sys.path.index(staged) + 1 if staged in sys.path else len(sys.path)
    sys.path.insert(at, path)
    os.environ["PYTHONPATH"] = first + os.pathsep + path if first else path


def _claim_protocol_channel():
    try:
        sys.stdout.flush()
    except Exception:
        pass
    fd = os.dup(1)  # non-inheritable duplicate of the pipe to the host
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    if os.name == "nt":  # processes started with default handles must not inherit the protocol pipe either
        try:
            import ctypes
            import msvcrt

            ctypes.windll.kernel32.SetStdHandle(-11, msvcrt.get_osfhandle(2))
        except Exception:
            pass
    return os.fdopen(fd, "wb")


def main(argv=None) -> int:
    global PROTOCOL_OUT, INTEGRITY_STATUS
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--policy-seed", type=int, default=0)
    args = parser.parse_args(argv)
    if args.policy in GRADER_POLICIES:
        print("the oracle runs grader-side only", file=sys.stderr)
        return 2
    if __name__ == "__main__":  # only the real child: a test calling main() in-process must not lower itself
        INTEGRITY_STATUS = _lower_integrity()
        if INTEGRITY_STATUS.startswith("failed"):
            print(f"auditgym: integrity level not lowered: {INTEGRITY_STATUS}", file=sys.stderr)
        elif INTEGRITY_STATUS.startswith("off: ") and INTEGRITY_STATUS != "off: control run":
            print(f"auditgym: integrity level not lowered ({INTEGRITY_STATUS[5:]}): the policy can read the host's memory",
                  file=sys.stderr)
        _add_policy_path()
    out = PROTOCOL_OUT = _claim_protocol_channel()
    if __name__ == "__main__":
        sys.modules.setdefault("auditgym.agent", sys.modules[__name__])  # `import auditgym.agent` sees PROTOCOL_OUT
    try:
        policy = make_policy(args.policy, seed=args.policy_seed)
    except (PolicyError, ImportError, AttributeError) as exc:
        print(f"cannot load policy: {exc}", file=sys.stderr)
        return 2
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        if msg.get("type") == "end":
            break
        if msg.get("type") != "observation":
            continue
        if msg.get("terminated") or msg.get("truncated"):
            continue
        action = policy.act(msg["observation"], msg.get("reward", 0.0), msg.get("info", {}))
        out.write((json.dumps({"type": "action", "action": action}, ensure_ascii=True) + "\n").encode("ascii"))
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
