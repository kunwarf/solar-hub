# External Service Adapters - SMS, Email, Payment gateways, AI providers

from .smtp_email_service import SMTPEmailService, MockEmailService
from .email_templates import (
    get_base_template,
    get_verification_email_template,
    get_password_reset_email_template,
    get_alert_notification_template,
    get_welcome_email_template,
)
from .system_b_client import (
    SystemBClient,
    DeviceInfo,
    SystemBClientError,
    DeviceNotFoundError,
    DeviceAlreadyClaimedError,
    get_system_b_client,
)

__all__ = [
    'SMTPEmailService',
    'MockEmailService',
    'get_base_template',
    'get_verification_email_template',
    'get_password_reset_email_template',
    'get_alert_notification_template',
    'get_welcome_email_template',
    # System B Client
    'SystemBClient',
    'DeviceInfo',
    'SystemBClientError',
    'DeviceNotFoundError',
    'DeviceAlreadyClaimedError',
    'get_system_b_client',
]
