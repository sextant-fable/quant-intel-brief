"""QuantConnect metadata collector."""

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


class QuantConnectCollector(SourceCollector):
    """Collect user-authorized QuantConnect project metadata."""

    endpoint = "https://www.quantconnect.com/api/v2/projects/read"

    def __init__(
        self,
        user_id: str | None = None,
        api_token: str | None = None,
        organization_id: str | None = None,
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="quantconnect",
            source_type="developer_api",
            display_name="QuantConnect",
            config=config,
        )
        self.user_id = user_id
        self.api_token = api_token
        self.organization_id = organization_id
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.user_id or not self.api_token:
            return self._result(
                CollectorStatus.FAILED,
                "QUANTCONNECT_USER_ID and QUANTCONNECT_TOKEN are required.",
                fetched_at,
            )

        params = {"organizationId": self.organization_id} if self.organization_id else None
        fetch = await self.fetch_json(
            self.endpoint,
            params=params,
            headers={
                "X-QC-User-Id": self.user_id,
                "X-QC-Api-Token": self.api_token,
            },
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(
                fetch.status,
                fetch.message or "QuantConnect request failed.",
                fetched_at,
            )

        data = fetch.data if isinstance(fetch.data, dict) else {}
        if data.get("success") is False:
            return self._result(CollectorStatus.FAILED, str(data.get("errors")), fetched_at)

        projects_value = data.get("projects")
        projects = projects_value if isinstance(projects_value, list) else []
        items = [
            item
            for project in projects
            if (item := self._project_to_item(project, fetched_at))
        ]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(
            status,
            f"Parsed {len(items)} QuantConnect project(s).",
            fetched_at,
            items,
        )

    def _project_to_item(self, project: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(project, dict):
            return None
        project_id = compact_text_for_storage(project.get("projectId") or project.get("id"))
        name = compact_text_for_storage(project.get("name"))
        if not project_id or not name:
            return None

        url = f"https://www.quantconnect.com/project/{project_id}"
        summary = compact_text_for_storage(project.get("description"))
        modified = project.get("modified") or project.get("modifiedTime")
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=project_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=name,
            summary=summary,
            excerpt=summary,
            publisher="QuantConnect",
            published_at=parse_datetime_utc(modified),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([project_id, name, summary or ""])),
            raw_metadata={
                "organization_id": self.organization_id,
                "language": project.get("language"),
                "created": project.get("created"),
                "modified": modified,
            },
        )

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


__all__ = ["QuantConnectCollector"]
