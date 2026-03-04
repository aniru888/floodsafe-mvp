"""
Authentication dependencies for FastAPI routes.
Provides dependency injection for protected endpoints.
"""
from typing import Optional
from collections import OrderedDict
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure.models import User
from src.domain.services.security import verify_token


# =============================================================================
# Rate Limiting
# =============================================================================

# In-memory rate limit store: key -> list of timestamps (LRU-bounded, max 10K keys)
_RATE_LIMIT_MAX_KEYS = 10_000
_rate_limit_store: OrderedDict[str, list[datetime]] = OrderedDict()


def check_rate_limit(
    key: str,
    max_requests: int = 5,
    window_seconds: int = 60
) -> None:
    """
    Simple in-memory rate limiter.

    Tracks requests per key (e.g., IP address) within a sliding window.
    Raises HTTP 429 if rate limit exceeded.

    Args:
        key: Unique identifier for rate limiting (e.g., "login:192.168.1.1")
        max_requests: Maximum allowed requests in the window
        window_seconds: Time window in seconds

    Raises:
        HTTPException: 429 Too Many Requests if limit exceeded

    Usage:
        @router.post("/login")
        async def login(request: Request, ...):
            check_rate_limit(f"login:{request.client.host}")
            ...
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    # Get existing timestamps for this key (empty list if new)
    timestamps = _rate_limit_store.get(key, [])

    # Clean old entries outside the window
    timestamps = [t for t in timestamps if t > cutoff]

    # Check if limit exceeded
    if len(timestamps) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {window_seconds} seconds before trying again.",
        )

    # Record this request and move key to end (most recently used)
    timestamps.append(now)
    _rate_limit_store[key] = timestamps
    _rate_limit_store.move_to_end(key)

    # Evict oldest keys if over capacity
    while len(_rate_limit_store) > _RATE_LIMIT_MAX_KEYS:
        _rate_limit_store.popitem(last=False)


# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    Raises 401 if not authenticated.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": str(user.id)}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Verify the access token
    payload = verify_token(token, token_type="access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current authenticated user.
    Returns None if not authenticated (does not raise).

    Usage:
        @router.get("/public")
        async def public_route(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.username}"}
            return {"message": "Hello guest"}
    """
    if not credentials:
        return None

    token = credentials.credentials

    # Verify the access token
    payload = verify_token(token, token_type="access")

    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current user and verify they are an admin.
    Raises 403 if not an admin.

    Usage:
        @router.delete("/admin/user/{user_id}")
        async def delete_user(admin: User = Depends(get_current_admin_user)):
            ...
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to verify user has verified_reporter, moderator, or admin role.
    Raises 403 if not a verified user.

    Usage:
        @router.post("/trusted-action")
        async def trusted_action(user: User = Depends(get_current_verified_user)):
            ...
    """
    if current_user.role not in ["verified_reporter", "moderator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified reporter access required",
        )

    return current_user


async def get_current_moderator(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to verify user has moderator or admin role.
    Raises 403 if not a moderator.

    Usage:
        @router.post("/moderate/report")
        async def moderate_report(user: User = Depends(get_current_moderator)):
            ...
    """
    if current_user.role not in ["moderator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required",
        )

    return current_user
