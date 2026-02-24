"""Push notification endpoints — FCM token registration."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..infrastructure.database import get_db
from .deps import get_current_user
from ..infrastructure.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["push"])


class FCMTokenRequest(BaseModel):
    token: str = Field(min_length=50, max_length=500)


@router.post("/register-token")
async def register_fcm_token(
    request: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store or update FCM device token for the authenticated user."""
    try:
        current_user.fcm_token = request.token
        current_user.fcm_token_updated_at = datetime.utcnow()
        db.commit()
        return {"status": "ok", "message": "FCM token registered"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to register FCM token for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to register push token")


@router.delete("/register-token")
async def unregister_fcm_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove FCM token (e.g., on logout)."""
    try:
        current_user.fcm_token = None
        current_user.fcm_token_updated_at = None
        db.commit()
        return {"status": "ok", "message": "FCM token removed"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to unregister FCM token for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to unregister push token")
