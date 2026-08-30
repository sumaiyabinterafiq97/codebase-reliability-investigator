"""Build numbered source context for one finding. No extra repos; no tools."""

from __future__ import annotations

from pathlib import Path

from cri.evaluation.match import normalize_path
from cri.models.finding import Finding

CONTEXT_PAD = 8


def _numbered(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(f"{i:>6}|{line}" for i, line in enumerate(lines, start=1))


def extract_snippet(repo_root: Path, relative: str, start: int, end: int) -> str:
    path = repo_root / normalize_path(relative)
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, start)
    end = min(len(lines), end)
    if start > end:
        return ""
    return "\n".join(lines[start - 1 : end])


def nearby_context(repo_root: Path, relative: str, start: int, end: int, pad: int = CONTEXT_PAD) -> str:
    path = repo_root / normalize_path(relative)
    if not path.is_file():
        return f"(missing file {relative})"
    lines = path.read_text(encoding="utf-8").splitlines()
    lo = max(1, start - pad)
    hi = min(len(lines), end + pad)
    chunk = "\n".join(f"{i:>6}|{lines[i - 1]}" for i in range(lo, hi + 1))
    return f"=== NEARBY {relative} lines {lo}-{hi} ===\n{chunk}"


def repo_source_context(repo_root: Path) -> str:
    """All .py files in this repository (these cases are tiny). Not other repos."""
    parts: list[str] = []
    paths = sorted(
        [p for p in repo_root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts],
        key=lambda p: p.relative_to(repo_root).as_posix(),
    )
    for path in paths:
        rel = path.relative_to(repo_root).as_posix()
        parts.append(f"=== FILE {rel} ===\n{_numbered(path.read_text(encoding='utf-8'))}")
    return "\n\n".join(parts)
