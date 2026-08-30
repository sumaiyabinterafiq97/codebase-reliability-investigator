"""Shared AST helpers for conservative post-filters."""

from __future__ import annotations

import ast
from pathlib import Path

from cri.evaluation.match import normalize_path
from cri.models.finding import Finding


def read_source(repo_root: Path, relative: str) -> str | None:
    path = repo_root / normalize_path(relative)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def parse_source(source: str) -> ast.AST | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def finding_span(finding: Finding) -> tuple[int, int]:
    return finding.location_span()


def node_span(node: ast.AST) -> tuple[int, int] | None:
    lineno = getattr(node, "lineno", None)
    if lineno is None:
        return None
    end = getattr(node, "end_lineno", lineno)
    return lineno, end
