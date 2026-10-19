// Etkinlikler: süren / yaklaşan / biten kampanyalar, ödüller ve etkinlik sıralaması
import { api } from '../api.js';
import { esc, icon, framedAvatar, formatCoins } from '../ui.js';

const STATUS_LABELS = { active: 'Sürüyor', upcoming: 'Yakında', ended: 'Bitti' };
const METRIC_LABELS = { gifts_sent: 'En çok hediye gönderen', gifts_received: 'En çok hediye alan' };

// "2 gün 5 saat" gibi kalan süre
function remaining(iso) {
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return 'bitti';
  const hours = Math.floor(ms / 3600000);
  const days = Math.floor(hours / 24);
  if (days) return `${days} gün ${hours % 24} saat`;
  const minutes = Math.floor((ms % 3600000) / 60000);
  return hours ? `${hours} saat ${minutes} dk` : `${minutes} dk`;
}

function timeLabel(event) {
  if (event.status === 'active') return `Bitmesine ${remaining(event.ends_at)}`;
  if (event.status === 'upcoming') return `Başlamasına ${remaining(event.starts_at)}`;
  return new Date(event.ends_at).toLocaleDateString('tr-TR');
}

function eventCard(event) {
  return `
    <a class="event-card event-${event.status}" href="#/event/${event.id}">
      <span class="event-emoji">${event.emoji}</span>
      <span class="member-info">
        <b>${esc(event.title)}</b>
        <small>${METRIC_LABELS[event.metric]} · 1. ödül 🪙 ${formatCoins(event.rewards[0] || 0)}</small>
        <small class="event-time">${timeLabel(event)}</small>
      </span>
      <span class="event-status">${STATUS_LABELS[event.status]}</span>
    </a>`;
}

export async function renderEvents(root) {
  const events = await api.listEvents();
  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Etkinlikler</h1>
      <span></span>
    </header>
    <section class="section event-list">
      ${events.length ? events.map(eventCard).join('') : '<div class="empty"><p>Şu an etkinlik yok.</p></div>'}
    </section>`;
}

function entryRow(entry, unit, extraClass = '') {
  return `
    <a class="board-row ${extraClass}" href="#/profile/${entry.user.id}">
      <span class="board-rank">${entry.rank <= 3 ? ['🥇', '🥈', '🥉'][entry.rank - 1] : entry.rank}</span>
      ${framedAvatar(entry.user, 'avatar-md')}
      <span class="member-info"><b>${esc(entry.user.display_name)}</b></span>
      <b class="board-score">${unit} ${formatCoins(entry.score)}</b>
    </a>`;
}

export async function renderEvent(root, { params }) {
  const event = await api.getEvent(params[0]);
  const unit = event.metric === 'gifts_received' ? '💎' : '🪙';
  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/events" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Etkinlik</h1>
      <span></span>
    </header>
    <section class="event-hero event-${event.status}">
      <span class="event-emoji event-emoji-lg">${event.emoji}</span>
      <h2>${esc(event.title)}</h2>
      <p>${esc(event.description)}</p>
      <span class="event-status">${STATUS_LABELS[event.status]} · <span id="event-time">${timeLabel(event)}</span></span>
    </section>
    <section class="section">
      <div class="section-head"><h2>Ödüller</h2><small>${METRIC_LABELS[event.metric]}</small></div>
      <div class="event-rewards">
        ${event.rewards.map((coins, i) => `<div><i>${['🥇', '🥈', '🥉'][i] || `${i + 1}.`}</i><b>🪙 ${formatCoins(coins)}</b></div>`).join('')}
      </div>
    </section>
    <section class="section">
      <div class="section-head"><h2>Sıralama</h2></div>
      ${event.entries.length
        ? `<div class="board-list">${event.entries.map((e) => entryRow(e, unit)).join('')}</div>`
        : '<p class="member-empty">Henüz kimse yok. Bir odada hediye göndererek yarışa katıl!</p>'}
      ${event.me && event.me.rank > event.entries.length ? `<div class="board-me">${entryRow(event.me, unit, 'is-me')}</div>` : ''}
    </section>`;

  // Kalan süre dakikada bir güncellenir
  const timer = setInterval(() => {
    const el = root.querySelector('#event-time');
    if (el) el.textContent = timeLabel(event);
  }, 60000);
  return () => clearInterval(timer);
}
