from pathlib import Path

from cri.models.finding import Evidence, Finding
from cri.verify.evidence import repair_finding

BENCH = Path(__file__).resolve().parents[1] / "benchmark" / "repositories"


def test_correct_evidence_keeps_except_lines():
    finding = Finding(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="checkout.py",
        line=16,
        line_start=16,
        line_end=17,
        function_name="checkout",
        description="bare except",
        evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
    )
    repaired, status = repair_finding(finding, BENCH / "cri-01-bare-except")
    assert status == "ok"
    assert repaired is not None
    assert "except:" in repaired.evidence.quote
    assert repaired.evidence.line_start >= 12
    assert repaired.evidence.quote.strip() != '"""'


def test_docstring_evidence_is_replaced():
    finding = Finding(
        repository_id="cri-03-leaked-file",
        category="resource_lifecycle",
        severity="medium",
        file="audit.py",
        line=1,
        line_start=1,
        line_end=11,
        function_name="append_audit",
        description="leak",
        evidence=Evidence(
            file="audit.py",
            line_start=1,
            line_end=11,
            quote='"""Write an audit line; handle is not closed if write fails."""',
        ),
    )
    repaired, status = repair_finding(finding, BENCH / "cri-03-leaked-file")
    assert status == "ok"
    assert repaired is not None
    assert "Write an audit line" not in repaired.evidence.quote
    assert "open(" in repaired.evidence.quote or "except OSError" in repaired.evidence.quote
    assert repaired.evidence.line_start > 1


def test_wrong_location_missing_file():
    finding = Finding(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="nope.py",
        line=1,
        description="x",
        evidence=Evidence(file="nope.py", line_start=1, line_end=1, quote="x"),
    )
    repaired, status = repair_finding(finding, BENCH / "cri-01-bare-except")
    assert repaired is None
    assert status == "missing_file"


def test_line_range_errors():
    finding = Finding(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="checkout.py",
        line=999,
        line_start=999,
        line_end=1000,
        description="x",
        evidence=Evidence(file="checkout.py", line_start=999, line_end=1000, quote="x"),
    )
    repaired, status = repair_finding(finding, BENCH / "cri-01-bare-except")
    assert repaired is None
    assert status == "invalid_line_range"
