// Mesh (eşten eşe) ses istemcisi: sesi diğer tarayıcılara doğrudan gönderir.
// Sunucu yalnızca bağlantı mesajlarını (`voice:signal`) oda WebSocket'i üzerinden taşır.
//
// KİM KİME BAĞLANIR? (koltuk listesinden herkes aynı sonuca varır)
//   - Koltukta değilsem: koltuktaki herkese ben bağlanırım (yalnızca dinlerim).
//   - Koltuktaysam: koltuktaki diğerlerinden id'si benden büyük olanlara ben bağlanırım,
//     küçük olanlar bana bağlanır. Dinleyiciler de bana bağlanır.
//   - İki taraf da koltukta değilse bağlantı kapatılır.
//
// Her bağlantıda tek bir ses kanalı (transceiver) vardır ve her iki yönde açıktır.
// Koltuğa oturunca mikrofon bu kanala takılır, kalkınca çıkarılır (replaceTrack).
// Bu yüzden oturup kalkmak bağlantıyı yeniden kurmayı gerektirmez.
//
// Aynı anda iki taraf teklif gönderirse ("glare") WebRTC'nin önerdiği "perfect negotiation"
// yöntemi uygulanır: id'si büyük olan taraf nazik (polite) davranır ve geri çekilir.
//
// KURAL UYGULAMASI: Sunucu sese dokunamaz. Bu yüzden herkes, koltukta olmayan ya da
// mikrofonu kapalı görünen birinin sesini kendi tarafında kısar (applyRemoteMute).
import { SpeakingDetector } from './speaking.js';
import { playWhenAllowed } from './index.js';

export function createVoiceClient(options) {
  return new MeshVoiceClient(options);
}

class MeshVoiceClient {
  constructor({ info, me, channel, onSpeaking, onError }) {
    this.me = me;
    this.channel = channel;
    this.iceServers = info.ice_servers;
    this.onError = onError;
    this.peers = new Map();       // kullanıcı id → { pc, polite, makingOffer, ignoreOffer, transceiver, audio }
    this.seats = [];
    this.localStream = null;
    this.micRequest = null;
    this.closed = false;
    this.detector = new SpeakingDetector(onSpeaking);
    this.audioRoot = document.createElement('div');
    this.audioRoot.hidden = true;
    document.body.appendChild(this.audioRoot);
    this.onSignal = (payload) => this.handleSignal(payload);
    channel.on('voice:signal', this.onSignal);
  }

  async start() {}

  seatOf(userId) {
    return this.seats.find((s) => s.user_id === userId);
  }

  localTrack() {
    return this.localStream?.getAudioTracks()[0] || null;
  }

  update(seats) {
    if (this.closed) return;
    this.seats = seats;
    const mySeat = this.seatOf(this.me.id);

    if (mySeat && !this.localStream && !this.micRequest) this.acquireMic();
    if (!mySeat && this.localStream) this.releaseMic();
    // Mikrofonu kapatmak = sesi göndermeyi durdurmak (bağlantı açık kalır)
    if (this.localTrack()) this.localTrack().enabled = !mySeat.is_muted;

    const seatedOthers = new Set(seats.filter((s) => s.user_id && s.user_id !== this.me.id).map((s) => s.user_id));
    for (const id of [...this.peers.keys()]) {
      if (!mySeat && !seatedOthers.has(id)) this.removePeer(id);
    }
    for (const id of seatedOthers) {
      if (!this.peers.has(id) && (!mySeat || this.me.id < id)) this.createPeer(id, true);
    }
    for (const [id, peer] of this.peers) this.applyRemoteMute(id, peer);
  }

  applyRemoteMute(userId, peer) {
    const seat = this.seatOf(userId);
    if (peer.audio) peer.audio.muted = !seat || seat.is_muted;
  }

  // ─── Mikrofon ──────────────────────────────────────────────────────────────
  acquireMic() {
    if (!navigator.mediaDevices?.getUserMedia) {
      this.onError('Mikrofon için güvenli bağlantı (https) gerekiyor.');
      return;
    }
    this.micRequest = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    }).then((stream) => {
      const mySeat = this.seatOf(this.me.id);
      // İzin penceresi açıkken koltuktan kalkmış ya da odadan çıkmış olabiliriz
      if (this.closed || !mySeat) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      this.localStream = stream;
      this.localTrack().enabled = !mySeat.is_muted;
      this.peers.forEach((peer) => peer.transceiver?.sender.replaceTrack(this.localTrack()));
      this.detector.add(this.me.id, stream);
    }).catch(() => {
      this.onError('Mikrofona izin verilmedi. Konuşmak için tarayıcı ayarlarından izin ver.');
    }).finally(() => {
      this.micRequest = null;
    });
  }

  releaseMic() {
    this.localStream.getTracks().forEach((t) => t.stop());
    this.localStream = null;
    this.peers.forEach((peer) => peer.transceiver?.sender.replaceTrack(null));
    this.detector.remove(this.me.id);
  }

  // ─── Bağlantılar ───────────────────────────────────────────────────────────
  send(to, message) {
    this.channel.send('voice:signal', { to, ...message });
  }

  createPeer(userId, isInitiator) {
    const pc = new RTCPeerConnection({ iceServers: this.iceServers });
    const peer = { pc, polite: this.me.id > userId, makingOffer: false, ignoreOffer: false, transceiver: null, audio: null };
    this.peers.set(userId, peer);

    pc.onicecandidate = ({ candidate }) => {
      if (candidate) this.send(userId, { candidate: candidate.toJSON() });
    };
    pc.onnegotiationneeded = async () => {
      try {
        peer.makingOffer = true;
        await pc.setLocalDescription();
        this.send(userId, { description: pc.localDescription.toJSON() });
      } catch (error) {
        console.warn('[voice] offer failed', error);
      } finally {
        peer.makingOffer = false;
      }
    };
    pc.ontrack = ({ track, streams }) => {
      const stream = streams[0] || new MediaStream([track]);
      peer.audio?.remove();
      peer.audio = document.createElement('audio');
      peer.audio.autoplay = true;
      peer.audio.srcObject = stream;
      this.audioRoot.appendChild(peer.audio);
      this.applyRemoteMute(userId, peer);
      playWhenAllowed(peer.audio, () => this.detector.resume());
      this.detector.add(userId, stream);
    };
    pc.onconnectionstatechange = () => {
      // Ağ değişti (ör. Wi-Fi → mobil veri): bağlantıyı bozmadan yeni yol ara
      if (pc.connectionState === 'failed') pc.restartIce();
    };

    if (isInitiator) {
      peer.transceiver = pc.addTransceiver('audio', { direction: 'sendrecv' });
      peer.transceiver.sender.replaceTrack(this.localTrack());
    }
    return peer;
  }

  // Karşı taraftan gelen bağlantı mesajı (teklif, cevap ya da ağ adresi)
  async handleSignal({ from, description, candidate }) {
    if (this.closed) return;
    let peer = this.peers.get(from);
    if (!peer) {
      // Bize ilk kez biri bağlanıyor (dinleyici ya da id'si küçük bir konuşmacı)
      if (description?.type !== 'offer') return;
      peer = this.createPeer(from, false);
    }
    const { pc } = peer;
    try {
      if (description) {
        const collision = description.type === 'offer' && (peer.makingOffer || pc.signalingState !== 'stable');
        peer.ignoreOffer = !peer.polite && collision;
        if (peer.ignoreOffer) return;
        await pc.setRemoteDescription(description);
        if (description.type === 'offer') {
          // Teklifle gelen ses kanalına kendi mikrofonumuzu takıp iki yönlü açıyoruz
          peer.transceiver ||= pc.getTransceivers().find((t) => t.receiver.track.kind === 'audio');
          if (peer.transceiver) {
            peer.transceiver.direction = 'sendrecv';
            await peer.transceiver.sender.replaceTrack(this.localTrack());
          }
          await pc.setLocalDescription();
          this.send(from, { description: pc.localDescription.toJSON() });
        }
      } else if (candidate) {
        try {
          await pc.addIceCandidate(candidate);
        } catch (error) {
          if (!peer.ignoreOffer) throw error;
        }
      }
    } catch (error) {
      console.warn('[voice] signal failed', error);
    }
  }

  removePeer(userId) {
    const peer = this.peers.get(userId);
    if (!peer) return;
    peer.pc.close();
    peer.audio?.remove();
    this.detector.remove(userId);
    this.peers.delete(userId);
  }

  close() {
    this.closed = true;
    this.channel.off('voice:signal', this.onSignal);
    [...this.peers.keys()].forEach((id) => this.removePeer(id));
    if (this.localStream) this.releaseMic();
    this.detector.close();
    this.audioRoot.remove();
  }
}
