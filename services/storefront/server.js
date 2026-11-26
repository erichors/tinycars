'use strict';
// TinyCars storefront (Node.js / Express, CommonJS).
// Plain app code: no telemetry imports. Tracing comes from OneAgent injection.
// Serves the UI, proxies /api/* to backend services, and hosts the hidden admin API.
// Problem-pattern + load state lives in Redis (tc:flags, tc:load).
const crypto = require('crypto');
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
const RANDOM_DAY_KEY = 'tc:random-day';
const RANDOM_DAY_LOCK_KEY = 'tc:random-day:lock';
const RANDOM_DAY_MS = 24 * 60 * 60 * 1000;

// Source of truth for the admin panel and for what services/agents react to.
const PATTERNS = [
  { name: 'inventory_db_not_responding', group: 'App', service: 'inventory', label: 'Inventory DB not responding', description: 'inventory throws database errors; stock cannot be reserved or restocked (easyTrade DbNotResponding).' },
  { name: 'catalog_search_slowdown', group: 'App', service: 'catalog', label: 'Catalog search slowdown', description: 'Search slows down, then starts timing out under load (easyTrade ErgoAggregatorSlowdown).' },
  { name: 'checkout_dependency_stall', group: 'App', service: 'cart-checkout', label: 'Checkout payment stall', description: 'Payment processor stops responding; checkouts hang then time out (easyTrade FactoryCrisis).' },
  { name: 'storefront_high_cpu', group: 'App', service: 'storefront', label: 'Storefront high CPU', description: 'Storefront burns CPU per request; latency climbs and pods throttle if a CPU limit is set (easyTrade HighCpuUsage).' },
  { name: 'inventory_pool_exhaustion', group: 'Postgres', service: 'inventory', label: 'Connection pool exhaustion', description: 'inventory holds DB connections too long; the pool fills and new requests queue then fail.' },
  { name: 'inventory_slow_query', group: 'Postgres', service: 'inventory', label: 'Slow / long-running query', description: 'inventory runs a sequential-scan query with an artificial sleep against Postgres.' },
  { name: 'ai_matcher_slowdown', group: 'AI', service: 'catalog', label: 'AI matcher slowdown / throttling', description: '"Find my car" model calls slow down (0.8 s x level); from level 3 they are throttled and the keyword fallback answers.' },
  { name: 'ai_hallucination', group: 'AI', service: 'catalog', label: 'AI hallucinated product', description: 'Poisons the model context with a phantom TC-999 product. The authoritative catalog allowlist blocks it and serves a safe fallback.' },
  { name: 'ai_prompt_guardrail', group: 'AI', service: 'catalog', label: 'AI prompt-attack guardrail', description: 'Adds a synthetic prompt-injection attempt. Amazon Bedrock Guardrails blocks it and TinyCars serves a safe fallback.' },
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
// ---------------------------------------------------------------- shopper accounts (demo logins)
// Sessions live in Redis (tc:sess:<token>). Browsers get an HttpOnly cookie; scripts (loadgen) may send x-tc-session.
const SESSION_TTL = 7 * 24 * 3600;
function sessionToken(req) {
  if (req.get('x-tc-session')) return req.get('x-tc-session');
  const m = /(?:^|;\s*)tc_sess=([^;]+)/.exec(req.get('cookie') || '');
  return m ? decodeURIComponent(m[1]) : null;
}
async function currentUser(req) {
  const t = sessionToken(req);
  if (!t) return null;
  try { const v = await redis.get('tc:sess:' + t); return v ? JSON.parse(v) : null; } catch (e) { return null; }
}
app.post('/api/auth/login', async (req, res) => {
  const { email, password, remember = true } = req.body || {};
  try {
    const r = await fetch(URLS.catalog + '/customers/login', {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-forwarded-for': req.get('x-forwarded-for') || req.ip },
      body: JSON.stringify({ email, password }), signal: AbortSignal.timeout(5000),
    });
    if (r.status === 401) { log('WARN', 'shopper login failed', { user: String(email || '').toLowerCase(), client_ip: req.ip }); return res.status(401).json({ error: 'Wrong email or password' }); }
    if (!r.ok) return res.status(502).json({ error: 'login unavailable' });
    const user = await r.json();
    const token = crypto.randomUUID();
    await redis.setEx('tc:sess:' + token, SESSION_TTL, JSON.stringify(user));
    if (remember) res.setHeader('Set-Cookie', `tc_sess=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_TTL}`);
    log('INFO', 'shopper login', { user: user.email });
    res.json({ user, token: remember ? undefined : token });
  } catch (e) {
    log('ERROR', 'login failed upstream', { error: String(e.message || e) });
    res.status(502).json({ error: 'login unavailable' });
  }
});
app.get('/api/auth/me', async (req, res) => res.json({ user: await currentUser(req) }));
app.post('/api/auth/logout', async (req, res) => {
  const t = sessionToken(req);
  if (t) { try { await redis.del('tc:sess:' + t); } catch (e) { /* ignore */ } }
  res.setHeader('Set-Cookie', 'tc_sess=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0');
  res.json({ user: null });
});
app.get('/api/account/orders', async (req, res) => {
  const user = await currentUser(req);
  if (!user) return res.status(401).json({ error: 'sign in to see your orders' });
  forward(req, res, URLS.catalog, '/customers/' + encodeURIComponent(user.email) + '/orders');
});
// Signed-in shoppers check out under their account email so the order lands in their history.
app.post('/api/checkout', async (req, res) => {
  const user = await currentUser(req);
  if (user) req.body = { ...(req.body || {}), email: user.email };
  forward(req, res, URLS.cart, '/checkout');
});
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
  const logFields = { ...evt };
  // Preserve the logging severity field; pattern intensity has its own semantic name.
  if (logFields.level !== undefined) {
    logFields.pattern_level = logFields.level;
    delete logFields.level;
  }
  log('INFO', evt.event, logFields);
  try {
    await redis.lPush('tc:events', JSON.stringify(e));
    await redis.lTrim('tc:events', 0, 49);
  } catch (err) { /* non-fatal */ }
}

async function setPatternFlag(name, on, level = 2, store, source = 'manual') {
  const def = PATTERNS.find((p) => p.name === name);
  if (!def) throw new Error(`unknown pattern ${name}`);
  const safeLevel = Math.max(1, Math.min(5, Number(level) || 2));
  const value = { on: !!on, level: safeLevel, updated: new Date().toISOString() };
  if (def.store) value.store = STORES.includes(store) ? store : 'boston';
  await redis.hSet('tc:flags', name, JSON.stringify(value));
  flags[name] = value;
  await pushEvent({ event: on ? 'PATTERN_ENABLED' : 'PATTERN_DISABLED', pattern: name,
    level: safeLevel, store: value.store || null, source });
  return { name, ...value };
}

function shuffled(items) {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = crypto.randomInt(0, i + 1);
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function createRandomDay() {
  const started = Date.now();
  const ends = started + RANDOM_DAY_MS;
  const ordered = shuffled(PATTERNS);
  const slot = RANDOM_DAY_MS / ordered.length;
  const events = [];
  ordered.forEach((pattern, index) => {
    // Start promptly, then distribute every pattern across its own randomized time slot.
    const at = index === 0 ? started + 3000 : started + Math.floor(index * slot + crypto.randomInt(0, Math.max(2, Math.floor(slot * 0.45))));
    const duration = crypto.randomInt(15, 46) * 60 * 1000;
    const offAt = Math.min(at + duration, ends - 1000);
    const level = crypto.randomInt(1, 6);
    const store = pattern.store ? STORES[crypto.randomInt(0, STORES.length)] : null;
    events.push({ at, action: 'enable', pattern: pattern.name, level, store });
    events.push({ at: offAt, action: 'disable', pattern: pattern.name, level, store });
  });
  events.sort((a, b) => a.at - b.at || a.action.localeCompare(b.action));
  return { id: crypto.randomUUID(), running: true, startedAt: new Date(started).toISOString(),
    endsAt: new Date(ends).toISOString(), cursor: 0, events };
}

async function readRandomDay() {
  const raw = await redis.get(RANDOM_DAY_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (e) { return null; }
}

function randomDayStatus(day) {
  if (!day) return { running: false, completed: 0, total: 0, next: null };
  const next = day.running && day.events[day.cursor] ? day.events[day.cursor] : null;
  return { id: day.id, running: !!day.running, startedAt: day.startedAt, endsAt: day.endsAt,
    stoppedAt: day.stoppedAt || null, completed: day.cursor || 0, total: day.events.length,
    next: next ? { ...next, at: new Date(next.at).toISOString() } : null };
}

async function processRandomDay() {
  const owner = crypto.randomUUID();
  if (!(await redis.set(RANDOM_DAY_LOCK_KEY, owner, { NX: true, PX: 15000 }))) return;
  try {
    const day = await readRandomDay();
    if (!day || !day.running) return;
    const now = Date.now();
    while (day.cursor < day.events.length && day.events[day.cursor].at <= now) {
      const evt = day.events[day.cursor];
      await setPatternFlag(evt.pattern, evt.action === 'enable', evt.level, evt.store, 'random_day');
      day.cursor += 1;
    }
    if (now >= Date.parse(day.endsAt) || day.cursor >= day.events.length) {
      day.running = false;
      day.stoppedAt = new Date().toISOString();
      await redis.del('tc:flags');
      flags = {};
      await pushEvent({ event: 'RANDOM_DAY_COMPLETED', schedule_id: day.id });
    }
    await redis.set(RANDOM_DAY_KEY, JSON.stringify(day));
  } finally {
    // Only release our own lease; a slow worker must not delete a successor's lock.
    await redis.eval('if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end',
      { keys: [RANDOM_DAY_LOCK_KEY], arguments: [owner] });
  }
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
  res.json({ patterns: PATTERNS, flags, load: await readLoad(), randomDay: randomDayStatus(await readRandomDay()),
    events, health: { catalog, 'cart-checkout': cart, inventory, storefront: true }, stores: STORES });
});

app.put('/api/admin/flags/:name', auth, async (req, res) => {
  const name = req.params.name;
  if (!PATTERN_NAMES.has(name)) return res.status(404).json({ error: 'unknown pattern' });
  const on = !!req.body.on;
  const level = Math.max(1, Math.min(5, Number(req.body.level || 2)));
  res.json(await setPatternFlag(name, on, level, req.body.store));
});

app.post('/api/admin/random-day/start', auth, async (req, res) => {
  const day = createRandomDay();
  await redis.del('tc:flags');
  flags = {};
  await redis.set(RANDOM_DAY_KEY, JSON.stringify(day));
  await pushEvent({ event: 'RANDOM_DAY_STARTED', schedule_id: day.id, ends_at: day.endsAt, patterns: PATTERNS.length });
  res.json(randomDayStatus(day));
});

app.post('/api/admin/random-day/stop', auth, async (req, res) => {
  const day = await readRandomDay();
  if (day) {
    day.running = false;
    day.stoppedAt = new Date().toISOString();
    await redis.set(RANDOM_DAY_KEY, JSON.stringify(day));
  }
  await redis.del('tc:flags');
  flags = {};
  await pushEvent({ event: 'RANDOM_DAY_STOPPED', schedule_id: day ? day.id : null });
  res.json(randomDayStatus(day));
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
  const day = await readRandomDay();
  if (day && day.running) {
    day.running = false;
    day.stoppedAt = new Date().toISOString();
    await redis.set(RANDOM_DAY_KEY, JSON.stringify(day));
  }
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
  await processRandomDay();
  setInterval(() => processRandomDay().catch((e) => log('WARN', 'random-day scheduler failed', { error: String(e.message || e) })), 10000);
})();
