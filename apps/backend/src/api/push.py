"""Push notification endpoints — FCM token registration."""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from .deps import get_current_user
from ..infrastructure.models import User

router = APIRouter(prefix="/push", tags=["push"])


class FCMTokenRequest(BaseModel):
    token: str


@router.post("/register-token")
async def register_fcm_token(
    request: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store or update FCM device token for the authenticated user."""
    current_user.fcm_token = request.token
    current_user.fcm_token_updated_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "message": "FCM token registered"}


@router.delete("/register-token")
async def unregister_fcm_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove FCM token (e.g., on logout)."""
    current_user.fcm_token = None
    current_user.fcm_token_updated_at = None
    db.commit()
    return {"status": "ok", "message": "FCM token removed"}
