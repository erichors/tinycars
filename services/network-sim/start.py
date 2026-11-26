"""TinyCars SNMP lab: one site per container, nine devices per site."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


COMMUNITY = os.getenv("SNMP_COMMUNITY", "tinycars")
BASE_PORT = int(os.getenv("SNMP_BASE_PORT", "1161"))
SITE = os.getenv("SNMP_SITE", "boston").lower()
FAULTS_ENABLED = os.getenv("SNMP_FAULTS_ENABLED", "true").lower() in ("1", "true", "yes")

SITES = ("boston", "chicago", "london")
SITE_PROFILES = {
    "Boston": ("downtown sales", 2, 12, 32),
    "Chicago": ("regional hub", 3, 20, 42),
    "London": ("flagship store", 1, 10, 28),
}
# Each issue changes standard IF-MIB or Host Resources MIB values that an SNMP
# poller can observe. Counter rates are per second; a down link stops traffic.
ISSUES = {
    ("boston", "pos-02", "eth0"): {"oper_status": 2, "alias": "POS wired link - down; Wi-Fi backup available"},
    ("chicago", "firewall-01", "wan0"): {
        "rate": 50_000_000,
        "in_discards": 30,
        "in_errors": 12,
        "out_discards": 20,
        "out_errors": 8,
        "alias": "WAN uplink - congestion and packet loss",
    },
    ("london", "ap-01", "wlan1"): {
        "in_discards": 25,
        "in_errors": 16,
        "out_discards": 18,
        "out_errors": 10,
        "alias": "Operations Wi-Fi - interference",
    },
    ("london", "handheld-02", "wlan0"): {
        "in_discards": 8,
        "in_errors": 6,
        "alias": "Operations Wi-Fi - retries and loss",
    },
}
DEVICE_TYPES = (
    ("router-01", "Edge Router", "router"),
    ("switch-01", "Access Switch", "switch"),
    ("ap-01", "Wireless AP", "wireless"),
    ("firewall-01", "Site Firewall", "firewall"),
    ("server-01", "Store Server", "server"),
    ("pos-01", "POS Terminal", "pos"),
    ("pos-02", "POS Terminal", "pos"),
    ("handheld-01", "Handheld Scanner", "handheld"),
    ("handheld-02", "Handheld Scanner", "handheld"),
)


def devices_for_site(site: str) -> tuple[tuple[str, str, str, str, int], ...]:
    if site not in SITES:
        raise ValueError(f"Unknown SNMP_SITE: {site}")
    site_index = SITES.index(site)
    devices = []
    for index, (suffix, role, kind) in enumerate(DEVICE_TYPES):
        # Preserve the original nine device IDs and MACs across the upgrade.
        device_id = site_index * 3 + index + 1 if index < 3 else 10 + site_index * 6 + index - 3
        devices.append((f"{site}-{suffix}", site.title(), role, kind, device_id))
    return tuple(devices)


def mac(device_id: int, interface_id: int) -> str:
    """Locally administered, stable MAC encoded as hexadecimal SNMP octets."""
    return f"02:54:43:{device_id:02x}:00:{interface_id:02x}".replace(":", "")


def build_record(name: str, site: str, role: str, kind: str, device_id: int, faults_enabled: bool = True) -> str:
    rows: list[tuple[str, str, str]] = []

    def add(oid: str, tag: str, value: object) -> None:
        rows.append((oid, tag, str(value)))

    def add_counter(oid: str, tag: str, rate: int, initial: int = 0) -> None:
        if rate:
            add(oid, f"{tag}:numeric", f"rate={rate},initial={initial},increasing=1")
        else:
            add(oid, tag, initial)

    object_type = {"router": 1, "switch": 2, "wireless": 3, "firewall": 4, "server": 5, "pos": 6, "handheld": 7}[kind]
    model = {
        "router": "TinyRouter XR-1000",
        "switch": "TinySwitch XS-48",
        "wireless": "TinyAP AX-6",
        "firewall": "TinyFirewall FW-100",
        "server": "TinyServer Store-1",
        "pos": "TinyPOS Register-1",
        "handheld": "TinyScanner HH-1",
    }[kind]
    interfaces = {
        "router": (("wan0", "TinyCars WAN uplink", 1000), ("lan0", "TinyCars site LAN", 1000), ("mgmt0", "Management", 100)),
        "switch": (("uplink0", "Router uplink", 10000), ("storefront0", "Storefront segment", 1000), ("inventory0", "Inventory segment", 1000)),
        "wireless": (("eth0", "Switch uplink", 1000), ("wlan0", "TinyCars guest Wi-Fi", 1200), ("wlan1", "TinyCars operations Wi-Fi", 1200)),
        "firewall": (("wan0", "Router uplink", 1000), ("lan0", "Protected store LAN", 1000), ("dmz0", "Store server DMZ", 1000)),
        "server": (("eth0", "Store LAN", 1000), ("mgmt0", "Management", 1000)),
        "pos": (("eth0", "POS payment network", 1000), ("wlan0", "Store Wi-Fi backup", 300)),
        "handheld": (("wlan0", "Operations Wi-Fi", 300),),
    }[kind]

    site_purpose, traffic_scale, cpu_min, cpu_max = SITE_PROFILES[site]
    suffix = name.removeprefix(f"{site.lower()}-")

    # SNMPv2-MIB system group.
    add("1.3.6.1.2.1.1.1.0", "4", f"TinyCars {model} ({role})")
    add("1.3.6.1.2.1.1.2.0", "6", f"1.3.6.1.4.1.8072.9999.{object_type}")
    add("1.3.6.1.2.1.1.3.0", "67:numeric", f"rate=100,initial={device_id * 100000},increasing=1")
    add("1.3.6.1.2.1.1.4.0", "4", "TinyCars Network Operations")
    add("1.3.6.1.2.1.1.5.0", "4", name)
    add("1.3.6.1.2.1.1.6.0", "4", f"{site} TinyCars showroom ({site_purpose})")
    add("1.3.6.1.2.1.1.7.0", "2", 6 if kind in ("router", "firewall") else 72 if kind in ("server", "pos", "handheld") else 2)

    # IF-MIB interface table and 64-bit counters. The first MAC acts as a stable chassis identity.
    add("1.3.6.1.2.1.2.1.0", "2", len(interfaces))
    for index, (if_name, alias, speed_mbps) in enumerate(interfaces, start=1):
        issue = ISSUES.get((site.lower(), suffix, if_name), {}) if faults_enabled else {}
        oper_status = issue.get("oper_status", 1)
        seed = device_id * 10_000_000 + index * 1_000_000
        rate = issue.get("rate", (device_id + index) * 4096 * traffic_scale) if oper_status == 1 else 0
        prefix = "1.3.6.1.2.1.2.2.1"
        add(f"{prefix}.1.{index}", "2", index)
        add(f"{prefix}.2.{index}", "4", if_name)
        add(f"{prefix}.3.{index}", "2", 6)
        add(f"{prefix}.4.{index}", "2", 1500)
        add(f"{prefix}.5.{index}", "66", min(speed_mbps * 1_000_000, 4_294_967_295))
        add(f"{prefix}.6.{index}", "4x", mac(device_id, index))
        add(f"{prefix}.7.{index}", "2", 1)
        add(f"{prefix}.8.{index}", "2", oper_status)
        add(f"{prefix}.9.{index}", "67", 0)
        add_counter(f"{prefix}.10.{index}", "65", rate, seed)
        add_counter(f"{prefix}.11.{index}", "65", max(rate // 800, 1) if rate else 0, seed // 800)
        add_counter(f"{prefix}.13.{index}", "65", issue.get("in_discards", 0))
        add_counter(f"{prefix}.14.{index}", "65", issue.get("in_errors", 0))
        add_counter(f"{prefix}.16.{index}", "65", rate * 2, seed * 2)
        add_counter(f"{prefix}.17.{index}", "65", max(rate // 400, 1) if rate else 0, seed // 400)
        add_counter(f"{prefix}.19.{index}", "65", issue.get("out_discards", 0))
        add_counter(f"{prefix}.20.{index}", "65", issue.get("out_errors", 0))
        add(f"{prefix}.21.{index}", "66", 0)
        add(f"{prefix}.22.{index}", "6", "0.0")

        xprefix = "1.3.6.1.2.1.31.1.1.1"
        add(f"{xprefix}.1.{index}", "4", if_name)
        add_counter(f"{xprefix}.6.{index}", "70", rate, seed)
        add_counter(f"{xprefix}.10.{index}", "70", rate * 2, seed * 2)
        add(f"{xprefix}.15.{index}", "66", speed_mbps)
        add(f"{xprefix}.16.{index}", "2", 2)
        add(f"{xprefix}.17.{index}", "2", 1)
        add(f"{xprefix}.18.{index}", "4", issue.get("alias", alias))

    # Host Resources CPU/memory values used by many generic SNMP profiles.
    add("1.3.6.1.2.1.25.3.3.1.1.1", "2", 1)
    if faults_enabled and site == "Chicago" and suffix == "firewall-01":
        cpu_min, cpu_max = 86, 96
    cpu_mid = (cpu_min + cpu_max) // 2
    cpu_radius = (cpu_max - cpu_min) // 2
    add("1.3.6.1.2.1.25.3.3.1.2.1", "2:numeric", f"function=sin,rate=0.05,scale={cpu_radius},offset={cpu_mid},min={cpu_min},max={cpu_max}")
    add("1.3.6.1.4.1.2021.4.5.0", "2", 524288)
    add("1.3.6.1.4.1.2021.4.6.0", "2:numeric", "function=variation,minimum=262144,maximum=458752")

    def oid_key(row: tuple[str, str, str]) -> tuple[int, ...]:
        return tuple(int(part) for part in row[0].split("."))

    return "\n".join("|".join(row) for row in sorted(rows, key=oid_key)) + "\n"


class HealthHandler(BaseHTTPRequestHandler):
    processes: list[subprocess.Popen[str]] = []

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        healthy = len(self.processes) == 1 and self.processes[0].poll() is None
        self.send_response(200 if healthy else 503)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok\n" if healthy else b"unhealthy\n")

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    devices = devices_for_site(SITE)
    root = Path(tempfile.mkdtemp(prefix="tinycars-snmp-"))
    stopping = False
    command = [
        "snmpsim-command-responder",
        "--quiet",
        "--logging-method=stderr",
    ]

    for offset, device in enumerate(devices):
        data_dir = root / device[0]
        data_dir.mkdir()
        (data_dir / f"{COMMUNITY}.snmprec").write_text(build_record(*device, faults_enabled=FAULTS_ENABLED), encoding="utf-8")
        port = BASE_PORT + offset
        command.extend(
            (
                "--v3-engine-id=auto",
                f"--data-dir={data_dir}",
                f"--agent-udpv4-endpoint=0.0.0.0:{port}",
            )
        )
        print(f"started {device[0]} ({device[1]} {device[3]}) on udp/{port}", flush=True)

    processes = [subprocess.Popen(command, text=True)]
    HealthHandler.processes = processes
    server = ThreadingHTTPServer(("0.0.0.0", 8080), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        failed = [process for process in processes if process.poll() is not None]
        if failed:
            print("an SNMP responder stopped unexpectedly", file=sys.stderr, flush=True)
            stopping = True
            break
        time.sleep(1)

    server.shutdown()
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    return 1 if any(process.returncode not in (0, -signal.SIGTERM) for process in processes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
