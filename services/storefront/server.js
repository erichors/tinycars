'use strict';
// TinyCars storefront (Node.js / Express, CommonJS).
// Plain app code: no OpenTelemetry imports. Tracing comes from the OTel Operator (inject-nodejs).
// Serves the UI, proxies /api/* to backend services, and hosts the hidden admin API.
// Problem-pattern + load state lives in Redis (tc:flags, tc:load).
const express = require('express');
const path = require('path');
const { createClient } = require('redis');

const PORT = Number(process.env.PORT || 8080);
const URLS = {
  catalog: process.env.CATALOG_URL || 'http://catalog:8081',
  cart: process.env.CART_URL || 'http://cart-checkout:8082',
  inventory: process.env.INVENTORY_URL || 'http://inventory:8083',
};
const REDIS_URL = process.env.REDIS_URL || 'redis://redis:6379/0';
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || 'tinycars';
const STORES = ['boston', 'chicago', 'london'];

// Source of truth for the admin panel and for what services/agents react to.
const PATTERNS = [
  { name: 'inventory_db_not_responding', group: 'App', service: 'inventory', label: 'Inventory DB not responding', description: 'inventory throws database errors; stock cannot be reserved or restocked (easyTrade DbNotResponding).' },
  { name: 'catalog_search_slowdown', group: 'App', service: 'catalog', label: 'Catalog search slowdown', description: 'Search slows down, then starts timing out under load (easyTrade ErgoAggregatorSlowdown).' },
  { name: 'checkout_dependency_stall', group: 'App', service: 'cart-checkout', label: 'Checkout payment stall', description: 'Payment processor stops responding; checkouts hang then time out (easyTrade FactoryCrisis).' },
  { name: 'storefront_high_cpu', group: 'App', service: 'storefront', label: 'Storefront high CPU', description: 'Storefront burns CPU per request; latency climbs and pods throttle if a CPU limit is set (easyTrade HighCpuUsage).' },
  { name: 'inventory_pool_exhaustion', group: 'Postgres', service: 'inventory', label: 'Connection pool exhaustion', description: 'inventory holds DB connections too long; the pool fills and new requests queue then fail.' },
  { name: 'inventory_slow_query', group: 'Postgres', service: 'inventory', label: 'Slow / long-running query', description: 'inventory runs a sequential-scan query with an artificial sleep against Postgres.' },
  { name: 'store_failed_login_flood', group: 'Store VM / SIEM', service: 'store-agent', store: true, label: 'Failed-login flood', description: 'Chosen store emits a burst of failed SSH login log lines (synthetic).' },
  { name: 'store_file_integrity_alert', group: 'Store VM / SIEM', service: 'store-agent', store: true, label: 'File-integrity alert', description: 'Chosen store emits synthetic audit events for edits to watched config files.' },
  { name: 'impossible_travel', group: 'Store VM / SIEM', service: 'store-agent', label: 'Impossible travel', description: 'Same account buys in a US store, then orders from London minutes later.' },
];
const PATTERN_NAMES = new Set(PATTERNS.map((p) => p.name));

function log(level, msg, fields = {}) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), level, service: 'storefront', msg, ...fields }));
}

// ---------------------------------------------------------------- Redis + flag cache
const redis = createClient({ url: REDIS_URL, socket: { reconnectStrategy: (n) => Math.min(n * 200, 2000) } });
redis.on('error', (e) => log('WARN', 'redis error', { error: String(e.message || e) }));
let flags = {};

async function refreshFlags() {
  try {
    const raw = await redis.hGetAll('tc:flags');
    const next = {};
    for (const [k, v] of Object.entries(raw)) next[k] = JSON.parse(v);
    flags = next;
  } catch (e) { /* keep last known flags */ }
}
function flagLevel(name) {
  const f = flags[name];
  return f && f.on ? Number(f.level || 1) : 0;
}

// ---------------------------------------------------------------- app
const app = express();
app.use(express.json());

// Pattern: storefront_high_cpu - burn CPU on every API request (admin excluded).
app.use((req, res, next) => {
  const level = flagLevel('storefront_high_cpu');
  if (level && req.path.startsWith('/api/') && !req.path.startsWith('/api/admin')) {
    const end = Date.now() + level * 60;
    while (Date.now() < end) Math.sqrt(Math.random() * 1e6);
  }
  next();
});

app.get('/healthz', (req, res) => res.json({ status: 'ok' }));

async function forward(req, res, base, suffix) {
  const opts = { method: req.method, headers: { 'content-type': 'application/json' }, signal: AbortSignal.timeout(20000) };
  if (!['GET', 'HEAD', 'DELETE'].includes(req.method)) opts.body = JSON.stringify(req.body || {});
  try {
    const r = await fetch(base + suffix, opts);
    res.status(r.status).type('application/json').send(await r.text());
  } catch (e) {
    log('ERROR', 'upstream request failed', { upstream: base, path: suffix, error: String(e.message || e) });
    res.status(502).json({ error: 'upstream unavailable' });
  }
}
app.all('/api/catalog/*', (req, res) => forward(req, res, URLS.catalog, req.originalUrl.replace('/api/catalog', '')));
app.all('/api/cart/*', (req, res) => forward(req, res, URLS.cart, req.originalUrl.replace('/api', '')));
app.post('/api/checkout', (req, res) => forward(req, res, URLS.cart, '/checkout'));
app.get('/api/orders/*', (req, res) => forward(req, res, URLS.cart, req.originalUrl.replace('/api', '')));
app.post('/api/stock/restock', (req, res) => forward(req, res, URLS.inventory, '/restock')); // used by store POS agents
app.get('/api/stock/*', (req, res) => forward(req, res, URLS.inventory, req.originalUrl.replace('/api', '')));

let statsCache = { t: 0, v: { cars_sold: 0, orders: 0 } };
app.get('/api/stats', async (req, res) => {
  if (Date.now() - statsCache.t > 10000) {
    try {
      const r = await fetch(URLS.cart + '/orders/stats', { signal: AbortSignal.timeout(5000) });
      if (r.ok) statsCache = { t: Date.now(), v: await r.json() };
    } catch (e) { /* serve stale */ }
  }
  res.json(statsCache.v);
});

// ---------------------------------------------------------------- admin API
function auth(req, res, next) {
  if (req.get('x-admin-token') !== ADMIN_TOKEN) return res.status(401).json({ error: 'unauthorized' });
  next();
}
async function readLoad() {
  const h = await redis.hGetAll('tc:load');
  return { running: h.running === '1', rpm: Number(h.rpm || 0), web_pct: Number(h.web_pct || 70) };
}
async function pushEvent(evt) {
  const e = { ts: new Date().toISOString(), ...evt };
  log('INFO', evt.event, { ...evt });
  try {
    await redis.lPush('tc:events', JSON.stringify(e));
    await redis.lTrim('tc:events', 0, 49);
  } catch (err) { /* non-fatal */ }
}
async function ping(base) {
  try { return (await fetch(base + '/healthz', { signal: AbortSignal.timeout(1000) })).ok; } catch (e) { return false; }
}

app.get('/api/admin/flags', auth, async (req, res) => {
  await refreshFlags();
  res.json({ flags, load: await readLoad() });
});

app.get('/api/admin/state', auth, async (req, res) => {
  await refreshFlags();
  const events = (await redis.lRange('tc:events', 0, 19)).map((s) => JSON.parse(s));
  const [catalog, cart, inventory] = await Promise.all([ping(URLS.catalog), ping(URLS.cart), ping(URLS.inventory)]);
  res.json({ patterns: PATTERNS, flags, load: await readLoad(), events, health: { catalog, 'cart-checkout': cart, inventory, storefront: true }, stores: STORES });
});

app.put('/api/admin/flags/:name', auth, async (req, res) => {
  const name = req.params.name;
  if (!PATTERN_NAMES.has(name)) return res.status(404).json({ error: 'unknown pattern' });
  const def = PATTERNS.find((p) => p.name === name);
  const on = !!req.body.on;
  const level = Math.max(1, Math.min(5, Number(req.body.level || 2)));
  const value = { on, level, updated: new Date().toISOString() };
  if (def.store) value.store = STORES.includes(req.body.store) ? req.body.store : 'boston';
  await redis.hSet('tc:flags', name, JSON.stringify(value));
  flags[name] = value;
  await pushEvent({ event: on ? 'PATTERN_ENABLED' : 'PATTERN_DISABLED', pattern: name, level, store: value.store || null });
  res.json({ name, ...value });
});

app.put('/api/admin/load', auth, async (req, res) => {
  const b = req.body || {};
  const next = {};
  if (b.running !== undefined) next.running = b.running ? '1' : '0';
  if (b.rpm !== undefined) next.rpm = String(Math.max(0, Math.min(600, Number(b.rpm) || 0)));
  if (b.web_pct !== undefined) next.web_pct = String(Math.max(0, Math.min(100, Number(b.web_pct) || 0)));
  if (Object.keys(next).length) await redis.hSet('tc:load', next);
  const load = await readLoad();
  await pushEvent({ event: 'LOAD_CHANGED', ...load });
  res.json(load);
});

app.post('/api/admin/reset', auth, async (req, res) => {
  await redis.del('tc:flags');
  flags = {};
  await pushEvent({ event: 'PATTERNS_RESET' });
  res.json({ reset: true });
});

// ---------------------------------------------------------------- static UI
app.get('/admin', (req, res) => res.sendFile(path.join(__dirname, 'public', 'admin.html')));
app.use(express.static(path.join(__dirname, 'public')));

(async () => {
  app.listen(PORT, '0.0.0.0', () => log('INFO', 'storefront started', { port: PORT }));
  await redis.connect();
  await redis.hSetNX('tc:load', 'running', '1');
  await redis.hSetNX('tc:load', 'rpm', '20');
  await redis.hSetNX('tc:load', 'web_pct', '70');
  await refreshFlags();
  setInterval(refreshFlags, 2000);
})();
