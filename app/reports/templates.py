"""Report template rendering helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.generator import DailyReport


def render_email_report(report: DailyReport, *, template_dir: Path | None = None) -> str:
    """Render the daily report as self-contained HTML email markup."""
    environment = _template_environment(str(template_dir) if template_dir else None)
    return environment.get_template("email_report.html").render(report=report)


@lru_cache(maxsize=4)
def _template_environment(template_dir: str | None = None) -> Environment:
    root = Path(template_dir) if template_dir else Path(__file__).resolve().parents[2] / "templates"
    return Environment(
        loader=FileSystemLoader(root),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


__all__ = ["render_email_report"]
