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
//   reconnect()          → isteğe bağlı: kopan sesi yeniden kur ("Yeniden bağlan" tuşu)
// Ekrana üç şey bildirir: onSpeaking(Set<kullanıcı id>), onError(mesaj) ve
// onConnectionLost(true/false) = ses koptu, tuşu göster / bağlantı yeniden deneniyor, gizle.
import { api } from '../api.js';
import { retried } from './retry.js';
import { mediaBlockedReason } from './secure.js';

const CLIENTS = {
  mesh: () => import('./mesh.js'),
  livekit: () => import('./livekit.js'),
  agora: () => import('./agora.js'),
};

export async function joinVoice({ room, me, channel, onSpeaking, onError, onConnectionLost, isCancelled = () => false }) {
  // Güvensiz adreste (telefondan http://192.168...) mikrofon hiç açılamaz: sebebini söyle
  const blocked = mediaBlockedReason();
  if (blocked) {
    onError(blocked);
    return null;
  }
  // Odaya girerken ağ bir an gittiyse kişi sessiz kalmasın. Odadan atılan için denemenin anlamı yok.
  let banned = false;
  return retried(async () => {
    try {
      return await connectOnce({ room, me, channel, onSpeaking, onError, onConnectionLost });
    } catch (error) {
      banned = error.code === 'room_banned';
      throw error;
    }
  }, { shouldStop: () => banned || isCancelled() });
}

async function connectOnce({ room, me, channel, onSpeaking, onError, onConnectionLost }) {
  const info = await api.getVoiceJoin(room.id);
  const load = CLIENTS[info.provider];
  if (!load) {
    onError('Ses sağlayıcısı tanınmadı.');
    return null;
  }
  const { createVoiceClient } = await load();
  const client = createVoiceClient({
    info, me, channel, onSpeaking, onError, onConnectionLost,
    // Konuşma izni token'a yazılan sağlayıcılarda izin değişince yeni bilgi almak için
    refreshInfo: () => api.getVoiceJoin(room.id),
  });
  // Ses hataları yalnızca tarayıcıda görünür; sunucu kaydına düşsün diye bildiriyoruz.
  // Bildirim başarısız olursa kullanıcıyı etkilemesin.
  client.report = (event, detail = '') => {
    api.reportVoiceEvent({ room_id: room.id, provider: info.provider, event, detail: String(detail).slice(0, 300) })
      .catch(() => {});
  };
  try {
    await client.start();
  } catch (error) {
    client.report('join_failed', `${error.code || ''} ${error.message}`);
    client.close();
    throw error;
  }
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
