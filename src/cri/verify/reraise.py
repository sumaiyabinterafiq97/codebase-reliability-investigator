"""Suppress error_handling when the cited handler always re-raises.

Detects: an ``except`` overlapping the finding whose body is a linear sequence of
expressions (e.g. logging) followed by ``raise`` / ``raise <exc>``, with no
``return`` and no branching.

Why: baseline-001 flagged ``except Exception: log; raise`` and
``except ValueError: raise`` as swallowed errors. Taxonomy allows re-raise.

Suppresses: ``error_handling`` findings whose cited span overlaps such a handler.

Must not suppress: handlers that return a value (cri-01 paid sentinel, cri-06
``return {}``, cri-08 ``return raw``), ``pass``, or branched handlers we cannot
prove always re-raise.
"""

from __future__ import annotations

import ast
from pathlib import Path

from cri.models.finding import Finding
from cri.verify.astutil import finding_span, node_span, parse_source, read_source, spans_overlap

FILTER_ID = "error_handling_reraise"


def _linear_always_reraise(handler: ast.ExceptHandler) -> bool:
    if not handler.body:
        return False
    has_raise = False
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise):
            has_raise = True
            continue
        if isinstance(stmt, ast.Expr):
            continue
        return False
    return has_raise


def should_suppress(finding: Finding, repo_root: Path) -> str | None:
    if finding.category != "error_handling":
        return None
    source = read_source(repo_root, finding.file)
    if source is None:
        return None
    tree = parse_source(source)
    if tree is None:
        return None
    span = finding_span(finding)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        hspan = node_span(node)
        if hspan is None or not spans_overlap(hspan, span):
            continue
        if _linear_always_reraise(node):
            return FILTER_ID
    return None
