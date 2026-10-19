// Uygulama girişi: hash tabanlı yönlendirme ve alt sekme çubuğu.
import { api } from './api.js';
import { icon, closeAllSheets, toast } from './ui.js';
import { startInbox, stopInbox, refreshUnread, paintUnreadBadge } from './inbox.js';
import { renderAuth } from './screens/auth.js';
import { renderHome } from './screens/home.js';
import { renderExplore } from './screens/explore.js';
import { renderFollowing } from './screens/following.js';
import { renderRoom } from './screens/room.js';
import { renderMessages, renderChat } from './screens/messages.js';
import { renderProfile } from './screens/profile.js';
import { renderWallet } from './screens/wallet.js';
import { renderNotifications } from './screens/notifications.js';
import { renderSettings } from './screens/settings.js';
import { openCreateRoomSheet } from './screens/create-room.js';

const routes = [
  { pattern: /^\/auth$/, render: renderAuth, isPublic: true },
  { pattern: /^\/home$/, render: renderHome, tab: 'home' },
  { pattern: /^\/explore$/, render: renderExplore, tab: 'explore' },
  { pattern: /^\/following$/, render: renderFollowing, tab: 'home' },
  { pattern: /^\/room\/(\d+)$/, render: renderRoom, isFixed: true },
  { pattern: /^\/messages$/, render: renderMessages, tab: 'messages' },
  { pattern: /^\/chat\/(\d+)$/, render: renderChat, isFixed: true },
  { pattern: /^\/profile$/, render: renderProfile, tab: 'profile' },
  { pattern: /^\/profile\/(\d+)$/, render: renderProfile },
  { pattern: /^\/wallet$/, render: renderWallet, tab: 'wallet' },
  { pattern: /^\/notifications$/, render: renderNotifications },
  { pattern: /^\/settings$/, render: renderSettings },
];

const TABS = [
  { id: 'home', label: 'Ana Sayfa', icon: 'home', href: '#/home' },
  { id: 'messages', label: 'Mesajlar', icon: 'chat', href: '#/messages' },
  { id: 'create', label: 'Oda Aç', icon: 'plus' },
  { id: 'wallet', label: 'Cüzdan', icon: 'wallet', href: '#/wallet' },
  { id: 'profile', label: 'Profil', icon: 'user', href: '#/profile' },
];

const screenEl = document.getElementById('screen');
const tabbarEl = document.getElementById('tabbar');
let cleanup = null;
let renderToken = 0;

function renderTabbar(activeTab) {
  tabbarEl.hidden = !activeTab;
  if (!activeTab) return;
  tabbarEl.innerHTML = TABS.map((tab) => (
    tab.id === 'create'
      ? `<button class="tab tab-create" data-action="create-room" aria-label="${tab.label}"><span class="tab-create-btn">${icon('plus', 28)}</span></button>`
      : `<a class="tab ${tab.id === activeTab ? 'is-active' : ''}" href="${tab.href}" data-tab="${tab.id}">${icon(tab.icon, 24)}<span>${tab.label}</span></a>`
  )).join('');
  paintUnreadBadge();
}

tabbarEl.addEventListener('click', (event) => {
  if (event.target.closest('[data-action="create-room"]')) openCreateRoomSheet();
});

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
  closeAllSheets();
  const token = ++renderToken;

  renderTabbar(route.tab);
  screenEl.className = `screen ${route.tab ? 'has-tabbar' : ''} ${route.isFixed ? 'is-fixed' : ''}`;
  screenEl.scrollTop = 0;
  // Her ekran yeni bir kapsayıcıya çizilir; böylece eski ekranın event dinleyicileri birikmez
  const view = document.createElement('div');
  view.className = 'view';
  view.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  screenEl.replaceChildren(view);

  try {
    const result = await route.render(view, { params: match.slice(1), query });
    // Kullanıcı render bitmeden başka sayfaya geçtiyse geç gelen cleanup'ı hemen çalıştır
    if (token !== renderToken) result?.();
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
