// Sıralama: zenginler, çekiciler, odalar, aileler × bugün, bu hafta, bu ay
import { api } from '../api.js';
import { esc, icon, framedAvatar, formatCoins } from '../ui.js';

const KINDS = [
  { id: 'rich', label: 'Zenginler', unit: '🪙' },
  { id: 'charm', label: 'Çekiciler', unit: '💎' },
  { id: 'rooms', label: 'Odalar', unit: '🪙' },
  { id: 'families', label: 'Aileler', unit: '🪙' },
];
const PERIODS = [
  { id: 'day', label: 'Bugün' },
  { id: 'week', label: 'Bu hafta' },
  { id: 'month', label: 'Bu ay' },
];

// Sıradaki öğenin görseli, adı ve tıklayınca gideceği yer (kişi, oda ya da aile)
function describe(entry) {
  if (entry.user) {
    return { href: `#/profile/${entry.user.id}`, image: framedAvatar(entry.user, 'avatar-md'), name: entry.user.display_name, badge: entry.user.family?.badge };
  }
  if (entry.room) {
    return { href: `#/room/${entry.room.id}`, image: `<img class="avatar avatar-md board-cover" src="${esc(entry.room.cover_url)}" alt="" />`, name: entry.room.title };
  }
  return { href: `#/family/${entry.family.id}`, image: `<span class="board-badge">${esc(entry.family.badge)}</span>`, name: entry.family.name };
}

function podium(entries, unit) {
  // Kürsü: 2. solda, 1. ortada (yüksek), 3. sağda
  const order = [entries[1], entries[0], entries[2]].filter(Boolean);
  return `
    <div class="podium">
      ${order.map((entry) => {
        const d = describe(entry);
        return `
          <a class="podium-place podium-${entry.rank}" href="${d.href}">
            <span class="podium-crown">${['👑', '🥈', '🥉'][entry.rank - 1]}</span>
            ${d.image}
            <b>${esc(d.name)}</b>
            <small>${unit} ${formatCoins(entry.score)}</small>
          </a>`;
      }).join('')}
    </div>`;
}

function row(entry, unit, extraClass = '') {
  const d = describe(entry);
  return `
    <a class="board-row ${extraClass}" href="${d.href}">
      <span class="board-rank">${entry.rank}</span>
      ${d.image}
      <span class="member-info"><b>${esc(d.name)} ${d.badge ? `<span class="family-chip">${esc(d.badge)}</span>` : ''}</b></span>
      <b class="board-score">${unit} ${formatCoins(entry.score)}</b>
    </a>`;
}

export async function renderLeaderboard(root, { query }) {
  let kind = KINDS.some((k) => k.id === query.kind) ? query.kind : 'rich';
  let period = 'week';

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Sıralama</h1>
      <a class="icon-btn icon-btn-plain" href="#/events" aria-label="Etkinlikler">${icon('trophy', 20)}</a>
    </header>
    <div class="segmented board-kinds">${KINDS.map((k) => `<button data-kind="${k.id}">${k.label}</button>`).join('')}</div>
    <div class="chips board-periods">${PERIODS.map((p) => `<button class="chip" data-period="${p.id}">${p.label}</button>`).join('')}</div>
    <div id="board"></div>`;
  const boardEl = root.querySelector('#board');
  let requestId = 0;

  async function load() {
    root.querySelectorAll('[data-kind]').forEach((b) => b.classList.toggle('is-active', b.dataset.kind === kind));
    root.querySelectorAll('[data-period]').forEach((b) => b.classList.toggle('is-active', b.dataset.period === period));
    const id = ++requestId;
    boardEl.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    const board = await api.getLeaderboard(kind, period);
    if (id !== requestId) return;
    const unit = KINDS.find((k) => k.id === kind).unit;
    boardEl.innerHTML = board.entries.length
      ? `${podium(board.entries.slice(0, 3), unit)}
         <div class="board-list">${board.entries.slice(3).map((e) => row(e, unit)).join('')}</div>
         ${board.me && board.me.rank > 3 ? `<div class="board-me">${row(board.me, unit, 'is-me')}</div>` : ''}`
      : '<div class="empty"><p>Bu dönemde henüz kimse yok. İlk sen ol!</p></div>';
  }

  root.addEventListener('click', (event) => {
    const kindBtn = event.target.closest('[data-kind]');
    const periodBtn = event.target.closest('[data-period]');
    if (kindBtn) kind = kindBtn.dataset.kind;
    if (periodBtn) period = periodBtn.dataset.period;
    if (kindBtn || periodBtn) load();
  });
  await load();
}

