import unittest
from datetime import date, datetime, timezone

from auditgym import timeutil as tu
from auditgym.money import convert_minor, format_minor, proportional_minor

UTC = timezone.utc


class DstRuleTests(unittest.TestCase):
    def assert_change(self, tz, before, after, off_before, off_after):
        self.assertEqual(tu.offset_minutes(tz, tu.parse_ts(before)), off_before)
        self.assertEqual(tu.offset_minutes(tz, tu.parse_ts(after)), off_after)

    def test_eu_2026(self):
        self.assert_change("Europe/Berlin", "2026-03-29T00:59:59Z", "2026-03-29T01:00:00Z", 60, 120)
        self.assert_change("Europe/Berlin", "2026-10-25T00:59:59Z", "2026-10-25T01:00:00Z", 120, 60)

    def test_us_2026(self):
        self.assert_change("America/New_York", "2026-03-08T06:59:59Z", "2026-03-08T07:00:00Z", -300, -240)
        self.assert_change("America/New_York", "2026-11-01T05:59:59Z", "2026-11-01T06:00:00Z", -240, -300)

    def test_sydney_2026(self):
        self.assert_change("Australia/Sydney", "2026-04-04T15:59:59Z", "2026-04-04T16:00:00Z", 660, 600)
        self.assert_change("Australia/Sydney", "2026-10-03T15:59:59Z", "2026-10-03T16:00:00Z", 600, 660)

    def test_schedule_lists_change_inside_window(self):
        sched = tu.offset_schedule("Europe/Berlin", tu.parse_ts("2026-02-01T00:00:00Z"), tu.parse_ts("2026-04-10T00:00:00Z"))
        self.assertEqual(sched, [
            {"from_utc": "2026-02-01T00:00:00Z", "offset": "+01:00"},
            {"from_utc": "2026-03-29T01:00:00Z", "offset": "+02:00"},
        ])

    def test_month_bounds_and_local_dates(self):
        start, end = tu.month_bounds("Europe/Berlin", 2026, 3)
        self.assertEqual(tu.format_local(start, "Europe/Berlin"), "2026-03-01T00:00:00+01:00")
        self.assertEqual(tu.format_local(end, "Europe/Berlin"), "2026-04-01T00:00:00+02:00")
        inst = tu.parse_ts("2026-03-31T22:30:00Z")
        self.assertEqual(tu.local_date(inst, "Asia/Almaty"), date(2026, 4, 1))
        self.assertEqual(tu.local_date(inst, "America/Sao_Paulo"), date(2026, 3, 31))
        self.assertEqual(tu.format_local(inst, "Asia/Kathmandu"), "2026-04-01T04:15:00+05:45")

    def test_parse_equivalent_representations(self):
        a = tu.parse_ts("2026-03-31T23:40:00+02:00")
        b = tu.parse_ts("2026-03-31T21:40:00Z")
        c = tu.parse_ts("2026-04-01T03:10:00+05:30")
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        with self.assertRaises(ValueError):
            tu.parse_ts("2026-03-31T21:40:00")


class MoneyGoldenTests(unittest.TestCase):
    """Hand-computed conversions, independent of the generator."""

    def test_exponent_zero_and_three(self):
        # 1,000.00 USD at 150.123 JPY per USD = 150,123 JPY (exponent 0)
        self.assertEqual(convert_minor(100000, "150.123", 2, 0, "half_even"), 150123)
        # 1,000.00 USD at 0.30712 KWD per USD = 307.120 KWD (exponent 3)
        self.assertEqual(convert_minor(100000, "0.30712", 2, 3, "half_even"), 307120)
        # 12,345 JPY at 0.006134 EUR per JPY = 75.724... EUR -> 7572 cents
        self.assertEqual(convert_minor(12345, "0.006134", 0, 2, "half_even"), 7572)

    def test_half_even_vs_half_up_boundary(self):
        # 0.125 * 100 cents = 12.5 cents exactly
        self.assertEqual(convert_minor(125, "0.1", 2, 2, "half_even"), 12)
        self.assertEqual(convert_minor(125, "0.1", 2, 2, "half_up"), 13)
        self.assertEqual(convert_minor(135, "0.1", 2, 2, "half_even"), 14)
        self.assertEqual(proportional_minor(101, 1, 2, "half_even"), 50)
        self.assertEqual(proportional_minor(101, 1, 2, "half_up"), 51)

    def test_format_minor(self):
        self.assertEqual(format_minor(125000, 2), "1250.00")
        self.assertEqual(format_minor(5, 3), "0.005")
        self.assertEqual(format_minor(150123, 0), "150123")
        self.assertEqual(format_minor(-7, 2), "-0.07")


if __name__ == "__main__":
    unittest.main()
