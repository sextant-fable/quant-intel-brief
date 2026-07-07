# Data Sources

This document tracks planned source adapters and their legal/technical requirements.

| Source | Module | Status | Access | Notes |
| --- | --- | --- | --- | --- |
| RSS | `app/collectors/rss.py` | Scaffold | Public feeds | Respect feed terms and robots guidance. |
| NewsAPI | `app/collectors/newsapi.py` | Scaffold | API key | Store key in `.env`. |
| GDELT | `app/collectors/gdelt.py` | Scaffold | Public/API | Confirm current API limits before use. |
| Alpha Vantage | `app/collectors/alphavantage.py` | Scaffold | API key | Use only permitted endpoints. |
| Finnhub | `app/collectors/finnhub.py` | Scaffold | API key | Check plan limits. |
| GitHub | `app/collectors/github.py` | Scaffold | Token optional | Use API terms-compliant access. |
| Reddit | `app/collectors/reddit.py` | Scaffold | OAuth | Respect subreddit and API rules. |
| YouTube | `app/collectors/youtube.py` | Scaffold | API key | Metadata only unless transcript use is permitted. |
| X API | `app/collectors/x_api.py` | Scaffold | Bearer token | Follow API and redistribution terms. |
| arXiv | `app/collectors/arxiv.py` | Scaffold | Public API | Preserve paper IDs and links. |
| SEC EDGAR | `app/collectors/sec_edgar.py` | Scaffold | User agent | Follow SEC fair-access policy. |
| FRED | `app/collectors/fred.py` | Scaffold | API key | Macroeconomic indicators. |
| Stack Exchange | `app/collectors/stackexchange.py` | Scaffold | API key optional | Developer signal source. |
| QuantConnect | `app/collectors/quantconnect.py` | Scaffold | Token | Confirm permitted endpoints. |
| Premium Browser | `app/collectors/premium_browser.py` | Scaffold | User-authorized | No paywall bypass or redistribution. |

## Source Rules

- Prefer official APIs and documented feeds.
- Confirm current terms and rate limits before implementing each adapter.
- Keep credentials in `.env`; never commit secrets, cookies, or session exports.
- Store metadata, source links, compact excerpts, and hashes by default.
- Do not store full text unless the source terms and user authorization clearly permit it.
