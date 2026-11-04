// Gerçek zamanlı kanallar. Event adları `domain:action` biçimindedir ve backend ile aynıdır.
//   - connectRoom → oda kanalı (/ws/rooms/:id): sohbet, hediye, koltuklar.
//   - connectUser → kişiye özel kanal (/ws/me): `message:new` (özel mesaj). Giriş yapılı olduğu sürece açık.
//
// İstemci yalnızca şunları gönderir: `chat:message` { text }, `game:dice_rolled` {},
// `game:roulette_start` {} ve `game:roulette_bet` { color }.
// Moderasyon (roller, koltuk, susturma, mesaj silme, atma, oda ayarları) REST ile yapılır;
// sonucu sunucu `room:seats_updated`, `room:roles_updated`, `room:chat_muted`,
// `chat:message_deleted`, `room:user_kicked`, `room:updated`, `room:closed` olarak yayınlar.
// Odaya girince yalnızca bize `chat:history` (son mesajlar) gelir; koltuğa davet edilince `room:seat_invite`.
// Mesajın sahibini ve zarın sonucunu sunucu belirler, sonra tüm odaya yayınlar.
import { WS_BASE_URL, STORAGE_KEYS } from './config.js';
import { refreshSession } from './api.js';

class BaseChannel {
  constructor() {
    this.handlers = {};
  }

  on(event, handler) {
    (this.handlers[event] ||= []).push(handler);
    return this;
  }

  off(event, handler) {
    this.handlers[event] = (this.handlers[event] || []).filter((h) => h !== handler);
  }

  emit(event, payload) {
    (this.handlers[event] || []).forEach((handler) => handler(payload));
  }
}

// Sunucunun özel kapanış kodları (bkz. backend realtime/room_socket.py)
const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_BANNED = 4403;
const CLOSE_ROOM_NOT_FOUND = 4404;
const CLOSE_REPLACED = 4409;
const MAX_RECONNECT_ATTEMPTS = 5;

// Kopunca yeniden bağlanan WebSocket kanalı. `path`: '/rooms/12' ya da '/me'
class WebSocketChannel extends BaseChannel {
  constructor(path) {
    super();
    this.path = path;
    this.isClosed = false;
    this.attempts = 0;
    this.queue = [];
    this.connect();
  }

  connect() {
    const token = localStorage.getItem(STORAGE_KEYS.accessToken) || '';
    // resume: sunucu koparken kaçırdıklarımızı (koltukları) yeniden göndersin
    const resume = this.hasConnected ? '&resume=true' : '';
    const socket = new WebSocket(`${WS_BASE_URL}${this.path}?token=${encodeURIComponent(token)}${resume}`);
    this.socket = socket;

    socket.addEventListener('open', () => {
      if (this.hasConnected) this.emit('connection:reopened', {});
      this.hasConnected = true;
      this.attempts = 0;
      // Bağlantı açılmadan önce gönderilmek istenenleri şimdi yolla
      this.queue.splice(0).forEach((data) => socket.send(data));
    });

    socket.addEventListener('message', (message) => {
      const { event, payload } = JSON.parse(message.data);
      this.emit(event, payload);
    });

    socket.addEventListener('close', async ({ code }) => {
      if (this.isClosed || code === CLOSE_ROOM_NOT_FOUND) return;
      // Odadan atıldı: yasak süresince yeniden bağlanmayı denemenin anlamı yok
      if (code === CLOSE_BANNED) {
        this.emit('error', { code: 'room_banned', detail: 'Bu odadan çıkarıldın, bir süre giremezsin.' });
        return;
      }
      // Aynı hesap başka cihazdan girdi: yeniden bağlanırsak o cihazı biz atarız
      if (code === CLOSE_REPLACED) {
        this.emit('error', { code: 'session_replaced', detail: 'Hesabın başka bir cihazda bu odaya girdi.' });
        return;
      }
      if (++this.attempts > MAX_RECONNECT_ATTEMPTS) {
        this.emit('error', { code: 'connection_lost', detail: 'Bağlantı koptu. Sayfayı yenile.' });
        return;
      }
      try {
        // Access token'ın süresi dolmuş: yenisini al, sonra tekrar bağlan
        if (code === CLOSE_UNAUTHORIZED) await refreshSession();
        else await new Promise((resolve) => setTimeout(resolve, 1000 * this.attempts));
      } catch {
        return;
      }
      if (!this.isClosed) this.connect();
    });
  }

  send(event, payload) {
    const data = JSON.stringify({ event, payload });
    if (this.socket.readyState === WebSocket.OPEN) this.socket.send(data);
    else this.queue.push(data);
  }

  close() {
    this.isClosed = true;
    clearInterval(this.pingTimer);
    // 1000 = "kendim çıkıyorum". Sunucu ağ kopmasından bununla ayırır, koltuğu bekletmez.
    this.socket.close(1000);
    this.handlers = {};
  }
}

// Sunucu kişiyi son mesajından 5 dk sonrasına kadar çevrimiçi sayar; arada "buradayım" diyoruz
const PING_INTERVAL_MS = 2 * 60 * 1000;

export function connectRoom(room) {
  return new WebSocketChannel(`/rooms/${room.id}`);
}

export function connectUser() {
  const channel = new WebSocketChannel('/me');
  channel.pingTimer = setInterval(() => channel.send('ping', {}), PING_INTERVAL_MS);
  return channel;
}
