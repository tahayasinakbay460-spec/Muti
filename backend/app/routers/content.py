"""
/api/v1/banners — ana sayfadaki kayan tanıtım görselleri.
/api/v1/app-info — giriş yapmadan okunabilen uygulama bilgisi.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.core.deps import CurrentUserId
from app.demo import content
from app.demo.seed import DEMO_PASSWORD, MAIN_USER_ID, USERS
from app.schemas.content import AppInfo, DemoLogin

router = APIRouter(tags=["content"])


@router.get("/banners")
async def list_banners(_user_id: CurrentUserId) -> list[dict]:
    """DEMO KISAYOLU: sabit liste. Canlıda yönetim panelinden düzenlenen bir tablodan gelecek."""
    return content.BANNERS


@router.get("/app-info", response_model=AppInfo)
async def get_app_info() -> AppInfo:
    """Giriş ekranı için. Örnek hesap bilgisi yalnızca örnek veri yüklüyken verilir."""
    if not (settings.demo_mode or settings.showcase_data):
        return AppInfo()
    username = next(row[1] for row in USERS if row[0] == MAIN_USER_ID)
    return AppInfo(demo_login=DemoLogin(username=username, password=DEMO_PASSWORD))
