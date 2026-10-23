"""
Sesli görüşme sağlayıcısı sözleşmesi.

NEDEN BİR SÖZLEŞME?
Gerçek zamanlı ses (WebRTC) için farklı yollar var:
  - mesh    → tarayıcılar birbirine doğrudan bağlanır; sunucumuz yalnızca "kim kime
              bağlanacak" mesajlarını (sinyal) taşır. Ek sunucu gerekmez, küçük odalar için yeter.
  - livekit → açık kaynak bir medya sunucusu (SFU). Herkes sesini bir kez SFU'ya gönderir,
              SFU dağıtır. Yüzlerce dinleyicili odalar için gerekir. Kendi sunucumuza
              kurulabilir ya da LiveKit Cloud gibi bir hizmetten alınabilir.
  - agora   → ücretli bulut SFU; sunucu kurmadan kalabalık oda ve sıkı ağlar için.
İleride başka bir sağlayıcıya (mediasoup, Janus...) geçmek isteyebiliriz. Kodun
geri kalanı yalnızca bu sözleşmeyi bilir; sağlayıcı değiştirmek = yeni bir sınıf yazıp
`.env` içindeki VOICE_PROVIDER'ı değiştirmek. Oda, koltuk ve yetki kuralları hep bizde kalır.

SAĞLAYICIDAN BEKLENENLER
  1. join_info: istemcinin sese bağlanması için gerekenleri üretir (adres, token, ICE sunucuları).
  2. Kancalar (hook): odada bir şey değişince sağlayıcıya haber verilir. SFU'lu sağlayıcı
     bunları sunucu tarafında uygular (koltuktan inenin yayın izni alınır, atılan kişi
     ses odasından çıkarılır). Mesh'te sunucu medyaya dokunamaz; kancalar boş kalır ve
     kuralları istemciler uygular (bkz. frontend js/voice/).
"""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class IceServer(BaseModel):
    """
    Tarayıcının karşı tarafa ulaşmak için kullanacağı yardımcı sunucu (RTCIceServer).
      - STUN: "dışarıdan nasıl görünüyorum?" sorusunu cevaplar; çoğu ağda bu yeter.
      - TURN: doğrudan bağlantı kurulamazsa (sıkı şirket/mobil ağları) sesi aktarır.
    """
    urls: list[str]
    username: str | None = None
    credential: str | None = None


class VoiceJoinInfo(BaseModel):
    """GET /rooms/{id}/voice cevabı. Alanların hangileri dolu olduğu sağlayıcıya göre değişir."""
    provider: str                      # "mesh" | "livekit" | "agora"
    # Bu kişi şu an konuşabilir mi (koltukta ve mikrofonu engelli değil)?
    can_publish: bool
    ice_servers: list[IceServer] = []  # mesh: tarayıcının kullanacağı STUN/TURN listesi
    url: str | None = None             # SFU: bağlanılacak adres (wss://...)
    token: str | None = None           # SFU: kısa ömürlü giriş anahtarı
    app_id: str | None = None          # agora: projenin herkese açık kimliği (gizli değil)
    channel: str | None = None         # agora: odanın ses kanalı adı


class VoiceProvider(ABC):
    name: str

    # Sunucumuz oda WebSocket'i üzerinden sinyal (`voice:signal`) taşıyacak mı?
    # Yalnızca mesh'te gerekir; SFU'lu sağlayıcılar kendi bağlantılarını kurar.
    relays_signals: bool = False

    @abstractmethod
    async def join_info(self, room_id: int, user_id: int, display_name: str, can_publish: bool) -> VoiceJoinInfo:
        """İstemcinin bu odanın sesine bağlanması için gerekenler."""

    async def sync_publishers(self, room_id: int, publisher_ids: set[int]) -> None:
        """Koltuklar değişti: şu an konuşma izni olanlar bunlar (koltukta ve engelsiz)."""

    async def remove_participant(self, room_id: int, user_id: int) -> None:
        """Kişi odadan atıldı: sesten de çıkarılmalı."""

    async def close_room(self, room_id: int) -> None:
        """Oda kapatıldı: ses odası da kapatılmalı."""
