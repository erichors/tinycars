'use strict';
// TinyCars storefront UI: vanilla JS single-page app, hash routing.
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const state = { products: [], cats: [], currency: localStorage.getItem('tc_cur') || 'USD' };
const cartId = localStorage.getItem('tc_cart') || (() => { const id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()); localStorage.setItem('tc_cart', id); return id; })();
const CAT_COLOR = {
  'Classics & Muscle': '#e8453c', 'Imports & Compacts': '#8a5bd6', 'Off-Roaders': '#4c9a2a', 'Pickups': '#e0902b',
  'Everyday & Emergency': '#1f9d93', 'Sports & Racing': '#3d7be0', 'Military & Army': '#6b7a3a', 'Construction': '#d9a400', 'Limited Edition': '#c9962b',
};
const LOC_NAME = { warehouse: 'Web warehouse', boston: 'Boston store', chicago: 'Chicago store', london: 'London store' };

async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { headers: { 'content-type': 'application/json' }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
  let data = null;
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) { const err = new Error((data && data.error) || `Request failed (${r.status})`); err.status = r.status; throw err; }
  return data;
}
const sym = (c) => (c === 'GBP' ? '£' : '$');
const price = (p) => sym(state.currency) + Number(state.currency === 'GBP' ? p.price_gbp : p.price_usd).toFixed(2);
const byName = (n) => state.products.find((p) => p.name === n);

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2200);
}

// ------------------------------------------------------------------ cards (blister packs)
function card(p) {
  const ltd = p.category === 'Limited Edition';
  const color = CAT_COLOR[p.category] || '#e8453c';
  return `<article class="card ${ltd ? 'ltd' : ''}" style="--c:${color}">
    <div class="hang"></div>
    ${p.new_arrival ? '<div class="ribbon">NEW</div>' : ''}
    <div class="cardhead"><span>TINYCARS</span><b>${esc((p.specs && p.specs.scale) || '1:64')}</b></div>
    <a class="bubble" href="#/p/${esc(p.sku)}" aria-label="View ${esc(p.name)}"><img loading="lazy" src="${esc(p.image)}" alt="${esc(p.name)}"><span class="glare"></span><span class="peek">View details</span></a>
    <div class="info"><span class="meta">${esc(p.era)} &middot; ${esc(p.category)}</span>
      <a class="name" href="#/p/${esc(p.sku)}">${esc(p.name)}</a>
      <div class="row"><span class="price">${price(p)}</span><button class="add" data-sku="${esc(p.sku)}">+ Garage</button></div>
    </div></article>`;
}

async function refreshCartCount() {
  try {
    const c = await api('/cart/' + cartId);
    $('#cartCount').textContent = (c.items || []).reduce((n, i) => n + Number(i.qty), 0);
    return c;
  } catch (e) { return null; }
}

async function addToCart(sku, qty = 1) {
  try {
    await api(`/cart/${cartId}/items`, { method: 'POST', body: { sku, qty, currency: state.currency } });
    toast(qty > 1 ? `Added ${qty} to your garage!` : 'Added to your garage!');
    refreshCartCount();
  } catch (e) { toast('Could not add: ' + e.message); }
}

function drawAisles(active) {
  $('#aisles').innerHTML = `<a href="#/" class="${!active ? 'on' : ''}">Home</a>` +
    state.cats.map((c) => `<a href="#/cat/${encodeURIComponent(c.name)}" class="${active === c.name ? 'on' : ''}" style="--c:${CAT_COLOR[c.name] || '#e8453c'};--onc:#fff">${esc(c.name)}</a>`).join('');
}

function odometer(n) {
  return `<div class="digits">${String(n).padStart(6, '0').split('').map((d) => `<b>${d}</b>`).join('')}</div>`;
}

// ------------------------------------------------------------------ pages
async function home() {
  drawAisles();
  const featured = byName('Cone Cruiser') || state.products[0];
  let stats = { cars_sold: 0 };
  try { stats = await api('/stats'); } catch (e) { /* ok */ }
  const rails = state.cats.map((c) => {
    const items = state.products.filter((p) => p.category === c.name).slice(0, 9);
    return `<h2 class="rail" style="--c:${CAT_COLOR[c.name] || '#e8453c'}">${esc(c.name)} <a href="#/cat/${encodeURIComponent(c.name)}">See all ${c.count} &rarr;</a></h2><div class="rail-row">${items.map(card).join('')}</div>`;
  }).join('');
  const fresh = state.products.filter((p) => p.new_arrival);
  $('#view').innerHTML = `
    <section class="hero"><div><h1>Pocket-sized legends.</h1><p>${state.products.length} diecast cars, trucks, tanks and diggers for the whole garage. New arrivals every week.</p>
      <a class="btn" href="#/cat/${encodeURIComponent('Classics & Muscle')}">Browse the aisle</a>
      <div class="odo" style="margin-top:20px;text-align:left"><small>Cars sold so far</small><span id="odo">${odometer(stats.cars_sold || 0)}</span></div></div>
      <a class="herocar" href="#/p/${esc(featured.sku)}"><img src="${esc(featured.image)}" alt="${esc(featured.name)}"><span>${esc(featured.name)} &rarr;</span></a></section>
    <h2 class="rail" style="--c:#e8453c">Just rolled in <span class="tag">NEW</span></h2><div class="rail-row">${fresh.map(card).join('')}</div>${rails}`;
}

function category(name) {
  drawAisles(name);
  const items = state.products.filter((p) => p.category === name);
  $('#view').innerHTML = `<h2 class="rail" style="--c:${CAT_COLOR[name] || '#e8453c'}">${esc(name)} <span class="tag">${items.length} cars</span></h2><div class="grid">${items.map(card).join('')}</div>`;
}

async function search(q) {
  drawAisles();
  $('#view').innerHTML = `<h2 class="rail">Searching for &ldquo;${esc(q)}&rdquo;&hellip;</h2>`;
  try {
    const items = await api('/catalog/search?q=' + encodeURIComponent(q));
    $('#view').innerHTML = `<h2 class="rail">${items.length} result${items.length === 1 ? '' : 's'} for &ldquo;${esc(q)}&rdquo;</h2><div class="grid">${items.map(card).join('')}</div>`;
  } catch (e) {
    $('#view').innerHTML = `<div class="empty">The shelf is jammed (${esc(e.message)}). Try again in a moment.</div>`;
  }
}

// ------------------------------------------------------------------ detail view
function specRows(p) {
  const s = p.specs || {};
  const rows = [['Type', s.class], ['Scale', s.scale], ['Length', s.length_in ? Number(s.length_in).toFixed(1) + ' in' : ''], ['Model year', s.model_year], ['Finish', s.finish],
    ['Wheels', s.wheels], ['Material', s.material], ['Rarity', s.rarity], ['Pack', s.pack], ['Edition', s.edition], ['SKU', p.sku]].filter((r) => r[1]);
  return rows.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('');
}

function openLightbox(p) {
  const lb = document.createElement('div');
  lb.className = 'lightbox';
  lb.innerHTML = `<button class="lbclose" aria-label="Close">&times;</button><div class="lbstage"><img src="${esc(p.image)}" alt="${esc(p.name)}"></div><div class="lbcap">${esc(p.name)} &middot; move the mouse to look around</div>`;
  const img = $('img', lb);
  lb.addEventListener('mousemove', (e) => {
    const r = lb.getBoundingClientRect();
    img.style.transformOrigin = `${((e.clientX - r.left) / r.width) * 100}% ${((e.clientY - r.top) / r.height) * 100}%`;
  });
  const close = () => { lb.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  lb.addEventListener('click', (e) => { if (e.target === lb || e.target.classList.contains('lbclose')) close(); });
  document.addEventListener('keydown', onKey);
  document.body.appendChild(lb);
}

async function product(sku) {
  drawAisles();
  const p = state.products.find((x) => x.sku === sku);
  if (!p) { $('#view').innerHTML = '<div class="empty">That car rolled off the shelf.</div>'; return; }
  const s = p.specs || {};
  const spots = s.hotspots || [];
  const same = state.products.filter((x) => x.category === p.category);
  const idx = same.findIndex((x) => x.sku === sku);
  const prev = same[(idx - 1 + same.length) % same.length], next = same[(idx + 1) % same.length];
  const related = same.filter((x) => x.sku !== sku).slice(0, 6);
  const color = CAT_COLOR[p.category] || '#e8453c';
  $('#view').innerHTML = `
    <div class="crumbs"><a href="#/">Home</a> &rsaquo; <a href="#/cat/${encodeURIComponent(p.category)}">${esc(p.category)}</a> &rsaquo; <b>${esc(p.name)}</b></div>
    <div class="detail" style="--c:${color}">
      <div>
        <div class="stage" id="stage">
          <div class="art" id="art"><img id="artImg" src="${esc(p.image)}" alt="${esc(p.name)}">
            ${spots.map((h, i) => `<button class="pin" data-i="${i}" style="left:${h.x}%;top:${h.y}%" aria-label="${esc(h.label)}"><span></span></button>`).join('')}
          </div>
          <button class="zoombtn" id="zoomBtn" aria-label="Full screen view">&#x2922; Full view</button>
          ${p.new_arrival ? '<div class="ribbon big">NEW</div>' : ''}
        </div>
        <div class="closeups" id="closeups">
          <button class="chip on" data-i="-1">Whole car</button>${spots.map((h, i) => `<button class="chip" data-i="${i}">${esc(h.label)}</button>`).join('')}
        </div>
        <div class="callout" id="callout">Tap a pin or a close-up to look closer. Move your mouse over the car to tilt it.</div>
        <div class="pager"><a href="#/p/${esc(prev.sku)}">&larr; ${esc(prev.name)}</a><a href="#/p/${esc(next.sku)}">${esc(next.name)} &rarr;</a></div>
      </div>
      <div>
        <span class="tag" style="background:${color}">${esc(p.category)}</span>
        <h1>${esc(p.name)}</h1>
        <p class="meta">${esc(p.era)} &middot; ${esc(s.class || '')}${s.edition ? ' &middot; ' + esc(s.edition) : ''}</p>
        <p class="lead">${esc(p.description)}</p>
        <div class="buy"><div class="price" style="font-size:36px">${price(p)}</div>
          <label class="qty">Qty <select id="qty">${[1, 2, 3, 4, 5, 6].map((n) => `<option>${n}</option>`).join('')}</select></label>
          <button class="btn" id="addBtn">Add to my garage</button></div>
        <div class="feats">${(s.features || []).map((f) => `<span>&#10003; ${esc(f)}</span>`).join('')}</div>
        <h3 class="sub">On the shelf</h3><div class="stock" id="stock">Checking shelves&hellip;</div>
        <h3 class="sub">Collector specs</h3><table class="specs">${specRows(p)}</table>
      </div>
    </div>
    <h2 class="rail" style="--c:${color}">More from ${esc(p.category)}</h2><div class="rail-row">${related.map(card).join('')}</div>`;

  // tilt + close-ups
  const stage = $('#stage'), art = $('#art'), callout = $('#callout');
  let zoomed = -1;
  const setZoom = (i) => {
    zoomed = i;
    document.querySelectorAll('#closeups .chip').forEach((c) => c.classList.toggle('on', Number(c.dataset.i) === i));
    if (i < 0) {
      art.style.setProperty('--z', 1); art.style.setProperty('--ox', '50%'); art.style.setProperty('--oy', '50%');
      callout.textContent = 'Tap a pin or a close-up to look closer. Move your mouse over the car to tilt it.';
    } else {
      const h = spots[i];
      art.style.setProperty('--z', 2.7); art.style.setProperty('--ox', h.x + '%'); art.style.setProperty('--oy', h.y + '%');
      callout.innerHTML = `<b>${esc(h.label)}.</b> ${esc(h.text)}`;
    }
    art.style.setProperty('--rx', '0deg'); art.style.setProperty('--ry', '0deg');
  };
  stage.addEventListener('mousemove', (e) => {
    if (zoomed >= 0) return;
    const r = stage.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
    art.style.setProperty('--ry', (px * 9).toFixed(2) + 'deg'); art.style.setProperty('--rx', (-py * 7).toFixed(2) + 'deg');
  });
  stage.addEventListener('mouseleave', () => { if (zoomed < 0) { art.style.setProperty('--rx', '0deg'); art.style.setProperty('--ry', '0deg'); } });
  document.querySelectorAll('.pin').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); setZoom(zoomed === Number(b.dataset.i) ? -1 : Number(b.dataset.i)); }));
  document.querySelectorAll('#closeups .chip').forEach((b) => b.addEventListener('click', () => setZoom(Number(b.dataset.i))));
  $('#zoomBtn').onclick = () => openLightbox(p);
  $('#artImg').addEventListener('dblclick', () => openLightbox(p));
  $('#addBtn').onclick = () => addToCart(sku, Number($('#qty').value));

  try {
    const rows = await api('/stock/' + sku);
    $('#stock').innerHTML = ['warehouse', 'boston', 'chicago', 'london'].map((loc) => {
      const r = rows.find((x) => x.location === loc); const q = r ? r.qty : 0;
      return `<div class="loc ${q === 0 ? 'out' : q < 6 ? 'low' : 'ok'}"><b>${q}</b><span>${esc(LOC_NAME[loc])}</span><i>${q === 0 ? 'Sold out' : q < 6 ? 'Low stock' : 'In stock'}</i></div>`;
    }).join('');
  } catch (e) {
    $('#stock').innerHTML = `<span class="low">Stock check unavailable (${esc(e.message)})</span>`;
  }
}

async function cartView() {
  drawAisles();
  const c = await refreshCartCount();
  const items = (c && c.items) || [];
  if (!items.length) {
    const pic = (byName('Bubble Bug') || state.products[0]).image;
    $('#view').innerHTML = `<div class="empty"><img src="${esc(pic)}" alt="">Your garage is empty.<br><a class="btn" href="#/">Go find some cars</a></div>`;
    return;
  }
  const cur = c.currency || 'USD';
  const total = items.reduce((s, i) => s + i.unit_price * i.qty, 0);
  $('#view').innerHTML = `<h2 class="rail">My Garage</h2><div class="detail cartpage"><div class="panel">
    ${items.map((i) => `<div class="cartline"><a href="#/p/${esc(i.sku)}"><img src="${esc(i.image)}" alt=""></a><div><b>${esc(i.name)}</b><div class="note">${esc(i.sku)} &times; ${i.qty}</div></div><b>${sym(cur)}${(i.unit_price * i.qty).toFixed(2)}</b></div>`).join('')}
    <h3 style="text-align:right">Total ${sym(cur)}${total.toFixed(2)}</h3></div>
    <div class="panel"><h3 style="margin-top:0">Check out</h3>
    <form class="checkout" id="co"><input name="email" type="email" required placeholder="you@example.com" value="shopper@example.com">
    <input name="card" required value="4242 4242 4242 4242"><div class="note">Test cards: 4242&hellip; approves, 4000&hellip; declines. Ships from our warehouse.</div>
    <button class="btn" type="submit">Place order</button></form><div id="coMsg"></div></div></div>`;
  $('#co').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target); const msg = $('#coMsg'); msg.innerHTML = '<div class="msg">Placing your order&hellip;</div>';
    try {
      const o = await api('/checkout', { method: 'POST', body: { cartId, email: f.get('email'), location: 'warehouse', channel: 'web', cardNumber: String(f.get('card')).replace(/\s/g, '') } });
      msg.innerHTML = `<div class="msg ok">Thank you! Order ${esc(o.order_id)} is on its way (${sym(o.currency)}${o.total.toFixed(2)}).</div>`;
      $('#cartCount').textContent = '0';
    } catch (err) {
      msg.innerHTML = `<div class="msg bad">${err.status === 402 ? 'Card declined.' : esc(err.message)}</div>`;
      refreshCartCount();
    }
  };
}

async function route() {
  const h = location.hash.replace(/^#/, '') || '/';
  const [, kind, arg] = h.split('/');
  window.scrollTo(0, 0);
  if (kind === 'cat') category(decodeURIComponent(arg));
  else if (kind === 'p') await product(arg);
  else if (kind === 'cart') await cartView();
  else if (kind === 'search') await search(decodeURIComponent(arg));
  else await home();
}

document.addEventListener('click', (e) => {
  const b = e.target.closest('button.add');
  if (b) addToCart(b.dataset.sku);
});
$('#searchForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const q = $('#q').value.trim();
  if (q) location.hash = '#/search/' + encodeURIComponent(q);
});
$('#currency').value = state.currency;
$('#currency').addEventListener('change', (e) => { state.currency = e.target.value; localStorage.setItem('tc_cur', state.currency); route(); });
window.addEventListener('hashchange', route);

(async function init() {
  try {
    [state.cats, state.products] = await Promise.all([api('/catalog/categories'), api('/catalog/products?limit=200')]);
  } catch (e) {
    $('#view').innerHTML = `<div class="empty">The shop is warming up (${esc(e.message)}). Refresh in a few seconds.</div>`;
    return;
  }
  refreshCartCount();
  route();
  setInterval(async () => {
    const el = $('#odo');
    if (!el) return;
    try { el.innerHTML = odometer((await api('/stats')).cars_sold || 0); } catch (e) { /* ignore */ }
  }, 10000);
})();
