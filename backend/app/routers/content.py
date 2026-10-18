"""
/api/v1/banners — ana sayfadaki kayan tanıtım görselleri.
"""
from fastapi import APIRouter

from app.core.deps import CurrentUserId
from app.demo import content

router = APIRouter(tags=["content"])


@router.get("/banners")
async def list_banners(_user_id: CurrentUserId) -> list[dict]:
    """DEMO KISAYOLU: sabit liste. Canlıda yönetim panelinden düzenlenen bir tablodan gelecek."""
    return content.BANNERS
