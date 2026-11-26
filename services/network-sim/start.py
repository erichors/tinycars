"""TinyCars SNMP lab: nine deterministic network devices on nine UDP ports."""

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

DEVICES = (
    ("boston-router-01", "Boston", "Edge Router", "router", 1),
    ("boston-switch-01", "Boston", "Access Switch", "switch", 2),
    ("boston-ap-01", "Boston", "Wireless AP", "wireless", 3),
    ("chicago-router-01", "Chicago", "Edge Router", "router", 4),
    ("chicago-switch-01", "Chicago", "Access Switch", "switch", 5),
    ("chicago-ap-01", "Chicago", "Wireless AP", "wireless", 6),
    ("london-router-01", "London", "Edge Router", "router", 7),
    ("london-switch-01", "London", "Access Switch", "switch", 8),
    ("london-ap-01", "London", "Wireless AP", "wireless", 9),
)


def mac(device_id: int, interface_id: int) -> str:
    """Locally administered, stable MAC encoded as hexadecimal SNMP octets."""
    return f"02:54:43:{device_id:02x}:00:{interface_id:02x}".replace(":", "")


def build_record(name: str, site: str, role: str, kind: str, device_id: int) -> str:
    rows: list[tuple[str, str, str]] = []

    def add(oid: str, tag: str, value: object) -> None:
        rows.append((oid, tag, str(value)))

    object_type = {"router": 1, "switch": 2, "wireless": 3}[kind]
    model = {"router": "TinyRouter XR-1000", "switch": "TinySwitch XS-48", "wireless": "TinyAP AX-6"}[kind]
    interfaces = {
        "router": (("wan0", "TinyCars WAN uplink", 1000), ("lan0", "TinyCars site LAN", 1000), ("mgmt0", "Management", 100)),
        "switch": (("uplink0", "Router uplink", 10000), ("storefront0", "Storefront segment", 1000), ("inventory0", "Inventory segment", 1000)),
        "wireless": (("eth0", "Switch uplink", 1000), ("wlan0", "TinyCars guest Wi-Fi", 1200), ("wlan1", "TinyCars operations Wi-Fi", 1200)),
    }[kind]

    # SNMPv2-MIB system group.
    add("1.3.6.1.2.1.1.1.0", "4", f"TinyCars {model} ({role})")
    add("1.3.6.1.2.1.1.2.0", "6", f"1.3.6.1.4.1.8072.9999.{object_type}")
    add("1.3.6.1.2.1.1.3.0", "67:numeric", f"rate=100,initial={device_id * 100000},increasing=1")
    add("1.3.6.1.2.1.1.4.0", "4", "TinyCars Network Operations")
    add("1.3.6.1.2.1.1.5.0", "4", name)
    add("1.3.6.1.2.1.1.6.0", "4", f"{site} TinyCars showroom")
    add("1.3.6.1.2.1.1.7.0", "2", 6 if kind == "router" else 2)

    # IF-MIB interface table and 64-bit counters. The first MAC acts as a stable chassis identity.
    add("1.3.6.1.2.1.2.1.0", "2", len(interfaces))
    for index, (if_name, alias, speed_mbps) in enumerate(interfaces, start=1):
        seed = device_id * 10_000_000 + index * 1_000_000
        rate = (device_id + index) * 4096
        prefix = "1.3.6.1.2.1.2.2.1"
        add(f"{prefix}.1.{index}", "2", index)
        add(f"{prefix}.2.{index}", "4", if_name)
        add(f"{prefix}.3.{index}", "2", 6)
        add(f"{prefix}.4.{index}", "2", 1500)
        add(f"{prefix}.5.{index}", "66", min(speed_mbps * 1_000_000, 4_294_967_295))
        add(f"{prefix}.6.{index}", "4x", mac(device_id, index))
        add(f"{prefix}.7.{index}", "2", 1)
        add(f"{prefix}.8.{index}", "2", 1)
        add(f"{prefix}.9.{index}", "67", 0)
        add(f"{prefix}.10.{index}", "65:numeric", f"rate={rate},initial={seed},increasing=1")
        add(f"{prefix}.11.{index}", "65:numeric", f"rate={max(rate // 800, 1)},initial={seed // 800},increasing=1")
        add(f"{prefix}.13.{index}", "65", 0)
        add(f"{prefix}.14.{index}", "65", 0)
        add(f"{prefix}.16.{index}", "65:numeric", f"rate={rate * 2},initial={seed * 2},increasing=1")
        add(f"{prefix}.17.{index}", "65:numeric", f"rate={max(rate // 400, 1)},initial={seed // 400},increasing=1")
        add(f"{prefix}.19.{index}", "65", 0)
        add(f"{prefix}.20.{index}", "65", 0)
        add(f"{prefix}.21.{index}", "66", 0)
        add(f"{prefix}.22.{index}", "6", "0.0")

        xprefix = "1.3.6.1.2.1.31.1.1.1"
        add(f"{xprefix}.1.{index}", "4", if_name)
        add(f"{xprefix}.6.{index}", "70:numeric", f"rate={rate},initial={seed},increasing=1")
        add(f"{xprefix}.10.{index}", "70:numeric", f"rate={rate * 2},initial={seed * 2},increasing=1")
        add(f"{xprefix}.15.{index}", "66", speed_mbps)
        add(f"{xprefix}.16.{index}", "2", 2)
        add(f"{xprefix}.17.{index}", "2", 1)
        add(f"{xprefix}.18.{index}", "4", alias)

    # Host Resources CPU/memory values used by many generic SNMP profiles.
    add("1.3.6.1.2.1.25.3.3.1.1.1", "2", 1)
    add("1.3.6.1.2.1.25.3.3.1.2.1", "2:numeric", f"function=variation,minimum=8,maximum={20 + device_id}")
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
    root = Path(tempfile.mkdtemp(prefix="tinycars-snmp-"))
    stopping = False
    command = [
        "snmpsim-command-responder",
        "--quiet",
        "--logging-method=stderr",
    ]

    for offset, device in enumerate(DEVICES):
        data_dir = root / device[0]
        data_dir.mkdir()
        (data_dir / f"{COMMUNITY}.snmprec").write_text(build_record(*device), encoding="utf-8")
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
