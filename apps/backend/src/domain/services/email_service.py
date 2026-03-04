"""
Email Service for FloodSafe

Handles sending verification emails using SendGrid.
Falls back to console logging if SendGrid is not configured.
"""
import logging
from typing import Optional

from src.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service using SendGrid for sending verification emails.
    Falls back to console logging if SENDGRID_API_KEY is not set.
    """

    def __init__(self):
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Lazy initialization of SendGrid client."""
        if not self._initialized:
            self._initialized = True
            if settings.SENDGRID_API_KEY:
                try:
                    from sendgrid import SendGridAPIClient
                    self._client = SendGridAPIClient(settings.SENDGRID_API_KEY)
                    logger.info("SendGrid client initialized")
                except ImportError:
                    logger.warning("sendgrid package not installed, using mock mode")
                except Exception as e:
                    logger.error(f"Failed to initialize SendGrid: {e}")
            else:
                logger.warning("SENDGRID_API_KEY not set, using mock email mode")
        return self._client

    async def send_verification_email(
        self,
        email: str,
        token: str,
        username: str
    ) -> bool:
        """
        Send email verification link to user.

        Args:
            email: User's email address
            token: Raw verification token (not hashed)
            username: User's display name

        Returns:
            True if email sent successfully, False otherwise
        """
        verification_link = self._build_verification_link(token)

        client = self._get_client()
        if not client:
            # Mock mode - log to console
            print(f"\n{'='*60}")
            print("[EMAIL] MOCK MODE - Verification email")
            print(f"{'='*60}")
            print(f"To: {email}")
            print(f"Subject: Verify your FloodSafe email")
            print(f"Username: {username}")
            print(f"Verification Link: {verification_link}")
            print(f"{'='*60}\n")
            return True

        # Real SendGrid mode
        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content

            message = Mail(
                from_email=Email(
                    settings.SENDGRID_FROM_EMAIL,
                    settings.SENDGRID_FROM_NAME
                ),
                to_emails=To(email),
                subject="Verify your FloodSafe email",
                html_content=self._build_verification_html(username, verification_link)
            )

            response = client.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Verification email sent to {email}")
                return True
            else:
                logger.warning(f"SendGrid returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    async def send_password_reset_email(
        self,
        email: str,
        token: str,
        username: str
    ) -> bool:
        """Send password reset link to user."""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        client = self._get_client()
        if not client:
            print(f"\n{'='*60}")
            print("[EMAIL] MOCK MODE - Password reset email")
            print(f"{'='*60}")
            print(f"To: {email}")
            print(f"Subject: Reset your FloodSafe password")
            print(f"Reset Link: {reset_link}")
            print(f"{'='*60}\n")
            return True

        try:
            from sendgrid.helpers.mail import Mail, Email, To

            message = Mail(
                from_email=Email(
                    settings.SENDGRID_FROM_EMAIL,
                    settings.SENDGRID_FROM_NAME
                ),
                to_emails=To(email),
                subject="Reset your FloodSafe password",
                html_content=self._build_reset_html(username or "User", reset_link)
            )

            response = client.send(message)
            if response.status_code in (200, 201, 202):
                logger.info(f"Password reset email sent to {email}")
                return True
            else:
                logger.warning(f"SendGrid returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending reset email: {e}")
            return False

    def _build_reset_html(self, username: str, reset_link: str) -> str:
        """Build HTML for password reset email."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">FloodSafe</h1>
                <p style="color: rgba(255,255,255,0.9); margin-top: 10px;">Password Reset</p>
            </div>
            <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                <h2 style="color: #1f2937; margin-top: 0;">Hi {username},</h2>
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Reset Password</a>
                </div>
                <p style="color: #6b7280; font-size: 14px;">Or copy and paste this link:<br><a href="{reset_link}" style="color: #667eea; word-break: break-all;">{reset_link}</a></p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #6b7280; font-size: 12px;">This link expires in 1 hour. If you didn't request this, ignore this email — your password won't change.</p>
            </div>
        </body>
        </html>
        """

    def _build_verification_link(self, token: str) -> str:
        """Build the verification URL that users will click.

        Points to backend /api/auth/verify-email which validates the token
        and redirects to frontend /email-verified with success/error status.
        """
        return f"{settings.BACKEND_URL}/api/auth/verify-email?token={token}"

    def _build_verification_html(self, username: str, verification_link: str) -> str:
        """Build the HTML email content."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify your FloodSafe email</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🌊 FloodSafe</h1>
                <p style="color: rgba(255,255,255,0.9); margin-top: 10px;">Stay safe from floods</p>
            </div>

            <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                <h2 style="color: #1f2937; margin-top: 0;">Welcome, {username}!</h2>

                <p>Thanks for signing up for FloodSafe. Please verify your email address by clicking the button below:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}"
                       style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">
                        Verify Email
                    </a>
                </div>

                <p style="color: #6b7280; font-size: 14px;">
                    Or copy and paste this link into your browser:
                    <br>
                    <a href="{verification_link}" style="color: #667eea; word-break: break-all;">{verification_link}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">

                <p style="color: #6b7280; font-size: 12px;">
                    This link will expire in 24 hours.
                    <br><br>
                    If you didn't create a FloodSafe account, you can safely ignore this email.
                </p>
            </div>

            <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
                <p>FloodSafe - Community flood monitoring for social good</p>
            </div>
        </body>
        </html>
        """


# Singleton instance
email_service = EmailService()
