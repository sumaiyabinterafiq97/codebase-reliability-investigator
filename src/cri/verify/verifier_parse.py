from __future__ import annotations

import json

from pydantic import ValidationError

from cri.baseline.parse import extract_json_text
from cri.models.verifier import VerifierResult


def parse_verifier_response(raw: str) -> tuple[VerifierResult | None, str]:
    """Invalid JSON/schema is not treated as a successful reject or confirm."""
    try:
        text, _via = extract_json_text(raw)
        payload = json.loads(text)
    except (ValueError, json.JSONDecodeError) as exc:
        return None, f"json_parse_error: {exc}"
    if not isinstance(payload, dict):
        return None, "schema_error: top-level must be an object"
    extra = set(payload) - {"decision", "reason", "confidence", "evidence"}
    if extra:
        # extra keys allowed as long as required fields validate
        pass
    try:
        return VerifierResult.model_validate(payload), "ok"
    except ValidationError as exc:
        return None, f"schema_error: {exc.errors()[0]['msg']}"
