"""Deterministic URL and source-reference normalization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "spm",
    }
)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Stable reference to source material without storing full text."""

    url: str
    canonical_url: str
    payload_hash: str

    def to_metadata(self) -> dict[str, str]:
        return {
            "url": self.url,
            "canonical_url": self.canonical_url,
            "payload_hash": self.payload_hash,
        }


def canonicalize_url(url: str) -> str:
    """Normalize a URL for deterministic storage and duplicate checks."""
    stripped_url = url.strip()
    parts = urlsplit(stripped_url)
    scheme = (parts.scheme or "https").lower()
    hostname = (parts.hostname or "").lower()
    port = _normalized_port(parts.scheme, parts.port)
    netloc = f"{hostname}:{port}" if port else hostname
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = _normalized_query(parts.query)
    return urlunsplit((scheme, netloc, path, query, ""))


def source_payload_hash(*parts: str | None) -> str:
    """Hash source metadata fragments without storing the source payload."""
    normalized = "\x1f".join(part.strip() for part in parts if part)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_source_reference(
    url: str,
    *hash_parts: str | None,
    canonical_url: str | None = None,
) -> SourceReference:
    """Build a compact source reference from URL and metadata fragments."""
    normalized_url = canonical_url or canonicalize_url(url)
    payload_hash = source_payload_hash(normalized_url, *hash_parts)
    return SourceReference(url=url, canonical_url=normalized_url, payload_hash=payload_hash)


def _normalized_port(scheme: str, port: int | None) -> int | None:
    if port is None:
        return None
    normalized_scheme = (scheme or "https").lower()
    if normalized_scheme == "http" and port == 80:
        return None
    if normalized_scheme == "https" and port == 443:
        return None
    return port


def _normalized_query(query: str) -> str:
    pairs = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=False)
        if not _is_tracking_key(key)
    ]
    return urlencode(sorted(pairs), doseq=True)


def _is_tracking_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in TRACKING_QUERY_KEYS or lowered.startswith(TRACKING_QUERY_PREFIXES)


__all__ = [
    "SourceReference",
    "build_source_reference",
    "canonicalize_url",
    "source_payload_hash",
]
