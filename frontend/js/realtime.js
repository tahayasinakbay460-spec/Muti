// Oda içi gerçek zamanlı kanal. Event adları `domain:action` biçimindedir ve
// backend WebSocket'i ile aynıdır; mock sürüm bunları zamanlayıcıyla üretir.
//
// İstemci yalnızca şunları gönderir: `chat:message` { text } ve `game:dice_rolled` {}.
// Mesajın sahibini ve zarın sonucunu sunucu belirler, sonra tüm odaya yayınlar.
import { USE_MOCK, WS_BASE_URL, STORAGE_KEYS } from './config.js';
import { refreshSession } from './api.js';
import { users, gifts, chatLines, CURRENT_USER_ID } from './mock-data.js';

const pick = (list) => list[Math.floor(Math.random() * list.length)];

class BaseChannel {
  constructor() {
    this.handlers = {};
  }

  on(event, handler) {
    (this.handlers[event] ||= []).push(handler);
    return this;
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
const CLOSE_ROOM_NOT_FOUND = 4404;
const MAX_RECONNECT_ATTEMPTS = 5;

class WebSocketRoomChannel extends BaseChannel {
  constructor(room) {
    super();
    this.room = room;
    this.isClosed = false;
    this.attempts = 0;
    this.queue = [];
    this.connect();
  }

  connect() {
    const token = localStorage.getItem(STORAGE_KEYS.accessToken) || '';
    const socket = new WebSocket(`${WS_BASE_URL}/rooms/${this.room.id}?token=${encodeURIComponent(token)}`);
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
      if (++this.attempts > MAX_RECONNECT_ATTEMPTS) {
        this.emit('error', { code: 'connection_lost', detail: 'Oda bağlantısı koptu. Odaya yeniden gir.' });
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
    this.socket.close();
    this.handlers = {};
  }
}

export function connectRoom(room, me) {
  return USE_MOCK ? new MockRoomChannel(room, me) : new WebSocketRoomChannel(room);
}
