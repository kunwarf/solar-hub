"""
HTML email templates for Solar Hub.

Provides templates for verification, password reset, and alert notifications.
"""
from typing import Optional


def get_base_template(content: str, title: str = "Solar Hub") -> str:
    """Wrap content in base HTML email template."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .email-wrapper {{
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1a73e8 0%, #34a853 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .header .logo {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .content {{
            padding: 30px 20px;
        }}
        .content p {{
            margin: 0 0 15px 0;
        }}
        .button {{
            display: inline-block;
            padding: 14px 28px;
            background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%);
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .button:hover {{
            background: linear-gradient(135deg, #1557b0 0%, #0d47a1 100%);
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #666;
        }}
        .footer a {{
            color: #1a73e8;
            text-decoration: none;
        }}
        .alert-box {{
            border-radius: 6px;
            padding: 15px;
            margin: 15px 0;
        }}
        .alert-critical {{
            background-color: #fee2e2;
            border-left: 4px solid #ef4444;
        }}
        .alert-warning {{
            background-color: #fef3c7;
            border-left: 4px solid #f59e0b;
        }}
        .alert-info {{
            background-color: #e0f2fe;
            border-left: 4px solid #0ea5e9;
        }}
        .code {{
            background-color: #f3f4f6;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }}
        .expiry-note {{
            background-color: #fef3c7;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 13px;
            color: #92400e;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-wrapper">
            <div class="header">
                <div class="logo">&#9728;</div>
                <h1>Solar Hub</h1>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                <p>&copy; 2026 Solar Hub. All rights reserved.</p>
                <p>
                    Commercial Solar Monitoring Platform<br>
                    Pakistan's Leading Solar Management Solution
                </p>
                <p>
                    <a href="#">Privacy Policy</a> |
                    <a href="#">Terms of Service</a> |
                    <a href="#">Unsubscribe</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_verification_email_template(
    user_name: str,
    verification_url: str,
    expiry_hours: int = 24
) -> tuple[str, str]:
    """
    Get email verification template.

    Returns:
        Tuple of (plain_text, html_body)
    """
    plain_text = f"""
Hello {user_name},

Welcome to Solar Hub! Please verify your email address to complete your registration.

Click the link below to verify your email:
{verification_url}

This link will expire in {expiry_hours} hours.

If you didn't create an account with Solar Hub, please ignore this email.

Best regards,
The Solar Hub Team
"""

    html_content = f"""
<h2>Verify Your Email Address</h2>
<p>Hello {user_name},</p>
<p>Welcome to Solar Hub! Please verify your email address to complete your registration and start monitoring your solar installations.</p>

<p style="text-align: center;">
    <a href="{verification_url}" class="button">Verify Email Address</a>
</p>

<div class="expiry-note">
    <strong>Note:</strong> This verification link will expire in {expiry_hours} hours.
</div>

<p>If the button doesn't work, copy and paste this link into your browser:</p>
<p style="word-break: break-all; font-size: 13px; color: #666;">
    {verification_url}
</p>

<p>If you didn't create an account with Solar Hub, please ignore this email.</p>

<p>Best regards,<br>The Solar Hub Team</p>
"""

    return plain_text, get_base_template(html_content, "Verify Your Email - Solar Hub")


def get_password_reset_email_template(
    user_name: str,
    reset_url: str,
    expiry_minutes: int = 60
) -> tuple[str, str]:
    """
    Get password reset template.

    Returns:
        Tuple of (plain_text, html_body)
    """
    plain_text = f"""
Hello {user_name},

We received a request to reset your password for your Solar Hub account.

Click the link below to reset your password:
{reset_url}

This link will expire in {expiry_minutes} minutes for security reasons.

If you didn't request a password reset, please ignore this email or contact support if you're concerned about your account security.

Best regards,
The Solar Hub Team
"""

    html_content = f"""
<h2>Reset Your Password</h2>
<p>Hello {user_name},</p>
<p>We received a request to reset your password for your Solar Hub account.</p>

<p style="text-align: center;">
    <a href="{reset_url}" class="button">Reset Password</a>
</p>

<div class="expiry-note">
    <strong>Security Notice:</strong> This link will expire in {expiry_minutes} minutes for your protection.
</div>

<p>If the button doesn't work, copy and paste this link into your browser:</p>
<p style="word-break: break-all; font-size: 13px; color: #666;">
    {reset_url}
</p>

<p><strong>Didn't request this?</strong></p>
<p>If you didn't request a password reset, please ignore this email. Your password will remain unchanged.</p>

<p>If you're concerned about your account security, please contact our support team.</p>

<p>Best regards,<br>The Solar Hub Team</p>
"""

    return plain_text, get_base_template(html_content, "Reset Your Password - Solar Hub")


def get_alert_notification_template(
    user_name: str,
    alert_type: str,
    site_name: str,
    message: str,
    severity: str = "warning",
    alert_time: Optional[str] = None,
    dashboard_url: Optional[str] = None
) -> tuple[str, str]:
    """
    Get alert notification template.

    Args:
        severity: One of 'critical', 'warning', 'info'

    Returns:
        Tuple of (plain_text, html_body)
    """
    severity_labels = {
        "critical": "CRITICAL",
        "warning": "WARNING",
        "info": "INFO"
    }
    severity_label = severity_labels.get(severity.lower(), "ALERT")

    time_str = f" at {alert_time}" if alert_time else ""
    dashboard_link = f"\n\nView details: {dashboard_url}" if dashboard_url else ""

    plain_text = f"""
[{severity_label}] Alert for {site_name}

Hello {user_name},

An alert has been triggered for your solar site:

Site: {site_name}
Type: {alert_type}
Time: {alert_time or 'Just now'}

Message:
{message}
{dashboard_link}

Please review this alert and take appropriate action if needed.

Best regards,
The Solar Hub Team
"""

    alert_class = f"alert-{severity.lower()}" if severity.lower() in ["critical", "warning", "info"] else "alert-warning"

    dashboard_button = ""
    if dashboard_url:
        dashboard_button = f"""
<p style="text-align: center;">
    <a href="{dashboard_url}" class="button">View Dashboard</a>
</p>
"""

    html_content = f"""
<h2>[{severity_label}] Alert Notification</h2>
<p>Hello {user_name},</p>
<p>An alert has been triggered for your solar site:</p>

<div class="alert-box {alert_class}">
    <p><strong>Site:</strong> {site_name}</p>
    <p><strong>Alert Type:</strong> {alert_type}</p>
    <p><strong>Time:</strong> {alert_time or 'Just now'}</p>
    <p><strong>Message:</strong></p>
    <p>{message}</p>
</div>

{dashboard_button}

<p>Please review this alert and take appropriate action if needed.</p>

<p>Best regards,<br>The Solar Hub Team</p>
"""

    return plain_text, get_base_template(html_content, f"[{severity_label}] Alert - Solar Hub")


def get_welcome_email_template(user_name: str, login_url: str) -> tuple[str, str]:
    """
    Get welcome email template (sent after email verification).

    Returns:
        Tuple of (plain_text, html_body)
    """
    plain_text = f"""
Hello {user_name},

Your email has been verified! Welcome to Solar Hub.

You can now log in to your account and start monitoring your solar installations.

Login: {login_url}

Getting Started:
1. Add your organization details
2. Register your first solar site
3. Connect your devices
4. Start monitoring in real-time

If you have any questions, our support team is here to help.

Best regards,
The Solar Hub Team
"""

    html_content = f"""
<h2>Welcome to Solar Hub!</h2>
<p>Hello {user_name},</p>
<p>Your email has been verified successfully! You're now ready to start monitoring your solar installations.</p>

<p style="text-align: center;">
    <a href="{login_url}" class="button">Go to Dashboard</a>
</p>

<h3>Getting Started</h3>
<ol>
    <li><strong>Set up your organization</strong> - Add your company details and invite team members</li>
    <li><strong>Register your first site</strong> - Add your solar installation location and configuration</li>
    <li><strong>Connect your devices</strong> - Link your inverters, meters, and sensors</li>
    <li><strong>Start monitoring</strong> - View real-time data and analytics</li>
</ol>

<p>If you have any questions, our support team is here to help.</p>

<p>Best regards,<br>The Solar Hub Team</p>
"""

    return plain_text, get_base_template(html_content, "Welcome to Solar Hub!")
