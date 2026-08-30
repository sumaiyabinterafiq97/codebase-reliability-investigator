"""Parse and validate baseline LLM JSON into Finding objects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from cri.models.finding import Finding

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


@dataclass
class ParseResult:
    findings: list[Finding]
    status: str
    error: str | None = None
    invalid_finding_count: int = 0
    invalid_errors: list[str] = field(default_factory=list)
    extracted_via: str = "json"


def extract_json_text(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if not text:
        raise ValueError("empty model response")
    fenced = _FENCE_RE.search(text)
    if fenced:
        return fenced.group(1).strip(), "fenced_json"
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model response")
    return text[start : end + 1], "braces_json"


def parse_findings(raw: str, repository_id: str) -> ParseResult:
    """Invalid output is recorded, not treated as successful findings."""
    try:
        json_text, via = extract_json_text(raw)
        payload = json.loads(json_text)
    except (ValueError, json.JSONDecodeError) as exc:
        return ParseResult(
            findings=[],
            status="json_parse_error",
            error=str(exc),
            extracted_via="none",
        )

    if not isinstance(payload, dict):
        return ParseResult(
            findings=[],
            status="schema_error",
            error="top-level JSON must be an object",
            extracted_via=via,
        )
    if "findings" not in payload:
        return ParseResult(
            findings=[],
            status="schema_error",
            error="missing 'findings' key",
            extracted_via=via,
        )
    items = payload["findings"]
    if not isinstance(items, list):
        return ParseResult(
            findings=[],
            status="schema_error",
            error="'findings' must be a list",
            extracted_via=via,
        )

    findings: list[Finding] = []
    invalid_errors: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            invalid_errors.append(f"findings[{i}] is not an object")
            continue
        data = dict(item)
        data["repository_id"] = repository_id
        if "file" in data and isinstance(data["file"], str):
            data["file"] = data["file"].replace("\\", "/").lstrip("./")
        ev = data.get("evidence")
        if isinstance(ev, dict):
            ev = dict(ev)
            if "file" in ev and isinstance(ev["file"], str):
                ev["file"] = ev["file"].replace("\\", "/").lstrip("./")
            if "file" not in ev and "file" in data:
                ev["file"] = data["file"]
            data["evidence"] = ev
        try:
            findings.append(Finding.model_validate(data))
        except ValidationError as exc:
            invalid_errors.append(f"findings[{i}]: {exc.errors()[0]['msg']}")

    if invalid_errors and not findings:
        return ParseResult(
            findings=[],
            status="schema_error",
            error="; ".join(invalid_errors),
            invalid_finding_count=len(invalid_errors),
            invalid_errors=invalid_errors,
            extracted_via=via,
        )
    status = "ok" if not invalid_errors else "partial_invalid"
    return ParseResult(
        findings=findings,
        status=status,
        error="; ".join(invalid_errors) if invalid_errors else None,
        invalid_finding_count=len(invalid_errors),
        invalid_errors=invalid_errors,
        extracted_via=via,
    )
