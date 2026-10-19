"""
Mesh (eşten eşe) ses: tarayıcılar sesi birbirine doğrudan gönderir.

Sunucunun işi yalnızca sinyal taşımaktır: iki tarayıcının bağlantı kurmak için
birbirine yollaması gereken teklif/cevap (SDP) ve ağ adresi (ICE candidate) mesajlarını
oda WebSocket'inden alıp karşı tarafa iletir (bkz. realtime/room_socket.py, `voice:signal`).

KİM KİME BAĞLANIR? Koltuktaki her konuşmacı, odadaki herkese sesini ayrı ayrı gönderir.
  - Dinleyici → her konuşmacıya bağlantı açar (yalnızca dinler).
  - Konuşmacı ↔ konuşmacı → küçük id'li olan bağlantıyı açar.
SINIR: 8 konuşmacı ve 30 dinleyicide bir konuşmacı 37 ayrı ses akışı gönderir. Telefon
ve ev interneti için bu yaklaşık üst sınırdır. Daha kalabalık odalar için VOICE_PROVIDER=livekit.

SUNUCU MEDYAYA DOKUNAMAZ: mikrofon engeli ve koltuk kuralını istemciler uygular.
Dinleyiciler, koltukta olmayan ya da mikrofonu kapalı görünen birinin sesini kendi
tarafında kısar; bu yüzden kuralı çiğneyen değiştirilmiş bir istemcinin sesi de duyulmaz.
"""
from app.voice.base import VoiceJoinInfo, VoiceProvider
from app.voice.ice import ice_servers_for


class MeshVoiceProvider(VoiceProvider):
    name = "mesh"
    relays_signals = True

    async def join_info(self, room_id: int, user_id: int, display_name: str, can_publish: bool) -> VoiceJoinInfo:
        return VoiceJoinInfo(provider=self.name, can_publish=can_publish, ice_servers=ice_servers_for(user_id))
