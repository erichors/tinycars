# TinyCars SNMP network lab

TinyCars can deploy 27 private SNMPv2 devices with the application. Each site
has its own simulator pod and nine device services:

| Site | Devices |
| --- | --- |
| Boston | `boston-router-01`, `boston-switch-01`, `boston-ap-01`, `boston-firewall-01`, `boston-server-01`, `boston-pos-01`, `boston-pos-02`, `boston-handheld-01`, `boston-handheld-02` |
| Chicago | `chicago-router-01`, `chicago-switch-01`, `chicago-ap-01`, `chicago-firewall-01`, `chicago-server-01`, `chicago-pos-01`, `chicago-pos-02`, `chicago-handheld-01`, `chicago-handheld-02` |
| London | `london-router-01`, `london-switch-01`, `london-ap-01`, `london-firewall-01`, `london-server-01`, `london-pos-01`, `london-pos-02`, `london-handheld-01`, `london-handheld-02` |

One low-overhead pod runs the nine responders for each site. Each device has its own
ClusterIP service on UDP/161, stable chassis/interface MAC addresses, system
identity, location, interface state, and changing traffic counters. The
services are intentionally private; do not expose the default SNMPv2 community
to the internet.

The server, POS terminals, and handhelds are simulated SNMP endpoints, not
separate application containers or real payment devices.

## Site profiles and network issues

| Site | Normal traffic | Simulated issue |
| --- | --- | --- |
| Boston | Downtown sales; moderate traffic | `boston-pos-02` wired `eth0` is administratively up but operationally down. Its Wi-Fi backup stays up. |
| Chicago | Regional hub; busiest site | `chicago-firewall-01` WAN runs near capacity with rising packet discards and errors; CPU varies between 86% and 96%. |
| London | Flagship store; lighter traffic | `london-ap-01` operations Wi-Fi and `london-handheld-02` report rising wireless errors and discards. |

The admin panel's **Network** problem-pattern group controls these issues live.
Toggle a site's pattern and choose level 1–5; the corresponding SNMP simulator
reloads its records within a few seconds. Turning it off restores the healthy
baseline. The 24-hour random-problems schedule includes these patterns. State
lives in Redis along with the application patterns. If Redis is unavailable,
`networkSimulator.faultsEnabled` supplies the fallback baseline (default false).
The issues are SNMP telemetry simulations;
they do not inject packet loss into the storefront's real network traffic.

Poll `ifOperStatus` (`1.3.6.1.2.1.2.2.1.8`), IF-MIB discards/errors
(`1.3.6.1.2.1.2.2.1.13`, `.14`, `.19`, `.20`), 64-bit octets
(`1.3.6.1.2.1.31.1.1.1.6`, `.10`), and CPU
(`1.3.6.1.2.1.25.3.3.1.2`) to see the scenarios.

## Deploy

`deploy-eks.sh` enables the simulator automatically. For a direct Helm install:

```bash
helm upgrade --install tinycars deploy/helm/tinycars \
  --namespace tinycars \
  --set networkSimulator.enabled=true \
  --set-string networkSimulator.community='<private-community>'
```

Build and push `tinycars-network-sim` alongside the application images with
`deploy/build-push.sh`.

## Verify in Kubernetes

```bash
kubectl -n tinycars get deploy -l app.kubernetes.io/name=network-simulator
kubectl -n tinycars get svc -l app.kubernetes.io/name=network-simulator
```

The simulator image includes PySNMP, so a responder can also be queried from
inside the pod. The standard identity OID is `1.3.6.1.2.1.1.5.0` (`sysName`).

## Dynatrace requirements

### In-cluster OTLP polling

On the TinyCars EKS deployment, `network-poller` reads the 27 private SNMP
services and sends device and interface metrics to the configured OTLP endpoint.
Each series includes `tinycars.app=tinycars`, `device.name`, `device.site`,
`device.type`, `device.address`, `device.description`, `device.location`, and
`device.contact`; interface series also include `if.name`. The poller checks
`sysName` and the TinyCars description before accepting a device. Metrics use
the `tinycars.network.*` namespace and include device availability and CPU,
interface operational status, per-second errors/discards, and throughput.
Throughput uses 64-bit IF-MIB counters to handle the high-volume WAN scenario.

Enable with `networkPoller.enabled=true` when `networkSimulator.enabled=true`.
The endpoint defaults to the chart's `otel.endpoint` plus `/v1/metrics`.
This provides Dynatrace metrics with TinyCars metadata without an extension
runner. It does **not** create native `EXT_NETWORK_DEVICE` Smartscape nodes;
that requires the Generic network device extension described below.

The [network-failures.dql](../deploy/dynatrace/network-failures.dql) query is
ready for a single record-based Dynatrace anomaly detector. It returns one
row per failing interface and uses the stable `device.name` plus `if.name` as
alert identity. Use `dt.alert_group=tinycars-network` and event type
`CUSTOM_ALERT` when creating the detector. A detector is a separate Dynatrace
configuration: metric ingestion alone does not open a Davis problem.
The [Settings API payload](../deploy/dynatrace/network-failures-detector.json)
is prepared alongside the query. It needs `settings:objects:write`,
`settings:schemas:read`, `storage:metrics:read`, and detector execution
permission on the target environment before it can be applied.

### Native network device entities

For native network-device entities and interface metrics, install the
**Generic network device** extension
(`com.dynatrace.extension.snmp-generic-device`) and create a remote SNMP
monitoring configuration for the 27 service IPs. If you previously configured
the nine original devices, refresh their target IPs after upgrading because
Kubernetes may assign new ClusterIP addresses when services are recreated.

The poller must have a network path into the EKS service CIDR. A traditional
host-based Environment ActiveGate supports SNMP extensions. A containerized
ActiveGate does not run ActiveGate extensions; on Kubernetes, use a supported
Extension Execution Controller deployment when available, or run a host-based
ActiveGate in a connected subnet. The SNMP auto-discovery extension can find
devices but does not replace the Generic network device extension's metrics.

The admin toggle changes SNMP responses, but a Dynatrace problem requires a
working SNMP poller plus an alert detector for interface status, error/discard
rates, or CPU. Check those two stages if no Dynatrace problem appears.

Required platform-token scopes are:

- `extensions:definitions:read` and `extensions:definitions:write`
- `extensions:configurations:read` and `extensions:configurations:write`

Keep the community in Dynatrace's credential vault for non-demo environments.
