"""Report generation package."""

from app.reports.generator import DailyReport, ReportEvent, ReportSectionData, generate_daily_report
from app.reports.templates import render_email_report

__all__ = [
    "DailyReport",
    "ReportEvent",
    "ReportSectionData",
    "generate_daily_report",
    "render_email_report",
]
