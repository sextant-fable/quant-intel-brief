"""SEC EDGAR submissions metadata collector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.collectors.base import (
    CollectedItem,
    CollectorConfig,
    CollectorRunResult,
    CollectorStatus,
    SourceCollector,
    canonicalize_url_for_storage,
    compact_text_for_storage,
    hash_text,
    parse_datetime_utc,
)
from app.core.timezones import utc_now


class SecEdgarCollector(SourceCollector):
    """Collect SEC EDGAR filing metadata from submissions JSON."""

    endpoint_template = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(
        self,
        user_agent: str | None = None,
        cik: str = "0000320193",
        config: CollectorConfig | None = None,
        endpoint_template: str | None = None,
    ) -> None:
        super().__init__(
            source_name="sec_edgar",
            source_type="official_api",
            display_name="SEC EDGAR",
            config=config,
        )
        self.user_agent = user_agent
        self.cik = cik.zfill(10)
        self.endpoint_template = endpoint_template or self.endpoint_template

    @property
    def endpoint(self) -> str:
        return self.endpoint_template.format(cik=self.cik)

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.user_agent:
            return self._result(CollectorStatus.FAILED, "SEC_USER_AGENT is required.", fetched_at)

        fetch = await self.fetch_json(
            self.endpoint,
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "SEC EDGAR request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        items = self._recent_filings_to_items(data, fetched_at)
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} SEC filing(s).", fetched_at, items)

    def _recent_filings_to_items(
        self,
        data: dict[str, Any],
        fetched_at: datetime,
    ) -> list[CollectedItem]:
        filings = data.get("filings")
        recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
        if not isinstance(recent, dict):
            return []

        accession_numbers = _list_value(recent, "accessionNumber")
        forms = _list_value(recent, "form")
        filing_dates = _list_value(recent, "filingDate")
        report_dates = _list_value(recent, "reportDate")
        primary_documents = _list_value(recent, "primaryDocument")
        company_name = compact_text_for_storage(data.get("name")) or self.cik
        items: list[CollectedItem] = []

        for index, accession in enumerate(accession_numbers[: self.config.max_items]):
            accession_number = compact_text_for_storage(accession)
            if not accession_number:
                continue
            form = _get_index(forms, index) or "FILING"
            filing_date = _get_index(filing_dates, index)
            report_date = _get_index(report_dates, index)
            primary_document = _get_index(primary_documents, index) or ""
            filing_url = _filing_url(self.cik, accession_number, primary_document)
            title = f"{company_name} {form} filing {accession_number}"
            summary = compact_text_for_storage(
                "Filing date: "
                f"{filing_date or 'unknown'}; "
                f"report date: {report_date or 'unknown'}"
            )
            items.append(
                CollectedItem(
                    source_name=self.source_name,
                    source_item_id=accession_number,
                    url=filing_url,
                    canonical_url=canonicalize_url_for_storage(filing_url),
                    title=title,
                    summary=summary,
                    excerpt=summary,
                    publisher="SEC EDGAR",
                    published_at=parse_datetime_utc(filing_date),
                    fetched_at=fetched_at,
                    raw_payload_hash=hash_text("|".join([accession_number, title])),
                    raw_metadata={
                        "cik": self.cik,
                        "company_name": company_name,
                        "form": form,
                        "filing_date": filing_date,
                        "report_date": report_date,
                        "primary_document": primary_document,
                    },
                )
            )

        return items

    def _result(
        self,
        status: CollectorStatus,
        message: str,
        fetched_at: datetime,
        items: list[CollectedItem] | None = None,
    ) -> CollectorRunResult:
        return CollectorRunResult(
            source_name=self.source_name,
            source_type=self.source_type,
            display_name=self.display_name,
            status=status,
            message=message,
            source_url=self.endpoint,
            fetched_at=fetched_at,
            items=items or [],
        )


def _list_value(source: dict[str, Any], key: str) -> list[Any]:
    value = source.get(key)
    return value if isinstance(value, list) else []


def _get_index(values: list[Any], index: int) -> str | None:
    if index >= len(values):
        return None
    return compact_text_for_storage(values[index])


def _filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_path = str(int(cik))
    accession_path = accession_number.replace("-", "")
    if primary_document:
        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik_path}/{accession_path}/{primary_document}"
        )
    return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/"


__all__ = ["SecEdgarCollector"]
