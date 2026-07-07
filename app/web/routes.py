"""Local system and dashboard routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.timezones import utc_now
from app.db.models import ContentItem, Report, ReportSection, SourceStatus
from app.web.filters import dashboard_filters_from_query, filter_content_items
from app.web.view_models import (
    build_dashboard_view,
    build_feed_view,
    build_report_detail_view,
    build_reports_view,
    build_source_status_view,
    source_status_json,
)

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def register_routes(app: FastAPI, settings: Settings) -> None:
    """Register local health, dashboard, and source status routes."""

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/dashboard/today", status_code=307)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "phase": "phase_9",
            "app": settings.app_name,
            "environment": settings.app_env,
            "time_utc": utc_now().isoformat(),
        }

    @app.get("/status/sources", tags=["system"])
    def source_status() -> dict[str, Any]:
        statuses = _source_statuses(app)
        return {
            "status": "ok",
            "phase": "phase_9",
            "sources": source_status_json(statuses),
            "note": (
                "Collectors are available for explicit runs; "
                "the app shell does not auto-run them."
            ),
        }

    @app.get("/settings/public", tags=["system"])
    def public_settings() -> dict[str, Any]:
        return settings.public_summary()

    @app.get("/dashboard/today", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_today(request: Request) -> HTMLResponse:
        with Session(app.state.engine) as session:
            view = build_dashboard_view(
                items=session.exec(select(ContentItem)).all(),
                reports=session.exec(select(Report)).all(),
                statuses=session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all(),
            )
        return templates.TemplateResponse(
            request,
            "dashboard_today.html",
            {"settings": settings, "view": view},
        )

    @app.get("/feed", response_class=HTMLResponse, tags=["dashboard"])
    def feed(
        request: Request,
        date_filter: str | None = Query(default=None, alias="date"),
        source: str | None = None,
        ticker: str | None = None,
        asset_class: str | None = None,
        quant_theme: str | None = None,
    ) -> HTMLResponse:
        filters = dashboard_filters_from_query(
            date_value=date_filter,
            source=source,
            ticker=ticker,
            asset_class=asset_class,
            quant_theme=quant_theme,
        )
        with Session(app.state.engine) as session:
            items = session.exec(select(ContentItem)).all()
        view = build_feed_view(items=filter_content_items(items, filters), filters=filters)
        return templates.TemplateResponse(
            request,
            "feed.html",
            {"settings": settings, "view": view},
        )

    @app.get("/reports", response_class=HTMLResponse, tags=["dashboard"])
    def reports(request: Request) -> HTMLResponse:
        with Session(app.state.engine) as session:
            view = build_reports_view(session.exec(select(Report)).all())
        return templates.TemplateResponse(
            request,
            "reports.html",
            {"settings": settings, "view": view},
        )

    @app.get("/reports/{report_id}", response_class=HTMLResponse, tags=["dashboard"])
    def report_detail(request: Request, report_id: str) -> HTMLResponse:
        with Session(app.state.engine) as session:
            report = session.get(Report, report_id)
            if report is None:
                raise HTTPException(status_code=404, detail="Report not found")
            sections = session.exec(
                select(ReportSection).where(ReportSection.report_id == report_id)
            ).all()
            view = build_report_detail_view(report=report, sections=sections)
        return templates.TemplateResponse(
            request,
            "report_detail.html",
            {"settings": settings, "view": view},
        )

    @app.get("/sources", response_class=HTMLResponse, tags=["dashboard"])
    def sources(request: Request) -> HTMLResponse:
        view = build_source_status_view(_source_statuses(app))
        return templates.TemplateResponse(
            request,
            "source_status.html",
            {"settings": settings, "view": view},
        )


def _source_statuses(app: FastAPI) -> list[SourceStatus]:
    with Session(app.state.engine) as session:
        return list(session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all())
