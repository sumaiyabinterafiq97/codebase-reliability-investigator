"""Deterministic matching of predictions to gold issues. See docs/evaluation-plan.md."""

from pathlib import Path

from cri.models.finding import Finding
from cri.models.ground_truth import Issue

LINE_WINDOW = 8


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def gold_window(issue: Issue) -> tuple[int, int]:
    return issue.line - LINE_WINDOW, issue.line + LINE_WINDOW


def location_ok(finding: Finding, issue: Issue) -> bool:
    pred = finding.location_span()
    return spans_overlap(pred, gold_window(issue))


def hard_constraints(finding: Finding, issue: Issue, repository_id: str) -> bool:
    if finding.repository_id != repository_id:
        return False
    if finding.category != issue.category:
        return False
    if normalize_path(finding.file) != normalize_path(issue.file):
        return False
    return location_ok(finding, issue)


def evidence_grounded(finding: Finding, issue: Issue, repo_root: Path | None) -> bool:
    ev = finding.evidence
    if repo_root is None:
        return spans_overlap(finding.location_span(), gold_window(issue)) or bool(
            ev.quote.strip()
        )

    path = repo_root / normalize_path(ev.file)
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    if ev.line_start < 1 or ev.line_end > n:
        return False
    if spans_overlap((ev.line_start, ev.line_end), gold_window(issue)):
        return True
    snippet = "\n".join(lines[ev.line_start - 1 : ev.line_end])
    quote = ev.quote.strip()
    return bool(quote) and quote in snippet
