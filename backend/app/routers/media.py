"""
/api/v1/media — fotoğraf yükleme ve herkese açık görselleri verme (bkz. services/media_service.py).
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.uploads import read_limited_body
from app.schemas.media import MediaOut
from app.services import media_service

router = APIRouter(prefix="/media", tags=["media"])


@router.post("", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    kind: Annotated[Literal["avatar", "cover", "moment", "room_cover"], Query()],
    content_type: Annotated[str, Header()] = "",
):
    """
    Fotoğraf yükler. Gövde dosyanın kendisidir (form değil), türü `Content-Type` başlığında.
    Cevaptaki `url` profil / anı / oda formunda gönderilir.
    """
    data = await read_limited_body(request, settings.image_max_bytes, "Fotoğraf çok büyük.", "image_too_large")
    return await media_service.upload_image(db, user, kind, content_type, data)


@router.get("/images/{name}")
async def get_image(name: str, db: DbSession):
    """
    Herkese açık görsel (profil, anı, oda kapağı). Token istemez: `<img>` etiketi başlık gönderemez.
    Adı rastgele ve değişmez olduğu için tarayıcı bir yıl önbellekte tutabilir.
    """
    path, media_type = await media_service.public_file(db, name)
    return FileResponse(path, media_type=media_type, headers={
        "Cache-Control": "public, max-age=31536000, immutable",
        # Tarayıcı dosyayı bildirdiğimiz türden başka bir şey sanıp çalıştırmasın
        "X-Content-Type-Options": "nosniff",
    })
