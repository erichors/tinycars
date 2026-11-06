'use strict';
// TinyCars storefront UI: vanilla JS single-page app, hash routing. Marketplace-style layout:
// header with categories menu, big search, sign-in and cart; demo shopper accounts with order history.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
};
const state = { products: [], cats: [], currency: store.get('tc_cur', 'USD'), user: null, favs: new Set(JSON.parse(store.get('tc_favs', '[]'))) };
const cartId = store.get('tc_cart', null) || (() => { const id = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()); store.set('tc_cart', id); return id; })();
const LOC_NAME = { warehouse: 'Online (warehouse)', boston: 'Boston store', chicago: 'Chicago store', london: 'London store' };
const DEMO_USERS = [
  ['alex.rivera@example.com', 'Alex Rivera'], ['priya.patel@example.com', 'Priya Patel'], ['sam.okafor@example.com', 'Sam Okafor'],
  ['jordan.kim@example.com', 'Jordan Kim'], ['casey.nguyen@example.com', 'Casey Nguyen'], ['morgan.rossi@example.com', 'Morgan Rossi'],
  ['taylor.brooks@example.com', 'Taylor Brooks'], ['riley.chen@example.com', 'Riley Chen'], ['jamie.walker@example.com', 'Jamie Walker'],
  ['avery.lopez@example.com', 'Avery Lopez'], ['drew.murphy@example.com', 'Drew Murphy'], ['harper.singh@example.com', 'Harper Singh'],
];

async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { credentials: 'same-origin', headers: { 'content-type': 'application/json' }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
  let data = null;
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) { const err = new Error((data && data.error) || `Request failed (${r.status})`); err.status = r.status; throw err; }
  return data;
}
const sym = (c) => (c === 'GBP' ? '£' : '$');
const money = (v, c = state.currency) => sym(c) + Number(v).toFixed(2);
const price = (p) => money(state.currency === 'GBP' ? p.price_gbp : p.price_usd);
const byName = (n) => state.products.find((p) => p.name === n);
const initials = (n) => n.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2200);
}

// deterministic review stats per SKU (demo data)
function rating(p) {
  const n = Number(String(p.sku).replace(/\D/g, '')) || 1;
  return { stars: 4 + ((n * 37) % 10) / 10, count: 40 + ((n * 977) % 2400) };
}
function starsHtml(p) {
  const r = rating(p);
  const full = Math.round(r.stars * 2) / 2;
  let s = '';
  for (let i = 1; i <= 5; i++) s += `<i class="${full >= i ? 'on' : full >= i - 0.5 ? 'half' : ''}">&#9733;</i>`;
  return `<span class="stars" aria-label="${r.stars.toFixed(1)} out of 5">${s}</span><span class="rc">(${r.count.toLocaleString('en-US')})</span>`;
}

// ------------------------------------------------------------------ product cards
function card(p) {
  const ltd = p.category === 'Limited Edition';
  const fav = state.favs.has(p.sku);
  return `<article class="card${ltd ? ' ltd' : ''}">
    <div class="media"><a class="thumb" href="#/p/${esc(p.sku)}" aria-label="View ${esc(p.name)}"><img loading="lazy" src="${esc(p.image)}" alt="${esc(p.name)}">
      ${p.new_arrival ? '<span class="badge new">New</span>' : ltd ? '<span class="badge ltd">Limited</span>' : ''}</a>
      <button class="fav${fav ? ' on' : ''}" data-sku="${esc(p.sku)}" aria-label="Save ${esc(p.name)}">${fav ? '&#9829;' : '&#9825;'}</button>
      <button class="add" data-sku="${esc(p.sku)}">Add to cart</button></div>
    <a class="name" href="#/p/${esc(p.sku)}">${esc(p.name)}</a>
    <div class="rating">${starsHtml(p)}</div>
    <div class="price">${price(p)}</div>
    <div class="meta">${esc(p.era)} &middot; ${esc(p.category)}</div>
  </article>`;
}

async function refreshCartCount() {
  try {
    const c = await api('/cart/' + cartId);
    const n = (c.items || []).reduce((s, i) => s + Number(i.qty), 0);
    $('#cartCount').textContent = n;
    $('#cartCount').classList.toggle('zero', n === 0);
    return c;
  } catch (e) { return null; }
}

async function addToCart(sku, qty = 1) {
  try {
    await api(`/cart/${cartId}/items`, { method: 'POST', body: { sku, qty, currency: state.currency } });
    toast(qty > 1 ? `Added ${qty} to your cart` : 'Added to your cart');
    refreshCartCount();
  } catch (e) { toast('Could not add: ' + e.message); }
}

function toggleFav(sku) {
  if (state.favs.has(sku)) state.favs.delete(sku); else state.favs.add(sku);
  store.set('tc_favs', JSON.stringify([...state.favs]));
  $$(`.fav[data-sku="${sku}"]`).forEach((b) => { const on = state.favs.has(sku); b.classList.toggle('on', on); b.innerHTML = on ? '&#9829;' : '&#9825;'; });
  toast(state.favs.has(sku) ? 'Saved to favorites' : 'Removed from favorites');
}

// ------------------------------------------------------------------ header: aisles, categories menu, account
function drawAisles(active) {
  $('#aisles').innerHTML = `<a href="#/new" class="${active === 'new' ? 'on' : ''}"><b class="gift">&#9733;</b> New arrivals</a>` +
    state.cats.map((c) => `<a href="#/cat/${encodeURIComponent(c.name)}" class="${active === c.name ? 'on' : ''}">${esc(c.name)}</a>`).join('');
}

function drawMega() {
  $('#mega').innerHTML = `<div class="megagrid">${state.cats.map((c) => {
    const pic = state.products.find((p) => p.category === c.name);
    return `<a href="#/cat/${encodeURIComponent(c.name)}"><img src="${esc(pic ? pic.image : '')}" alt=""><span><b>${esc(c.name)}</b><small>${c.count} items</small></span></a>`;
  }).join('')}</div>`;
}
function setMega(open) {
  $('#mega').hidden = !open;
  $('#catBtn').setAttribute('aria-expanded', String(open));
}

function drawAccount() {
  const u = state.user;
  if (!u) {
    $('#acct').innerHTML = '<button class="signin" id="signInBtn">Sign in</button>';
    $('#signInBtn').onclick = () => openSignIn();
    $('#footSignIn').textContent = 'Sign in';
    return;
  }
  $('#acct').innerHTML = `<button class="me" id="meBtn" aria-haspopup="true"><span class="avatar">${esc(initials(u.name))}</span><span class="hi">Hi, ${esc(u.name.split(' ')[0])}</span></button>
    <div class="menu" id="meMenu" hidden><div class="who"><b>${esc(u.name)}</b><small>${esc(u.email)}</small></div>
      <a href="#/account">Purchases and reviews</a><a href="#/favorites">Favorites</a><button id="signOutBtn">Sign out</button></div>`;
  $('#footSignIn').textContent = 'Switch account';
  $('#meBtn').onclick = (e) => { e.stopPropagation(); $('#meMenu').hidden = !$('#meMenu').hidden; };
  $('#signOutBtn').onclick = signOut;
}

async function loadMe() {
  try { state.user = (await api('/auth/me')).user; } catch (e) { state.user = null; }
  drawAccount();
}

function openSignIn(after) {
  const root = $('#modalRoot');
  root.innerHTML = `<div class="modal" id="modal" role="dialog" aria-modal="true" aria-labelledby="mTitle">
    <div class="sheet"><button class="x" id="mClose" aria-label="Close">&times;</button>
      <h2 id="mTitle">Sign in</h2><p class="sub">Welcome back to TinyCars.</p>
      <form id="loginForm" class="form">
        <label>Email address<input name="email" type="email" required autocomplete="username"></label>
        <label>Password<input name="password" type="password" required autocomplete="current-password"></label>
        <button class="btn block" type="submit">Sign in</button>
        <div id="loginMsg" class="formmsg"></div>
      </form>
      <div class="demo"><b>Demo shoppers</b> <span>password <code>tinycars</code></span>
        <div class="demolist">${DEMO_USERS.map(([e, n]) => `<button type="button" data-e="${esc(e)}"><span class="avatar sm">${esc(initials(n))}</span>${esc(n)}</button>`).join('')}</div></div>
    </div></div>`;
  const close = () => { root.innerHTML = ''; };
  $('#mClose').onclick = close;
  $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') close(); });
  $$('.demolist button', root).forEach((b) => b.addEventListener('click', () => {
    $('#loginForm [name=email]').value = b.dataset.e; $('#loginForm [name=password]').value = 'tinycars';
  }));
  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    $('#loginMsg').textContent = 'Signing in…';
    try {
      const r = await api('/auth/login', { method: 'POST', body: { email: f.get('email'), password: f.get('password') } });
      state.user = r.user; drawAccount(); close();
      toast(`Welcome back, ${r.user.name.split(' ')[0]}!`);
      if (after) after(); else route();
    } catch (err) {
      $('#loginMsg').textContent = err.status === 401 ? 'That email and password do not match.' : err.message;
      $('#loginMsg').classList.add('bad');
    }
  };
  setTimeout(() => { const i = $('#loginForm [name=email]'); if (i) i.focus(); }, 0);
}

async function signOut() {
  try { await api('/auth/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
  state.user = null; drawAccount(); toast('Signed out'); route();
}

// ------------------------------------------------------------------ pages
async function home() {
  drawAisles();
  const featured = byName('Cone Cruiser') || state.products[0];
  const side = byName('Golden Fastback') || state.products[1];
  let stats = { cars_sold: 0 };
  try { stats = await api('/stats'); } catch (e) { /* ok */ }
  const fresh = state.products.filter((p) => p.new_arrival).slice(0, 10);
  const rails = state.cats.map((c) => {
    const items = state.products.filter((p) => p.category === c.name).slice(0, 5);
    return `<section class="rail"><h2>Popular in ${esc(c.name)} <a href="#/cat/${encodeURIComponent(c.name)}">See more &rarr;</a></h2><div class="grid">${items.map(card).join('')}</div></section>`;
  }).join('');
  const hello = state.user ? `<div class="welcome">Welcome back, <b>${esc(state.user.name.split(' ')[0])}</b>! <a href="#/account">See your recent orders &rarr;</a></div>` : '';
  $('#view').innerHTML = `${hello}
    <section class="heroes">
      <a class="hero-main" href="#/new">
        <div class="copy"><h1>Pocket-sized legends just rolled in</h1><span class="pill">Shop new arrivals</span></div>
        <div class="pic"><img src="${esc(featured.image)}" alt="${esc(featured.name)}"></div>
      </a>
      <a class="hero-side" href="#/cat/${encodeURIComponent('Limited Edition')}">
        <img src="${esc(side.image)}" alt="${esc(side.name)}">
        <div class="scrim"><b>Celebrate the season with Limited Editions</b><span>Shop now</span></div>
      </a>
    </section>
    <section class="circles"><h2>Shop by category</h2><div class="circle-row">${state.cats.map((c) => {
      const pic = state.products.find((p) => p.category === c.name);
      return `<a class="circ" href="#/cat/${encodeURIComponent(c.name)}"><span><img src="${esc(pic ? pic.image : '')}" alt=""></span><b>${esc(c.name)}</b></a>`;
    }).join('')}</div></section>
    <div class="strip"><span><b id="odo">${Number(stats.cars_sold || 0).toLocaleString('en-US')}</b> cars sold so far</span><span>Free shipping on orders over $35</span><span>Pick up in Boston, Chicago or London</span></div>
    <section class="rail"><h2>New arrivals <a href="#/new">See all &rarr;</a></h2><div class="grid">${fresh.map(card).join('')}</div></section>
    ${rails}`;
}

function sortItems(items, how) {
  const val = (p) => Number(state.currency === 'GBP' ? p.price_gbp : p.price_usd);
  const out = [...items];
  if (how === 'price_asc') out.sort((a, b) => val(a) - val(b));
  else if (how === 'price_desc') out.sort((a, b) => val(b) - val(a));
  else if (how === 'rating') out.sort((a, b) => rating(b).stars - rating(a).stars);
  else if (how === 'newest') out.sort((a, b) => Number(b.new_arrival) - Number(a.new_arrival));
  return out;
}
function listing(title, items, active, sub) {
  drawAisles(active);
  const how = store.get('tc_sort', 'relevance');
  const draw = () => {
    $('#listGrid').innerHTML = items.length ? sortItems(items, store.get('tc_sort', 'relevance')).map(card).join('') : '<div class="empty">No cars match. Try another search.</div>';
  };
  $('#view').innerHTML = `<div class="crumbs"><a href="#/">Home</a> &rsaquo; <b>${esc(title)}</b></div>
    <div class="listhead"><div><h1>${esc(title)}</h1><p class="sub">${sub || ''}${items.length} item${items.length === 1 ? '' : 's'}</p></div>
      <label class="sort">Sort by <select id="sortSel">
        ${[['relevance', 'Relevancy'], ['price_asc', 'Lowest price'], ['price_desc', 'Highest price'], ['rating', 'Top customer reviews'], ['newest', 'Most recent']].map(([v, l]) => `<option value="${v}" ${how === v ? 'selected' : ''}>${l}</option>`).join('')}
      </select></label></div>
    <div class="grid wide" id="listGrid"></div>`;
  draw();
  $('#sortSel').onchange = (e) => { store.set('tc_sort', e.target.value); draw(); };
}

function category(name) { listing(name, state.products.filter((p) => p.category === name), name); }
function newArrivals() { listing('New arrivals', state.products.filter((p) => p.new_arrival), 'new'); }
function favorites() { listing('Favorites', state.products.filter((p) => state.favs.has(p.sku))); }

async function search(q) {
  drawAisles();
  $('#q').value = q;
  $('#view').innerHTML = `<div class="loading">Searching for &ldquo;${esc(q)}&rdquo;&hellip;</div>`;
  try {
    const items = await api('/catalog/search?q=' + encodeURIComponent(q));
    listing(`Results for “${q}”`, items, null);
  } catch (e) {
    $('#view').innerHTML = `<div class="empty">Search is having a moment (${esc(e.message)}). Try again shortly.</div>`;
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
  const related = same.filter((x) => x.sku !== sku).slice(0, 5);
  const r = rating(p);
  const fav = state.favs.has(p.sku);
  const thumb = (h, i) => `<button class="chip${i < 0 ? ' on' : ''}" data-i="${i}" aria-label="${esc(h ? h.label : 'Whole car')}">
      <span class="tz"><img src="${esc(p.image)}" alt="" style="${h ? `transform:scale(2.6);transform-origin:${h.x}% ${h.y}%` : ''}"></span><small>${esc(h ? h.label : 'Whole car')}</small></button>`;
  $('#view').innerHTML = `
    <div class="crumbs"><a href="#/">Home</a> &rsaquo; <a href="#/cat/${encodeURIComponent(p.category)}">${esc(p.category)}</a> &rsaquo; <b>${esc(p.name)}</b></div>
    <div class="detail">
      <div class="gallery">
        <div class="closeups" id="closeups">${thumb(null, -1)}${spots.map((h, i) => thumb(h, i)).join('')}</div>
        <div class="stagecol">
          <div class="stage" id="stage">
            <div class="art" id="art"><img id="artImg" src="${esc(p.image)}" alt="${esc(p.name)}">
              ${spots.map((h, i) => `<button class="pin" data-i="${i}" style="left:${h.x}%;top:${h.y}%" aria-label="${esc(h.label)}"><span></span></button>`).join('')}
            </div>
            <button class="zoombtn" id="zoomBtn" aria-label="Full screen view">&#x2922; Full view</button>
            ${p.new_arrival ? '<span class="badge new big">New</span>' : ''}
          </div>
          <div class="callout" id="callout">Tap a pin or a close-up to look closer. Move your mouse over the car to tilt it.</div>
        </div>
      </div>
      <div class="buybox">
        <div class="seller">TinyCars Garage &middot; <span class="stars">&#9733;</span> ${r.stars.toFixed(1)} &middot; ${r.count.toLocaleString('en-US')} reviews</div>
        <div class="price big">${price(p)}</div>
        <h1>${esc(p.name)}</h1>
        <p class="meta">${esc(p.era)} &middot; ${esc(s.class || '')}${s.edition ? ' &middot; ' + esc(s.edition) : ''}</p>
        <p class="lead">${esc(p.description)}</p>
        <label class="qty">Quantity <select id="qty">${[1, 2, 3, 4, 5, 6].map((n) => `<option>${n}</option>`).join('')}</select></label>
        <button class="btn block" id="addBtn">Add to cart</button>
        <button class="btn ghost block fav${fav ? ' on' : ''}" data-sku="${esc(p.sku)}" id="favBtn">${fav ? '&#9829;' : '&#9825;'} ${fav ? 'Saved' : 'Add to favorites'}</button>
        <ul class="perks"><li><b>&#10003;</b> Ships in 1-2 business days</li><li><b>&#10003;</b> Free shipping on orders over $35</li><li><b>&#10003;</b> Free pickup in store</li></ul>
        <details open><summary>Highlights</summary><ul class="feats">${(s.features || []).map((f) => `<li>${esc(f)}</li>`).join('')}</ul></details>
        <details open><summary>Pick up in store</summary><div class="stock" id="stock">Checking shelves&hellip;</div></details>
        <details><summary>Item details</summary><table class="specs">${specRows(p)}</table></details>
      </div>
    </div>
    <section class="rail"><h2>More from ${esc(p.category)} <a href="#/cat/${encodeURIComponent(p.category)}">See more &rarr;</a></h2><div class="grid">${related.map(card).join('')}</div></section>`;

  // tilt + close-ups
  const stage = $('#stage'), art = $('#art'), callout = $('#callout');
  let zoomed = -1;
  const setZoom = (i) => {
    zoomed = i;
    $$('#closeups .chip').forEach((c) => c.classList.toggle('on', Number(c.dataset.i) === i));
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
    const rc = stage.getBoundingClientRect();
    const px = (e.clientX - rc.left) / rc.width - 0.5, py = (e.clientY - rc.top) / rc.height - 0.5;
    art.style.setProperty('--ry', (px * 9).toFixed(2) + 'deg'); art.style.setProperty('--rx', (-py * 7).toFixed(2) + 'deg');
  });
  stage.addEventListener('mouseleave', () => { if (zoomed < 0) { art.style.setProperty('--rx', '0deg'); art.style.setProperty('--ry', '0deg'); } });
  $$('.pin').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); setZoom(zoomed === Number(b.dataset.i) ? -1 : Number(b.dataset.i)); }));
  $$('#closeups .chip').forEach((b) => b.addEventListener('click', () => setZoom(Number(b.dataset.i))));
  $('#zoomBtn').onclick = () => openLightbox(p);
  $('#artImg').addEventListener('dblclick', () => openLightbox(p));
  $('#addBtn').onclick = () => addToCart(sku, Number($('#qty').value));
  $('#favBtn').addEventListener('click', () => setTimeout(() => {
    const on = state.favs.has(sku); $('#favBtn').innerHTML = `${on ? '&#9829; Saved' : '&#9825; Add to favorites'}`;
  }, 0));

  try {
    const rows = await api('/stock/' + sku);
    $('#stock').innerHTML = ['warehouse', 'boston', 'chicago', 'london'].map((loc) => {
      const row = rows.find((x) => x.location === loc); const q = row ? row.qty : 0;
      return `<div class="loc ${q === 0 ? 'out' : q < 6 ? 'low' : 'ok'}"><b>${q}</b><span>${esc(LOC_NAME[loc])}</span><i>${q === 0 ? 'Sold out' : q < 6 ? 'Only a few left' : 'In stock'}</i></div>`;
    }).join('');
  } catch (e) {
    $('#stock').innerHTML = `<span class="low">Stock check unavailable (${esc(e.message)})</span>`;
  }
}

// ------------------------------------------------------------------ cart + checkout
async function cartView() {
  drawAisles();
  const c = await refreshCartCount();
  const items = (c && c.items) || [];
  if (!items.length) {
    const pic = (byName('Bubble Bug') || state.products[0]).image;
    $('#view').innerHTML = `<div class="empty"><img src="${esc(pic)}" alt=""><h2>Your cart is empty.</h2><p>Discover something unique to fill it up.</p><a class="btn" href="#/new">Discover new arrivals</a></div>`;
    return;
  }
  const cur = c.currency || 'USD';
  const count = items.reduce((s, i) => s + Number(i.qty), 0);
  const total = items.reduce((s, i) => s + i.unit_price * i.qty, 0);
  const ship = total >= 35 ? 0 : 4.99;
  const u = state.user;
  $('#view').innerHTML = `<h1 class="pagehead">${count} item${count === 1 ? '' : 's'} in your cart</h1>
    <div class="cartgrid"><div class="panel">
      <div class="shop">TinyCars Garage <small>Ships from our warehouse</small></div>
      ${items.map((i) => `<div class="cartline"><a href="#/p/${esc(i.sku)}"><img src="${esc(i.image)}" alt=""></a><div><a class="name" href="#/p/${esc(i.sku)}">${esc(i.name)}</a><div class="note">${esc(i.sku)} &middot; Qty ${i.qty} &middot; ${money(i.unit_price, cur)} each</div></div><b>${money(i.unit_price * i.qty, cur)}</b></div>`).join('')}
    </div>
    <div class="panel summary"><h3>Order summary</h3>
      <div class="sumrow"><span>Item(s) total</span><span>${money(total, cur)}</span></div>
      <div class="sumrow"><span>Shipping</span><span>${ship ? money(ship, cur) : '<b class="free">FREE</b>'}</span></div>
      <div class="sumrow total"><span>Total (${count} item${count === 1 ? '' : 's'})</span><span>${money(total + ship, cur)}</span></div>
      <form class="form" id="co">
        ${u ? `<div class="as"><span class="avatar sm">${esc(initials(u.name))}</span>Checking out as <b>${esc(u.name)}</b><small>${esc(u.email)}</small></div><input name="email" type="hidden" value="${esc(u.email)}">`
    : `<label>Email for your receipt<input name="email" type="email" required placeholder="you@example.com" value="guest@example.com"></label><div class="note"><a href="#" id="coSignIn">Sign in</a> to save this order to your purchase history.</div>`}
        <label>Card number<input name="card" required value="4242 4242 4242 4242"></label>
        <div class="note">Test cards: 4242&hellip; approves, 4000&hellip; declines.</div>
        <button class="btn block" type="submit">Proceed to checkout</button>
      </form><div id="coMsg"></div></div></div>`;
  if ($('#coSignIn')) $('#coSignIn').onclick = (e) => { e.preventDefault(); openSignIn(() => cartView()); };
  $('#co').onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target); const msg = $('#coMsg'); msg.innerHTML = '<div class="msg">Placing your order&hellip;</div>';
    try {
      const o = await api('/checkout', { method: 'POST', body: { cartId, email: f.get('email'), location: 'warehouse', channel: 'web', cardNumber: String(f.get('card')).replace(/\s/g, '') } });
      msg.innerHTML = `<div class="msg ok">Thank you! Order ${esc(o.order_id)} is on its way (${money(o.total, o.currency)}).${state.user ? ' <a href="#/account">View your purchases</a>' : ''}</div>`;
      $('#cartCount').textContent = '0'; $('#cartCount').classList.add('zero');
    } catch (err) {
      msg.innerHTML = `<div class="msg bad">${err.status === 402 ? 'Card declined. Try a different card.' : esc(err.message)}</div>`;
      refreshCartCount();
    }
  };
}

// ------------------------------------------------------------------ account: purchases
async function account() {
  drawAisles();
  if (!state.user) {
    $('#view').innerHTML = `<div class="empty"><h2>Sign in to see your purchases</h2><p>Use one of the demo shoppers, password <code>tinycars</code>.</p><button class="btn" id="acctSignIn">Sign in</button></div>`;
    $('#acctSignIn').onclick = () => openSignIn();
    openSignIn();
    return;
  }
  const u = state.user;
  $('#view').innerHTML = `<div class="profile"><span class="avatar lg">${esc(initials(u.name))}</span><div><h1>${esc(u.name)}</h1>
      <p class="sub">${esc(u.city)} &middot; Member since ${esc(new Date(u.member_since + 'T12:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' }))}${u.home_store ? ' &middot; Home store: ' + esc(LOC_NAME[u.home_store]) : ''}</p></div></div>
    <h2 class="pagehead">Purchases</h2><div id="orders" class="loading">Loading your orders&hellip;</div>`;
  try {
    const orders = await api('/account/orders');
    if (!orders.length) { $('#orders').outerHTML = '<div class="empty">No purchases yet.</div>'; return; }
    $('#orders').outerHTML = `<div class="orders">${orders.map((o) => `<article class="order">
      <header><div><b>${esc(new Date(o.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }))}</b><small>Order ${esc(o.order_id)}</small></div>
        <div><small>${o.channel === 'in_store' ? 'In store' : 'Online'}</small><b>${esc(LOC_NAME[o.location] || o.location)}</b></div>
        <div><small>Total</small><b>${money(o.total, o.currency)}</b></div>
        <span class="status ${esc(o.status)}">${o.status === 'completed' ? 'Delivered' : esc(o.status)}</span></header>
      ${o.items.map((i) => `<div class="oline"><a href="#/p/${esc(i.sku)}"><img src="${esc(i.image || '')}" alt=""></a><div><a class="name" href="#/p/${esc(i.sku)}">${esc(i.name || i.sku)}</a><small>Qty ${i.qty} &middot; ${money(i.unit_price, o.currency)}</small></div><button class="btn ghost sm add" data-sku="${esc(i.sku)}">Buy this again</button></div>`).join('')}
    </article>`).join('')}</div>`;
  } catch (e) {
    $('#orders').outerHTML = `<div class="empty">Could not load your orders (${esc(e.message)}).</div>`;
  }
}

// ------------------------------------------------------------------ "Find my car" (AI matcher)
const MATCH_IDEAS = ['Outdoorsy, a bit loud, and I love the 70s', 'Calm, classic, Sunday-drive person', 'Competitive and always early',
  'I build things and get my hands dirty', 'Quirky, artsy, a little bit silly', 'I help people and stay cool under pressure'];
function openMatcher() {
  const root = $('#modalRoot');
  root.innerHTML = `<div class="modal" id="modal" role="dialog" aria-modal="true" aria-labelledby="fmTitle">
    <div class="sheet wide"><button class="x" id="mClose" aria-label="Close">&times;</button>
      <h2 id="fmTitle">Find my car</h2><p class="sub">Tell us a little about yourself and we'll pick the TinyCar that fits you.</p>
      <form id="matchForm" class="form">
        <textarea name="text" id="matchText" maxlength="300" rows="3" required placeholder="e.g. I'm outdoorsy, a bit loud, and I love the 70s"></textarea>
        <div class="ideas">${MATCH_IDEAS.map((i) => `<button type="button" data-t="${esc(i)}">${esc(i)}</button>`).join('')}</div>
        <button class="btn block" type="submit" id="matchGo">Match me</button>
      </form>
      <div id="matchOut"></div>
    </div></div>`;
  const close = () => { root.innerHTML = ''; };
  $('#mClose').onclick = close;
  $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') close(); });
  $$('.ideas button', root).forEach((b) => b.addEventListener('click', () => { $('#matchText').value = b.dataset.t; $('#matchText').focus(); }));
  $('#matchForm').onsubmit = async (e) => {
    e.preventDefault();
    const out = $('#matchOut'); const go = $('#matchGo');
    go.disabled = true; go.textContent = 'Finding your car…';
    out.innerHTML = '<div class="matching"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
    try {
      const r = await api('/catalog/match', { method: 'POST', body: { text: $('#matchText').value } });
      const p = r.product;
      out.innerHTML = `<div class="matchcard"><a href="#/p/${esc(p.sku)}" class="mimg"><img src="${esc(p.image)}" alt="${esc(p.name)}"></a>
        <div><small>Your TinyCar is</small><h3>${esc(p.name)}</h3><p>${esc(r.reason)}</p><div class="mprice">${price(p)}</div>
        <div class="mbtns"><button class="btn add" data-sku="${esc(p.sku)}">Add to cart</button><a class="btn ghost" href="#/p/${esc(p.sku)}" id="matchView">View details</a></div>
        <div class="by">${r.provider === 'bedrock' ? `Matched by Claude on Amazon Bedrock (${esc(r.model)})` : r.fallback ? 'Matched by our quick matcher (the AI matchmaker is busy right now)' : 'Matched by our quick matcher'}</div></div></div>`;
      $('#matchView').onclick = close;
    } catch (err) {
      out.innerHTML = `<div class="msg bad">${esc(err.message)}</div>`;
    } finally { go.disabled = false; go.textContent = 'Match me again'; }
  };
  setTimeout(() => { const i = $('#matchText'); if (i) i.focus(); }, 0);
}

// ------------------------------------------------------------------ routing + wiring
async function route() {
  const h = location.hash.replace(/^#/, '') || '/';
  const [, kind, arg] = h.split('/');
  setMega(false);
  window.scrollTo(0, 0);
  if (kind === 'cat') category(decodeURIComponent(arg));
  else if (kind === 'new') newArrivals();
  else if (kind === 'favorites') favorites();
  else if (kind === 'p') await product(arg);
  else if (kind === 'cart') await cartView();
  else if (kind === 'account') await account();
  else if (kind === 'search') await search(decodeURIComponent(arg));
  else await home();
}

document.addEventListener('click', (e) => {
  const add = e.target.closest('button.add');
  if (add) { addToCart(add.dataset.sku); return; }
  const fav = e.target.closest('button.fav');
  if (fav) { toggleFav(fav.dataset.sku); return; }
  if (!e.target.closest('.catmenu')) setMega(false);
  const menu = $('#meMenu');
  if (menu && !e.target.closest('.acct')) menu.hidden = true;
});
$('#catBtn').addEventListener('click', () => setMega($('#mega').hidden));
$('#matchBtn').addEventListener('click', openMatcher);
$('#searchForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const q = $('#q').value.trim();
  if (q) location.hash = '#/search/' + encodeURIComponent(q);
});
$('#currency').value = state.currency;
$('#currency').addEventListener('change', (e) => { state.currency = e.target.value; store.set('tc_cur', state.currency); route(); });
window.addEventListener('hashchange', route);

(async function init() {
  drawAccount();
  try {
    [state.cats, state.products] = await Promise.all([api('/catalog/categories'), api('/catalog/products?limit=200')]);
  } catch (e) {
    $('#view').innerHTML = `<div class="empty">The shop is warming up (${esc(e.message)}). Refresh in a few seconds.</div>`;
    return;
  }
  drawMega();
  await loadMe();
  refreshCartCount();
  route();
  setInterval(async () => {
    const el = $('#odo');
    if (!el) return;
    try { el.textContent = Number((await api('/stats')).cars_sold || 0).toLocaleString('en-US'); } catch (e) { /* ignore */ }
  }, 10000);
})();
