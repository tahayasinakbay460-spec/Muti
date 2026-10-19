// Bildirim merkezi: takip, hediye, seviye atlama, oda rolü bildirimleri
import { api } from '../api.js';
import { esc, icon, avatarImg } from '../ui.js';
import { clearNotificationBadge, onInbox } from '../inbox.js';

const TYPE_ICONS = { follow: '👤', gift_received: '🎁', level_up: '⭐', room_role: '👑' };

// Bildirime dokununca gidilecek yer
function targetHref(notification) {
  if (notification.data?.room_id) return `#/room/${notification.data.room_id}`;
  if (notification.actor) return `#/profile/${notification.actor.id}`;
  if (notification.type === 'level_up') return '#/profile';
  return null;
}

function notificationRow(n) {
  const href = targetHref(n);
  const tag = href ? 'a' : 'div';
  return `
    <${tag} class="notification ${n.is_read ? '' : 'is-unread'}" ${href ? `href="${href}"` : ''}>
      ${n.actor ? avatarImg(n.actor, 'avatar-md') : `<span class="notification-icon">${TYPE_ICONS[n.type] || '🔔'}</span>`}
      <span class="notification-body">
        <p>${esc(n.text)}</p>
        <small>${TYPE_ICONS[n.type] || ''} ${esc(n.time_label)}</small>
      </span>
    </${tag}>`;
}

export async function renderNotifications(root) {
  const notifications = await api.listNotifications();

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Bildirimler</h1>
      <span></span>
    </header>
    <div class="notification-list" id="notification-list">
      ${notifications.length
        ? notifications.map(notificationRow).join('')
        : `<div class="empty">${icon('bell', 40)}<p>Henüz bildirimin yok.</p></div>`}
    </div>`;

  // Ekran açıldı → hepsi okundu (rozet söner). Okunmamışlar bu açılışta vurgulu görünmeye devam eder.
  if (notifications.some((n) => !n.is_read)) {
    api.markNotificationsRead().catch(() => {});
  }
  clearNotificationBadge();

  // Ekran açıkken gelen bildirim listenin başına eklenir
  const listEl = root.querySelector('#notification-list');
  return onInbox('notification:new', (notification) => {
    listEl.querySelector('.empty')?.remove();
    listEl.insertAdjacentHTML('afterbegin', notificationRow(notification));
    clearNotificationBadge();
    api.markNotificationsRead().catch(() => {});
  });
}
