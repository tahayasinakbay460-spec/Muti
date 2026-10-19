// Keşfet: oda ve kişi arama, oda kategori filtresi
import { api } from '../api.js';
import { ROOM_CATEGORIES } from '../config.js';
import { esc, icon, avatarImg, joinParts, levelBadge } from '../ui.js';
import { roomRow, chips } from './components.js';

function userRow(user) {
  return `
    <a class="member-row user-row" href="#/profile/${user.id}">
      ${avatarImg(user, 'avatar-md')}
      <span class="member-info">
        <b>${esc(user.display_name)} ${levelBadge(user.level)}</b>
        <small>${esc(joinParts([`@${user.username}`, `ID ${user.id}`, user.city]))}</small>
      </span>
      ${user.is_online ? '<span class="online-dot" title="Çevrimiçi"></span>' : ''}
    </a>`;
}

export async function renderExplore(root, { query }) {
  let mode = query.mode === 'people' ? 'people' : 'rooms';
  let activeCategory = ROOM_CATEGORIES.some((c) => c.id === query.category) ? query.category : 'for_you';
  let searchText = '';

  root.innerHTML = `
    <header class="topbar"><h1 class="page-title">Keşfet</h1></header>
    <div class="segmented explore-modes">
      <button data-mode="rooms">Odalar</button>
      <button data-mode="people">Kişiler</button>
    </div>
    <div class="search-box">${icon('search', 18)}<input id="search" type="search" autocomplete="off" /></div>
    <div id="category-chips">${chips(ROOM_CATEGORIES.map((c) => (c.id === 'for_you' ? { ...c, label: 'Tümü' } : c)), activeCategory)}</div>
    <div class="room-list" id="results"></div>`;

  const resultsEl = root.querySelector('#results');
  const searchEl = root.querySelector('#search');
  const chipsEl = root.querySelector('#category-chips');
  // Yavaş gelen eski cevap yeni aramanın sonucunu ezmesin
  let requestId = 0;

  async function load() {
    const id = ++requestId;
    if (mode === 'rooms') {
      const rooms = await api.listRooms({ category: activeCategory, query: searchText });
      if (id !== requestId) return;
      resultsEl.innerHTML = rooms.length
        ? rooms.map(roomRow).join('')
        : '<div class="empty"><p>Aramana uygun oda bulunamadı.</p></div>';
    } else {
      // Arama boşken önerilen kişiler gösterilir
      const users = searchText ? await api.searchUsers(searchText) : await api.listSuggestedUsers();
      if (id !== requestId) return;
      resultsEl.innerHTML = users.length
        ? `${searchText ? '' : '<h3 class="sub-title">Tanıyor olabileceğin kişiler</h3>'}${users.map(userRow).join('')}`
        : '<div class="empty"><p>Bu ada ya da ID\'ye sahip kimse bulunamadı.</p></div>';
    }
  }

  function setMode(next) {
    mode = next;
    root.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('is-active', b.dataset.mode === mode));
    searchEl.placeholder = mode === 'rooms' ? 'Oda adı ara...' : 'Kişi adı, @kullanıcı adı ya da ID ara...';
    chipsEl.hidden = mode !== 'rooms';
    return load();
  }
  await setMode(mode);

  let debounce;
  searchEl.addEventListener('input', (event) => {
    searchText = event.target.value.trim();
    clearTimeout(debounce);
    debounce = setTimeout(load, 250);
  });

  root.querySelector('.explore-modes').addEventListener('click', (event) => {
    const button = event.target.closest('[data-mode]');
    if (button && button.dataset.mode !== mode) setMode(button.dataset.mode);
  });

  chipsEl.addEventListener('click', (event) => {
    const chip = event.target.closest('[data-chip]');
    if (!chip) return;
    activeCategory = chip.dataset.chip;
    root.querySelectorAll('#category-chips .chip').forEach((c) => c.classList.toggle('is-active', c === chip));
    load();
  });

  return () => clearTimeout(debounce);
}
