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

Faults are enabled by default. Set `networkSimulator.faultsEnabled=false` in
Helm for healthy per-site baselines. The issues are SNMP telemetry simulations;
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

Required platform-token scopes are:

- `extensions:definitions:read` and `extensions:definitions:write`
- `extensions:configurations:read` and `extensions:configurations:write`

Keep the community in Dynatrace's credential vault for non-demo environments.
