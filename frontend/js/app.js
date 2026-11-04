// Uygulama girişi: hash tabanlı yönlendirme ve alt sekme çubuğu (Muti · Anılar · Odalar · Mesajlar · Profil).
import { api } from './api.js';
import { APP_NAME } from './config.js';
import { esc, icon, closeAllSheets, toast } from './ui.js';
import { startInbox, stopInbox, refreshUnread, paintUnreadBadge } from './inbox.js';
import { renderAuth } from './screens/auth.js';
import { renderHome } from './screens/home.js';
import { renderExplore } from './screens/explore.js';
import { renderRoom, roomSession } from './screens/room.js';
import { renderMessages, renderChat, renderRequests, renderVisitors } from './screens/messages.js';
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
  if (!wasParked) location.hash = '#/home';
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
  } catch (error) {
    console.error(error);
    if (token !== renderToken) return;
    toast(error.message || 'Bir şeyler ters gitti.', 'error');
    view.innerHTML = '<div class="empty"><p>Sayfa yüklenemedi.</p><a class="btn btn-primary" href="#/home">Ana sayfaya dön</a></div>';
  }
}

window.addEventListener('hashchange', handleRoute);
handleRoute();
