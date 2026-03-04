"""
Authentication API endpoints for FloodSafe.
Handles Google OAuth, Phone Auth, Email/Password, and token management.
"""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.infrastructure.models import User
from src.domain.services.auth_service import auth_service
from src.domain.services.email_service import email_service
from src.domain.services.verification_service import verification_service
from src.core.config import settings
from .deps import get_current_user, check_rate_limit


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class GoogleAuthRequest(BaseModel):
    """Request for Google OAuth authentication"""
    id_token: str = Field(..., description="Google ID token from client-side sign-in")


class PhoneAuthRequest(BaseModel):
    """Request for Firebase Phone authentication"""
    id_token: str = Field(..., description="Firebase ID token from phone auth")


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token"""
    refresh_token: str = Field(..., description="Refresh token")


class LogoutRequest(BaseModel):
    """Request to logout (revoke refresh token)"""
    refresh_token: str = Field(..., description="Refresh token to revoke")


class TokenResponse(BaseModel):
    """Response containing auth tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """User profile response"""
    id: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    auth_provider: str
    profile_photo_url: Optional[str] = None
    points: int
    level: int
    reputation_score: int

    # Verification status
    email_verified: bool = False
    phone_verified: bool = False

    # Onboarding & City Preference
    city_preference: Optional[str] = None
    profile_complete: bool = False
    onboarding_step: Optional[int] = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str


# =============================================================================
# Google OAuth Endpoints
# =============================================================================

@router.post("/google", response_model=TokenResponse, tags=["authentication"])
async def google_auth(
    request: GoogleAuthRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate with Google OAuth.

    Exchange a Google ID token (from client-side Google Sign-In) for
    FloodSafe JWT tokens.

    Returns access and refresh tokens for authenticated requests.

    Rate limited to 10 attempts per minute per IP address.
    """
    # Rate limit: 10 OAuth attempts per minute per IP (more lenient for OAuth)
    client_ip = http_request.client.host if http_request.client else "unknown"
    check_rate_limit(f"google:{client_ip}", max_requests=10, window_seconds=60)

    # Verify Google token
    google_data = await auth_service.verify_google_token(request.id_token)

    if not google_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )

    # Get or create user
    user = auth_service.get_or_create_google_user(google_data, db)

    # Create tokens
    tokens = auth_service.create_tokens(user, db)

    return TokenResponse(**tokens)


# =============================================================================
# Phone Authentication Endpoints
# =============================================================================

@router.post("/phone/verify", response_model=TokenResponse, tags=["authentication"])
async def phone_auth(
    request: PhoneAuthRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate with Firebase Phone Auth.

    Exchange a Firebase ID token (from phone OTP verification) for
    FloodSafe JWT tokens.

    The client should:
    1. Use Firebase SDK to send OTP to phone
    2. Verify the OTP with Firebase
    3. Get the ID token from Firebase
    4. Send the ID token to this endpoint

    Returns access and refresh tokens for authenticated requests.

    Rate limited to 5 attempts per minute per IP address.
    """
    # Rate limit: 5 phone auth attempts per minute per IP
    client_ip = http_request.client.host if http_request.client else "unknown"
    check_rate_limit(f"phone:{client_ip}", max_requests=5, window_seconds=60)

    # Verify Firebase token
    phone_data = await auth_service.verify_firebase_phone_token(request.id_token)

    if not phone_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone verification token"
        )

    # Get or create user
    user = auth_service.get_or_create_phone_user(phone_data["phone"], db)

    # Create tokens
    tokens = auth_service.create_tokens(user, db)

    return TokenResponse(**tokens)


# =============================================================================
# Email/Password Authentication Endpoints
# =============================================================================

COMMON_PASSWORDS = {
    "password", "12345678", "123456789", "1234567890", "qwerty123",
    "password1", "iloveyou", "admin123", "welcome1", "monkey123",
}


class EmailRegisterRequest(BaseModel):
    """Request for email/password registration"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Optional username")

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if v.lower() in COMMON_PASSWORDS:
            raise ValueError("This password is too common. Please choose a stronger password.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'~/`]', v):
            raise ValueError("Password must contain at least one special character.")
        return v


class EmailLoginRequest(BaseModel):
    """Request for email/password login"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Password")


@router.post("/register/email", response_model=TokenResponse, tags=["authentication"])
async def register_email(
    request: EmailRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new user with email and password.

    Creates a new user account, sends a verification email, and returns JWT tokens.
    Password must be at least 8 characters.

    The user can use the app immediately but will see a verification reminder
    until they click the link in their email.

    Returns access and refresh tokens for authenticated requests.
    """
    # Basic email validation
    email = request.email.lower().strip()
    if '@' not in email or '.' not in email.split('@')[1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    try:
        user = auth_service.register_email_user(
            email=email,
            password=request.password,
            username=request.username,
            db=db
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Generate verification token and send email (async in background)
    token = verification_service.create_email_verification_token(user.id, db)
    background_tasks.add_task(
        email_service.send_verification_email,
        user.email,
        token,
        user.username
    )

    # Create tokens - user can use app immediately
    tokens = auth_service.create_tokens(user, db)

    return TokenResponse(**tokens)


@router.post("/login/email", response_model=TokenResponse, tags=["authentication"])
async def login_email(
    request: EmailLoginRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate with email and password.

    Exchange email/password credentials for JWT tokens.

    Returns access and refresh tokens for authenticated requests.

    Rate limited to 5 attempts per minute per IP address.
    """
    # Rate limit: 5 login attempts per minute per IP
    client_ip = http_request.client.host if http_request.client else "unknown"
    check_rate_limit(f"login:{client_ip}", max_requests=5, window_seconds=60)

    user = auth_service.authenticate_email_user(
        email=request.email,
        password=request.password,
        db=db
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Enforce email verification for email/password users
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for a verification link.",
            headers={"X-Verification-Required": "true"},
        )

    # Create tokens
    tokens = auth_service.create_tokens(user, db)

    return TokenResponse(**tokens)


# =============================================================================
# Token Management Endpoints
# =============================================================================

@router.post("/refresh", response_model=TokenResponse, tags=["authentication"])
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token.

    Exchange a valid refresh token for new access and refresh tokens.
    The old refresh token is revoked (token rotation for security).

    Call this endpoint when the access token expires.
    """
    tokens = auth_service.refresh_tokens(request.refresh_token, db)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    return TokenResponse(**tokens)


@router.post("/logout", response_model=MessageResponse, tags=["authentication"])
async def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db)
):
    """
    Logout and revoke refresh token.

    Revokes the provided refresh token so it can no longer be used.
    The client should also clear local token storage.
    """
    success = auth_service.revoke_refresh_token(request.refresh_token, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token not found or already revoked"
        )

    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse, tags=["authentication"])
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout from all devices.

    Revokes all refresh tokens for the current user.
    Requires authentication.
    """
    count = auth_service.revoke_all_user_tokens(str(current_user.id), db)

    return MessageResponse(message=f"Logged out from {count} session(s)")


# =============================================================================
# User Profile Endpoints
# =============================================================================

@router.get("/me", response_model=UserResponse, tags=["authentication"])
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile.

    Returns the profile of the currently authenticated user.
    Requires a valid access token.
    """
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        auth_provider=current_user.auth_provider or "local",
        profile_photo_url=current_user.profile_photo_url,
        points=current_user.points,
        level=current_user.level,
        reputation_score=current_user.reputation_score,
        email_verified=current_user.email_verified,
        phone_verified=current_user.phone_verified,
        city_preference=current_user.city_preference,
        profile_complete=current_user.profile_complete,
        onboarding_step=current_user.onboarding_step,
    )


@router.get("/check", tags=["authentication"])
async def check_auth(
    current_user: User = Depends(get_current_user)
):
    """
    Check if the current token is valid.

    Simple endpoint to verify authentication status.
    Returns 200 if authenticated, 401 if not.
    """
    return {"authenticated": True, "user_id": str(current_user.id)}


# =============================================================================
# Email Verification Endpoints
# =============================================================================

class VerificationStatusResponse(BaseModel):
    """Response for verification status"""
    email_verified: bool
    phone_verified: bool
    auth_provider: str


@router.get("/verify-email", tags=["authentication"])
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Verify email address via link click.

    This endpoint is called when a user clicks the verification link in their email.
    It validates the token, marks the email as verified, and redirects to the frontend.

    Query Parameters:
        token: The verification token from the email link

    Returns:
        Redirect to frontend success or error page
    """
    success, user, message = verification_service.verify_email_token(token, db)

    if success:
        # Redirect to success page
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/email-verified?success=true",
            status_code=status.HTTP_302_FOUND
        )
    else:
        # Redirect to error page with message
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/email-verified?success=false&message={encoded_message}",
            status_code=status.HTTP_302_FOUND
        )


@router.post("/resend-verification", response_model=MessageResponse, tags=["authentication"])
async def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resend verification email.

    Sends a new verification email to the current user.
    Rate limited to 3 emails per hour.

    Requires authentication.

    Returns:
        Message indicating success or failure
    """
    # Check if already verified
    if current_user.email_verified:
        return MessageResponse(message="Email already verified")

    # Check if user has an email (phone-only users don't)
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address associated with this account"
        )

    # Check rate limit
    can_resend, rate_message = verification_service.can_resend_verification(
        current_user.id, db
    )
    if not can_resend:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_message
        )

    # Generate new token and send email
    token = verification_service.create_email_verification_token(current_user.id, db)
    background_tasks.add_task(
        email_service.send_verification_email,
        current_user.email,
        token,
        current_user.username
    )

    return MessageResponse(message="Verification email sent")


@router.get("/verification-status", response_model=VerificationStatusResponse, tags=["authentication"])
async def get_verification_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current verification status.

    Returns the email and phone verification status for the current user.
    Used by the frontend to poll for verification completion.

    Requires authentication.

    Returns:
        email_verified: Whether email is verified
        phone_verified: Whether phone is verified
        auth_provider: The authentication provider used
    """
    status_data = verification_service.get_verification_status(current_user)
    return VerificationStatusResponse(**status_data)


# =============================================================================
# Password Reset Endpoints
# =============================================================================

class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset"""
    email: str = Field(..., description="Email address of the account")


class ResetPasswordRequest(BaseModel):
    """Request to set a new password with a reset token"""
    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if v.lower() in COMMON_PASSWORDS:
            raise ValueError("This password is too common. Please choose a stronger password.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'~/`]', v):
            raise ValueError("Password must contain at least one special character.")
        return v


@router.post("/forgot-password", response_model=MessageResponse, tags=["authentication"])
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request a password reset email.

    Always returns success (even if email not found) to prevent email enumeration.
    Rate limited to 5 requests per minute per IP.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    check_rate_limit(f"forgot-password:{client_ip}", max_requests=5, window_seconds=60)

    email = request.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if user and user.password_hash:
        # Only send for email/password users (not OAuth/phone-only)
        can_send, _ = verification_service.can_request_password_reset(user.id, db)
        if can_send:
            token = verification_service.create_password_reset_token(user.id, db)
            background_tasks.add_task(
                email_service.send_password_reset_email,
                user.email,
                token,
                user.username
            )

    # Always return success to prevent email enumeration
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse, tags=["authentication"])
async def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Reset password using a valid reset token.

    Validates the token, sets the new password, and revokes all existing sessions.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    check_rate_limit(f"reset-password:{client_ip}", max_requests=5, window_seconds=60)

    success, user, message = verification_service.validate_password_reset_token(
        request.token, db
    )

    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # Set new password
    from src.domain.services.security import hash_password
    user.password_hash = hash_password(request.new_password)

    # Revoke all existing sessions for security
    auth_service.revoke_all_user_tokens(str(user.id), db)

    db.commit()

    return MessageResponse(message="Password reset successfully. Please log in with your new password.")
