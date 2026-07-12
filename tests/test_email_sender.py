"""Phase 8 email preview and provider tests."""

from __future__ import annotations

import json
from datetime import date
from email.message import EmailMessage as StdlibEmailMessage
from typing import Any

import httpx
import pytest

from app.email.resend_sender import ResendEmailSender
from app.email.sender import (
    DryRunEmailSender,
    EmailConfigurationError,
    OutboundEmail,
    build_report_email,
    normalize_recipients,
)
from app.email.smtp_sender import SmtpEmailSender
from app.llm.schemas import EventSummary, SummaryResult
from app.reports.generator import generate_daily_report


def _report_email() -> OutboundEmail:
    summary = EventSummary(
        event_id="macro",
        headline="FOMC path update",
        headline_zh="FOMC 利率路径更新",
        factual_summary="A cited source reported an FOMC path update.",
        factual_summary_zh="引用来源报告了 FOMC 利率路径变化。",
        market_relevance="Relevant as a macro risk input.",
        market_relevance_zh="这可作为宏观风险观察信号。",
        uncertainty="Future Fed communication may change interpretation.",
        what_to_watch=["Watch the next Fed communication."],
        what_to_watch_zh=["关注下一次美联储沟通。"],
        source_credibility="high",
        source_credibility_reason="The event uses a cited official-style source.",
        source_ids=["source-1"],
        source_urls=["https://example.test/fomc"],
        assets=["macro"],
    )
    report = generate_daily_report(
        [
            SummaryResult(
                success=True,
                ranked_item_id="ranked-macro",
                event_id="macro",
                ranked_score=91.0,
                summary=summary,
            )
        ],
        report_date=date(2026, 7, 8),
    )
    return build_report_email(
        report,
        "alpha@example.test; beta@example.test",
        from_email="brief@example.test",
    )


def test_build_report_email_normalizes_recipients_and_preview_body() -> None:
    message = _report_email()

    assert normalize_recipients("alpha@example.test, beta@example.test") == [
        "alpha@example.test",
        "beta@example.test",
    ]
    assert message.subject == "Quant Intel Brief - 2026-07-08"
    assert message.recipients == ["alpha@example.test", "beta@example.test"]
    assert "FOMC path update" in message.html_body
    assert "FOMC 利率路径更新" in message.html_body
    assert "Why it matters" in (message.text_body or "")
    assert "https://example.test/fomc" in (message.text_body or "")


def test_dry_run_sender_never_uses_network() -> None:
    result = DryRunEmailSender().send(_report_email())

    assert result.status == "dry_run"
    assert result.provider == "dry_run"
    assert result.recipient_count == 2


def test_smtp_dry_run_does_not_create_connection() -> None:
    def fail_factory(_host: str, _port: int) -> Any:
        raise AssertionError("SMTP factory should not be called during dry-run")

    sender = SmtpEmailSender(
        host="smtp.example.test",
        from_email="brief@example.test",
        smtp_factory=fail_factory,
    )

    result = sender.send(_report_email())

    assert result.status == "dry_run"


def test_smtp_mock_send_path() -> None:
    fake = FakeSmtp()

    def factory(host: str, port: int) -> FakeSmtp:
        fake.host = host
        fake.port = port
        return fake

    sender = SmtpEmailSender(
        host="smtp.example.test",
        port=2525,
        username="user",
        password="pass",
        from_email="brief@example.test",
        smtp_factory=factory,
    )

    result = sender.send(_report_email(), dry_run=False)

    assert result.status == "sent"
    assert fake.host == "smtp.example.test"
    assert fake.port == 2525
    assert fake.started_tls is True
    assert fake.login_args == ("user", "pass")
    assert fake.sent_message is not None
    assert fake.sent_message["Subject"] == "Quant Intel Brief - 2026-07-08"


def test_smtp_live_send_requires_explicit_configuration() -> None:
    sender = SmtpEmailSender(host=None, from_email="brief@example.test")

    with pytest.raises(EmailConfigurationError):
        sender.send(_report_email(), dry_run=False)


def test_resend_dry_run_does_not_use_http_client() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP transport should not be called during dry-run")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sender = ResendEmailSender(
        api_key="test-key",
        from_email="brief@example.test",
        http_client=client,
    )

    result = sender.send(_report_email())

    assert result.status == "dry_run"


def test_resend_mock_send_path() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        assert request.url.path == "/emails"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert payload["from"] == "brief@example.test"
        assert payload["to"] == ["alpha@example.test", "beta@example.test"]
        return httpx.Response(200, json={"id": "email-123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sender = ResendEmailSender(
        api_key="test-key",
        from_email="brief@example.test",
        http_client=client,
    )

    result = sender.send(_report_email(), dry_run=False)

    assert len(requests) == 1
    assert result.status == "sent"
    assert result.message_id == "email-123"


class FakeSmtp:
    def __init__(self) -> None:
        self.host: str | None = None
        self.port: int | None = None
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.sent_message: StdlibEmailMessage | None = None

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: StdlibEmailMessage) -> None:
        self.sent_message = message
