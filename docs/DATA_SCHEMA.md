# Data Schema

Shared SQLModel table definitions are implemented in `app/db/models.py`. Phase 1 adds collector persistence helpers that populate source, raw item, content item, and source status rows from metadata-only collector results. Phase 2 adds official/public API collectors that emit the same normalized metadata shape. Phase 3 extends that shape to configured social, community, video, developer-platform, and premium metadata sources. Phase 4 adds deterministic canonicalization, source references, and retention metadata. Phase 5 adds deterministic event clusters, event-item relationships, and rule-based tags. Phase 6 adds ranked items with visible score components and explanations. Phase 7 adds structured LLM summary schemas without adding summary persistence tables. Phase 8 adds in-memory report payloads and email delivery result schemas before persistence wiring.

## Planned Core Entities

- `Source`: configured upstream data source.
- `RawItem`: source-specific metadata and raw payload reference as fetched.
- `ContentItem`: normalized article, post, filing, paper, video, or dataset signal.
- `CollectionRun`: one explicit collection invocation with its trigger, sources, counts, and UTC timestamps.
- `CollectionRunItem`: links every item observed in a collection invocation to that run, including known items seen again.
- `EntityTag`: ticker, asset, organization, person, market, or topic.
- `Cluster`: deduplicated group of related items.
- `EventItem`: relationship between a cluster and a content item.
- `RankedItem`: item or cluster with ranking score and explanation.
- `Report`: generated daily brief.
- `ReportSection`: grouped report content.
- `ReportEventRecord`: structured Top 10 event content persisted for dashboard, feed, and report views.
- `DeliveryLog`: email or notification delivery result.

## Normalized Item Fields

- `id`
- `source_name`
- `source_item_id`
- `url`
- `canonical_url`
- `title`
- `summary`
- `excerpt`
- `author`
- `publisher`
- `published_at`
- `fetched_at`
- `language`
- `tickers`
- `assets`
- `quant_topics`
- `raw_payload_hash`
- `source_terms_checked_at`
- `storage_policy`
- `retain_for_days`
- `retention_until`
- `source_reference`

## Schema Rules

- Store timestamps in UTC.
- Use source `published_at` for freshness and ranking; collection timestamps only record when collection happened.
- Keep source timestamps separately from fetch timestamps.
- Preserve source URLs and canonical URLs.
- Do not store secret request headers or private cookies.
- Do not store full text by default. Use compact excerpts and source references unless permitted.
- Make uniqueness explicit with `source_name` plus `source_item_id` or canonical URL.

## Phase 0 Tables

- `sources`
- `raw_items`
- `content_items`
- `entity_tags`
- `clusters`
- `ranked_items`
- `reports`
- `report_sections`
- `delivery_logs`
- `source_statuses`
- `event_items`

## Phase 1 Persistence Rules

- Collector results are persisted through `persist_collector_result`.
- `Source` rows are keyed by source name.
- `RawItem` rows are keyed by source ID plus source item ID.
- `ContentItem` rows are keyed by source name plus source item ID, with duplicate canonical URLs collapsed deterministically.
- `SourceStatus` stores the last returned status for a collector run.
- RSS metadata stores compact excerpts only; no article body or premium full text is stored.

## Phase 2 Metadata Rules

- Public/official API collectors emit `CollectedItem` records only.
- API keys, bearer tokens, user agents, and request headers are never persisted.
- JSON/XML fixture responses are parsed into compact summaries, source IDs, URLs, timestamps, publisher/author fields, and safe source metadata.
- SEC EDGAR stores filing metadata and filing links only; filing body text is not downloaded or stored.
- arXiv stores paper metadata and links only; PDFs are not downloaded or stored.

## Phase 3 Metadata Rules

- Social, video, community, and premium collectors emit `CollectedItem` records only.
- Premium metadata is filtered by `PremiumMetadataExtractor` before storage.
- Forbidden premium text fields include body, content, full text, article text, transcripts, HTML, and Markdown.
- Platform credentials, authorization headers, cookies, and local browser profile data are never persisted.

## Phase 4 Storage Hygiene Rules

- Canonical URLs are normalized by `app/dedup/canonicalize.py`.
- Raw and content items store `storage_policy="metadata_only"` by default.
- Raw and content items include source-reference metadata with URL, canonical URL, and payload hash.
- Raw and content items include `retain_for_days=30` and `retention_until` for local history cleanup.
- Article extraction defaults to no text extraction and refuses full-text storage requests.

## Phase 5 Event And Tagging Rules

- `Cluster` stores deterministic event fingerprints, canonical URL, member item IDs, source names, and aggregate tags.
- `EventItem` stores event-to-content-item membership with confidence and provenance.
- `EntityTag` records source, ticker, asset, and quant-theme tags with confidence and rule provenance.
- Ticker extraction is conservative and ignores ambiguous uppercase terms unless they are known tickers or explicit cashtags.
- Tagging is rule-based only; no LLM tagging is used in Phase 5.

## Phase 6 Ranking Rules

- `RankedItem` stores score, component dictionary, explanation, and ranking timestamp.
- Score components include source credibility, publication-time recency, cross-source corroboration, asset importance, research signal, and capped community heat.
- Ranking explanations must remain informational and non-advisory.
- Ranking is deterministic for a fixed fixture set and does not call an LLM.

## Daily Brief Selection Rules

- Daily candidates require a real `published_at`; `fetched_at` never makes an old item current.
- Finance News MCP publishers are stored as separate sources such as `finance_news_mcp_bloomberg` and `finance_news_mcp_wsj`.
- Candidate extraction is capped per source before the global pool is assembled.
- News and community items use a 72-hour default window; SEC and arXiv use explicit longer windows.
- Old Stack Exchange questions remain available in the long-term Research Feed but are excluded from the daily brief.
- Top 10 selection allows at most two events per source and three per market section, and attempts to cover all five sections before filling remaining positions by score.

## Phase 7 Summary Rules

- `EventSummary` is a Pydantic output schema for source-grounded LLM results.
- Summary outputs must cite only evidence source IDs and URLs passed into the prompt.
- Missing evidence produces an explicit insufficient-evidence result without calling an LLM.
- Invalid citations or advisory language fail validation and preserve ranked-event context for review.
- Phase 7 does not add report tables, email delivery, scheduler behavior, or dashboard business views.

## Phase 8 Report Rules

- `DailyReport`, `ReportSectionData`, and `ReportEvent` are in-memory report payload schemas.
- Report events require source IDs and source URLs before rendering.
- Failed or uncited summaries are skipped and reflected in the source coverage note.
- Email delivery returns preview/dry-run or mocked provider results before any live delivery wiring.
- Phase 8 does not add scheduler behavior or dashboard business views.

## Phase 9 Dashboard Rules

- Dashboard views read existing local `ContentItem`, `Report`, `ReportSection`, and `SourceStatus` rows.
- Feed filters run against local normalized metadata only.
- Source status messages are redacted before JSON or HTML rendering.
- Phase 9 does not add new tables, external calls, email sending, or scheduler behavior.

## Phase 10 Operations Rules

- Daily job orchestration persists local `Report`, `ReportSection`, and optional `DeliveryLog` rows.
- Manual runs accept injected collector and summary results; default command runs without external calls.
- Retention cleanup removes expired local rows while preserving the configured history window.
- Scheduler wiring is optional and disabled unless `ENABLE_SCHEDULER=true`.

## Bilingual Report Event Rules

- New reports persist structured `ReportEventRecord` rows without altering legacy report rows.
- English fields remain primary. Chinese fields translate only the headline, factual takeaway, market relevance, and watch points.
- Each event stores rank, market section, affected tickers/assets, uncertainty, source confidence, and paired source IDs/URLs.
- The dashboard and feed reuse the same persisted event instead of generating unsourced page-specific explanations.
