// Odalar sekmesi (alt çubuğun ortasındaki büyük düğme). Üç üst sekme:
//   Ben    → Yayın odam + Ajans kutuları → yayıncılık kutusu ("Yayıncı ol") → Odam (büyük kart)
//            → son girdiğim odalar (yan yana kayar) → takip ettiğim odalar
//   Keşfet → etkinlik şeridi → tür çipleri (Önerilen, Oyun, PK...)
//            → ülke çipleri (Genel, 🇹🇷 Türkiye...) → Önerilen'de en kalabalık 3 oda (Popüler)
//            → satır satır oda listesi, aşağı indikçe uzar
//   Canlı  → mikrofonunda şu an biri olan odalar, iki sütunlu kartlar, aşağı indikçe uzar.
//            (Kameralı canlı yayın sonraki iş; şimdilik sesli odalar.)
// Sağ üstte: günlük giriş, sıralama, arama. Oda açmak "Yayın odam" ekranından ya da Ben'den yapılır.
import { api } from '../api.js';
import { CATEGORY_LABELS } from '../config.js';
import { countryName, flagEmoji } from '../countries.js';
import { esc, icon, avatarImg, formatCoins, formatCount, levelBadge, toast } from '../ui.js';
import { openCreateRoomSheet } from './create-room.js';
import { hostCard, openAgencyContactSheet, openHostApplySheet } from './host-sheets.js';

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
  { id: 'mine', label: 'Ben' },
  { id: 'explore', label: 'Keşfet' },
  { id: 'live', label: 'Canlı' },
];

const POPULAR_SIZE = 3;
const PAGE_SIZE = 20;

export const seatedAvatars = (room, max = 4) => room.seats.filter((s) => s.user).slice(0, max).map((s) => avatarImg(s.user, 'avatar-xs')).join('');
export const statusPill = (room) => (room.camera_user_id ? '<span class="pill pill-live">🎥 CANLI</span>'
  : room.has_pk ? '<span class="pill pill-pk">PK</span>' : room.is_live ? '<span class="pill pill-live">CANLI</span>' : '');
export const listenerCount = (room) => `<span class="eq"><i></i><i></i><i></i></span>${formatCount(room.listener_count)}`;

// Satır: solda kare kapak, ortada ad + duyuru + yayıncı, sağda PK rozeti ve kişi sayısı
function roomRow(room) {
  return `
    <a class="room-row" href="#/room/${room.id}">
      <span class="room-row-cover">
        <img src="${esc(room.cover_url)}" alt="" loading="lazy" />
      </span>
      <span class="room-row-body">
        <b>${esc(room.title)}</b>
        <small>${esc(room.announcement || CATEGORY_LABELS[room.category] || '')}</small>
        <span class="room-row-meta">${avatarImg(room.host, 'avatar-xs')}<span>${esc(room.host.display_name)}</span>${levelBadge(room.host.level)}<span class="room-tag">${esc(CATEGORY_LABELS[room.category] || 'Sohbet')}</span></span>
      </span>
      <span class="room-row-side">
        ${room.camera_user_id ? '<span class="pill pill-live">🎥</span>' : ''}
        ${room.has_pk ? '<span class="pill pill-pk">PK</span>' : ''}
        <span class="room-row-count">${listenerCount(room)}</span>
      </span>
    </a>`;
}

// Canlı sekmesi kartı: büyük kare kapak, sol altta 🔥 kişi sayısı, altında oda adı ve yayıncı
function liveCard(room) {
  const speakers = room.seats.filter((s) => s.user).length;
  return `
    <a class="live-card" href="#/room/${room.id}">
      <span class="live-card-cover">
        <img src="${esc(room.cover_url)}" alt="" loading="lazy" />
        ${room.has_pk ? '<span class="pill pill-pk live-card-pk">PK</span>' : ''}
        ${room.camera_user_id ? '<span class="pill pill-live live-card-camera">🎥 Kamera</span>' : ''}
        <span class="live-card-heat">${icon('flame', 13)}${formatCount(room.listener_count)}</span>
        <span class="live-card-mic">${icon('mic', 12)}${speakers}</span>
      </span>
      <b>${esc(room.title)}</b>
      <span class="live-card-host">${avatarImg(room.host, 'avatar-xs')}<span>${esc(room.host.display_name)}</span>${room.host.country ? `<i title="${esc(countryName(room.host.country))}">${flagEmoji(room.host.country)}</i>` : ''}</span>
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

// Yayın odam ve Ajans: yan yana iki renkli kutu. Ajansı olmayan için Ajans kutusu tanıtım panelini açar
// (ajans kurmak müşteri hizmetleriyle konuşularak olur).
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
      <a class="promo-tile promo-tile-agency" href="#/agency" ${agency?.role || agency?.invite || agency?.application ? '' : 'data-action="agency-contact"'}>
        <span class="promo-tile-text"><b>Ajans</b><small>${esc(agency?.role || agency?.invite || agency?.application ? agencyText : 'Ajans kur, komisyon kazan')}</small></span>
        <i>${icon('building', 30)}</i>
      </a>
    </div>`;
}

// Ben sekmesindeki büyük "Odam" kartı: kapak arkada, üstünde ad, takipçi, elmas ve "Odama gir"
function myRoomHero({ room, follower_count: followers, gift_diamonds: diamonds }) {
  return `
    <a class="my-room-hero" href="#/room/${room.id}">
      <img src="${esc(room.cover_url)}" alt="" />
      <span class="my-room-hero-body">
        <small>Odam · ID ${room.id}</small>
        <b>${esc(room.title)}</b>
        <span class="my-room-hero-stats">
          <span>${listenerCount(room)}</span>
          <span>${formatCount(followers)} takipçi</span>
          <span>💎 ${formatCoins(diamonds)}</span>
        </span>
      </span>
      <span class="btn btn-sm btn-primary my-room-hero-enter">Odama gir</span>
    </a>`;
}

// Son girdiğim odalar: küçük kare kapaklar yan yana kayar
function recentStrip(rooms) {
  return `
    <div class="recent-rooms">
      ${rooms.map((room) => `
        <a class="recent-room" href="#/room/${room.id}">
          <span class="recent-room-cover"><img src="${esc(room.cover_url)}" alt="" loading="lazy" />${room.seats.some((s) => s.user) ? '<span class="recent-room-live"><span class="eq"><i></i><i></i><i></i></span></span>' : ''}</span>
          <small>${esc(room.title)}</small>
        </a>`).join('')}
    </div>`;
}

function mineView(myRooms, recent, followed, agency, hostStatus) {
  const [first, ...others] = myRooms;
  return `
    ${promoTiles(myRooms, agency)}
    <div class="host-card-wrap" id="host-card">${hostCard(hostStatus)}</div>
    <section class="home-section">
      <div class="section-head"><h2>Odam</h2><a href="#/my-rooms">Kazanç ve takipçiler ${icon('chevron-right', 13)}</a></div>
      <div class="room-list">
        ${first ? myRoomHero(first) : `
          <button class="room-row room-row-create" data-action="create-room">
            <span class="room-row-cover">${icon('plus', 26)}</span>
            <span class="room-row-body"><b>Kendi odanı aç</b><small>Ad ve tür seç, odan hemen açılsın. Gelen hediyeler elmas olarak cüzdanına geçer.</small></span>
          </button>`}
        ${others.map(({ room }) => roomRow(room)).join('')}
      </div>
    </section>
    <section class="home-section">
      <div class="section-head"><h2>Son girdiğim odalar</h2><small>${recent.length || ''}</small></div>
      ${recent.length ? recentStrip(recent) : '<p class="room-list-empty">Henüz bir odaya girmedin. Keşfet\'ten bir oda seç.</p>'}
    </section>
    <section class="home-section">
      <div class="section-head"><h2>Takip ettiğim odalar</h2><small>${followed.length}</small></div>
      <div class="room-list">
        ${followed.map(roomRow).join('') || '<p class="room-list-empty">Henüz bir oda takip etmiyorsun. Odada "Takip Et"e dokunduğunda burada görünür.</p>'}
      </div>
    </section>`;
}

export async function renderRooms(root, { query }) {
  const [featured, myRooms, agency, events, checkin, countries] = await Promise.all([
    api.listRooms({ category: 'for_you', limit: 30 }),
    api.listMyRooms().catch(() => []),
    api.getMyAgency().catch(() => null),
    api.listEvents().catch(() => []),
    api.getCheckin().catch(() => null),
    api.listRoomCountries().catch(() => []),
  ]);
  const popular = [...featured].sort((a, b) => b.listener_count - a.listener_count).slice(0, POPULAR_SIZE);
  const popularIds = new Set(popular.map((r) => r.id));

  let tab = TABS.some((t) => t.id === query.tab) ? query.tab : 'explore';
  let filter = FILTERS.some((f) => f.id === query.filter) ? query.filter : 'for_you';
  // Boş = Genel (bütün ülkeler)
  let country = countries.some((c) => c.country === query.country) ? query.country : '';
  let rooms = [];
  let hasMore = true;
  let isLoading = false;
  let loadToken = 0;
  let observer = null;
  let currentHostStatus = null;

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

  // Ülke çipleri yalnızca birden çok ülkeden oda varken anlamlı
  const countryBar = () => (countries.length > 1 ? `
    <div class="filter-bar filter-bar-countries" id="room-countries">
      <button class="filter-chip ${country === '' ? 'is-active' : ''}" data-country=""><i>🌐</i>Genel</button>
      ${countries.map((c) => `<button class="filter-chip ${c.country === country ? 'is-active' : ''}" data-country="${esc(c.country)}" title="${c.room_count} oda"><i>${flagEmoji(c.country)}</i>${esc(countryName(c.country))}</button>`).join('')}
    </div>` : '');

  function paintExplore() {
    body.innerHTML = `
      ${eventStrip(events)}
      <div class="filter-sticky">
        <div class="filter-bar" id="room-filters">
          ${FILTERS.map((f) => `<button class="filter-chip ${f.id === filter ? 'is-active' : ''}" data-filter="${f.id}">${f.label}</button>`).join('')}
        </div>
        ${countryBar()}
      </div>
      <div id="popular-slot"></div>
      <div class="room-list" id="room-list"></div>
      <div class="feed-sentinel" id="room-sentinel"></div>`;
    paintPopular();
  }

  function paintLive() {
    body.innerHTML = `
      ${eventStrip(events)}
      <div class="live-grid" id="room-list"></div>
      <div class="feed-sentinel" id="room-sentinel"></div>`;
  }

  // Popüler yalnızca Önerilen + Genel'de, listenin üstünde
  const showsPopular = () => tab === 'explore' && filter === 'for_you' && !country && popular.length;
  function paintPopular() {
    const slot = body.querySelector('#popular-slot');
    slot.innerHTML = showsPopular() ? `
      <section class="home-section">
        <div class="section-head"><h2>Popüler</h2><small>Şu an en kalabalık</small></div>
        <div class="popular-rooms">${popular.map(popularCard).join('')}</div>
      </section>` : '';
  }

  function emptyText() {
    if (tab === 'live') return 'Şu an mikrofonda kimse yok. Bir odaya gir, sohbeti sen başlat.';
    if (country && !rooms.length) return `${countryName(country)} için bu türde oda yok. Genel'e göz at.`;
    if (filter === 'pk') return 'Şu an PK yapan oda yok.';
    return filter === 'for_you' ? 'Başka oda yok; yukarıdakilere göz at.' : 'Bu türde şu an oda yok.';
  }

  async function loadMore() {
    if (isLoading || !hasMore || tab === 'mine') return;
    const list = body.querySelector('#room-list');
    const sentinel = body.querySelector('#room-sentinel');
    isLoading = true;
    const token = loadToken;
    sentinel.innerHTML = '<div class="spinner"></div>';
    try {
      const params = tab === 'live'
        ? { category: 'live', limit: PAGE_SIZE, offset: rooms.length }
        : { category: filter, limit: PAGE_SIZE, offset: rooms.length, country };
      const page = await api.listRooms(params);
      if (token !== loadToken) return;   // bu arada filtre ya da sekme değişti
      hasMore = page.length === PAGE_SIZE;
      rooms = rooms.concat(page);
      // Popüler'de zaten büyük gösterilen odalar bir daha listelenmez
      const fresh = showsPopular() ? page.filter((r) => !popularIds.has(r.id)) : page;
      if (fresh.length) {
        list.insertAdjacentHTML('beforeend', fresh.map(tab === 'live' ? liveCard : roomRow).join(''));
      } else if (!hasMore && !list.querySelector('.room-row, .live-card')) {
        list.innerHTML = `<p class="room-list-empty">${esc(emptyText())}</p>`;
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

  // Tür ya da ülke değişti: liste baştan yüklenir
  function reloadList() {
    syncUrl();
    loadToken += 1;
    rooms = [];
    hasMore = true;
    isLoading = false;
    body.querySelector('#room-list').innerHTML = '';
    body.querySelectorAll('#room-filters [data-filter]').forEach((b) => b.classList.toggle('is-active', b.dataset.filter === filter));
    body.querySelectorAll('#room-countries [data-country]').forEach((b) => b.classList.toggle('is-active', b.dataset.country === country));
    paintPopular();
    loadMore();
  }

  // Seçili sekme / tür / ülke adrese yazılır (#/rooms?tab=mine...). Neden? Odaya girip geri tuşuna
  // basınca tarayıcı bu adrese döner; adreste yoksa ekran varsayılanla (Keşfet) açılırdı.
  // replaceState geçmişe yeni kayıt eklemez (sekme değiştirmek "geri" ile tek tek gezilmesin) ve
  // hashchange olayı çıkarmaz (ekran yeniden çizilmez). Geçmişteki derinlik bilgisi (state) korunur.
  function syncUrl() {
    const params = new URLSearchParams();
    if (tab !== 'explore') params.set('tab', tab);
    if (filter !== 'for_you') params.set('filter', filter);
    if (country) params.set('country', country);
    const search = params.toString();
    history.replaceState(history.state, '', `#/rooms${search ? `?${search}` : ''}`);
  }

  async function showTab(id) {
    tab = id;
    syncUrl();
    loadToken += 1;
    root.querySelectorAll('#rooms-tabs button').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === id));
    if (id === 'mine') {
      observer?.disconnect();
      body.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
      const [recent, followed, hostStatus] = await Promise.all([
        api.listRecentRooms().catch(() => []),
        api.listFollowedRooms().catch(() => []),
        api.getHostStatus().catch(() => null),
      ]);
      if (tab !== 'mine') return;
      currentHostStatus = hostStatus;
      body.innerHTML = mineView(myRooms, recent, followed, agency, hostStatus);
      return;
    }
    rooms = [];
    hasMore = true;
    isLoading = false;
    if (id === 'live') paintLive();
    else paintExplore();
    await loadMore();
    watchSentinel();
  }

  root.addEventListener('click', (event) => {
    const tabButton = event.target.closest('[data-tab]');
    if (tabButton && tabButton.dataset.tab !== tab) { showTab(tabButton.dataset.tab); return; }
    const chip = event.target.closest('[data-filter]');
    if (chip && chip.dataset.filter !== filter) { filter = chip.dataset.filter; reloadList(); return; }
    const flag = event.target.closest('[data-country]');
    if (flag && flag.dataset.country !== country) { country = flag.dataset.country; reloadList(); return; }
    if (event.target.closest('[data-action="create-room"]')) openCreateRoomSheet();
    if (event.target.closest('[data-action="agency-contact"]')) {
      event.preventDefault();
      openAgencyContactSheet({ isHost: Boolean(currentHostStatus?.is_host) });
    }
    if (event.target.closest('[data-action="host-apply"]')) {
      openHostApplySheet((status) => {
        currentHostStatus = status;
        const slot = body.querySelector('#host-card');
        if (slot) slot.innerHTML = hostCard(status);
      });
    }
  });

  await showTab(tab);
  // Ana sayfada oyuna dokunup gelindiyse doğrudan listeye in (geri ile dönünce değil)
  if (query.jump) body.querySelector('#room-filters')?.scrollIntoView({ block: 'start' });
  return () => observer?.disconnect();
}
