"""Deterministic source-file collection for the baseline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

SOURCE_SUFFIXES = (".py",)
SKIP_DIR_NAMES = frozenset(
    {"__pycache__", ".git", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)
SKIP_FILE_NAMES = frozenset({".ds_store"})


@dataclass(frozen=True)
class CollectedFile:
    relative_path: str
    text: str
    line_count: int
    sha256: str


@dataclass(frozen=True)
class CollectedRepo:
    repository_id: str
    root: Path
    files: tuple[CollectedFile, ...]
    excluded: tuple[str, ...]
    bundle: str
    bundle_sha256: str


def posix_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def list_repository_dirs(benchmark_root: Path) -> list[Path]:
    if not benchmark_root.is_dir():
        raise FileNotFoundError(f"benchmark directory not found: {benchmark_root}")
    dirs = [
        p
        for p in benchmark_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    return sorted(dirs, key=lambda p: p.name)


def iter_source_paths(root: Path) -> tuple[list[Path], list[str]]:
    included: list[Path] = []
    excluded: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if path.is_dir():
            continue
        rel = posix_rel(path, root)
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            excluded.append(rel)
            continue
        if path.name.lower() in SKIP_FILE_NAMES:
            excluded.append(rel)
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            excluded.append(rel)
            continue
        included.append(path)
    included.sort(key=lambda p: posix_rel(p, root))
    return included, excluded


def format_bundle(repository_id: str, files: list[CollectedFile]) -> str:
    parts = [
        f"repository_id: {repository_id}",
        f"file_count: {len(files)}",
        "Each file is listed with 1-based line numbers. Cite those line numbers.",
        "",
    ]
    for item in files:
        parts.append(f"=== FILE {item.relative_path} ({item.line_count} lines) ===")
        numbered = item.text.splitlines()
        if not numbered and item.text == "":
            parts.append("")
            continue
        for i, line in enumerate(numbered, start=1):
            parts.append(f"{i:>6}|{line}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def collect_repository(root: Path, repository_id: str | None = None) -> CollectedRepo:
    root = root.resolve()
    repo_id = repository_id or root.name
    paths, excluded = iter_source_paths(root)
    files: list[CollectedFile] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        rel = posix_rel(path, root)
        files.append(
            CollectedFile(
                relative_path=rel,
                text=text,
                line_count=len(text.splitlines()) or (0 if text == "" else 1),
                sha256=sha256_text(text),
            )
        )
    bundle = format_bundle(repo_id, files)
    return CollectedRepo(
        repository_id=repo_id,
        root=root,
        files=tuple(files),
        excluded=tuple(excluded),
        bundle=bundle,
        bundle_sha256=sha256_text(bundle),
    )
