import unittest

from poller import COUNTERS, Target, calculate_rates, oid_list, parse_values
from topology import topology_events


class PollerTest(unittest.TestCase):
    def test_identity_and_interface_fields(self):
        target = Target("boston", "pos-02", "pos", 1)
        values = ["boston-pos-02", "TinyCars TinyPOS Register-1", "Boston TinyCars showroom", "TinyCars Network Operations", "30", "02 54 43 07 00 01 "]
        values += ["eth0", "1", "2", "4", "3", "6", "5", "1000", "2000"]
        device, interfaces = parse_values(target, values, "10.0.0.1")
        self.assertEqual(device["attrs"]["tinycars.app"], "tinycars")
        self.assertEqual(device["attrs"]["device.site"], "boston")
        self.assertEqual(device["attrs"]["device.chassis_mac"], "02:54:43:07:00:01")
        self.assertEqual(interfaces[0]["up"], 0)
        self.assertEqual(interfaces[0]["admin_up"], 1)
        self.assertEqual(len(oid_list(1)), len(values))
        self.assertIn("1.3.6.1.2.1.31.1.1.1.6.1", oid_list(1))
        self.assertIn("1.3.6.1.2.1.31.1.1.1.10.1", oid_list(1))

    def test_counter_reset_is_not_a_negative_rate(self):
        self.assertEqual(calculate_rates({field: 20 for field in COUNTERS}, {field: 10 for field in COUNTERS}, 10),
                         {field: 0 for field in COUNTERS})

    def test_native_network_topology_identity_and_edge(self):
        events = topology_events([{"name": "boston-router-01", "site": "boston", "type": "router",
                                  "up": True, "chassis_mac": "02:54:43:01:00:01",
                                  "interfaces": [{"name": "wan0", "up": False, "admin_up": True}]}])
        self.assertEqual([event["type"] for event in events], ["EXT_NETWORK_DEVICE", "EXT_NETWORK_INTERFACE"])
        self.assertEqual(events[0]["id_components"], [{"identifier": "02:54:43:01:00:01"}])
        self.assertEqual(events[0]["chassis_mac"], "02:54:43:01:00:01")
        self.assertEqual(events[1]["id_components"], [{"name": "wan0"}, {"device.identifier": "02:54:43:01:00:01"}])
        self.assertEqual(events[1]["static_edges"]["belongs_to"][0],
                         {"type": "EXT_NETWORK_DEVICE", "id_components": [{"identifier": "02:54:43:01:00:01"}]})


if __name__ == "__main__":
    unittest.main()
