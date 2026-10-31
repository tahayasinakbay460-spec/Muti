// Ses istemcisinin hata yolları, sahte Agora ile. Gerçek Agora'ya bağlanılmaz.
// Çalıştırmak için (kök klasörde): node --test "frontend/tests/*.test.js"
import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import { setImmediate as nextTurn } from 'node:timers/promises';

class FakeTrack {
  constructor() {
    this.handlers = {};
    this.closed = false;
    this.muted = false;
    this.isPlaying = false;
  }
  on(event, handler) { this.handlers[event] = handler; }
  async setMuted(value) { this.muted = value; }
  getMediaStreamTrack() { return { readyState: 'live', muted: false }; }
  close() { this.closed = true; }
  play() { this.isPlaying = true; }
  stop() { this.isPlaying = false; }
}

class FakeClient {
  constructor() {
    this.handlers = {};
    this.connectionState = 'DISCONNECTED';
    this.remoteUsers = [];
    this.published = [];
    this.subscribed = [];
    this.roles = [];
    this.joinedTokens = [];
    this.renewed = [];
    this.left = false;
  }
  on(event, handler) { (this.handlers[event] ||= []).push(handler); }
  removeAllListeners() { this.handlers = {}; }
  emit(event, ...args) { (this.handlers[event] || []).forEach((handler) => handler(...args)); }
  async join(appId, channel, token) {
    consumeFailure('join');
    this.joinedTokens.push(token);
    this.connectionState = 'CONNECTED';
  }
  async leave() {
    this.left = true;
    this.connectionState = 'DISCONNECTED';
  }
  async setClientRole(role) { this.roles.push(role); }
  async publish(track) {
    consumeFailure('publish');
    this.published.push(track);
  }
  async unpublish(track) { this.published = this.published.filter((t) => t !== track); }
  async subscribe(user) {
    consumeFailure('subscribe');
    user.audioTrack = new FakeTrack();
    this.subscribed.push(user.uid);
  }
  async renewToken(token) {
    consumeFailure('renew');
    this.renewed.push(token);
  }
  getLocalAudioStats() { return { sendBytes: 1, sendBitrate: 1 }; }
}

let failures;       // işlem adı → kaç kez daha hata versin
let clients;        // oluşturulan Agora bağlantıları, sırayla
let tracks;         // açılan mikrofonlar
let micRequests;

function consumeFailure(name) {
  if (failures[name] > 0) {
    failures[name] -= 1;
    throw Object.assign(new Error(`${name} failed`), { code: 'TEST' });
  }
}

globalThis.window = {
  AudioContext: class {
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createAnalyser() { return { fftSize: 0, getFloatTimeDomainData() {} }; }
    close() { return Promise.resolve(); }
  },
  AgoraRTC: {
    setLogLevel() {},
    createClient() {
      const client = new FakeClient();
      clients.push(client);
      return client;
    },
    async createMicrophoneAudioTrack() {
      micRequests += 1;
      consumeFailure('mic');
      const track = new FakeTrack();
      tracks.push(track);
      return track;
    },
  },
};
globalThis.MediaStream = class {};
globalThis.document = { addEventListener() {} };

const { createVoiceClient } = await import('../js/voice/agora.js');

const ME = 7;
const seated = (extra = {}) => [{ user_id: ME, is_muted: false, is_mic_blocked: false, ...extra }];

function makeVoice(overrides = {}) {
  const log = { errors: [], lost: [], reports: [], refreshes: 0 };
  const voice = createVoiceClient({
    info: { app_id: 'app', channel: 'room-1', token: 'token-0', can_publish: true },
    me: { id: ME },
    onSpeaking() {},
    onError: (message) => log.errors.push(message),
    onConnectionLost: (isLost) => log.lost.push(isLost),
    refreshInfo: async () => {
      log.refreshes += 1;
      consumeFailure('refresh');
      return { app_id: 'app', channel: 'room-1', token: `token-${log.refreshes}`, can_publish: true };
    },
    retryDelays: [0, 0, 0],
    ...overrides,
  });
  voice.report = (event, detail = '') => log.reports.push([event, detail]);
  return { voice, log };
}

// Kuyruktaki ve zamanlayıcıdaki işler bitsin
async function settled(voice) {
  for (let i = 0; i < 12; i += 1) {
    await voice.queue;
    await new Promise((resolve) => setTimeout(resolve, 0));
    await nextTurn();
  }
}

async function started(seats = []) {
  const made = makeVoice();
  await made.voice.start();
  made.voice.update(seats);
  await settled(made.voice);
  return made;
}

const reported = (log, event) => log.reports.filter(([name]) => name === event);

beforeEach(() => {
  failures = {};
  clients = [];
  tracks = [];
  micRequests = 0;
});

test('yayın hatası tekrar denenir, başarıda mikrofon yayında kalır', async () => {
  failures.publish = 2;
  const { voice, log } = await started(seated());
  assert.deepEqual(clients[0].published, [tracks[0]]);
  assert.equal(voice.localTrack, tracks[0]);
  assert.deepEqual(log.errors, []);
  voice.close();
});

test('yayın kalıcı başarısızsa mikrofon bırakılır, sonraki koltuk güncellemesi yeniden dener', async () => {
  failures.publish = 4;
  const { voice, log } = await started(seated());
  assert.equal(voice.localTrack, null, 'yarım kalan mikrofon nesnesi kalmamalı');
  assert.equal(tracks[0].closed, true);
  assert.deepEqual(log.errors, ['Mikrofon açılamadı.']);

  voice.update(seated());
  await settled(voice);
  assert.deepEqual(clients[0].published, [tracks[1]]);
  voice.close();
});

test('koltuk değiştirmek mikrofonu yeniden açmaz ama kalkınca bırakılır', async () => {
  const { voice } = await started(seated());
  voice.update(seated({ index: 3 }));
  await settled(voice);
  assert.equal(tracks.length, 1);
  voice.update([]);
  await settled(voice);
  assert.equal(voice.localTrack, null);
  assert.deepEqual(clients[0].published, []);
  voice.close();
});

test('mikrofon izni reddedilince hata bir kez çıkar, her koltuk güncellemesinde tekrar sorulmaz', async () => {
  failures.mic = 1;
  const { voice, log } = await started(seated());
  voice.update(seated());
  voice.update(seated());
  await settled(voice);
  assert.equal(micRequests, 1);
  assert.equal(log.errors.length, 1);
  assert.equal(clients[0].roles.at(-1), 'audience');

  // Kalkıp yeniden oturunca hak yenilenir.
  voice.update([]);
  voice.update(seated());
  await settled(voice);
  assert.equal(micRequests, 2);
  assert.deepEqual(clients[0].published, [tracks[0]]);
  voice.close();
});

test('abonelik hatası tekrar denenir ve konuşmacı çalınır', async () => {
  failures.subscribe = 2;
  const { voice, log } = await started([{ user_id: 2, is_muted: false, is_mic_blocked: false }]);
  const speaker = { uid: 2, hasAudio: true };
  clients[0].emit('user-published', speaker, 'audio');
  await settled(voice);
  assert.deepEqual(clients[0].subscribed, [2]);
  assert.equal(speaker.audioTrack.isPlaying, true);
  assert.deepEqual(log.lost, []);
  voice.close();
});

test('abonelik kalıcı başarısızsa yeniden bağlan tuşu çıkar, tuş herkese yeniden abone eder', async () => {
  failures.subscribe = 4;
  const { voice, log } = await started();
  const speaker = { uid: 2, hasAudio: true };
  clients[0].emit('user-published', speaker, 'audio');
  await settled(voice);
  assert.equal(reported(log, 'subscribe_failed').length, 1);
  assert.deepEqual(log.lost, [true]);

  await voice.reconnect();
  clients[1].emit('user-published', speaker, 'audio');   // Agora yeni girene yayınları yeniden bildirir
  await settled(voice);
  assert.deepEqual(clients[1].subscribed, [2]);
  voice.close();
});

test('konuşmacı yayını kapattıysa abonelik denemesi hata göstermeden biter', async () => {
  failures.subscribe = 4;
  const { voice, log } = await started();
  const speaker = { uid: 2, hasAudio: false };
  clients[0].emit('user-published', speaker, 'audio');
  await settled(voice);
  assert.deepEqual(log.lost, []);
  voice.close();
});

test('bağlantı tamamen düşünce yeni token ile girilir ve koltuktaki kişinin mikrofonu yeniden açılır', async () => {
  const { voice, log } = await started(seated());
  clients[0].connectionState = 'DISCONNECTED';
  clients[0].emit('connection-state-change', 'DISCONNECTED', 'RECONNECTING', 'NETWORK_ERROR');
  await settled(voice);
  assert.equal(clients.length, 2);
  assert.equal(clients[0].left, true);
  assert.deepEqual(clients[1].joinedTokens, ['token-1']);
  assert.deepEqual(clients[1].published, [tracks[1]]);
  assert.equal(tracks[0].closed, true);
  assert.equal(reported(log, 'voice_reconnected').length, 1);
  assert.deepEqual(log.lost, [false]);
  voice.close();
});

test('yeniden bağlanma art arda tetiklense de tek bağlantı kurulur', async () => {
  const { voice } = await started();
  clients[0].connectionState = 'DISCONNECTED';
  clients[0].emit('connection-state-change', 'DISCONNECTED', 'CONNECTED', 'NETWORK_ERROR');
  clients[0].emit?.('token-privilege-did-expire');
  voice.reconnect();
  await settled(voice);
  assert.equal(clients.length, 2);
  voice.close();
});

test('geçici hatada tekrar dener, denemeler bitince tuş çıkar, tuş bağlantıyı geri getirir', async () => {
  const first = await started();
  failures.join = 2;
  clients[0].emit('connection-state-change', 'DISCONNECTED', 'CONNECTED', 'SERVER_ERROR');
  await settled(first.voice);
  assert.equal(clients.at(-1).connectionState, 'CONNECTED');
  assert.equal(first.voice.joined, true);
  first.voice.close();

  const second = await started(seated());
  failures.refresh = 4;
  const before = clients.length;
  clients.at(-1).emit('connection-state-change', 'DISCONNECTED', 'CONNECTED', 'NETWORK_ERROR');
  await settled(second.voice);
  assert.equal(clients.length, before, 'token alınamadı, bağlantı kurulmadı');
  assert.deepEqual(second.log.lost, [false, true]);
  assert.equal(reported(second.log, 'reconnect_failed').length, 1);

  await second.voice.reconnect();
  await settled(second.voice);
  assert.equal(clients.at(-1).connectionState, 'CONNECTED');
  assert.deepEqual(clients.at(-1).published, [tracks.at(-1)]);
  assert.deepEqual(second.log.lost, [false, true, false]);
  second.voice.close();
});

test('Agora kişiyi çıkardıysa otomatik deneme yapılmaz, mikrofon kapanır, tuş çıkar', async () => {
  const { voice, log } = await started(seated());
  clients[0].connectionState = 'DISCONNECTED';
  clients[0].emit('connection-state-change', 'DISCONNECTED', 'CONNECTED', 'UID_BANNED');
  await settled(voice);
  assert.equal(clients.length, 1);
  assert.equal(voice.localTrack, null);
  assert.equal(tracks[0].closed, true);
  assert.deepEqual(log.lost, [true]);
  assert.equal(reported(log, 'voice_banned').length, 1);

  // Sonradan gelen koltuk yayını kopuk bağlantıda mikrofon açmaya çalışmaz.
  voice.update(seated());
  await settled(voice);
  assert.equal(micRequests, 1);
  voice.close();
});

test('kendi çıkışımız yeniden bağlanma başlatmaz', async () => {
  const { voice, log } = await started();
  clients[0].emit('connection-state-change', 'DISCONNECTED', 'DISCONNECTING', 'LEAVE');
  await settled(voice);
  assert.equal(clients.length, 1);
  assert.deepEqual(log.lost, []);
  voice.close();
});

test('token süresi dolmadan yenilenir, ilk deneme hata verse de', async () => {
  failures.renew = 1;
  const { voice, log } = await started();
  clients[0].emit('token-privilege-will-expire');
  await settled(voice);
  assert.deepEqual(clients[0].renewed, ['token-2']);
  assert.equal(clients.length, 1);
  assert.deepEqual(reported(log, 'token_renew_failed'), []);
  voice.close();
});

test('token yenilemesi tamamen başarısızsa kaydedilir', async () => {
  failures.renew = 4;
  const { voice, log } = await started();
  clients[0].emit('token-privilege-will-expire');
  await settled(voice);
  assert.equal(reported(log, 'token_renew_failed').length, 1);
  voice.close();
});

test('süresi dolan token sonrası kanala yeniden girilir', async () => {
  const { voice, log } = await started(seated());
  clients[0].emit('token-privilege-did-expire');
  await settled(voice);
  assert.equal(clients.length, 2);
  assert.deepEqual(clients[1].joinedTokens, ['token-1']);
  assert.deepEqual(clients[1].published, [tracks[1]]);
  assert.equal(reported(log, 'token_expired').length, 1);
  voice.close();
});

test('mikrofon koparsa yeniden açılır, kısa sürede ikinci kez koparsa bırakılır', async () => {
  const { voice, log } = await started(seated());
  tracks[0].handlers['track-ended']();
  await settled(voice);
  assert.equal(tracks.length, 2);
  assert.deepEqual(clients[0].published, [tracks[1]]);
  assert.equal(log.errors.length, 1);

  tracks[1].handlers['track-ended']();
  await settled(voice);
  assert.equal(tracks.length, 2, 'bozuk cihazda döngüye girilmez');
  assert.equal(voice.localTrack, null);
  assert.equal(log.errors.length, 2);
  voice.close();
});

test('kütüphane kendisi toparlarsa kaçırılan abonelik ve koltuk işleri tamamlanır', async () => {
  const { voice } = await started();
  clients[0].connectionState = 'RECONNECTING';
  voice.update(seated());
  await settled(voice);
  assert.equal(micRequests, 0, 'bağlantı yokken mikrofon açılmaz');

  clients[0].remoteUsers = [{ uid: 2, hasAudio: true }];
  clients[0].connectionState = 'CONNECTED';
  clients[0].emit('connection-state-change', 'CONNECTED', 'RECONNECTING', '');
  await settled(voice);
  assert.deepEqual(clients[0].subscribed, [2]);
  assert.deepEqual(clients[0].published, [tracks[0]]);
  assert.equal(clients.length, 1);
  voice.close();
});

test('eski bağlantıdan gelen geç olay yeni bağlantıyı etkilemez', async () => {
  const { voice } = await started();
  const old = clients[0];
  const lateHandlers = { ...old.handlers };
  await voice.reconnect();
  await settled(voice);
  lateHandlers['connection-state-change'].forEach((handler) => handler('DISCONNECTED', 'CONNECTED', 'NETWORK_ERROR'));
  await settled(voice);
  assert.equal(clients.length, 2);
  voice.close();
});

test('ilk bağlantı hatası çağırana iletilir ve yarım bağlantı kalmaz', async () => {
  failures.join = 1;
  const { voice } = makeVoice();
  await assert.rejects(voice.start());
  assert.equal(voice.client, null);
  voice.close();
});

test('bağlanırken odadan çıkılırsa kanaldan hemen ayrılınır', async () => {
  const { voice } = makeVoice();
  const starting = voice.start();
  await nextTurn();
  voice.close();
  await starting;
  await settled(voice);
  assert.equal(clients[0].left, true);
});

test('odadan çıkınca mikrofon kapanır, kanal bırakılır, yeniden bağlanma başlamaz', async () => {
  const { voice } = await started(seated());
  const client = clients[0];
  voice.close();
  await settled(voice);
  assert.equal(tracks[0].closed, true);
  assert.equal(client.left, true);
  await voice.reconnect();
  assert.equal(clients.length, 1);
});
