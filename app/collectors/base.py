"""Base collector scaffold."""

from __future__ import annotations


class SourceCollector:
    """Base class placeholder for source collectors."""

    source_name: str

    async def collect(self):
        """Collect raw items once implementation begins."""
        raise NotImplementedError
