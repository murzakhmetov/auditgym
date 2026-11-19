"""examples/findings_t03_correct.json (used by the README grade command) must follow the committed episodes."""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "regen_examples.py"


class RegenExamplesTest(unittest.TestCase):
    def test_example_answer_is_current(self):
        spec = importlib.util.spec_from_file_location("regen_examples", TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = module.main(["--check"])
        self.assertEqual(code, 0, out.getvalue() + " (run: python tools/regen_examples.py)")


if __name__ == "__main__":
    unittest.main()
