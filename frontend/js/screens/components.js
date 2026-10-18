// Birden fazla ekranda kullanılan kart bileşenleri
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins } from '../ui.js';

export function roomRow(room) {
  return `
    <a class="room-row" href="#/room/${room.id}">
      <img class="room-row-cover" src="${esc(room.cover_url)}" alt="" loading="lazy" />
      <div class="room-row-body">
        <h3>${esc(room.title)} ${room.is_live ? '<span class="pill pill-live">CANLI</span>' : ''}</h3>
        <p>${esc(room.host.display_name)} • ${CATEGORY_LABELS[room.category]}</p>
        <div class="avatar-stack">${room.seats.filter((s) => s.user).slice(0, 5).map((s) => avatarImg(s.user, 'avatar-xs')).join('')}</div>
      </div>
      <span class="room-row-count"><span class="eq"><i></i><i></i><i></i></span>${room.listener_count}</span>
    </a>`;
}

export function chips(items, activeId) {
  return `<div class="chips">${items.map((item) => (
    `<button class="chip ${item.id === activeId ? 'is-active' : ''}" data-chip="${item.id}">${item.label}</button>`
  )).join('')}</div>`;
}

export function coinPill(balance) {
  return `<a class="coin-pill" href="#/wallet"><span class="coin"></span><b>${formatCoins(balance)}</b><span class="coin-plus">+</span></a>`;
}
