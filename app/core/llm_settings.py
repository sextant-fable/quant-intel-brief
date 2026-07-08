"""Local OpenAI-compatible LLM settings helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LLM_ENV_KEYS = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")


@dataclass(frozen=True, slots=True)
class LlmProviderPreset:
    """Provider defaults for the local settings page."""

    provider: str
    label: str
    base_url: str
    model: str


LLM_PROVIDER_PRESETS = {
    "deepseek": LlmProviderPreset(
        provider="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
    ),
    "glm": LlmProviderPreset(
        provider="glm",
        label="GLM / Z.AI",
        base_url="https://api.z.ai/api/paas/v4/",
        model="glm-5.2",
    ),
    "kimi": LlmProviderPreset(
        provider="kimi",
        label="Kimi / Moonshot",
        base_url="https://api.moonshot.ai/v1",
        model="kimi-k2.6",
    ),
    "custom": LlmProviderPreset(
        provider="custom",
        label="Custom OpenAI-compatible",
        base_url="",
        model="",
    ),
}


@dataclass(frozen=True, slots=True)
class SavedLlmSettings:
    """Saved local LLM settings without exposing the API key."""

    provider: str
    base_url: str
    model: str
    has_api_key: bool


def load_llm_settings(env_path: Path) -> SavedLlmSettings:
    """Load saved LLM settings from a local env file."""
    values = _read_env_values(env_path)
    provider = values.get("LLM_PROVIDER") or "deepseek"
    preset = LLM_PROVIDER_PRESETS.get(provider, LLM_PROVIDER_PRESETS["custom"])
    base_url = values.get("LLM_BASE_URL")
    model = values.get("LLM_MODEL")
    if provider == "deepseek":
        base_url = base_url or values.get("DEEPSEEK_BASE_URL")
        model = model or values.get("DEEPSEEK_MODEL")
    return SavedLlmSettings(
        provider=provider,
        base_url=base_url or preset.base_url,
        model=model or preset.model,
        has_api_key=bool(values.get("LLM_API_KEY") or values.get("DEEPSEEK_API_KEY")),
    )


def save_llm_settings(
    env_path: Path,
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str | None,
    clear_api_key: bool = False,
) -> SavedLlmSettings:
    """Persist LLM settings to `.env`, preserving a blank key unless cleared."""
    provider = provider.strip() or "custom"
    base_url = base_url.strip()
    model = model.strip()
    api_key = (api_key or "").strip()

    existing = _read_env_values(env_path)
    if clear_api_key:
        stored_key = ""
    elif api_key:
        stored_key = api_key
    else:
        stored_key = existing.get("LLM_API_KEY", "") or existing.get("DEEPSEEK_API_KEY", "")

    updates = {
        "LLM_PROVIDER": provider,
        "LLM_API_KEY": stored_key,
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": model,
    }
    if clear_api_key:
        updates["DEEPSEEK_API_KEY"] = ""
    _write_env_updates(env_path, updates)
    return SavedLlmSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        has_api_key=bool(stored_key),
    )


def _read_env_values(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_updates(env_path: Path, updates: dict[str, str]) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                next_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        next_lines.append(line)

    if not next_lines:
        next_lines.append("# Local settings")

    missing = [key for key in LLM_ENV_KEYS if key not in seen]
    if missing:
        if next_lines[-1].strip():
            next_lines.append("")
        next_lines.append("# OpenAI-compatible LLM")
        next_lines.extend(f"{key}={updates[key]}" for key in missing)

    env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


__all__ = [
    "LLM_PROVIDER_PRESETS",
    "LlmProviderPreset",
    "SavedLlmSettings",
    "load_llm_settings",
    "save_llm_settings",
]
