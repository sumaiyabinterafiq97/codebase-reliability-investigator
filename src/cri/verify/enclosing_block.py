"""Deterministic enclosing_block tool. One tool; no repo walk, grep, or tests."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from cri.evaluation.match import normalize_path
from cri.verify.astutil import node_span, parse_source

_BLOCK_TYPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.With,
    ast.If,
    ast.Try,
    ast.ExceptHandler,
)


def _numbered_slice(lines: list[str], start: int, end: int) -> str:
    start = max(1, start)
    end = min(len(lines), end)
    if not lines or start > end:
        return ""
    return "\n".join(f"{i:>6}|{lines[i - 1]}" for i in range(start, end + 1))


def _encloses(node: ast.AST, start_line: int, end_line: int) -> bool:
    span = node_span(node)
    if span is None:
        return False
    return span[0] <= start_line and end_line <= span[1]


def enclosing_block(
    path: str | Path,
    start_line: int,
    end_line: int,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return the innermost enclosing function (or whole file) as a numbered slice.

    ``path`` is the repo-relative path when ``repo_root`` is set, otherwise a
    filesystem path. Tool arguments recorded by the runner are path / start / end
    only; ``repo_root`` is how the agent locates the file.
    """
    if repo_root is not None:
        relative = normalize_path(str(path))
        fs_path = repo_root / relative
        file_label = relative
    else:
        fs_path = Path(path)
        file_label = fs_path.as_posix()

    source = fs_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    collected: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, _BLOCK_TYPES) and _encloses(node, start_line, end_line):
            collected.append(node)
    collected.sort(
        key=lambda n: (
            (node_span(n) or (0, 0))[0],
            -((node_span(n) or (0, 0))[1]),
        )
    )
    node_types = [type(n).__name__ for n in collected]

    funcs = [
        n
        for n in collected
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if funcs:
        inner = min(
            funcs,
            key=lambda n: (
                (node_span(n) or (0, 10**9))[1] - (node_span(n) or (0, 0))[0],
                -(n.lineno or 0),
            ),
        )
        span = node_span(inner)
        assert span is not None
        start, end = span
    else:
        start, end = 1, max(len(lines), 1)

    return {
        "file": file_label,
        "start": start,
        "end": end if lines else 1,
        "text": _numbered_slice(lines, start, end),
        "node_types": node_types,
    }
