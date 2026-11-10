"""
/api/v1/hosts — yayıncı olma başvurusu (bkz. services/host_service.py). Onay/ret panelde (/admin/host-applications).
"""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.host import HostApplyRequest, HostStatus
from app.services import host_service

router = APIRouter(prefix="/hosts", tags=["hosts"])


@router.get("/me", response_model=HostStatus)
async def my_status(user: CurrentUser, db: DbSession):
    """Yayıncı mıyım, başvurum ne durumda, başvurabilir miyim?"""
    return await host_service.status(db, user)


@router.post("/apply", response_model=HostStatus)
async def apply(data: HostApplyRequest, user: CurrentUser, db: DbSession):
    """Yayıncı olmak için başvurur (18 yaş üstü; panelde moderatör onaylar)."""
    return await host_service.apply(db, user, data)
