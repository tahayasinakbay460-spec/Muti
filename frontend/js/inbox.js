// Gelen kutusu: kişiye özel kanal (/ws/me), okunmamış mesaj rozeti ve "yeni mesaj" bildirimi.
// Giriş yapılı olduğu sürece tek bir bağlantı açık durur; ekranlar `onInbox` ile olaylara abone olur.
import { api } from './api.js';
import { connectUser } from './realtime.js';
import { esc, toast } from './ui.js';

let channel = null;
let unreadCount = 0;
// Şu an ekranda açık olan sohbet; o sohbete gelen mesaj için bildirim çıkmaz, rozet artmaz
let openConversationId = null;

export function startInbox() {
  if (channel) return;
  channel = connectUser();
  channel.on('message:new', handleNewMessage);
  refreshUnread();
}

export function stopInbox() {
  channel?.close();
  channel = null;
  setUnread(0);
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
    setUnread(await api.getUnreadCount());
  } catch {
    // Rozet kritik değil; bir sonraki ekran değişiminde yeniden denenir
  }
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
