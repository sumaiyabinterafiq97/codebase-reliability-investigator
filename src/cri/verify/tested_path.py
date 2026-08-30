"""Suppress testing_coverage when a test directly calls the fallback callee.

Detects: ``testing_coverage`` findings whose cited production span includes an
``except`` body that calls a function, and some ``test_*.py`` / ``*_test.py``
file in the repo contains a Call to that same name.

Why: taxonomy says a recovery path that tests already exercise is not an issue.

Suppresses: only when the fallback callee is literally invoked from a test.

Must not suppress: cri-05, where tests call ``checkout`` on the happy path only
and never call ``charge_secondary``. Indirect coverage via keyword flags is
intentionally not inferred (too easy to false-suppress).
"""

from __future__ import annotations

import ast
from pathlib import Path

from cri.models.finding import Finding
from cri.verify.astutil import finding_span, node_span, parse_source, read_source, spans_overlap

FILTER_ID = "testing_coverage_path_exercised"


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _fallback_callees(tree: ast.AST, span: tuple[int, int]) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        hspan = node_span(node)
        if hspan is None or not spans_overlap(hspan, span):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _call_name(child)
                if name:
                    names.add(name)
    return names


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _test_call_names(repo_root: Path) -> set[str]:
    names: set[str] = set()
    for path in repo_root.rglob("*.py"):
        if not _is_test_file(path):
            continue
        source = path.read_text(encoding="utf-8")
        tree = parse_source(source)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name:
                    names.add(name)
    return names


def should_suppress(finding: Finding, repo_root: Path) -> str | None:
    if finding.category != "testing_coverage":
        return None
    source = read_source(repo_root, finding.file)
    if source is None:
        return None
    tree = parse_source(source)
    if tree is None:
        return None
    callees = _fallback_callees(tree, finding_span(finding))
    if not callees:
        return None
    tested = _test_call_names(repo_root)
    if callees & tested:
        return FILTER_ID
    return None
