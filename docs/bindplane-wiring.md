# Wiring TinyCars to Bindplane

Goal: collect **metrics, traces and logs** from the EKS cluster and the store VM in Bindplane, then send them to whatever destinations you add in the Bindplane UI. Nothing in the app or chart is destination-specific.

```
EKS pods --OTLP/HTTP :4318--> Bindplane Node collector (DaemonSet) --+
EKS container logs + kubelet metrics ----^                           |
EKS cluster metrics + events --> Bindplane Cluster collector --------+--> Bindplane Cloud --> your destinations
Store VM: OTLP :4318 (localhost), host metrics, 3 log files --> Bindplane collector on the VM --+
```

Bindplane is the pipeline (collect, parse, enrich, route). The OpenTelemetry Operator does the auto-instrumentation. Bindplane does not instrument applications.

## 1. Create three configurations in Bindplane Cloud

| Configuration | Platform | Sources | Purpose |
|---|---|---|---|
| `tinycars-eks-node` | Kubernetes Node | OpenTelemetry (OTLP), Kubernetes Container Logs, Kubernetes Kubelet Metrics | App traces/metrics/logs via OTLP, container logs, node and pod metrics |
| `tinycars-eks-cluster` | Kubernetes Cluster | Kubernetes Cluster Metrics, Kubernetes Cluster Events | Deployment/pod state, restarts, OOMKills, events |
| `tinycars-vm-stores` | Linux | OpenTelemetry (OTLP), Host Metrics, File x3 | Store POS traces, host CPU/mem/disk, store/security/audit logs |

Kubernetes collectors are bound to one configuration each, so create the configuration before installing the collector.

Attach your destination(s) to **all three** configurations, with Logs, Metrics and Traces all selected. Add or swap destinations later (Datadog, Splunk, Google Cloud, Grafana, Dynatrace, ...) the same way; the apps and chart do not change.

### Source settings that matter

- **OTLP (EKS node config):** keep the default ports (HTTP 4318, gRPC 4317). Pods reach it through the collector's ClusterIP service.
- **OTLP (VM config):** bind to `127.0.0.1` (only the local store agent sends to it).
- **Kubernetes Container Logs:** restrict to the namespace you install TinyCars into and exclude the collector's own namespace to avoid feedback loops.
- **File (VM config):** create three File sources, each with *Include File Path Attribute* turned on (so the store name is available from `log.file.path`) and *Start At* = `beginning` for the first run:

  | Source | File Path(s) | Log Type |
  |---|---|---|
  | stores-app | `/var/log/tinycars/*/store.log` | `tinycars_store` |
  | stores-security | `/var/log/tinycars/*/security.log` | `tinycars_security` |
  | stores-audit | `/var/log/tinycars/*/audit.log` | `tinycars_audit` |

  The File source does not parse content; add the processors below.

## 2. Parsing processors (this is the "SIEM-ready" layer)

All app logs are one JSON object per line, so parsing is one processor.

**Container logs (EKS) and `store.log` (VM):** add a **Parse JSON** processor (parse from body). Useful fields after parsing: `service`, `level`, `msg`, `event`, `pattern`, `pattern_level`, `order_id`, `account`, `store`, `city`, `country`, `correlation`.

**`security.log` (syslog-style lines, e.g. `Oct 15 13:16:12 boston-pos-01 sshd[13863]: Failed password for invalid user backup from 203.0.113.26 port 54785 ssh2`):** add **Parse with Regex** processors:

```
^(?P<syslog_ts>\w{3}\s+\d+\s[\d:]+)\s(?P<host>\S+)\s(?P<process>[\w-]+)\[(?P<pid>\d+)\]:\s(?P<message>.*)$
```

then a second one on `message` for failed logins:

```
Failed password for (?:invalid user )?(?P<auth_user>\S+) from (?P<src_ip>\S+) port (?P<src_port>\d+)
```

Then use **Add Fields** to stamp events you want to key detections on, e.g. `security.signal = auth_failure` for failed-password lines. The store name is in `host` (`boston-pos-01`, `chicago-pos-01`, `london-pos-01`).

**`audit.log` (`type=SYSCALL msg=audit(...): ... key="tinycars_config"`):** add **Parse Key Value** (delimiter space, pair delimiter `=`), then stamp `security.signal = file_integrity` where `key` is `tinycars_config`.

Optional: **Parse Severity** on `level`, and **Filter**/**Log Sampling** processors if volume matters when you fan out to several backends.

## 3. Install the collectors on EKS

1. In Bindplane, open each Kubernetes configuration, choose **Install Collectors**, and copy the generated command or manifest for your cluster. Apply it with `kubectl`/`helm` as shown.
2. Confirm the pods are running, then find the Node collector's OTLP service:

   ```bash
   kubectl get pods -A | grep -i -E 'bindplane|observiq'
   kubectl get svc  -A | grep -i -E 'bindplane|observiq'
   ```

3. Your endpoint for TinyCars is `http://<service>.<namespace>.svc.cluster.local:4318`. Deploy with the explicit Bindplane mode:

   ```bash
   COLLECTOR_MODE=bindplane \
   OTLP_ENDPOINT=http://<service>.<namespace>.svc.cluster.local:4318 \
   ./deploy-eks.sh
   ```

   For direct Helm use, add `-f deploy/helm/tinycars/values-bindplane.yaml` and override `otel.endpoint`. The Bindplane project secret stays in the collector manifest; TinyCars never needs it.

## 4. Install the collector on the store VM

1. In `tinycars-vm-stores`, choose **Install Collectors**, pick Linux, and run the generated one-line install on the VM.
2. The collector must be able to read `/var/log/tinycars` (the store agent creates it world-readable).
3. Optional traces from the store POS: install the agent with `TINYCARS_OTEL=1`, so POS calls to the storefront appear as traces that continue into the cluster services (same trace across VM and EKS).

## 5. Verify

Use Bindplane's live preview/snapshot on each collector:

| Where | You should see |
|---|---|
| EKS node collector | Traces from `storefront`, `catalog`, `cart-checkout`, `inventory`, `loadgen`; JSON container logs; kubelet metrics |
| EKS cluster collector | Cluster metrics and Kubernetes events |
| VM collector | `store.log` JSON events, `security.log` lines, `audit.log` lines, host metrics, `store-pos` traces if enabled |

A single checkout trace should span `storefront` (Node) -> `cart-checkout` (Java) -> `catalog` (Python) and `inventory` (.NET) -> Postgres/Redis. If every service appears but traces are not joined, check that propagators include `tracecontext`.

## 6. Adding more destinations later

Add the destination in the Bindplane UI and attach it to the three configurations. Things to think about first:

- **Cost and volume:** five backends means five bills. Keep log verbosity sensible and sample in Bindplane (one place), not per backend.
- **Attributes stay standard OTel:** `service.name`, `service.namespace`, `deployment.environment`, plus `store`, `city`, `country`. Any vendor-specific enrichment (for example a Dynatrace enrichment processor) should be attached to that destination only, so the base data stays portable.
- **Metrics types:** some backends do not accept every OTel metric type (cumulative monotonic sums are a known gap for some); check each destination's page in the Bindplane docs.
- **Credentials:** every destination needs its own token/key, stored in Bindplane, not in this repo.

## 7. Recipe: add a new service

1. Write the service with plain app code (no vendor SDKs). Read config from env.
2. Add an entry under `services:` in `values.yaml` with its image, port and `inject` language (`java`, `nodejs`, `python`, `dotnet`).
3. The pod annotation `instrumentation.opentelemetry.io/inject-<lang>: "true"` is added by the chart; it points at the `tinycars` Instrumentation CR.
4. Make sure `OTEL_EXPORTER_OTLP_ENDPOINT` reaches the pod (the chart provides it through the `tinycars-config` ConfigMap).
5. Redeploy, then confirm the service appears in the Bindplane live preview. Done.

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| No traces at all | `kubectl describe pod <pod>` shows an `opentelemetry-auto-instrumentation` init container? If not: Operator + cert-manager running, and the Instrumentation CR exists in the same namespace as the pods. |
| Pods show the init container but no data | Endpoint wrong or not reachable: `kubectl run -it --rm curl --image=curlimages/curl -- curl -v http://<svc>.<ns>.svc:4318/v1/traces` should return HTTP 405/200, not a connection error. |
| One language missing | Look at that pod's startup logs for the agent banner. Java: `JAVA_TOOL_OPTIONS` set by the Operator. .NET: image is Debian-based, so no musl annotation is needed. |
| Logs arrive unparsed | Add the Parse JSON / Regex / Key Value processors from section 2 to that source. |
| VM logs missing | `sudo -u <collector user> ls /var/log/tinycars/boston/`; File source *Start At*; offsets reset in the collector storage directory. |
| Metrics missing in one backend | Destination page in Bindplane docs (metric type support); check the destination's logs in Bindplane. |
