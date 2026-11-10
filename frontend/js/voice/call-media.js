// Birebir aramanın ses/görüntü bağlantısı (özel mesajlardaki 📞 ve 🎥).
// Odadaki ses istemcilerinden ayrıdır: koltuk yok, iki kişi var, ikisi de konuşur, görüntülüde kamera da açılır.
// Sağlayıcıyı sunucu söyler (backend .env VOICE_PROVIDER), oda sesiyle aynıdır:
//   agora → iki taraf da Agora'daki "call-<id>" kanalına girer
//   mesh  → iki tarayıcı doğrudan bağlanır; bağlantı mesajları kişiye özel kanaldan (`call:signal`) taşınır
//
// Ekran şunları verir: info (sunucudan bağlantı bilgisi), isCaller, video (kamera açılsın mı),
// localEl/remoteEl (görüntülerin çizileceği kutular), sendSignal/onSignal (yalnızca mesh), refreshInfo,
// onRemoteVideo(var mı), onError(mesaj).
import { loadSdk } from './agora.js';

export async function connectCallMedia(options) {
  const media = options.info.provider === 'agora' ? new AgoraCallMedia(options) : new MeshCallMedia(options);
  try {
    await media.start();
  } catch (error) {
    media.close();
    throw error;
  }
  return media;
}

// Mikrofon/kamera izni reddedilince anlaşılır bir mesaj
function mediaErrorText(error) {
  if (error?.name === 'NotAllowedError' || error?.code === 'PERMISSION_DENIED') {
    return 'Mikrofon/kamera izni verilmedi. Tarayıcı ayarlarından izin ver.';
  }
  if (error?.name === 'NotFoundError' || error?.code === 'DEVICE_NOT_FOUND') return 'Mikrofon ya da kamera bulunamadı.';
  return 'Bağlantı kurulamadı.';
}

class AgoraCallMedia {
  constructor({ info, me, video, localEl, remoteEl, refreshInfo, onRemoteVideo = () => {}, onError = () => {} }) {
    Object.assign(this, { info, me, video, localEl, remoteEl, refreshInfo, onRemoteVideo, onError });
    this.tracks = [];
    this.closed = false;
  }

  async start() {
    const AgoraRTC = await loadSdk();
    AgoraRTC.setLogLevel(3);
    // "rtc" kipi: iki kişilik görüşme, iki taraf da yayıncı (odadaki "live" kipinin aksine)
    this.client = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });
    this.client.on('user-published', async (user, mediaType) => {
      await this.client.subscribe(user, mediaType);
      if (mediaType === 'audio') user.audioTrack.play();
      if (mediaType === 'video') {
        user.videoTrack.play(this.remoteEl, { fit: 'cover' });
        this.onRemoteVideo(true);
      }
    });
    this.client.on('user-unpublished', (_user, mediaType) => {
      if (mediaType === 'video') this.onRemoteVideo(false);
    });
    // Token bir saat geçerli; uzun görüşmede bitmeden yenilenir
    this.client.on('token-privilege-will-expire', async () => {
      try {
        const fresh = await this.refreshInfo();
        await this.client.renewToken(fresh.token);
      } catch { /* token yenilenemezse süre dolunca bağlantı kapanır, ekran kapanış mesajını gösterir */ }
    });
    await this.client.join(this.info.app_id, this.info.channel, this.info.token, this.me.id);
    try {
      this.mic = await AgoraRTC.createMicrophoneAudioTrack({ AEC: true, ANS: true });
      this.tracks.push(this.mic);
      if (this.video) {
        this.camera = await AgoraRTC.createCameraVideoTrack({ encoderConfig: '480p_1' });
        this.tracks.push(this.camera);
        this.camera.play(this.localEl, { mirror: true, fit: 'cover' });
      }
    } catch (error) {
      throw Object.assign(new Error(mediaErrorText(error)), { code: 'media_denied' });
    }
    if (this.closed) return;
    await this.client.publish(this.tracks);
  }

  async setMicEnabled(enabled) { await this.mic?.setEnabled(enabled); }

  async setCameraEnabled(enabled) { await this.camera?.setEnabled(enabled); }

  close() {
    this.closed = true;
    this.tracks.forEach((track) => track.close());
    this.tracks = [];
    this.client?.leave().catch(() => {});
  }
}

class MeshCallMedia {
  constructor({ info, isCaller, video, localEl, remoteEl, sendSignal, onSignal, onRemoteVideo = () => {}, onError = () => {} }) {
    Object.assign(this, { info, isCaller, video, localEl, remoteEl, sendSignal, onRemoteVideo, onError });
    // Karşı tarafın teklifi, biz mikrofon iznini beklerken gelebilir: bağlantı hazır olana kadar biriktir
    this.early = [];
    this.unsubscribe = onSignal((signal) => (this.pc ? this.handleSignal(signal) : this.early.push(signal)));
    this.pendingCandidates = [];
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: this.video ? { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } : false,
      });
    } catch (error) {
      throw Object.assign(new Error(mediaErrorText(error)), { code: 'media_denied' });
    }
    if (this.video) {
      const local = document.createElement('video');
      Object.assign(local, { muted: true, autoplay: true, playsInline: true, srcObject: this.stream });
      this.localEl.replaceChildren(local);
    }
    const pc = new RTCPeerConnection({ iceServers: this.info.ice_servers });
    this.pc = pc;
    this.stream.getTracks().forEach((track) => pc.addTrack(track, this.stream));
    pc.onicecandidate = ({ candidate }) => {
      if (candidate) this.sendSignal({ candidate: candidate.toJSON() });
    };
    pc.ontrack = ({ streams: [remote], track }) => {
      // Ses de görüntü de aynı <video> öğesinde çalar (sesli aramada görünmez durur)
      let element = this.remoteEl.querySelector('video');
      if (!element) {
        element = document.createElement('video');
        Object.assign(element, { autoplay: true, playsInline: true });
        this.remoteEl.replaceChildren(element);
      }
      element.srcObject = remote;
      element.play().catch(() => document.addEventListener('pointerdown', () => element.play().catch(() => {}), { once: true }));
      if (track.kind === 'video') this.onRemoteVideo(true);
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed') this.onError('Bağlantı kurulamadı. Ağın görüntülü görüşmeye izin vermiyor olabilir.');
    };
    for (const signal of this.early.splice(0)) await this.handleSignal(signal);
    // Teklifi (offer) yalnızca arayan yapar; aranan cevap verir. İkisi aynı anda teklif yapıp çakışmaz.
    if (this.isCaller) {
      await pc.setLocalDescription(await pc.createOffer());
      this.sendSignal({ description: pc.localDescription.toJSON() });
    }
  }

  async handleSignal({ description, candidate }) {
    const { pc } = this;
    if (!pc) return;
    try {
      if (description) {
        await pc.setRemoteDescription(description);
        if (description.type === 'offer') {
          await pc.setLocalDescription(await pc.createAnswer());
          this.sendSignal({ description: pc.localDescription.toJSON() });
        }
        // Teklif gelmeden ulaşan adaylar şimdi eklenir
        for (const queued of this.pendingCandidates.splice(0)) await pc.addIceCandidate(queued).catch(() => {});
      } else if (candidate) {
        if (pc.remoteDescription) await pc.addIceCandidate(candidate).catch(() => {});
        else this.pendingCandidates.push(candidate);
      }
    } catch {
      this.onError('Bağlantı kurulamadı.');
    }
  }

  async setMicEnabled(enabled) { this.stream?.getAudioTracks().forEach((t) => { t.enabled = enabled; }); }

  async setCameraEnabled(enabled) { this.stream?.getVideoTracks().forEach((t) => { t.enabled = enabled; }); }

  close() {
    this.unsubscribe?.();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.pc?.close();
    this.pc = null;
  }
}
