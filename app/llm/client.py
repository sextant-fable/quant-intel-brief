"""OpenAI-compatible JSON completion client wrapper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI
from pydantic import SecretStr

from app.core.config import Settings


class LlmClientError(RuntimeError):
    """Raised when an LLM request or response fails."""


class MissingLlmApiKeyError(LlmClientError):
    """Raised when a real LLM client is requested without an API key."""


class JsonCompletionClient(Protocol):
    """Protocol used by summarization tests and production client."""

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Return JSON-decoded model output."""


@dataclass(frozen=True, slots=True)
class OpenAICompatibleClientConfig:
    """OpenAI-compatible chat completion settings."""

    api_key: SecretStr | None
    provider: str = "openai-compatible"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleClientConfig:
        api_key = settings.llm_api_key or settings.deepseek_api_key
        base_url = settings.llm_base_url or settings.deepseek_base_url
        model = settings.llm_model or settings.deepseek_model
        return cls(
            api_key=api_key,
            provider=settings.llm_provider,
            base_url=base_url,
            model=model,
        )


class OpenAICompatibleClient:
    """Small JSON completion client for OpenAI-compatible providers."""

    def __init__(
        self,
        config: OpenAICompatibleClientConfig,
        openai_client: Any | None = None,
    ) -> None:
        if openai_client is None and config.api_key is None:
            raise MissingLlmApiKeyError(
                "LLM_API_KEY or a provider-specific API key is required for live LLM calls."
            )
        self.config = config
        self._client: Any = openai_client or OpenAI(
            api_key=config.api_key.get_secret_value() if config.api_key else None,
            base_url=config.base_url,
        )

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Call the chat API and decode a JSON object response."""
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                raise LlmClientError("LLM returned an empty response.")
            decoded = json.loads(content)
            if not isinstance(decoded, dict):
                raise LlmClientError("LLM JSON response must be an object.")
            return decoded
        except json.JSONDecodeError as exc:
            raise LlmClientError(f"LLM returned invalid JSON: {exc}") from exc
        except LlmClientError:
            raise
        except Exception as exc:
            raise LlmClientError(f"LLM request failed: {exc}") from exc


DeepSeekClientConfig = OpenAICompatibleClientConfig
DeepSeekClient = OpenAICompatibleClient

__all__ = [
    "DeepSeekClient",
    "DeepSeekClientConfig",
    "JsonCompletionClient",
    "LlmClientError",
    "MissingLlmApiKeyError",
    "OpenAICompatibleClient",
    "OpenAICompatibleClientConfig",
]
