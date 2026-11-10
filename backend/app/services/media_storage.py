"""
Yüklenen dosyaların (sesli mesaj ve fotoğraf) saklandığı yer.

NEDEN BİR SÖZLEŞME?
Bugün dosyalar sunucunun diskinde duruyor (LocalMediaStorage). Kullanıcı ve sunucu sayısı
artınca dosyalar bir nesne deposuna (S3, Cloudflare R2, MinIO) taşınır: o zaman yalnızca
yeni bir sınıf yazılır, kodun geri kalanı `media_storage` nesnesini aynı şekilde kullanır.

GÜVENLİK
  - Dosya adını kullanıcı seçmez: rastgele üretilir. Böylece "../../.env" gibi bir adla
    sunucudaki başka bir dosyaya ulaşılamaz, adı tahmin edip başkasının kaydı da açılamaz.
  - Klasör dışarıya (statik dosya olarak) açılmaz. Dosyayı yalnızca yetki kontrolünden geçen
    uç verir (bkz. message_service.voice_file).
"""
import re
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

import anyio

from app.core.config import BACKEND_DIR, settings

# Depodaki anahtar biçimi: "voice/<32 onaltılık karakter>.<uzantı>" (sesli mesaj) ya da
# "images/<32 onaltılık karakter>.<uzantı>" (fotoğraf). Başka bir şeye izin yok.
KEY_PATTERN = re.compile(r"^(voice/[0-9a-f]{32}\.(webm|ogg|m4a)|images/[0-9a-f]{32}\.(jpg|png|webp))$")


class MediaStorage(ABC):
    @abstractmethod
    async def save(self, folder: str, extension: str, data: bytes) -> str:
        """Dosyayı saklar, daha sonra okumak için anahtarını döner."""

    @abstractmethod
    def local_path(self, key: str) -> Path:
        """Dosyanın diskteki yolu (cevap olarak doğrudan gönderilir)."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Dosyayı siler; yoksa sessizce geçer."""


class LocalMediaStorage(MediaStorage):
    """
    Dosyaları sunucunun diskinde tutar.
    DEMO KISAYOLU: tek sunucu için. Docker'da klasör kalıcı bir volume'a bağlanmalı
    (bkz. deploy/docker-compose.yml), yoksa her güncellemede kayıtlar kaybolur.
    """

    def __init__(self, root: Path):
        self.root = root

    async def save(self, folder: str, extension: str, data: bytes) -> str:
        key = f"{folder}/{secrets.token_hex(16)}.{extension}"
        path = self.local_path(key)
        # Disk işlemi sunucuyu bekletmesin diye ayrı bir iş parçacığında (thread) yazılır.
        await anyio.to_thread.run_sync(self._write, path, data)
        return key

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def local_path(self, key: str) -> Path:
        if not KEY_PATTERN.match(key):
            raise ValueError("invalid media key")
        return self.root / key

    async def delete(self, key: str) -> None:
        await anyio.to_thread.run_sync(lambda: self.local_path(key).unlink(missing_ok=True))


media_storage: MediaStorage = LocalMediaStorage(Path(settings.media_dir) if settings.media_dir else BACKEND_DIR / "media")
