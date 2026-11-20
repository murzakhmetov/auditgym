"""Repository hygiene: source, tests, docs and configuration hold no control characters.

A stray backspace byte once replaced a regex word boundary in a test that only runs inside the image, so the
failure showed up in CI alone. Tab, newline and carriage return are allowed; every other byte below 0x20, and DEL,
is not.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNED_DIRS = ("auditgym", "tests", "docs", "examples", "tools", "configs", "schemas", ".github")
SCANNED_FILES = ("README.md", "README.ru.md", "Dockerfile", "Makefile", "pyproject.toml", ".gitattributes",
                 ".gitignore", ".dockerignore")
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".csv", ".yml", ".yaml", ".txt", ".html", ".js", ".toml", ".cfg"}
BAD = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text_files():
    for name in SCANNED_FILES:
        p = ROOT / name
        if p.is_file():
            yield p
    for d in SCANNED_DIRS:
        for p in sorted((ROOT / d).rglob("*")):
            if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and "__pycache__" not in p.parts:
                yield p


def _stamp_inputs():
    """The files the report's code stamp hashes byte for byte (auditgym.check.code_stamp): the package without the
    viewer and bytecode, configs/*.json and schemas/*.json."""
    pkg = ROOT / "auditgym"
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and p.relative_to(pkg).parts[0] != "viewer" and "__pycache__" not in p.parts \
                and p.suffix not in (".pyc", ".pyo"):
            yield p
    yield from sorted((ROOT / "configs").glob("*.json"))
    yield from sorted((ROOT / "schemas").glob("*.json"))


class Hygiene(unittest.TestCase):
    def test_no_control_characters_in_text_files(self):
        """No control bytes anywhere, and LF only in the code-stamp inputs: .gitattributes checks them out with LF,
        so a CR there means a local tool rewrote the file and the stamp would no longer match the committed one."""
        found = []
        n = 0
        for p in _text_files():
            n += 1
            m = BAD.search(p.read_bytes())
            if m:
                found.append(f"{p.relative_to(ROOT).as_posix()}: byte {m.start()} is {m.group()!r}")
        crlf = [p.relative_to(ROOT).as_posix() for p in _stamp_inputs() if b"\r" in p.read_bytes()]
        self.assertGreater(n, 50)
        self.assertEqual(found, [])
        self.assertEqual(crlf, [])

    def test_the_scan_catches_a_backspace(self):
        self.assertIsNotNone(BAD.search(b"r'%d" + bytes([8]) + b"'"))
        self.assertIsNone(BAD.search(b"tab\tnewline\ncarriage\r"))


if __name__ == "__main__":
    unittest.main()
