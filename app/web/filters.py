"""Dashboard filtering helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date as Date

from pydantic import BaseModel, Field

from app.db.models import ContentItem


class DashboardFilters(BaseModel):
    """Filters accepted by local dashboard feed views."""

    date: Date | None = None
    source: str | None = None
    ticker: str | None = None
    asset_class: str | None = None
    quant_theme: str | None = None
    errors: list[str] = Field(default_factory=list)

    @property
    def has_active_filters(self) -> bool:
        return any(
            [
                self.date,
                self.source,
                self.ticker,
                self.asset_class,
                self.quant_theme,
            ]
        )


def dashboard_filters_from_query(
    *,
    date_value: str | None = None,
    source: str | None = None,
    ticker: str | None = None,
    asset_class: str | None = None,
    quant_theme: str | None = None,
) -> DashboardFilters:
    """Build filters from query parameters without raising on bad input."""
    errors: list[str] = []
    parsed_date = None
    if date_value:
        try:
            parsed_date = Date.fromisoformat(date_value)
        except ValueError:
            errors.append("Invalid date filter. Use YYYY-MM-DD.")

    return DashboardFilters(
        date=parsed_date,
        source=_clean(source),
        ticker=_clean(ticker.upper() if ticker else None),
        asset_class=_clean(asset_class.lower() if asset_class else None),
        quant_theme=_clean(quant_theme.lower() if quant_theme else None),
        errors=errors,
    )


def filter_content_items(
    items: Iterable[ContentItem],
    filters: DashboardFilters,
) -> list[ContentItem]:
    """Apply dashboard filters to normalized content items."""
    return [item for item in items if _matches_filters(item, filters)]


def _matches_filters(item: ContentItem, filters: DashboardFilters) -> bool:
    if filters.date:
        item_date = item.published_at or item.fetched_at
        if item_date.date() != filters.date:
            return False
    if filters.source and item.source_name.lower() != filters.source.lower():
        return False
    if filters.ticker and filters.ticker.upper() not in {ticker.upper() for ticker in item.tickers}:
        return False
    if filters.asset_class and filters.asset_class.lower() not in {
        asset.lower() for asset in item.assets
    }:
        return False
    if filters.quant_theme and filters.quant_theme.lower() not in {
        topic.lower() for topic in item.quant_topics
    }:
        return False
    return True


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = ["DashboardFilters", "dashboard_filters_from_query", "filter_content_items"]
