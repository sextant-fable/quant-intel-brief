"""Premium-source metadata boundary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FORBIDDEN_PREMIUM_TEXT_KEYS = frozenset(
    {
        "body",
        "content",
        "full_text",
        "article_text",
        "transcript",
        "html",
        "markdown",
    }
)
ALLOWED_PREMIUM_METADATA_KEYS = frozenset(
    {
        "source_item_id",
        "url",
        "canonical_url",
        "title",
        "summary",
        "excerpt",
        "author",
        "publisher",
        "published_at",
        "source_name",
        "tags",
    }
)


class PremiumExtractionError(ValueError):
    """Raised when premium data includes disallowed full-text fields."""


@dataclass(frozen=True, slots=True)
class PremiumMetadataExtractor:
    """Accept only user-provided premium metadata, never premium full text."""

    def extract_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        forbidden = [
            key for key in FORBIDDEN_PREMIUM_TEXT_KEYS if record.get(key) not in (None, "")
        ]
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise PremiumExtractionError(f"Premium full-text fields are not permitted: {names}")

        return {key: record[key] for key in ALLOWED_PREMIUM_METADATA_KEYS if key in record}


__all__ = [
    "ALLOWED_PREMIUM_METADATA_KEYS",
    "FORBIDDEN_PREMIUM_TEXT_KEYS",
    "PremiumExtractionError",
    "PremiumMetadataExtractor",
]
