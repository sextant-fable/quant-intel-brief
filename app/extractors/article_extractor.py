"""Safe article metadata and compact-excerpt extraction boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from app.dedup.canonicalize import SourceReference, build_source_reference

DEFAULT_EXCERPT_CHARS = 500


class ExtractionNotPermittedError(ValueError):
    """Raised when extraction would violate the no-full-text boundary."""


@dataclass(frozen=True, slots=True)
class ArticleExtractionPolicy:
    """Controls what text, if any, may be extracted."""

    allow_excerpt: bool = False
    store_full_text: bool = False
    max_excerpt_chars: int = DEFAULT_EXCERPT_CHARS


@dataclass(frozen=True, slots=True)
class ExtractedArticleMetadata:
    """Metadata extracted without archiving full source text."""

    url: str
    canonical_url: str
    title: str | None
    excerpt: str | None
    source_reference: SourceReference


def extract_article_metadata(
    url: str,
    *,
    html: str | None = None,
    text: str | None = None,
    title: str | None = None,
    policy: ArticleExtractionPolicy | None = None,
) -> ExtractedArticleMetadata:
    """Extract permitted metadata and compact excerpts from user-provided content."""
    active_policy = policy or ArticleExtractionPolicy()
    if active_policy.store_full_text:
        raise ExtractionNotPermittedError("Full-text article storage is not permitted.")

    cleaned_title = _compact_text(title, max_chars=220)
    excerpt = None
    if active_policy.allow_excerpt:
        source_text = text if text is not None else _html_to_text(html)
        excerpt = _compact_text(source_text, max_chars=active_policy.max_excerpt_chars)

    reference = build_source_reference(url, cleaned_title, excerpt)
    return ExtractedArticleMetadata(
        url=url,
        canonical_url=reference.canonical_url,
        title=cleaned_title,
        excerpt=excerpt,
        source_reference=reference,
    )


def _html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _compact_text(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    suffix = "..."
    cutoff = max(0, max_chars - len(suffix))
    candidate = cleaned[:cutoff].rstrip()
    boundary = candidate.rfind(" ")
    if boundary > 0:
        candidate = candidate[:boundary]
    return f"{candidate}{suffix}"


__all__ = [
    "ArticleExtractionPolicy",
    "ExtractedArticleMetadata",
    "ExtractionNotPermittedError",
    "extract_article_metadata",
]
