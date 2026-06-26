from fastapi import APIRouter, Depends
from app.models import User
from app.runtime_config import access_settings, save_access_settings
from app.schemas.api import AccessSettingsIn, AccessSettingsOut
from app.services.auth_service import require_admin

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/access", response_model=AccessSettingsOut)
def get_access_settings(admin: User = Depends(require_admin)):
    return access_settings()


@router.patch("/access", response_model=AccessSettingsOut)
def update_access_settings(data: AccessSettingsIn, admin: User = Depends(require_admin)):
    return save_access_settings(data.model_dump(exclude_unset=True))
