"""Email preview and delivery interfaces."""

from __future__ import annotations

from collections.abc import Iterable
from email.utils import parseaddr
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.reports.generator import DailyReport
from app.reports.templates import render_email_report


class EmailConfigurationError(RuntimeError):
    """Raised when a live email sender lacks explicit local configuration."""


class OutboundEmail(BaseModel):
    """A rendered report email ready for preview or explicit delivery."""

    subject: str
    html_body: str
    recipients: list[str] = Field(min_length=1)
    from_email: str | None = None
    text_body: str | None = None

    @field_validator("recipients")
    @classmethod
    def _validate_recipients(cls, recipients: list[str]) -> list[str]:
        cleaned = []
        for recipient in recipients:
            _, email_address = parseaddr(recipient)
            if not email_address or "@" not in email_address:
                raise ValueError(f"Invalid email recipient: {recipient!r}")
            cleaned.append(email_address)
        return cleaned


class EmailDeliveryResult(BaseModel):
    """Result of an email preview or delivery attempt."""

    provider: str
    status: Literal["dry_run", "sent", "failed"]
    dry_run: bool
    recipient_count: int
    message_id: str | None = None
    error_message: str | None = None


class EmailSender:
    """Base email sender interface."""

    provider = "base"

    def send(self, message: OutboundEmail, *, dry_run: bool = True) -> EmailDeliveryResult:
        """Send or preview an email."""
        raise NotImplementedError


class DryRunEmailSender(EmailSender):
    """Preview sender that never performs network I/O."""

    provider = "dry_run"

    def send(self, message: OutboundEmail, *, dry_run: bool = True) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            provider=self.provider,
            status="dry_run",
            dry_run=True,
            recipient_count=len(message.recipients),
        )


def normalize_recipients(recipients: str | Iterable[str]) -> list[str]:
    """Normalize comma, semicolon, or iterable recipient input."""
    if isinstance(recipients, str):
        raw_values = recipients.replace(";", ",").split(",")
    else:
        raw_values = list(recipients)

    cleaned = [value.strip() for value in raw_values if value.strip()]
    return OutboundEmail(subject="validation", html_body="<p></p>", recipients=cleaned).recipients


def build_report_email(
    report: DailyReport,
    recipients: str | Iterable[str],
    *,
    from_email: str | None = None,
) -> OutboundEmail:
    """Render a daily report into a previewable outbound email."""
    subject = f"{report.title} - {report.report_date.isoformat()}"
    html_body = render_email_report(report)
    text_body = _plain_text_preview(report)
    return OutboundEmail(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        recipients=normalize_recipients(recipients),
        from_email=from_email,
    )


def _plain_text_preview(report: DailyReport) -> str:
    lines = [report.title, report.report_date.isoformat(), report.source_coverage_note, ""]
    for section in report.sections:
        lines.append(section.title)
        if not section.events:
            lines.append("No qualifying summarized events.")
            lines.append("")
            continue
        for event in section.events:
            lines.append(f"- {event.headline}")
            lines.append(f"  Sources: {', '.join(event.source_urls)}")
        lines.append("")
    return "\n".join(lines).strip()


__all__ = [
    "DryRunEmailSender",
    "EmailConfigurationError",
    "EmailDeliveryResult",
    "EmailSender",
    "OutboundEmail",
    "build_report_email",
    "normalize_recipients",
]
