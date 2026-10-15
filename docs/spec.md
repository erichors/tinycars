# TinyCars — Spec

A diecast-style toy car storefront used as an observability test bed: polyglot microservices running on any Kubernetes cluster, auto-instrumented via the OpenTelemetry Operator, a Boston "retail location" VM generating store and security telemetry, an in-app load generator and problem-pattern injector behind a hidden admin panel, all routed through Bindplane to whichever backends are configured there (Dynatrace and Grafana today; Datadog, Splunk, and Google Cloud are future additions configured entirely in the Bindplane UI — nothing destination-specific lives in this spec or in application code).

## Design principles

1. **Lightweight.** Five core services, no Go/eBPF auto-instrumentation complexity, slim/alpine-based images, no component included that isn't earning its keep.
2. **Fun and nice-looking.** Toy-aisle visual theme throughout, playful touches (a running "cars sold" counter, a "new arrival" ribbon, an empty-garage empty-cart state), consistent flat-vector illustration style across the catalog.
3. **Extensible.** Every new module is its own small service with its own OTel instrumentation, following the onboarding recipe in §6 — no logic gets jammed into an existing service to avoid standing up a new one.
4. **Easy to use.** One Helm chart (or one `docker compose up` locally) stands up every service, Postgres, Redis, and the Instrumentation CR together.
5. **Runs anywhere.** Pure OTLP to a configurable collector endpoint, no vendor SDKs or cloud-specific managed services baked into application code, no cloud-specific IAM/storage assumptions in manifests. Portable across EKS, GKE, AKS, or a local kind cluster — only the collector endpoint value and ingress type change per environment.

## 1. Product concept

**Brand**: TinyCars — vintage diecast-style toy cars, original designs (not licensed replicas). Studio-rendered/illustration art style: clean shapes, limited flat color palettes, consistent framing (3/4 angle) across all 50+ images so the catalog feels cohesive and is cheap to extend with more SKUs later.

**Catalog**: 60 SKUs at launch (the "50+" floor with headroom), generic body styles/eras rather than real makes/models or trademarked names (no "Bronco," "Jeep," "Humvee," etc. in product names or art — use evocative generic names instead). Categories:

| Category | Approx. SKUs | Examples (generic names) |
|---|---|---|
| Classics & Muscle | 10 | "'67 Muscle Coupe," "Classic Microbus," "Rally Hatch" |
| Off-Roaders (Bronco/Jeep-style 4x4s) | 10 | "Trailblazer 4x4," "Canyon Climber," "Boxy Ranger," "Rock Crawler" |
| Pickups | 8 | "Farm Hauler," "Crew Cab Classic," "Lowrider Pickup" |
| Sports & Supercars | 10 | "Apex Roadster," "Midnight GT," "Track Day Special" |
| Military & Army | 8 | utility-truck/Humvee-style, troop transport, supply truck, recon jeep-style, tank, armored carrier (generic silhouettes, no insignia/manufacturer branding) |
| Construction | 6 | dump truck, excavator, bulldozer, cement mixer, crane truck, front loader |
| Limited editions (cross-category) | 8 | numbered/gold-trim variants of popular castings |

**Pricing**:
- Basic casting: $3.99–$8.99
- Premium/detailed casting: $12.99–$24.99
- Limited edition / military line: $29.99–$59.99

**Inventory fields per SKU**: id, name, category, body style, era/decade, color/livery, price (USD; GBP for London), stock count per location, weight class (basic/premium/limited), image asset.

**Locations**: web warehouse plus three retail stores — Boston (US East), Chicago (US Central), London (UK). Each store has its own stock levels, local timezone/business-hours traffic pattern, and currency (London prices in GBP).

**Seed data**: populate all 60 SKUs with realistic per-location stock levels, plus a backlog of historical orders/logs, so dashboards have something to show from first boot rather than starting empty.

## 2. Services

| Service | Language | Role | Datastore |
|---|---|---|---|
| `storefront` | Node.js | Web UI: catalog pages, cart, checkout flow, hosts the hidden admin entry point | — |
| `catalog` | Python | Product catalog, search, 50+ SKU data, images | Postgres (read) |
| `cart-checkout` | Java | Cart state (Redis, 1h TTL), checkout, payment simulation (approve/decline), order history | Postgres + Redis |
| `inventory` | .NET | Per-location stock levels (web warehouse + Boston store), restock logic | Postgres |
| `loadgen` | Python, in-cluster | Driven by the admin panel; generates synthetic storefront traffic at an adjustable rate | reads config from Redis |

**Postgres**: backs `catalog`, `cart-checkout`, and `inventory` — gives Dynatrace/Grafana a real relational datastore to show database spans, query latency, and connection-pool metrics against.

**Redis**: a lightweight shared key-value store, read by every service, holding the current state of all problem-pattern toggles and the load generator's target rate. This is what the admin panel writes to — no dedicated feature-flag service, no restarts required; services poll or subscribe to the relevant keys and apply the behavior change within a few seconds.

Each service gets an OTel Operator `Instrumentation` CR annotation for its language (Node/Python/Java/.NET — no Go services, so no eBPF auto-instrumentation needed).

## 3. Admin panel ("the wrench")

- A small wrench glyph layered into the TinyCars logo (e.g. top-right corner, low-contrast until hovered). Clicking it opens `/admin`, not linked anywhere in the main nav, gated behind a simple static token or click-sequence.
- Visually distinct from the storefront (plain/utilitarian, monospace, dark background) so it reads as "behind the curtain."

**Load controls**:
- Slider/presets for requests-per-minute against the storefront (Quiet / Normal / Black Friday)
- Toggle: web traffic vs. Boston in-store traffic mix
- Start/stop the load generator independently of problem patterns

**Problem-pattern toggles** — each writes its state to Redis; services read it and apply the behavior live. Each toggle also emits a clear `PATTERN_ENABLED`/`PATTERN_DISABLED` log event (pattern name, timestamp) so cause and effect are visible on dashboards.

*App-level (mapped from Dynatrace's easyTrade demo patterns):*
1. `inventory_db_not_responding` — `inventory` starts throwing DB errors; no stock updates or restocks can complete (easyTrade's `DbNotResponding`)
2. `catalog_search_slowdown` — `catalog` search responses slow down and eventually drop traffic under load (easyTrade's `ErgoAggregatorSlowdown`)
3. `checkout_dependency_stall` — `cart-checkout`'s payment-processor dependency stops responding, blocking checkout (easyTrade's `FactoryCrisis`)
4. `storefront_high_cpu` — `storefront` CPU spikes and response times degrade; apply a pod CPU limit to see throttling in K8s metrics (easyTrade's `HighCpuUsage`)

*Postgres-specific:*
5. `inventory_pool_exhaustion` — `inventory` holds DB connections too long; the pool fills up and new requests queue/fail
6. `inventory_slow_query` — `inventory` runs an artificially slow query (e.g. forced full table scan) against Postgres, visible as DB span latency and query-level detail

*VM / SIEM-style (see §4):*
7. `store_failed_login_flood` — burst of failed SSH/auth log lines on the VM (selectable store: Boston, Chicago, or London)
8. `store_file_integrity_alert` — synthetic audit-style event on a watched config path (selectable store)
9. `impossible_travel` — an in-store checkout at one location (e.g. Boston) and an order from a distant location (e.g. London) on the same account/session within minutes — classic fraud/SIEM correlation signal, and now realistic with three geographies

## 4. Retail locations (VM): Boston, Chicago, London

- Three physical TinyCars stores, separate from the web warehouse. Default deployment is **one VM running three store-agent processes** (one per location, each with its own log file and resource attributes) to stay lightweight; the same agent can later be split onto separate VMs/regions with no code change.
- Each store agent differs by timezone/business-hours traffic curve, currency (London in GBP), and local stock levels. Per-store attributes: `location` (boston | chicago | london), `store.id`, `cloud.region`/`geo.country` where applicable.
- Each store agent:
  - Calls the storefront's APIs to simulate in-store POS checkouts (tagged `channel: in_store`, `location: <store>`)
  - Writes structured JSON logs for store lifecycle events (sale rung up, local pickup, restock request to `inventory`)
  - Emits host-level telemetry (`sshd`/auth logs, `auditd` watches on sensitive paths) — the normal source for the security-pattern toggles above; no live attack tooling runs on the VM, only the log lines those patterns would produce.
- Location metadata (store id, address, lat/long) attached as resource attributes so dashboards can show it as a distinct site.

## 5. Visual direction

- Product grid with large card images, warm wood-tone/cardboard-box background cues, clean typography, category rails (Classics, Muscle, Military & Army Line, Limited Editions).
- Studio-rendered illustration style throughout — single car, 3/4 angle, limited flat palette, consistent silhouette treatment so all 50+ images read as one cohesive set and new SKUs are cheap to add later.
- Admin panel stays visually separate, as noted in §3.

## 6. OTel + Bindplane onboarding recipe (apply to every current and future service)

1. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (env var/config map) to the Bindplane Node collector's in-cluster service address, e.g. `http://<svc>.<namespace>.svc.cluster.local:4318` (HTTP) or `:4317` (gRPC). This is the only environment-specific value — everything else about instrumentation is identical regardless of where the cluster runs.
2. Add the service's pod annotation for the OTel Operator's `Instrumentation` CR, matching its language — `inject-java`, `inject-python`, `inject-nodejs`, or `inject-dotnet` set to `"true"`, per the service/language mapping in §2's table.
3. Set standard OTel resource attributes, not vendor-specific ones: `service.name`, `service.namespace`, `deployment.environment`, `service.version`, plus TinyCars-specific attributes (`location`, `channel`) using plain OTel semantic conventions so every backend's service/entity view (Dynatrace, Datadog, Splunk, Grafana, Google Cloud) maps it the same way.
4. Do not add a vendor SDK or vendor-specific exporter to application code, ever — OTLP to the collector only. Any vendor-specific enrichment (e.g. a Dynatrace-specific attribute mapping) happens as an optional Bindplane processor, attached per destination, not baked into the base pipeline.
5. Confirm the new service shows up in Bindplane's Live Preview/Snapshot before considering it wired up.

## 7. What this spec deliberately avoids

- No real automotive brand likenesses, logos, or copyrighted toy-brand names on the product itself.
- No real military unit insignia or manufacturer branding on the Humvee-style/army vehicles/tank.
- No live brute-force or scanning tools on the VM — security-pattern toggles generate the log lines a real attack would produce, without running actual exploitation or scanning tools.
- No destination-specific (Dynatrace/Datadog/Splunk/GCP) configuration anywhere in this spec or in application code — new backends are added entirely via the Bindplane UI as destinations attached to the existing pipeline configs.
- No cloud-specific managed services or IAM assumptions baked into manifests, to keep the whole thing portable across clusters.

## 8. As built (v1)

- Repository: `tinycars/` (app code, Dockerfiles, Helm chart, store agent, docs, generators). Start with its `README.md`; Bindplane wiring is in `docs/bindplane-wiring.md`, patterns in `docs/patterns-and-siem.md`.
- Toggles and load state: Redis hashes `tc:flags` (JSON per pattern: on, level 1-5, store) and `tc:load` (running, rpm, web_pct); services cache them for ~2 seconds.
- Store VM: one Python (stdlib-only) agent runs the three stores as threads, reads the flags from the storefront admin API, and writes `store.log` (JSON), `security.log` (syslog-style) and `audit.log` (auditd-style) per store under `/var/log/tinycars/<store>/`. Security patterns write synthetic log lines only; no real SSH, scanning or file edits. Optional POS traces with `TINYCARS_OTEL=1`.
- Delivery: Helm chart is primary (`otel.endpoint` and `image.registry` are the only environment-specific values); `docker-compose.yml` is a no-telemetry preview.
- Verification status: Python and Node components and the SQL were run against real Postgres/Redis; Java was type-checked against stubs; .NET, Docker builds, Helm and a live cluster were not run in the build environment.

## 9. Open items

- Decided: v1 uses one VM hosting all three store agents (single Bindplane VM collector). Splitting into per-region VMs is a later option.
- Catalog is 67 SKUs (60 at launch plus later additions); adjust category counts in §1 if you want a different mix.
- Future modules (not in v1, each following the §6 recipe when added): recommendations service, returns/RMA service, loyalty/rewards service, second physical store location, external synthetic-monitoring check against the storefront.

## 9. Update: catalog and detail views (v2)

- 72 SKUs across 9 categories: Classics & Muscle 10, Imports & Compacts 8, Off-Roaders 8, Pickups 4, Everyday & Emergency 13, Sports & Racing 8, Military & Army 6, Construction 10, Limited Edition 5. SKUs TC-061 to TC-066 (angular stainless pickup, bucket truck, sand rail, flatbed, farm tractor, backhoe) were appended so earlier SKU numbers are stable, followed by TC-067 (oval-track stock car) and TC-068 to TC-072 (police SUV, fire command SUV, steam roller, 1970s subcompact fastback, stainless gullwing coupe). TC-005 is now a hot-dog promo car (Big Frank Cruiser) instead of a second long-roof wagon.
- 67 distinct hand-built SVG silhouettes, with softened die-cast-style corners and crowned panels (the wedge cars stay hard-edged) (coupe, sedan, wagons, boxy sedan, muscle, rear-engine sports, rat rod, motorhome, microbus, 3-wheelers, mini, monster truck, bug, convertible, funny car and more), generated by `tools/carart.py`. Shaded bodies, glass, chrome, detailed wheels, floor reflection. All names and shapes are generic.
- Each product has a `specs` jsonb column (class, scale, length, year, finish, wheels, features, rarity, pack, hotspots).
- Detail view: tilt stage, clickable hotspot pins and close-up chips with zoom and callout, lightbox, spec table, per-location stock tiles, quantity picker, related cars.
