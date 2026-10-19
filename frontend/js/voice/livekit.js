// LiveKit ses istemcisi (SFU). Backend'de VOICE_PROVIDER=livekit seçilince kullanılır.
// Sesi LiveKit sunucusuna bir kez gönderir, sunucu herkese dağıtır; kalabalık odalar için.
//
// Kimin konuşabileceğine LiveKit sunucusu karar verir: backend koltuklar değiştikçe
// kişinin yayın iznini açıp kapatır (bkz. backend app/voice/livekit.py). Biz yalnızca
// koltuktaysak ve mikrofonumuz açıksa mikrofonu yayınlamayı deneriz.
//
// DURUM: LiveKit sunucusuyla henüz denenmedi (bkz. GECMIS.md).
const LIVEKIT_CLIENT_URL = 'https://cdn.jsdelivr.net/npm/livekit-client@2.5.7/+esm';

export function createVoiceClient(options) {
  return new LiveKitVoiceClient(options);
}

class LiveKitVoiceClient {
  constructor({ info, me, onSpeaking, onError, refreshInfo }) {
    this.info = info;
    this.me = me;
    this.onSpeaking = onSpeaking;
    this.onError = onError;
    this.refreshInfo = refreshInfo;
    this.seats = [];
    this.closed = false;
    this.audioRoot = document.createElement('div');
    this.audioRoot.hidden = true;
    document.body.appendChild(this.audioRoot);
  }

  async start() {
    const lk = await import(LIVEKIT_CLIENT_URL);
    this.room = new lk.Room({ adaptiveStream: true, dynacast: true });
    this.room
      .on(lk.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === 'audio') this.audioRoot.appendChild(track.attach());
      })
      .on(lk.RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((el) => el.remove()))
      .on(lk.RoomEvent.ActiveSpeakersChanged, (speakers) => {
        this.onSpeaking(new Set(speakers.map((p) => Number(p.identity))));
      })
      // Tarayıcı sesi otomatik başlatmazsa ilk dokunuşta başlat
      .on(lk.RoomEvent.AudioPlaybackStatusChanged, () => {
        if (!this.room.canPlaybackAudio) {
          document.addEventListener('pointerdown', () => this.room.startAudio(), { once: true });
        }
      });
    await this.room.connect(this.info.url, this.info.token);
    this.applySeat();
  }

  update(seats) {
    this.seats = seats;
    if (this.room) this.applySeat();
  }

  async applySeat() {
    if (this.closed) return;
    const seat = this.seats.find((s) => s.user_id === this.me.id);
    const wantsToTalk = Boolean(seat && !seat.is_muted && !seat.is_mic_blocked);
    try {
      await this.room.localParticipant.setMicrophoneEnabled(wantsToTalk);
    } catch {
      // Token odaya girerken (koltukta değilken) alındıysa ve sunucunun izin güncellemesi
      // henüz ulaşmadıysa bir kez yeni token ile yeniden bağlanırız
      if (!wantsToTalk || this.retried) {
        this.onError('Mikrofon açılamadı.');
        return;
      }
      this.retried = true;
      this.info = await this.refreshInfo();
      await this.room.disconnect();
      await this.room.connect(this.info.url, this.info.token);
      await this.applySeat();
    }
    this.retried = false;
  }

  // Atılan/çıkan kişiyi LiveKit sunucusu kendisi düşürür
  removePeer() {}

  close() {
    this.closed = true;
    this.room?.disconnect();
    this.audioRoot.remove();
  }
}
