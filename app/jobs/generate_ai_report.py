"""Generate a local AI report from already-collected content."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import Settings
from app.db.models import Cluster, ContentItem, RankedItem
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
    max_events: int = 8,
) -> AiReportGenerationResult:
    """Summarize top-ranked local content into a persisted draft report."""
    items = _recent_content_items(session, limit=max_source_items)
    clusters = _cluster_tagged_items(items)
    ranked_items = rank_clusters(clusters)[:max_events]
    cluster_by_id = {cluster.id: cluster for cluster in clusters}
    summary_results = _summarize_ranked_items(
        ranked_items=ranked_items,
        clusters=cluster_by_id,
        source_items=items,
        settings=settings,
        client=client,
    )
    report = run_daily(
        session,
        summary_results=summary_results,
        report_date=report_date,
        report_title="Quant Intel Brief",
        reports_dir=reports_dir,
    )
    return AiReportGenerationResult(
        report=report,
        source_item_count=len(items),
        ranked_event_count=len(ranked_items),
        successful_summary_count=sum(1 for result in summary_results if result.success),
        failed_summary_count=sum(1 for result in summary_results if not result.success),
    )


def _recent_content_items(session: Session, *, limit: int) -> list[ContentItem]:
    return list(
        session.exec(
            select(ContentItem).order_by(text("fetched_at DESC")).limit(limit)
        ).all()
    )


def _cluster_tagged_items(items: list[ContentItem]) -> list[Cluster]:
    for item in items:
        tag_item_entities(item)
    return cluster_items(items).clusters


def _summarize_ranked_items(
    *,
    ranked_items: list[RankedItem],
    clusters: dict[str, Cluster],
    source_items: list[ContentItem],
    settings: Settings,
    client: JsonCompletionClient | None,
) -> list[SummaryResult]:
    if not ranked_items:
        return []

    summary_client = client or OpenAICompatibleClient(
        OpenAICompatibleClientConfig.from_settings(settings)
    )
    results: list[SummaryResult] = []
    for ranked_item in ranked_items:
        if ranked_item.cluster_id is None:
            continue
        cluster = clusters.get(ranked_item.cluster_id)
        if cluster is None:
            continue
        results.append(
            summarize_ranked_event(
                ranked_item,
                cluster,
                source_items,
                summary_client,
            )
        )
    return results


__all__ = [
    "AiReportGenerationResult",
    "generate_ai_report_from_local_content",
]
