"""Local system routes."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.timezones import utc_now
from app.db.models import SourceStatus


def register_routes(app: FastAPI, settings: Settings) -> None:
    """Register local health and source status routes."""

    @app.get("/health", tags=["system"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "phase": "phase_4",
            "app": settings.app_name,
            "environment": settings.app_env,
            "time_utc": utc_now().isoformat(),
        }

    @app.get("/status/sources", tags=["system"])
    def source_status() -> dict[str, Any]:
        with Session(app.state.engine) as session:
            statuses = session.exec(
                select(SourceStatus).order_by(SourceStatus.source_name)
            ).all()

        return {
            "status": "ok",
            "phase": "phase_4",
            "sources": [
                {
                    "source_name": item.source_name,
                    "status": item.status,
                    "message": item.message,
                    "last_checked_at": item.last_checked_at.isoformat(),
                }
                for item in statuses
            ],
            "note": (
                "Collectors are available for explicit runs; "
                "the app shell does not auto-run them."
            ),
        }

    @app.get("/settings/public", tags=["system"])
    def public_settings() -> dict[str, Any]:
        return settings.public_summary()
