# Data Schema

Shared SQLModel table definitions are implemented in `app/db/models.py`. Phase 1 adds collector persistence helpers that populate source, raw item, content item, and source status rows from metadata-only collector results.

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
