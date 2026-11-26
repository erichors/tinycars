"""Poll TinyCars SNMP devices and export per-device/per-interface OTLP metrics."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


SITES = ("boston", "chicago", "london")
DEVICES = (
    ("router-01", "router", 3),
    ("switch-01", "switch", 3),
    ("ap-01", "wireless-ap", 3),
    ("firewall-01", "firewall", 3),
    ("server-01", "server", 2),
    ("pos-01", "pos", 2),
    ("pos-02", "pos", 2),
    ("handheld-01", "handheld", 1),
    ("handheld-02", "handheld", 1),
)
SYS_NAME = "1.3.6.1.2.1.1.5.0"
SYS_DESCRIPTION = "1.3.6.1.2.1.1.1.0"
SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
CPU = "1.3.6.1.2.1.25.3.3.1.2.1"
IF_BASE = "1.3.6.1.2.1.2.2.1"
IF_X_BASE = "1.3.6.1.2.1.31.1.1.1"
FIELDS = {"name": 2, "admin": 7, "oper": 8, "in_errors": 14, "out_errors": 20,
          "in_discards": 13, "out_discards": 19, "in_octets": 10, "out_octets": 16}
COUNTERS = ("in_errors", "out_errors", "in_discards", "out_discards", "in_octets", "out_octets")
METRIC_NAMES = {
    "device_up": "tinycars.network.device.up",
    "cpu": "tinycars.network.device.cpu.percent",
    "interface_up": "tinycars.network.interface.up",
    "in_errors": "tinycars.network.interface.in_errors_per_second",
    "out_errors": "tinycars.network.interface.out_errors_per_second",
    "in_discards": "tinycars.network.interface.in_discards_per_second",
    "out_discards": "tinycars.network.interface.out_discards_per_second",
    "in_octets": "tinycars.network.interface.in_bytes_per_second",
    "out_octets": "tinycars.network.interface.out_bytes_per_second",
}


@dataclass(frozen=True)
class Target:
    site: str
    suffix: str
    kind: str
    interfaces: int

    @property
    def name(self) -> str:
        return f"{self.site}-{self.suffix}"

    @property
    def address(self) -> str:
        namespace = os.getenv("SNMP_NAMESPACE", "tinycars")
        return f"{self.name}.{namespace}.svc.cluster.local"


TARGETS = tuple(Target(site, *device) for site in SITES for device in DEVICES)


def oid_list(count: int) -> list[str]:
    result = [SYS_NAME, SYS_DESCRIPTION, SYS_LOCATION, SYS_CONTACT, CPU]
    for index in range(1, count + 1):
        for key, field in FIELDS.items():
            if key in ("in_octets", "out_octets"):
                result.append(f"{IF_X_BASE}.{6 if key == 'in_octets' else 10}.{index}")
            else:
                result.append(f"{IF_BASE}.{field}.{index}")
    return result


def to_number(value: str) -> float:
    return float(value.strip().split(": ")[-1].replace(",", ""))


def parse_values(target: Target, values: list[str], address: str) -> tuple[dict, list[dict]]:
    expected = 5 + target.interfaces * len(FIELDS)
    if len(values) != expected:
        raise ValueError(f"expected {expected} OIDs, received {len(values)}")
    sys_name, description, location, contact = (value.strip().strip('"') for value in values[:4])
    if sys_name != target.name or "TinyCars" not in description:
        raise ValueError(f"unexpected SNMP identity: {sys_name}")
    common = {"tinycars.app": "tinycars", "device.name": sys_name, "device.site": target.site,
              "device.type": target.kind, "device.address": address, "device.description": description,
              "device.location": location, "device.contact": contact}
    device = {"attrs": common, "cpu": to_number(values[4])}
    interfaces = []
    for index in range(target.interfaces):
        row = dict(zip(FIELDS, values[5 + index * len(FIELDS):5 + (index + 1) * len(FIELDS)]))
        attrs = {**common, "if.name": row["name"].strip().strip('"')}
        interfaces.append({"attrs": attrs, "up": int(to_number(row["oper"]) == 1),
                           "admin_up": int(to_number(row["admin"]) == 1),
                           "counters": {field: to_number(row[field]) for field in COUNTERS}})
    return device, interfaces


def poll(target: Target, community: str) -> tuple[dict, list[dict]]:
    address = socket.gethostbyname(target.address)
    command = ["snmpget", "-v2c", "-c", community, "-Oqv", "-t", "1", "-r", "1",
               target.address, *oid_list(target.interfaces)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=True)
    return parse_values(target, result.stdout.splitlines(), address)


def calculate_rates(previous: dict, current: dict, seconds: float) -> dict:
    if not previous or seconds <= 0:
        return {field: 0.0 for field in COUNTERS}
    return {field: max(0.0, (current[field] - previous[field]) / seconds) for field in COUNTERS}


def main() -> None:
    from opentelemetry import metrics
    from opentelemetry.metrics import Observation
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    community = os.environ["SNMP_COMMUNITY"]
    endpoint = os.getenv("OTLP_METRICS_ENDPOINT", "http://telemetry-ingest.dynatrace.svc.cluster.local:4318/v1/metrics")
    interval = max(15, int(os.getenv("SNMP_POLL_INTERVAL_SECONDS", "30")))
    latest: dict[str, list[tuple[float, dict]]] = {key: [] for key in METRIC_NAMES}
    previous: dict[tuple[str, str], tuple[dict, float]] = {}
    lock = threading.Lock()

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint), export_interval_millis=interval * 1000)
    provider = MeterProvider(resource=Resource.create({"service.name": "tinycars-network-poller", "service.namespace": "tinycars",
                                                     "deployment.environment": "tinycars", "tinycars.app": "tinycars"}),
                             metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter("tinycars.network.snmp")

    def observe(key: str):
        def callback(_options):
            with lock:
                return [Observation(value, attrs) for value, attrs in latest[key]]
        return callback

    for key, name in METRIC_NAMES.items():
        unit = "1" if key.endswith("up") else "%" if key == "cpu" else "{event}/s" if "errors" in key or "discards" in key else "By/s"
        meter.create_observable_gauge(name, callbacks=[observe(key)], unit=unit)

    print(json.dumps({"event": "SNMP_POLLER_STARTED", "targets": len(TARGETS), "interval_seconds": interval}), flush=True)
    while True:
        started = time.monotonic()
        snapshots: dict[str, list[tuple[float, dict]]] = {key: [] for key in METRIC_NAMES}
        healthy = 0
        for target in TARGETS:
            try:
                device, interfaces = poll(target, community)
                healthy += 1
                snapshots["device_up"].append((1, device["attrs"]))
                snapshots["cpu"].append((device["cpu"], device["attrs"]))
                now = time.monotonic()
                for interface in interfaces:
                    attrs = interface["attrs"]
                    snapshots["interface_up"].append((interface["up"], {**attrs, "if.admin_up": interface["admin_up"]}))
                    key = (target.name, attrs["if.name"])
                    old, old_time = previous.get(key, (None, now))
                    rates = calculate_rates(old, interface["counters"], now - old_time)
                    previous[key] = (interface["counters"], now)
                    for field, value in rates.items():
                        snapshots[field].append((value, attrs))
            except (OSError, subprocess.SubprocessError, ValueError) as error:
                snapshots["device_up"].append((0, {"tinycars.app": "tinycars", "device.name": target.name,
                                                    "device.site": target.site, "device.type": target.kind}))
                print(json.dumps({"event": "SNMP_POLL_FAILED", "device": target.name, "error": str(error)[:200]}), flush=True)
        with lock:
            latest = snapshots
        Path("/tmp/tinycars-network-poller-ready").touch()
        print(json.dumps({"event": "SNMP_POLL_COMPLETED", "devices_up": healthy, "targets": len(TARGETS)}), flush=True)
        time.sleep(max(0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
