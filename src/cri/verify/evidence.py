"""Replace model evidence with a bounded on-disk snippet; drop invalid locations.

A module docstring or a range that is merely 'near' the defect is not sufficient.
We re-extract from the claimed file, prefer the named function, skip leading
docstrings, and cap snippet length.

Does not use an LLM.
"""

from __future__ import annotations

import ast
from pathlib import Path

from cri.evaluation.match import normalize_path
from cri.models.finding import Evidence, Finding
from cri.verify.astutil import node_span, parse_source, spans_overlap

MAX_SNIPPET_LINES = 8


def _is_docstring_expr(node: ast.AST) -> bool:
    if not isinstance(node, ast.Expr):
        return False
    value = node.value
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def _module_docstring_span(tree: ast.AST) -> tuple[int, int] | None:
    if not isinstance(tree, ast.Module) or not tree.body:
        return None
    first = tree.body[0]
    if _is_docstring_expr(first):
        return node_span(first)
    return None


def _function_for_finding(tree: ast.AST, finding: Finding) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    span = finding.location_span()
    named: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    overlapping: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nspan = node_span(node)
        if nspan is None:
            continue
        if finding.function_name and node.name == finding.function_name:
            named = node
        if spans_overlap(nspan, span):
            overlapping.append(node)
    if named is not None:
        return named
    if not overlapping:
        return None
    overlapping.sort(key=lambda n: (node_span(n) or (0, 0))[1] - (node_span(n) or (0, 0))[0])
    return overlapping[0]


def _clip(start: int, end: int, nlines: int) -> tuple[int, int] | None:
    if nlines < 1:
        return None
    start = max(1, start)
    end = min(nlines, end)
    if start > end:
        return None
    return start, end


def _skip_leading_docstrings(lines: list[str], start: int, end: int, tree: ast.AST) -> tuple[int, int]:
    doc = _module_docstring_span(tree)
    while start <= end:
        text = lines[start - 1].strip()
        if text == "":
            start += 1
            continue
        if doc and doc[0] <= start <= doc[1]:
            start = doc[1] + 1
            continue
        if text.startswith('"""') or text.startswith("'''"):
            start += 1
            continue
        break
    return start, end


def repair_finding(finding: Finding, repo_root: Path) -> tuple[Finding | None, str]:
    path = repo_root / normalize_path(finding.file)
    if not path.is_file():
        return None, "missing_file"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    n = len(lines)
    start, end = finding.location_span()
    clipped = _clip(start, end, n)
    if clipped is None:
        return None, "invalid_line_range"
    start, end = clipped

    tree = parse_source(text)
    if tree is not None:
        fn = _function_for_finding(tree, finding)
        if fn is not None:
            fspan = node_span(fn)
            if fspan is not None:
                overlap_s = max(start, fspan[0])
                overlap_e = min(end, fspan[1])
                if overlap_s <= overlap_e:
                    start, end = overlap_s, overlap_e
                else:
                    start, end = fspan
        start, end = _skip_leading_docstrings(lines, start, end, tree)

    clipped = _clip(start, end, n)
    if clipped is None:
        return None, "empty_after_docstring_strip"
    start, end = clipped

    if end - start + 1 > MAX_SNIPPET_LINES:
        focus = finding.line if finding.line is not None else end
        focus = min(max(focus, start), end)
        start = max(start, focus - MAX_SNIPPET_LINES + 1)
        end = min(end, start + MAX_SNIPPET_LINES - 1)

    quote = "\n".join(lines[start - 1 : end])
    if not quote.strip():
        return None, "empty_snippet"

    evidence = Evidence(
        file=normalize_path(finding.file),
        line_start=start,
        line_end=end,
        quote=quote,
    )
    updated = finding.model_copy(
        update={
            "line": finding.line if finding.line is not None else start,
            "line_start": start,
            "line_end": end,
            "evidence": evidence,
        }
    )
    return updated, "ok"


def apply_evidence(
    findings: list[Finding],
    repos_dir: Path,
) -> tuple[list[Finding], list[dict]]:
    kept: list[Finding] = []
    log: list[dict] = []
    for finding in findings:
        repaired, status = repair_finding(finding, repos_dir / finding.repository_id)
        log.append(
            {
                "repository_id": finding.repository_id,
                "file": finding.file,
                "status": status,
                "kept": repaired is not None,
            }
        )
        if repaired is not None:
            kept.append(repaired)
    return kept, log
