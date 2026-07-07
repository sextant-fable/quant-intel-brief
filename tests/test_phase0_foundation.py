"""Phase 0 foundation tests."""

from __future__ import annotations

import logging
from io import StringIO

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.core.config import Settings
from app.core.logging import RedactingFilter, redact_text
from app.core.timezones import UTC, ensure_utc, to_timezone, utc_now
from app.db.models import ContentItem, Source
from app.db.session import create_db_engine, init_db
from app.main import create_app


def test_settings_load_defaults_and_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "phase-zero-test")
    monkeypatch.setenv("WEB_PORT", "8123")
    monkeypatch.setenv("STORE_FULL_TEXT", "false")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-committed")

    settings = Settings()

    assert settings.app_name == "phase-zero-test"
    assert settings.web_port == 8123
    assert settings.store_full_text is False
    assert settings.deepseek_api_key is not None
    assert settings.deepseek_api_key.get_secret_value() == "not-committed"
    assert "deepseek_api_key" not in settings.public_summary()


def test_sqlmodel_schema_can_be_created_in_memory() -> None:
    engine = create_db_engine("sqlite://")
    init_db(engine)

    with Session(engine) as session:
        source = Source(name="fixture", source_type="fixture", display_name="Fixture")
        session.add(source)
        session.commit()

        item = ContentItem(
            source_id=source.id,
            source_name=source.name,
            source_item_id="fixture-1",
            url="https://example.test/item",
            title="Fixture item",
            excerpt="Compact excerpt only",
        )
        session.add(item)
        session.commit()

        stored_item = session.exec(select(ContentItem)).one()

    assert stored_item.source_name == "fixture"
    assert stored_item.excerpt == "Compact excerpt only"
    assert not hasattr(stored_item, "content_text")
    assert SQLModel.metadata.tables["content_items"] is not None


def test_create_app_registers_fixture_only_health_routes() -> None:
    settings = Settings(
        app_name="phase-zero-test",
        database_url="sqlite://",
        dashboard_title="Phase Zero",
    )
    app = create_app(settings=settings, engine=create_db_engine("sqlite://"))
    client = TestClient(app)

    health = client.get("/health")
    source_status = client.get("/status/sources")
    public_settings = client.get("/settings/public")

    assert health.status_code == 200
    assert health.json()["phase"] == "phase_1"
    assert health.json()["app"] == "phase-zero-test"
    assert source_status.status_code == 200
    assert source_status.json()["sources"] == []
    assert "does not auto-run" in source_status.json()["note"]
    assert public_settings.status_code == 200
    assert "deepseek_api_key" not in public_settings.json()


def test_timezone_helpers_return_aware_datetimes() -> None:
    now = utc_now()
    converted = to_timezone(now, "America/New_York")

    assert now.tzinfo is UTC
    assert ensure_utc(converted).tzinfo is UTC


def test_logging_redacts_secret_patterns_and_values() -> None:
    assert "super-secret" not in redact_text("token=super-secret", ["super-secret"])

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter(["abc123"]))

    logger = logging.getLogger("tests.phase0.redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.warning("api_key=%s token=%s", "abc123", "secret-token")

    output = stream.getvalue()
    assert "abc123" not in output
    assert "secret-token" not in output
    assert "***" in output
