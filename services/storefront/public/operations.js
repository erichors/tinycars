'use strict';

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const locations = ['warehouse', 'boston', 'chicago', 'london'];
const siteTimezones = { warehouse: 'UTC', boston: 'America/New_York', chicago: 'America/Chicago', london: 'Europe/London' };
const state = { token: sessionStorage.getItem('tc_admin') || '', summary: {}, products: [], stock: [], movements: [], purchaseOrders: [], orders: [], orderResults: null, returnOrder: null, shipments: [], returns: [] };
const titles = {
  overview: ['Good morning, garage.', 'Keep orders moving and shelves stocked.'],
  inventory: ['Know what is on every shelf.', 'Four locations. One accurate view of stock.'],
  purchasing: ['Keep supply moving.', 'Place orders, then receive units where they are needed.'],
  orders: ['From checkout to doorstep.', 'Track every paid purchase through fulfillment.'],
  returns: ['Make the return journey clear.', 'Record what came back and where it went.'],
};

function notify(message, error = false) {
  const box = $('#notice');
  box.textContent = message;
  box.classList.toggle('error', error);
  box.classList.remove('hidden');
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => box.classList.add('hidden'), 7000);
}

function gate(message = '') {
  $('#gate').classList.remove('hidden');
  $('#shell').classList.add('hidden');
  $('#gate-message').textContent = message;
}

async function api(path, method = 'GET', body) {
  const response = await fetch('/api/admin/ops' + path, {
    method,
    headers: { 'x-admin-token': state.token, 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (response.status === 401) {
    sessionStorage.removeItem('tc_admin');
    state.token = '';
    gate('The admin token is invalid or has expired.');
    throw new Error('Unauthorized');
  }
  if (!response.ok) throw new Error(data.detail || data.error || `Request failed (${response.status})`);
  return data;
}

function date(value, location) {
  return value ? new Intl.DateTimeFormat('en-US', {
    timeZone: siteTimezones[location] || 'UTC', month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  }).format(new Date(value)) : '—';
}

function renderStoreClocks() {
  const now = new Date();
  $('#store-clocks').innerHTML = locations.filter((location) => location !== 'warehouse').map((location) => {
    const timeZone = siteTimezones[location];
    const parts = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short' }).formatToParts(now);
    const part = (type) => parts.find((item) => item.type === type)?.value || '';
    const hour = Number(part('hour'));
    const isOpen = hour >= 10 && hour < 20;
    const name = location[0].toUpperCase() + location.slice(1);
    return `<div class="store-clock"><span class="store-clock-name">${name}</span><strong>${part('hour')}:${part('minute')} <small>${part('timeZoneName')}</small></strong><span class="store-clock-status ${isOpen ? 'open' : ''}">${isOpen ? 'Open · 10:00–20:00' : 'After hours · 10:00–20:00'}</span></div>`;
  }).join('');
}
function money(value, currency = 'USD') { return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0)); }
function badge(value) { return `<span class="badge ${escapeHtml(value || '')}">${escapeHtml(value || 'unshipped')}</span>`; }
function empty(message) { return `<div class="empty">${escapeHtml(message)}</div>`; }

function switchTab(name) {
  if (!titles[name]) return;
  document.querySelectorAll('[data-tab]').forEach((button) => button.classList.toggle('active', button.dataset.tab === name));
  document.querySelectorAll('.view').forEach((view) => view.classList.toggle('active', view.id === name));
  $('#section-name').textContent = name === 'purchasing' ? 'Buying' : name === 'orders' ? 'Orders & shipping' : name[0].toUpperCase() + name.slice(1);
  $('#page-title').textContent = titles[name][0];
  $('#page-subtitle').textContent = titles[name][1];
  window.location.hash = name;
}

function productOptions() { return state.products.map((p) => `<option value="${escapeHtml(p.sku)}">${escapeHtml(p.sku)} · ${escapeHtml(p.name)}</option>`).join(''); }
function locationOptions(selected) { return locations.map((location) => `<option value="${location}" ${location === selected ? 'selected' : ''}>${location[0].toUpperCase() + location.slice(1)}</option>`).join(''); }

function fillSelectors() {
  document.querySelectorAll('select[data-products]').forEach((select) => {
    const selected = select.value;
    select.innerHTML = productOptions();
    if (selected) select.value = selected;
  });
  document.querySelectorAll('select[data-locations]').forEach((select) => {
    const selected = select.value;
    select.innerHTML = locationOptions();
    if (selected) select.value = selected;
  });
}

function renderOverview() {
  const s = state.summary;
  const tiles = [
    ['Low stock cells', s.low_stock, true],
    ['Awaiting shipping', s.awaiting_shipping, true],
    ['Open purchase orders', s.open_purchase_orders],
    ['Return requests', s.open_returns],
    ['Sales, last 30 days', [money(s.sales_30d_usd, 'USD'), money(s.sales_30d_gbp, 'GBP')]],
  ];
  $('#kpis').innerHTML = tiles.map(([label, value, warn]) => `<div class="kpi ${warn && value ? 'warn' : ''}"><span>${escapeHtml(label)}</span><b class="${Array.isArray(value) ? 'multi' : ''}">${Array.isArray(value) ? value.map(escapeHtml).join('<br>') : escapeHtml(value ?? 0)}</b></div>`).join('');
  $('#overview-stock').innerHTML = state.stock.filter((r) => r.qty < 8).slice(0, 7).map((r) => `<div class="small-row"><span><b>${escapeHtml(r.name)}</b><br><small>${escapeHtml(r.sku)} · ${escapeHtml(r.location)}</small></span><span class="qty low">${r.qty}</span></div>`).join('') || empty('No low stock right now.');
  $('#overview-orders').innerHTML = state.orders.slice(0, 7).map((o) => `<div class="small-row"><span><b>${escapeHtml(o.order_id)}</b><br><small>${escapeHtml(o.customer_email)} · ${escapeHtml(o.location)} · ${date(o.created_at, o.location)}</small></span><span>${money(o.total, o.currency)}</span></div>`).join('') || empty('No orders yet.');
  $('#overview-movements').innerHTML = state.movements.slice(0, 10).map((m) => `<div class="small-row"><span><b>${escapeHtml(m.sku)}</b> · ${escapeHtml(m.kind)}<br><small>${escapeHtml(m.location)} · ${escapeHtml(m.reference)} · ${date(m.created_at, m.location)}</small></span><span class="${m.delta < 0 ? 'muted' : ''}">${m.delta > 0 ? '+' : ''}${m.delta}</span></div>`).join('') || empty('Operations stock movements will appear here.');
}

function renderStock() {
  const location = $('#stock-location').value;
  const low = $('#stock-low').checked;
  const records = state.stock.filter((row) => (!location || row.location === location) && (!low || row.qty < 8));
  $('#stock-rows').innerHTML = records.map((r) => `<tr><td><strong>${escapeHtml(r.name)}</strong><br><span class="muted">${escapeHtml(r.category)}</span></td><td>${escapeHtml(r.sku)}</td><td>${escapeHtml(r.location)}</td><td><span class="qty ${r.qty < 8 ? 'low' : ''}">${r.qty}</span></td><td class="muted">${date(r.updated_at, r.location)}</td></tr>`).join('') || `<tr><td colspan="5">${empty('No matching stock.')}</td></tr>`;
}

function renderPurchaseOrders() {
  $('#purchase-orders').innerHTML = state.purchaseOrders.map((po) => {
    const lines = po.items.map((item) => {
      const remaining = item.qty - item.received_qty;
      return `<div class="record-lines">${escapeHtml(item.sku)} · ${escapeHtml(item.name)} — ${item.received_qty}/${item.qty} received · ${money(item.unit_cost)} each
        ${remaining ? `<input class="inline-qty" type="number" min="0" max="${remaining}" value="${remaining}" data-po-sku="${escapeHtml(item.sku)}" aria-label="Units to receive for ${escapeHtml(item.sku)}">` : ''}</div>`;
    }).join('');
    return `<div class="record" data-po="${escapeHtml(po.po_id)}"><div class="record-head"><div><h3>${escapeHtml(po.po_id)} · ${escapeHtml(po.supplier)}</h3><p>${escapeHtml(po.destination)} · ${date(po.created_at, po.destination)}${po.received_at ? ` · received ${date(po.received_at, po.destination)}` : ''}</p></div>${badge(po.status)}</div>${lines}
      ${po.status !== 'received' ? `<div class="record-actions"><button class="secondary" data-action="receive-po" data-id="${escapeHtml(po.po_id)}">Receive selected units</button></div>` : ''}</div>`;
  }).join('') || empty('No purchase orders yet.');
}

function renderOrders() {
  const query = $('#order-search').value.toLowerCase();
  const orders = (state.orderResults || state.orders).filter((o) => [o.order_id, o.customer_email, o.location].some((v) => String(v).toLowerCase().includes(query)));
  $('#orders-list').innerHTML = orders.map((o) => {
    const items = o.items.map((item) => `${escapeHtml(item.qty)} × ${escapeHtml(item.name)}`).join(' · ') || 'No items';
    const canShip = o.channel === 'web' && o.status === 'completed' && o.payment_status === 'approved' && !o.shipment_id;
    return `<div class="record" data-order="${escapeHtml(o.order_id)}"><div class="record-head"><div><h3>${escapeHtml(o.order_id)} · ${money(o.total, o.currency)}</h3><p>${escapeHtml(o.customer_email)} · ${escapeHtml(o.location)} · ${date(o.created_at, o.location)}</p></div>${badge(o.shipment_id ? o.shipping_status : o.status)}</div><div class="record-lines">${items}</div>
      <p>${escapeHtml(o.channel)} · payment ${escapeHtml(o.payment_status)}${o.tracking_number ? ` · ${escapeHtml(o.carrier)} ${escapeHtml(o.tracking_number)}` : ''}</p>
      ${canShip ? `<div class="record-actions"><select data-carrier aria-label="Carrier"><option>TinyCars Parcel</option><option>Demo Express</option><option>Store courier</option></select><input data-tracking placeholder="Tracking (optional)" aria-label="Tracking number"><button class="secondary" data-action="ship" data-id="${escapeHtml(o.order_id)}">Create shipment</button></div>` : ''}</div>`;
  }).join('') || empty('No matching orders.');
  $('#shipments-list').innerHTML = state.shipments.map((s) => `<div class="record"><div class="record-head"><div><h3>${escapeHtml(s.shipment_id)} · ${escapeHtml(s.order_id)}</h3><p>${escapeHtml(s.carrier)} · ${escapeHtml(s.tracking_number)} · ${escapeHtml(s.location)} · shipped ${date(s.shipped_at, s.location)}</p></div>${badge(s.status)}</div><p>${escapeHtml(s.customer_email)}${s.delivered_at ? ` · delivered ${date(s.delivered_at, s.location)}` : ''}</p>${s.status === 'shipped' ? `<div class="record-actions"><button class="secondary" data-action="deliver" data-id="${escapeHtml(s.shipment_id)}">Mark delivered</button></div>` : ''}</div>`).join('') || empty('No shipments recorded yet.');
}

function fillReturnItems() {
  const order = state.returnOrder && state.returnOrder.order_id === $('#return-order').value ? state.returnOrder : state.orders.find((o) => o.order_id === $('#return-order').value);
  $('#return-sku').innerHTML = order ? order.items.map((item) => `<option value="${escapeHtml(item.sku)}">${escapeHtml(item.sku)} · ${escapeHtml(item.name)} (${item.qty} bought)</option>`).join('') : '';
}

function renderReturns() {
  const eligible = state.orders.filter((o) => o.status === 'completed' && o.payment_status === 'approved' && o.items.length);
  $('#recent-return-orders').innerHTML = eligible.map((o) => `<option value="${escapeHtml(o.order_id)}">${escapeHtml(o.customer_email)}</option>`).join('');
  fillReturnItems();
  $('#returns-list').innerHTML = state.returns.map((r) => `<div class="record" data-return="${escapeHtml(r.return_id)}"><div class="record-head"><div><h3>${escapeHtml(r.return_id)} · ${escapeHtml(r.name)}</h3><p>${escapeHtml(r.order_id)} · ${escapeHtml(r.customer_email)} · ${r.qty} units · ${escapeHtml(r.location)} · requested ${date(r.requested_at, r.location)}</p></div>${badge(r.status)}</div><p>${escapeHtml(r.reason)} · refund ${money(r.refund_amount, r.currency)} (${escapeHtml(r.refund_status)})</p>${r.received_at ? `<p>Received ${date(r.received_at, r.restock_location || r.location)}</p>` : ''}${r.restock_location ? `<p>Restocked at ${escapeHtml(r.restock_location)}</p>` : ''}
    ${r.status === 'requested' ? `<div class="record-actions"><label><input type="checkbox" data-restock checked> Restock</label><select data-return-location aria-label="Restock location">${locationOptions(r.location === 'warehouse' ? 'warehouse' : r.location)}</select><button class="secondary" data-action="receive-return" data-id="${escapeHtml(r.return_id)}">Receive & record refund</button><button class="secondary danger" data-action="reject-return" data-id="${escapeHtml(r.return_id)}">Reject</button></div>` : ''}</div>`).join('') || empty('No returns yet.');
}

function renderAll() {
  renderOverview(); renderStock(); renderPurchaseOrders(); renderOrders(); renderReturns();
  renderStoreClocks();
  $('#updated').textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

async function refresh() {
  const paths = ['/summary', '/products', '/stock', '/movements', '/purchase-orders', '/orders?limit=200', '/shipments', '/returns'];
  const values = await Promise.all(paths.map((path) => api(path)));
  [state.summary, state.products, state.stock, state.movements, state.purchaseOrders, state.orders, state.shipments, state.returns] = values;
  const search = $('#order-search').value.trim();
  state.orderResults = search ? await api('/orders?limit=200&search=' + encodeURIComponent(search)) : null;
  fillSelectors(); renderAll();
}

function addPoLine() {
  const row = document.createElement('div');
  row.className = 'po-line';
  row.innerHTML = `<label>Product<select name="sku" data-products required>${productOptions()}</select></label><label>Units<input name="qty" type="number" min="1" max="10000" value="10" required></label><label>Unit cost<input name="unit_cost" type="number" min="0" step="0.01" value="4.00" required></label><button class="secondary" type="button" data-action="remove-line" aria-label="Remove line">×</button>`;
  $('#po-lines').append(row);
}

async function mutate(path, body, success) {
  try {
    await api(path, 'POST', body);
    notify(success);
    await refresh();
  } catch (error) { if (state.token) notify(error.message, true); }
}

document.addEventListener('click', async (event) => {
  const tab = event.target.closest('[data-tab]');
  if (tab) switchTab(tab.dataset.tab);
  const action = event.target.closest('[data-action]');
  if (action) {
    const { id } = action.dataset;
    if (action.dataset.action === 'remove-line') { if ($('#po-lines').children.length > 1) action.closest('.po-line').remove(); }
    if (action.dataset.action === 'receive-po') {
      const record = action.closest('[data-po]');
      const items = [...record.querySelectorAll('[data-po-sku]')].map((input) => ({ sku: input.dataset.poSku, qty: Number(input.value) })).filter((item) => item.qty > 0);
      await mutate(`/purchase-orders/${encodeURIComponent(id)}/receive`, { items }, `Received stock for ${id}.`);
    }
    if (action.dataset.action === 'ship') {
      const record = action.closest('[data-order]');
      await mutate('/shipments', { order_id: id, carrier: record.querySelector('[data-carrier]').value, tracking_number: record.querySelector('[data-tracking]').value || null }, `Shipment created for ${id}.`);
    }
    if (action.dataset.action === 'deliver') await mutate(`/shipments/${encodeURIComponent(id)}/deliver`, {}, `Shipment ${id} delivered.`);
    if (action.dataset.action === 'receive-return') {
      const record = action.closest('[data-return]');
      await mutate(`/returns/${encodeURIComponent(id)}/receive`, { restock: record.querySelector('[data-restock]').checked, location: record.querySelector('[data-return-location]').value }, `Return ${id} received.`);
    }
    if (action.dataset.action === 'reject-return') await mutate(`/returns/${encodeURIComponent(id)}/reject`, {}, `Return ${id} rejected.`);
  }
  if (event.target.id === 'add-po-line') addPoLine();
  if (event.target.id === 'create-reorder') {
    const site = $('#stock-location').value;
    const target = Number($('#reorder-target').value);
    if (!site) return notify('Choose a location before creating a replenishment order.', true);
    if (!Number.isInteger(target) || target < 8 || target > 1000) return notify('Choose a target from 8 to 1000 units.', true);
    const items = state.stock.filter((row) => row.location === site && row.qty < 8).map((row) => {
      const product = state.products.find((p) => p.sku === row.sku);
      return { sku: row.sku, qty: target - row.qty, unit_cost: (Math.round(Number(product.price_usd) * 60) / 100).toFixed(2) };
    });
    if (!items.length) return notify(`No low stock items at ${site}.`);
    try {
      const order = await api('/purchase-orders', 'POST', { supplier: 'TinyCars Distribution', destination: site, items });
      await refresh(); switchTab('purchasing');
      notify(`Created ${order.po_id} with ${items.length} products for ${site}. Receive it when stock arrives.`);
    } catch (error) { notify(error.message, true); }
  }
  if (event.target.id === 'refresh') { try { await refresh(); notify('Operations refreshed.'); } catch (error) { notify(error.message, true); } }
  if (event.target.id === 'lock') { sessionStorage.removeItem('tc_admin'); state.token = ''; gate(); }
});

document.addEventListener('change', (event) => {
  if (['stock-location', 'stock-low'].includes(event.target.id)) renderStock();
  if (event.target.id === 'return-order') {
    const id = event.target.value.trim();
    if (!id) { state.returnOrder = null; fillReturnItems(); return; }
    api('/orders/' + encodeURIComponent(id)).then((order) => { state.returnOrder = order; fillReturnItems(); })
      .catch((error) => { state.returnOrder = null; fillReturnItems(); notify(error.message, true); });
  }
});
let searchTimer;
$('#order-search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    const search = $('#order-search').value.trim();
    try { state.orderResults = search ? await api('/orders?limit=200&search=' + encodeURIComponent(search)) : null; renderOrders(); }
    catch (error) { notify(error.message, true); }
  }, 300);
});

document.addEventListener('submit', async (event) => {
  if (event.target.id === 'login-form') {
    event.preventDefault();
    state.token = $('#admin-token').value;
    try {
      await api('/summary');
      sessionStorage.setItem('tc_admin', state.token);
      $('#gate').classList.add('hidden'); $('#shell').classList.remove('hidden');
      await refresh();
    } catch (error) { gate(error.message); }
    return;
  }
  const form = event.target;
  if (!['adjust-form', 'transfer-form', 'purchase-form', 'return-form'].includes(form.id)) return;
  event.preventDefault();
  const values = Object.fromEntries(new FormData(form));
  if (form.id === 'adjust-form') { await mutate('/stock/adjust', { ...values, delta: Number(values.delta) }, 'Inventory adjusted.'); }
  if (form.id === 'transfer-form') { await mutate('/stock/transfer', { ...values, qty: Number(values.qty) }, 'Stock transferred.'); }
  if (form.id === 'purchase-form') {
    const items = [...$('#po-lines').children].map((line) => ({ sku: line.querySelector('[name=sku]').value, qty: Number(line.querySelector('[name=qty]').value), unit_cost: line.querySelector('[name=unit_cost]').value }));
    await mutate('/purchase-orders', { supplier: values.supplier, destination: values.destination, items }, 'Purchase order created.');
  }
  if (form.id === 'return-form') { await mutate('/returns', { ...values, qty: Number(values.qty) }, 'Return requested.'); }
});

addPoLine();
renderStoreClocks();
setInterval(renderStoreClocks, 30000);
if (state.token) {
  api('/summary').then(() => { $('#gate').classList.add('hidden'); $('#shell').classList.remove('hidden'); return refresh(); })
    .catch((error) => { if (state.token) gate(error.message); });
} else gate();
switchTab(titles[window.location.hash.slice(1)] ? window.location.hash.slice(1) : 'overview');
