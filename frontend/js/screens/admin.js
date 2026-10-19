// Yönetim paneli (yalnızca yöneticiler): özet, şikâyetler, kullanıcılar, odalar, ajanslar.
// Yetki kontrolü sunucuda; yönetici olmayan biri adresi açarsa sunucu 403 döner, ekran uyarı gösterir.
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCoins, formatCount, toast, openSheet } from '../ui.js';
import { REASONS } from './report.js';

const TABS = [
  { id: 'stats', label: 'Özet' },
  { id: 'reports', label: 'Şikâyet' },
  { id: 'users', label: 'Kişi' },
  { id: 'rooms', label: 'Oda' },
  { id: 'agencies', label: 'Ajans' },
];
const REASON_LABELS = Object.fromEntries(REASONS.map((r) => [r.id, r.label]));
const ACTION_LABELS = { dismiss: 'Reddedildi', ban_user: 'Kullanıcı banlandı', close_room: 'Oda kapatıldı' };

// Geri alınamayan işlem için iki dokunuş: ilk dokunuşta düğme "Emin misin?" olur
function confirmTap(button) {
  if (button.dataset.confirming) return true;
  const original = button.textContent;
  button.dataset.confirming = '1';
  button.textContent = 'Emin misin? Tekrar dokun';
  setTimeout(() => { delete button.dataset.confirming; button.textContent = original; }, 3000);
  return false;
}

// Kısa metin sorar (ban gerekçesi, karar notu). Vazgeçilirse null döner.
function ask(title, placeholder, { required = true } = {}) {
  return new Promise((resolve) => {
    const sheet = openSheet(`
      <h2 class="sheet-title">${esc(title)}</h2>
      <form id="ask-form">
        <label class="field"><input name="text" maxlength="300" placeholder="${esc(placeholder)}" ${required ? 'required minlength="3"' : ''} /></label>
        <button class="btn btn-primary btn-block" type="submit">Onayla</button>
      </form>`, { className: 'sheet-dark' });
    let done = false;
    sheet.el.querySelector('#ask-form').addEventListener('submit', (event) => {
      event.preventDefault();
      done = true;
      sheet.close();
      resolve(event.target.elements.text.value.trim());
    });
    const observer = new MutationObserver(() => {
      if (!sheet.el.isConnected) { observer.disconnect(); if (!done) resolve(null); }
    });
    observer.observe(document.getElementById('overlay-root'), { childList: true });
  });
}

// ─── Sekmeler ──────────────────────────────────────────────────────────────────

async function statsPanel(panel) {
  const s = await api.adminStats();
  const cards = [
    ['👥', 'Kullanıcı', formatCount(s.users_total), `bugün +${s.users_today}`],
    ['🟢', 'Çevrimiçi', formatCount(s.online_now), ''],
    ['🎙️', 'Açık oda', formatCount(s.rooms_active), ''],
    ['🪙', 'Bugün satılan coin', formatCoins(s.coins_sold_today), 'demo: ödeme yok'],
    ['🎁', 'Bugün hediye', formatCoins(s.gift_coins_today), 'coin'],
    ['🚩', 'Açık şikâyet', formatCount(s.open_reports), ''],
    ['⛔', 'Banlı', formatCount(s.banned_users), ''],
  ];
  panel.innerHTML = `<div class="admin-stats">${cards.map(([emoji, label, value, hint]) => `
    <div class="admin-stat"><i>${emoji}</i><b>${value}</b><span>${label}</span>${hint ? `<small>${hint}</small>` : ''}</div>`).join('')}</div>`;
}

async function reportsPanel(panel) {
  let status = 'open';
  async function render() {
    const reports = await api.adminReports(status);
    panel.innerHTML = `
      <div class="chips chips-wrap admin-filter">
        <button class="chip ${status === 'open' ? 'is-active' : ''}" data-status="open">Açık</button>
        <button class="chip ${status === 'closed' ? 'is-active' : ''}" data-status="closed">Karara bağlanan</button>
      </div>
      ${reports.map((r) => `
        <article class="admin-card">
          <header>
            <b>${r.target_type === 'user' ? '👤' : '🎙️'} <a href="#/${r.target_type === 'user' ? 'profile' : 'room'}/${r.target_id}">${esc(r.target_label)}</a></b>
            <span class="admin-tag">${esc(REASON_LABELS[r.reason] || r.reason)}</span>
          </header>
          ${r.details ? `<p>${esc(r.details)}</p>` : ''}
          <small>Şikâyet eden: ${esc(r.reporter?.display_name || '—')} · ${new Date(r.created_at).toLocaleString('tr-TR')}</small>
          ${r.status === 'open'
            ? `<div class="activity-options">
                 <button class="btn btn-sm btn-soft" data-resolve="dismiss" data-id="${r.id}">Reddet</button>
                 ${r.target_type === 'user'
                   ? `<button class="btn btn-sm btn-danger" data-resolve="ban_user" data-id="${r.id}">Kullanıcıyı banla</button>`
                   : `<button class="btn btn-sm btn-danger" data-resolve="close_room" data-id="${r.id}">Odayı kapat</button>`}
               </div>`
            : `<small class="admin-resolution">${ACTION_LABELS[r.action] || r.status}${r.resolution_note ? ` · ${esc(r.resolution_note)}` : ''}</small>`}
        </article>`).join('') || '<p class="member-empty">Burada şikâyet yok.</p>'}`;
  }
  panel.onclick = async (event) => {
    const filter = event.target.closest('[data-status]');
    if (filter) { status = filter.dataset.status; return render(); }
    const button = event.target.closest('[data-resolve]');
    if (!button) return;
    const action = button.dataset.resolve;
    const note = await ask(ACTION_LABELS[action], 'Karar notu (isteğe bağlı)', { required: action === 'ban_user' });
    if (note === null) return;
    try {
      await api.adminResolveReport(Number(button.dataset.id), action, note);
      toast('Şikâyet karara bağlandı', 'success');
      await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  await render();
}

function openUserSheet(userId, onChange) {
  const sheet = openSheet('<div id="admin-user"><div class="loading"><div class="spinner"></div></div></div>', { className: 'sheet-dark' });
  const body = sheet.el.querySelector('#admin-user');
  async function render() {
    const d = await api.adminUser(userId);
    body.innerHTML = `
      <div class="admin-user-head">
        ${avatarImg(d.user, 'avatar-md')}
        <span class="member-info">
          <b>${esc(d.user.display_name)} ${d.is_active ? '' : '<span class="admin-tag admin-tag-danger">Banlı</span>'}${d.is_admin ? '<span class="admin-tag">Yönetici</span>' : ''}</b>
          <small>@${esc(d.user.username)} · ID ${d.user.id}${d.email ? ` · ${esc(d.email)}` : ''}</small>
        </span>
      </div>
      <div class="admin-balances">
        <span>🪙 <b>${formatCoins(d.coin_balance)}</b></span><span>💎 <b>${formatCoins(d.diamond_balance)}</b></span><span>🚩 <b>${d.reports_against}</b> şikâyet</span>
      </div>
      <div class="activity-options">
        <a class="btn btn-sm btn-soft" href="#/profile/${d.user.id}" data-close>Profil</a>
        ${d.is_admin ? '' : `<button class="btn btn-sm ${d.is_active ? 'btn-danger' : 'btn-primary'}" data-user-act="${d.is_active ? 'ban' : 'unban'}">${d.is_active ? 'Banla' : 'Banı kaldır'}</button>`}
      </div>
      <form class="admin-adjust" id="adjust-form">
        <b>Bakiye düzeltme</b>
        <div>
          <select name="currency"><option value="coin">Coin</option><option value="diamond">Elmas</option></select>
          <input name="amount" type="number" placeholder="+500 / -500" required />
        </div>
        <input name="reason" maxlength="200" minlength="3" placeholder="Gerekçe (zorunlu, deftere yazılır)" required />
        <button class="btn btn-sm btn-primary" type="submit">Uygula</button>
      </form>
      <h3 class="sub-title">Son hareketler</h3>
      <div class="tx-list">${d.recent_transactions.map((t) => `
        <div class="tx"><span class="tx-body"><b>${esc(t.label)}</b><small>${esc(t.time_label)} · ${t.currency === 'coin' ? '🪙' : '💎'}</small></span>
        <b class="tx-amount ${t.amount > 0 ? 'is-positive' : ''}">${t.amount > 0 ? '+' : ''}${formatCoins(t.amount)}</b></div>`).join('') || '<p class="member-empty">Hareket yok.</p>'}</div>`;
  }
  body.addEventListener('click', async (event) => {
    const act = event.target.closest('[data-user-act]')?.dataset.userAct;
    if (!act) return;
    try {
      if (act === 'ban') {
        const reason = await ask('Banlama gerekçesi', 'Ör. spam hesap');
        if (!reason) return;
        await api.adminBan(userId, reason);
        toast('Kullanıcı banlandı; oturumları kapatıldı', 'success');
      } else {
        await api.adminUnban(userId);
        toast('Ban kaldırıldı', 'success');
      }
      await render();
      onChange();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
  body.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      const result = await api.adminAdjustBalance(userId, {
        currency: form.elements.currency.value, amount: Number(form.elements.amount.value), reason: form.elements.reason.value,
      });
      toast(`Yeni bakiye: ${formatCoins(result.balance)}`, 'success');
      await render();
    } catch (error) {
      toast(error.code === 'insufficient_balance' ? 'Bakiye bu kadar düşmeye yetmiyor.' : error.message, 'error');
    }
  });
  render().catch((error) => { body.innerHTML = `<p class="member-empty">${esc(error.message)}</p>`; });
}

async function usersPanel(panel) {
  panel.innerHTML = `
    <div class="search-box admin-search">${icon('search', 18)}<input id="admin-user-search" type="search" placeholder="Ad, @kullanıcı adı, e-posta ya da ID" autocomplete="off" /></div>
    <div id="admin-user-list"></div>`;
  const listEl = panel.querySelector('#admin-user-list');
  let query = '';
  let requestId = 0;
  async function load() {
    const id = ++requestId;
    const users = await api.adminUsers(query);
    if (id !== requestId) return;
    listEl.innerHTML = users.map((u) => `
      <button class="member-row" data-user="${u.user.id}">
        ${avatarImg(u.user, 'avatar-md')}
        <span class="member-info"><b>${esc(u.user.display_name)} ${u.is_active ? '' : '<span class="admin-tag admin-tag-danger">Banlı</span>'}</b>
        <small>@${esc(u.user.username)} · ID ${u.user.id} · 🪙 ${formatCoins(u.coin_balance)}${u.reports_against ? ` · 🚩 ${u.reports_against}` : ''}</small></span>
      </button>`).join('') || '<p class="member-empty">Kimse bulunamadı.</p>';
  }
  let debounce;
  panel.querySelector('#admin-user-search').addEventListener('input', (event) => {
    query = event.target.value.trim();
    clearTimeout(debounce);
    debounce = setTimeout(load, 250);
  });
  panel.onclick = (event) => {
    const row = event.target.closest('[data-user]');
    if (row) openUserSheet(Number(row.dataset.user), load);
  };
  await load();
}

async function roomsPanel(panel) {
  async function render() {
    const rooms = await api.adminRooms();
    panel.innerHTML = rooms.map((r) => `
      <div class="admin-card admin-room">
        <span class="member-info">
          <b><a href="#/room/${r.id}">${esc(r.title)}</a> ${r.is_live ? '<span class="pill pill-live">CANLI</span>' : ''}</b>
          <small>ID ${r.id} · ${icon('users', 11)} ${r.listener_count} · Sahibi: ${esc(r.host?.display_name || '—')}</small>
        </span>
        <button class="btn btn-sm btn-danger" data-close-room="${r.id}">Kapat</button>
      </div>`).join('') || '<p class="member-empty">Açık oda yok.</p>';
  }
  panel.onclick = async (event) => {
    const button = event.target.closest('[data-close-room]');
    if (!button || !confirmTap(button)) return;
    try {
      await api.adminCloseRoom(Number(button.dataset.closeRoom));
      toast('Oda kapatıldı; içerideki herkes çıkarıldı', 'success');
      await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  await render();
}

async function agenciesPanel(panel) {
  async function render() {
    const agencies = await api.adminAgencies();
    panel.innerHTML = `
      <form class="admin-adjust" id="agency-form">
        <b>Yeni ajans</b>
        <input name="name" maxlength="40" minlength="2" placeholder="Ajans adı" required />
        <div>
          <input name="owner_id" type="number" placeholder="Sahibinin kullanıcı ID'si" required />
          <input name="commission" type="number" min="0" max="50" value="10" title="Komisyon %" />
        </div>
        <button class="btn btn-sm btn-primary" type="submit">Kur</button>
      </form>
      ${agencies.map((a) => `
        <div class="admin-card admin-room">
          ${avatarImg(a.owner, 'avatar-sm')}
          <span class="member-info"><b>🏢 ${esc(a.name)}</b><small>Sahibi: ${esc(a.owner.display_name)} · ${a.member_count} yayıncı · %${a.commission_percent} komisyon</small></span>
        </div>`).join('') || '<p class="member-empty">Henüz ajans yok.</p>'}`;
  }
  panel.onsubmit = async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.adminCreateAgency({
        name: form.elements.name.value, owner_id: Number(form.elements.owner_id.value),
        commission_percent: Number(form.elements.commission.value),
      });
      toast('Ajans kuruldu', 'success');
      await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  await render();
}

const PANELS = { stats: statsPanel, reports: reportsPanel, users: usersPanel, rooms: roomsPanel, agencies: agenciesPanel };

export async function renderAdmin(root, { query }) {
  let tab = PANELS[query.tab] ? query.tab : 'stats';
  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/profile" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Yönetim</h1>
      <span></span>
    </header>
    <div class="segmented admin-tabs">${TABS.map((t) => `<button data-tab="${t.id}">${t.label}</button>`).join('')}</div>
    <div class="section" id="admin-panel"></div>`;
  const panel = root.querySelector('#admin-panel');

  async function show(next) {
    tab = next;
    root.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === tab));
    panel.onclick = null;
    panel.onsubmit = null;
    panel.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
      await PANELS[tab](panel);
    } catch (error) {
      panel.innerHTML = `<div class="empty"><p>${error.code === 'admin_only' ? 'Bu sayfa yalnızca yöneticilere açık.' : esc(error.message)}</p></div>`;
    }
  }
  root.querySelector('.admin-tabs').addEventListener('click', (event) => {
    const button = event.target.closest('[data-tab]');
    if (button && button.dataset.tab !== tab) show(button.dataset.tab);
  });
  await show(tab);
}
