"""Generate a local AI report from already-collected content."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.timezones import ensure_utc, utc_now
from app.db.models import Cluster, ContentItem
from app.dedup.clusterer import cluster_items
from app.enrichers.quant_tagger import tag_item_entities
from app.jobs.run_daily import DailyRunResult, run_daily
from app.llm.client import (
    JsonCompletionClient,
    OpenAICompatibleClient,
    OpenAICompatibleClientConfig,
)
from app.llm.schemas import SummaryResult
from app.llm.summarize import summarize_ranked_event
from app.ranking.ranker import rank_clusters
from app.ranking.selection import (
    BriefSelectionPolicy,
    SelectedRankedEvent,
    cluster_publication_times,
    select_daily_candidates,
    select_diverse_top_events,
)


@dataclass(frozen=True, slots=True)
class AiReportGenerationResult:
    """Summary of one user-triggered AI report generation."""

    report: DailyRunResult
    source_item_count: int
    ranked_event_count: int
    successful_summary_count: int
    failed_summary_count: int


def generate_ai_report_from_local_content(
    session: Session,
    *,
    settings: Settings,
    client: JsonCompletionClient | None = None,
    report_date: date | None = None,
    reports_dir: Path | None = None,
    max_source_items: int = 120,
    max_events: int = 10,
    now: datetime | None = None,
) -> AiReportGenerationResult:
    """Summarize top-ranked local content into a persisted draft report."""
    active_now = ensure_utc(now or utc_now())
    policy = _selection_policy(settings)
    items = _recent_content_items(
        session,
        limit=max_source_items,
        now=active_now,
        policy=policy,
    )
    clusters = _cluster_tagged_items(items)
    cluster_by_id = {cluster.id: cluster for cluster in clusters}
    ranked_items = rank_clusters(
        clusters,
        now=active_now,
        published_at_by_cluster=cluster_publication_times(clusters, items),
    )
    selected_events = select_diverse_top_events(
        ranked_items,
        cluster_by_id,
        limit=max_events,
        policy=policy,
    )
    summary_results = _summarize_ranked_items(
        selected_events=selected_events,
        clusters=cluster_by_id,
        source_items=items,
        settings=settings,
        client=client,
    )
    report = run_daily(
        session,
        summary_results=summary_results,
        report_date=report_date,
        report_title="Pre-Market Brief",
        reports_dir=reports_dir,
    )
    return AiReportGenerationResult(
        report=report,
        source_item_count=len(items),
        ranked_event_count=len(selected_events),
        successful_summary_count=sum(1 for result in summary_results if result.success),
        failed_summary_count=sum(1 for result in summary_results if not result.success),
    )


def _recent_content_items(
    session: Session,
    *,
    limit: int,
    now: datetime,
    policy: BriefSelectionPolicy,
) -> list[ContentItem]:
    return select_daily_candidates(
        session.exec(select(ContentItem)).all(),
        limit=limit,
        now=now,
        policy=policy,
    )


def _cluster_tagged_items(items: list[ContentItem]) -> list[Cluster]:
    for item in items:
        tag_item_entities(item)
    return cluster_items(items).clusters


def _summarize_ranked_items(
    *,
    selected_events: list[SelectedRankedEvent],
    clusters: dict[str, Cluster],
    source_items: list[ContentItem],
    settings: Settings,
    client: JsonCompletionClient | None,
) -> list[SummaryResult]:
    if not selected_events:
        return []

    summary_client = client or OpenAICompatibleClient(
        OpenAICompatibleClientConfig.from_settings(settings)
    )
    results: list[SummaryResult] = []
    for selected_event in selected_events:
        ranked_item = selected_event.ranked_item
        if ranked_item.cluster_id is None:
            continue
        cluster = clusters.get(ranked_item.cluster_id)
        if cluster is None:
            continue
        result = summarize_ranked_event(
            ranked_item,
            cluster,
            source_items,
            summary_client,
        )
        result.section_key = selected_event.section_key
        results.append(result)
    return results


def _selection_policy(settings: Settings) -> BriefSelectionPolicy:
    return BriefSelectionPolicy(
        items_per_source=settings.brief_candidate_items_per_source,
        news_window_hours=settings.brief_news_window_hours,
        community_window_hours=settings.brief_community_window_hours,
        sec_window_days=settings.brief_sec_window_days,
        arxiv_window_days=settings.brief_arxiv_window_days,
        research_window_days=settings.brief_research_window_days,
        default_window_days=settings.brief_default_window_days,
        top_source_limit=settings.brief_top_source_limit,
        top_section_limit=settings.brief_top_section_limit,
    )


__all__ = [
    "AiReportGenerationResult",
    "generate_ai_report_from_local_content",
]
