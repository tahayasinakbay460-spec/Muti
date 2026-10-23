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
import { SpeakingDetector } from './speaking.js';

// Agora'nın resmî tarayıcı kütüphanesi; yüklenince window.AgoraRTC olarak gelir.
const AGORA_SDK_URL = 'https://cdn.jsdelivr.net/npm/agora-rtc-sdk-ng@4.24.8/AgoraRTC_N-production.js';
let sdkLoading = null;

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
  constructor({ info, me, onSpeaking, onError, refreshInfo }) {
    this.info = info;
    this.me = me;
    this.onError = onError;
    this.refreshInfo = refreshInfo;
    this.canPublish = info.can_publish;
    this.seats = [];
    this.remote = new Map();      // kullanıcı id → Agora'daki uzak kullanıcı (sesine abone olduk)
    this.localTrack = null;
    this.queue = Promise.resolve();
    this.closed = false;
    this.detector = new SpeakingDetector(onSpeaking);
  }

  async start() {
    const AgoraRTC = await loadSdk();
    AgoraRTC.setLogLevel(3);   // yalnızca uyarı ve hatalar konsola yazılsın
    this.AgoraRTC = AgoraRTC;
    // Tarayıcı sesi kullanıcı sayfaya dokunmadan çalmazsa ilk dokunuşta yeniden dene
    AgoraRTC.onAutoplayFailed = () => {
      document.addEventListener('pointerdown', () => {
        this.remote.forEach((_, userId) => this.applyRemoteMute(userId, true));
        this.detector.resume();
      }, { once: true });
    };

    this.client = AgoraRTC.createClient({ mode: 'live', codec: 'vp8' });
    this.client.on('user-published', async (user, mediaType) => {
      if (mediaType !== 'audio' || this.closed) return;
      await this.client.subscribe(user, 'audio');
      this.remote.set(user.uid, user);
      this.detector.add(user.uid, new MediaStream([user.audioTrack.getMediaStreamTrack()]));
      this.applyRemoteMute(user.uid);
    });
    const forget = (user) => {
      this.remote.delete(user.uid);
      this.detector.remove(user.uid);
    };
    this.client.on('user-unpublished', forget);
    this.client.on('user-left', forget);
    // Token süresi dolmadan sunucudan yenisini al (bağlantı kopmadan)
    const renew = () => this.renewToken().catch((error) => console.warn('[voice] token renew failed', error));
    this.client.on('token-privilege-will-expire', renew);
    this.client.on('token-privilege-did-expire', renew);

    await this.client.join(this.info.app_id, this.info.channel, this.info.token, this.me.id);
    this.enqueueSeat();
  }

  async renewToken() {
    this.info = await this.refreshInfo();
    this.canPublish = this.info.can_publish;
    await this.client.renewToken(this.info.token);
  }

  seatOf(userId) {
    return this.seats.find((s) => s.user_id === userId);
  }

  update(seats) {
    if (this.closed) return;
    this.seats = seats;
    this.remote.forEach((_, userId) => this.applyRemoteMute(userId));
    if (this.client) this.enqueueSeat();
  }

  // Koltuk değişiklikleri art arda gelebilir; mikrofon işlemleri sırayla yapılsın
  enqueueSeat() {
    this.queue = this.queue.then(() => this.applySeat()).catch((error) => {
      console.warn('[voice] seat change failed', error);
      this.onError('Mikrofon açılamadı.');
    });
  }

  async applySeat() {
    if (this.closed) return;
    const seat = this.seatOf(this.me.id);
    const wantsMic = Boolean(seat && !seat.is_mic_blocked);

    if (wantsMic && !this.localTrack) {
      // Odaya dinleyici olarak girdiysek token'da konuşma izni yok: yenisini iste
      if (!this.canPublish) await this.renewToken();
      if (!this.canPublish) return;
      await this.client.setClientRole('host');
      try {
        this.localTrack = await this.AgoraRTC.createMicrophoneAudioTrack({ AEC: true, ANS: true, AGC: true });
      } catch {
        await this.client.setClientRole('audience');
        this.onError('Mikrofona izin verilmedi. Konuşmak için tarayıcı ayarlarından izin ver.');
        return;
      }
      // İzin penceresi açıkken koltuktan kalkmış ya da odadan çıkmış olabiliriz
      if (this.closed || !this.seatOf(this.me.id)) return this.releaseMic();
      await this.client.publish(this.localTrack);
      this.detector.add(this.me.id, new MediaStream([this.localTrack.getMediaStreamTrack()]));
    } else if (!wantsMic && this.localTrack) {
      await this.releaseMic();
    }
    // Mikrofonu kapatmak = sesi göndermeyi durdurmak (yayın ve bağlantı açık kalır)
    if (this.localTrack) await this.localTrack.setMuted(Boolean(seat.is_muted));
  }

  async releaseMic() {
    const track = this.localTrack;
    this.localTrack = null;
    this.detector.remove(this.me.id);
    if (!track) return;
    if (this.client.connectionState === 'CONNECTED') {
      await this.client.unpublish(track).catch(() => {});
      await this.client.setClientRole('audience').catch(() => {});
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
    this.releaseMic().finally(() => this.client?.leave().catch(() => {}));
    this.detector.close();
  }
}
