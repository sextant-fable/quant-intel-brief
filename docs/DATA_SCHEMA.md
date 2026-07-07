# Data Schema

Shared SQLModel table definitions are implemented in `app/db/models.py`. Phase 1 adds collector persistence helpers that populate source, raw item, content item, and source status rows from metadata-only collector results. Phase 2 adds official/public API collectors that emit the same normalized metadata shape. Phase 3 extends that shape to configured social, community, video, developer-platform, and premium metadata sources. Phase 4 adds deterministic canonicalization, source references, and retention metadata.

## Planned Core Entities

- `Source`: configured upstream data source.
- `RawItem`: source-specific metadata and raw payload reference as fetched.
- `ContentItem`: normalized article, post, filing, paper, video, or dataset signal.
- `EntityTag`: ticker, asset, organization, person, market, or topic.
- `Cluster`: deduplicated group of related items.
- `RankedItem`: item or cluster with ranking score and explanation.
- `Report`: generated daily brief.
- `ReportSection`: grouped report content.
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
