// Kameralı canlı yayının GÖRÜNTÜ bağlantısı. Ses buradan gitmez: yayıncının sesi odanın ses
// kanalından (koltuk) gider; bu dosya yalnızca kamerayı taşır (bkz. backend voice/base.py live_join_info).
// Sağlayıcıyı sunucu söyler:
//   agora → herkes Agora'daki "live-<oda id>" kanalına girer; yayıncı "host", izleyiciler "audience"
//   mesh  → yayıncının tarayıcısı görüntüyü her izleyiciye ayrı gönderir; bağlantı mesajları oda
//           kanalından (`live:signal`) taşınır. İzleyici sayısı sınırlı (info.max_viewers).
//
// Ekran şunları verir: info (GET /rooms/:id/camera/join), me, stageEl (görüntünün çizileceği kutu),
// channel (oda WebSocket'i, yalnızca mesh), refreshInfo, onError(mesaj).
import { loadSdk } from './agora.js';

export async function connectLiveVideo(options) {
  const video = options.info.provider === 'agora' ? new AgoraLiveVideo(options) : new MeshLiveVideo(options);
  try {
    await video.start();
  } catch (error) {
    video.close();
    throw error;
  }
  return video;
}

function cameraErrorText(error) {
  if (error?.name === 'NotAllowedError' || error?.code === 'PERMISSION_DENIED') {
    return 'Kamera izni verilmedi. Tarayıcı ayarlarından izin ver.';
  }
  if (error?.name === 'NotFoundError' || error?.code === 'DEVICE_NOT_FOUND') return 'Kamera bulunamadı.';
  return 'Kamera açılamadı.';
}

function videoElement(stageEl, { muted = false, mirror = false } = {}) {
  const element = document.createElement('video');
  Object.assign(element, { autoplay: true, playsInline: true, muted });
  if (mirror) element.style.transform = 'scaleX(-1)';
  stageEl.replaceChildren(element);
  return element;
}

class AgoraLiveVideo {
  constructor({ info, me, stageEl, refreshInfo, onError = () => {} }) {
    Object.assign(this, { info, me, stageEl, refreshInfo, onError });
    this.isStreamer = info.can_publish;
    this.closed = false;
  }

  async start() {
    const AgoraRTC = await loadSdk();
    this.client = AgoraRTC.createClient({ mode: 'live', codec: 'vp8' });
    await this.client.setClientRole(this.isStreamer ? 'host' : 'audience');
    // Yalnızca sunucunun söylediği yayıncının görüntüsü çizilir; başkası görüntü gönderse de görünmez
    this.client.on('user-published', async (user, mediaType) => {
      if (mediaType !== 'video' || user.uid !== this.info.streamer_id || this.closed) return;
      await this.client.subscribe(user, 'video');
      user.videoTrack.play(this.stageEl, { fit: 'cover' });
    });
    this.client.on('token-privilege-will-expire', async () => {
      try {
        this.info = await this.refreshInfo();
        await this.client.renewToken(this.info.token);
      } catch { /* yenilenemezse süre dolunca görüntü kapanır; ses etkilenmez */ }
    });
    await this.client.join(this.info.app_id, this.info.channel, this.info.token, this.me.id);
    if (!this.isStreamer || this.closed) return;
    try {
      this.camera = await AgoraRTC.createCameraVideoTrack({ encoderConfig: this.info.video_profile || '480p_1' });
    } catch (error) {
      throw Object.assign(new Error(cameraErrorText(error)), { code: 'camera_denied' });
    }
    this.camera.play(this.stageEl, { mirror: true, fit: 'cover' });
    if (!this.closed) await this.client.publish(this.camera);
  }

  close() {
    this.closed = true;
    this.camera?.close();
    this.client?.removeAllListeners();
    this.client?.leave().catch(() => {});
  }
}

class MeshLiveVideo {
  constructor({ info, me, stageEl, channel, onError = () => {} }) {
    Object.assign(this, { info, me, stageEl, channel, onError });
    this.isStreamer = info.can_publish;
    this.peers = new Map();   // karşı taraf id → RTCPeerConnection
    this.onSignal = (signal) => this.handleSignal(signal);
    this.onLeft = ({ user_id: userId }) => this.dropPeer(userId);
  }

  async start() {
    this.channel.on('live:signal', this.onSignal).on('room:user_left', this.onLeft);
    if (this.isStreamer) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false,
        });
      } catch (error) {
        throw Object.assign(new Error(cameraErrorText(error)), { code: 'camera_denied' });
      }
      videoElement(this.stageEl, { muted: true, mirror: true }).srcObject = this.stream;
      return;
    }
    // İzleyici bağlantıyı kendisi ister: yalnızca görüntü alacağını söyleyen bir teklif gönderir
    const pc = this.createPeer(this.info.streamer_id);
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
      const element = videoElement(this.stageEl, { muted: true });
      element.srcObject = remote;
      element.play().catch(() => {});
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed' && !this.isStreamer) this.onError('Yayın görüntüsü alınamadı. Ağın izin vermiyor olabilir.');
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
      if (!this.isStreamer) this.onError('Yayın görüntüsü alınamadı.');
    }
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
