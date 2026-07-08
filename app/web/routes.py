"""Local system and dashboard routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import SecretStr
from sqlmodel import Session, select

from app.collectors.base import CollectorStatus
from app.core.config import Settings
from app.core.llm_settings import LLM_PROVIDER_PRESETS, load_llm_settings, save_llm_settings
from app.core.logging import redact_text
from app.core.source_settings import (
    SavedSourceSettings,
    load_source_settings,
    read_env_values,
    save_source_settings,
)
from app.core.timezones import utc_now
from app.db.models import ContentItem, Report, ReportSection, SourceStatus
from app.jobs.collect_once import SUPPORTED_SOURCES, CollectOnceResult, collect_once
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
            "phase": "phase_10",
            "app": settings.app_name,
            "environment": settings.app_env,
            "time_utc": utc_now().isoformat(),
        }

    @app.get("/status/sources", tags=["system"])
    def source_status() -> dict[str, Any]:
        statuses = _source_statuses(app)
        return {
            "status": "ok",
            "phase": "phase_10",
            "sources": source_status_json(statuses),
            "note": (
                "Collectors are available for explicit runs; "
                "the app shell does not auto-run them."
            ),
        }

    @app.get("/settings/public", tags=["system"])
    def public_settings() -> dict[str, Any]:
        return settings.public_summary()

    @app.get("/settings/llm", response_class=HTMLResponse, tags=["dashboard"])
    def llm_settings(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "llm_settings.html",
            {
                "settings": settings,
                "view": _llm_settings_view(app, settings),
            },
        )

    @app.post("/settings/llm", response_class=HTMLResponse, tags=["dashboard"])
    async def save_llm_settings_route(request: Request) -> HTMLResponse:
        form = _parse_form(await request.body())
        provider = form.get("provider", "custom")
        saved = save_llm_settings(
            _env_path(app),
            provider=provider,
            base_url=form.get("base_url", ""),
            model=form.get("model", ""),
            api_key=form.get("api_key"),
            clear_api_key=form.get("clear_api_key") == "on",
        )
        _apply_runtime_llm_settings(
            settings,
            saved,
            api_key=form.get("api_key", ""),
            clear_api_key=form.get("clear_api_key") == "on",
        )
        return templates.TemplateResponse(
            request,
            "llm_settings.html",
            {
                "settings": settings,
                "view": _llm_settings_view(app, settings, saved=True),
            },
        )

    @app.get("/settings/sources", response_class=HTMLResponse, tags=["dashboard"])
    def source_settings(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "source_settings.html",
            {
                "settings": settings,
                "view": _source_settings_view(app, settings),
            },
        )

    @app.post("/settings/sources", response_class=HTMLResponse, tags=["dashboard"])
    async def save_source_settings_route(request: Request) -> HTMLResponse:
        form = _parse_form(await request.body())
        saved = save_source_settings(
            _env_path(app),
            rss_feed_urls=form.get("rss_feed_urls", ""),
            sec_user_agent=form.get("sec_user_agent", ""),
            sec_cik=form.get("sec_cik", ""),
            arxiv_search_query=form.get("arxiv_search_query", ""),
            github_query=form.get("github_query", ""),
            github_token=form.get("github_token"),
            clear_github_token=form.get("clear_github_token") == "on",
            fred_api_key=form.get("fred_api_key"),
            clear_fred_api_key=form.get("clear_fred_api_key") == "on",
            fred_series_id=form.get("fred_series_id", ""),
        )
        _apply_runtime_source_settings(
            app,
            settings,
            saved,
            clear_github_token=form.get("clear_github_token") == "on",
            clear_fred_api_key=form.get("clear_fred_api_key") == "on",
        )

        run_result: CollectOnceResult | None = None
        run_error: str | None = None
        if form.get("action") == "run":
            selected_sources = _selected_source_names(form)
            if selected_sources:
                try:
                    with Session(app.state.engine) as session:
                        run_result = await collect_once(
                            session,
                            settings=settings,
                            sources=selected_sources,
                        )
                except Exception as exc:
                    run_error = redact_text(f"Collect once failed: {exc}")
            else:
                run_error = "Select at least one source before running collection."

        return templates.TemplateResponse(
            request,
            "source_settings.html",
            {
                "settings": settings,
                "view": _source_settings_view(
                    app,
                    settings,
                    saved=True,
                    run_result=run_result,
                    run_error=run_error,
                ),
            },
        )

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


def _llm_settings_view(
    app: FastAPI,
    settings: Settings,
    *,
    saved: bool = False,
) -> dict[str, Any]:
    saved_settings = load_llm_settings(_env_path(app))
    return {
        "saved": saved,
        "provider": saved_settings.provider or settings.llm_provider,
        "base_url": saved_settings.base_url or settings.llm_base_url,
        "model": saved_settings.model or settings.llm_model,
        "has_api_key": saved_settings.has_api_key or settings.llm_api_key is not None,
        "presets": [preset for preset in LLM_PROVIDER_PRESETS.values()],
    }


def _source_settings_view(
    app: FastAPI,
    settings: Settings,
    *,
    saved: bool = False,
    run_result: CollectOnceResult | None = None,
    run_error: str | None = None,
) -> dict[str, Any]:
    saved_settings = load_source_settings(_env_path(app))
    return {
        "saved": saved,
        "rss_feed_urls": saved_settings.rss_feed_urls or settings.rss_feed_urls or "",
        "sec_user_agent": saved_settings.sec_user_agent or settings.sec_user_agent or "",
        "sec_cik": saved_settings.sec_cik or settings.sec_cik,
        "arxiv_search_query": saved_settings.arxiv_search_query or settings.arxiv_search_query,
        "github_query": saved_settings.github_query or settings.github_query,
        "has_github_token": saved_settings.has_github_token or settings.github_token is not None,
        "has_fred_api_key": saved_settings.has_fred_api_key or settings.fred_api_key is not None,
        "fred_series_id": saved_settings.fred_series_id or settings.fred_series_id,
        "source_options": _source_options(),
        "run_result": _collect_once_result_view(run_result),
        "run_error": run_error,
    }


def _apply_runtime_llm_settings(
    settings: Settings,
    saved: Any,
    *,
    api_key: str,
    clear_api_key: bool,
) -> None:
    settings.llm_provider = saved.provider
    settings.llm_base_url = saved.base_url
    settings.llm_model = saved.model
    if clear_api_key:
        settings.llm_api_key = None
    elif api_key.strip():
        settings.llm_api_key = SecretStr(api_key.strip())


def _apply_runtime_source_settings(
    app: FastAPI,
    settings: Settings,
    saved: SavedSourceSettings,
    *,
    clear_github_token: bool,
    clear_fred_api_key: bool,
) -> None:
    values = read_env_values(_env_path(app))
    settings.rss_feed_urls = saved.rss_feed_urls
    settings.sec_user_agent = saved.sec_user_agent or None
    settings.sec_cik = saved.sec_cik
    settings.arxiv_search_query = saved.arxiv_search_query
    settings.github_query = saved.github_query
    settings.fred_series_id = saved.fred_series_id
    if clear_github_token:
        settings.github_token = None
    elif values.get("GITHUB_TOKEN"):
        settings.github_token = SecretStr(values["GITHUB_TOKEN"])
    if clear_fred_api_key:
        settings.fred_api_key = None
    elif values.get("FRED_API_KEY"):
        settings.fred_api_key = SecretStr(values["FRED_API_KEY"])


def _env_path(app: FastAPI) -> Path:
    return getattr(app.state, "env_file_path", Path(".env"))


def _parse_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _selected_source_names(form: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        source_name
        for source_name in SUPPORTED_SOURCES
        if form.get(f"source_{source_name}") == "on"
    )


def _source_options() -> list[dict[str, str]]:
    labels = {
        "rss": "RSS",
        "sec_edgar": "SEC EDGAR",
        "arxiv": "arXiv",
        "github": "GitHub",
        "fred": "FRED",
    }
    return [
        {
            "name": source_name,
            "field": f"source_{source_name}",
            "label": labels[source_name],
        }
        for source_name in SUPPORTED_SOURCES
    ]


def _collect_once_result_view(result: CollectOnceResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "collector_count": result.collector_count,
        "total_items_seen": result.total_items_seen,
        "source_failure_count": result.source_failure_count,
        "summaries": [
            {
                "source_name": summary.source_name,
                "status": summary.status.value,
                "new_items": summary.content_items_seen,
                "skipped_duplicates": summary.skipped_duplicates,
                "is_failure": summary.status
                not in {CollectorStatus.SUCCESS, CollectorStatus.EMPTY},
            }
            for summary in result.summaries
        ],
    }
