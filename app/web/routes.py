"""Fixture-only Phase 0 web routes."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.core.config import Settings
from app.core.timezones import utc_now


def register_routes(app: FastAPI, settings: Settings) -> None:
    """Register local health and fixture status routes."""

    @app.get("/health", tags=["system"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "phase": "phase_0",
            "app": settings.app_name,
            "environment": settings.app_env,
            "time_utc": utc_now().isoformat(),
        }

    @app.get("/status/sources", tags=["system"])
    def source_status() -> dict[str, Any]:
        return {
            "status": "ok",
            "phase": "phase_0",
            "sources": [],
            "note": "Fixture-only source status; collectors are not implemented in Phase 0.",
        }

    @app.get("/settings/public", tags=["system"])
    def public_settings() -> dict[str, Any]:
        return settings.public_summary()
