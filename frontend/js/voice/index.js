// Sesli görüşme girişi. Odaya girince sunucuya "sesine nasıl bağlanayım?" diye sorar
// (GET /rooms/:id/voice) ve cevaptaki sağlayıcıya göre doğru istemciyi yükler.
//
// Sağlayıcı sunucuda seçilir (backend .env: VOICE_PROVIDER). Frontend'de bir şey
// değiştirmek gerekmez; yeni bir sağlayıcı eklemek = bu klasöre aynı arayüzde bir dosya
// yazıp aşağıdaki listeye eklemek. Her istemci şu metodları sunar:
//   start()              → bağlan
//   update(seats)        → koltuklar değişti (oturdum/kalktım, mikrofon açıldı/kapandı)
//   removePeer(userId)   → kişi odadan çıktı/atıldı
//   close()              → odadan çıkarken her şeyi kapat
// Ekrana iki şey bildirir: onSpeaking(Set<kullanıcı id>) ve onError(mesaj).
import { api } from '../api.js';
import { USE_MOCK } from '../config.js';

const CLIENTS = {
  mesh: () => import('./mesh.js'),
  livekit: () => import('./livekit.js'),
  agora: () => import('./agora.js'),
};

export async function joinVoice({ room, me, channel, onSpeaking, onError }) {
  // Mock'ta ses yok; "konuşuyor" halkasını mock kanal taklit eder
  if (USE_MOCK) return null;
  if (!window.RTCPeerConnection) {
    onError('Bu tarayıcı sesli görüşmeyi desteklemiyor.');
    return null;
  }
  const info = await api.getVoiceJoin(room.id);
  const load = CLIENTS[info.provider];
  if (!load) {
    onError('Ses sağlayıcısı tanınmadı.');
    return null;
  }
  const { createVoiceClient } = await load();
  const client = createVoiceClient({
    info, me, channel, onSpeaking, onError,
    // Konuşma izni token'a yazılan sağlayıcılarda izin değişince yeni bilgi almak için
    refreshInfo: () => api.getVoiceJoin(room.id),
  });
  await client.start();
  return client;
}

// Tarayıcılar sesi kullanıcı sayfaya dokunmadan çalmaz (autoplay kuralı).
// Çalınamayan ses öğelerini ilk dokunuşta yeniden başlatır.
export function playWhenAllowed(audio, onUnlock) {
  audio.play().catch(() => {
    const retry = () => {
      audio.play().catch(() => {});
      onUnlock?.();
    };
    document.addEventListener('pointerdown', retry, { once: true });
  });
}
