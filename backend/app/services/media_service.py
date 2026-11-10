"""
Fotoğraf yükleme: profil fotoğrafı/kapak, anı, oda kapağı ve özel mesaj.

GÜVENLİK KURALLARI
  1. Tür: yalnızca JPEG, PNG, WebP. `Content-Type` başlığına değil dosyanın ilk baytlarına
     ("sihirli bayt", her biçimin dosya başındaki imzası) bakılır: adı .jpg olan bir HTML ya da
     program dosyası kabul edilmez.
  2. Boyut: en fazla IMAGE_MAX_BYTES. Uygulama yüklemeden önce fotoğrafı küçültür ve konum bilgisini
     (EXIF) siler; sunucu yine de sınırı kendisi uygular.
  3. Sahiplik: her yükleme `media_uploads` tablosuna "kim, ne için" diye yazılır. Profil, anı ve oda
     kapağı yalnızca kişinin kendi yüklediği, o iş için yüklediği görseli kabul eder.
  4. Gizlilik: sohbet fotoğrafları herkese açık adresten verilmez; yalnızca sohbetin iki üyesine.
  5. Sıklık: bir saatte en fazla IMAGE_UPLOADS_PER_HOUR yükleme (diski doldurma girişimine karşı).
  6. Misafir hesaplar fotoğraf yükleyemez (kimliği belirsiz hesaplardan uygunsuz içerik).

DEMO KISAYOLU: Fotoğraflar otomatik içerik denetiminden (çıplaklık vb.) geçmiyor; şikâyet ve panel
ile yakalanıyor. Kameralı yayından önce otomatik denetim hizmeti eklenmeli.
"""
import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.logs import audit
from app.models import MediaUpload, User
from app.schemas.media import MediaOut
from app.services.media_storage import media_storage

# Herkese açık görsellerin adresi. Profil, anı ve oda kapağı bu adresle saklanır.
PUBLIC_PREFIX = "/api/v1/media/images/"
PUBLIC_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
PUBLIC_KINDS = ("avatar", "cover", "moment", "room_cover")
IMAGE_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def sniff_image(data: bytes) -> str | None:
    """Dosyanın ilk baytlarından gerçek türü bulur (jpg / png / webp), tanınmazsa None."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


async def store_image(db: AsyncSession, user: User, kind: str, content_type: str, data: bytes) -> MediaUpload:
    """Görseli doğrulayıp saklar ve kaydını yazar (commit eder). Sohbet fotoğrafı da buradan geçer."""
    if user.is_guest:
        raise ForbiddenError("Fotoğraf yüklemek için hesap oluştur.", code="guest_cannot_upload")
    declared = IMAGE_CONTENT_TYPES.get(content_type.split(";")[0].strip().lower())
    if declared is None:
        raise AppError("Yalnızca JPEG, PNG ya da WebP fotoğraf yüklenebilir.", code="unsupported_image")
    if not data:
        raise AppError("Dosya boş.", code="empty_image")
    if len(data) > settings.image_max_bytes:
        raise AppError("Fotoğraf çok büyük.", code="image_too_large")
    actual = sniff_image(data)
    if actual is None:
        raise AppError("Dosya bir fotoğraf değil.", code="invalid_image_file")
    recent = await db.scalar(
        select(func.count(MediaUpload.id))
        .where(MediaUpload.owner_id == user.id, MediaUpload.created_at >= utcnow() - timedelta(hours=1))
    )
    if recent >= settings.image_uploads_per_hour:
        raise AppError("Çok fazla fotoğraf yükledin, biraz sonra tekrar dene.", code="too_many_uploads")

    # Uzantıyı başlıktan değil gerçek içerikten alıyoruz: tarayıcı dosyayı hep doğru türle sunar.
    key = await media_storage.save("images", actual, data)
    upload = MediaUpload(key=key, owner_id=user.id, kind=kind, size_bytes=len(data))
    db.add(upload)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await media_storage.delete(key)
        raise
    audit("image_uploaded", upload_id=upload.id, kind=kind, size_bytes=len(data))
    return upload


def public_url(upload: MediaUpload) -> str:
    return PUBLIC_PREFIX + upload.key.removeprefix("images/")


async def upload_image(db: AsyncSession, user: User, kind: str, content_type: str, data: bytes) -> MediaOut:
    """Profil, anı ve oda kapağı için yükleme. Cevaptaki adres ilgili forma yazılıp kaydedilir."""
    if kind not in PUBLIC_KINDS:
        raise AppError("Geçersiz yükleme türü.", code="invalid_upload_kind")
    upload = await store_image(db, user, kind, content_type, data)
    return MediaOut(id=upload.id, url=public_url(upload))


async def is_own_upload(db: AsyncSession, user_id: int, url: str | None, kinds: tuple[str, ...]) -> bool:
    """`url` bu kişinin yüklediği ve `kinds` türlerinden biri olan bir görsel mi?"""
    if not url or not url.startswith(PUBLIC_PREFIX):
        return False
    name = url.removeprefix(PUBLIC_PREFIX)
    if not PUBLIC_NAME.match(name):
        return False
    return await db.scalar(
        select(MediaUpload.id).where(
            MediaUpload.key == f"images/{name}", MediaUpload.owner_id == user_id, MediaUpload.kind.in_(kinds),
        )
    ) is not None


async def public_file(db: AsyncSession, name: str) -> tuple[str, str]:
    """Herkese açık görselin diskteki yolu ve türü. Sohbet fotoğrafları bu yoldan VERİLMEZ."""
    if not PUBLIC_NAME.match(name):
        raise NotFoundError("Görsel bulunamadı.")
    upload = await db.scalar(select(MediaUpload).where(MediaUpload.key == f"images/{name}"))
    if upload is None or upload.kind not in PUBLIC_KINDS:
        raise NotFoundError("Görsel bulunamadı.")
    path = media_storage.local_path(upload.key)
    if not path.is_file():
        raise NotFoundError("Görsel bulunamadı.")
    extension = name.rsplit(".", 1)[1]
    return str(path), {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[extension]


async def forget_public_uploads(db: AsyncSession, user_id: int) -> list[str]:
    """
    Hesap silinirken: kişinin profil, kapak, anı ve oda fotoğraflarının kayıtlarını siler (commit
    çağıranda) ve diskten silinecek anahtarları döner. Sohbet fotoğrafları karşı tarafın sohbetinin
    parçası olduğu için kalır (WhatsApp gibi).
    """
    rows = list(await db.scalars(select(MediaUpload).where(
        MediaUpload.owner_id == user_id, MediaUpload.kind.in_(PUBLIC_KINDS))))
    for row in rows:
        await db.delete(row)
    return [row.key for row in rows]


async def delete_files(keys: list[str]) -> None:
    for key in keys:
        await media_storage.delete(key)
