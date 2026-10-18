// Gerçek zamanlı kanallar. Event adları `domain:action` biçimindedir ve backend ile aynıdır.
//   - connectRoom → oda kanalı (/ws/rooms/:id): sohbet, hediye, koltuklar. Mock sürüm zamanlayıcıyla üretir.
//   - connectUser → kişiye özel kanal (/ws/me): `message:new` (özel mesaj). Giriş yapılı olduğu sürece açık.
//
// İstemci yalnızca şunları gönderir: `chat:message` { text }, `game:dice_rolled` {},
// `game:roulette_start` {} ve `game:roulette_bet` { color }.
// Moderasyon (koltuk kilitleme, atma) REST ile yapılır; sonucu sunucu `room:seats_updated`,
// `room:roles_updated` ve `room:user_kicked` olarak yayınlar.
// Mesajın sahibini ve zarın sonucunu sunucu belirler, sonra tüm odaya yayınlar.
import { USE_MOCK, WS_BASE_URL, STORAGE_KEYS } from './config.js';
import { refreshSession } from './api.js';
import { users, gifts, chatLines, CURRENT_USER_ID } from './mock-data.js';

const pick = (list) => list[Math.floor(Math.random() * list.length)];
const MOCK_RED_NUMBERS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

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

  // Gerçek backend'de hediye yayınını sunucu yapar (POST /gifts/send başarılı olunca).
  // Mock'ta sunucu olmadığı için ekran bu metodla yayını taklit eder.
  simulateServerEvent() {}
}

class MockRoomChannel extends BaseChannel {
  constructor(room, me) {
    super();
    this.room = room;
    this.me = me;
    this.timers = [];
    const others = users.filter((u) => u.id !== CURRENT_USER_ID);

    // Sohbet akışı
    this.timers.push(setInterval(() => {
      this.emit('chat:message', { user: pick(others), text: pick(chatLines) });
    }, 3800));

    // Ara sıra başka kullanıcılardan hediye
    this.timers.push(setInterval(() => {
      const seated = this.room.seats.filter((s) => s.user && s.user.id !== CURRENT_USER_ID);
      if (!seated.length) return;
      this.emit('gift:sent', {
        sender: pick(others), receiver: pick(seated).user, gift: pick(gifts.slice(0, 7)), quantity: pick([1, 1, 5, 10]),
      });
    }, 9000));

    // Konuşan koltuk göstergesi
    this.timers.push(setInterval(() => {
      const active = this.room.seats.filter((s) => s.user && !s.is_muted);
      this.emit('room:speaking', { seat_indexes: active.filter(() => Math.random() < 0.35).map((s) => s.index) });
    }, 1400));

    // Dinleyici sayısı dalgalanması
    this.timers.push(setInterval(() => {
      this.room.listener_count = Math.max(1, this.room.listener_count + pick([-1, 0, 1, 1, 2]));
      this.emit('room:listener_count', { listener_count: this.room.listener_count });
    }, 5000));

    this.timers.push(setTimeout(() => {
      this.emit('room:user_joined', { user: pick(others) });
    }, 2500));

    // Oda boş görünmesin diye koltuktakilerden birkaç açılış mesajı
    this.timers.push(setTimeout(() => {
      this.room.seats.filter((s) => s.user && s.user.id !== CURRENT_USER_ID).slice(0, 3).forEach((s, i) => {
        this.emit('chat:message', { user: s.user, text: chatLines[i] });
      });
    }, 0));
  }

  // Mock'ta sunucu olmadığı için sunucunun yapacağı işi burada taklit ediyoruz
  send(event, payload) {
    if (event === 'chat:message') {
      this.emit(event, { user: this.me, text: payload.text });
    } else if (event === 'game:dice_rolled') {
      const values = [1, 2].map(() => 1 + Math.floor(Math.random() * 6));
      this.timers.push(setTimeout(() => this.emit(event, { user: this.me, values }), 150));
    } else if (event === 'game:roulette_start' && !this.roulette) {
      this.roulette = { round_id: Date.now(), bets: new Map() };
      this.emit('game:roulette_started', { round_id: this.roulette.round_id, started_by: this.me, betting_seconds: 10 });
      this.timers.push(setTimeout(() => {
        const number = Math.floor(Math.random() * 37);
        const color = number === 0 ? 'green' : MOCK_RED_NUMBERS.has(number) ? 'red' : 'black';
        const winners = [...this.roulette.bets.values()].filter((b) => b.color === color).map((b) => b.user);
        this.emit('game:roulette_result', { round_id: this.roulette.round_id, number, color, winners, player_count: this.roulette.bets.size });
        this.roulette = null;
      }, 10000));
    } else if (event === 'game:roulette_bet' && this.roulette) {
      this.roulette.bets.set(this.me.id, { user: this.me, color: payload.color });
      this.emit('game:roulette_bet_placed', { round_id: this.roulette.round_id, user: this.me, color: payload.color });
    }
  }

  simulateServerEvent(event, payload) {
    this.emit(event, payload);
  }

  close() {
    this.timers.forEach((t) => { clearInterval(t); clearTimeout(t); });
    this.handlers = {};
  }
}

// Sunucunun özel kapanış kodları (bkz. backend realtime/room_socket.py)
const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_BANNED = 4403;
const CLOSE_ROOM_NOT_FOUND = 4404;
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
    const socket = new WebSocket(`${WS_BASE_URL}${this.path}?token=${encodeURIComponent(token)}`);
    this.socket = socket;

    socket.addEventListener('open', () => {
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
    this.socket.close();
    this.handlers = {};
  }
}

// Sunucu kişiyi son mesajından 5 dk sonrasına kadar çevrimiçi sayar; arada "buradayım" diyoruz
const PING_INTERVAL_MS = 2 * 60 * 1000;

export function connectRoom(room, me) {
  if (USE_MOCK) return new MockRoomChannel(room, me);
  const channel = new WebSocketChannel(`/rooms/${room.id}`);
  channel.room = room;
  return channel;
}

// Mock'ta kişiye özel olay yok (karşı tarafın cevabını sohbet ekranı kendisi taklit eder)
export function connectUser() {
  if (USE_MOCK) return Object.assign(new BaseChannel(), { close() {} });
  const channel = new WebSocketChannel('/me');
  channel.pingTimer = setInterval(() => channel.send('ping', {}), PING_INTERVAL_MS);
  return channel;
}
