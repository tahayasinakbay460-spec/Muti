// Uygulama girişi: hash tabanlı yönlendirme ve alt sekme çubuğu (Muti · Anılar · Odalar · Mesajlar · Profil).
import { api } from './api.js';
import { API_BASE_URL, APP_NAME } from './config.js';
import { esc, icon, closeAllSheets, goBack, toast } from './ui.js';
import { startInbox, stopInbox, refreshUnread, paintUnreadBadge } from './inbox.js';
import { renderAuth } from './screens/auth.js';
import { renderHome } from './screens/home.js';
import { renderExplore } from './screens/explore.js';
import { renderRoom, roomSession } from './screens/room.js';
import { renderMessages, renderRequests, renderVisitors } from './screens/messages.js';
import { renderChat } from './screens/chat.js';
import { renderMoments } from './screens/moments.js';
import { renderMyRooms } from './screens/my-rooms.js';
import { renderRooms } from './screens/rooms.js';
import { renderProfile } from './screens/profile.js';
import { renderWallet } from './screens/wallet.js';
import { renderStore } from './screens/store.js';
import { renderVip } from './screens/vip.js';
import { renderTasks } from './screens/tasks.js';
import { renderLeaderboard } from './screens/leaderboard.js';
import { renderFamilies, renderFamily } from './screens/families.js';
import { renderEvents, renderEvent } from './screens/events.js';
import { renderAgency } from './screens/agency.js';
import { renderNotifications } from './screens/notifications.js';
import { renderSettings } from './screens/settings.js';

const routes = [
  { pattern: /^\/auth$/, render: renderAuth, isPublic: true },
  { pattern: /^\/home$/, render: renderHome, tab: 'home' },
  { pattern: /^\/explore$/, render: renderExplore, tab: 'rooms' },
  { pattern: /^\/rooms$/, render: renderRooms, tab: 'rooms' },
  { pattern: /^\/room\/(\d+)$/, render: renderRoom, isFixed: true },
  { pattern: /^\/moments$/, render: renderMoments, tab: 'moments' },
  { pattern: /^\/messages$/, render: renderMessages, tab: 'messages' },
  { pattern: /^\/requests$/, render: renderRequests, tab: 'messages' },
  { pattern: /^\/visitors$/, render: renderVisitors, tab: 'messages' },
  { pattern: /^\/my-rooms$/, render: renderMyRooms, tab: 'rooms' },
  { pattern: /^\/chat\/(\d+)$/, render: renderChat, isFixed: true },
  { pattern: /^\/profile$/, render: renderProfile, tab: 'profile' },
  { pattern: /^\/profile\/(\d+)$/, render: renderProfile },
  { pattern: /^\/wallet$/, render: renderWallet, tab: 'profile' },
  { pattern: /^\/store$/, render: renderStore, tab: 'profile' },
  { pattern: /^\/vip$/, render: renderVip, tab: 'profile' },
  { pattern: /^\/tasks$/, render: renderTasks, tab: 'rooms' },
  { pattern: /^\/agency$/, render: renderAgency, tab: 'rooms' },
  { pattern: /^\/leaderboard$/, render: renderLeaderboard, tab: 'rooms' },
  { pattern: /^\/families$/, render: renderFamilies, tab: 'rooms' },
  { pattern: /^\/family\/(\d+)$/, render: renderFamily, tab: 'rooms' },
  { pattern: /^\/events$/, render: renderEvents, tab: 'rooms' },
  { pattern: /^\/event\/(\d+)$/, render: renderEvent, tab: 'rooms' },
  { pattern: /^\/notifications$/, render: renderNotifications },
  { pattern: /^\/settings$/, render: renderSettings },
];

// Beş sekme; ortadaki büyük düğme Odalar (yayın odam, ajans, popüler ve tüm odalar orada).
// Cüzdan/VIP/mağaza profildeki kısayollardan ve ana sayfadaki bakiyeden açılır.
const TABS = [
  { id: 'home', label: APP_NAME, icon: 'home', href: '#/home' },
  { id: 'moments', label: 'Anılar', icon: 'image', href: '#/moments' },
  { id: 'rooms', label: 'Odalar', icon: 'radio', href: '#/rooms', isCenter: true },
  { id: 'messages', label: 'Mesajlar', icon: 'chat', href: '#/messages' },
  { id: 'profile', label: 'Profil', icon: 'user', href: '#/profile' },
];

const screenEl = document.getElementById('screen');
const tabbarEl = document.getElementById('tabbar');
const roomBubbleEl = document.getElementById('room-bubble');
let cleanup = null;
let renderToken = 0;
// Açık oda: { id, view, cleanup }. Başka sayfaya geçince kapanmaz, görünmez olup arka planda
// çalışmaya devam eder (ses ve bağlantı açık kalır). Yalnızca closeRoom kapatır.
let activeRoom = null;

const isRoomParked = () => Boolean(activeRoom?.view.classList.contains('is-parked'));

function closeRoom() {
  if (!activeRoom) return;
  const { view, cleanup: closeConnections } = activeRoom;
  activeRoom = null;
  closeConnections();
  view.remove();
  renderRoomBubble();
}

// Arka plandaki odaya dönmeyi sağlayan sağ alttaki yuvarlak düğme
function renderRoomBubble() {
  const isVisible = isRoomParked();
  roomBubbleEl.hidden = !isVisible;
  if (!isVisible) return;
  const room = roomSession.getRoom();
  roomBubbleEl.innerHTML = `
    <a class="room-bubble-open" href="#/room/${activeRoom.id}" aria-label="${esc(room.title)} odasına dön">
      <img src="${esc(room.cover_url)}" alt="" />
    </a>
    <button class="room-bubble-close" data-action="close-room" aria-label="Odadan çık">${icon('close', 14)}</button>`;
}

roomBubbleEl.addEventListener('click', (event) => {
  if (event.target.closest('[data-action="close-room"]')) closeRoom();
});

// Oda ekranı "çık" dediğinde, atıldığında ya da oda kapandığında buraya gelir.
// Kullanıcı başka sayfadaysa (oda arka plandaysa) o sayfadan koparılmaz.
roomSession.exit = () => {
  const wasParked = isRoomParked();
  closeRoom();
  // Odadan çıkınca odaya girmeden önceki sayfaya dönülür (ör. Odalar listesi)
  if (!wasParked) goBack('#/rooms');
};

function renderTabbar(activeTab) {
  tabbarEl.hidden = !activeTab;
  if (!activeTab) return;
  tabbarEl.innerHTML = TABS.map((tab) => (
    tab.isCenter
      ? `<a class="tab tab-center ${tab.id === activeTab ? 'is-active' : ''}" href="${tab.href}" data-tab="${tab.id}"><span class="tab-center-btn">${icon(tab.icon, 26)}</span><span>${tab.label}</span></a>`
      : `<a class="tab ${tab.id === activeTab ? 'is-active' : ''}" href="${tab.href}" data-tab="${tab.id}">${icon(tab.icon, 24)}<span>${esc(tab.label)}</span></a>`
  )).join('');
  paintUnreadBadge();
}

async function handleRoute() {
  const [path, queryString = ''] = (location.hash.slice(1) || '/home').split('?');
  const query = Object.fromEntries(new URLSearchParams(queryString));

  let match = null;
  const route = routes.find((r) => (match = path.match(r.pattern)));
  if (!route) {
    location.hash = '#/home';
    return;
  }
  if (!route.isPublic && !api.isAuthenticated()) {
    location.hash = '#/auth';
    return;
  }
  if (route.isPublic && api.isAuthenticated()) {
    location.hash = '#/home';
    return;
  }

  // Kişiye özel kanal giriş yapılıyken açık, giriş ekranında kapalı
  if (route.isPublic) {
    stopInbox();
  } else {
    startInbox();
    // Sohbet ekranında okunanlar sayacı düşürür; ekran değişince rozeti sunucudan tazele
    refreshUnread();
  }

  // Önceki ekranın zamanlayıcı/bağlantılarını kapat
  if (cleanup) cleanup();
  cleanup = null;
  const roomId = route.render === renderRoom ? match[1] : null;
  // Aynı anda tek oda: çıkış yapınca ya da başka odaya girince açık oda gerçekten kapanır
  if (route.isPublic || (roomId && roomId !== activeRoom?.id)) closeRoom();
  closeAllSheets();
  const token = ++renderToken;

  renderTabbar(route.tab);
  screenEl.className = `screen ${route.tab ? 'has-tabbar' : ''} ${route.isFixed ? 'is-fixed' : ''}`;
  screenEl.scrollTop = 0;
  // Arka plandaki oda sayfadan sökülmez; sökülse YouTube oynatıcısı baştan yüklenirdi
  [...screenEl.children].forEach((child) => {
    if (child !== activeRoom?.view) child.remove();
  });

  // Arka plandaki odaya dönüş: bağlantılar açık, yeniden çizmeye gerek yok
  if (roomId && activeRoom) {
    activeRoom.view.classList.remove('is-parked');
    renderRoomBubble();
    return;
  }
  activeRoom?.view.classList.add('is-parked');
  renderRoomBubble();

  // Her ekran yeni bir kapsayıcıya çizilir; böylece eski ekranın event dinleyicileri birikmez
  const view = document.createElement('div');
  view.className = 'view';
  view.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  screenEl.append(view);

  try {
    const result = await route.render(view, { params: match.slice(1), query });
    // Kullanıcı render bitmeden başka sayfaya geçtiyse geç gelen cleanup'ı hemen çalıştır
    if (token !== renderToken) result?.();
    else if (roomId) activeRoom = { id: roomId, view, cleanup: result };
    else cleanup = result || null;
    if (token === renderToken && !roomId) restoreScroll(token);
  } catch (error) {
    console.error(error);
    if (token !== renderToken) return;
    toast(error.message || 'Bir şeyler ters gitti.', 'error');
    view.innerHTML = '<div class="empty"><p>Sayfa yüklenemedi.</p><a class="btn btn-primary" href="#/home">Ana sayfaya dön</a></div>';
  }
}

// ── Yüklenen fotoğraflar (yalnızca geliştirmede) ─────────────────────────────
// Yüklenen fotoğrafların adresi "/api/v1/media/images/..." biçimindedir. Canlıda sayfa ve API aynı
// adreste olduğu için doğrudan açılır. Geliştirmede sayfa 5500'den, API 8000'den açıldığından ilk
// deneme boşa düşer; düşen resmi bir kez API adresinden yeniden isteriz.
if (!API_BASE_URL.startsWith(location.origin)) {
  const apiOrigin = new URL(API_BASE_URL).origin;
  document.addEventListener('error', (event) => {
    const img = event.target;
    if (img?.tagName !== 'IMG' || img.dataset.retried) return;
    const url = new URL(img.src, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/v1/media/')) return;
    img.dataset.retried = '1';
    img.src = apiOrigin + url.pathname;
  }, true);   // resim hataları kabarcık (bubble) yapmaz; yakalama (capture) aşamasında dinlenir
}

// ── Geri tuşu ────────────────────────────────────────────────────────────────
// Ekranlardaki geri tuşları (data-back) bir önceki sayfaya döner: tarayıcının kendi geçmişi.
// Her sayfaya geçmişte bir "derinlik" numarası yazılır. Derinlik 1 ise uygulama bu sayfadan açılmış
// demektir (bağlantıyla geldi, sayfa yenilendi): geri gidince uygulamadan çıkmasın diye tuşun kendi
// adresine (href, ör. #/home) gidilir.
let navDepth = 0;

// ── Kaydırma konumu ──────────────────────────────────────────────────────────
// Geri tuşuyla bir sayfaya dönünce sayfa en üstten değil, bırakıldığı yerden açılsın.
// Kaydırdıkça konum o sayfanın geçmiş kaydına (history.state.scroll) yazılır. Neden kaydırırken?
// Başka sayfaya geçildiğinde (hashchange) tarayıcı geçmişte çoktan yeni kayda geçmiş olur;
// eski sayfanın konumunu o an yazacak yer kalmaz.
// Sayfalar kendi kaydırma kutumuzda (#screen) kaydığı için tarayıcının kendi hatırlaması işe yaramaz.
let returnScroll = null;   // geri/ileri ile dönülen sayfanın kayıtlı konumu; yeni sayfada null
let scrollSaveTimer = null;

screenEl.addEventListener('scroll', () => {
  // Her kaydırma olayında değil, durunca bir kez yaz (tarayıcı sık replaceState'i yavaşlatır/sınırlar)
  clearTimeout(scrollSaveTimer);
  scrollSaveTimer = setTimeout(() => {
    history.replaceState({ ...(history.state || {}), scroll: Math.round(screenEl.scrollTop) }, '');
  }, 150);
}, { passive: true });

// Ekran çizildikten sonra kayıtlı konuma in. Liste parça parça yükleniyorsa (sonsuz kaydırma)
// sayfa henüz o kadar uzun olmayabilir: 2 saniye boyunca her karede yeniden denenir.
// Kullanıcı bu arada başka sayfaya geçerse (token değişir) ya da kendisi kaydırırsa bırakılır.
function restoreScroll(token) {
  const target = returnScroll;
  returnScroll = null;
  if (!target) return;
  const startedAt = performance.now();
  let last = null;
  const step = () => {
    if (token !== renderToken) return;
    if (last !== null && Math.abs(screenEl.scrollTop - last) > 2) return;   // kullanıcı kaydırdı
    screenEl.scrollTop = target;
    last = screenEl.scrollTop;
    if (last < target - 2 && performance.now() - startedAt < 2000) requestAnimationFrame(step);
  };
  step();
}

function rememberDepth() {
  const known = history.state?.depth;
  // Geçmişte zaten numarası olan sayfaya (geri/ileri ile) dönüldü: o numarayı ve kaydırma konumunu kullan
  navDepth = known || navDepth + 1;
  returnScroll = known ? history.state.scroll ?? null : null;
  clearTimeout(scrollSaveTimer);   // önceki sayfanın bekleyen kaydı yeni sayfaya yazılmasın
  if (!known) history.replaceState({ ...(history.state || {}), depth: navDepth }, '');
}

document.addEventListener('click', (event) => {
  const back = event.target.closest('[data-back]');
  if (!back) return;
  event.preventDefault();
  goBack(back.getAttribute('href') || '#/home');
});

window.addEventListener('hashchange', () => { rememberDepth(); handleRoute(); });
rememberDepth();
handleRoute();
