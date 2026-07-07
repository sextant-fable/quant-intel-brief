# Data Schema

Shared SQLModel table definitions are implemented in `app/db/models.py`. These are schema foundations for later phases; collectors and business pipeline behavior are not implemented in Phase 0.

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
