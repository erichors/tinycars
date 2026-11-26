# TinyCars SNMP network lab

TinyCars can deploy nine private SNMPv2 devices with the application:

| Site | Devices |
| --- | --- |
| Boston | `boston-router-01`, `boston-switch-01`, `boston-ap-01` |
| Chicago | `chicago-router-01`, `chicago-switch-01`, `chicago-ap-01` |
| London | `london-router-01`, `london-switch-01`, `london-ap-01` |

One low-overhead pod runs all nine responders. Each device has its own
ClusterIP service on UDP/161, stable chassis/interface MAC addresses, system
identity, location, interface state, and changing traffic counters. The
services are intentionally private; do not expose the default SNMPv2 community
to the internet.

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
kubectl -n tinycars get pod -l app.kubernetes.io/name=network-simulator
kubectl -n tinycars get svc -l app.kubernetes.io/name=network-simulator
```

The simulator image includes PySNMP, so a responder can also be queried from
inside the pod. The standard identity OID is `1.3.6.1.2.1.1.5.0` (`sysName`).

## Dynatrace requirements

For native network-device entities and interface metrics, install the
**Generic network device** extension
(`com.dynatrace.extension.snmp-generic-device`) and create a remote SNMP
monitoring configuration for the nine service IPs.

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
