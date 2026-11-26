"""Check the SNMP values the site fault scenarios expose to pollers."""

import unittest

from start import build_record, devices_for_site


def record(site: str, suffix: str, faults_enabled: bool = True) -> dict[str, tuple[str, str]]:
    device = next(device for device in devices_for_site(site) if device[0].endswith(suffix))
    return {
        oid: (tag, value)
        for oid, tag, value in (line.split("|", 2) for line in build_record(*device, faults_enabled).splitlines())
    }


class NetworkScenariosTest(unittest.TestCase):
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
