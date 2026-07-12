"""Local system and dashboard routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import SecretStr
from sqlalchemy import desc
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
    write_env_updates,
)
from app.core.timezones import utc_now
from app.db.models import (
    CollectionRun,
    CollectionRunItem,
    ContentItem,
    PremiumSourceNote,
    Report,
    ReportEventRecord,
    ReportSection,
    SourceStatus,
)
from app.jobs.collect_once import SUPPORTED_SOURCES, CollectOnceResult, collect_once
from app.jobs.generate_ai_report import (
    AiReportGenerationResult,
    generate_ai_report_from_local_content,
)
from app.premium.queue import (
    PremiumRssCollectResult,
    collect_premium_rss_feeds,
    update_premium_note,
    upsert_premium_note,
)
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
            finance_news_mcp_url=form.get("finance_news_mcp_url", ""),
            finance_news_mcp_sources=form.get("finance_news_mcp_sources", ""),
            finance_news_mcp_items_per_source=form.get(
                "finance_news_mcp_items_per_source",
                "20",
            ),
            sec_user_agent=form.get("sec_user_agent", ""),
            sec_cik=form.get("sec_cik", ""),
            arxiv_search_query=form.get("arxiv_search_query", ""),
            github_query=form.get("github_query", ""),
            github_token=form.get("github_token"),
            clear_github_token=form.get("clear_github_token") == "on",
            fred_api_key=form.get("fred_api_key"),
            clear_fred_api_key=form.get("clear_fred_api_key") == "on",
            fred_series_id=form.get("fred_series_id", ""),
            newsapi_key=form.get("newsapi_key"),
            clear_newsapi_key=form.get("clear_newsapi_key") == "on",
            newsapi_query=form.get("newsapi_query", ""),
            gdelt_query=form.get("gdelt_query", ""),
            alphavantage_api_key=form.get("alphavantage_api_key"),
            clear_alphavantage_api_key=form.get("clear_alphavantage_api_key") == "on",
            alphavantage_topics=form.get("alphavantage_topics", ""),
            finnhub_api_key=form.get("finnhub_api_key"),
            clear_finnhub_api_key=form.get("clear_finnhub_api_key") == "on",
            finnhub_category=form.get("finnhub_category", ""),
            reddit_access_token=form.get("reddit_access_token"),
            clear_reddit_access_token=form.get("clear_reddit_access_token") == "on",
            reddit_user_agent=form.get("reddit_user_agent", ""),
            reddit_query=form.get("reddit_query", ""),
            reddit_subreddit=form.get("reddit_subreddit", ""),
            youtube_api_key=form.get("youtube_api_key"),
            clear_youtube_api_key=form.get("clear_youtube_api_key") == "on",
            youtube_query=form.get("youtube_query", ""),
            x_bearer_token=form.get("x_bearer_token"),
            clear_x_bearer_token=form.get("clear_x_bearer_token") == "on",
            x_query=form.get("x_query", ""),
            stackexchange_key=form.get("stackexchange_key"),
            clear_stackexchange_key=form.get("clear_stackexchange_key") == "on",
            stackexchange_query=form.get("stackexchange_query", ""),
            stackexchange_site=form.get("stackexchange_site", ""),
            quantconnect_user_id=form.get("quantconnect_user_id"),
            clear_quantconnect_user_id=form.get("clear_quantconnect_user_id") == "on",
            quantconnect_token=form.get("quantconnect_token"),
            clear_quantconnect_token=form.get("clear_quantconnect_token") == "on",
            quantconnect_organization_id=form.get("quantconnect_organization_id", ""),
        )
        _apply_runtime_source_settings(
            app,
            settings,
            saved,
            form=form,
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
                            trigger="source_settings",
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

    @app.get("/premium", response_class=HTMLResponse, tags=["dashboard"])
    def premium_sources(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "premium_sources.html",
            {
                "settings": settings,
                "view": _premium_sources_view(app),
            },
        )

    @app.post("/premium", response_class=HTMLResponse, tags=["dashboard"])
    async def save_premium_sources(request: Request) -> HTMLResponse:
        form = _parse_form(await request.body())
        action = form.get("action", "")
        message: str | None = None
        error: str | None = None
        rss_result: PremiumRssCollectResult | None = None

        if action in {"save_rss", "collect_rss"}:
            feed_urls = form.get("premium_rss_feed_urls", "")
            write_env_updates(
                _env_path(app),
                {"PREMIUM_RSS_FEED_URLS": feed_urls.strip()},
                ("PREMIUM_RSS_FEED_URLS",),
                header="Premium public RSS",
            )
            settings.premium_rss_feed_urls = feed_urls.strip() or None
            message = "Premium RSS settings saved locally."
            if action == "collect_rss":
                if not feed_urls.strip():
                    error = "Add at least one public RSS feed URL before collecting."
                else:
                    try:
                        with Session(app.state.engine) as session:
                            rss_result = await collect_premium_rss_feeds(
                                session,
                                feed_urls=feed_urls,
                                settings=settings,
                            )
                    except Exception as exc:
                        error = redact_text(f"Premium RSS collection failed: {exc}")

        elif action == "add_manual":
            with Session(app.state.engine) as session:
                upsert_premium_note(
                    session,
                    url=form.get("url", ""),
                    title=form.get("title", ""),
                    publisher=form.get("publisher"),
                    public_summary=form.get("public_summary"),
                    user_note=form.get("user_note"),
                    tickers=form.get("tickers"),
                    importance=form.get("importance"),
                    status=form.get("status", "to_read"),
                )
                session.commit()
            message = "Premium reading item saved."

        elif action == "update_note":
            with Session(app.state.engine) as session:
                note = update_premium_note(
                    session,
                    form.get("note_id", ""),
                    user_note=form.get("user_note"),
                    tickers=form.get("tickers"),
                    importance=form.get("importance"),
                    status=form.get("status", "to_read"),
                )
                if note is None:
                    error = "Premium note was not found."
                else:
                    session.commit()
                    message = "Premium note updated."

        return templates.TemplateResponse(
            request,
            "premium_sources.html",
            {
                "settings": settings,
                "view": _premium_sources_view(
                    app,
                    message=message,
                    error=error,
                    rss_result=rss_result,
                ),
            },
        )

    @app.get("/dashboard/today", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_today(request: Request) -> HTMLResponse:
        with Session(app.state.engine) as session:
            view = _dashboard_view(session)
        return templates.TemplateResponse(
            request,
            "dashboard_today.html",
            {"settings": settings, "view": view},
        )

    @app.post("/dashboard/refresh", response_class=HTMLResponse, tags=["dashboard"])
    async def refresh_dashboard(request: Request) -> HTMLResponse:
        """Run configured sources and build a new brief after an explicit click."""
        collection_result: CollectOnceResult | None = None
        report_result: AiReportGenerationResult | None = None
        error: str | None = None
        _refresh_runtime_source_settings(app, settings)
        _refresh_runtime_llm_settings(app, settings)
        selected_sources = _configured_source_names(settings)

        try:
            with Session(app.state.engine) as session:
                if selected_sources:
                    collection_result = await collect_once(
                        session,
                        settings=settings,
                        sources=selected_sources,
                        trigger="dashboard_refresh",
                    )
                report_result = generate_ai_report_from_local_content(
                    session,
                    settings=settings,
                    reports_dir=_reports_dir(app),
                )
                view = _dashboard_view(session)
        except Exception as exc:
            error = redact_text(f"Brief refresh failed: {exc}")
            with Session(app.state.engine) as session:
                view = _dashboard_view(session)

        view["refresh"] = {
            "error": error,
            "source_count": len(selected_sources),
            "collection": _collect_once_result_view(collection_result),
            "report": _ai_report_result_view(report_result),
        }
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
            collection_runs = session.exec(select(CollectionRun)).all()
            collection_run_items = session.exec(select(CollectionRunItem)).all()
            report_events = _latest_structured_report_events(session)
        view = build_feed_view(
            items=filter_content_items(items, filters),
            filters=filters,
            report_events=report_events,
            collection_runs=collection_runs,
            collection_run_items=collection_run_items,
        )
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

    @app.post("/reports/generate-ai", response_class=HTMLResponse, tags=["dashboard"])
    def generate_ai_report(request: Request) -> HTMLResponse:
        message: str | None = None
        error: str | None = None
        result: AiReportGenerationResult | None = None
        _refresh_runtime_llm_settings(app, settings)
        try:
            with Session(app.state.engine) as session:
                result = generate_ai_report_from_local_content(
                    session,
                    settings=settings,
                    reports_dir=_reports_dir(app),
                )
                reports_view = build_reports_view(session.exec(select(Report)).all())
            message = (
                f"AI report generated from {result.source_item_count} local item(s): "
                f"{result.successful_summary_count} summarized, "
                f"{result.failed_summary_count} failed."
            )
        except Exception as exc:
            error = redact_text(f"AI report generation failed: {exc}")
            with Session(app.state.engine) as session:
                reports_view = build_reports_view(session.exec(select(Report)).all())

        reports_view["message"] = message
        reports_view["error"] = error
        reports_view["generate_result"] = _ai_report_result_view(result)
        return templates.TemplateResponse(
            request,
            "reports.html",
            {"settings": settings, "view": reports_view},
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
            report_events = session.exec(
                select(ReportEventRecord).where(ReportEventRecord.report_id == report_id)
            ).all()
            view = build_report_detail_view(
                report=report,
                sections=sections,
                report_events=report_events,
            )
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


def _dashboard_view(session: Session) -> dict[str, Any]:
    return build_dashboard_view(
        items=session.exec(select(ContentItem)).all(),
        reports=session.exec(select(Report)).all(),
        statuses=session.exec(select(SourceStatus).order_by(SourceStatus.source_name)).all(),
        report_events=_latest_structured_report_events(session),
    )


def _latest_structured_report_events(session: Session) -> list[ReportEventRecord]:
    reports = list(session.exec(select(Report).order_by(desc("created_at"))).all())
    events = list(session.exec(select(ReportEventRecord)).all())
    for report in reports:
        report_events = [event for event in events if event.report_id == report.id]
        if report_events:
            return report_events
    return []


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
        "has_api_key": (
            saved_settings.has_api_key
            or settings.llm_api_key is not None
            or settings.deepseek_api_key is not None
        ),
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
        "finance_news_mcp_url": saved_settings.finance_news_mcp_url
        or settings.finance_news_mcp_url
        or "",
        "finance_news_mcp_sources": saved_settings.finance_news_mcp_sources
        or settings.finance_news_mcp_sources,
        "finance_news_mcp_items_per_source": saved_settings.finance_news_mcp_items_per_source
        or settings.finance_news_mcp_items_per_source,
        "sec_user_agent": saved_settings.sec_user_agent or settings.sec_user_agent or "",
        "sec_cik": saved_settings.sec_cik or settings.sec_cik,
        "arxiv_search_query": saved_settings.arxiv_search_query or settings.arxiv_search_query,
        "github_query": saved_settings.github_query or settings.github_query,
        "has_github_token": saved_settings.has_github_token or settings.github_token is not None,
        "has_fred_api_key": saved_settings.has_fred_api_key or settings.fred_api_key is not None,
        "fred_series_id": saved_settings.fred_series_id or settings.fred_series_id,
        "has_newsapi_key": saved_settings.has_newsapi_key or settings.newsapi_key is not None,
        "newsapi_query": saved_settings.newsapi_query or settings.newsapi_query,
        "gdelt_query": saved_settings.gdelt_query or settings.gdelt_query,
        "has_alphavantage_api_key": saved_settings.has_alphavantage_api_key
        or settings.alphavantage_api_key is not None,
        "alphavantage_topics": saved_settings.alphavantage_topics
        or settings.alphavantage_topics,
        "has_finnhub_api_key": saved_settings.has_finnhub_api_key
        or settings.finnhub_api_key is not None,
        "finnhub_category": saved_settings.finnhub_category or settings.finnhub_category,
        "has_reddit_access_token": saved_settings.has_reddit_access_token
        or settings.reddit_access_token is not None,
        "reddit_user_agent": saved_settings.reddit_user_agent
        or settings.reddit_user_agent
        or "",
        "reddit_query": saved_settings.reddit_query or settings.reddit_query,
        "reddit_subreddit": saved_settings.reddit_subreddit
        or settings.reddit_subreddit
        or "",
        "has_youtube_api_key": saved_settings.has_youtube_api_key
        or settings.youtube_api_key is not None,
        "youtube_query": saved_settings.youtube_query or settings.youtube_query,
        "has_x_bearer_token": saved_settings.has_x_bearer_token
        or settings.x_bearer_token is not None,
        "x_query": saved_settings.x_query or settings.x_query,
        "has_stackexchange_key": saved_settings.has_stackexchange_key
        or settings.stackexchange_key is not None,
        "stackexchange_query": saved_settings.stackexchange_query or settings.stackexchange_query,
        "stackexchange_site": saved_settings.stackexchange_site or settings.stackexchange_site,
        "has_quantconnect_user_id": saved_settings.has_quantconnect_user_id
        or settings.quantconnect_user_id is not None,
        "has_quantconnect_token": saved_settings.has_quantconnect_token
        or settings.quantconnect_token is not None,
        "quantconnect_organization_id": saved_settings.quantconnect_organization_id
        or settings.quantconnect_organization_id
        or "",
        "source_options": _source_options(settings),
        "run_result": _collect_once_result_view(run_result),
        "run_error": run_error,
    }


def _premium_sources_view(
    app: FastAPI,
    *,
    message: str | None = None,
    error: str | None = None,
    rss_result: PremiumRssCollectResult | None = None,
) -> dict[str, Any]:
    values = read_env_values(_env_path(app))
    with Session(app.state.engine) as session:
        notes = list(
            session.exec(
                select(PremiumSourceNote).order_by(
                    desc("importance"),
                    desc("created_at"),
                )
            ).all()
        )
    return {
        "message": message,
        "error": error,
        "rss_result": _premium_rss_result_view(rss_result),
        "premium_rss_feed_urls": values.get("PREMIUM_RSS_FEED_URLS", ""),
        "notes": [_premium_note_view(note) for note in notes],
        "note_count": len(notes),
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


def _refresh_runtime_llm_settings(app: FastAPI, settings: Settings) -> None:
    values = read_env_values(_env_path(app))
    saved = load_llm_settings(_env_path(app))
    settings.llm_provider = saved.provider
    settings.llm_base_url = saved.base_url
    settings.llm_model = saved.model
    settings.llm_api_key = SecretStr(values["LLM_API_KEY"]) if values.get("LLM_API_KEY") else None
    settings.deepseek_api_key = (
        SecretStr(values["DEEPSEEK_API_KEY"]) if values.get("DEEPSEEK_API_KEY") else None
    )


def _refresh_runtime_source_settings(app: FastAPI, settings: Settings) -> None:
    saved = load_source_settings(_env_path(app))
    _apply_runtime_source_settings(app, settings, saved, form={})
    values = read_env_values(_env_path(app))
    secret_fields = {
        "github_token": "GITHUB_TOKEN",
        "fred_api_key": "FRED_API_KEY",
        "newsapi_key": "NEWSAPI_KEY",
        "alphavantage_api_key": "ALPHAVANTAGE_API_KEY",
        "finnhub_api_key": "FINNHUB_API_KEY",
        "reddit_access_token": "REDDIT_ACCESS_TOKEN",
        "youtube_api_key": "YOUTUBE_API_KEY",
        "x_bearer_token": "X_BEARER_TOKEN",
        "stackexchange_key": "STACKEXCHANGE_KEY",
        "quantconnect_user_id": "QUANTCONNECT_USER_ID",
        "quantconnect_token": "QUANTCONNECT_TOKEN",
    }
    for attribute_name, env_key in secret_fields.items():
        value = values.get(env_key, "")
        setattr(settings, attribute_name, SecretStr(value) if value else None)


def _configured_source_names(settings: Settings) -> tuple[str, ...]:
    """Select sources that have the minimum configuration for an explicit refresh."""
    ready = {
        "rss": bool(settings.rss_feed_urls),
        "finance_news_mcp": bool(settings.finance_news_mcp_url),
        "sec_edgar": bool(settings.sec_user_agent),
        "arxiv": True,
        "github": True,
        "fred": settings.fred_api_key is not None,
        "newsapi": settings.newsapi_key is not None,
        "gdelt": True,
        "alphavantage": settings.alphavantage_api_key is not None,
        "finnhub": settings.finnhub_api_key is not None,
        "reddit": settings.reddit_access_token is not None and bool(settings.reddit_user_agent),
        "youtube": settings.youtube_api_key is not None,
        "x_api": settings.x_bearer_token is not None,
        "stackexchange": True,
        "quantconnect": (
            settings.quantconnect_user_id is not None
            and settings.quantconnect_token is not None
        ),
    }
    return tuple(source_name for source_name in SUPPORTED_SOURCES if ready[source_name])


def _apply_runtime_source_settings(
    app: FastAPI,
    settings: Settings,
    saved: SavedSourceSettings,
    *,
    form: dict[str, str],
) -> None:
    values = read_env_values(_env_path(app))
    settings.rss_feed_urls = saved.rss_feed_urls
    settings.finance_news_mcp_url = saved.finance_news_mcp_url or None
    settings.finance_news_mcp_sources = saved.finance_news_mcp_sources
    settings.finance_news_mcp_items_per_source = saved.finance_news_mcp_items_per_source
    settings.sec_user_agent = saved.sec_user_agent or None
    settings.sec_cik = saved.sec_cik
    settings.arxiv_search_query = saved.arxiv_search_query
    settings.github_query = saved.github_query
    settings.fred_series_id = saved.fred_series_id
    settings.newsapi_query = saved.newsapi_query
    settings.gdelt_query = saved.gdelt_query
    settings.alphavantage_topics = saved.alphavantage_topics
    settings.finnhub_category = saved.finnhub_category
    settings.reddit_user_agent = saved.reddit_user_agent or None
    settings.reddit_query = saved.reddit_query
    settings.reddit_subreddit = saved.reddit_subreddit or None
    settings.youtube_query = saved.youtube_query
    settings.x_query = saved.x_query
    settings.stackexchange_query = saved.stackexchange_query
    settings.stackexchange_site = saved.stackexchange_site
    settings.quantconnect_organization_id = saved.quantconnect_organization_id or None
    _apply_secret_setting(settings, "github_token", values, "GITHUB_TOKEN", form)
    _apply_secret_setting(settings, "fred_api_key", values, "FRED_API_KEY", form)
    _apply_secret_setting(settings, "newsapi_key", values, "NEWSAPI_KEY", form)
    _apply_secret_setting(settings, "alphavantage_api_key", values, "ALPHAVANTAGE_API_KEY", form)
    _apply_secret_setting(settings, "finnhub_api_key", values, "FINNHUB_API_KEY", form)
    _apply_secret_setting(settings, "reddit_access_token", values, "REDDIT_ACCESS_TOKEN", form)
    _apply_secret_setting(settings, "youtube_api_key", values, "YOUTUBE_API_KEY", form)
    _apply_secret_setting(settings, "x_bearer_token", values, "X_BEARER_TOKEN", form)
    _apply_secret_setting(settings, "stackexchange_key", values, "STACKEXCHANGE_KEY", form)
    _apply_secret_setting(settings, "quantconnect_user_id", values, "QUANTCONNECT_USER_ID", form)
    _apply_secret_setting(settings, "quantconnect_token", values, "QUANTCONNECT_TOKEN", form)


def _env_path(app: FastAPI) -> Path:
    return getattr(app.state, "env_file_path", Path(".env"))


def _reports_dir(app: FastAPI) -> Path:
    return getattr(app.state, "reports_dir", Path("data/reports"))


def _parse_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _selected_source_names(form: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        source_name
        for source_name in SUPPORTED_SOURCES
        if form.get(f"source_{source_name}") == "on"
    )


def _source_options(settings: Settings) -> list[dict[str, Any]]:
    labels = {
        "rss": "RSS",
        "finance_news_mcp": "Finance News MCP",
        "sec_edgar": "SEC EDGAR",
        "arxiv": "arXiv",
        "github": "GitHub",
        "fred": "FRED",
        "newsapi": "NewsAPI",
        "gdelt": "GDELT",
        "alphavantage": "Alpha Vantage",
        "finnhub": "Finnhub",
        "reddit": "Reddit",
        "youtube": "YouTube",
        "x_api": "X API",
        "stackexchange": "Quant StackExchange",
        "quantconnect": "QuantConnect",
    }
    configured_sources = set(_configured_source_names(settings))
    return [
        {
            "name": source_name,
            "field": f"source_{source_name}",
            "label": labels[source_name],
            "checked": source_name in configured_sources,
        }
        for source_name in SUPPORTED_SOURCES
    ]


def _apply_secret_setting(
    settings: Settings,
    attribute_name: str,
    values: dict[str, str],
    env_key: str,
    form: dict[str, str],
) -> None:
    clear_key = f"clear_{env_key.lower()}"
    if form.get(clear_key) == "on":
        setattr(settings, attribute_name, None)
    elif values.get(env_key):
        setattr(settings, attribute_name, SecretStr(values[env_key]))


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


def _ai_report_result_view(result: AiReportGenerationResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "report_id": result.report.report_id,
        "source_item_count": result.source_item_count,
        "ranked_event_count": result.ranked_event_count,
        "successful_summary_count": result.successful_summary_count,
        "failed_summary_count": result.failed_summary_count,
        "html_path": result.report.html_path,
    }


def _premium_rss_result_view(result: PremiumRssCollectResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "collector_count": len(result.summaries),
        "queued_items": result.queued_items,
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


def _premium_note_view(note: PremiumSourceNote) -> dict[str, Any]:
    return {
        "id": note.id,
        "url": note.url,
        "title": note.title,
        "publisher": note.publisher,
        "public_summary": note.public_summary,
        "user_note": note.user_note,
        "tickers_text": ", ".join(note.tickers),
        "importance": note.importance,
        "status": note.status,
        "storage_policy": note.storage_policy,
    }
