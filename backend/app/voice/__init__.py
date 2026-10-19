"""
Sesli görüşme (WebRTC) katmanı. Hangi sağlayıcının kullanılacağı `.env` içindeki
VOICE_PROVIDER ile seçilir; kodun geri kalanı yalnızca `voice_provider` nesnesini kullanır.

Yeni bir sağlayıcı eklemek için:
  1. app/voice/ altına VoiceProvider'dan türeyen bir sınıf yaz (bkz. base.py).
  2. Aşağıdaki `_build` fonksiyonuna bir satır ekle.
  3. Frontend'de js/voice/ altına aynı adla bir istemci yaz ve js/voice/index.js'e ekle.
"""
from app.core.config import settings
from app.voice.base import IceServer, VoiceJoinInfo, VoiceProvider


def _build() -> VoiceProvider:
    if settings.voice_provider == "livekit":
        from app.voice.livekit import LiveKitVoiceProvider
        return LiveKitVoiceProvider(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
    from app.voice.mesh import MeshVoiceProvider
    return MeshVoiceProvider()


# Uygulamanın kullandığı tek ses sağlayıcısı.
voice_provider: VoiceProvider = _build()

__all__ = ["IceServer", "VoiceJoinInfo", "VoiceProvider", "voice_provider"]
