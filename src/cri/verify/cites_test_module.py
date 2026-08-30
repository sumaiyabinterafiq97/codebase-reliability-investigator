"""Suppress testing_coverage findings that point at a test module, not production.

Detects: category ``testing_coverage`` and a cited path named ``test_*.py`` or
``*_test.py``.

Why: EXP-1 cited ``test_payments.py`` for cri-05 instead of the untested
production fallback in ``payments.py``. A test file is not the missing-coverage
site.

Suppresses: testing_coverage findings whose ``file`` is a test module.

Must not suppress: findings that cite production code (``payments.py``) even
when tests exist in the same repo.
"""

from __future__ import annotations

from pathlib import Path

from cri.evaluation.match import normalize_path
from cri.models.finding import Finding

FILTER_ID = "testing_coverage_cites_test_file"


def _is_test_path(relative: str) -> bool:
    name = Path(normalize_path(relative)).name
    return name.startswith("test_") or name.endswith("_test.py")


def should_suppress(finding: Finding, repo_root: Path) -> str | None:
    if finding.category != "testing_coverage":
        return None
    if _is_test_path(finding.file):
        return FILTER_ID
    return None
