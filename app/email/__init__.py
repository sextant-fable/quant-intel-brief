"""Email delivery package."""

from app.email.resend_sender import ResendEmailSender
from app.email.sender import (
    DryRunEmailSender,
    EmailConfigurationError,
    EmailDeliveryResult,
    EmailSender,
    OutboundEmail,
    build_report_email,
    normalize_recipients,
)
from app.email.smtp_sender import SmtpEmailSender

__all__ = [
    "DryRunEmailSender",
    "EmailConfigurationError",
    "EmailDeliveryResult",
    "EmailSender",
    "OutboundEmail",
    "ResendEmailSender",
    "SmtpEmailSender",
    "build_report_email",
    "normalize_recipients",
]
