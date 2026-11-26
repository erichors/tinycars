import unittest

from poller import COUNTERS, Target, calculate_rates, oid_list, parse_values


class PollerTest(unittest.TestCase):
    def test_identity_and_interface_fields(self):
        target = Target("boston", "pos-02", "pos", 1)
        values = ["boston-pos-02", "TinyCars TinyPOS Register-1", "Boston TinyCars showroom", "TinyCars Network Operations", "30"]
        values += ["eth0", "1", "2", "4", "3", "6", "5", "1000", "2000"]
        device, interfaces = parse_values(target, values, "10.0.0.1")
        self.assertEqual(device["attrs"]["tinycars.app"], "tinycars")
        self.assertEqual(device["attrs"]["device.site"], "boston")
        self.assertEqual(interfaces[0]["up"], 0)
        self.assertEqual(interfaces[0]["admin_up"], 1)
        self.assertEqual(len(oid_list(1)), len(values))

    def test_counter_reset_is_not_a_negative_rate(self):
        self.assertEqual(calculate_rates({field: 20 for field in COUNTERS}, {field: 10 for field in COUNTERS}, 10),
                         {field: 0 for field in COUNTERS})


if __name__ == "__main__":
    unittest.main()
