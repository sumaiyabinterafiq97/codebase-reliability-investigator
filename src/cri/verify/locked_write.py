"""Suppress state_concurrency when the cited mutation sits in a lock ``with``.

Detects: assignment / annotated assignment / augassign in the finding span whose
line is inside ``with lock:`` where lock is ``Lock()``, ``RLock()``,
``threading.Lock()``, or a name containing ``lock``.

Why: a shared write is not an obvious race if that write is in the critical
section. ``with ThreadPoolExecutor`` is not treated as a lock.

Suppresses: ``state_concurrency`` findings whose mutation line is inside such a
``with``.

Must not suppress: unlocked writes (cri-04 ``credit``, cri-07 ``reserve``),
check-then-act where the write is outside the ``with``, or non-lock context
managers.
"""

from __future__ import annotations

import ast
from pathlib import Path

from cri.models.finding import Finding
from cri.verify.astutil import finding_span, node_span, parse_source, read_source, spans_overlap

FILTER_ID = "state_concurrency_locked_write"

_LOCK_FUNCS = frozenset({"Lock", "RLock"})


def _is_lock_expr(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Name):
        lowered = expr.id.lower()
        return lowered in {"lock", "_lock", "rlock"} or lowered.endswith("_lock")
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Name) and func.id in _LOCK_FUNCS:
            return True
        if isinstance(func, ast.Attribute) and func.attr in _LOCK_FUNCS:
            return True
    return False


def _lock_with_spans(tree: ast.AST) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        if not any(_is_lock_expr(item.context_expr) for item in node.items):
            continue
        body_span = node_span(node)
        if body_span is None:
            continue
        spans.append(body_span)
    return spans


def _mutation_lines(tree: ast.AST, span: tuple[int, int]) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        nspan = node_span(node)
        if nspan is None or not spans_overlap(nspan, span):
            continue
        lines.append(nspan[0])
    return lines


def should_suppress(finding: Finding, repo_root: Path) -> str | None:
    if finding.category != "state_concurrency":
        return None
    source = read_source(repo_root, finding.file)
    if source is None:
        return None
    tree = parse_source(source)
    if tree is None:
        return None
    span = finding_span(finding)
    lock_spans = _lock_with_spans(tree)
    if not lock_spans:
        return None
    mutations = _mutation_lines(tree, span)
    if not mutations:
        return None
    for line in mutations:
        if any(lo <= line <= hi for lo, hi in lock_spans):
            return FILTER_ID
    return None
