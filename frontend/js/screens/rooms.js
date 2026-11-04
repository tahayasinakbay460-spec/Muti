// Odalar sekmesi (alt çubuğun ortasındaki büyük düğme). İki üst sekme:
//   Keşfet → etkinlik şeridi → Yayın odam + Ajans kutuları → filtre çipleri (Önerilen, Oyun, PK...)
//            → Önerilen'de en kalabalık 3 oda (Popüler) → satır satır oda listesi, aşağı indikçe uzar
//   Benim  → açtığım odalar (takipçi, hediye) → takip ettiğim odalar
// Sağ üstte: günlük giriş, sıralama, arama. Oda açmak "Yayın odam" ekranından yapılır.
import { api } from '../api.js';
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins, formatCount, levelBadge, toast } from '../ui.js';
import { openCreateRoomSheet } from './create-room.js';

// Liste üstündeki filtreler. `pk` gerçek bir kategori değil: sunucu PK'si süren odaları verir.
const FILTERS = [
  { id: 'for_you', label: 'Önerilen' },
  { id: 'game', label: 'Oyun' },
  { id: 'pk', label: 'PK' },
  { id: 'chat', label: 'Sohbet' },
  { id: 'music', label: 'Müzik' },
  { id: 'new_people', label: 'Yeni İnsanlar' },
];
const TABS = [
  { id: 'mine', label: 'Benim' },
  { id: 'explore', label: 'Keşfet' },
];

const POPULAR_SIZE = 3;
const PAGE_SIZE = 20;

export const seatedAvatars = (room, max = 4) => room.seats.filter((s) => s.user).slice(0, max).map((s) => avatarImg(s.user, 'avatar-xs')).join('');
export const statusPill = (room) => (room.has_pk ? '<span class="pill pill-pk">PK</span>' : room.is_live ? '<span class="pill pill-live">CANLI</span>' : '');
export const listenerCount = (room) => `<span class="eq"><i></i><i></i><i></i></span>${formatCount(room.listener_count)}`;

// Satır: solda kare kapak, ortada ad + duyuru + yayıncı, sağda PK rozeti ve kişi sayısı
function roomRow(room) {
  return `
    <a class="room-row" href="#/room/${room.id}">
      <span class="room-row-cover">
        <img src="${esc(room.cover_url)}" alt="" loading="lazy" />
        ${room.is_live ? '<span class="room-row-live"><span class="eq"><i></i><i></i><i></i></span></span>' : ''}
      </span>
      <span class="room-row-body">
        <b>${esc(room.title)}</b>
        <small>${esc(room.announcement || CATEGORY_LABELS[room.category] || '')}</small>
        <span class="room-row-meta">${avatarImg(room.host, 'avatar-xs')}<span>${esc(room.host.display_name)}</span>${levelBadge(room.host.level)}<span class="room-tag">${esc(CATEGORY_LABELS[room.category] || 'Sohbet')}</span></span>
      </span>
      <span class="room-row-side">
        ${room.has_pk ? '<span class="pill pill-pk">PK</span>' : ''}
        <span class="room-row-count">${listenerCount(room)}</span>
      </span>
    </a>`;
}

// Popüler: ilk üç oda büyükçe, sıra numarasıyla
function popularCard(room, index) {
  return `
    <a class="popular-room rank-${index + 1}" href="#/room/${room.id}">
      <img src="${esc(room.cover_url)}" alt="" loading="lazy" />
      <span class="popular-rank">${index + 1}</span>
      <span class="popular-room-body">
        <b>${esc(room.title)}</b>
        <small>${listenerCount(room)} kişi</small>
      </span>
    </a>`;
}

// Etkinlik şeridi: süren etkinlikler yan yana kayar
function eventStrip(events) {
  const live = events.filter((e) => e.status !== 'ended').slice(0, 5);
  if (!live.length) return '';
  return `
    <div class="event-strip">
      ${live.map((e) => `
        <a class="event-slide" href="#/event/${e.id}">
          <i>${e.emoji}</i>
          <span><b>${esc(e.title)}</b><small>${e.status === 'active' ? 'Sürüyor' : 'Yakında'} · 1. ödül 🪙 ${formatCoins(e.rewards[0] || 0)}</small></span>
          ${icon('chevron-right', 16)}
        </a>`).join('')}
    </div>`;
}

// Yayın odam ve Ajans: yan yana iki renkli kutu
function promoTiles(myRooms, agency) {
  const diamonds = myRooms.reduce((sum, r) => sum + r.gift_diamonds, 0);
  let agencyText = 'Katıl, aylık bonus kazan';
  if (agency?.role === 'owner') agencyText = `${agency.dashboard.agency.name} · sahibisin`;
  else if (agency?.role === 'member') agencyText = agency.agency.name;
  else if (agency?.invite) agencyText = 'Yeni davetin var';
  else if (agency?.application) agencyText = 'Başvurun bekliyor';
  return `
    <div class="promo-tiles">
      <a class="promo-tile promo-tile-broadcast" href="#/my-rooms">
        <span class="promo-tile-text"><b>Yayın odam</b><small>${myRooms.length ? `${myRooms.length} oda · 💎 ${formatCoins(diamonds)}` : 'Odanı aç, kazan'}</small></span>
        <i>${icon('mic', 30)}</i>
      </a>
      <a class="promo-tile promo-tile-agency" href="#/agency">
        <span class="promo-tile-text"><b>Ajans</b><small>${esc(agencyText)}</small></span>
        <i>${icon('building', 30)}</i>
      </a>
    </div>`;
}

// Benim sekmesi: açtığım odalar ve takip ettiklerim
function mineView(myRooms, followed) {
  const mine = myRooms.map(({ room, follower_count: followers, gift_diamonds: diamonds }) => `
    <a class="room-row" href="#/room/${room.id}">
      <span class="room-row-cover"><img src="${esc(room.cover_url)}" alt="" /></span>
      <span class="room-row-body">
        <b>${esc(room.title)}</b>
        <small>${formatCount(followers)} takipçi · 💎 ${formatCoins(diamonds)} hediye</small>
        <span class="room-row-meta"><span class="room-tag">${esc(CATEGORY_LABELS[room.category] || 'Sohbet')}</span><span class="room-tag">ID ${room.id}</span></span>
      </span>
      <span class="room-row-side"><span class="room-row-count">${listenerCount(room)}</span></span>
    </a>`).join('');
  return `
    <section class="home-section">
      <div class="section-head"><h2>Odalarım</h2><a href="#/my-rooms">Kazanç ve takipçiler ${icon('chevron-right', 13)}</a></div>
      <div class="room-list">
        ${mine || `
          <button class="room-row room-row-create" data-action="create-room">
            <span class="room-row-cover">${icon('plus', 26)}</span>
            <span class="room-row-body"><b>Kendi odanı aç</b><small>Ad ve tür seç, odan hemen açılsın. Gelen hediyeler elmas olarak cüzdanına geçer.</small></span>
          </button>`}
      </div>
    </section>
    <section class="home-section">
      <div class="section-head"><h2>Takip ettiğim odalar</h2><small>${followed.length}</small></div>
      <div class="room-list">
        ${followed.map(roomRow).join('') || '<p class="room-list-empty">Henüz bir oda takip etmiyorsun. Odada "Takip Et"e dokunduğunda burada görünür.</p>'}
      </div>
    </section>`;
}

export async function renderRooms(root, { query }) {
  const [featured, myRooms, agency, events, checkin] = await Promise.all([
    api.listRooms({ category: 'for_you', limit: 30 }),
    api.listMyRooms().catch(() => []),
    api.getMyAgency().catch(() => null),
    api.listEvents().catch(() => []),
    api.getCheckin().catch(() => null),
  ]);
  const popular = [...featured].sort((a, b) => b.listener_count - a.listener_count).slice(0, POPULAR_SIZE);
  const popularIds = new Set(popular.map((r) => r.id));

  let tab = query.tab === 'mine' ? 'mine' : 'explore';
  let filter = FILTERS.some((f) => f.id === query.filter) ? query.filter : 'for_you';
  let rooms = [];
  let hasMore = true;
  let isLoading = false;
  let loadToken = 0;
  let observer = null;

  root.innerHTML = `
    <header class="topbar rooms-head">
      <nav class="head-tabs" id="rooms-tabs">
        ${TABS.map((t) => `<button class="${t.id === tab ? 'is-active' : ''}" data-tab="${t.id}">${t.label}</button>`).join('')}
      </nav>
      <div class="topbar-actions">
        <a class="icon-btn icon-btn-plain ${checkin && !checkin.claimed_today ? 'has-dot' : ''}" href="#/tasks" aria-label="Günlük giriş">${icon('calendar', 22)}</a>
        <a class="icon-btn icon-btn-plain" href="#/leaderboard" aria-label="Sıralama">${icon('crown', 22)}</a>
        <a class="icon-btn icon-btn-plain" href="#/explore?focus=1" aria-label="Oda ara">${icon('search', 22)}</a>
      </div>
    </header>
    <div id="rooms-body"></div>`;
  const body = root.querySelector('#rooms-body');

  function paintExplore() {
    body.innerHTML = `
      ${eventStrip(events)}
      ${promoTiles(myRooms, agency)}
      <div class="filter-bar" id="room-filters">
        ${FILTERS.map((f) => `<button class="filter-chip ${f.id === filter ? 'is-active' : ''}" data-filter="${f.id}">${f.label}</button>`).join('')}
      </div>
      <div id="popular-slot"></div>
      <div class="room-list" id="room-list"></div>
      <div class="feed-sentinel" id="room-sentinel"></div>`;
    paintPopular();
  }

  // Popüler yalnızca Önerilen'de, listenin üstünde
  function paintPopular() {
    const slot = body.querySelector('#popular-slot');
    slot.innerHTML = filter === 'for_you' && popular.length ? `
      <section class="home-section">
        <div class="section-head"><h2>Popüler</h2><small>Şu an en kalabalık</small></div>
        <div class="popular-rooms">${popular.map(popularCard).join('')}</div>
      </section>` : '';
  }

  async function loadMore() {
    if (isLoading || !hasMore || tab !== 'explore') return;
    const list = body.querySelector('#room-list');
    const sentinel = body.querySelector('#room-sentinel');
    isLoading = true;
    const token = loadToken;
    sentinel.innerHTML = '<div class="spinner"></div>';
    try {
      const page = await api.listRooms({ category: filter, limit: PAGE_SIZE, offset: rooms.length });
      if (token !== loadToken) return;   // bu arada filtre ya da sekme değişti
      hasMore = page.length === PAGE_SIZE;
      rooms = rooms.concat(page);
      // Önerilen'de Popüler'de zaten büyük gösterilen odalar bir daha listelenmez
      const fresh = filter === 'for_you' ? page.filter((r) => !popularIds.has(r.id)) : page;
      if (fresh.length) {
        list.insertAdjacentHTML('beforeend', fresh.map(roomRow).join(''));
      } else if (!hasMore && !list.querySelector('.room-row')) {
        list.innerHTML = `<p class="room-list-empty">${filter === 'pk' ? 'Şu an PK yapan oda yok.' : filter === 'for_you' ? 'Başka oda yok; yukarıdakilere göz at.' : 'Bu türde şu an oda yok.'}</p>`;
      }
    } catch (error) {
      toast(error.message, 'error');
      hasMore = false;
    } finally {
      if (token === loadToken) {
        isLoading = false;
        sentinel.innerHTML = '';
      }
    }
  }

  function watchSentinel() {
    observer?.disconnect();
    const sentinel = body.querySelector('#room-sentinel');
    if (!sentinel) return;
    // Listenin sonu görünür olunca bir sonraki sayfa gelir
    observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore();
    }, { rootMargin: '300px 0px' });
    observer.observe(sentinel);
  }

  function setFilter(id) {
    filter = id;
    loadToken += 1;
    rooms = [];
    hasMore = true;
    isLoading = false;
    body.querySelector('#room-list').innerHTML = '';
    body.querySelectorAll('#room-filters [data-filter]').forEach((b) => b.classList.toggle('is-active', b.dataset.filter === id));
    paintPopular();
    loadMore();
  }

  async function showTab(id) {
    tab = id;
    loadToken += 1;
    root.querySelectorAll('#rooms-tabs button').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === id));
    if (id === 'mine') {
      observer?.disconnect();
      body.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
      const followed = await api.listFollowedRooms().catch(() => []);
      if (tab !== 'mine') return;
      body.innerHTML = mineView(myRooms, followed);
      return;
    }
    rooms = [];
    hasMore = true;
    isLoading = false;
    paintExplore();
    await loadMore();
    watchSentinel();
  }

  root.addEventListener('click', (event) => {
    const tabButton = event.target.closest('[data-tab]');
    if (tabButton && tabButton.dataset.tab !== tab) { showTab(tabButton.dataset.tab); return; }
    const chip = event.target.closest('[data-filter]');
    if (chip && chip.dataset.filter !== filter) { setFilter(chip.dataset.filter); return; }
    if (event.target.closest('[data-action="create-room"]')) openCreateRoomSheet();
  });

  await showTab(tab);
  // Oyuna dokunup gelindiyse doğrudan listeye in
  if (query.filter) body.querySelector('#room-filters')?.scrollIntoView({ block: 'start' });
  return () => observer?.disconnect();
}
