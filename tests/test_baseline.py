from __future__ import annotations

import json
from pathlib import Path

from cri.baseline.collect import collect_repository, list_repository_dirs
from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMResponse
from cri.baseline.parse import parse_findings
from cri.baseline.runner import analyze_repository, run_baseline
from cri.baseline.variants import ABSTENTION
from cri.evaluation.cli import main as eval_main
from cri.evaluation.load import load_ground_truth_dir
from cri.evaluation.metrics import evaluate
from cri.models.finding import Evidence, Finding, FindingList

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "repositories"
GT = ROOT / "benchmark" / "ground_truth"


def _config(**kwargs) -> BaselineConfig:
    defaults = dict(
        provider="openai",
        model="mock-model",
        temperature=0.0,
        max_tokens=4096,
        max_bundle_chars=200_000,
        api_key="not-used",
        base_url="https://example.invalid/v1",
        usd_per_million_prompt_tokens=None,
        usd_per_million_completion_tokens=None,
    )
    defaults.update(kwargs)
    return BaselineConfig(**defaults)


class FakeClient:
    def __init__(self, text: str, prompt_tokens: int | None = 10, completion_tokens: int | None = 5):
        self.text = text
        self.calls: list[str] = []
        self.system_prompts: list[str | None] = []
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse:
        self.calls.append(user_text)
        self.system_prompts.append(system_prompt)
        return LLMResponse(
            text=self.text,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            raw_http_body="{}",
        )


def test_collects_only_python_and_excludes_readme():
    collected = collect_repository(BENCH / "cri-01-bare-except")
    assert [f.relative_path for f in collected.files] == ["checkout.py"]
    assert "README.md" in collected.excluded


def test_includes_tests_and_stable_order(tmp_path: Path):
    repo = tmp_path / "demo"
    (repo / "b").mkdir(parents=True)
    (repo / "a").mkdir()
    (repo / "z.py").write_text("z = 1\n", encoding="utf-8")
    (repo / "a" / "test_a.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (repo / "b" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("nope\n", encoding="utf-8")
    collected = collect_repository(repo, repository_id="demo")
    assert [f.relative_path for f in collected.files] == ["a/test_a.py", "b/mod.py", "z.py"]
    again = collect_repository(repo, repository_id="demo")
    assert collected.bundle_sha256 == again.bundle_sha256
    assert collected.bundle == again.bundle


def test_list_repos_sorted():
    names = [p.name for p in list_repository_dirs(BENCH)]
    assert names == sorted(names)
    assert len(names) == 12


def test_bundle_contains_line_numbers():
    collected = collect_repository(BENCH / "cri-01-bare-except")
    assert "    16|    except:" in collected.bundle or "    16|    except:\n" in collected.bundle
    assert collected.bundle.startswith("repository_id: cri-01-bare-except")


def test_finding_schema_validation():
    finding = Finding(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="checkout.py",
        line=16,
        description="bare except",
        evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
    )
    FindingList(system="baseline", findings=[finding])


def test_malformed_json_yields_no_findings():
    parsed = parse_findings("this is not json", "cri-01-bare-except")
    assert parsed.findings == []
    assert parsed.status == "json_parse_error"
    assert parsed.error


def test_missing_findings_key_is_schema_error():
    parsed = parse_findings('{"issues": []}', "cri-01-bare-except")
    assert parsed.findings == []
    assert parsed.status == "schema_error"


def test_invalid_item_dropped_valid_kept():
    raw = json.dumps(
        {
            "findings": [
                {
                    "category": "not_a_category",
                    "severity": "high",
                    "file": "checkout.py",
                    "line": 16,
                    "description": "bad",
                    "evidence": {
                        "file": "checkout.py",
                        "line_start": 16,
                        "line_end": 16,
                        "quote": "except:",
                    },
                },
                {
                    "category": "error_handling",
                    "severity": "high",
                    "file": "checkout.py",
                    "line": 16,
                    "description": "bare except",
                    "evidence": {
                        "file": "checkout.py",
                        "line_start": 16,
                        "line_end": 16,
                        "quote": "except:",
                    },
                },
            ]
        }
    )
    parsed = parse_findings(raw, "cri-01-bare-except")
    assert parsed.status == "partial_invalid"
    assert parsed.invalid_finding_count == 1
    assert len(parsed.findings) == 1
    assert parsed.findings[0].repository_id == "cri-01-bare-except"


def test_forced_repository_id():
    raw = json.dumps(
        {
            "findings": [
                {
                    "repository_id": "wrong-id",
                    "category": "error_handling",
                    "severity": "low",
                    "file": "checkout.py",
                    "line": 1,
                    "description": "x",
                    "evidence": {
                        "file": "checkout.py",
                        "line_start": 1,
                        "line_end": 1,
                        "quote": "#",
                    },
                }
            ]
        }
    )
    parsed = parse_findings(raw, "cri-01-bare-except")
    assert parsed.findings[0].repository_id == "cri-01-bare-except"


def test_over_limit_skips_llm(tmp_path: Path):
    client = FakeClient('{"findings":[]}')
    config = _config(max_bundle_chars=10)
    findings, meta, _, raw = analyze_repository(
        collect_repository(BENCH / "cri-01-bare-except"),
        client,
        config,
    )
    assert findings == []
    assert meta.parse_status == "over_limit"
    assert client.calls == []
    assert raw == ""


def test_runner_writes_artifacts_and_meta(tmp_path: Path):
    out = tmp_path / "run"
    bench = tmp_path / "repos"
    src = bench / "mini"
    src.mkdir(parents=True)
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    (src / "README.md").write_text("hi\n", encoding="utf-8")
    payload = {"findings": []}
    client = FakeClient(json.dumps(payload), prompt_tokens=11, completion_tokens=3)
    listing, meta = run_baseline(
        bench,
        out,
        _config(),
        client=client,
        evaluate_run=False,
    )
    assert listing.system == "baseline"
    assert (out / "findings.json").is_file()
    assert (out / "run_meta.json").is_file()
    assert (out / "raw" / "prompts" / "mini.txt").is_file()
    assert (out / "raw" / "responses" / "mini.txt").is_file()
    assert (out / "raw" / "bundles" / "mini.txt").is_file()
    assert (out / "raw" / "manifests" / "mini.json").is_file()
    dumped = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert dumped["system_id"] == "baseline"
    assert dumped["model"] == "mock-model"
    assert dumped["provider"] == "openai"
    assert dumped["temperature"] == 0.0
    assert dumped["repos"][0]["prompt_tokens"] == 11
    assert dumped["repos"][0]["completion_tokens"] == 3
    assert dumped["repos"][0]["parse_status"] == "ok"
    assert "api_key" not in json.dumps(dumped).lower()
    manifest = json.loads((out / "raw" / "manifests" / "mini.json").read_text(encoding="utf-8"))
    assert manifest["excluded"] == ["README.md"]


def test_abstention_variant_uses_separate_prompt(tmp_path: Path):
    out = tmp_path / "run"
    bench = tmp_path / "repos"
    src = bench / "mini"
    src.mkdir(parents=True)
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    client = FakeClient('{"findings":[]}')
    listing, meta = run_baseline(
        bench,
        out,
        _config(),
        client=client,
        evaluate_run=False,
        variant=ABSTENTION,
    )
    assert listing.system == "baseline-abstention"
    assert meta.system_id == "baseline-abstention"
    assert meta.experiment_id == "EXP-1-abstention"
    assert client.system_prompts
    assert "Do not aim for one finding per repository" in (client.system_prompts[0] or "")
    assert "Do not invent an issue" in (out / "raw" / "prompts" / "mini.txt").read_text(encoding="utf-8")


def test_evaluation_integration_with_mocked_findings(tmp_path: Path):
    """Mocked findings exercising eval — not a claimed model score."""
    out = tmp_path / "run"
    client = FakeClient(
        json.dumps(
            {
                "findings": [
                    {
                        "category": "error_handling",
                        "severity": "high",
                        "file": "checkout.py",
                        "line": 16,
                        "description": "bare except swallows charge failures",
                        "evidence": {
                            "file": "checkout.py",
                            "line_start": 16,
                            "line_end": 17,
                            "quote": "except:",
                        },
                    }
                ]
            }
        )
    )
    one = tmp_path / "one"
    repo = one / "cri-01-bare-except"
    repo.mkdir(parents=True)
    (repo / "checkout.py").write_text(
        (BENCH / "cri-01-bare-except" / "checkout.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    gt_dir = tmp_path / "gt"
    gt_dir.mkdir()
    (gt_dir / "cri-01-bare-except.yaml").write_text(
        (GT / "cri-01-bare-except.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    run_baseline(one, out, _config(), client=client, ground_truth_dir=gt_dir)
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["per_repo"][0]["tp"] == 1
    eval_main(
        [
            "--predictions",
            str(out / "findings.json"),
            "--ground-truth-dir",
            str(gt_dir),
            "--repos-dir",
            str(one),
            "--run-meta",
            str(out / "run_meta.json"),
            "--output",
            str(out / "metrics-cli.json"),
        ]
    )
    assert (out / "metrics-cli.json").is_file()


def test_empty_findings_eval_on_gold():
    gold = load_ground_truth_dir(GT)
    metrics = evaluate([], gold)
    assert metrics.false_positive_count == 0
    assert metrics.micro_recall == 0.0
    assert metrics.negative_repo_count == 3
    assert metrics.repo_level_fpr == 0.0
