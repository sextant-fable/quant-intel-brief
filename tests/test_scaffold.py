"""Scaffold-level tests that should pass before business logic exists."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_reports_gitkeep_is_preserved() -> None:
    assert (ROOT / "data" / "reports" / ".gitkeep").is_file()


def test_env_example_uses_deepseek_placeholders() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    old_openai_key_name = "OPENAI" + "_API_KEY"

    assert "DEEPSEEK_API_KEY=" in env_example
    assert "DEEPSEEK_BASE_URL=" in env_example
    assert "DEEPSEEK_MODEL=" in env_example
    assert old_openai_key_name not in env_example
