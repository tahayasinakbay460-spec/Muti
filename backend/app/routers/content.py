"""
/api/v1/app-info — giriş yapmadan okunabilen uygulama bilgisi.
"""
from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DbSession
from app.demo.seed import DEMO_PASSWORD, MAIN_USER_ID, USERS
from app.models import User
from app.schemas.content import AppInfo, DemoLogin

router = APIRouter(tags=["content"])


@router.get("/app-info", response_model=AppInfo)
async def get_app_info(db: DbSession) -> AppInfo:
    """
    Giriş ekranı ve genel ayarlar. Örnek hesap bilgisi yalnızca örnek veri yüklüyken verilir.
    `support_user_id`: "Müşteri hizmetlerine yaz" tuşunun sohbet açacağı hesap.
    """
    support_name = (settings.support_username or settings.admin_username or ("admin" if settings.demo_mode else "")).lower()
    support_id = await db.scalar(select(User.id).where(User.username == support_name, User.is_active)) if support_name else None
    if not (settings.demo_mode or settings.showcase_data):
        return AppInfo(support_user_id=support_id)
    username = next(row[1] for row in USERS if row[0] == MAIN_USER_ID)
    return AppInfo(demo_login=DemoLogin(username=username, password=DEMO_PASSWORD), support_user_id=support_id)
