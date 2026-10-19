// Ana sayfa: üst sekmeler, banner, hızlı kategoriler, öne çıkan odalar, oyunlar, popüler yayıncılar
import { api } from '../api.js';
import { APP_NAME, CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins, formatCount, toast } from '../ui.js';
import { roomRow, coinPill } from './components.js';
import { paintNotificationBadge } from '../inbox.js';
import { maybeShowCheckin } from './tasks.js';

// Üst sekmeler. Henüz ekranı olmayanlar "Yakında" bildirimi gösterir.
const TOP_TABS = [
  { id: 'discover', label: 'Keşfet', icon: 'flame' },
  { id: 'rooms', label: 'Odalar', icon: 'home', href: '#/explore' },
  { id: 'games', label: 'Oyunlar', icon: 'gamepad', scrollTo: 'games' },
  { id: 'events', label: 'Etkinlik', icon: 'trophy', href: '#/events' },
  { id: 'following', label: 'Takip', icon: 'users', href: '#/following' },
];

const QUICK_TILES = [
  { id: 'tasks', label: 'Görevler', emoji: '🎯', href: '#/tasks' },
  { id: 'leaderboard', label: 'Sıralama', emoji: '🏆', href: '#/leaderboard' },
  { id: 'families', label: 'Aileler', emoji: '🛡️', href: '#/families' },
  { id: 'game-rooms', label: 'Oyun Odaları', emoji: '🎮', href: '#/explore?category=game' },
  { id: 'vip', label: 'VIP', emoji: '👑', href: '#/vip' },
];

// Oda içi oyunlar. Oynanabilenler (isPlayable) oda içinden açılır: kart oyun odalarına götürür.
const GAMES = [
  { id: 'roulette', name: 'Rulet', emoji: '🎡', isPlayable: true },
  { id: 'billiards', name: 'Bilardo', emoji: '🎱' },
  { id: 'okey', name: '101 Okey', emoji: '🀄' },
  { id: 'candy', name: 'Candy', emoji: '🍭' },
];

// Banner başlığının son satırı renkli vurguyla yazılır ("Muti'de!")
function bannerTitle(title) {
  const lines = esc(title).split('\n');
  const last = lines.pop();
  return [...lines, `<em>${last}</em>`].join('<br />');
}

function featuredRoomCard(room) {
  return `
    <a class="feature-card" href="#/room/${room.id}">
      <img class="feature-card-cover" src="${esc(room.cover_url)}" alt="" loading="lazy" />
      <div class="feature-card-top">
        ${room.is_live ? '<span class="pill pill-live">CANLI</span>' : '<span></span>'}
        <span class="pill pill-dark">${icon('users', 11)} ${formatCount(room.listener_count)}</span>
      </div>
      <div class="feature-card-body">
        ${avatarImg(room.host)}
        <span>
          <b>${esc(room.title)}</b>
          <small>${CATEGORY_LABELS[room.category] || ''} • Herkes</small>
        </span>
      </div>
    </a>`;
}

// Popüler yayıncılar: önce şu an canlı odası olan ev sahipleri, sonra önerilen kişiler (kullanıcının kendisi hariç)
function collectStreamers(rooms, suggested, meId) {
  const seen = new Set([meId]);
  const list = [];
  for (const room of rooms) {
    if (!room.is_live || seen.has(room.host.id)) continue;
    seen.add(room.host.id);
    list.push({ user: room.host, roomId: room.id });
  }
  for (const user of suggested) {
    if (seen.has(user.id)) continue;
    seen.add(user.id);
    list.push({ user, roomId: null });
  }
  return list.slice(0, 12);
}

export async function renderHome(root) {
  const [me, banners, suggested, gifters, rooms] = await Promise.all([
    api.getMe(), api.listBanners(), api.listSuggestedUsers(), api.listTopGifters(),
    api.listRooms({ category: 'for_you' }),
  ]);
  const sorted = [...rooms].sort((a, b) => a.hourly_rank - b.hourly_rank);
  const featured = sorted.slice(0, 8);
  const active = sorted.slice(8);
  const streamers = collectStreamers(sorted, suggested, me.id);

  root.innerHTML = `
    <header class="topbar">
      <div class="logo"><span class="logo-mark">M</span><span class="logo-text">${APP_NAME}</span></div>
      <div class="topbar-actions">
        <a class="icon-btn icon-btn-plain" href="#/explore?focus=1" aria-label="Ara">${icon('search', 22)}</a>
        <button class="icon-btn icon-btn-plain" data-action="notifications" aria-label="Bildirimler">${icon('bell', 22)}</button>
        ${coinPill(me.coin_balance)}
      </div>
    </header>

    <nav class="top-tabs">
      ${TOP_TABS.map((t) => `
        <button class="top-tab ${t.id === 'discover' ? 'is-active' : ''}" data-top-tab="${t.id}">${icon(t.icon, 14)}${t.label}</button>`).join('')}
    </nav>

    <section class="banner" id="banner">
      <div class="banner-track">
        ${banners.map((b) => `
          <a class="banner-slide" href="${esc(b.target)}">
            <img src="${esc(b.image_url)}" alt="" />
            <div class="banner-text">
              <h2>${bannerTitle(b.title)}</h2>
              <span class="banner-cta">${esc(b.cta)} ${icon('chevron-right', 13)}</span>
            </div>
            <div class="banner-dots">${banners.map((_, i) => `<i class="${i === 0 ? 'is-active' : ''}"></i>`).join('')}</div>
          </a>`).join('')}
      </div>
    </section>

    <div class="quick-cats">
      ${QUICK_TILES.map((t) => `
        <button class="quick-cat" data-quick="${t.id}"><i>${t.emoji}</i><span>${t.label}</span></button>`).join('')}
    </div>

    <section class="section">
      <div class="section-head"><h2>Sana Özel Öne Çıkan Odalar</h2><a href="#/explore">Tümünü Gör ${icon('chevron-right', 13)}</a></div>
      <div class="h-strip">
        ${featured.map(featuredRoomCard).join('') || '<p class="muted">Şu an açık oda yok.</p>'}
      </div>
    </section>

    <section class="section" id="games">
      <div class="section-head"><h2>Oyunlar</h2><a href="#/explore?category=game">Tümünü Gör ${icon('chevron-right', 13)}</a></div>
      <div class="game-grid">
        ${GAMES.map((g) => `
          <button class="game-card" data-game="${g.id}">
            <span class="game-art game-${g.id}"><i>${g.emoji}</i></span>
            <b>${g.name}</b>
          </button>`).join('')}
      </div>
    </section>

    <section class="section" id="streamers">
      <div class="section-head"><h2>Popüler Yayıncılar</h2><a href="#/explore?mode=people">Tümünü Gör ${icon('chevron-right', 13)}</a></div>
      <div class="streamer-strip">
        ${streamers.map(({ user, roomId }, i) => `
          <a class="streamer" href="${roomId ? `#/room/${roomId}` : `#/profile/${user.id}`}">
            <span class="streamer-ring ${i === 0 && roomId ? 'is-live' : ''}">
              ${i === 0 && roomId ? '<i class="streamer-crown">👑</i>' : ''}
              ${avatarImg(user)}
              ${i === 0 && roomId ? '<span class="streamer-live">CANLI</span>' : (user.is_online ? '<span class="online-dot"></span>' : '')}
            </span>
            <b>${esc(user.display_name)}</b>
          </a>`).join('')}
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Haftanın Yıldızları</h2><span class="muted">En çok hediye alanlar</span></div>
      <div class="rank-strip">
        ${gifters.map((g) => `
          <a class="rank-item rank-${g.rank}" href="#/profile/${g.user.id}">
            <span class="rank-no">${g.rank}</span>
            ${avatarImg(g.user, 'avatar-md')}
            <b>${esc(g.user.display_name)}</b>
            <small><span class="coin coin-sm"></span>${formatCoins(g.total_coins)}</small>
          </a>`).join('')}
      </div>
    </section>

    <section class="section" ${active.length ? '' : 'hidden'}>
      <div class="section-head"><h2>Şu An Aktif</h2></div>
      <div class="room-list">${active.map(roomRow).join('')}</div>
    </section>`;

  const scrollToSection = (id) => root.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  // Bağlantısı ya da kaydırma hedefi olmayan öğeler henüz yapılmadı
  const follow = (item) => {
    if (item.href) location.hash = item.href;
    else if (item.scrollTo) scrollToSection(item.scrollTo);
    else toast('Yakında');
  };

  paintNotificationBadge();

  root.addEventListener('click', (event) => {
    const topTab = event.target.closest('[data-top-tab]');
    if (topTab && topTab.dataset.topTab !== 'discover') follow(TOP_TABS.find((t) => t.id === topTab.dataset.topTab));

    const quick = event.target.closest('[data-quick]');
    if (quick) follow(QUICK_TILES.find((t) => t.id === quick.dataset.quick));

    const game = event.target.closest('[data-game]');
    if (game) {
      const item = GAMES.find((g) => g.id === game.dataset.game);
      if (item.isPlayable) {
        location.hash = '#/explore?category=game';
        toast(`${item.name} oda içinden oynanır: bir odaya gir, alttaki oyun düğmesine dokun`);
      } else {
        toast(`${item.name} yakında geliyor`);
      }
    }

    if (event.target.closest('[data-action="notifications"]')) location.hash = '#/notifications';
  });

  // Banner otomatik kaydırma; kullanıcı elle kaydırırsa noktalar da güncellenir.
  // Slaytlar tam genişlik değil (yanda bir sonrakinin ucu görünür), bu yüzden slayt genişliğiyle hesaplanır.
  const track = root.querySelector('.banner-track');
  const slideStep = () => (track.firstElementChild?.getBoundingClientRect().width ?? track.clientWidth) + 10;
  const currentIndex = () => Math.round(track.scrollLeft / slideStep());
  track.addEventListener('scroll', () => {
    const index = currentIndex();
    track.querySelectorAll('.banner-dots').forEach((group) => {
      [...group.children].forEach((dot, i) => dot.classList.toggle('is-active', i === index));
    });
  }, { passive: true });
  const bannerTimer = setInterval(() => {
    const next = (currentIndex() + 1) % banners.length;
    track.scrollTo({ left: next * slideStep(), behavior: 'smooth' });
  }, 4500);

  // Bugünkü giriş ödülü alınmadıysa günde bir kez hatırlat
  maybeShowCheckin();

  return () => clearInterval(bannerTimer);
}
