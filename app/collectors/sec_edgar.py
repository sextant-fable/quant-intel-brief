"""SEC EDGAR collector scaffold."""

from __future__ import annotations

from app.collectors.base import SourceCollector


class SecEdgarCollector(SourceCollector):
    """Placeholder SEC EDGAR collector."""

    source_name = "sec_edgar"
