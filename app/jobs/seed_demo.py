"""Seed local demo data for dashboard review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.collectors.base import (
    CollectedItem,
    CollectorRunResult,
    CollectorStatus,
    persist_collector_result,
)
from app.core.config import get_settings
from app.core.timezones import ensure_utc, utc_now
from app.db.models import ContentItem, DeliveryLog, Report, ReportEventRecord, ReportSection
from app.db.session import create_db_engine, init_db
from app.jobs.run_daily import run_daily
from app.llm.schemas import EventSummary, SummaryResult

DEMO_REPORT_TITLE = "Demo Quant Intel Brief"


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    """Summary of demo data written to local storage."""

    report_id: str
    content_items: int
    source_statuses: int


def seed_demo(session: Session, *, now: datetime | None = None) -> DemoSeedResult:
    """Seed deterministic local demo data without external API calls."""
    seed_time = ensure_utc(now or utc_now())
    _delete_existing_demo_report(session)
    for collector_result in _collector_results(seed_time):
        persist_collector_result(session, collector_result)
    result = run_daily(
        session,
        summary_results=_summary_results(session),
        report_date=seed_time.date(),
        report_title=DEMO_REPORT_TITLE,
    )
    _apply_demo_tags(session)
    session.commit()

    content_count = len(
        session.exec(
            select(ContentItem).where(ContentItem.source_item_id.startswith("demo-"))
        ).all()
    )
    source_count = len({item.source_name for item in _demo_items(seed_time)})
    return DemoSeedResult(
        report_id=result.report_id,
        content_items=content_count,
        source_statuses=source_count,
    )


def main() -> None:
    """Seed the configured local database with demo data."""
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    with Session(engine) as session:
        result = seed_demo(session)
    print(  # noqa: T201
        f"Seeded demo dashboard data: {result.content_items} items, "
        f"{result.source_statuses} sources, report {result.report_id}."
    )


def _collector_results(seed_time: datetime) -> list[CollectorRunResult]:
    results: list[CollectorRunResult] = []
    for item in _demo_items(seed_time):
        results.append(
            CollectorRunResult(
                source_name=item.source_name,
                source_type=_source_type(item.source_name),
                display_name=_display_name(item.source_name),
                status=CollectorStatus.SUCCESS,
                items=[item],
                fetched_at=seed_time,
            )
        )
    return results


def _demo_items(seed_time: datetime) -> list[CollectedItem]:
    return [
        CollectedItem(
            source_name="fred",
            source_item_id="demo-fed-1",
            url="https://example.test/demo/fed-policy-path",
            title="FOMC minutes point to a slower disinflation path",
            summary="Fed officials discussed inflation persistence and rate-path uncertainty.",
            excerpt="Metadata-only demo excerpt about Fed policy, inflation, and rates.",
            publisher="Federal Reserve demo",
            published_at=seed_time - timedelta(hours=2),
        ),
        CollectedItem(
            source_name="newsapi",
            source_item_id="demo-options-1",
            url="https://example.test/demo/spy-options-skew",
            title="SPY options skew rises ahead of CPI",
            summary="Options desks reported higher implied volatility and downside skew in SPY.",
            excerpt="Metadata-only demo excerpt about SPY options skew and CPI risk.",
            publisher="Market News demo",
            published_at=seed_time - timedelta(hours=3),
        ),
        CollectedItem(
            source_name="sec_edgar",
            source_item_id="demo-sec-1",
            url="https://example.test/demo/nvda-10q",
            title="NVDA files 10-Q with stronger data-center revenue",
            summary="The filing metadata highlights data-center revenue and margin commentary.",
            excerpt="Metadata-only demo excerpt about an SEC filing signal.",
            publisher="SEC EDGAR demo",
            published_at=seed_time - timedelta(hours=5),
        ),
        CollectedItem(
            source_name="arxiv",
            source_item_id="demo-arxiv-1",
            url="https://example.test/demo/intraday-factor-decay",
            title="arXiv paper evaluates intraday factor decay",
            summary="A research paper studies intraday factor decay and microstructure effects.",
            excerpt="Metadata-only demo excerpt about factor research.",
            publisher="arXiv demo",
            published_at=seed_time - timedelta(hours=6),
        ),
        CollectedItem(
            source_name="github",
            source_item_id="demo-github-1",
            url="https://example.test/demo/backtesting-engine",
            title="Open-source backtesting engine adds slippage model",
            summary="A GitHub project added a slippage model for event-driven backtests.",
            excerpt="Metadata-only demo excerpt about a backtesting library update.",
            publisher="GitHub demo",
            published_at=seed_time - timedelta(hours=8),
        ),
        CollectedItem(
            source_name="reddit",
            source_item_id="demo-reddit-1",
            url="https://example.test/demo/vol-regime-filters",
            title="Quant community discusses volatility regime filters",
            summary="Community metadata points to discussion of volatility filters and drawdowns.",
            excerpt="Metadata-only demo excerpt about community heat.",
            publisher="Reddit demo",
            published_at=seed_time - timedelta(hours=9),
        ),
    ]


def _summary_results(session: Session) -> list[SummaryResult]:
    summary_specs = [
        (
            "demo-fed",
            "Fed path uncertainty remains a macro input",
            "FOMC metadata points to persistent inflation debate and rate-path uncertainty.",
            "Macro and rates assumptions can affect factor, duration, and volatility workflows.",
            "This is demo data; live interpretation requires real source verification.",
            ["https://example.test/demo/fed-policy-path"],
            [],
            ["macro"],
            ["risk_model"],
        ),
        (
            "demo-options",
            "SPY options skew rises ahead of CPI",
            "Demo market metadata shows higher implied volatility and downside skew in SPY.",
            "Options skew can inform volatility monitoring and ETF risk dashboards.",
            "This is demo data and not a live market reading.",
            ["https://example.test/demo/spy-options-skew"],
            ["SPY"],
            ["etf", "options"],
            ["volatility"],
        ),
        (
            "demo-sec",
            "NVDA filing metadata flags data-center revenue",
            "Demo SEC metadata highlights revenue and margin commentary in a 10-Q filing.",
            "Filing metadata can feed equity watchlists and fundamental-event tracking.",
            "This is demo data and does not reproduce filing text.",
            ["https://example.test/demo/nvda-10q"],
            ["NVDA"],
            ["equity"],
            [],
        ),
        (
            "demo-research",
            "Intraday factor decay paper enters the research queue",
            "Demo arXiv metadata describes research on factor decay and microstructure effects.",
            "Research metadata can guide model-review and backtest-prioritization workflows.",
            "This is demo data; the paper is represented by metadata only.",
            ["https://example.test/demo/intraday-factor-decay"],
            [],
            ["equity"],
            ["factor", "microstructure"],
        ),
        (
            "demo-github",
            "Backtesting engine adds slippage modeling",
            "Demo GitHub metadata points to a new slippage model in a backtesting project.",
            "Developer activity can surface tooling changes relevant to systematic research.",
            "This is demo data and does not include repository code.",
            ["https://example.test/demo/backtesting-engine"],
            [],
            [],
            ["backtesting"],
        ),
        (
            "demo-community",
            "Community metadata highlights volatility regime filters",
            "Demo community metadata shows discussion of volatility filters and drawdown controls.",
            "Community heat can be useful as a weak signal when paired with stronger sources.",
            "This is demo data and not a source of investment advice.",
            ["https://example.test/demo/vol-regime-filters"],
            [],
            ["options"],
            ["volatility"],
        ),
    ]
    return [
        SummaryResult(
            success=True,
            ranked_item_id=f"ranked-{index}",
            event_id=event_id,
            ranked_score=95.0 - index,
            summary=EventSummary(
                event_id=event_id,
                headline=headline,
                headline_zh=_demo_translation(event_id, "headline"),
                factual_summary=factual_summary,
                factual_summary_zh=_demo_translation(event_id, "summary"),
                market_relevance=market_relevance,
                market_relevance_zh=_demo_translation(event_id, "relevance"),
                uncertainty=uncertainty,
                what_to_watch=["Review the next cited update from this source."],
                what_to_watch_zh=["关注该来源下一次有引用依据的更新。"],
                source_credibility="medium",
                source_credibility_reason="This is deterministic local demo metadata.",
                source_ids=[_content_id_for_url(session, source_urls[0])],
                source_urls=source_urls,
                tickers=tickers,
                assets=assets,
                quant_topics=topics,
            ),
        )
        for index, (
            event_id,
            headline,
            factual_summary,
            market_relevance,
            uncertainty,
            source_urls,
            tickers,
            assets,
            topics,
        ) in enumerate(summary_specs, start=1)
    ]


def _content_id_for_url(session: Session, url: str) -> str:
    item = session.exec(select(ContentItem).where(ContentItem.url == url)).one()
    return item.id


def _demo_translation(event_id: str, field: str) -> str:
    translations = {
        "demo-fed": {
            "headline": "美联储路径的不确定性仍是重要宏观变量",
            "summary": "模拟数据表明，通胀争论仍在影响市场对利率路径的判断。",
            "relevance": "利率预期会影响因子、久期和波动率策略。",
        },
        "demo-options": {
            "headline": "CPI 公布前 SPY 期权偏斜上升",
            "summary": "模拟市场数据反映 SPY 隐含波动率和下行保护需求上升。",
            "relevance": "期权偏斜可帮助观察 ETF 风险情绪。",
        },
        "demo-sec": {
            "headline": "NVDA 文件显示数据中心收入信号",
            "summary": "模拟 SEC 元数据突出显示了收入和利润率相关信息。",
            "relevance": "公司文件是跟踪基本面事件的重要来源。",
        },
        "demo-research": {
            "headline": "日内因子衰减研究进入观察清单",
            "summary": "模拟 arXiv 元数据介绍了因子衰减和市场微观结构研究。",
            "relevance": "该研究可用于决定模型复核和回测优先级。",
        },
        "demo-github": {
            "headline": "回测引擎新增滑点建模",
            "summary": "模拟 GitHub 元数据显示一个回测项目加入了滑点模型。",
            "relevance": "开发活动可能揭示系统化研究工具的变化。",
        },
        "demo-community": {
            "headline": "社区开始关注波动率状态过滤器",
            "summary": "模拟社区元数据显示，波动率过滤和回撤控制讨论升温。",
            "relevance": "社区热度只能作为需要其他来源验证的弱信号。",
        },
    }
    return translations[event_id][field]


def _apply_demo_tags(session: Session) -> None:
    tag_map = {
        "demo-fed-1": ([], ["macro"], ["risk_model"]),
        "demo-options-1": (["SPY"], ["etf", "options"], ["volatility"]),
        "demo-sec-1": (["NVDA"], ["equity"], []),
        "demo-arxiv-1": ([], ["equity"], ["factor", "microstructure"]),
        "demo-github-1": ([], [], ["backtesting"]),
        "demo-reddit-1": ([], ["options"], ["volatility"]),
    }
    for source_item_id, (tickers, assets, topics) in tag_map.items():
        item = session.exec(
            select(ContentItem).where(ContentItem.source_item_id == source_item_id)
        ).one_or_none()
        if item is None:
            continue
        item.tickers = tickers
        item.assets = assets
        item.quant_topics = topics


def _delete_existing_demo_report(session: Session) -> None:
    reports = list(session.exec(select(Report).where(Report.title == DEMO_REPORT_TITLE)).all())
    report_ids = [report.id for report in reports]
    for event in session.exec(select(ReportEventRecord)).all():
        if event.report_id in report_ids:
            session.delete(event)
    for section in session.exec(select(ReportSection)).all():
        if section.report_id in report_ids:
            session.delete(section)
    for log in session.exec(select(DeliveryLog)).all():
        if log.report_id in report_ids:
            session.delete(log)
    for report in reports:
        session.delete(report)
    session.commit()


def _source_type(source_name: str) -> str:
    return {
        "fred": "macro",
        "newsapi": "news",
        "sec_edgar": "filing",
        "arxiv": "research",
        "github": "developer",
        "reddit": "community",
    }.get(source_name, "demo")


def _display_name(source_name: str) -> str:
    return {
        "fred": "FRED Demo",
        "newsapi": "NewsAPI Demo",
        "sec_edgar": "SEC EDGAR Demo",
        "arxiv": "arXiv Demo",
        "github": "GitHub Demo",
        "reddit": "Reddit Demo",
    }.get(source_name, source_name)


__all__ = ["DEMO_REPORT_TITLE", "DemoSeedResult", "main", "seed_demo"]


if __name__ == "__main__":
    main()
