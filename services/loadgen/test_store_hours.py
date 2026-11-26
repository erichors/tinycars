import unittest
from datetime import datetime, timezone

from store_hours import is_open, open_stores


class StoreHoursTest(unittest.TestCase):
    def test_winter_store_hours(self):
        at_15_utc = datetime(2026, 1, 15, 15, tzinfo=timezone.utc)
        self.assertEqual(open_stores(at_15_utc), ["boston", "london"])
        self.assertTrue(is_open("chicago", datetime(2026, 1, 15, 16, tzinfo=timezone.utc)))

    def test_summer_store_hours_follow_dst(self):
        at_14_utc = datetime(2026, 7, 15, 14, tzinfo=timezone.utc)
        self.assertEqual(open_stores(at_14_utc), ["boston", "london"])
        self.assertFalse(is_open("chicago", at_14_utc))

    def test_london_dst_transition(self):
        self.assertFalse(is_open("london", datetime(2026, 3, 28, 9, tzinfo=timezone.utc)))
        self.assertTrue(is_open("london", datetime(2026, 3, 29, 9, tzinfo=timezone.utc)))

    def test_overnight_and_naive_time(self):
        self.assertEqual(open_stores(datetime(2026, 1, 15, 6, tzinfo=timezone.utc)), [])
        with self.assertRaises(ValueError):
            is_open("boston", datetime(2026, 1, 15, 15))


if __name__ == "__main__":
    unittest.main()
