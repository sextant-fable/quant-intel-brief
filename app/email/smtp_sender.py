"""SMTP email sender with dry-run default behavior."""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from email.message import EmailMessage as StdlibEmailMessage
from typing import Any

from pydantic import SecretStr

from app.email.sender import (
    EmailConfigurationError,
    EmailDeliveryResult,
    EmailSender,
    OutboundEmail,
)


class SmtpEmailSender(EmailSender):
    """SMTP sender that only sends when dry_run is disabled explicitly."""

    provider = "smtp"

    def __init__(
        self,
        *,
        host: str | None,
        port: int = 587,
        username: str | SecretStr | None = None,
        password: str | SecretStr | None = None,
        from_email: str | None = None,
        use_tls: bool = True,
        smtp_factory: Callable[[str, int], Any] = smtplib.SMTP,
    ) -> None:
        self.host = host
        self.port = port
        self.username = _secret_value(username)
        self.password = _secret_value(password)
        self.from_email = from_email
        self.use_tls = use_tls
        self._smtp_factory = smtp_factory

    def send(self, message: OutboundEmail, *, dry_run: bool = True) -> EmailDeliveryResult:
        if dry_run:
            return EmailDeliveryResult(
                provider=self.provider,
                status="dry_run",
                dry_run=True,
                recipient_count=len(message.recipients),
            )

        self._validate_live_config(message)
        if self.host is None:
            raise EmailConfigurationError("SMTP_HOST is required for live SMTP delivery.")
        host = self.host
        outbound = self._build_message(message)

        try:
            with self._smtp_factory(host, self.port) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.send_message(outbound)
        except Exception as exc:  # pragma: no cover - exercised through provider mocks.
            return EmailDeliveryResult(
                provider=self.provider,
                status="failed",
                dry_run=False,
                recipient_count=len(message.recipients),
                error_message=str(exc),
            )

        return EmailDeliveryResult(
            provider=self.provider,
            status="sent",
            dry_run=False,
            recipient_count=len(message.recipients),
        )

    def _validate_live_config(self, message: OutboundEmail) -> None:
        if not self.host:
            raise EmailConfigurationError("SMTP_HOST is required for live SMTP delivery.")
        if not (message.from_email or self.from_email):
            raise EmailConfigurationError("SMTP_FROM or message.from_email is required.")

    def _build_message(self, message: OutboundEmail) -> StdlibEmailMessage:
        email_message = StdlibEmailMessage()
        email_message["Subject"] = message.subject
        email_message["From"] = message.from_email or self.from_email
        email_message["To"] = ", ".join(message.recipients)
        email_message.set_content(message.text_body or "HTML report attached in email body.")
        email_message.add_alternative(message.html_body, subtype="html")
        return email_message


def _secret_value(value: str | SecretStr | None) -> str | None:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


__all__ = ["SmtpEmailSender"]
