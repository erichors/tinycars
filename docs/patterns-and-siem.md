# Problem patterns and SIEM use cases

Flip these in the hidden admin panel (click the wrench in the TinyCars logo, or go to `/admin`; default token `tinycars`). Each toggle has a **level 1-5** that scales delay, error rate or burst size, and every change writes a `PATTERN_ENABLED` / `PATTERN_DISABLED` event to the logs so you can line up cause and effect on dashboards.

State lives in Redis (`tc:flags`), so a toggle applies within about 2-3 seconds, with no restarts.

## App and Postgres patterns

| Pattern | Service | What you will see | Detection idea |
|---|---|---|---|
| `inventory_db_not_responding` | inventory (.NET) | HTTP 500s from `/stock`, `/reserve`; logs `pattern=inventory_db_not_responding`; checkout failures (502 "inventory unavailable") in cart-checkout | Error-rate spike on one service; downstream failure propagation in traces |
| `catalog_search_slowdown` | catalog (Python) | `/search` latency = 0.4s x level; at level 3+ a growing share of 503s | p95 latency alert on `GET /search`; error-rate alert at higher levels |
| `checkout_dependency_stall` | cart-checkout (Java) | `/checkout` hangs 2s x level then 504 "payment processor timed out"; stock is released | Checkout latency + 504s; conversion drop |
| `storefront_high_cpu` | storefront (Node) | Request latency climbs (busy loop 60ms x level per API call); container CPU high; CPU throttling if `cpuLimit` is set on the storefront | CPU saturation and throttling metrics; latency correlated with CPU |
| `inventory_pool_exhaustion` | inventory (.NET) | Each request holds a DB connection 1.5s x level; pool (6) fills; Npgsql "connection pool has been exhausted" timeouts (HTTP 500) | Connection-pool wait/timeouts; latency rising with load |
| `inventory_slow_query` | inventory (.NET) | Query with `pg_sleep` and a sequential scan of `order_items` (no index on `sku` on purpose) | Slow DB span / long statements; DB time dominating request time |

Tip: raise the load first (admin panel, "Black Friday" preset) so pool and CPU patterns bite quickly.

## AI pattern

| Pattern | Service | What breaks | What you should see |
|---|---|---|---|
| `ai_matcher_slowdown` | catalog | "Find my car" model calls get 0.8 s x level slower; from level 3 they are throttled and the keyword matcher answers instead | `/match` latency rises; `ai match` log lines switch to `fallback: true` with a throttling `error`; the Bedrock span disappears from traces while requests still succeed (graceful degradation) |

## Store VM / SIEM-style patterns (synthetic log lines only)

The store agent writes log text; it does not touch SSH, scan anything, or edit real files. Attacker addresses use RFC 5737 documentation ranges (203.0.113.x, 198.51.100.x, 192.0.2.x), which are never real hosts.

| Pattern | Where | What is written | Detection idea |
|---|---|---|---|
| `store_failed_login_flood` (pick a store) | `/var/log/tinycars/<store>/security.log` + `store.log` | Bursts (15 x level) of `sshd` "Failed password" / `pam_unix` failures from one test IP across common usernames, then "Too many authentication failures"; repeats every 30s while on | >N failed logins from one `src_ip` in 60s; many distinct `auth_user`s from one source (password spraying) |
| `store_file_integrity_alert` (pick a store) | `/var/log/tinycars/<store>/audit.log` + `store.log` | auditd-style `SYSCALL` + `PATH` lines for edits to `/etc/tinycars/pos.conf`, `/etc/ssh/sshd_config`, `/etc/passwd`, `/etc/sudoers.d/pos` (key `tinycars_config`) | Any write to a watched path outside a change window |
| `impossible_travel` | `store.log` for two stores | Same `account` completes an in-store sale in Boston or Chicago, then in London 20-60s later (`correlation=impossible_travel_leg1/leg2`) | Same account in two countries within minutes (real travel is physically impossible) |

## Web sign-in events (always on)

The catalog service logs every shopper sign-in as JSON: `event_type=auth.login_success` or `auth.login_failed` with `user`, `reason` (`bad_password` or `unknown_user`) and `client_ip`. The loadgen produces a steady trickle of failures (about 5% of its sign-ins), which is a good baseline for a "failed logins per user or IP" detection on the web side to sit next to the store SSH patterns.

Baseline noise is always on: normal `Accepted publickey` and `sudo` lines plus an occasional single mistyped password, so detections have to tell signal from noise.

## Useful fields

- App logs (JSON): `service`, `level`, `msg`, `pattern`, `pattern_level`, `order_id`, `email`, and for sign-ins `event_type`, `user`, `reason`, `client_ip`
- Store logs (JSON): `store`, `city`, `country`, `host`, `client_ip`, `event`, `account`, `order_id`, `total`, `currency`, `correlation`
- Security lines after parsing: `host`, `process`, `auth_user`, `src_ip`, `src_port`
- Resource attributes: `service.name`, `service.namespace=tinycars`, `deployment.environment`

## Where the data shows up

Alert rules live in your destinations, not in Bindplane. In Bindplane you tag and route (see `bindplane-wiring.md`); in each backend you write the rule (log-count thresholds, latency and error-rate alerts, anomaly detection). The patterns are designed so the same toggle shows up in all three signals: a trace shows where it breaks, a metric shows the shape, and a log line names the pattern.
