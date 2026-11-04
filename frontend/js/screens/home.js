// Ana sayfa (alt çubukta "Muti"). Yukarıdan aşağı:
//   üst çubuk: avatarım, bakiye (+), mağaza · görevler, arama
//   → günlük giriş şeridi (bugünkü ödül alınmadıysa "Al")
//   → Klasik oyunlar: üç sütun, aşağı doğru; 8 oyun + "Diğer oyunlar" (hepsi alttan açılan panelde)
//   → Sana Özel: havuz (vitrin) odaları, geniş kartlar.
// Odaların tamamı, Yayın odam, Ajans ve Popüler ayrı "Odalar" sekmesinde (rooms.js).
import { api } from '../api.js';
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet } from '../ui.js';
import { coinPill } from './components.js';
import { seatedAvatars, statusPill, listenerCount } from './rooms.js';
import { openCreateRoomSheet } from './create-room.js';
import { maybeShowCheckin } from './tasks.js';

// Oyun vitrini. `inRoom`: bugün oda içinden oynanabilenler; diğerleri yalnızca görsel ("Yakında").
// DEMO: oyun görselleri renk + emoji; kendi oyun görsellerimiz gelince `art-*` sınıfları görsel olur.
const GAMES = [
  { id: 'roulette', name: 'Rulet', emoji: '🎡', inRoom: true },
  { id: 'connect4', name: 'Dört Bağla', emoji: '🔴', inRoom: true, tag: 'Yeni' },
  { id: 'rps', name: 'Taş Kağıt Makas', emoji: '✂️', inRoom: true },
  { id: 'ludo', name: 'Ludo', emoji: '🏁' },
  { id: 'okey', name: '101 Okey', emoji: '🀄' },
  { id: 'backgammon', name: 'Tavla', emoji: '🎲' },
  { id: 'domino', name: 'Domino', emoji: '🁣' },
  { id: 'uno', name: 'UNO', emoji: '🃏' },
  { id: 'chess', name: 'Satranç', emoji: '♟️' },
  { id: 'carrom', name: 'Carrom', emoji: '🥏' },
  { id: 'billiards', name: 'Bilardo', emoji: '🎱' },
  { id: 'draw', name: 'Çiz Tahmin Et', emoji: '🎨' },
  { id: 'werewolf', name: 'Kurt Adam', emoji: '🐺' },
  { id: 'mines', name: 'Mayın Tarlası', emoji: '💣' },
  { id: 'song', name: 'Şarkı Tahmini', emoji: '🎵' },
  { id: 'match', name: 'Eşleştirme', emoji: '🧩' },
];
const FRONT_GAMES = 8;      // ana sayfada görünen; kalanı "Diğer oyunlar"
const SHOWCASE_SIZE = 8;

// Üç sütunlu büyük oyun kartı: adı kartın içinde, altta
const gameCard = (g) => `
  <button class="game-card art-${g.id}" data-game="${g.id}">
    ${g.tag ? `<em class="game-tag">${g.tag}</em>` : g.inRoom ? '' : '<em class="game-tag game-tag-soon">Yakında</em>'}
    <i>${g.emoji}</i>
    <b>${esc(g.name)}</b>
  </button>`;

// Oyuna dokununca: odada oynanıyorsa oyun odalarına götür, değilse "yakında"
function openGame(gameId) {
  const item = GAMES.find((g) => g.id === gameId);
  if (!item) return;
  if (item.inRoom) {
    location.hash = '#/rooms?filter=game';
    toast(`${item.name} odada oynanır: bir odaya gir, alttaki oyun düğmesine dokun`);
  } else {
    toast(`${item.name} yakında geliyor`);
  }
}

function openAllGames() {
  const sheet = openSheet(`
    <h2 class="sheet-title">Bütün oyunlar</h2>
    <div class="game-grid game-grid-sheet">${GAMES.map(gameCard).join('')}</div>`, { className: 'sheet-tall' });
  sheet.el.addEventListener('click', (event) => {
    const game = event.target.closest('[data-game]');
    if (!game) return;
    sheet.close();
    openGame(game.dataset.game);
  });
}

// Sana Özel: geniş vitrin kartı (yeni kullanıcı ilk bunları görür)
function showcaseCard(room) {
  return `
    <a class="showcase-card" href="#/room/${room.id}">
      <img src="${esc(room.cover_url)}" alt="" loading="lazy" />
      <span class="showcase-top">${statusPill(room)}<span class="pill pill-dark">${listenerCount(room)}</span></span>
      <span class="showcase-body">
        <b>${esc(room.title)}</b>
        <span class="showcase-host">${avatarImg(room.host, 'avatar-xs')}<span>${esc(room.host.display_name)}</span><em>${esc(CATEGORY_LABELS[room.category] || '')}</em></span>
        <span class="avatar-stack">${seatedAvatars(room, 5)}</span>
      </span>
    </a>`;
}

// Günlük giriş şeridi: alınmadıysa ödülü söyler ve "Al" düğmesi; alındıysa görevlere götürür
function checkinBanner(status) {
  if (!status) return '';
  const coins = status.rewards[status.day - 1] || 0;
  return status.claimed_today
    ? `<a class="promo-banner is-done" href="#/tasks">
         <span class="promo-banner-icon">${icon('target', 22)}</span>
         <span class="promo-banner-text"><b>Günlük ödülünü aldın</b><small>Görevleri tamamla, daha çok coin kazan</small></span>
         <span class="btn btn-sm btn-soft">Görevler</span>
       </a>`
    : `<div class="promo-banner">
         <span class="promo-banner-icon">🎁</span>
         <span class="promo-banner-text"><b>${status.day}. gün giriş ödülün hazır</b><small>Bugün al: +${formatCoins(coins)} coin · art arda gel, ödül büyüsün</small></span>
         <button class="btn btn-sm btn-primary" data-action="checkin">Al</button>
       </div>`;
}

export async function renderHome(root) {
  const [me, rooms, checkin] = await Promise.all([
    api.getMe(),
    api.listRooms({ category: 'for_you', limit: 30 }),
    api.getCheckin().catch(() => null),
  ]);
  const showcase = [...rooms].sort((a, b) => b.listener_count - a.listener_count).slice(0, SHOWCASE_SIZE);

  root.innerHTML = `
    <header class="home-head">
      <a class="home-me" href="#/profile" aria-label="Profilim">${avatarImg(me, 'avatar-sm')}</a>
      ${coinPill(me.coin_balance)}
      <a class="icon-btn icon-btn-plain" href="#/store" aria-label="Mağaza">${icon('gift', 22)}</a>
      <div class="topbar-actions">
        <a class="icon-btn icon-btn-plain" href="#/tasks" aria-label="Görevler">${icon('target', 22)}</a>
        <a class="icon-btn icon-btn-plain" href="#/explore?focus=1" aria-label="Ara">${icon('search', 22)}</a>
      </div>
    </header>

    <div id="checkin-slot">${checkinBanner(checkin)}</div>

    <section class="home-section">
      <div class="section-head"><h2>Klasik oyunlar</h2><button class="btn btn-sm btn-soft" data-action="create-room">Özel oda ${icon('plus', 14)}</button></div>
      <div class="game-grid">
        ${GAMES.slice(0, FRONT_GAMES).map(gameCard).join('')}
        <button class="game-card game-card-more" data-action="all-games"><i>🎮</i><b>Diğer oyunlar</b></button>
      </div>
    </section>

    <section class="home-section">
      <div class="section-head"><h2>Sana Özel</h2><a href="#/rooms">Tüm odalar ${icon('chevron-right', 13)}</a></div>
      <div class="showcase-strip">
        ${showcase.map(showcaseCard).join('') || '<p class="muted">Şu an açık oda yok.</p>'}
      </div>
    </section>`;

  root.addEventListener('click', async (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'create-room') return openCreateRoomSheet();
    if (action === 'all-games') return openAllGames();
    if (action === 'checkin') {
      const button = event.target.closest('[data-action]');
      button.disabled = true;
      try {
        const result = await api.claimCheckin();
        toast(`🎉 ${result.day}. gün ödülü: +${formatCoins(result.coins)} coin`, 'success');
        root.querySelector('.coin-pill b').textContent = formatCoins(result.coin_balance);
        root.querySelector('#checkin-slot').innerHTML = checkinBanner({ ...checkin, claimed_today: true });
      } catch (error) {
        toast(error.message, 'error');
        button.disabled = false;
      }
      return;
    }
    const game = event.target.closest('[data-game]');
    if (game) openGame(game.dataset.game);
  });

  // Bugünkü giriş ödülü alınmadıysa günde bir kez hatırlat
  maybeShowCheckin();
}
