"""
Authentication Service for FloodSafe.
Handles Google OAuth, Phone Auth, and token management.
"""
from datetime import datetime, timedelta
from typing import Optional
import httpx

from sqlalchemy.orm import Session

from src.infrastructure.models import User, RefreshToken
from src.core.config import settings
from src.core.phone_utils import normalize_phone
from .security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_token,
    get_token_expiry
)


class AuthService:
    """Service for handling all authentication operations"""

    # =========================================================================
    # Google OAuth
    # =========================================================================

    async def verify_google_token(self, id_token: str) -> Optional[dict]:
        """
        Verify Google ID token with Google's servers.

        Args:
            id_token: The ID token from Google Sign-In

        Returns:
            Google user info if valid, None otherwise
        """
        try:
            # Verify token with Google
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
                )

                if response.status_code != 200:
                    return None

                token_info = response.json()

                # Verify the token is for our app
                if settings.GOOGLE_CLIENT_ID and token_info.get("aud") != settings.GOOGLE_CLIENT_ID:
                    return None

                return {
                    "google_id": token_info.get("sub"),
                    "email": token_info.get("email"),
                    "email_verified": token_info.get("email_verified") == "true",
                    "name": token_info.get("name"),
                    "picture": token_info.get("picture"),
                }

        except Exception as e:
            print(f"Google token verification error: {e}")
            return None

    def get_or_create_google_user(self, google_data: dict, db: Session) -> User:
        """
        Get existing user by Google ID or create a new one.

        Args:
            google_data: Verified Google user data
            db: Database session

        Returns:
            User instance
        """
        # Try to find by google_id first
        user = db.query(User).filter(User.google_id == google_data["google_id"]).first()

        if user:
            # Update profile photo if changed
            if google_data.get("picture") and user.profile_photo_url != google_data["picture"]:
                user.profile_photo_url = google_data["picture"]
                user.updated_at = datetime.utcnow()
                db.commit()
            return user

        # Try to find by email (user might have signed up differently before)
        user = db.query(User).filter(User.email == google_data["email"]).first()

        if user:
            # Link Google account to existing user
            user.google_id = google_data["google_id"]
            user.auth_provider = "google"
            if google_data.get("picture"):
                user.profile_photo_url = google_data["picture"]
            user.updated_at = datetime.utcnow()
            db.commit()
            return user

        # Create new user
        username = self._generate_unique_username(google_data.get("name", "user"), db)

        user = User(
            username=username,
            email=google_data["email"],
            google_id=google_data["google_id"],
            auth_provider="google",
            profile_photo_url=google_data.get("picture"),
            # Initialize onboarding state for new users
            profile_complete=False,
            onboarding_step=1,
            city_preference=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    # =========================================================================
    # Phone Authentication
    # =========================================================================

    async def verify_firebase_phone_token(self, id_token: str) -> Optional[dict]:
        """
        Verify Firebase Phone Auth ID token.

        Args:
            id_token: The ID token from Firebase Phone Auth

        Returns:
            Phone auth info if valid, None otherwise
        """
        try:
            # Verify with Firebase (using REST API for simplicity)
            async with httpx.AsyncClient() as client:
                # Firebase token verification endpoint
                response = await client.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:lookup",
                    params={"key": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else {},
                    json={"idToken": id_token}
                )

                if response.status_code != 200:
                    # Fallback: decode the token ourselves for development
                    # In production, always verify with Firebase
                    return self._decode_firebase_token_dev(id_token)

                data = response.json()
                users = data.get("users", [])

                if not users:
                    return None

                user_data = users[0]
                phone = user_data.get("phoneNumber")

                if not phone:
                    return None

                return {
                    "phone": phone,
                    "firebase_uid": user_data.get("localId"),
                }

        except Exception as e:
            print(f"Firebase token verification error: {e}")
            return None

    def _decode_firebase_token_dev(self, id_token: str) -> Optional[dict]:
        """
        Development fallback: Extract phone from Firebase token.
        WARNING: Only use in development. Production must verify with Firebase.
        """
        try:
            # Decode without verification (DEV ONLY)
            import base64
            import json

            parts = id_token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload
            payload = parts[1]
            # Add padding
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)

            phone = data.get("phone_number")
            if phone:
                return {
                    "phone": phone,
                    "firebase_uid": data.get("user_id") or data.get("sub"),
                }
            return None

        except Exception:
            return None

    def get_or_create_phone_user(self, phone: str, db: Session) -> User:
        """
        Get existing user by phone or create a new one.

        Args:
            phone: Verified phone number
            db: Database session

        Returns:
            User instance
        """
        # Normalize before query/store to ensure consistent E.164 format
        phone = normalize_phone(phone)

        # Try to find by phone
        user = db.query(User).filter(User.phone == phone).first()

        if user:
            # Mark phone as verified
            if not user.phone_verified:
                user.phone_verified = True
                user.updated_at = datetime.utcnow()
                db.commit()
            return user

        # Create new user
        username = self._generate_unique_username(f"user_{phone[-4:]}", db)

        user = User(
            username=username,
            phone=phone,
            phone_verified=True,
            auth_provider="phone",
            # Initialize onboarding state for new users
            profile_complete=False,
            onboarding_step=1,
            city_preference=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    # =========================================================================
    # Email/Password Authentication
    # =========================================================================

    def register_email_user(
        self,
        email: str,
        password: str,
        username: Optional[str],
        db: Session
    ) -> User:
        """
        Register a new user with email and password.

        Args:
            email: User's email address
            password: Plaintext password (will be hashed)
            username: Optional username (generated if not provided)
            db: Database session

        Returns:
            Created User instance

        Raises:
            ValueError: If email is already registered
        """
        from .security import hash_password

        # Normalize email
        email = email.lower().strip()

        # Check if email already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("Email already registered")

        # Generate username if not provided
        if not username:
            username = self._generate_unique_username(email.split('@')[0], db)

        # Create user with hashed password
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            auth_provider="local",
            # Initialize onboarding state for new users
            profile_complete=False,
            onboarding_step=1,
            city_preference=None,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    def authenticate_email_user(
        self,
        email: str,
        password: str,
        db: Session
    ) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            email: User's email address
            password: Plaintext password to verify
            db: Database session

        Returns:
            User instance if authentication successful, None otherwise
        """
        from .security import verify_password

        # Normalize email
        email = email.lower().strip()

        # Find user by email
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return None

        # User must have a password_hash (not OAuth/Phone only user)
        if not user.password_hash:
            return None

        # Verify password
        if not verify_password(password, user.password_hash):
            return None

        return user

    # =========================================================================
    # Token Management
    # =========================================================================

    def create_tokens(self, user: User, db: Session) -> dict:
        """
        Create access and refresh tokens for a user.

        Args:
            user: The authenticated user
            db: Database session

        Returns:
            Dict with access_token, refresh_token, token_type, and expires_in
        """
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})

        # Create refresh token
        refresh_token, token_hash = create_refresh_token(str(user.id))

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Store refresh token hash in database
        db_token = RefreshToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=expires_at,
        )
        db.add(db_token)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
        }

    def refresh_tokens(self, refresh_token: str, db: Session) -> Optional[dict]:
        """
        Exchange a refresh token for new tokens (with rotation).

        Args:
            refresh_token: The refresh token to exchange
            db: Database session

        Returns:
            New tokens dict or None if invalid
        """
        # Verify the refresh token
        payload = verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        # Find the token in database
        token_hash = hash_token(refresh_token)
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False
        ).first()

        if not db_token:
            return None

        # Check if expired
        if db_token.expires_at < datetime.utcnow():
            db_token.revoked = True
            db.commit()
            return None

        # Revoke the old token (rotation)
        db_token.revoked = True

        # Get the user
        user = db.query(User).filter(User.id == db_token.user_id).first()
        if not user:
            db.commit()
            return None

        # Create new tokens
        new_tokens = self.create_tokens(user, db)

        db.commit()

        return new_tokens

    def revoke_refresh_token(self, refresh_token: str, db: Session) -> bool:
        """
        Revoke a refresh token (logout).

        Args:
            refresh_token: The token to revoke
            db: Database session

        Returns:
            True if revoked, False if not found
        """
        token_hash = hash_token(refresh_token)

        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if not db_token:
            return False

        db_token.revoked = True
        db.commit()

        return True

    def revoke_all_user_tokens(self, user_id: str, db: Session) -> int:
        """
        Revoke all refresh tokens for a user (logout all devices).

        Args:
            user_id: The user's ID
            db: Database session

        Returns:
            Number of tokens revoked
        """
        result = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})

        db.commit()

        return result

    # =========================================================================
    # Helpers
    # =========================================================================

    def _generate_unique_username(self, base_name: str, db: Session) -> str:
        """Generate a unique username from a base name."""
        # Clean the base name
        clean_name = "".join(c for c in base_name if c.isalnum() or c == "_").lower()
        if not clean_name:
            clean_name = "user"

        # Check if it's unique
        username = clean_name
        counter = 1

        while db.query(User).filter(User.username == username).first():
            username = f"{clean_name}_{counter}"
            counter += 1

        return username


# Singleton instance
auth_service = AuthService()
