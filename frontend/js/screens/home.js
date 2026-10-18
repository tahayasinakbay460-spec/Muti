// Ana sayfa: banner, popüler odalar, sıralama, tanışabileceğin kişiler
import { api } from '../api.js';
import { APP_NAME, ROOM_CATEGORIES } from '../config.js';
import { esc, icon, avatarImg, formatCoins, joinParts, toast } from '../ui.js';
import { roomCard, roomRow, chips, coinPill } from './components.js';

export async function renderHome(root) {
  const [me, banners, suggested, gifters] = await Promise.all([
    api.getMe(), api.listBanners(), api.listSuggestedUsers(), api.listTopGifters(),
  ]);
  let activeCategory = 'for_you';

  root.innerHTML = `
    <header class="topbar">
      <div class="logo"><span class="logo-mark">M</span><span class="logo-text">${APP_NAME}</span></div>
      <div class="topbar-actions">
        <a class="icon-btn" href="#/explore" aria-label="Ara">${icon('search', 20)}</a>
        ${coinPill(me.coin_balance)}
        <button class="icon-btn has-dot" data-action="notifications" aria-label="Bildirimler">${icon('bell', 20)}</button>
      </div>
    </header>

    <div id="category-chips">${chips(ROOM_CATEGORIES, activeCategory)}</div>

    <section class="banner" id="banner">
      <div class="banner-track">
        ${banners.map((b) => `
          <a class="banner-slide" href="${esc(b.target)}">
            <img src="${esc(b.image_url)}" alt="" />
            <div class="banner-text">
              <h2>${esc(b.title).replace(/\n/g, '<br />')}</h2>
              <span class="banner-cta">${esc(b.cta)} <i>${icon('chevron-right', 14)}</i></span>
            </div>
          </a>`).join('')}
      </div>
      <div class="banner-dots">${banners.map((_, i) => `<i class="${i === 0 ? 'is-active' : ''}"></i>`).join('')}</div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Popüler Odalar</h2><a href="#/explore">Tümünü Gör ${icon('chevron-right', 14)}</a></div>
      <div class="room-grid" id="popular-rooms"></div>
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

    <section class="section">
      <div class="section-head"><h2>Tanışabileceğin Kişiler</h2><a href="#/explore">Tümünü Gör ${icon('chevron-right', 14)}</a></div>
      <div class="people-strip">
        ${suggested.map((u) => `
          <div class="person" data-user="${u.id}">
            <a class="person-avatar" href="#/profile/${u.id}">
              ${avatarImg(u, 'avatar-lg')}
              ${u.is_online ? '<span class="online-dot"></span>' : ''}
            </a>
            <button class="person-follow ${u.is_following ? 'is-following' : ''}" data-action="follow" aria-label="Takip et">${icon(u.is_following ? 'check' : 'plus', 14)}</button>
            <b>${esc(u.display_name)}</b>
            <small>${esc(joinParts([u.age, u.city]))}</small>
          </div>`).join('')}
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Şu An Aktif</h2></div>
      <div class="room-list" id="active-rooms"></div>
    </section>`;

  const popularEl = root.querySelector('#popular-rooms');
  const activeEl = root.querySelector('#active-rooms');

  async function loadRooms() {
    const rooms = await api.listRooms({ category: activeCategory });
    const sorted = [...rooms].sort((a, b) => a.hourly_rank - b.hourly_rank);
    popularEl.innerHTML = sorted.slice(0, 4).map(roomCard).join('') || '<p class="muted">Bu kategoride oda yok.</p>';
    activeEl.innerHTML = sorted.slice(4).map(roomRow).join('');
    activeEl.closest('.section').hidden = sorted.length <= 4;
  }
  await loadRooms();

  root.querySelector('#category-chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-chip]');
    if (!chip) return;
    activeCategory = chip.dataset.chip;
    root.querySelectorAll('#category-chips .chip').forEach((c) => c.classList.toggle('is-active', c === chip));
    loadRooms();
  });

  root.addEventListener('click', async (event) => {
    const followBtn = event.target.closest('[data-action="follow"]');
    if (followBtn) {
      const { is_following } = await api.toggleFollow(followBtn.closest('[data-user]').dataset.user);
      followBtn.classList.toggle('is-following', is_following);
      followBtn.innerHTML = icon(is_following ? 'check' : 'plus', 14);
      toast(is_following ? 'Takip edildi' : 'Takipten çıkıldı');
    }
    if (event.target.closest('[data-action="notifications"]')) toast('Yeni bildirimin yok');
  });

  // Banner otomatik kaydırma; kullanıcı elle kaydırırsa noktalar da güncellenir
  const track = root.querySelector('.banner-track');
  const dots = [...root.querySelectorAll('.banner-dots i')];
  const syncDots = () => {
    const index = Math.round(track.scrollLeft / track.clientWidth);
    dots.forEach((dot, i) => dot.classList.toggle('is-active', i === index));
  };
  track.addEventListener('scroll', syncDots, { passive: true });
  const bannerTimer = setInterval(() => {
    const next = (Math.round(track.scrollLeft / track.clientWidth) + 1) % banners.length;
    track.scrollTo({ left: next * track.clientWidth, behavior: 'smooth' });
  }, 4500);

  return () => clearInterval(bannerTimer);
}
