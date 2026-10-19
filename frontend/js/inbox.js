// Gelen kutusu: kişiye özel kanal (/ws/me), okunmamış mesaj rozeti ve "yeni mesaj" bildirimi,
// bildirim merkezinin okunmamış sayısı (zil rozeti) ve "yeni bildirim" uyarısı.
// Giriş yapılı olduğu sürece tek bir bağlantı açık durur; ekranlar `onInbox` ile olaylara abone olur.
import { api } from './api.js';
import { connectUser } from './realtime.js';
import { esc, toast } from './ui.js';

let channel = null;
let unreadCount = 0;
let unreadNotifications = 0;
// Şu an ekranda açık olan sohbet; o sohbete gelen mesaj için bildirim çıkmaz, rozet artmaz
let openConversationId = null;

export function startInbox() {
  if (channel) return;
  channel = connectUser();
  channel.on('message:new', handleNewMessage);
  channel.on('notification:new', handleNewNotification);
  refreshUnread();
}

export function stopInbox() {
  channel?.close();
  channel = null;
  setUnread(0);
  setUnreadNotifications(0);
}

// Ekranların abone olması için. Dönen fonksiyon aboneliği bırakır (ekran temizliğinde çağrılır).
export function onInbox(event, handler) {
  channel?.on(event, handler);
  return () => channel?.off(event, handler);
}

export function setOpenConversation(conversationId) {
  openConversationId = conversationId == null ? null : Number(conversationId);
}

export async function refreshUnread() {
  try {
    const [messages, notifications] = await Promise.all([api.getUnreadCount(), api.getNotificationUnreadCount()]);
    setUnread(messages);
    setUnreadNotifications(notifications);
  } catch {
    // Rozet kritik değil; bir sonraki ekran değişiminde yeniden denenir
  }
}

// Bildirim ekranı açılınca sayaç sıfırlanır
export function clearNotificationBadge() {
  setUnreadNotifications(0);
}

function handleNewNotification(notification) {
  setUnreadNotifications(unreadNotifications + 1);
  if (!location.hash.startsWith('#/notifications')) toast(`🔔 ${notification.text}`);
}

function setUnreadNotifications(count) {
  unreadNotifications = count;
  paintNotificationBadge();
}

// Ana sayfadaki zil. Ekran yeniden çizilince home.js de bunu çağırır.
export function paintNotificationBadge() {
  const bell = document.querySelector('[data-action="notifications"]');
  if (!bell) return;
  bell.classList.toggle('has-dot', unreadNotifications > 0);
}

function handleNewMessage({ conversation_id: conversationId, sender, message }) {
  if (message.from_me || conversationId === openConversationId) return;
  setUnread(unreadCount + 1);
  // Mesajlar listesi açıksa satırlar zaten güncellenir; bildirim gerekmez
  if (location.hash.startsWith('#/messages')) return;
  toast(`💬 ${sender.display_name}: ${message.text.length > 40 ? `${message.text.slice(0, 40)}…` : message.text}`);
}

function setUnread(count) {
  unreadCount = count;
  paintUnreadBadge();
}

// Alt çubuk her ekran değişiminde yeniden çizildiği için app.js de bunu çağırır
export function paintUnreadBadge() {
  const tab = document.querySelector('.tab[data-tab="messages"]');
  if (!tab) return;
  tab.querySelector('.tab-badge')?.remove();
  if (unreadCount > 0) {
    tab.insertAdjacentHTML('beforeend', `<i class="tab-badge">${esc(unreadCount > 99 ? '99+' : unreadCount)}</i>`);
  }
}
