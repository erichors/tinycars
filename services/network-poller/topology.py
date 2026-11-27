"""Optional direct Smartscape event ingestion for TinyCars network topology."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def topology_events(devices: list[dict]) -> list[dict]:
    events = []
    for device in devices:
        if not device.get("up") or not device.get("chassis_mac"):
            continue
        identity = {"type": "EXT_NETWORK_DEVICE", "id_components": [{"identifier": device["chassis_mac"]}]}
        events.append({
            **identity,
            "name": device["name"],
            "monitoring_mode": "Extension",
            "device_type": device["type"],
            "description": device.get("description", ""),
            "location": device.get("location", ""),
            "ext.tinycars.address": device.get("address", ""),
            "ext.tinycars.cpu_percent": device.get("cpu_percent", 0),
            "tags:custom.tinycars": {"app": "tinycars", "site": device["site"]},
        })
        for interface in device.get("interfaces", []):
            events.append({
                "type": "EXT_NETWORK_INTERFACE",
                "id_components": [{"name": interface["name"]}, {"device.identifier": device["chassis_mac"]}],
                "name": interface["name"],
                "device.chassis_mac": device["chassis_mac"],
                "operational_status": "up" if interface["up"] else "down",
                "admin_status": "up" if interface["admin_up"] else "down",
                "ext.tinycars.device_name": device["name"],
                "static_edges": {"belongs_to": [identity]},
            })
    return events


def publish_topology(devices: list[dict]) -> None:
    token = os.getenv("SMARTSCAPE_INGEST_TOKEN")
    endpoint = os.getenv("SMARTSCAPE_INGEST_ENDPOINT")
    if not token or not endpoint:
        return
    events = topology_events(devices)
    if not events:
        return
    request = urllib.request.Request(
        endpoint, data=json.dumps(events).encode(), method="POST",
        headers={"Authorization": f"{'Api-Token' if token.startswith('dt0c') else 'Bearer'} {token}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print(json.dumps({"event": "SMARTSCAPE_TOPOLOGY_SENT", "status": response.status,
                              "devices": sum(e["type"] == "EXT_NETWORK_DEVICE" for e in events),
                              "interfaces": sum(e["type"] == "EXT_NETWORK_INTERFACE" for e in events)}), flush=True)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        print(json.dumps({"event": "SMARTSCAPE_TOPOLOGY_FAILED", "status": getattr(error, "code", None),
                          "error_type": type(error).__name__}), flush=True)
