import unittest

from auditgym.calculator import CalcError, evaluate


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        cases = {
            "1+2*3": "7",
            "(1+2)*3": "9",
            "-3 + +5": "2",
            "--4": "4",
            "10/4": "2.5",
            ".5 * 4": "2",
            "125000 - 92234": "32766",
            "1/3": "0.333333333333",
            "0.1 + 0.2": "0.3",
            "2 - 2": "0",
            "-0.0": "0",
        }
        for expr, expected in cases.items():
            with self.subTest(expr=expr):
                self.assertEqual(evaluate(expr), expected)

    def test_large_results_inside_the_range(self):
        self.assertEqual(evaluate("99999999999*99999999999*1000"), "9999999999800000000001000")
        self.assertEqual(evaluate("123456789012*1000000000"), "123456789012000000000")
        self.assertEqual(evaluate("99999999999999999999999999999 + 0.5"), "99999999999999999999999999999.5")

    def test_fx_style_division(self):
        self.assertTrue(evaluate("100000 / 1.0842").startswith("92233.9051835"))

    def test_rejects_non_arithmetic(self):
        bad = [
            "", "   ", "2**3", "2^3", "1e5", "abs(-1)", "__import__('os')", "a+1", "1/0", "(1+2",
            "1+2)", "1..2", "3.", "1 2", "open('x')", "1;2", "٣+1", "x" * 300, "(" * 40 + "1" + ")" * 40,
            "9" * 31 + "*10",
        ]
        for expr in bad:
            with self.subTest(expr=expr[:30]):
                with self.assertRaises(CalcError):
                    evaluate(expr)

    def test_rejects_non_string(self):
        with self.assertRaises(CalcError):
            evaluate(42)


if __name__ == "__main__":
    unittest.main()
