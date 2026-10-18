// Keşfet: oda arama ve kategori filtresi
import { api } from '../api.js';
import { ROOM_CATEGORIES } from '../config.js';
import { icon } from '../ui.js';
import { roomRow, chips } from './components.js';

export async function renderExplore(root, { query }) {
  let activeCategory = ROOM_CATEGORIES.some((c) => c.id === query.category) ? query.category : 'for_you';
  let searchText = '';

  root.innerHTML = `
    <header class="topbar"><h1 class="page-title">Keşfet</h1></header>
    <div class="search-box">${icon('search', 18)}<input id="room-search" type="search" placeholder="Oda ara..." autocomplete="off" /></div>
    <div id="category-chips">${chips(ROOM_CATEGORIES.map((c) => (c.id === 'for_you' ? { ...c, label: 'Tümü' } : c)), activeCategory)}</div>
    <div class="room-list" id="room-results"></div>`;

  const resultsEl = root.querySelector('#room-results');

  async function load() {
    const rooms = await api.listRooms({ category: activeCategory, query: searchText });
    resultsEl.innerHTML = rooms.length
      ? rooms.map(roomRow).join('')
      : '<div class="empty"><p>Aramana uygun oda bulunamadı.</p></div>';
  }
  await load();

  let debounce;
  root.querySelector('#room-search').addEventListener('input', (event) => {
    searchText = event.target.value.trim();
    clearTimeout(debounce);
    debounce = setTimeout(load, 200);
  });

  root.querySelector('#category-chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-chip]');
    if (!chip) return;
    activeCategory = chip.dataset.chip;
    root.querySelectorAll('#category-chips .chip').forEach((c) => c.classList.toggle('is-active', c === chip));
    load();
  });

  return () => clearTimeout(debounce);
}
