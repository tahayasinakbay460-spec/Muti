// Masaüstü yönetim paneli. Uygulamanın veri katmanını (api.js) kullanır: aynı giriş, aynı token.
// Yetki kontrolü sunucuda (/api/v1/admin/... yalnızca yöneticilere açık); bu sayfa yalnızca gösterir.
import { api } from '../api.js';
import { esc, formatCoins, formatCount } from '../ui.js';
import { DEFAULT_AVATAR_URL } from '../config.js';
import { REASONS } from '../screens/report.js';

const appEl = document.getElementById('admin-app');

const PAGES = [
  { id: 'overview', label: 'Genel Bakış', icon: '📊' },
  { id: 'finance', label: 'Finans', icon: '💰' },
  { id: 'transactions', label: 'Para Hareketleri', icon: '🧾' },
  { id: 'users', label: 'Kullanıcılar', icon: '👥' },
  { id: 'messages', label: 'Mesajlar', icon: '💬' },
  { id: 'rooms', label: 'Odalar', icon: '🎙️' },
  { id: 'reports', label: 'Şikâyetler', icon: '🚩' },
  { id: 'catalog', label: 'Hediye & Paketler', icon: '🎁' },
  { id: 'agencies', label: 'Ajanslar', icon: '🏢' },
  { id: 'broadcast', label: 'Duyuru', icon: '📢' },
];

// Para defterindeki işlem türlerinin Türkçe adları
const TX_LABELS = {
  purchase: 'Coin satın alma', gift_sent: 'Hediye gönderme', gift_received: 'Hediye alma', exchange: 'Elmas çevirme',
  store_purchase: 'Mağaza', vip_purchase: 'VIP üyelik', vip_daily: 'VIP günlük ödül', lucky_win: 'Şanslı hediye kazancı',
  chest_reward: 'Hazine sandığı', daily_checkin: 'Günlük giriş', task_reward: 'Görev ödülü', family_create: 'Aile kurma',
  cp_proposal: 'CP teklifi', cp_refund: 'CP iadesi', event_reward: 'Etkinlik ödülü', admin_adjustment: 'Yönetici düzeltmesi',
  reward: 'Ödül',
};
const REASON_LABELS = Object.fromEntries(REASONS.map((r) => [r.id, r.label]));
const ACTION_LABELS = { dismiss: 'Reddedildi', ban_user: 'Kullanıcı banlandı', close_room: 'Oda kapatıldı' };

// ─── Küçük yardımcılar ─────────────────────────────────────────────────────────
const avatar = (user, cls = '') => `<img class="avatar ${cls}" src="${esc(user?.avatar_url || DEFAULT_AVATAR_URL)}" alt="" loading="lazy" />`;
const dateTime = (iso) => (iso ? new Date(iso).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' }) : '—');
const signed = (n) => `<span class="${n > 0 ? 'pos' : n < 0 ? 'neg' : ''}">${n > 0 ? '+' : ''}${formatCoins(n)}</span>`;
const userCell = (user) => (user
  ? `<div class="cell-user">${avatar(user)}<span><b>${esc(user.display_name)}</b><small>@${esc(user.username)} · ID ${user.id}</small></span></div>`
  : '<small>—</small>');

function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// İki dokunuşlu onay: geri alınamayan işlemler (ban, oda kapatma) yanlışlıkla yapılmasın
function confirmTap(button) {
  if (button.dataset.confirming) return true;
  const original = button.textContent;
  button.dataset.confirming = '1';
  button.textContent = 'Emin misin? Tekrar tıkla';
  setTimeout(() => { delete button.dataset.confirming; button.textContent = original; }, 3000);
  return false;
}

// Basit çubuk + çizgi grafik (SVG). values: [{ label, bars: [..], line }]
function chart(points, { barColors, lineColor }) {
  const width = 720;
  const height = 220;
  const pad = { left: 58, right: 10, top: 12, bottom: 26 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const max = Math.max(1, ...points.map((p) => Math.max(p.bars.reduce((a, b) => a + b, 0), p.line ?? 0)));
  const step = innerW / points.length;
  const barW = Math.max(4, step * 0.6);
  const y = (v) => pad.top + innerH - (v / max) * innerH;
  const grid = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const value = Math.round(max * f);
    return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${y(value)}" y2="${y(value)}" stroke="rgba(255,255,255,0.06)" />
            <text x="${pad.left - 6}" y="${y(value) + 3}" text-anchor="end">${formatCount(value)}</text>`;
  }).join('');
  const bars = points.map((p, i) => {
    let stacked = 0;
    return p.bars.map((value, j) => {
      const top = y(stacked + value);
      const h = y(stacked) - top;
      stacked += value;
      return `<rect x="${pad.left + i * step + (step - barW) / 2}" y="${top}" width="${barW}" height="${Math.max(0, h)}" rx="3" fill="${barColors[j]}"><title>${esc(p.label)}: ${formatCoins(value)}</title></rect>`;
    }).join('');
  }).join('');
  const line = lineColor
    ? `<polyline fill="none" stroke="${lineColor}" stroke-width="2" points="${points.map((p, i) => `${pad.left + i * step + step / 2},${y(p.line)}`).join(' ')}" />`
    : '';
  const labels = points.map((p, i) => (i % Math.ceil(points.length / 10) === 0
    ? `<text x="${pad.left + i * step + step / 2}" y="${height - 8}" text-anchor="middle">${esc(p.label)}</text>` : '')).join('');
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${grid}${bars}${line}${labels}</svg>`;
}

const dayLabel = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });

// ─── Sayfalar ──────────────────────────────────────────────────────────────────

async function overviewPage(main) {
  const [stats, finance] = await Promise.all([api.adminStats(), api.adminFinance(14)]);
  const today = finance.days[finance.days.length - 1];
  const kpis = [
    ['👥', 'Toplam kullanıcı', formatCount(stats.users_total), `bugün +${stats.users_today}`],
    ['🟢', 'Şu an çevrimiçi', formatCount(stats.online_now), ''],
    ['🎙️', 'Açık oda', formatCount(stats.rooms_active), ''],
    ['🪙', 'Bugün satılan coin', formatCoins(stats.coins_sold_today), 'demo: gerçek ödeme yok'],
    ['🎁', 'Bugün hediye (coin)', formatCoins(stats.gift_coins_today), ''],
    ['👑', 'Bugün VIP (coin)', formatCoins(today.vip_coins), ''],
    ['🚩', 'Açık şikâyet', formatCount(stats.open_reports), '', stats.open_reports > 0],
    ['⛔', 'Banlı hesap', formatCount(stats.banned_users), ''],
  ];
  main.innerHTML = `
    <div class="grid grid-kpi">${kpis.map(([icon, label, value, hint, alert]) => `
      <div class="card kpi ${alert ? 'is-alert' : ''}"><span>${icon} ${label}</span><b>${value}</b>${hint ? `<small>${hint}</small>` : ''}</div>`).join('')}</div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card">
        <h2>Son 14 gün <small>coin</small></h2>
        ${chart(finance.days.map((d) => ({ label: dayLabel(d.day), bars: [d.coins_sold], line: d.gift_coins })), { barColors: ['#8b5cff'], lineColor: '#ffc53d' })}
        <div class="legend"><span><i style="background:#8b5cff"></i>Satılan coin</span><span><i style="background:#ffc53d"></i>Hediyeye harcanan</span></div>
      </div>
      <div class="card">
        <h2>Yeni kullanıcılar <small>14 gün</small></h2>
        ${chart(finance.days.map((d) => ({ label: dayLabel(d.day), bars: [d.new_users] })), { barColors: ['#2ee6a6'] })}
      </div>
    </div>
    <div class="grid grid-3" style="margin-top:16px">
      ${rankCard('En çok harcayanlar', finance.top_spenders, '🪙')}
      ${rankCard('En çok kazananlar', finance.top_earners, '💎')}
      <div class="card"><h2>En çok hediye alan odalar <small>bu ay</small></h2>
        <div class="rank-list">${finance.top_rooms.map((r, i) => `
          <div class="rank-row"><span class="no">${i + 1}</span><img class="avatar" src="${esc(r.cover_url)}" alt="" /><b>${esc(r.title)}</b><span class="amount">🪙 ${formatCoins(r.coins)}</span></div>`).join('') || '<p class="empty">Veri yok</p>'}</div>
      </div>
    </div>`;
}

function rankCard(title, rows, unit) {
  return `<div class="card"><h2>${title} <small>14 gün</small></h2><div class="rank-list">${rows.map((row, i) => `
    <div class="rank-row" data-open-user="${row.user.id}" style="cursor:pointer"><span class="no">${i + 1}</span>${avatar(row.user)}<b>${esc(row.user.display_name)}</b><span class="amount">${unit} ${formatCoins(row.amount)}</span></div>`).join('') || '<p class="empty">Veri yok</p>'}</div></div>`;
}

async function financePage(main) {
  let days = 14;
  async function render() {
    const finance = await api.adminFinance(days);
    const sum = (field) => finance.days.reduce((total, d) => total + d[field], 0);
    const totals = Object.entries(finance.totals).sort((a, b) => b[1] - a[1]);
    main.innerHTML = `
      <div class="toolbar">
        <select class="input" id="days">${[7, 14, 30, 90].map((d) => `<option value="${d}" ${d === days ? 'selected' : ''}>Son ${d} gün</option>`).join('')}</select>
        <span class="tag tag-gold">Demo: coin satışında gerçek ödeme alınmıyor</span>
      </div>
      <div class="grid grid-kpi">
        <div class="card kpi"><span>🪙 Satılan coin</span><b>${formatCoins(sum('coins_sold'))}</b></div>
        <div class="card kpi"><span>🎁 Hediyeye harcanan</span><b>${formatCoins(sum('gift_coins'))}</b></div>
        <div class="card kpi"><span>👑 VIP</span><b>${formatCoins(sum('vip_coins'))}</b></div>
        <div class="card kpi"><span>🛍️ Mağaza</span><b>${formatCoins(sum('store_coins'))}</b></div>
        <div class="card kpi"><span>👥 Yeni kullanıcı</span><b>${formatCount(sum('new_users'))}</b></div>
      </div>
      <div class="grid grid-2" style="margin-top:16px">
        <div class="card"><h2>Coin harcama dağılımı <small>günlük</small></h2>
          ${chart(finance.days.map((d) => ({ label: dayLabel(d.day), bars: [d.gift_coins, d.vip_coins, d.store_coins], line: d.coins_sold })), { barColors: ['#ffc53d', '#b14bff', '#3d8bff'], lineColor: '#2ee6a6' })}
          <div class="legend"><span><i style="background:#ffc53d"></i>Hediye</span><span><i style="background:#b14bff"></i>VIP</span><span><i style="background:#3d8bff"></i>Mağaza</span><span><i style="background:#2ee6a6"></i>Satılan coin</span></div>
        </div>
        <div class="card"><h2>İşlem türüne göre toplam</h2>
          <table><tbody>${totals.map(([kind, amount]) => `<tr><td>${esc(TX_LABELS[kind] || kind)}</td><td class="num">${formatCoins(amount)}</td></tr>`).join('')}</tbody></table>
        </div>
      </div>`;
    main.querySelector('#days').addEventListener('change', (event) => { days = Number(event.target.value); render(); });
  }
  await render();
}

async function transactionsPage(main, { userId = '' } = {}) {
  let filters = { type: '', userId };
  let rows = [];
  main.innerHTML = `
    <div class="toolbar">
      <select class="input" id="tx-type"><option value="">Bütün türler</option>${Object.entries(TX_LABELS).map(([id, label]) => `<option value="${id}">${label}</option>`).join('')}</select>
      <input class="input" id="tx-user" type="number" placeholder="Kullanıcı ID" value="${esc(userId)}" />
      <button class="btn" id="tx-apply">Süz</button>
    </div>
    <div class="card table-wrap"><table>
      <thead><tr><th>#</th><th>Kullanıcı</th><th>Tür</th><th>Açıklama</th><th class="num">Tutar</th><th class="num">Sonraki bakiye</th><th>Zaman</th></tr></thead>
      <tbody id="tx-body"></tbody></table>
      <div class="more"><button class="btn btn-sm" id="tx-more">Daha eski</button></div>
    </div>`;
  const body = main.querySelector('#tx-body');
  const draw = () => {
    body.innerHTML = rows.map((t) => `
      <tr><td><small>${t.id}</small></td><td>${userCell(t.user)}</td><td><span class="tag">${esc(TX_LABELS[t.type] || t.type)}</span></td>
      <td>${esc(t.label)}</td><td class="num">${signed(t.amount)} ${t.currency === 'coin' ? '🪙' : '💎'}</td>
      <td class="num">${formatCoins(t.balance_after)}</td><td><small>${dateTime(t.created_at)}</small></td></tr>`).join('')
      || '<tr><td colspan="7" class="empty">Kayıt yok</td></tr>';
  };
  async function load(append = false) {
    const page = await api.adminTransactions({ ...filters, beforeId: append ? rows[rows.length - 1]?.id : '' });
    rows = append ? rows.concat(page) : page;
    main.querySelector('#tx-more').hidden = page.length < 50;
    draw();
  }
  main.querySelector('#tx-apply').addEventListener('click', () => {
    filters = { type: main.querySelector('#tx-type').value, userId: main.querySelector('#tx-user').value };
    load();
  });
  main.querySelector('#tx-more').addEventListener('click', () => load(true));
  await load();
}

async function usersPage(main) {
  let query = '';
  let sort = 'newest';
  main.innerHTML = `
    <div class="toolbar">
      <input class="input input-wide" id="user-search" type="search" placeholder="Ad, @kullanıcı adı, e-posta ya da ID" />
      <select class="input" id="user-sort">
        <option value="newest">En yeni üyeler</option><option value="richest">En çok coin</option><option value="reported">En çok şikâyet</option>
      </select>
    </div>
    <div class="card table-wrap"><table>
      <thead><tr><th>Kullanıcı</th><th>Durum</th><th class="num">Coin</th><th class="num">Elmas</th><th>Seviye</th><th>VIP</th><th>Aile</th><th class="num">Şikâyet</th></tr></thead>
      <tbody id="user-body"></tbody></table></div>`;
  let requestId = 0;
  async function load() {
    const id = ++requestId;
    const users = await api.adminUsers(query, sort);
    if (id !== requestId) return;
    main.querySelector('#user-body').innerHTML = users.map((u) => `
      <tr class="is-clickable" data-open-user="${u.user.id}">
        <td>${userCell(u.user)}</td>
        <td>${u.is_active ? '<span class="tag tag-green">Aktif</span>' : '<span class="tag tag-red">Banlı</span>'}${u.is_admin ? ' <span class="tag tag-purple">Yönetici</span>' : ''}</td>
        <td class="num">${formatCoins(u.coin_balance)}</td><td class="num">${formatCoins(u.diamond_balance)}</td>
        <td>Lv.${u.user.level}</td><td>${u.user.vip_level ? `<span class="tag tag-gold">VIP ${u.user.vip_level}</span>` : '—'}</td>
        <td>${u.user.family ? `${esc(u.user.family.badge)} ${esc(u.user.family.name)}` : '—'}</td>
        <td class="num">${u.reports_against ? `<span class="tag tag-red">${u.reports_against}</span>` : '0'}</td>
      </tr>`).join('') || '<tr><td colspan="8" class="empty">Kimse bulunamadı</td></tr>';
  }
  let debounce;
  main.querySelector('#user-search').addEventListener('input', (event) => {
    query = event.target.value.trim();
    clearTimeout(debounce);
    debounce = setTimeout(load, 250);
  });
  main.querySelector('#user-sort').addEventListener('change', (event) => { sort = event.target.value; load(); });
  await load();
}

// Kullanıcı detayı: sağdan açılan panel (bakiye, işlemler, sohbetler, ban, bakiye düzeltme, VIP verme)
async function openUserDrawer(userId) {
  closeDrawer();
  const backdrop = document.createElement('div');
  backdrop.className = 'drawer-backdrop';
  const drawer = document.createElement('aside');
  drawer.className = 'drawer';
  drawer.innerHTML = '<p class="empty">Yükleniyor...</p>';
  document.body.append(backdrop, drawer);
  backdrop.addEventListener('click', closeDrawer);

  async function render() {
    const [d, conversations] = await Promise.all([api.adminUser(userId), api.adminConversations(userId)]);
    drawer.innerHTML = `
      <div class="drawer-head">
        ${avatar(d.user, 'avatar-lg')}
        <span><h2>${esc(d.user.display_name)}</h2><small>@${esc(d.user.username)} · ID ${d.user.id}${d.email ? ` · ${esc(d.email)}` : ''}</small>
        <span>${d.is_active ? '<span class="tag tag-green">Aktif</span>' : '<span class="tag tag-red">Banlı</span>'} ${d.user.vip_level ? `<span class="tag tag-gold">VIP ${d.user.vip_level}</span>` : ''} <span class="tag">Lv.${d.user.level}</span></span></span>
        <button class="btn btn-sm" data-close-drawer>✕</button>
      </div>
      <div class="balances">
        <div><small>Coin</small><b>🪙 ${formatCoins(d.coin_balance)}</b></div>
        <div><small>Elmas</small><b>💎 ${formatCoins(d.diamond_balance)}</b></div>
        <div><small>Şikâyet</small><b>🚩 ${d.reports_against}</b></div>
      </div>
      <div class="card"><h2>İşlemler</h2>
        <div class="form-row">
          ${d.is_admin ? '' : `<button class="btn ${d.is_active ? 'btn-danger' : 'btn-primary'}" data-user-act="${d.is_active ? 'ban' : 'unban'}">${d.is_active ? 'Banla' : 'Banı kaldır'}</button>`}
          <a class="btn" href="index.html#/profile/${d.user.id}" target="_blank" rel="noopener">Uygulamada aç</a>
          <button class="btn" data-goto-tx="${d.user.id}">Bütün para hareketleri</button>
        </div>
        ${d.is_admin ? '' : '<input class="input" id="ban-reason" placeholder="Ban gerekçesi (zorunlu)" style="margin-top:8px;width:100%" />'}
      </div>
      <form class="card" id="adjust-form"><h2>Bakiye düzeltme <small>deftere yazılır</small></h2>
        <div class="form-row">
          <select class="input" name="currency" style="flex:none"><option value="coin">Coin</option><option value="diamond">Elmas</option></select>
          <input class="input" name="amount" type="number" placeholder="+500 ekle / -500 düş" required />
        </div>
        <div class="form-row" style="margin-top:8px"><input class="input" name="reason" minlength="3" maxlength="200" placeholder="Gerekçe" required /><button class="btn btn-primary">Uygula</button></div>
      </form>
      <form class="card" id="vip-form"><h2>VIP ver <small>ücretsiz, eşyalarıyla</small></h2>
        <div class="form-row">
          <select class="input" name="level"><option value="1">VIP 1 · Gümüş</option><option value="2">VIP 2 · Altın</option><option value="3">VIP 3 · Elmas</option></select>
          <input class="input" name="days" type="number" min="1" max="365" value="30" />
          <button class="btn btn-primary">Ver</button>
        </div>
      </form>
      <div class="card"><h2>Özel sohbetleri <small>${conversations.length}</small></h2>
        ${conversations.map((c) => {
          const other = c.users.find((u) => u.id !== d.user.id) || c.users[0];
          return `<button class="conv" data-open-conv="${c.id}">${avatar(other)}<span><b>${esc(other?.display_name || '—')}</b><small>${esc(c.last_message_text || '')}</small></span><small style="margin-left:auto">${c.message_count} mesaj</small></button>`;
        }).join('') || '<p class="empty">Sohbet yok</p>'}
      </div>
      <div class="card"><h2>Son hareketler</h2><table><tbody>${d.recent_transactions.map((t) => `
        <tr><td>${esc(t.label)}<br /><small>${dateTime(t.created_at)}</small></td><td class="num">${signed(t.amount)} ${t.currency === 'coin' ? '🪙' : '💎'}</td></tr>`).join('') || '<tr><td class="empty">Hareket yok</td></tr>'}</tbody></table></div>`;
  }

  drawer.addEventListener('click', async (event) => {
    if (event.target.closest('[data-close-drawer]')) return closeDrawer();
    const conv = event.target.closest('[data-open-conv]');
    if (conv) { closeDrawer(); return navigate('messages', { conversationId: Number(conv.dataset.openConv) }); }
    const tx = event.target.closest('[data-goto-tx]');
    if (tx) { closeDrawer(); return navigate('transactions', { userId: tx.dataset.gotoTx }); }
    const button = event.target.closest('[data-user-act]');
    if (!button) return;
    try {
      if (button.dataset.userAct === 'ban') {
        const reason = drawer.querySelector('#ban-reason').value.trim();
        if (reason.length < 3) return toast('Ban gerekçesi yaz (en az 3 harf).', 'error');
        if (!confirmTap(button)) return;
        await api.adminBan(userId, reason);
        toast('Kullanıcı banlandı; oturumları kapatıldı', 'success');
      } else {
        await api.adminUnban(userId);
        toast('Ban kaldırıldı', 'success');
      }
      await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
  drawer.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      if (form.id === 'adjust-form') {
        const result = await api.adminAdjustBalance(userId, {
          currency: form.elements.currency.value, amount: Number(form.elements.amount.value), reason: form.elements.reason.value,
        });
        toast(`Yeni bakiye: ${formatCoins(result.balance)}`, 'success');
      } else {
        await api.adminGrantVip(userId, Number(form.elements.level.value), Number(form.elements.days.value));
        toast('VIP verildi', 'success');
      }
      await render();
    } catch (error) {
      toast(error.code === 'insufficient_balance' ? 'Bakiye bu kadar düşmeye yetmiyor.' : error.message, 'error');
    }
  });
  await render();
}

function closeDrawer() {
  document.querySelectorAll('.drawer, .drawer-backdrop').forEach((el) => el.remove());
}

function threadHtml(messages, rightUserId) {
  return messages.map((m) => `
    <div class="msg ${m.sender?.id === rightUserId ? 'is-right' : ''} ${m.deleted_at ? 'is-deleted' : ''}">
      ${avatar(m.sender)}
      <div><b>${esc(m.sender?.display_name || '—')}</b><small>${dateTime(m.created_at)}${m.deleted_at ? ' · odadan silindi' : ''}</small><p>${esc(m.text)}</p></div>
    </div>`).join('') || '<p class="empty">Mesaj yok</p>';
}

async function messagesPage(main, { conversationId = null } = {}) {
  main.innerHTML = `
    <div class="privacy-note">⚠️ Demo ayarı: yöneticiler bütün özel mesajları görebiliyor. Her açılış denetim kaydına yazılır.
    Canlıya çıkmadan önce yalnızca şikâyet edilen sohbetlere erişim ve gizlilik metninde bilgilendirme gerekir (KVKK).</div>
    <div class="inbox">
      <div class="card">
        <div class="toolbar" style="padding:12px;margin:0"><input class="input input-wide" id="conv-user" type="number" placeholder="Kullanıcı ID ile süz" /></div>
        <div class="inbox-list" id="conv-list"></div>
      </div>
      <div class="card"><div class="thread-head" id="thread-head">Bir sohbet seç</div><div class="thread" id="thread"></div></div>
    </div>`;
  const listEl = main.querySelector('#conv-list');
  let conversations = [];
  async function loadList(userId = '') {
    conversations = await api.adminConversations(userId);
    listEl.innerHTML = conversations.map((c) => `
      <button class="conv" data-conv="${c.id}">
        <span class="avatars">${c.users.map((u) => avatar(u)).join('')}</span>
        <span><b>${c.users.map((u) => esc(u.display_name)).join(' & ')}</b><small>${esc(c.last_message_text || '')}</small></span>
        <small style="margin-left:auto">${c.message_count}</small>
      </button>`).join('') || '<p class="empty">Sohbet yok</p>';
  }
  async function open(id) {
    listEl.querySelectorAll('[data-conv]').forEach((b) => b.classList.toggle('is-active', Number(b.dataset.conv) === id));
    const conv = conversations.find((c) => c.id === id);
    const messages = await api.adminConversationMessages(id);
    main.querySelector('#thread-head').innerHTML = conv ? `${conv.users.map((u) => `${avatar(u)} ${esc(u.display_name)}`).join(' ↔ ')}` : `Sohbet #${id}`;
    const thread = main.querySelector('#thread');
    thread.innerHTML = threadHtml(messages, conv?.users[1]?.id);
    thread.scrollTop = thread.scrollHeight;
  }
  listEl.addEventListener('click', (event) => {
    const button = event.target.closest('[data-conv]');
    if (button) open(Number(button.dataset.conv));
  });
  let debounce;
  main.querySelector('#conv-user').addEventListener('input', (event) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => loadList(event.target.value.trim()), 300);
  });
  await loadList();
  if (conversationId) await open(conversationId);
}

async function roomsPage(main) {
  async function render() {
    const rooms = await api.adminRooms();
    main.innerHTML = `
      <div class="card table-wrap"><table>
        <thead><tr><th>Oda</th><th>Sahibi</th><th class="num">İçeride</th><th>Durum</th><th>Açılış</th><th></th></tr></thead>
        <tbody>${rooms.map((r) => `
          <tr><td><b>${esc(r.title)}</b><br /><small>ID ${r.id}</small></td><td>${userCell(r.host)}</td><td class="num">${r.listener_count}</td>
          <td>${r.is_live ? '<span class="tag tag-red">CANLI</span>' : '<span class="tag">Açık</span>'}</td><td><small>${dateTime(r.created_at)}</small></td>
          <td class="num"><button class="btn btn-sm" data-room-log="${r.id}" data-title="${esc(r.title)}">Sohbet geçmişi</button>
            <a class="btn btn-sm" href="index.html#/room/${r.id}" target="_blank" rel="noopener">Odaya git</a>
            <button class="btn btn-sm btn-danger" data-close-room="${r.id}">Kapat</button></td></tr>`).join('') || '<tr><td colspan="6" class="empty">Açık oda yok</td></tr>'}</tbody>
      </table></div>
      <div class="card" id="room-log" style="margin-top:16px" hidden></div>`;
  }
  main.onclick = async (event) => {
    const log = event.target.closest('[data-room-log]');
    if (log) {
      const messages = await api.adminRoomMessages(Number(log.dataset.roomLog));
      const box = main.querySelector('#room-log');
      box.hidden = false;
      box.innerHTML = `<h2>${esc(log.dataset.title)} · sohbet geçmişi <small>${messages.length} mesaj · üstü çizili: odadan silinmiş</small></h2><div class="thread" style="max-height:460px">${threadHtml(messages)}</div>`;
      box.scrollIntoView({ behavior: 'smooth' });
      return;
    }
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

async function reportsPage(main) {
  let status = 'open';
  async function render() {
    const reports = await api.adminReports(status);
    main.innerHTML = `
      <div class="toolbar">
        <button class="btn ${status === 'open' ? 'btn-primary' : ''}" data-status="open">Açık</button>
        <button class="btn ${status === 'closed' ? 'btn-primary' : ''}" data-status="closed">Karara bağlanan</button>
      </div>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(340px,1fr))">${reports.map((r) => `
        <div class="card report">
          <header><span class="tag tag-red">${esc(REASON_LABELS[r.reason] || r.reason)}</span>
            <b>${r.target_type === 'user' ? '👤' : '🎙️'} ${esc(r.target_label)}</b><small style="margin-left:auto;color:var(--muted)">#${r.id}</small></header>
          ${r.details ? `<p>${esc(r.details)}</p>` : ''}
          <small style="color:var(--muted)">Şikâyet eden: ${esc(r.reporter?.display_name || '—')} · ${dateTime(r.created_at)}</small>
          ${r.status === 'open' ? `
            <input class="input" data-note="${r.id}" placeholder="Karar notu (ban için zorunlu)" />
            <div class="actions">
              <button class="btn btn-sm" data-resolve="dismiss" data-id="${r.id}">Reddet</button>
              ${r.target_type === 'user'
                ? `<button class="btn btn-sm" data-open-user="${r.target_id}">Kullanıcıyı incele</button><button class="btn btn-sm btn-danger" data-resolve="ban_user" data-id="${r.id}">Banla</button>`
                : `<button class="btn btn-sm btn-danger" data-resolve="close_room" data-id="${r.id}">Odayı kapat</button>`}
            </div>` : `<span class="tag tag-green">${ACTION_LABELS[r.action] || r.status}${r.resolution_note ? ` · ${esc(r.resolution_note)}` : ''}</span>`}
        </div>`).join('') || '<div class="card empty">Burada şikâyet yok 🎉</div>'}</div>`;
  }
  main.onclick = async (event) => {
    const filter = event.target.closest('[data-status]');
    if (filter) { status = filter.dataset.status; return render(); }
    const button = event.target.closest('[data-resolve]');
    if (!button) return;
    const note = main.querySelector(`[data-note="${button.dataset.id}"]`)?.value.trim() || '';
    if (button.dataset.resolve === 'ban_user' && note.length < 3) return toast('Ban için karar notu yaz.', 'error');
    if (button.dataset.resolve !== 'dismiss' && !confirmTap(button)) return;
    try {
      await api.adminResolveReport(Number(button.dataset.id), button.dataset.resolve, note);
      toast('Şikâyet karara bağlandı', 'success');
      await render();
      refreshBadges();
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  await render();
}

async function catalogPage(main) {
  async function render() {
    const [gifts, packages] = await Promise.all([api.adminGifts(), api.adminPackages()]);
    main.innerHTML = `
      <div class="grid grid-2">
        <div class="card table-wrap"><h2>Hediyeler <small>fiyat coin</small></h2><table>
          <thead><tr><th>Hediye</th><th class="num">Fiyat</th><th>Şanslı</th><th>Satışta</th><th></th></tr></thead>
          <tbody>${gifts.map((g) => `
            <tr data-gift="${g.id}"><td>${g.emoji} <b>${esc(g.name)}</b></td>
            <td class="num"><input class="input input-inline" type="number" min="1" value="${g.price}" data-field="price" /></td>
            <td><input type="checkbox" data-field="is_lucky" ${g.is_lucky ? 'checked' : ''} /></td>
            <td><input type="checkbox" data-field="is_active" ${g.is_active ? 'checked' : ''} /></td>
            <td><button class="btn btn-sm" data-save-gift>Kaydet</button></td></tr>`).join('')}</tbody></table></div>
        <div class="card table-wrap"><h2>Coin paketleri</h2><table>
          <thead><tr><th>Paket</th><th class="num">Coin</th><th class="num">Bonus</th><th>Fiyat</th><th>Satışta</th><th></th></tr></thead>
          <tbody>${packages.map((p) => `
            <tr data-package="${p.id}"><td><b>${esc(p.title || `Paket ${p.id}`)}</b>${p.is_popular ? ' <span class="tag tag-purple">Popüler</span>' : ''}</td>
            <td class="num"><input class="input input-inline" type="number" min="1" value="${p.coins}" data-field="coins" /></td>
            <td class="num"><input class="input input-inline" type="number" min="0" value="${p.bonus}" data-field="bonus" /></td>
            <td><input class="input input-inline" value="${esc(p.price_label)}" data-field="price_label" /></td>
            <td><input type="checkbox" data-field="is_active" ${p.is_active ? 'checked' : ''} /></td>
            <td><button class="btn btn-sm" data-save-package>Kaydet</button></td></tr>`).join('')}</tbody></table>
          <p style="margin-top:10px;color:var(--muted);font-size:12px">Fiyat etiketi yalnızca gösterim; gerçek ücreti mağaza (App Store / Google Play) belirler.</p></div>
      </div>`;
  }
  // Satırdaki alanları { alan: değer } olarak toplar
  const collect = (row) => Object.fromEntries([...row.querySelectorAll('[data-field]')].map((input) => [
    input.dataset.field, input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value,
  ]));
  main.onclick = async (event) => {
    const giftBtn = event.target.closest('[data-save-gift]');
    const packageBtn = event.target.closest('[data-save-package]');
    if (!giftBtn && !packageBtn) return;
    const row = event.target.closest('tr');
    try {
      if (giftBtn) await api.adminUpdateGift(Number(row.dataset.gift), collect(row));
      else await api.adminUpdatePackage(Number(row.dataset.package), collect(row));
      toast('Kaydedildi; kullanıcılar yeni değeri hemen görür', 'success');
    } catch (error) {
      toast(error.message, 'error');
    }
  };
  await render();
}

async function agenciesPage(main) {
  async function render() {
    const agencies = await api.adminAgencies();
    main.innerHTML = `
      <div class="grid grid-2">
        <div class="card table-wrap"><h2>Ajanslar</h2><table>
          <thead><tr><th>Ajans</th><th>Sahibi</th><th class="num">Yayıncı</th><th class="num">Komisyon</th></tr></thead>
          <tbody>${agencies.map((a) => `<tr><td><b>🏢 ${esc(a.name)}</b></td><td>${userCell(a.owner)}</td><td class="num">${a.member_count}</td><td class="num">%${a.commission_percent}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Ajans yok</td></tr>'}</tbody>
        </table></div>
        <form class="card" id="agency-form"><h2>Yeni ajans</h2>
          <div class="grid" style="gap:10px">
            <input class="input" name="name" minlength="2" maxlength="40" placeholder="Ajans adı" required />
            <input class="input" name="owner_id" type="number" placeholder="Sahibinin kullanıcı ID'si" required />
            <input class="input" name="commission" type="number" min="0" max="50" value="10" placeholder="Komisyon %" />
            <button class="btn btn-primary">Ajans kur</button>
          </div>
        </form>
      </div>`;
    main.querySelector('#agency-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.target;
      try {
        await api.adminCreateAgency({ name: form.elements.name.value, owner_id: Number(form.elements.owner_id.value), commission_percent: Number(form.elements.commission.value) });
        toast('Ajans kuruldu', 'success');
        await render();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }
  await render();
}

async function broadcastPage(main) {
  main.innerHTML = `
    <form class="card" id="broadcast-form" style="max-width:640px"><h2>Bütün kullanıcılara duyuru</h2>
      <p style="color:var(--muted);margin-bottom:12px">Bildirim merkezine düşer; uygulamada olanlar anında görür. Uygulama kapalıyken bildirim (push) henüz yok.</p>
      <textarea class="input" name="text" minlength="3" maxlength="200" placeholder="Ör. Bu akşam 21:00'de büyük hediye etkinliği başlıyor!" required></textarea>
      <div class="form-row" style="margin-top:12px"><button class="btn btn-primary">Gönder</button></div>
    </form>`;
  main.querySelector('#broadcast-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = event.target.querySelector('button');
    if (!confirmTap(button)) return;
    try {
      const result = await api.adminBroadcast(event.target.elements.text.value);
      toast(`${result.sent} kişiye gönderildi`, 'success');
      event.target.reset();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

const RENDERERS = {
  overview: overviewPage, finance: financePage, transactions: transactionsPage, users: usersPage, messages: messagesPage,
  rooms: roomsPage, reports: reportsPage, catalog: catalogPage, agencies: agenciesPage, broadcast: broadcastPage,
};

// ─── Çerçeve: menü, sayfa değiştirme, giriş ─────────────────────────────────────
let me = null;

function shell() {
  appEl.innerHTML = `
    <nav class="sidebar">
      <div class="brand"><i>M</i> Muti Yönetim</div>
      ${PAGES.map((p) => `<button class="nav-item" data-page="${p.id}">${p.icon} ${p.label}${p.id === 'reports' ? '<b id="report-badge" hidden></b>' : ''}</button>`).join('')}
      <div class="sidebar-foot">
        <span>${avatar(me)} ${esc(me.display_name)}</span>
        <a href="index.html" target="_blank" rel="noopener">Uygulamayı aç ↗</a>
        <button class="nav-item" data-logout>Çıkış yap</button>
      </div>
    </nav>
    <main class="main"><div class="topline"><h1 id="page-title"></h1><span class="spacer"></span></div><div id="page"></div></main>`;
  appEl.querySelector('.sidebar').addEventListener('click', async (event) => {
    if (event.target.closest('[data-logout]')) { await api.logout(); return location.reload(); }
    const item = event.target.closest('[data-page]');
    if (item) navigate(item.dataset.page);
  });
  // Herhangi bir sayfada kullanıcıya tıklanınca detay paneli açılır
  appEl.addEventListener('click', (event) => {
    const user = event.target.closest('[data-open-user]');
    if (user && !event.target.closest('.drawer')) openUserDrawer(Number(user.dataset.openUser));
  });
}

async function refreshBadges() {
  try {
    const stats = await api.adminStats();
    const badge = document.getElementById('report-badge');
    badge.textContent = stats.open_reports;
    badge.hidden = !stats.open_reports;
  } catch { /* rozet olmasa da panel çalışır */ }
}

async function navigate(pageId, options = {}) {
  const page = PAGES.find((p) => p.id === pageId) || PAGES[0];
  history.replaceState(null, '', `#${page.id}`);
  appEl.querySelectorAll('[data-page]').forEach((b) => b.classList.toggle('is-active', b.dataset.page === page.id));
  document.getElementById('page-title').textContent = page.label;
  const main = document.getElementById('page');
  main.onclick = null;
  main.innerHTML = '<p class="empty">Yükleniyor...</p>';
  try {
    await RENDERERS[page.id](main, options);
  } catch (error) {
    main.innerHTML = `<div class="card empty">${esc(error.message)}</div>`;
  }
}

function loginScreen(message = '') {
  appEl.innerHTML = `
    <div class="login"><form id="login-form">
      <h1>Muti Yönetim</h1>
      <p>${message || 'Yönetici hesabınla giriş yap.'}</p>
      <input class="input" name="username" placeholder="Kullanıcı adı" autocomplete="username" required />
      <input class="input" name="password" type="password" placeholder="Şifre" autocomplete="current-password" required />
      <button class="btn btn-primary">Giriş yap</button>
    </form></div>`;
  appEl.querySelector('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await api.login({ username: event.target.elements.username.value, password: event.target.elements.password.value });
      start();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

async function start() {
  if (!api.isAuthenticated()) return loginScreen();
  try {
    me = await api.getMe();
  } catch {
    return loginScreen();
  }
  if (!me.is_admin) return loginScreen('Bu hesap yönetici değil. Yönetici hesabıyla giriş yap.');
  shell();
  refreshBadges();
  navigate(location.hash.slice(1) || 'overview');
}

start();
