"""
/api/v1/app-info — giriş yapmadan okunabilen uygulama bilgisi.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.demo.seed import DEMO_PASSWORD, MAIN_USER_ID, USERS
from app.schemas.content import AppInfo, DemoLogin

router = APIRouter(tags=["content"])


@router.get("/app-info", response_model=AppInfo)
async def get_app_info() -> AppInfo:
    """Giriş ekranı için. Örnek hesap bilgisi yalnızca örnek veri yüklüyken verilir."""
    if not (settings.demo_mode or settings.showcase_data):
        return AppInfo()
    username = next(row[1] for row in USERS if row[0] == MAIN_USER_ID)
    return AppInfo(demo_login=DemoLogin(username=username, password=DEMO_PASSWORD))
