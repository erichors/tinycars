# TinyCars

A toy-car storefront built as an observability test bed. Five small services in four languages run on any Kubernetes cluster, get auto-instrumented by the OpenTelemetry Operator, and send metrics, traces and logs to a Bindplane collector. A VM simulates three retail stores (Boston, Chicago, London) and produces store and security logs. A hidden admin panel (the wrench in the logo) controls load and switches on problem patterns.

![catalog](docs/contact-sheet.png)

| Service | Language | Datastore | Notes |
|---|---|---|---|
| `storefront` | Node.js (Express) | Redis | UI, API gateway, hidden `/admin` |
| `catalog` | Python (FastAPI) | Postgres | 72 SKUs, search |
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

Postgres seeds 72 cars, per-location stock, and ~420 historical orders on first boot. The loadgen starts at a gentle 20 sessions/min.

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
python3 tools/gen_catalog.py     # regenerate the 72 SVGs and db/seed.sql (deterministic)
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

72 cars in 9 categories with 68 distinct generic silhouettes, rendered as studio product shots (lit paint, tinted glass, chrome, detailed wheels and tracks, contact shadows and floor reflections; SVG lighting filters, so they look best in a browser). Click any car for a detail view with hotspot pins, close-up zoom, lightbox, specs and per-store stock. Regenerate art and seed data with `python3 tools/gen_catalog.py`.

## Shopping, accounts and order history

The storefront is laid out like a marketplace: a header with a categories menu, a large search bar, sign-in and a cart, a category row underneath, a split hero, "shop by category" circles and product grids. It uses the AHEAD 2024 palette on a white background.

Twelve demo shoppers are seeded, each with 14 to 28 past orders going back about 18 months (online and in-store). Every demo account uses the password `tinycars`; the sign-in dialog lists them so you can click one.

| Account | Name | Home store |
|---|---|---|
| alex.rivera@example.com | Alex Rivera | Boston |
| priya.patel@example.com | Priya Patel | Chicago |
| sam.okafor@example.com | Sam Okafor | London |
| jordan.kim@example.com | Jordan Kim | Boston |
| casey.nguyen@example.com | Casey Nguyen | Chicago |
| morgan.rossi@example.com | Morgan Rossi | London |
| taylor.brooks@example.com | Taylor Brooks | Boston |
| riley.chen@example.com | Riley Chen | Chicago |
| jamie.walker@example.com | Jamie Walker | London |
| avery.lopez@example.com | Avery Lopez | online only |
| drew.murphy@example.com | Drew Murphy | online only |
| harper.singh@example.com | Harper Singh | online only |

Signed-in shoppers check out under their account, so new orders appear at the top of **Purchases** (`#/account`). Sessions are kept in Redis (`tc:sess:<token>`, HttpOnly cookie). The loadgen signs in as a demo shopper for about 30% of web sessions (`SIGN_IN_PCT`) and mistypes the password about 5% of the time, so login traces and `auth.login_failed` log events show up without any extra setup.

Static previews of each page are in `docs/` (`storefront-preview.html`, `-categories-`, `-category-`, `-product-`, `-signin-`, `-cart-`, `-account-`); open them in a browser.

## Find my car (AI matcher)

A **Find my car** button in the header lets a shopper describe their personality and get a car picked for them, with a one-line reason. It runs a local keyword matcher by default, so it works anywhere. Set `ai.matcher.provider=bedrock` to have Claude Haiku on Amazon Bedrock make the pick (`us.anthropic.claude-haiku-5-5`). Setup (IAM policy, EKS Pod Identity, verification), log fields and the `ai_matcher_slowdown` problem pattern are in [docs/ai-matcher.md](docs/ai-matcher.md).
