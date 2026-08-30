from __future__ import annotations

from pathlib import Path

from cri.evaluation.match import normalize_path
from cri.models.finding import Finding
from cri.verify.context import extract_snippet, nearby_context, repo_source_context
from cri.verify.verifier_prompt import taxonomy_for


def build_user_prompt(finding: Finding, repo_root: Path) -> str:
    start, end = finding.location_span()
    snippet = extract_snippet(repo_root, finding.file, start, end)
    claimed_quote = finding.evidence.quote
    return (
        f"repository_id: {finding.repository_id}\n"
        f"category: {finding.category}\n"
        f"severity: {finding.severity}\n"
        f"file: {finding.file}\n"
        f"line: {finding.line}\n"
        f"line_start: {start}\n"
        f"line_end: {end}\n"
        f"function_name: {finding.function_name or ''}\n"
        f"description: {finding.description}\n\n"
        "TAXONOMY FOR THE CLAIMED CATEGORY:\n"
        f"{taxonomy_for(finding.category)}\n"
        "CLAIMED EVIDENCE QUOTE FROM THE FINDING:\n"
        f"{claimed_quote}\n\n"
        "EXTRACTED SOURCE SNIPPET AT THE CLAIMED LOCATION:\n"
        f"{snippet}\n\n"
        f"{nearby_context(repo_root, finding.file, start, end)}\n\n"
        "FULL SOURCE IN THIS REPOSITORY (for context only; do not hunt new issues):\n"
        f"{repo_source_context(repo_root)}\n"
    )


def quote_in_file(repo_root: Path, file: str, start: int, end: int, quote: str) -> bool:
    path = repo_root / normalize_path(file)
    if not path.is_file() or not quote.strip():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    if start < 1 or end > len(lines) or start > end:
        return False
    window = "\n".join(lines[start - 1 : end])
    whole = path.read_text(encoding="utf-8")
    q = quote.strip()
    return q in window or q in whole
