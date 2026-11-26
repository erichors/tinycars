"""Check the SNMP values the site fault scenarios expose to pollers."""

import unittest

from start import build_record, devices_for_site, fault_level_from_flags


def record(site: str, suffix: str, faults_enabled: bool = True) -> dict[str, tuple[str, str]]:
    device = next(device for device in devices_for_site(site) if device[0].endswith(suffix))
    return {
        oid: (tag, value)
        for oid, tag, value in (line.split("|", 2) for line in build_record(*device, faults_enabled).splitlines())
    }


class NetworkScenariosTest(unittest.TestCase):
    def test_admin_flags_control_each_site(self) -> None:
        flags = {"network_wan_congestion": '{"on":true,"level":4}'}
        self.assertEqual(fault_level_from_flags(flags, "chicago"), 4)
        self.assertEqual(fault_level_from_flags(flags, "boston"), 0)
        self.assertEqual(fault_level_from_flags({"network_wan_congestion": '{"on":false,"level":4}'}, "chicago"), 0)

    def test_level_scales_wan_errors_and_off_restores_baseline(self) -> None:
        device = next(d for d in devices_for_site("chicago") if d[0].endswith("firewall-01"))
        level_4 = dict((oid, value) for oid, _, value in (line.split("|", 2) for line in build_record(*device, fault_level=4).splitlines()))
        healthy = dict((oid, value) for oid, _, value in (line.split("|", 2) for line in build_record(*device, fault_level=0).splitlines()))
        self.assertIn("rate=120", level_4["1.3.6.1.2.1.2.2.1.13.1"])
        self.assertEqual(healthy["1.3.6.1.2.1.2.2.1.13.1"], "0")

    def test_boston_pos_link_is_down_but_backup_remains_up(self) -> None:
        values = record("boston", "pos-02")
        self.assertEqual(values["1.3.6.1.2.1.2.2.1.7.1"], ("2", "1"))
        self.assertEqual(values["1.3.6.1.2.1.2.2.1.8.1"], ("2", "2"))
        self.assertEqual(values["1.3.6.1.2.1.2.2.1.8.2"], ("2", "1"))
        self.assertEqual(values["1.3.6.1.2.1.31.1.1.1.6.1"][0], "70")

    def test_chicago_firewall_has_loss_and_high_cpu(self) -> None:
        values = record("chicago", "firewall-01")
        self.assertIn("rate=50000000", values["1.3.6.1.2.1.31.1.1.1.6.1"][1])
        self.assertIn("rate=30", values["1.3.6.1.2.1.2.2.1.13.1"][1])
        self.assertIn("rate=12", values["1.3.6.1.2.1.2.2.1.14.1"][1])
        self.assertIn("min=86,max=96", values["1.3.6.1.2.1.25.3.3.1.2.1"][1])

    def test_london_wireless_errors_and_healthy_baseline(self) -> None:
        affected = record("london", "ap-01")
        healthy = record("london", "ap-01", faults_enabled=False)
        self.assertIn("rate=16", affected["1.3.6.1.2.1.2.2.1.14.3"][1])
        self.assertEqual(healthy["1.3.6.1.2.1.2.2.1.14.3"], ("65", "0"))
        self.assertIn("interference", affected["1.3.6.1.2.1.31.1.1.1.18.3"][1])


if __name__ == "__main__":
    unittest.main()
