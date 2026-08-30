from __future__ import annotations

import json
from pathlib import Path

import pytest

from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMError, LLMResponse
from cri.models.finding import Evidence, Finding, FindingList
from cri.models.run_meta import RepoRuntime, RunMeta
from cri.models.trajectory import TrajectoryLog
from cri.verify.enclosing_block import enclosing_block
from cri.verify.gate import needs_semantic_review
from cri.verify.gated_prompt import GATED_SYSTEM_PROMPT
from cri.verify.gated_run import review_gated_finding, run_gated_semantic
from cri.verify.verifier_prompt import VERIFIER_SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "repositories"
BASELINE = ROOT / "outputs" / "baseline-001"
TRUE_POSITIVE_IDS = (
    "cri-01-bare-except",
    "cri-02-unchecked-quantity",
    "cri-03-leaked-file",
    "cri-04-racy-balance",
    "cri-05-untested-fallback",
    "cri-06-silent-json-default",
    "cri-07-toctou-inventory",
    "cri-08-log-then-use-corrupt",
    "cri-09-validate-then-mutate",
)
CRI12_ID = "cri-12-locked-and-tested"


def _config() -> BaselineConfig:
    return BaselineConfig(
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


def _finding(**kwargs) -> Finding:
    data = dict(
        repository_id="case",
        category="error_handling",
        severity="high",
        file="mod.py",
        line=1,
        description="claimed failure",
        evidence=Evidence(file="mod.py", line_start=1, line_end=1, quote="x"),
    )
    data.update(kwargs)
    if "evidence" not in kwargs and "file" in kwargs:
        start = kwargs.get("line_start", kwargs.get("line", 1))
        end = kwargs.get("line_end", start)
        data["evidence"] = Evidence(
            file=kwargs["file"],
            line_start=start,
            line_end=end,
            quote="x",
        )
    return Finding(**data)


def _ok_json(decision: str, quote: str = "x") -> str:
    return json.dumps(
        {
            "decision": decision,
            "reason": "test",
            "confidence": 0.8,
            "evidence": {
                "file": "mod.py",
                "start_line": 1,
                "end_line": 1,
                "quote": quote,
            },
        }
    )


class SeqClient:
    def __init__(self, texts: list[str] | None = None, *, error: Exception | None = None):
        self.texts = list(texts or [])
        self.error = error
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse:
        self.prompts.append(user_text)
        self.system_prompts.append(system_prompt)
        if self.error is not None:
            raise self.error
        text = self.texts.pop(0)
        return LLMResponse(text=text, prompt_tokens=4, completion_tokens=2, raw_http_body="{}")


def test_gate_error_handling_overlapping_except(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def run():\n    try:\n        x = 1\n    except Exception:\n        return None\n",
        encoding="utf-8",
    )
    finding = _finding(line=4, line_start=4, line_end=5)
    assert needs_semantic_review(finding, tmp_path) is False


def test_gate_error_handling_no_except(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def run(n):\n    if n < 0:\n        return False\n    value = n - 1\n    return True\n",
        encoding="utf-8",
    )
    finding = _finding(line=4, line_start=4, line_end=5)
    assert needs_semantic_review(finding, tmp_path) is True


def test_gate_non_error_handling_is_false(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(category="input_validation", line=1, line_start=1, line_end=1)
    assert needs_semantic_review(finding, tmp_path) is False
    finding2 = _finding(category="state_concurrency", line=1, line_start=1, line_end=1)
    assert needs_semantic_review(finding2, tmp_path) is False


def test_gate_missing_file(tmp_path: Path):
    finding = _finding(file="missing.py", line=1, line_start=1, line_end=1)
    assert needs_semantic_review(finding, tmp_path) is False


def test_gate_syntax_error(tmp_path: Path):
    (tmp_path / "mod.py").write_text("def broken(\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    assert needs_semantic_review(finding, tmp_path) is False


def test_gate_wide_span_overlapping_except(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def run():\n    a = 1\n    try:\n        b = 2\n    except ValueError:\n        return\n    c = 3\n",
        encoding="utf-8",
    )
    finding = _finding(line=1, line_start=1, line_end=7)
    assert needs_semantic_review(finding, tmp_path) is False


def test_gate_except_does_not_overlap_nearby_assignment(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def run():\n    try:\n        parse()\n    except ValueError:\n        log()\n    value = 1\n",
        encoding="utf-8",
    )
    finding = _finding(line=6, line_start=6, line_end=6)
    assert needs_semantic_review(finding, tmp_path) is True


def test_production_gate_has_no_benchmark_strings():
    sources = [
        ROOT / "src" / "cri" / "verify" / "gate.py",
        ROOT / "src" / "cri" / "verify" / "enclosing_block.py",
        ROOT / "src" / "cri" / "verify" / "gated_prompt.py",
        ROOT / "src" / "cri" / "verify" / "gated_run.py",
    ]
    forbidden = (
        "cri-01",
        "cri-12",
        "bare-except",
        "locked-and-tested",
        "_lock",
        "available",
    )
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{needle} in {path.name}"


def test_enclosing_block_innermost_function(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def outer():\n"
        "    def inner(n):\n"
        "        with ctx:\n"
        "            if n < 0:\n"
        "                return False\n"
        "            value = n - 1\n"
        "            return True\n",
        encoding="utf-8",
    )
    block = enclosing_block("mod.py", 6, 7, repo_root=tmp_path)
    assert block["file"] == "mod.py"
    assert block["start"] == 2
    assert block["end"] == 7
    assert "FunctionDef" in block["node_types"]
    assert "With" in block["node_types"]
    assert "If" not in block["node_types"]
    assert "6|" in block["text"]
    assert "value = n - 1" in block["text"]


def test_enclosing_block_whole_file_without_function(tmp_path: Path):
    (tmp_path / "mod.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    block = enclosing_block("mod.py", 2, 2, repo_root=tmp_path)
    assert block["start"] == 1
    assert block["end"] == 2
    assert block["node_types"] == []
    assert "a = 1" in block["text"]


def test_enclosing_block_try_except(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def run():\n    try:\n        x = 1\n    except Exception:\n        return x\n",
        encoding="utf-8",
    )
    block = enclosing_block("mod.py", 5, 5, repo_root=tmp_path)
    assert "FunctionDef" in block["node_types"]
    assert "Try" in block["node_types"]
    assert "ExceptHandler" in block["node_types"]


def test_prompt_is_confirm_unless_not_default_reject():
    assert "CONFIRM unless" in GATED_SYSTEM_PROMPT
    assert "CHALLENGE" not in GATED_SYSTEM_PROMPT
    assert "Default to REJECT" not in GATED_SYSTEM_PROMPT
    assert "Default to REJECT unless" not in GATED_SYSTEM_PROMPT
    assert "CHALLENGE" in VERIFIER_SYSTEM_PROMPT
    assert "Default to REJECT" in VERIFIER_SYSTEM_PROMPT


def test_fail_open_on_tool_exception(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    client = SeqClient([_ok_json("reject")])

    def boom(*_args, **_kwargs):
        raise RuntimeError("tool exploded")

    log = review_gated_finding(finding, tmp_path, client, 0, enclosing_block_fn=boom)
    assert log["fail_open"] is True
    assert log["kept"] is True
    assert log["decision"] == "confirm"
    assert log["llm_calls"] == 0
    assert client.prompts == []
    assert log["trajectory"].events[-1].kind == "feedback"


def test_fail_open_on_llm_exception(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    client = SeqClient(error=LLMError("timeout"))
    log = review_gated_finding(finding, tmp_path, client, 0)
    assert log["fail_open"] is True
    assert log["kept"] is True
    assert log["decision"] == "confirm"
    assert log["parse_status"] == "llm_error"


def test_fail_open_on_malformed_response(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    log = review_gated_finding(finding, tmp_path, SeqClient(["not json"]), 0)
    assert log["fail_open"] is True
    assert log["kept"] is True
    assert log["decision"] == "confirm"


def test_fail_open_on_schema_failure(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    raw = json.dumps(
        {
            "decision": "maybe",
            "reason": "x",
            "confidence": 0.5,
            "evidence": {"file": "mod.py", "start_line": 1, "end_line": 1, "quote": "x"},
        }
    )
    log = review_gated_finding(finding, tmp_path, SeqClient([raw]), 0)
    assert log["fail_open"] is True
    assert log["kept"] is True


def test_valid_reject_removes_finding(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    log = review_gated_finding(finding, tmp_path, SeqClient([_ok_json("reject")]), 0)
    assert log["fail_open"] is False
    assert log["kept"] is False
    assert log["decision"] == "reject"
    assert log["llm_calls"] == 1


def test_confirm_keeps_finding(tmp_path: Path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    log = review_gated_finding(finding, tmp_path, SeqClient([_ok_json("confirm")]), 0)
    assert log["kept"] is True
    assert log["decision"] == "confirm"
    assert log["fail_open"] is False


def test_non_gated_findings_bypass_llm(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    repos = tmp_path / "repos"
    repos.mkdir()
    (repos / "alpha").mkdir()
    (repos / "alpha" / "mod.py").write_text(
        "def run():\n    try:\n        x = 1\n    except Exception:\n        return None\n",
        encoding="utf-8",
    )
    (repos / "beta").mkdir()
    (repos / "beta" / "mod.py").write_text("q = 1\n", encoding="utf-8")
    findings = FindingList(
        system="baseline",
        findings=[
            _finding(
                repository_id="alpha",
                file="mod.py",
                line=4,
                line_start=4,
                line_end=5,
                description="swallow",
            ),
            _finding(
                repository_id="beta",
                category="input_validation",
                file="mod.py",
                line=1,
                line_start=1,
                line_end=1,
                description="unchecked",
            ),
        ],
    )
    (src / "findings.json").write_text(findings.model_dump_json(), encoding="utf-8")
    (src / "run_meta.json").write_text(
        RunMeta(
            system="baseline",
            repos=[RepoRuntime(repository_id="alpha"), RepoRuntime(repository_id="beta")],
        ).model_dump_json(),
        encoding="utf-8",
    )
    client = SeqClient([_ok_json("reject")])
    listing = run_gated_semantic(
        src,
        tmp_path / "out",
        repos,
        ROOT / "benchmark" / "ground_truth",
        _config(),
        client=client,
        evaluate_run=False,
    )
    assert client.prompts == []
    assert len(listing.findings) == 2


def test_at_most_one_llm_call_per_gated_finding(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    repos = tmp_path / "repos" / "gamma"
    repos.mkdir(parents=True)
    (repos / "mod.py").write_text("value = 1\n", encoding="utf-8")
    findings = FindingList(
        system="baseline",
        findings=[
            _finding(
                repository_id="gamma",
                file="mod.py",
                line=1,
                line_start=1,
                line_end=1,
                description="assignment labeled error_handling",
            )
        ],
    )
    (src / "findings.json").write_text(findings.model_dump_json(), encoding="utf-8")
    (src / "run_meta.json").write_text(
        RunMeta(system="baseline", repos=[RepoRuntime(repository_id="gamma")]).model_dump_json(),
        encoding="utf-8",
    )
    client = SeqClient([_ok_json("confirm")])
    run_gated_semantic(
        src,
        tmp_path / "out",
        tmp_path / "repos",
        ROOT / "benchmark" / "ground_truth",
        _config(),
        client=client,
        evaluate_run=False,
    )
    assert len(client.prompts) == 1
    assert client.system_prompts == [GATED_SYSTEM_PROMPT]
    assert "CONFIRM unless" in (client.system_prompts[0] or "")
    assert "enclosing_block" in client.prompts[0]


def test_trajectory_records_tool_and_decision(tmp_path: Path):
    (tmp_path / "mod.py").write_text("value = 1\n", encoding="utf-8")
    finding = _finding(line=1, line_start=1, line_end=1)
    log = review_gated_finding(finding, tmp_path, SeqClient([_ok_json("reject")]), 0)
    traj: TrajectoryLog = log["trajectory"]
    kinds = [e.kind for e in traj.events]
    assert kinds[0] == "instruction"
    assert any(e.tool_name == "enclosing_block" and e.kind == "action" for e in traj.events)
    tool_call = next(e for e in traj.events if e.kind == "action" and e.tool_name == "enclosing_block")
    assert tool_call.tool_args == {"path": "mod.py", "start_line": 1, "end_line": 1}
    assert any(e.kind == "tool_result" and e.ok is True for e in traj.events)
    assert any(e.kind == "feedback" and '"decision": "reject"' in e.content for e in traj.events)
    assert traj.system == "baseline-filters-gated-verifier"


def test_baseline_true_positives_do_not_enter_gate():
    listing = FindingList.model_validate_json((BASELINE / "findings.json").read_text(encoding="utf-8"))
    by_id = {f.repository_id: f for f in listing.findings}
    for repo_id in TRUE_POSITIVE_IDS:
        finding = by_id[repo_id]
        assert needs_semantic_review(finding, BENCH / repo_id) is False, repo_id


def test_baseline_cri12_enters_gate():
    listing = FindingList.model_validate_json((BASELINE / "findings.json").read_text(encoding="utf-8"))
    finding = next(f for f in listing.findings if f.repository_id == CRI12_ID)
    assert finding.category == "error_handling"
    assert needs_semantic_review(finding, BENCH / CRI12_ID) is True


def test_runner_on_frozen_baseline_one_gated_call(tmp_path: Path):
    client = SeqClient([_ok_json("reject", quote="return True")])
    listing = run_gated_semantic(
        BASELINE,
        tmp_path / "out",
        BENCH,
        ROOT / "benchmark" / "ground_truth",
        _config(),
        client=client,
        evaluate_run=False,
    )
    assert len(client.prompts) == 1
    kept_ids = {f.repository_id for f in listing.findings}
    assert set(TRUE_POSITIVE_IDS) <= kept_ids
    assert CRI12_ID not in kept_ids
    gate_log = json.loads((tmp_path / "out" / "raw" / "gate_log.json").read_text(encoding="utf-8"))
    gated = [row for row in gate_log if row["gated"]]
    assert len(gated) == 1
    assert gated[0]["repository_id"] == CRI12_ID
    traj_files = list((tmp_path / "out" / "raw" / "trajectories").glob("*.json"))
    assert len(traj_files) == 1
    traj = json.loads(traj_files[0].read_text(encoding="utf-8"))
    assert traj["repository_id"] == CRI12_ID
    meta = json.loads((tmp_path / "out" / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["experiment_id"] == "EXP-5-gated-semantic"
    assert meta["parent_run"].endswith("baseline-001")
    assert not (tmp_path / "out" / "metrics.json").exists()


def test_cli_help_includes_gated(capsys):
    from cri.verify.verifier_cli import main as verify_main

    with pytest.raises(SystemExit) as exc:
        verify_main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--gated" in out
    assert "EXP-5" in out
