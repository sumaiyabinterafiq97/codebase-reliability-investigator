from pathlib import Path

from cri.baseline.prompt import ABSTENTION_SYSTEM_PROMPT, SYSTEM_PROMPT, abstention_user_prompt
from cri.baseline.variants import ABSTENTION
from cri.models.finding import Evidence, Finding
from cri.verify.filters import apply_filters
from cri.verify.locked_write import should_suppress as lock_suppress
from cri.verify.reraise import should_suppress as reraise_suppress
from cri.verify.cites_test_module import should_suppress as cites_test_suppress
from cri.verify.tested_path import should_suppress as coverage_suppress
ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "repositories"


def _f(**kwargs) -> Finding:
    data = dict(
        repository_id="x",
        category="error_handling",
        severity="high",
        file="a.py",
        line=1,
        description="d",
        evidence=Evidence(file="a.py", line_start=1, line_end=1, quote="x"),
    )
    data.update(kwargs)
    return Finding(**data)


def test_abstention_prompt_allows_empty_and_does_not_require_a_finding():
    assert "at least one" not in ABSTENTION_SYSTEM_PROMPT.lower()
    assert '{"findings": []}' in ABSTENTION_SYSTEM_PROMPT
    user = abstention_user_prompt("r", "bundle")
    assert "Do not invent an issue" in user
    assert ABSTENTION.system_id == "baseline-abstention"
    assert ABSTENTION.system_prompt != SYSTEM_PROMPT


def test_reraise_suppresses_logged_reraise():
    finding = _f(
        repository_id="cri-10-logged-reraise",
        file="transfers.py",
        line=17,
        line_start=17,
        line_end=19,
        evidence=Evidence(file="transfers.py", line_start=17, line_end=19, quote="except"),
    )
    assert reraise_suppress(finding, BENCH / "cri-10-logged-reraise") == "error_handling_reraise"


def test_reraise_suppresses_bare_raise():
    finding = _f(
        repository_id="cri-11-clean-checkout",
        file="store.py",
        line=20,
        line_start=19,
        line_end=20,
        evidence=Evidence(file="store.py", line_start=19, line_end=20, quote="raise"),
    )
    assert reraise_suppress(finding, BENCH / "cri-11-clean-checkout")


def test_reraise_does_not_suppress_swallowed_return():
    finding = _f(
        repository_id="cri-01-bare-except",
        file="checkout.py",
        line=16,
        line_start=16,
        line_end=17,
        evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
    )
    assert reraise_suppress(finding, BENCH / "cri-01-bare-except") is None


def test_reraise_does_not_suppress_silent_json_default():
    finding = _f(
        repository_id="cri-06-silent-json-default",
        file="config.py",
        line=9,
        line_start=8,
        line_end=9,
        evidence=Evidence(file="config.py", line_start=8, line_end=9, quote="return {}"),
    )
    assert reraise_suppress(finding, BENCH / "cri-06-silent-json-default") is None


def test_reraise_does_not_suppress_log_then_return_raw():
    finding = _f(
        repository_id="cri-08-log-then-use-corrupt",
        file="billing.py",
        line=13,
        line_start=11,
        line_end=13,
        evidence=Evidence(file="billing.py", line_start=11, line_end=13, quote="return raw"),
    )
    assert reraise_suppress(finding, BENCH / "cri-08-log-then-use-corrupt") is None


def test_lock_suppresses_locked_stock_when_labeled_concurrency():
    finding = _f(
        repository_id="cri-12-locked-and-tested",
        category="state_concurrency",
        file="stock.py",
        line=12,
        line_start=12,
        line_end=12,
        evidence=Evidence(file="stock.py", line_start=12, line_end=12, quote="stock[sku]"),
    )
    assert lock_suppress(finding, BENCH / "cri-12-locked-and-tested") == "state_concurrency_locked_write"


def test_lock_does_not_apply_to_error_handling_label():
    finding = _f(
        repository_id="cri-12-locked-and-tested",
        category="error_handling",
        file="stock.py",
        line=12,
        line_start=12,
        line_end=12,
        evidence=Evidence(file="stock.py", line_start=12, line_end=12, quote="stock[sku]"),
    )
    assert lock_suppress(finding, BENCH / "cri-12-locked-and-tested") is None


def test_lock_does_not_suppress_unlocked_credit():
    finding = _f(
        repository_id="cri-04-racy-balance",
        category="state_concurrency",
        file="wallet.py",
        line=10,
        line_start=10,
        line_end=11,
        evidence=Evidence(file="wallet.py", line_start=10, line_end=11, quote="balance_cents"),
    )
    assert lock_suppress(finding, BENCH / "cri-04-racy-balance") is None


def test_lock_does_not_treat_threadpool_as_lock():
    finding = _f(
        repository_id="cri-04-racy-balance",
        category="state_concurrency",
        file="wallet.py",
        line=15,
        line_start=14,
        line_end=16,
        evidence=Evidence(file="wallet.py", line_start=14, line_end=16, quote="ThreadPoolExecutor"),
    )
    assert lock_suppress(finding, BENCH / "cri-04-racy-balance") is None


def test_lock_does_not_suppress_toctou():
    finding = _f(
        repository_id="cri-07-toctou-inventory",
        category="state_concurrency",
        file="warehouse.py",
        line=11,
        line_start=9,
        line_end=11,
        evidence=Evidence(file="warehouse.py", line_start=9, line_end=11, quote="stock[sku]"),
    )
    assert lock_suppress(finding, BENCH / "cri-07-toctou-inventory") is None


def test_testing_does_not_suppress_untested_fallback():
    finding = _f(
        repository_id="cri-05-untested-fallback",
        category="testing_coverage",
        file="payments.py",
        line=27,
        line_start=24,
        line_end=28,
        evidence=Evidence(file="payments.py", line_start=24, line_end=28, quote="charge_secondary"),
    )
    assert coverage_suppress(finding, BENCH / "cri-05-untested-fallback") is None


def test_testing_suppresses_when_test_calls_fallback(tmp_path: Path):
    (tmp_path / "prod.py").write_text(
        "def fallback():\n    return 1\n\ndef run():\n    try:\n        raise TimeoutError\n    except TimeoutError:\n        return fallback()\n",
        encoding="utf-8",
    )
    (tmp_path / "test_prod.py").write_text(
        "from prod import fallback\n\ndef test_fb():\n    assert fallback() == 1\n",
        encoding="utf-8",
    )
    finding = _f(
        category="testing_coverage",
        file="prod.py",
        line=7,
        line_start=6,
        line_end=8,
        evidence=Evidence(file="prod.py", line_start=6, line_end=8, quote="fallback"),
    )
    assert coverage_suppress(finding, tmp_path) == "testing_coverage_path_exercised"


def test_cites_test_file_suppresses_exp1_pattern():
    finding = _f(
        repository_id="cri-05-untested-fallback",
        category="testing_coverage",
        file="test_payments.py",
        line=4,
        line_start=4,
        line_end=5,
        evidence=Evidence(file="test_payments.py", line_start=4, line_end=5, quote="checkout"),
    )
    assert cites_test_suppress(finding, BENCH / "cri-05-untested-fallback") == "testing_coverage_cites_test_file"


def test_cites_test_file_does_not_suppress_production_path():
    finding = _f(
        repository_id="cri-05-untested-fallback",
        category="testing_coverage",
        file="payments.py",
        line=27,
        line_start=24,
        line_end=28,
        evidence=Evidence(file="payments.py", line_start=24, line_end=28, quote="charge_secondary"),
    )
    assert cites_test_suppress(finding, BENCH / "cri-05-untested-fallback") is None


def test_apply_filters_on_baseline_pattern():
    findings = [
        _f(
            repository_id="cri-10-logged-reraise",
            file="transfers.py",
            line=17,
            line_start=17,
            line_end=19,
            evidence=Evidence(file="transfers.py", line_start=17, line_end=19, quote="except"),
        ),
        _f(
            repository_id="cri-01-bare-except",
            file="checkout.py",
            line=16,
            line_start=16,
            line_end=17,
            evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
        ),
    ]
    kept, log = apply_filters(findings, BENCH)
    assert len(kept) == 1
    assert kept[0].repository_id == "cri-01-bare-except"
    assert log[0]["suppressed"] is True
