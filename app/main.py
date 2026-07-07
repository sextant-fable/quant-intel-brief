"""Application entry points."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_engine, init_db
from app.web.routes import register_routes


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    """Create the local FastAPI app."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    active_engine = engine or create_db_engine(active_settings.database_url)
    init_db(active_engine)

    app = FastAPI(title=active_settings.dashboard_title)
    app.state.settings = active_settings
    app.state.engine = active_engine
    register_routes(app, active_settings)
    return app


def main() -> None:
    """Run the local FastAPI app."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.web_host,
        port=settings.web_port,
    )
