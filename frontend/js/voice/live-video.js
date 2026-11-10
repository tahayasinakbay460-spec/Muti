// Tam ekran kameralı canlı yayının ses + görüntü bağlantısı (bkz. backend services/live_service.py).
// Yayıncı mikrofon + kamera gönderir, izleyiciler yalnızca alır. İkisi aynı kanalda: ses ile görüntü
// senkron kalır, izleyicinin dakikası bir kez sayılır. Sağlayıcıyı sunucu söyler:
//   agora → herkes Agora'daki "live-<oda id>" kanalına girer; yayıncı "host", izleyiciler "audience"
//   mesh  → yayıncının tarayıcısı ses + görüntüyü her izleyiciye ayrı gönderir; bağlantı mesajları
//           oda kanalından (`live:signal`) taşınır. İzleyici sayısı sınırlı (info.max_viewers).
//
// Ekran şunları verir: info (GET /rooms/:id/camera/join), me, stageEl (görüntünün çizileceği kutu),
// channel (oda WebSocket'i, yalnızca mesh), refreshInfo, onError(mesaj), onNeedsTap() (tarayıcı sesi
// dokunmadan çalmıyor: ekran "Sesi aç" tuşu gösterir).
import { loadSdk } from './agora.js';
import { requireMedia } from './secure.js';

export async function connectLiveVideo(options) {
  requireMedia();
  const video = options.info.provider === 'agora' ? new AgoraLiveVideo(options) : new MeshLiveVideo(options);
  try {
    await video.start();
  } catch (error) {
    video.close();
    throw error;
  }
  return video;
}

function mediaErrorText(error) {
  if (error?.name === 'NotAllowedError' || error?.code === 'PERMISSION_DENIED') {
    return 'Kamera/mikrofon izni verilmedi. Tarayıcı ayarlarından izin ver.';
  }
  if (error?.name === 'NotFoundError' || error?.code === 'DEVICE_NOT_FOUND') return 'Kamera ya da mikrofon bulunamadı.';
  return 'Kamera açılamadı.';
}

// Yayına çıkmadan önce yayıncının kendini görmesi (yalnızca bu tarayıcıda, kimseye gitmez)
export async function startPreview(stageEl, facingMode = 'user') {
  requireMedia();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode, width: { ideal: 720 }, height: { ideal: 1280 } }, audio: false,
    });
  } catch (error) {
    throw Object.assign(new Error(mediaErrorText(error)), { code: 'camera_denied' });
  }
  const element = videoElement(stageEl, { muted: true, mirror: facingMode === 'user' });
  element.srcObject = stream;
  return { stop: () => stream.getTracks().forEach((track) => track.stop()) };
}

function videoElement(stageEl, { muted = false, mirror = false } = {}) {
  const element = document.createElement('video');
  Object.assign(element, { autoplay: true, playsInline: true, muted });
  if (mirror) element.style.transform = 'scaleX(-1)';
  stageEl.replaceChildren(element);
  return element;
}

class AgoraLiveVideo {
  constructor({ info, me, stageEl, refreshInfo, onError = () => {}, onNeedsTap = () => {} }) {
    Object.assign(this, { info, me, stageEl, refreshInfo, onError, onNeedsTap });
    this.isStreamer = info.can_publish;
    this.closed = false;
    this.facingMode = 'user';
  }

  async start() {
    const AgoraRTC = await loadSdk();
    this.AgoraRTC = AgoraRTC;
    // Tarayıcı sesi dokunmadan çalmadı: dokununca yayıncının sesini yeniden başlat
    AgoraRTC.onAutoplayFailed = () => this.onNeedsTap(() => this.client?.remoteUsers.forEach((u) => u.audioTrack?.play()));
    this.client = AgoraRTC.createClient({ mode: 'live', codec: 'vp8' });
    await this.client.setClientRole(this.isStreamer ? 'host' : 'audience');
    // Yalnızca sunucunun söylediği yayıncı çizilir/duyulur; başkası gönderse de görünmez
    this.client.on('user-published', async (user, mediaType) => {
      if (user.uid !== this.info.streamer_id || this.closed) return;
      await this.client.subscribe(user, mediaType);
      if (mediaType === 'video') user.videoTrack.play(this.stageEl, { fit: 'cover' });
      else user.audioTrack.play();
    });
    this.client.on('token-privilege-will-expire', async () => {
      try {
        this.info = await this.refreshInfo();
        await this.client.renewToken(this.info.token);
      } catch { /* yenilenemezse süre dolunca bağlantı kapanır; ekran "yayın bitti" der */ }
    });
    await this.client.join(this.info.app_id, this.info.channel, this.info.token, this.me.id);
    if (!this.isStreamer || this.closed) return;
    try {
      [this.mic, this.camera] = await AgoraRTC.createMicrophoneAndCameraTracks(
        { AEC: true, ANS: true, AGC: true },
        { encoderConfig: this.info.video_profile || '480p_1', facingMode: this.facingMode },
      );
    } catch (error) {
      throw Object.assign(new Error(mediaErrorText(error)), { code: 'camera_denied' });
    }
    this.camera.play(this.stageEl, { mirror: true, fit: 'cover' });
    if (!this.closed) await this.client.publish([this.mic, this.camera]);
  }

  async setMicEnabled(enabled) { await this.mic?.setEnabled(enabled); }

  // Ön / arka kamera (telefonda)
  async switchCamera() {
    if (!this.camera) return;
    const devices = await this.AgoraRTC.getCameras();
    if (devices.length < 2) return;
    const current = this.camera.getTrackLabel();
    const next = devices.find((d) => d.label !== current) || devices[0];
    await this.camera.setDevice(next.deviceId);
  }

  close() {
    this.closed = true;
    this.mic?.close();
    this.camera?.close();
    this.client?.removeAllListeners();
    this.client?.leave().catch(() => {});
  }
}

class MeshLiveVideo {
  constructor({ info, me, stageEl, channel, onError = () => {}, onNeedsTap = () => {} }) {
    Object.assign(this, { info, me, stageEl, channel, onError, onNeedsTap });
    this.isStreamer = info.can_publish;
    this.peers = new Map();   // karşı taraf id → RTCPeerConnection
    this.facingMode = 'user';
    this.onSignal = (signal) => this.handleSignal(signal);
    this.onLeft = ({ user_id: userId }) => this.dropPeer(userId);
  }

  async start() {
    this.channel.on('live:signal', this.onSignal).on('room:user_left', this.onLeft);
    if (this.isStreamer) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
          video: { facingMode: this.facingMode, width: { ideal: 640 }, height: { ideal: 960 } },
        });
      } catch (error) {
        throw Object.assign(new Error(mediaErrorText(error)), { code: 'camera_denied' });
      }
      // Kendi sesimizi duymayalım (muted); izleyiciye giden akış etkilenmez
      videoElement(this.stageEl, { muted: true, mirror: true }).srcObject = new MediaStream(this.stream.getVideoTracks());
      return;
    }
    // İzleyici bağlantıyı kendisi ister: yalnızca alacağını söyleyen bir teklif gönderir
    const pc = this.createPeer(this.info.streamer_id);
    pc.addTransceiver('audio', { direction: 'recvonly' });
    pc.addTransceiver('video', { direction: 'recvonly' });
    await pc.setLocalDescription(await pc.createOffer());
    this.send(this.info.streamer_id, { description: pc.localDescription.toJSON() });
  }

  send(to, signal) { this.channel.send('live:signal', { to, ...signal }); }

  createPeer(userId) {
    const pc = new RTCPeerConnection({ iceServers: this.info.ice_servers });
    pc.pendingCandidates = [];
    this.peers.set(userId, pc);
    pc.onicecandidate = ({ candidate }) => {
      if (candidate) this.send(userId, { candidate: candidate.toJSON() });
    };
    pc.ontrack = ({ streams: [remote] }) => {
      // Ses de görüntü de aynı <video> öğesinde çalar
      let element = this.stageEl.querySelector('video');
      if (!element) element = videoElement(this.stageEl);
      if (element.srcObject !== remote) element.srcObject = remote;
      element.play().catch(() => {
        // Tarayıcı sesli videoyu dokunmadan oynatmadı: önce sessiz başlat, "Sesi aç" tuşu çıksın
        element.muted = true;
        element.play().catch(() => {});
        this.onNeedsTap(() => { element.muted = false; element.play().catch(() => {}); });
      });
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed' && !this.isStreamer) this.onError('Yayına bağlanılamadı. Ağın izin vermiyor olabilir.');
    };
    return pc;
  }

  async handleSignal({ from, description, candidate }) {
    // İzleyici yalnızca yayıncıdan gelen mesajı dinler; yayıncı herkesin teklifini kabul eder (sınıra kadar)
    if (!this.isStreamer && from !== this.info.streamer_id) return;
    let pc = this.peers.get(from);
    try {
      if (description?.type === 'offer' && this.isStreamer) {
        if (!pc) {
          if (this.peers.size >= (this.info.max_viewers || 8)) return;   // telefonun yükleme hızı sınırı
          pc = this.createPeer(from);
          this.stream.getTracks().forEach((track) => pc.addTrack(track, this.stream));
        }
        await pc.setRemoteDescription(description);
        await pc.setLocalDescription(await pc.createAnswer());
        this.send(from, { description: pc.localDescription.toJSON() });
      } else if (description && pc) {
        await pc.setRemoteDescription(description);
      } else if (candidate && pc) {
        if (!pc.remoteDescription) return void pc.pendingCandidates.push(candidate);
        await pc.addIceCandidate(candidate).catch(() => {});
      }
      if (pc?.remoteDescription) {
        for (const queued of pc.pendingCandidates.splice(0)) await pc.addIceCandidate(queued).catch(() => {});
      }
    } catch {
      if (!this.isStreamer) this.onError('Yayına bağlanılamadı.');
    }
  }

  async setMicEnabled(enabled) { this.stream?.getAudioTracks().forEach((t) => { t.enabled = enabled; }); }

  // Ön / arka kamera: yeni kamerayı açıp bütün izleyici bağlantılarında görüntüyü değiştirir
  async switchCamera() {
    if (!this.stream) return;
    this.facingMode = this.facingMode === 'user' ? 'environment' : 'user';
    let fresh;
    try {
      fresh = await navigator.mediaDevices.getUserMedia({ video: { facingMode: this.facingMode } });
    } catch {
      return;
    }
    const [track] = fresh.getVideoTracks();
    const [old] = this.stream.getVideoTracks();
    this.peers.forEach((pc) => pc.getSenders().find((s) => s.track?.kind === 'video')?.replaceTrack(track));
    this.stream.removeTrack(old);
    old.stop();
    this.stream.addTrack(track);
    const element = this.stageEl.querySelector('video');
    element.style.transform = this.facingMode === 'user' ? 'scaleX(-1)' : '';
    element.srcObject = new MediaStream([track]);
  }

  dropPeer(userId) {
    this.peers.get(userId)?.close();
    this.peers.delete(userId);
  }

  close() {
    this.channel.off('live:signal', this.onSignal);
    this.channel.off('room:user_left', this.onLeft);
    this.peers.forEach((pc) => pc.close());
    this.peers.clear();
    this.stream?.getTracks().forEach((track) => track.stop());
  }
}
