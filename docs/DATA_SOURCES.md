# Data Sources

This document tracks planned source adapters and their legal/technical requirements.

| Source | Module | Status | Access | Notes |
| --- | --- | --- | --- | --- |
| RSS | `app/collectors/rss.py` | Phase 1 implemented | Public feeds | Metadata-only RSS/Atom parsing with mocked HTTP tests. Respect feed terms and robots guidance. |
| NewsAPI | `app/collectors/newsapi.py` | Phase 2 implemented | API key | Metadata-only `/v2/everything` adapter. Store key in `.env`. |
| GDELT | `app/collectors/gdelt.py` | Phase 2 implemented | Public/API | Metadata-only DOC API adapter. Confirm current API limits before live use. |
| Alpha Vantage | `app/collectors/alphavantage.py` | Phase 2 implemented | API key | Metadata-only `NEWS_SENTIMENT` adapter. Use only permitted endpoints. |
| Finnhub | `app/collectors/finnhub.py` | Phase 2 implemented | API key | Metadata-only market news adapter. Check plan limits. |
| GitHub | `app/collectors/github.py` | Phase 2 implemented | Token optional | Metadata-only repository search adapter. Use API terms-compliant access. |
| Reddit | `app/collectors/reddit.py` | Scaffold | OAuth | Respect subreddit and API rules. |
| YouTube | `app/collectors/youtube.py` | Scaffold | API key | Metadata only unless transcript use is permitted. |
| X API | `app/collectors/x_api.py` | Scaffold | Bearer token | Follow API and redistribution terms. |
| arXiv | `app/collectors/arxiv.py` | Phase 2 implemented | Public API | Preserve paper IDs and links; do not download PDFs. |
| SEC EDGAR | `app/collectors/sec_edgar.py` | Phase 2 implemented | User agent | Metadata-only submissions JSON adapter. Follow SEC fair-access policy. |
| FRED | `app/collectors/fred.py` | Phase 2 implemented | API key | Metadata-only macro observation adapter. |
| Stack Exchange | `app/collectors/stackexchange.py` | Scaffold | API key optional | Developer signal source. |
| QuantConnect | `app/collectors/quantconnect.py` | Scaffold | Token | Confirm permitted endpoints. |
| Premium Browser | `app/collectors/premium_browser.py` | Scaffold | User-authorized | No paywall bypass or redistribution. |

## Source Rules

- Prefer official APIs and documented feeds.
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
- These collectors are not scheduled and are not wired to dashboard actions yet.
