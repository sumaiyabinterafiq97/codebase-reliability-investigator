from __future__ import annotations

import json
from pathlib import Path

from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMResponse
from cri.models.finding import Evidence, Finding, FindingList
from cri.models.run_meta import RepoRuntime, RunMeta
from cri.verify.verifier_parse import parse_verifier_response
from cri.verify.verifier_prompt import VERIFIER_SYSTEM_PROMPT
from cri.verify.verifier_run import run_semantic_verifier, verify_one

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "repositories"


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


def _ok_json(decision: str) -> str:
    return json.dumps(
        {
            "decision": decision,
            "reason": "test",
            "confidence": 0.9,
            "evidence": {
                "file": "checkout.py",
                "start_line": 16,
                "end_line": 17,
                "quote": "except:",
            },
        }
    )


class SeqClient:
    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.prompts: list[str] = []

    def complete(self, user_text: str, system_prompt: str | None = None) -> LLMResponse:
        self.prompts.append(user_text)
        text = self.texts.pop(0)
        return LLMResponse(text=text, prompt_tokens=4, completion_tokens=2, raw_http_body="{}")


def test_prompt_challenges_and_has_no_case_ids():
    assert "CHALLENGE" in VERIFIER_SYSTEM_PROMPT
    assert "REJECT" in VERIFIER_SYSTEM_PROMPT
    assert "cri-12" not in VERIFIER_SYSTEM_PROMPT
    assert "logged-reraise" not in VERIFIER_SYSTEM_PROMPT.lower()


def test_parse_confirm_and_reject():
    ok, status = parse_verifier_response(_ok_json("reject"))
    assert status == "ok"
    assert ok is not None
    assert ok.decision == "reject"
    ok2, _ = parse_verifier_response(_ok_json("confirm"))
    assert ok2.decision == "confirm"


def test_parse_malformed():
    result, status = parse_verifier_response("not json")
    assert result is None
    assert "json_parse_error" in status


def test_parse_bad_decision():
    raw = json.dumps(
        {
            "decision": "maybe",
            "reason": "x",
            "confidence": 0.5,
            "evidence": {"file": "a.py", "start_line": 1, "end_line": 1, "quote": "x"},
        }
    )
    result, status = parse_verifier_response(raw)
    assert result is None
    assert "schema_error" in status


def test_fail_open_on_garbage():
    finding = Finding(
        repository_id="cri-01-bare-except",
        category="error_handling",
        severity="high",
        file="checkout.py",
        line=16,
        description="bare except",
        evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
    )
    log = verify_one(finding, BENCH / "cri-01-bare-except", SeqClient(["oops"]), 0)
    assert log["fail_open"] is True
    assert log["decision"] == "confirm"


def test_runner_filters_then_one_call_per_survivor(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    findings = FindingList(
        system="baseline",
        findings=[
            Finding(
                repository_id="cri-01-bare-except",
                category="error_handling",
                severity="high",
                file="checkout.py",
                line=16,
                description="swallow",
                evidence=Evidence(file="checkout.py", line_start=16, line_end=17, quote="except:"),
            ),
            Finding(
                repository_id="cri-10-logged-reraise",
                category="error_handling",
                severity="high",
                file="transfers.py",
                line=17,
                description="broad except",
                evidence=Evidence(file="transfers.py", line_start=17, line_end=19, quote="except"),
            ),
            Finding(
                repository_id="cri-12-locked-and-tested",
                category="error_handling",
                severity="high",
                file="stock.py",
                line=12,
                description="negative stock",
                evidence=Evidence(file="stock.py", line_start=12, line_end=13, quote="stock[sku]"),
            ),
        ],
    )
    (src / "findings.json").write_text(findings.model_dump_json(), encoding="utf-8")
    (src / "run_meta.json").write_text(
        RunMeta(
            system="baseline",
            system_id="baseline",
            repos=[
                RepoRuntime(repository_id="cri-01-bare-except"),
                RepoRuntime(repository_id="cri-10-logged-reraise"),
                RepoRuntime(repository_id="cri-12-locked-and-tested"),
            ],
        ).model_dump_json(),
        encoding="utf-8",
    )
    # cri-10 is filtered; two verifier calls remain.
    client = SeqClient([_ok_json("confirm"), _ok_json("reject")])
    out = tmp_path / "out"
    listing = run_semantic_verifier(
        src,
        out,
        BENCH,
        ROOT / "benchmark" / "ground_truth",
        _config(),
        client=client,
        evaluate_run=True,
    )
    assert len(client.prompts) == 2
    assert all("CHALLENGE" not in p for p in client.prompts)  # challenge is system-side
    ids = {f.repository_id for f in listing.findings}
    assert ids == {"cri-01-bare-except"}
    log = json.loads((out / "raw" / "verifier_log.json").read_text(encoding="utf-8"))
    assert {row["repository_id"] for row in log} == {
        "cri-01-bare-except",
        "cri-12-locked-and-tested",
    }
    assert any(row["decision"] == "reject" for row in log)
    assert (out / "metrics.json").is_file()
    filt = json.loads((out / "raw" / "filter_log.json").read_text(encoding="utf-8"))
    assert any(row["repository_id"] == "cri-10-logged-reraise" and row["suppressed"] for row in filt)
