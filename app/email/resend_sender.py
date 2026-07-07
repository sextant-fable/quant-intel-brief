"""Resend email sender with explicit live-send configuration."""

from __future__ import annotations

import httpx
from pydantic import SecretStr

from app.email.sender import (
    EmailConfigurationError,
    EmailDeliveryResult,
    EmailSender,
    OutboundEmail,
)


class ResendEmailSender(EmailSender):
    """Resend sender that supports dry-run preview and mocked HTTP tests."""

    provider = "resend"

    def __init__(
        self,
        *,
        api_key: str | SecretStr | None,
        from_email: str | None,
        base_url: str = "https://api.resend.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = _secret_value(api_key)
        self.from_email = from_email
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client

    def send(self, message: OutboundEmail, *, dry_run: bool = True) -> EmailDeliveryResult:
        if dry_run:
            return EmailDeliveryResult(
                provider=self.provider,
                status="dry_run",
                dry_run=True,
                recipient_count=len(message.recipients),
            )

        self._validate_live_config(message)
        payload = {
            "from": message.from_email or self.from_email,
            "to": message.recipients,
            "subject": message.subject,
            "html": message.html_body,
            "text": message.text_body,
        }
        client = self._http_client or httpx.Client(timeout=10)
        close_after = self._http_client is None

        try:
            response = client.post(
                f"{self.base_url}/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            message_id = response.json().get("id")
        except (httpx.HTTPError, ValueError) as exc:
            return EmailDeliveryResult(
                provider=self.provider,
                status="failed",
                dry_run=False,
                recipient_count=len(message.recipients),
                error_message=str(exc),
            )
        finally:
            if close_after:
                client.close()

        return EmailDeliveryResult(
            provider=self.provider,
            status="sent",
            dry_run=False,
            recipient_count=len(message.recipients),
            message_id=message_id,
        )

    def _validate_live_config(self, message: OutboundEmail) -> None:
        if not self.api_key:
            raise EmailConfigurationError("RESEND_API_KEY is required for live Resend delivery.")
        if not (message.from_email or self.from_email):
            raise EmailConfigurationError("RESEND_FROM or message.from_email is required.")


def _secret_value(value: str | SecretStr | None) -> str | None:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


__all__ = ["ResendEmailSender"]
