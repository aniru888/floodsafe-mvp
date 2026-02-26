"""FCM Push Notification Service.

Sends push notifications via Firebase Cloud Messaging.
Handles both web (VAPID) and native (Capacitor) tokens.
"""
import os
import json
import base64
import logging
import threading
from typing import Optional

from sqlalchemy.orm import Session

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (once at module load, thread-safe)
_firebase_app = None
_firebase_lock = threading.Lock()


def _get_firebase_app():
    """Lazy-init Firebase Admin SDK from base64-encoded service account.

    Uses double-checked locking to ensure thread safety during initialization
    while avoiding lock overhead on subsequent calls.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    with _firebase_lock:
        # Double-check after acquiring lock
        if _firebase_app is not None:
            return _firebase_app

        b64_creds = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64")
        if not b64_creds:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_B64 not set — push notifications disabled")
            return None

        try:
            creds_dict = json.loads(base64.b64decode(b64_creds))
            cred = credentials.Certificate(creds_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized for push notifications")
            return _firebase_app
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
            return None


async def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    click_url: Optional[str] = None,
) -> bool:
    """Send a push notification to a single device.

    Args:
        fcm_token: FCM device registration token
        title: Notification title
        body: Notification body text
        data: Optional data payload (key-value strings)
        click_url: Optional URL to open on notification click

    Returns:
        True if sent successfully, False otherwise
    """
    app = _get_firebase_app()
    if app is None:
        logger.warning("Firebase not initialized — skipping push notification")
        return False

    try:
        notification = messaging.Notification(title=title, body=body)

        web_push = None
        if click_url:
            web_push = messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(link=click_url)
            )

        message = messaging.Message(
            notification=notification,
            data=data or {},
            token=fcm_token,
            webpush=web_push,
        )

        response = messaging.send(message)
        logger.info(f"Push sent successfully: {response}")
        return True

    except messaging.UnregisteredError:
        logger.warning(f"FCM token expired/unregistered: {fcm_token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return False


async def send_push_to_user(
    db: Session,
    user,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Send push notification to a user, respecting preferences and handling stale tokens.

    Args:
        db: SQLAlchemy session (for clearing stale tokens)
        user: User ORM instance
        title: Notification title
        body: Notification body text
        data: Optional data payload (key-value strings)

    Returns:
        True if sent, False if skipped or failed
    """
    if not user.notification_push:
        return False

    if not user.fcm_token:
        return False

    result = await send_push_notification(
        fcm_token=user.fcm_token,
        title=title,
        body=body,
        data=data,
    )

    # If the token was unregistered, clear it from the DB
    if not result:
        # Check if the low-level function logged an UnregisteredError
        # Re-check by attempting to detect stale token scenario:
        # send_push_notification returns False for both UnregisteredError and other errors.
        # We clear the token on any failure — worst case, user re-registers on next app open.
        # The usePushNotifications hook re-registers tokens on every app open anyway.
        user.fcm_token = None
        user.fcm_token_updated_at = None
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.info(f"Cleared stale FCM token for user {user.id}")

    return result
