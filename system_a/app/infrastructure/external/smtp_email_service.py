"""
SMTP Email Service implementation.

Provides async email sending using aiosmtplib.
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib

from ...application.interfaces.services import EmailService
from ...config import NotificationSettings
from .email_templates import (
    get_verification_email_template,
    get_password_reset_email_template,
    get_alert_notification_template,
)

logger = logging.getLogger(__name__)


class SMTPEmailService(EmailService):
    """
    SMTP-based email service implementation.

    Uses aiosmtplib for async email operations with TLS support.
    """

    def __init__(self, settings: NotificationSettings):
        """
        Initialize SMTP email service.

        Args:
            settings: Notification settings with SMTP configuration
        """
        self._settings = settings
        self._enabled = settings.email_enabled

    async def _create_connection(self) -> aiosmtplib.SMTP:
        """Create and return an SMTP connection."""
        smtp = aiosmtplib.SMTP(
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            use_tls=False,  # We'll use STARTTLS
            start_tls=True,
        )
        return smtp

    async def _send_message(
        self,
        to: str,
        subject: str,
        plain_body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Internal method to send email message.

        Args:
            to: Recipient email address
            subject: Email subject
            plain_body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            logger.warning("Email service is disabled. Skipping email to %s", to)
            return False

        if not self._settings.smtp_user or not self._settings.smtp_password:
            logger.error("SMTP credentials not configured")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self._settings.smtp_from_name} <{self._settings.smtp_from_email}>"
            msg["To"] = to

            # Attach plain text
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))

            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Send email
            async with aiosmtplib.SMTP(
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                use_tls=False,
                start_tls=True,
            ) as smtp:
                await smtp.login(self._settings.smtp_user, self._settings.smtp_password)
                await smtp.send_message(msg)

            logger.info("Email sent successfully to %s: %s", to, subject)
            return True

        except aiosmtplib.SMTPAuthenticationError as e:
            logger.error("SMTP authentication failed: %s", str(e))
            return False
        except aiosmtplib.SMTPConnectError as e:
            logger.error("Failed to connect to SMTP server: %s", str(e))
            return False
        except aiosmtplib.SMTPException as e:
            logger.error("SMTP error sending email to %s: %s", to, str(e))
            return False
        except Exception as e:
            logger.exception("Unexpected error sending email to %s: %s", to, str(e))
            return False

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send a generic email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if sent successfully, False otherwise
        """
        return await self._send_message(to, subject, body, html_body)

    async def send_verification_email(
        self,
        to: str,
        verification_url: str,
        user_name: str = "User"
    ) -> bool:
        """
        Send email verification email.

        Args:
            to: Recipient email address
            verification_url: URL for email verification
            user_name: Name of the user for personalization

        Returns:
            True if sent successfully, False otherwise
        """
        plain_body, html_body = get_verification_email_template(
            user_name=user_name,
            verification_url=verification_url,
            expiry_hours=24
        )
        return await self._send_message(
            to=to,
            subject="Verify Your Email - Solar Hub",
            plain_body=plain_body,
            html_body=html_body
        )

    async def send_password_reset_email(
        self,
        to: str,
        reset_url: str,
        user_name: str = "User"
    ) -> bool:
        """
        Send password reset email.

        Args:
            to: Recipient email address
            reset_url: URL for password reset
            user_name: Name of the user for personalization

        Returns:
            True if sent successfully, False otherwise
        """
        plain_body, html_body = get_password_reset_email_template(
            user_name=user_name,
            reset_url=reset_url,
            expiry_minutes=60
        )
        return await self._send_message(
            to=to,
            subject="Reset Your Password - Solar Hub",
            plain_body=plain_body,
            html_body=html_body
        )

    async def send_alert_notification(
        self,
        to: str,
        alert_type: str,
        site_name: str,
        message: str,
        user_name: str = "User",
        severity: str = "warning",
        alert_time: Optional[str] = None,
        dashboard_url: Optional[str] = None
    ) -> bool:
        """
        Send alert notification email.

        Args:
            to: Recipient email address
            alert_type: Type of alert (e.g., "Low Power Output")
            site_name: Name of the affected site
            message: Alert message
            user_name: Name of the user for personalization
            severity: Alert severity (critical, warning, info)
            alert_time: Time when alert was triggered
            dashboard_url: URL to view alert details

        Returns:
            True if sent successfully, False otherwise
        """
        plain_body, html_body = get_alert_notification_template(
            user_name=user_name,
            alert_type=alert_type,
            site_name=site_name,
            message=message,
            severity=severity,
            alert_time=alert_time,
            dashboard_url=dashboard_url
        )

        severity_prefix = {
            "critical": "[CRITICAL]",
            "warning": "[WARNING]",
            "info": "[INFO]"
        }.get(severity.lower(), "[ALERT]")

        return await self._send_message(
            to=to,
            subject=f"{severity_prefix} Alert: {alert_type} - {site_name}",
            plain_body=plain_body,
            html_body=html_body
        )


class MockEmailService(EmailService):
    """
    Mock email service for testing and development.

    Logs emails instead of sending them.
    """

    def __init__(self):
        """Initialize mock email service."""
        self._sent_emails: list[dict] = []

    @property
    def sent_emails(self) -> list[dict]:
        """Get list of sent emails for testing."""
        return self._sent_emails

    def clear(self) -> None:
        """Clear sent emails list."""
        self._sent_emails.clear()

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Log email instead of sending."""
        email_data = {
            "to": to,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "type": "generic"
        }
        self._sent_emails.append(email_data)
        logger.info("Mock email sent to %s: %s", to, subject)
        return True

    async def send_verification_email(self, to: str, verification_url: str) -> bool:
        """Log verification email."""
        email_data = {
            "to": to,
            "subject": "Verify Your Email - Solar Hub",
            "verification_url": verification_url,
            "type": "verification"
        }
        self._sent_emails.append(email_data)
        logger.info("Mock verification email sent to %s", to)
        return True

    async def send_password_reset_email(self, to: str, reset_url: str) -> bool:
        """Log password reset email."""
        email_data = {
            "to": to,
            "subject": "Reset Your Password - Solar Hub",
            "reset_url": reset_url,
            "type": "password_reset"
        }
        self._sent_emails.append(email_data)
        logger.info("Mock password reset email sent to %s", to)
        return True

    async def send_alert_notification(
        self,
        to: str,
        alert_type: str,
        site_name: str,
        message: str
    ) -> bool:
        """Log alert notification."""
        email_data = {
            "to": to,
            "subject": f"Alert: {alert_type} - {site_name}",
            "alert_type": alert_type,
            "site_name": site_name,
            "message": message,
            "type": "alert"
        }
        self._sent_emails.append(email_data)
        logger.info("Mock alert email sent to %s for %s", to, site_name)
        return True
