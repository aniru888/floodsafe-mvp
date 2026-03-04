"""
Verification Service for FloodSafe

Handles email verification token generation, validation, and rate limiting.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.core.config import settings
from src.infrastructure.models import User, EmailVerificationToken, PasswordResetToken
from src.domain.services.security import hash_token


class VerificationService:
    """
    Manages email verification tokens and state.

    Token Security:
    - Tokens are random 32-byte URL-safe strings (cryptographically secure)
    - Only the hash is stored in the database
    - Tokens expire after 24 hours (configurable)
    - Tokens are single-use (marked as used after verification)
    """

    def create_email_verification_token(
        self,
        user_id: UUID,
        db: Session
    ) -> str:
        """
        Generate a new email verification token for a user.

        Args:
            user_id: The user's UUID
            db: Database session

        Returns:
            Raw verification token (to be sent to user via email)
        """
        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)

        # Hash for storage
        token_hash = hash_token(raw_token)

        # Calculate expiry
        expires_at = datetime.utcnow() + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)

        # Create token record
        token_record = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        db.add(token_record)
        db.commit()

        return raw_token

    def verify_email_token(
        self,
        token: str,
        db: Session
    ) -> tuple[bool, Optional[User], str]:
        """
        Validate a verification token and mark email as verified.

        Args:
            token: Raw verification token from email link
            db: Database session

        Returns:
            Tuple of (success, user, message)
            - success: True if verification succeeded
            - user: The verified User object (or None on failure)
            - message: Human-readable message about the result
        """
        # Hash the provided token
        token_hash = hash_token(token)

        # Look up token record
        token_record = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == token_hash
        ).first()

        if not token_record:
            return False, None, "Invalid verification link. Please request a new one."

        # Get the user
        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            return False, None, "User not found."

        # Check if already verified
        if user.email_verified:
            return True, user, "Email already verified."

        # Check if token was already used
        if token_record.used_at is not None:
            return False, None, "This verification link has already been used."

        # Check if token has expired
        if token_record.expires_at < datetime.utcnow():
            return False, None, "Verification link has expired. Please request a new one."

        # Mark token as used
        token_record.used_at = datetime.utcnow()

        # Mark user email as verified
        user.email_verified = True

        db.commit()

        return True, user, "Email verified successfully!"

    def can_resend_verification(
        self,
        user_id: UUID,
        db: Session,
        max_per_hour: int = 3
    ) -> tuple[bool, str]:
        """
        Check if user can request another verification email (rate limiting).

        Args:
            user_id: The user's UUID
            db: Database session
            max_per_hour: Maximum verification emails per hour (default 3)

        Returns:
            Tuple of (allowed, message)
        """
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        # Count recent tokens for this user
        recent_count = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.created_at > one_hour_ago
        ).count()

        if recent_count >= max_per_hour:
            return False, f"Too many verification emails. Please try again in an hour."

        return True, "OK"

    def get_verification_status(
        self,
        user: User
    ) -> dict:
        """
        Get the verification status for a user.

        Args:
            user: The User object

        Returns:
            Dict with email_verified and phone_verified status
        """
        return {
            "email_verified": user.email_verified,
            "phone_verified": user.phone_verified,
            "auth_provider": user.auth_provider,
        }

    def cleanup_expired_tokens(self, db: Session) -> int:
        """
        Remove expired tokens from the database.
        Can be run periodically as a cleanup job.

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        result = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return result

    # =========================================================================
    # Password Reset
    # =========================================================================

    def create_password_reset_token(self, user_id: UUID, db: Session) -> str:
        """Generate a single-use password reset token (1 hour expiry)."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        token_record = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(token_record)
        db.commit()
        return raw_token

    def validate_password_reset_token(
        self, token: str, db: Session
    ) -> tuple[bool, Optional[User], str]:
        """
        Validate a password reset token.

        Returns:
            Tuple of (success, user, message)
        """
        token_hash = hash_token(token)
        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash
        ).first()

        if not token_record:
            return False, None, "Invalid or expired reset link."

        if token_record.used_at is not None:
            return False, None, "This reset link has already been used."

        if token_record.expires_at < datetime.utcnow():
            return False, None, "Reset link has expired. Please request a new one."

        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            return False, None, "User not found."

        # Mark token as used
        token_record.used_at = datetime.utcnow()
        db.flush()

        return True, user, "Token valid."

    def can_request_password_reset(
        self, user_id: UUID, db: Session, max_per_hour: int = 3
    ) -> tuple[bool, str]:
        """Rate limit password reset requests: max 3 per hour."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.created_at > one_hour_ago,
        ).count()

        if recent_count >= max_per_hour:
            return False, "Too many reset requests. Please try again in an hour."
        return True, "OK"


# Singleton instance
verification_service = VerificationService()
