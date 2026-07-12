# Data Sources

This document tracks planned source adapters and their legal/technical requirements.

| Source | Module | Status | Access | Notes |
| --- | --- | --- | --- | --- |
| RSS | `app/collectors/rss.py` | Phase 1 implemented | Public feeds | Metadata-only RSS/Atom parsing with mocked HTTP tests. Respect feed terms and robots guidance. |
| Finance News MCP | `app/collectors/finance_news_mcp.py` | Post-MVP implemented | Independent Streamable HTTP MCP | Calls `get_latest_finance_news` per publisher and stores public RSS metadata only. The MCP process is user-managed and optional. |
| NewsAPI | `app/collectors/newsapi.py` | Phase 2 implemented | API key | Metadata-only `/v2/everything` adapter. Store key in `.env`. |
| GDELT | `app/collectors/gdelt.py` | Phase 2 implemented | Public/API | Metadata-only DOC API adapter. Confirm current API limits before live use. |
| Alpha Vantage | `app/collectors/alphavantage.py` | Phase 2 implemented | API key | Metadata-only `NEWS_SENTIMENT` adapter. Use only permitted endpoints. |
| Finnhub | `app/collectors/finnhub.py` | Phase 2 implemented | API key | Metadata-only market news adapter. Check plan limits. |
| GitHub | `app/collectors/github.py` | Phase 2 implemented | Token optional | Metadata-only repository search adapter. Use API terms-compliant access. |
| Reddit | `app/collectors/reddit.py` | Phase 3 implemented | OAuth | Metadata-only post adapter. Respect subreddit and API rules. |
| YouTube | `app/collectors/youtube.py` | Phase 3 implemented | API key | Metadata-only video search adapter; transcripts are not collected. |
| X API | `app/collectors/x_api.py` | Phase 3 implemented | Bearer token | Metadata-only recent-search adapter. Follow API and redistribution terms. |
| arXiv | `app/collectors/arxiv.py` | Phase 2 implemented | Public API | Preserve paper IDs and links; do not download PDFs. |
| SEC EDGAR | `app/collectors/sec_edgar.py` | Phase 2 implemented | User agent | Metadata-only submissions JSON adapter. Follow SEC fair-access policy. |
| FRED | `app/collectors/fred.py` | Phase 2 implemented | API key | Metadata-only macro observation adapter. |
| Stack Exchange | `app/collectors/stackexchange.py` | Phase 3 implemented | API key optional | Disabled by default; metadata-only question search adapter. |
| QuantConnect | `app/collectors/quantconnect.py` | Phase 3 implemented | User ID and token | Metadata-only project adapter. Confirm permitted endpoints before live use. |
| Premium Browser | `app/collectors/premium_browser.py` | Phase 3 implemented | User-authorized | Disabled by default; accepts metadata records only. No paywall bypass or redistribution. |
| Premium Sources | `app/premium/queue.py` | Backlog implemented | Public RSS/manual links | Public metadata plus user notes only; no login cookies, paywall bypass, or full-text storage. |

## Source Rules

- Prefer official APIs and documented feeds.
- Treat third-party MCP servers as independent, untrusted metadata providers; validate and normalize every returned field.
- Confirm current terms and rate limits before implementing each adapter.
- Keep credentials in `.env`; never commit secrets, cookies, or session exports.
- Store metadata, source links, compact excerpts, and hashes by default.
- Do not store full text unless the source terms and user authorization clearly permit it.

## Phase 1 RSS Behavior

- `RssCollector` accepts an explicit feed URL and does not run automatically from the app shell.
- HTTP fetches use shared timeout, retry, and HTTP 429 handling from `app/collectors/base.py`.
- Parsed records include source IDs, URLs, canonical URLs, titles, compact excerpts, authors, publisher/feed name, publication time, fetch time, language, tags, and payload hashes.
- Duplicate source IDs or canonical URLs are skipped deterministically within a run.
- Tests use local XML fixtures and `respx`; no live feed requests are made in tests.

## Phase 2 Public And Official API Behavior

- Implemented adapters: NewsAPI, GDELT, Alpha Vantage, Finnhub, FRED, SEC EDGAR, arXiv, and GitHub.
- API-key or user-agent requirements are enforced before HTTP requests for key-gated sources.
- All tests use fixture responses and `respx`; no live API calls are made in tests.
- Stored records are source IDs, canonical links, publication/fetch timestamps, compact excerpts or summaries, and safe metadata only.
- RSS, SEC EDGAR, arXiv, GitHub, FRED, NewsAPI, GDELT, Alpha Vantage, Finnhub, Reddit, YouTube, X API, Quant StackExchange, and QuantConnect can be run through `python -m app.jobs.collect_once --sources ...` or the local `/settings/sources` page.
- Manual collection is not scheduled and is not wired to dashboard actions.

## Phase 3 Social, Community, Video, And Premium Behavior

- Implemented adapters: Reddit, YouTube, X API, Stack Exchange, QuantConnect, and premium metadata intake.
- Reddit, YouTube, X, and QuantConnect fail before HTTP unless required local credentials are configured.
- Stack Exchange is API-key optional and is enabled only when explicitly selected for a manual run.
- Premium metadata intake is disabled by default and requires explicit authorization for each configured run.
- Premium metadata rejects full-text fields such as article bodies, transcripts, HTML, Markdown, or exported content.
- Premium Sources stores reading links, public summaries, and user-authored notes only.
- Tests use fixtures and `respx`; no live social, video, community, premium, or platform API calls are made in tests.
