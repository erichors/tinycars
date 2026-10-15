'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let token = sessionStorage.getItem('tc_admin') || '';
let busy = false; // pause polling while the user is dragging a slider / editing

async function call(path, method = 'GET', body) {
  const r = await fetch('/api/admin' + path, { method, headers: { 'content-type': 'application/json', 'x-admin-token': token }, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401) { sessionStorage.removeItem('tc_admin'); showGate('Wrong token.'); throw new Error('unauthorized'); }
  return r.json();
}
function showGate(msg) { $('#gate').classList.remove('hide'); $('#app').classList.add('hide'); $('#gateMsg').textContent = msg || ''; }

function render(s) {
  $('#health').innerHTML = Object.entries(s.health).map(([k, v]) => `<span class="badge"><span class="dot ${v ? 'up' : ''}"></span>${esc(k)}</span>`).join(' ');
  if (!busy) {
    $('#rpm').value = s.load.rpm; $('#web').value = s.load.web_pct;
  }
  $('#rpmV').textContent = $('#rpm').value; $('#webV').textContent = $('#web').value;
  $('#lState').textContent = s.load.running ? 'RUNNING' : 'STOPPED';
  $('#lState').style.color = s.load.running ? 'var(--ok)' : 'var(--warn)';

  if (!document.activeElement || !document.activeElement.closest('#patterns')) {
    let html = '', group = '';
    for (const p of s.patterns) {
      if (p.group !== group) { group = p.group; html += `<div class="grp">${esc(group.toUpperCase())}</div>`; }
      const f = s.flags[p.name] || { on: false, level: 2, store: 'boston' };
      const storeSel = p.store ? `<select data-store="${p.name}">${s.stores.map((st) => `<option ${st === f.store ? 'selected' : ''}>${st}</option>`).join('')}</select>` : '';
      html += `<div class="pat"><button class="sw ${f.on ? 'on' : ''}" data-toggle="${p.name}" aria-label="toggle ${esc(p.label)}"></button>
        <div><b>${esc(p.label)}</b> <span class="badge">${esc(p.service)}</span><small>${esc(p.description)}</small></div>
        <select data-level="${p.name}" title="level">${[1, 2, 3, 4, 5].map((n) => `<option ${n === Number(f.level) ? 'selected' : ''} value="${n}">lvl ${n}</option>`).join('')}</select>${storeSel || '<span></span>'}</div>`;
    }
    $('#patterns').innerHTML = html;
  }
  $('#events').innerHTML = s.events.map((e) => {
    const kind = (e.event || '').includes('ENABLED') ? 'ENABLED' : (e.event || '').includes('DISABLED') ? 'DISABLED' : '';
    const bits = [e.pattern, e.level ? 'lvl ' + e.level : '', e.store, e.rpm != null ? e.rpm + '/min' : ''].filter(Boolean).join(' ');
    return `<div><span class="${kind}">${esc(e.event)}</span> ${esc(bits)} <small>${esc(new Date(e.ts).toLocaleTimeString())}</small></div>`;
  }).join('') || '<div>no events yet</div>';
}

async function refresh() { try { render(await call('/state')); } catch (e) { /* gate shown on 401 */ } }

async function setPattern(name, on) {
  const level = Number(document.querySelector(`[data-level="${name}"]`).value);
  const storeEl = document.querySelector(`[data-store="${name}"]`);
  await call('/flags/' + name, 'PUT', { on, level, store: storeEl ? storeEl.value : undefined });
  refresh();
}

document.addEventListener('click', async (e) => {
  const t = e.target.closest('[data-toggle]');
  if (t) setPattern(t.dataset.toggle, !t.classList.contains('on'));
  if (e.target.id === 'lStart') { await call('/load', 'PUT', { running: true }); refresh(); }
  if (e.target.id === 'lStop') { await call('/load', 'PUT', { running: false }); refresh(); }
  if (e.target.dataset && e.target.dataset.rpm) { await call('/load', 'PUT', { running: true, rpm: Number(e.target.dataset.rpm) }); refresh(); }
  if (e.target.id === 'reset') { await call('/reset', 'POST'); refresh(); }
});
document.addEventListener('change', (e) => {
  const lv = e.target.dataset && (e.target.dataset.level || e.target.dataset.store);
  if (lv) {
    const row = e.target.closest('.pat'); const sw = row.querySelector('[data-toggle]');
    if (sw.classList.contains('on')) setPattern(sw.dataset.toggle, true); // re-apply with new level/store
  }
  if (e.target.id === 'rpm' || e.target.id === 'web') {
    busy = false;
    call('/load', 'PUT', { rpm: Number($('#rpm').value), web_pct: Number($('#web').value) }).then(refresh);
  }
});
document.addEventListener('input', (e) => {
  if (e.target.id === 'rpm' || e.target.id === 'web') { busy = true; $('#rpmV').textContent = $('#rpm').value; $('#webV').textContent = $('#web').value; }
});

async function enter() {
  token = $('#tok').value || token;
  sessionStorage.setItem('tc_admin', token);
  try { await call('/flags'); $('#gate').classList.add('hide'); $('#app').classList.remove('hide'); refresh(); } catch (e) { /* gate shown */ }
}
$('#go').onclick = enter;
$('#tok').addEventListener('keydown', (e) => { if (e.key === 'Enter') enter(); });
if (token) enter(); else showGate();
setInterval(() => { if (!busy && !$('#app').classList.contains('hide')) refresh(); }, 3000);
