// Keşfet: tek arama kutusu hem odaları hem kişileri arar; sonuçlar Tümü / Odalar / Kişiler sekmeleriyle süzülür
import { api } from '../api.js';
import { ROOM_CATEGORIES } from '../config.js';
import { esc, icon, avatarImg, joinParts, levelBadge } from '../ui.js';
import { roomRow, chips } from './components.js';

// "Tümü" sekmesinde her bölümden kaç sonuç gösterilir; fazlası için "Tümünü gör"
const PREVIEW_PEOPLE = 3;
const PREVIEW_ROOMS = 5;

const TABS = [
  { id: 'all', label: 'Tümü' },
  { id: 'rooms', label: 'Odalar' },
  { id: 'people', label: 'Kişiler' },
];

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

function section(title, tab, items, limit, renderItem) {
  if (!items.length) return '';
  const more = items.length > limit
    ? `<button type="button" data-goto="${tab}">Tümünü gör ${icon('chevron-right', 13)}</button>`
    : '';
  return `
    <div class="section-head search-section-head"><h2>${title}</h2>${more}</div>
    ${items.slice(0, limit).map(renderItem).join('')}`;
}

const empty = (text) => `<div class="empty"><p>${text}</p></div>`;

export async function renderExplore(root, { query }) {
  let tab = TABS.some((t) => t.id === query.mode) ? query.mode : 'all';
  // Kategoriyle gelindiyse (ör. ana sayfadaki "Oyun Odaları") doğrudan Odalar sekmesi açılır
  let activeCategory = ROOM_CATEGORIES.some((c) => c.id === query.category) ? query.category : 'for_you';
  if (activeCategory !== 'for_you' && !query.mode) tab = 'rooms';
  let searchText = '';

  root.innerHTML = `
    <header class="topbar"><h1 class="page-title">Keşfet</h1></header>
    <div class="search-box">${icon('search', 18)}<input id="search" type="search" autocomplete="off" placeholder="Oda, kişi ya da ID ara..." /></div>
    <div class="segmented segmented-3 explore-modes">
      ${TABS.map((t) => `<button type="button" data-mode="${t.id}">${t.label}</button>`).join('')}
    </div>
    <div id="category-chips">${chips(ROOM_CATEGORIES.map((c) => (c.id === 'for_you' ? { ...c, label: 'Tümü' } : c)), activeCategory)}</div>
    <div class="room-list" id="results"></div>`;

  const resultsEl = root.querySelector('#results');
  const searchEl = root.querySelector('#search');
  const chipsEl = root.querySelector('#category-chips');
  // Yavaş gelen eski cevap yeni aramanın sonucunu ezmesin
  let requestId = 0;

  // Arama boşken kişi listesi yerine önerilen kişiler gösterilir
  const loadPeople = () => (searchText ? api.searchUsers(searchText) : api.listSuggestedUsers());
  const loadRooms = () => api.listRooms({ category: tab === 'rooms' ? activeCategory : 'for_you', query: searchText });

  async function load() {
    const id = ++requestId;
    let html;
    if (tab === 'rooms') {
      const rooms = await loadRooms();
      if (id !== requestId) return;
      html = rooms.length ? rooms.map(roomRow).join('') : empty('Aramana uygun oda bulunamadı.');
    } else if (tab === 'people') {
      const users = await loadPeople();
      if (id !== requestId) return;
      html = users.length
        ? `${searchText ? '' : '<h3 class="sub-title">Tanıyor olabileceğin kişiler</h3>'}${users.map(userRow).join('')}`
        : empty('Bu ada ya da ID\'ye sahip kimse bulunamadı.');
    } else {
      // İki arama birbirini beklemeden aynı anda gider
      const [users, rooms] = await Promise.all([loadPeople(), loadRooms()]);
      if (id !== requestId) return;
      html = section(searchText ? 'Kişiler' : 'Tanıyor olabileceğin kişiler', 'people', users, PREVIEW_PEOPLE, userRow)
        + section(searchText ? 'Odalar' : 'Popüler odalar', 'rooms', rooms, PREVIEW_ROOMS, roomRow);
      if (!html) html = empty(`"${esc(searchText)}" için sonuç bulunamadı.`);
    }
    resultsEl.innerHTML = html;
  }

  function setTab(next) {
    tab = next;
    root.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('is-active', b.dataset.mode === tab));
    // Kategori süzgeci yalnızca oda listesinde anlamlı
    chipsEl.hidden = tab !== 'rooms';
    return load();
  }
  await setTab(tab);
  // Ana sayfadaki arama simgesinden gelindiyse klavye hemen açılsın
  if (query.focus) searchEl.focus();

  let debounce;
  searchEl.addEventListener('input', (event) => {
    searchText = event.target.value.trim();
    clearTimeout(debounce);
    debounce = setTimeout(load, 250);
  });

  root.querySelector('.explore-modes').addEventListener('click', (event) => {
    const button = event.target.closest('[data-mode]');
    if (button && button.dataset.mode !== tab) setTab(button.dataset.mode);
  });

  resultsEl.addEventListener('click', (event) => {
    const more = event.target.closest('[data-goto]');
    if (more) setTab(more.dataset.goto);
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
