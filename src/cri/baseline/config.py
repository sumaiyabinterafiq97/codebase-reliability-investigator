from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class BaselineConfigError(RuntimeError):
    pass


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _opt_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if raw == "":
        return None
    return float(raw)


def _opt_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class BaselineConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int
    max_bundle_chars: int
    api_key: str
    base_url: str
    usd_per_million_prompt_tokens: float | None
    usd_per_million_completion_tokens: float | None

    @staticmethod
    def from_env() -> "BaselineConfig":
        provider = os.environ.get("CRI_LLM_PROVIDER", "openai").strip().lower()
        model = os.environ.get("CRI_LLM_MODEL", "").strip()
        if not model:
            model = "gpt-4o-mini" if provider == "openai" else "claude-3-5-haiku-latest"
        temperature = float(os.environ.get("CRI_LLM_TEMPERATURE", "0").strip() or "0")
        max_tokens = _opt_int("CRI_LLM_MAX_TOKENS", 4096)
        max_bundle_chars = _opt_int("CRI_MAX_BUNDLE_CHARS", 200_000)
        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            base_url = os.environ.get("CRI_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            if not api_key:
                raise BaselineConfigError("OPENAI_API_KEY is not set")
        elif provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            base_url = os.environ.get("CRI_LLM_BASE_URL", "https://api.anthropic.com").rstrip("/")
            if not api_key:
                raise BaselineConfigError("ANTHROPIC_API_KEY is not set")
        else:
            raise BaselineConfigError(
                f"unsupported CRI_LLM_PROVIDER={provider!r} (use openai or anthropic)"
            )
        return BaselineConfig(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_bundle_chars=max_bundle_chars,
            api_key=api_key,
            base_url=base_url,
            usd_per_million_prompt_tokens=_opt_float("CRI_USD_PER_MILLION_PROMPT_TOKENS"),
            usd_per_million_completion_tokens=_opt_float("CRI_USD_PER_MILLION_COMPLETION_TOKENS"),
        )
