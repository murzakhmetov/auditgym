"""Every command that reads --secret-env makes the host non-dumpable first (protocol.harden_host).

The rule is documented in auditgym/__main__.py and protocol.harden_host. harden_host is patched, so these tests run
on every platform; the run is stopped right after the secret is read by a sentinel raised from generate_episode.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import auditgym.__main__ as entry
import auditgym.check as check_mod
from auditgym import generator, protocol

SEEDS = str(Path(__file__).resolve().parent.parent / "examples" / "closed_seeds_example.json")
VAR = "AUDITGYM_TEST_ENTRYPOINT_SECRET"


class Stop(Exception):
    """Raised instead of generating an episode: the secret has been read by then."""


class _Order:
    def __init__(self):
        self.calls = []
        self._pop = os.environ.pop

    def harden(self):
        self.calls.append("harden")
        return True

    def pop(self, key, *default):
        if key == VAR:
            self.calls.append("secret")
        return self._pop(key, *default)

    def generate(self, *args, **kwargs):
        self.calls.append("generate")
        raise Stop


class HardenBeforeSecret(unittest.TestCase):
    def run_entry(self, runner):
        order = _Order()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {VAR: "entrypoint-test-secret"}), \
                mock.patch.object(protocol, "harden_host", side_effect=order.harden), \
                mock.patch.object(os.environ, "pop", side_effect=order.pop), \
                mock.patch.object(generator, "generate_episode", side_effect=order.generate), \
                mock.patch.object(check_mod, "generate_episode", side_effect=order.generate):
            with self.assertRaises(Stop):
                runner(tmp)
        return order.calls

    def assert_order(self, calls):
        self.assertIn("harden", calls)
        self.assertIn("secret", calls)
        self.assertLess(calls.index("harden"), calls.index("secret"), calls)
        self.assertEqual(calls[-1], "generate", calls)

    def test_run_hardens_before_the_secret_is_read(self):
        calls = self.run_entry(lambda tmp: entry.main(
            ["run", "--seeds-file", SEEDS, "--secret-env", VAR, "--policies", "silent", "--in-process", "--out", tmp]))
        self.assert_order(calls)

    def test_check_hardens_before_the_secret_is_read(self):
        calls = self.run_entry(lambda tmp: check_mod.main(["--seeds-file", SEEDS, "--secret-env", VAR, "--out", tmp]))
        self.assert_order(calls)

    def test_check_through_the_main_entry_point_hardens_first_too(self):
        calls = self.run_entry(lambda tmp: entry.main(["check", "--seeds-file", SEEDS, "--secret-env", VAR, "--out", tmp]))
        self.assert_order(calls)


if __name__ == "__main__":
    unittest.main()
