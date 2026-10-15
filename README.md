# TinyCars

A toy-car storefront built as an observability test bed. Five small services in four languages run on any Kubernetes cluster, get auto-instrumented by the OpenTelemetry Operator, and send metrics, traces and logs to a Bindplane collector. A VM simulates three retail stores (Boston, Chicago, London) and produces store and security logs. A hidden admin panel (the wrench in the logo) controls load and switches on problem patterns.

![catalog](docs/contact-sheet.png)

| Service | Language | Datastore | Notes |
|---|---|---|---|
| `storefront` | Node.js (Express) | Redis | UI, API gateway, hidden `/admin` |
| `catalog` | Python (FastAPI) | Postgres | 67 SKUs, search |
| `cart-checkout` | Java (JDK HttpServer) | Postgres, Redis | carts in Redis, orders in Postgres |
| `inventory` | .NET 8 minimal API | Postgres | per-location stock (warehouse, boston, chicago, london) |
| `loadgen` | Python (asyncio) | Redis | rate set from the admin panel |
| store agent (VM) | Python (stdlib only) | none | 3 stores, JSON + syslog-style + audit-style logs |

Design rules: app code contains **no OpenTelemetry or vendor SDKs**; the only environment-specific values are the image registry and the Bindplane OTLP endpoint; nothing is destination-specific. See `docs/spec.md`.

## What was and was not verified

Tested end to end in a sandbox with real Postgres and Redis: catalog, storefront (UI smoke-tested in jsdom, admin API), loadgen, store agent, the SQL, and the problem-pattern toggles for catalog and storefront. Contract-compatible Python stand-ins were used for `inventory` and `cart-checkout`.

**Not run here, so check first:** the Java and .NET services (the Java was type-checked against stubs; the .NET could not be compiled), the Docker builds, the Helm chart under real `helm` (it was rendered with a small template checker), and everything on a real cluster. If an image fails to build or a pod fails, the error will point at the line; expect one or two small fixes.

## Quick start (EKS shown; any Kubernetes works)

**Full step-by-step EKS guide: [docs/install-eks.md](docs/install-eks.md).** The summary below is the short version.

### 0. Prerequisites

`aws`, `eksctl`, `kubectl`, `helm`, `docker`; a Bindplane Cloud account; a Bindplane collector reachable from the cluster (step 4).

### 1. Cluster

```bash
eksctl create cluster --name tinycars --region us-east-1 --node-type m5.xlarge --nodes 2 --managed
```

### 2. Build and push images

```bash
for s in storefront catalog cart-checkout inventory loadgen; do aws ecr create-repository --repository-name tinycars-$s; done
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
REGISTRY=<account>.dkr.ecr.<region>.amazonaws.com/ TAG=1.0.0 ./deploy/build-push.sh
```

### 3. OpenTelemetry Operator

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl -n cert-manager rollout status deploy/cert-manager-webhook
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install opentelemetry-operator open-telemetry/opentelemetry-operator -n opentelemetry-operator-system --create-namespace
```

### 4. Bindplane collectors

Follow `docs/bindplane-wiring.md` sections 1-3: create the configurations, add your destinations in the Bindplane UI, install the Node and Cluster collectors, then note the Node collector's service address.

### 5. Install TinyCars

```bash
helm install tinycars deploy/helm/tinycars \
  --set image.registry=<account>.dkr.ecr.<region>.amazonaws.com/ \
  --set otel.endpoint=http://<node-collector-svc>.<ns>.svc.cluster.local:4318 \
  --set adminToken=<pick-one>
kubectl get pods -w        # wait for everything Running (first Postgres start seeds the data)
kubectl get svc storefront # EXTERNAL-IP / hostname = the store
```

Postgres seeds 67 cars, per-location stock, and ~420 historical orders on first boot. The loadgen starts at a gentle 20 sessions/min.

### 6. Use it

Open the storefront. Click the small **wrench** that is part of the logo (it is faint until hover) to open the control room, or browse to `/admin`. Enter the token. From there:

- Load: Quiet / Normal / Black Friday presets, sessions-per-minute slider, web vs in-store mix, start/stop.
- Nine problem-pattern toggles with levels 1-5 (see `docs/patterns-and-siem.md`).

### 7. The store VM

Launch an Ubuntu 22.04 EC2 instance in the same VPC. Copy `store-agent/` to it, then:

```bash
sudo STOREFRONT_URL=http://<storefront ELB hostname> ADMIN_TOKEN=<token> ./install.sh        # add TINYCARS_OTEL=1 for POS traces
```

Install the Bindplane collector on the VM from the `tinycars-vm-stores` configuration (`docs/bindplane-wiring.md` section 4). Logs are in `/var/log/tinycars/{boston,chicago,london}/`.

### 8. Check the data

Bindplane live preview first (traces from five services, container logs, kubelet metrics, VM logs), then your destinations. Walk `docs/patterns-and-siem.md` and flip a pattern to see it land.

## Local preview (no telemetry)

```bash
docker compose -f deploy/docker-compose.yml up --build     # http://localhost:8080
```

Auto-instrumentation comes from the Operator, so compose shows behavior only.

## Useful commands

```bash
python3 tools/gen_catalog.py     # regenerate the 67 SVGs and db/seed.sql (deterministic)
helm upgrade tinycars deploy/helm/tinycars --reuse-values --set services.storefront.cpuLimit=500m   # make CPU throttling visible
helm uninstall tinycars && kubectl delete pvc -l app.kubernetes.io/name=postgres                    # reset data
```

## Layout

```
services/{storefront,catalog,cart-checkout,inventory,loadgen}   app code + Dockerfiles
store-agent/                                                    VM agent, systemd installer
db/                                                             schema.sql, generated seed.sql
deploy/helm/tinycars/                                           Helm chart (values.yaml = all knobs)
deploy/docker-compose.yml, deploy/build-push.sh
docs/                                                           spec, Bindplane wiring, patterns, contact sheet
tools/                                                          art + catalog generator
```

## Notes

- All cars are original generic designs; no real makes, logos, military insignia or toy-brand names.
- The failed-login, file-integrity and impossible-travel patterns only write log text. The agent never touches SSH, scans anything or edits system files.
- The default admin token is `tinycars`. Change it for anything exposed beyond a lab, and keep the storefront load balancer restricted.

## Catalog and detail views

67 cars in 9 categories with 62 distinct generic silhouettes, rendered as studio product shots (lit paint, tinted glass, chrome, detailed wheels and tracks, contact shadows and floor reflections; SVG lighting filters, so they look best in a browser). Click any car for a detail view with hotspot pins, close-up zoom, lightbox, specs and per-store stock. Regenerate art and seed data with `python3 tools/gen_catalog.py`.
