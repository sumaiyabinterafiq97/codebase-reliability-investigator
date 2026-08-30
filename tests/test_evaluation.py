from pathlib import Path

from cri.evaluation.load import load_ground_truth_dir
from cri.evaluation.match import hard_constraints
from cri.evaluation.metrics import evaluate
from cri.models.finding import Evidence, Finding
from cri.models.ground_truth import GroundTruthFile, Issue

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "benchmark" / "ground_truth"
REPOS = ROOT / "benchmark" / "repositories"


def _finding(**kwargs) -> Finding:
    defaults = dict(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="checkout.py",
        line=16,
        description="bare except",
        evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_load_all_twelve_gold_files():
    gold = load_ground_truth_dir(GT_DIR)
    assert len(gold) == 12
    positives = sum(len(g.positive_issues()) for g in gold.values())
    assert positives == 9
    assert gold["cri-10-logged-reraise"].positive_issues() == []
    assert gold["cri-10-logged-reraise"].fp_anchors()


def test_perfect_match_is_tp():
    gold = load_ground_truth_dir(GT_DIR)
    issue = gold["cri-01-bare-except"].positive_issues()[0]
    finding = _finding()
    assert hard_constraints(finding, issue, "cri-01-bare-except")
    metrics = evaluate(
        [finding],
        {"cri-01-bare-except": gold["cri-01-bare-except"]},
        repo_roots={"cri-01-bare-except": REPOS / "cri-01-bare-except"},
    )
    assert metrics.per_repo[0].tp == 1
    assert metrics.per_repo[0].fn == 0
    assert metrics.matches[0].kind == "tp"
    assert metrics.matches[0].evidence_grounded is True
    assert metrics.matches[0].severity_match is True


def test_wrong_file_is_fn_and_fp():
    gold = load_ground_truth_dir(GT_DIR)
    finding = _finding(file="other.py", evidence=Evidence(file="other.py", line_start=1, line_end=1, quote="x"))
    metrics = evaluate(
        [finding],
        {"cri-01-bare-except": gold["cri-01-bare-except"]},
    )
    kinds = {m.kind for m in metrics.matches}
    assert kinds == {"fn", "fp"}


def test_line_outside_window_does_not_match():
    gold = load_ground_truth_dir(GT_DIR)
    issue = gold["cri-01-bare-except"].positive_issues()[0]
    finding = _finding(line=1, evidence=Evidence(file="checkout.py", line_start=1, line_end=1, quote="#"))
    assert not hard_constraints(finding, issue, "cri-01-bare-except")


def test_negative_repo_finding_is_fp():
    gold = load_ground_truth_dir(GT_DIR)
    finding = Finding(
        repository_id="cri-11-clean-checkout",
        category="error_handling",
        severity="low",
        file="store.py",
        line=16,
        description="should not flag",
        evidence=Evidence(file="store.py", line_start=16, line_end=16, quote="except"),
    )
    metrics = evaluate(
        [finding],
        {"cri-11-clean-checkout": gold["cri-11-clean-checkout"]},
    )
    assert metrics.per_repo[0].fp == 1
    assert metrics.per_repo[0].tp == 0
    assert metrics.repo_level_fpr == 1.0


def test_red_herring_tagged():
    gold = load_ground_truth_dir(GT_DIR)
    finding = Finding(
        repository_id="cri-10-logged-reraise",
        category="error_handling",
        severity="medium",
        file="transfers.py",
        line=17,
        description="broad except",
        evidence=Evidence(file="transfers.py", line_start=17, line_end=19, quote="except Exception"),
    )
    metrics = evaluate(
        [finding],
        {"cri-10-logged-reraise": gold["cri-10-logged-reraise"]},
        repo_roots={"cri-10-logged-reraise": REPOS / "cri-10-logged-reraise"},
    )
    assert metrics.matches[0].kind == "fp_red_herring"
    assert metrics.false_positive_count == 1


def test_empty_predictions_all_fn():
    gold = {"x": GroundTruthFile(
        repository_id="x",
        language="python",
        issues=[
            Issue(
                issue_id="i",
                category="error_handling",
                severity="low",
                file="a.py",
                line=1,
                description="d",
                why_reliability="w",
                expected_evidence="e",
                present=True,
                difficulty="easy",
            )
        ],
    )}
    metrics = evaluate([], gold)
    assert metrics.per_repo[0].fn == 1
    assert metrics.micro_recall == 0.0
