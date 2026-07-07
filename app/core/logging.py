"""Logging helpers with simple secret redaction."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)(=|:)\s*[^,\s]+"),
    re.compile(r"(?i)(authorization)(=|:)\s*[^,\s]+"),
)


def redact_text(message: str, extra_values: Iterable[str] | None = None) -> str:
    """Redact common secret-looking values from a log message."""
    redacted = message
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)} ***", redacted)
    for value in extra_values or ():
        if value:
            redacted = redacted.replace(value, "***")
    return redacted


class RedactingFilter(logging.Filter):
    """Logging filter that redacts common credential patterns."""

    def __init__(self, extra_values: Iterable[str] | None = None) -> None:
        super().__init__()
        self._extra_values = tuple(extra_values or ())

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self._extra_values)
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging for local app execution."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root_logger.addHandler(handler)

    if not any(isinstance(filter_, RedactingFilter) for filter_ in root_logger.filters):
        root_logger.addFilter(RedactingFilter())
