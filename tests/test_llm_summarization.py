"""Phase 7 OpenAI-compatible summarization tests."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.db.models import Cluster, ContentItem, RankedItem
from app.llm.client import (
    DeepSeekClient,
    DeepSeekClientConfig,
    LlmClientError,
    MissingLlmApiKeyError,
    OpenAICompatibleClient,
    OpenAICompatibleClientConfig,
)
from app.llm.prompts import build_event_summary_messages
from app.llm.schemas import EventEvidence, EventSummary
from app.llm.summarize import summarize_ranked_event


class FakeSummaryClient:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.payload


def _cluster() -> Cluster:
    return Cluster(
        id="event-1",
        canonical_title="ETF volatility surface update",
        item_ids=["content-1"],
        source_names=["newsapi"],
        tickers=["SPY"],
        assets=["etf", "options"],
        quant_topics=["volatility"],
    )


def _ranked_item() -> RankedItem:
    return RankedItem(
        id="ranked-1",
        cluster_id="event-1",
        score=72.5,
        score_components={"source_credibility": 0.2, "recency": 0.1},
        explanation="Informational importance score.",
    )


def _content_item() -> ContentItem:
    return ContentItem(
        id="content-1",
        source_name="newsapi",
        source_item_id="source-1",
        url="https://example.test/etf-vol",
        title="ETF volatility surface update",
        excerpt="ETF options desks reported higher implied volatility monitoring.",
    )


def _summary_payload() -> dict[str, Any]:
    return {
        "event_id": "event-1",
        "headline": "ETF volatility monitoring drew attention",
        "factual_summary": (
            "The provided source says ETF options desks monitored implied volatility."
        ),
        "market_relevance": "This is relevant as a volatility and ETF market-structure signal.",
        "uncertainty": "Only one source record was provided.",
        "source_ids": ["content-1"],
        "source_urls": ["https://example.test/etf-vol"],
        "tickers": ["SPY"],
        "assets": ["etf", "options"],
        "quant_topics": ["volatility"],
        "insufficient_evidence": False,
    }


def test_prompt_construction_includes_evidence_and_anti_hallucination_rules() -> None:
    evidence = [
        EventEvidence(
            source_id="content-1",
            url="https://example.test/etf-vol",
            title="ETF volatility surface update",
            excerpt="Compact evidence.",
        )
    ]

    messages = build_event_summary_messages(_ranked_item(), _cluster(), evidence)
    payload = json.loads(messages[1]["content"])

    assert messages[0]["role"] == "system"
    assert payload["event"]["event_id"] == "event-1"
    assert payload["evidence"][0]["source_id"] == "content-1"
    assert any("Do not add prices" in rule for rule in payload["rules"])
    assert "properties" in payload["required_schema"]


def test_structured_response_validation_requires_schema_fields() -> None:
    with pytest.raises(ValidationError):
        EventSummary.model_validate({"event_id": "event-1"})


def test_missing_evidence_returns_insufficient_evidence_without_llm_call() -> None:
    client = FakeSummaryClient(payload=_summary_payload())

    result = summarize_ranked_event(_ranked_item(), _cluster(), [], client)

    assert result.success is True
    assert result.summary is not None
    assert result.summary.insufficient_evidence is True
    assert client.calls == []


def test_mocked_deepseek_success_validates_grounded_summary() -> None:
    client = FakeSummaryClient(payload=_summary_payload())

    result = summarize_ranked_event(_ranked_item(), _cluster(), [_content_item()], client)

    assert result.success is True
    assert result.summary is not None
    assert result.summary.source_ids == ["content-1"]
    assert len(client.calls) == 1


def test_mocked_deepseek_failure_preserves_ranked_event_context() -> None:
    client = FakeSummaryClient(error=LlmClientError("fixture outage"))

    result = summarize_ranked_event(_ranked_item(), _cluster(), [_content_item()], client)

    assert result.success is False
    assert result.ranked_item_id == "ranked-1"
    assert result.event_id == "event-1"
    assert result.ranked_score == 72.5
    assert "fixture outage" in (result.error_message or "")


def test_anti_hallucination_rejects_unknown_sources_and_advisory_language() -> None:
    unknown_source = _summary_payload() | {"source_ids": ["not-provided"]}
    unknown_result = summarize_ranked_event(
        _ranked_item(),
        _cluster(),
        [_content_item()],
        FakeSummaryClient(payload=unknown_source),
    )
    advice_payload = _summary_payload() | {"market_relevance": "Investors should buy this ETF."}
    advice_result = summarize_ranked_event(
        _ranked_item(),
        _cluster(),
        [_content_item()],
        FakeSummaryClient(payload=advice_payload),
    )

    assert unknown_result.success is False
    assert "source IDs" in (unknown_result.error_message or "")
    assert advice_result.success is False
    assert "advisory" in (advice_result.error_message or "")


def test_openai_compatible_client_decodes_mocked_json() -> None:
    payload = _summary_payload()

    class FakeCompletions:
        def create(self, **_: Any) -> Any:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload))),
                ]
            )

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = OpenAICompatibleClient(
        OpenAICompatibleClientConfig(
            api_key=None,
            provider="glm",
            base_url="https://example.test",
            model="glm-demo",
        ),
        openai_client=fake_openai,
    )

    assert client.complete_json([{"role": "user", "content": "{}"}]) == payload


def test_openai_compatible_client_uses_generic_settings_first() -> None:
    settings = Settings(
        llm_provider="openai",
        llm_api_key=SecretStr("generic-key"),
        llm_base_url="https://api.openai.test/v1",
        llm_model="gpt-demo",
        deepseek_api_key=SecretStr("deepseek-key"),
        deepseek_base_url="https://deepseek.test",
        deepseek_model="deepseek-demo",
    )

    config = OpenAICompatibleClientConfig.from_settings(settings)

    assert config.provider == "openai"
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "generic-key"
    assert config.base_url == "https://api.openai.test/v1"
    assert config.model == "gpt-demo"


def test_deepseek_aliases_remain_supported() -> None:
    settings = Settings(
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        deepseek_api_key=SecretStr("deepseek-key"),
        deepseek_base_url="https://deepseek.test",
        deepseek_model="deepseek-demo",
    )

    config = DeepSeekClientConfig.from_settings(settings)

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "deepseek-key"
    assert config.base_url == "https://deepseek.test"
    assert config.model == "deepseek-demo"


def test_openai_compatible_client_requires_api_key_for_live_client() -> None:
    with pytest.raises(MissingLlmApiKeyError):
        DeepSeekClient(DeepSeekClientConfig(api_key=None))
