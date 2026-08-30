"""HTTP LLM clients. No SDK dependency. Never log API keys."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

import certifi

from cri.baseline.config import BaselineConfig
from cri.baseline.prompt import SYSTEM_PROMPT


@dataclass(frozen=True)
class LLMResponse:
    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    raw_http_body: str


class LLMClient(Protocol):
    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse: ...


class LLMError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, headers: dict[str, str], timeout: float = 120.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"HTTP {exc.code} from {url}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"request failed: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"provider returned non-JSON: {exc}") from exc
    parsed["_cri_raw_http_body"] = raw
    return parsed


class OpenAIClient:
    def __init__(self, config: BaselineConfig) -> None:
        self._config = config

    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse:
        url = f"{self._config.base_url}/chat/completions"
        payload = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }
        data = _post_json(url, payload, headers)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenAI response missing choices[0].message.content") from exc
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        return LLMResponse(
            text=text or "",
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
            raw_http_body=data.get("_cri_raw_http_body", json.dumps(data)),
        )


class AnthropicClient:
    def __init__(self, config: BaselineConfig) -> None:
        self._config = config

    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse:
        url = f"{self._config.base_url}/v1/messages"
        payload = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "system": system_prompt or SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_text}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = _post_json(url, payload, headers)
        try:
            blocks = data["content"]
            text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise LLMError("Anthropic response missing content text") from exc
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("input_tokens")
        completion_tokens = usage.get("output_tokens")
        return LLMResponse(
            text=text,
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
            raw_http_body=data.get("_cri_raw_http_body", json.dumps(data)),
        )


def client_from_config(config: BaselineConfig) -> LLMClient:
    if config.provider == "openai":
        return OpenAIClient(config)
    if config.provider == "anthropic":
        return AnthropicClient(config)
    raise LLMError(f"unsupported provider {config.provider}")
