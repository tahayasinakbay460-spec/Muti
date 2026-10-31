// Agora ses istemcisi (bulut SFU). Backend'de VOICE_PROVIDER=agora seçilince kullanılır.
// Konuşmacı sesini bir kez Agora'ya gönderir, Agora odadaki herkese dağıtır.
//
// ROLLER: Agora'nın "live" kipinde iki rol var: host (konuşur) ve audience (yalnızca dinler).
// Koltuğa oturunca sunucudan konuşma izinli yeni token alıp (renewToken) host oluruz,
// kalkınca audience'a döneriz. Bağlantı kopmaz, yeniden kurulmaz.
//
// KURAL UYGULAMASI: Koltuktan inen kişinin elindeki token süresi dolana kadar geçerli kalır
// (bkz. backend app/voice/agora.py). Bu yüzden mesh'teki gibi herkes, koltukta olmayan ya da
// mikrofonu kapalı/engelli görünen birinin sesini kendi tarafında çalmaz (applyRemoteMute).
//
// YENİDEN BAĞLANMA: Kısa ağ kesintilerini Agora'nın kütüphanesi kendisi toparlar (RECONNECTING).
// Bağlantı tamamen düşerse ya da token süresi dolarsa tek bir yol çalışır (reconnect): eski
// bağlantıyı temizle, yeni token al, kanala gir, koltuktaysan mikrofonu aç. O da olmazsa ekrana
// "Yeniden bağlan" tuşu çıkar (onConnectionLost). Kullanıcı odadan çıkıp girmek zorunda kalmaz.
import { SpeakingDetector } from './speaking.js';
import { RETRY_DELAYS_MS, retried } from './retry.js';

// Agora'nın resmî tarayıcı kütüphanesi; yüklenince window.AgoraRTC olarak gelir.
const AGORA_SDK_URL = 'https://cdn.jsdelivr.net/npm/agora-rtc-sdk-ng@4.24.8/AgoraRTC_N-production.js';
let sdkLoading = null;
const SEAT_SYNC_GRACE_MS = 3000;
const MIC_FLOW_CHECK_MS = 3000;
// Mikrofon bu kadar süre içinde ikinci kez koparsa cihaz sorunludur: sürekli yeniden açmayız
const MIC_RESTART_WINDOW_MS = 10000;
// Bu sebeplerle düşen kişiyi Agora bilerek çıkarmıştır; otomatik denemek iki cihazı birbirine atar
const BANNED_REASONS = new Set(['UID_BANNED', 'IP_BANNED', 'CHANNEL_BANNED']);

function loadSdk() {
  sdkLoading ||= new Promise((resolve, reject) => {
    if (window.AgoraRTC) return resolve(window.AgoraRTC);
    const script = document.createElement('script');
    script.src = AGORA_SDK_URL;
    script.onload = () => resolve(window.AgoraRTC);
    script.onerror = () => {
      sdkLoading = null;   // bir sonraki odaya girişte yeniden denensin
      reject(new Error('Agora SDK yüklenemedi'));
    };
    document.head.appendChild(script);
  });
  return sdkLoading;
}

export function createVoiceClient(options) {
  return new AgoraVoiceClient(options);
}

class AgoraVoiceClient {
  constructor({ info, me, onSpeaking, onError, onConnectionLost = () => {}, refreshInfo, retryDelays = RETRY_DELAYS_MS }) {
    this.info = info;
    this.me = me;
    this.onError = onError;
    this.onConnectionLost = onConnectionLost;
    this.refreshInfo = refreshInfo;
    this.retryDelays = retryDelays;
    this.canPublish = info.can_publish;
    this.seats = [];
    this.remote = new Map();      // kullanıcı id → Agora'daki uzak kullanıcı (sesine abone olduk)
    this.localTrack = null;       // mikrofonumuzu temsil eden Agora nesnesi; doluysa "yayındayız" demektir
    this.queue = Promise.resolve();
    this.closed = false;
    this.joined = false;          // kanala girdik mi
    this.reconnecting = false;
    this.micGaveUp = false;       // mikrofon açılamadı (izin yok): koltuktan kalkana kadar yeniden deneme
    this.micWarned = false;       // aynı hata her koltuk değişikliğinde ekrana çıkmasın
    this.lastMicEndAt = 0;
    this.detector = new SpeakingDetector(onSpeaking);
  }

  async start() {
    const AgoraRTC = await loadSdk();
    AgoraRTC.setLogLevel(3);   // yalnızca uyarı ve hatalar konsola yazılsın
    this.AgoraRTC = AgoraRTC;
    // Tarayıcı sesi kullanıcı sayfaya dokunmadan çalmazsa ilk dokunuşta yeniden dene
    AgoraRTC.onAutoplayFailed = () => {
      this.report('autoplay_blocked');
      document.addEventListener('pointerdown', () => {
        this.remote.forEach((_, userId) => this.applyRemoteMute(userId, true));
        this.detector.resume();
      }, { once: true });
    };
    await this.connect();
  }

  // Yeni bir Agora bağlantısı kurar. Her bağlantı kendi nesnesidir: yeniden bağlanınca eskisinden
  // gelen geç olaylar (`client !== this.client`) yeni bağlantıyı bozmasın diye yok sayılır.
  async connect() {
    const client = this.AgoraRTC.createClient({ mode: 'live', codec: 'vp8' });
    this.client = client;
    this.listen(client);
    try {
      await client.join(this.info.app_id, this.info.channel, this.info.token, this.me.id);
    } catch (error) {
      client.removeAllListeners();
      if (this.client === client) this.client = null;
      throw error;
    }
    // Bağlanırken odadan çıkıldıysa
    if (this.client !== client) {
      client.removeAllListeners();
      await client.leave().catch(() => {});
      return;
    }
    this.joined = true;
    this.enqueueSeat();
  }

  listen(client) {
    const live = (handler) => (...args) => {
      if (client === this.client && !this.closed) return handler(...args);
      return undefined;
    };
    client.on('user-published', live((user, mediaType) => {
      if (mediaType === 'audio') this.subscribeTo(client, user);
    }));
    client.on('connection-state-change', live((current, previous, reason) => {
      this.report('connection_changed', `${previous}->${current} ${reason || ''}`);
      if (current === 'DISCONNECTED') this.onDisconnected(reason);
      // Kütüphane kendisi toparladı: bu arada kaçırılan koltuk ve abonelik işlerini tamamla
      if (current === 'CONNECTED' && previous === 'RECONNECTING') {
        this.subscribeToMissing(client);
        this.enqueueSeat();
      }
    }));
    const forget = live((user) => {
      this.remote.delete(user.uid);
      this.detector.remove(user.uid);
    });
    client.on('user-unpublished', forget);
    client.on('user-left', forget);
    // Token süresi dolmadan sunucudan yenisini al (bağlantı kopmadan)
    client.on('token-privilege-will-expire', live(() => {
      retried(() => this.renewToken(), { delays: this.retryDelays, shouldStop: () => client !== this.client })
        .catch((error) => this.report('token_renew_failed', `${error.code || ''} ${error.message}`));
    }));
    // Süresi dolan token artık yenilenemez, kişi kanaldan düşer: yeni token ile yeniden gir
    client.on('token-privilege-did-expire', live(() => {
      this.report('token_expired');
      this.reconnect();
    }));
  }

  onDisconnected(reason) {
    // join sırasındaki düşüşü start/reconnect'teki deneme döngüsü zaten ele alıyor
    if (reason === 'LEAVE' || !this.joined) return;
    if (BANNED_REASONS.has(reason)) {
      // Aynı hesap başka cihazdan girdiyse oda kanalı da kapanır ve kişi doğru mesajı görür
      this.report('voice_banned', reason);
      this.enqueue(() => this.dropConnection());
      this.onError('Ses bağlantın kapatıldı.');
      this.onConnectionLost(true);
      return;
    }
    this.reconnect();
  }

  // Tek yeniden bağlanma yolu. Hem otomatik hem "Yeniden bağlan" tuşu buraya gelir.
  // Kuyruğa girer ki yarım kalmış bir mikrofon işiyle aynı anda çalışmasın.
  reconnect() {
    if (this.closed || this.reconnecting) return this.queue;
    this.reconnecting = true;
    this.onConnectionLost(false);
    return this.enqueue(async () => {
      try {
        await this.dropConnection();
        this.micGaveUp = false;
        this.micWarned = false;
        await retried(async () => {
          this.info = await this.refreshInfo();
          this.canPublish = this.info.can_publish;
          await this.connect();
        }, { delays: this.retryDelays, shouldStop: () => this.closed });
        if (!this.closed) this.report('voice_reconnected');
      } catch (error) {
        if (this.closed) return;
        this.report('reconnect_failed', `${error.code || ''} ${error.message}`);
        this.onConnectionLost(true);
      } finally {
        // Sıradaki koltuk işi bu görev bitince çalışır, bayrağı görmez
        this.reconnecting = false;
      }
    });
  }

  // Eski bağlantıdan iz kalmasın: abonelikler, mikrofon ve kanal
  async dropConnection() {
    const client = this.client;
    this.client = null;
    this.joined = false;
    this.remote.forEach((_, userId) => this.detector.remove(userId));
    this.remote.clear();
    await this.releaseMic(client);
    if (client) {
      client.removeAllListeners();
      await client.leave().catch(() => {});
    }
  }

  async renewToken() {
    const client = this.client;
    this.info = await this.refreshInfo();
    this.canPublish = this.info.can_publish;
    await client.renewToken(this.info.token);
  }

  // Abonelik = "bu konuşmacının sesini bana da gönder". Agora bunu bize konuşmacı yayına başlayınca
  // bir kez söyler; hata olunca biz yeniden denemezsek o kişi bir daha duyulmaz.
  async subscribeTo(client, user) {
    const gone = () => this.closed || client !== this.client || !user.hasAudio;
    try {
      await retried(() => client.subscribe(user, 'audio'), { delays: this.retryDelays, shouldStop: gone });
    } catch (error) {
      if (gone()) return;
      this.report('subscribe_failed', `uid=${user.uid} ${error.code || ''} ${error.message}`);
      this.onConnectionLost(true);   // tuş yeni bağlantı kurar, bütün konuşmacılara yeniden abone olur
      return;
    }
    if (gone()) return;
    this.remote.set(user.uid, user);
    this.detector.add(user.uid, new MediaStream([user.audioTrack.getMediaStreamTrack()]));
    this.applyRemoteMute(user.uid);
    // Koltuk haberi sesten biraz geç gelebilir; bu süreden sonra hâlâ yoksa koltuk listemiz eski
    setTimeout(() => {
      if (!this.closed && this.remote.has(user.uid) && !this.seatOf(user.uid)) {
        this.report('speaker_not_seated', `uid=${user.uid}`);
      }
    }, SEAT_SYNC_GRACE_MS);
  }

  subscribeToMissing(client) {
    client.remoteUsers
      .filter((user) => user.hasAudio && !this.remote.has(user.uid))
      .forEach((user) => this.subscribeTo(client, user));
  }

  seatOf(userId) {
    return this.seats.find((s) => s.user_id === userId);
  }

  update(seats) {
    if (this.closed) return;
    this.seats = seats;
    // Koltuktan kalkan kişi yeniden oturunca mikrofon baştan denenir
    if (!this.seatOf(this.me.id)) {
      this.micGaveUp = false;
      this.micWarned = false;
    }
    this.remote.forEach((_, userId) => this.applyRemoteMute(userId));
    if (this.client) this.enqueueSeat();
  }

  // Bağlantı ve mikrofon işleri sırayla yapılsın
  enqueue(task) {
    this.queue = this.queue.then(task).catch((error) => console.warn('[voice] task failed', error));
    return this.queue;
  }

  // Koltuk değişiklikleri art arda gelebilir
  enqueueSeat() {
    this.queue = this.queue.then(() => this.applySeat()).catch((error) => {
      console.warn('[voice] seat change failed', error);
      this.report('mic_failed', `seat_change ${error.code || ''} ${error.message}`);
      this.warnMic('Mikrofon açılamadı.');
    });
  }

  warnMic(message) {
    if (this.micWarned) return;
    this.micWarned = true;
    this.onError(message);
  }

  async applySeat() {
    const client = this.client;
    // Bağlı değilken yapılan işlem hata verir. Bağlantı dönünce bu kontrol yeniden çalışır.
    if (this.closed || this.reconnecting || !this.joined || client?.connectionState !== 'CONNECTED') return;
    const seat = this.seatOf(this.me.id);
    const wantsMic = Boolean(seat && !seat.is_mic_blocked);

    if (wantsMic && !this.localTrack && !this.micGaveUp) {
      // Odaya dinleyici olarak girdiysek token'da konuşma izni yok: yenisini iste
      if (!this.canPublish) await retried(() => this.renewToken(), { delays: this.retryDelays, shouldStop: () => client !== this.client });
      if (!this.canPublish) {
        this.report('mic_denied_by_server');
        return;
      }
      await retried(() => client.setClientRole('host'), { delays: this.retryDelays, shouldStop: () => client !== this.client });
      let track;
      try {
        track = await this.AgoraRTC.createMicrophoneAudioTrack({ AEC: true, ANS: true, AGC: true });
      } catch (error) {
        this.report('mic_failed', `create_track ${error.code || ''} ${error.message}`);
        await client.setClientRole('audience').catch(() => {});
        this.micGaveUp = true;
        this.warnMic('Mikrofona izin verilmedi. Konuşmak için tarayıcı ayarlarından izin ver.');
        return;
      }
      this.localTrack = track;
      track.on('track-ended', () => this.onMicEnded(track));
      // İzin penceresi açıkken koltuktan kalkmış, odadan çıkmış ya da bağlantı değişmiş olabilir
      const abandoned = () => this.closed || client !== this.client || !this.seatOf(this.me.id);
      if (abandoned()) return this.releaseMic(client);
      try {
        await retried(() => client.publish(track), { delays: this.retryDelays, shouldStop: abandoned });
      } catch (error) {
        // Mikrofon nesnesi kalırsa sonraki kontrol "zaten yayındayız" sanır ve kişi kalkıp
        // oturana kadar sesi gitmez. Bırakıyoruz ki bir sonraki koltuk değişikliği yeniden denesin.
        await this.releaseMic(client);
        if (abandoned()) return;
        this.report('mic_failed', `publish ${error.code || ''} ${error.message}`);
        this.warnMic('Mikrofon açılamadı.');
        return;
      }
      this.micWarned = false;
      this.report('mic_published');
      this.reportMicFlow();
      this.detector.add(this.me.id, new MediaStream([track.getMediaStreamTrack()]));
    } else if (!wantsMic && this.localTrack) {
      await this.releaseMic(client);
    }
    // Mikrofonu kapatmak = sesi göndermeyi durdurmak (yayın ve bağlantı açık kalır)
    if (this.localTrack) await this.localTrack.setMuted(Boolean(seat.is_muted));
  }

  // Mikrofon kaynağı gitti (kulaklık çıktı, tarayıcı izni kaldırıldı). Bir kez yeniden açmayı deneriz.
  onMicEnded(track) {
    if (this.closed || track !== this.localTrack) return;
    this.report('mic_track_ended');
    const now = Date.now();
    const endedAgain = now - this.lastMicEndAt < MIC_RESTART_WINDOW_MS;
    this.lastMicEndAt = now;
    this.enqueue(() => this.releaseMic(this.client));
    if (endedAgain) {
      this.micGaveUp = true;
      this.warnMic('Mikrofon bağlantısı kesildi. Koltuktan kalkıp yeniden oturarak deneyebilirsin.');
      return;
    }
    this.onError('Mikrofon bağlantısı kesildi, yeniden açılıyor.');
    this.enqueueSeat();
  }

  // Yalnızca kayıt: mikrofon gerçekten Agora'ya ses gönderiyor mu? Kapalı mikrofon ölçülmez.
  reportMicFlow() {
    setTimeout(() => {
      const track = this.localTrack;
      if (this.closed || !track || track.muted || !this.client) return;
      const { sendBytes, sendBitrate } = this.client.getLocalAudioStats();
      const { readyState, muted } = track.getMediaStreamTrack();
      this.report(sendBytes > 0 ? 'mic_flowing' : 'mic_silent',
        `bytes=${sendBytes} bitrate=${sendBitrate} state=${readyState} track_muted=${muted}`);
    }, MIC_FLOW_CHECK_MS);
  }

  async releaseMic(client) {
    const track = this.localTrack;
    this.localTrack = null;
    this.detector.remove(this.me.id);
    if (!track) return;
    if (client?.connectionState === 'CONNECTED') {
      await client.unpublish(track).catch(() => {});
      await client.setClientRole('audience').catch(() => {});
    }
    track.close();
  }

  applyRemoteMute(userId, retry = false) {
    const track = this.remote.get(userId)?.audioTrack;
    if (!track) return;
    const seat = this.seatOf(userId);
    const allowed = Boolean(seat && !seat.is_muted && !seat.is_mic_blocked);
    if (allowed && (retry || !track.isPlaying)) track.play();
    if (!allowed && track.isPlaying) track.stop();
  }

  // Atılan/çıkan kişinin sesi zaten çalınmaz (koltukta değil); Agora bağlantıyı kendisi düşürür
  removePeer() {}

  close() {
    this.closed = true;
    const client = this.client;
    this.client = null;
    this.joined = false;
    this.releaseMic(client).finally(() => client?.leave().catch(() => {}));
    this.detector.close();
  }
}
