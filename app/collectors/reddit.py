"""Reddit metadata collector."""

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


class RedditCollector(SourceCollector):
    """Collect Reddit post metadata from the official OAuth API."""

    endpoint = "https://oauth.reddit.com/search"

    def __init__(
        self,
        access_token: str | None = None,
        user_agent: str | None = None,
        query: str = "quant finance OR algotrading",
        subreddit: str | None = None,
        config: CollectorConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            source_name="reddit",
            source_type="community_api",
            display_name="Reddit",
            config=config,
        )
        self.access_token = access_token
        self.user_agent = user_agent
        self.query = query
        self.subreddit = subreddit
        self.endpoint = endpoint or self.endpoint

    async def collect(self, client: httpx.AsyncClient | None = None) -> CollectorRunResult:
        fetched_at = utc_now()
        if not self.access_token or not self.user_agent:
            return self._result(
                CollectorStatus.FAILED,
                "Reddit OAuth access token and user agent are required.",
                fetched_at,
            )

        endpoint = (
            f"https://oauth.reddit.com/r/{self.subreddit}/search"
            if self.subreddit
            else self.endpoint
        )
        fetch = await self.fetch_json(
            endpoint,
            params={
                "q": self.query,
                "restrict_sr": bool(self.subreddit),
                "limit": self.config.max_items,
            },
            headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": self.user_agent},
            client=client,
        )
        if fetch.status != CollectorStatus.SUCCESS:
            return self._result(fetch.status, fetch.message or "Reddit request failed.", fetched_at)

        data = fetch.data if isinstance(fetch.data, dict) else {}
        listing_value = data.get("data")
        listing: dict[str, Any] = listing_value if isinstance(listing_value, dict) else {}
        children_value = listing.get("children")
        children = children_value if isinstance(children_value, list) else []
        items = [item for child in children if (item := self._post_to_item(child, fetched_at))]
        status = CollectorStatus.SUCCESS if items else CollectorStatus.EMPTY
        return self._result(status, f"Parsed {len(items)} Reddit post(s).", fetched_at, items)

    def _post_to_item(self, child: Any, fetched_at: datetime) -> CollectedItem | None:
        if not isinstance(child, dict):
            return None
        post_value = child.get("data")
        post: dict[str, Any] = post_value if isinstance(post_value, dict) else {}
        title = compact_text_for_storage(post.get("title"))
        permalink = compact_text_for_storage(post.get("permalink"), max_chars=2000)
        post_id = compact_text_for_storage(post.get("id"))
        if not title or not permalink or not post_id:
            return None

        url = f"https://www.reddit.com{permalink}"
        summary = compact_text_for_storage(post.get("link_flair_text"))
        subreddit = compact_text_for_storage(post.get("subreddit")) or "unknown"
        return CollectedItem(
            source_name=self.source_name,
            source_item_id=post_id,
            url=url,
            canonical_url=canonicalize_url_for_storage(url),
            title=title,
            summary=summary,
            excerpt=summary,
            author=compact_text_for_storage(post.get("author")),
            publisher=f"r/{subreddit}",
            published_at=parse_datetime_utc(post.get("created_utc")),
            fetched_at=fetched_at,
            raw_payload_hash=hash_text("|".join([post_id, title, summary or ""])),
            raw_metadata={
                "subreddit": post.get("subreddit"),
                "score": post.get("score"),
                "num_comments": post.get("num_comments"),
                "upvote_ratio": post.get("upvote_ratio"),
                "is_self": post.get("is_self"),
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


__all__ = ["RedditCollector"]
