# Collector options

TinyCars exports standard OpenTelemetry data and supports three explicit
collector modes. The application images are identical in every mode.

| Mode | Instrumentation | OTLP receiver | EKS command |
|---|---|---|---|
| `dynatrace` | Dynatrace Application Monitoring | DynaKube `telemetry-ingest` | `COLLECTOR_MODE=dynatrace ./deploy-eks.sh` |
| `bindplane` | OpenTelemetry Operator | Bindplane collector Service | `COLLECTOR_MODE=bindplane OTLP_ENDPOINT=http://<svc>.<ns>.svc.cluster.local:4318 ./deploy-eks.sh` |
| `otel` | OpenTelemetry Operator | Any OTLP-compatible collector | `COLLECTOR_MODE=otel OTLP_ENDPOINT=http://<svc>.<ns>.svc.cluster.local:4318 ./deploy-eks.sh` |

`dynatrace` is the default for the existing demo cluster. Bindplane and generic
OTel modes require the OpenTelemetry Operator and an existing collector
Service. The deployment script checks both requirements before building images.

## Bindplane

Install the Kubernetes collector from the Bindplane project's **Install
Collectors** page, then locate its OTLP/HTTP Service:

```bash
kubectl get svc -A | grep -i -E 'bindplane|observiq'
```

Deploy TinyCars with the resulting cluster-local endpoint:

```bash
COLLECTOR_MODE=bindplane \
OTLP_ENDPOINT=http://bindplane-node-agent.bindplane-agent.svc.cluster.local:4318 \
./deploy-eks.sh
```

The Bindplane project secret belongs only in the collector installation
manifest. TinyCars does not need or store it.

## Generic OpenTelemetry Collector

Install the OpenTelemetry Operator and a collector using the official charts:

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace opentelemetry-operator-system --create-namespace \
  --set manager.collectorImage.repository=otel/opentelemetry-collector-k8s
```

After creating an OTLP collector Service, deploy with its endpoint:

```bash
COLLECTOR_MODE=otel \
OTLP_ENDPOINT=http://otel-collector.opentelemetry.svc.cluster.local:4318 \
./deploy-eks.sh
```

## Helm without the EKS script

The chart includes overlays for each mode:

```bash
helm upgrade --install tinycars deploy/helm/tinycars -f deploy/helm/tinycars/values-bindplane.yaml
helm upgrade --install tinycars deploy/helm/tinycars -f deploy/helm/tinycars/values-otel.yaml
helm upgrade --install tinycars deploy/helm/tinycars -f deploy/helm/tinycars/values-dynatrace.yaml
```

Override `otel.endpoint` for the actual Service name. Do not enable Dynatrace
and OpenTelemetry language injection on the same pods; the EKS script removes
the DynaKube namespace label when switching to Bindplane or generic OTel mode.
