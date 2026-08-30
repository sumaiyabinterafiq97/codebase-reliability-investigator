"""Deterministic EXP-5 gate: category ↔ construct, not discovery.

A finding enters semantic review only when it claims error_handling but the
cited span overlaps no ast.ExceptHandler. File/parse errors do not enter
(finding is kept). No repository IDs, file names, or line numbers are special.
"""

from __future__ import annotations

import ast
from pathlib import Path

from cri.models.finding import Finding
from cri.verify.astutil import finding_span, node_span, parse_source, read_source, spans_overlap


def needs_semantic_review(finding: Finding, repo_root: Path) -> bool:
    """Return True iff this finding should receive one fail-open LLM review."""
    if finding.category != "error_handling":
        return False
    try:
        source = read_source(repo_root, finding.file)
        if source is None:
            return False
        tree = parse_source(source)
        if tree is None:
            return False
        span = finding_span(finding)
        for node in ast.walk(tree):
            if type(node) is not ast.ExceptHandler:
                continue
            hspan = node_span(node)
            if hspan is not None and spans_overlap(hspan, span):
                return False
        return True
    except Exception:
        return False
