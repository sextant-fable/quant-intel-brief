"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def create_db_engine(database_url: str, echo: bool = False) -> Engine:
    """Create a SQLModel engine for SQLite-backed local storage."""
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {"echo": echo}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            engine_kwargs["poolclass"] = StaticPool
        _ensure_sqlite_parent(database_url)

    return create_engine(database_url, **engine_kwargs)


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return
    db_path = Path(database_url.replace("sqlite:///", "", 1))
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)


def init_db(engine: Engine) -> None:
    """Create all configured SQLModel tables."""
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_context(engine: Engine) -> Iterator[Session]:
    """Yield a SQLModel session with automatic close."""
    with Session(engine) as session:
        yield session


def get_session() -> Iterator[Session]:
    """FastAPI dependency for a session bound to configured local storage."""
    engine = create_db_engine(get_settings().database_url)
    with Session(engine) as session:
        yield session
