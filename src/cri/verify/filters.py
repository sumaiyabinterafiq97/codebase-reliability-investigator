from __future__ import annotations

from pathlib import Path

from cri.models.finding import Finding
from cri.verify import cites_test_module, locked_write, reraise, tested_path

FILTERS = (
    reraise.should_suppress,
    locked_write.should_suppress,
    tested_path.should_suppress,
    cites_test_module.should_suppress,
)


def first_suppression(finding: Finding, repo_root: Path) -> str | None:
    for fn in FILTERS:
        reason = fn(finding, repo_root)
        if reason:
            return reason
    return None


def apply_filters(
    findings: list[Finding],
    repos_dir: Path,
) -> tuple[list[Finding], list[dict]]:
    kept: list[Finding] = []
    log: list[dict] = []
    for finding in findings:
        root = repos_dir / finding.repository_id
        reason = first_suppression(finding, root)
        log.append(
            {
                "repository_id": finding.repository_id,
                "category": finding.category,
                "file": finding.file,
                "line": finding.line,
                "suppressed": reason is not None,
                "filter": reason,
            }
        )
        if reason is None:
            kept.append(finding)
    return kept, log
