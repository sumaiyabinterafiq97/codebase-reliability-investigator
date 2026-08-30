"""EXP-4: one LLM confirm/reject per finding that survived deterministic filters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMClient, LLMError, client_from_config
from cri.evaluation.write import write_metrics
from cri.models.finding import Finding, FindingList
from cri.models.run_meta import RepoRuntime, RunMeta
from cri.verify.filters import apply_filters
from cri.verify.verifier_input import build_user_prompt, quote_in_file
from cri.verify.verifier_parse import parse_verifier_response
from cri.verify.verifier_prompt import VERIFIER_SYSTEM_PROMPT


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_one(
    finding: Finding,
    repo_root: Path,
    client: LLMClient,
    index: int,
) -> dict:
    started = datetime.now(timezone.utc)
    prompt = build_user_prompt(finding, repo_root)
    raw = ""
    prompt_tokens = completion_tokens = None
    parse_status = "ok"
    error = None
    result = None
    try:
        response = client.complete(prompt, system_prompt=VERIFIER_SYSTEM_PROMPT)
        raw = response.text
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        result, parse_status = parse_verifier_response(raw)
        if result is None:
            error = parse_status
            parse_status = "parse_error"
    except LLMError as exc:
        parse_status = "llm_error"
        error = str(exc)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    # Fail-open on invalid/LLM error: keep the finding (preserve recall).
    if result is None:
        decision = "confirm"
        fail_open = True
    else:
        decision = result.decision
        fail_open = False

    evidence_ok = None
    if result is not None:
        evidence_ok = quote_in_file(
            repo_root,
            result.evidence.file,
            result.evidence.start_line,
            result.evidence.end_line,
            result.evidence.quote,
        )

    return {
        "index": index,
        "repository_id": finding.repository_id,
        "category": finding.category,
        "file": finding.file,
        "line": finding.line,
        "decision": decision,
        "fail_open": fail_open,
        "parse_status": parse_status,
        "error": error,
        "confidence": None if result is None else result.confidence,
        "reason": None if result is None else result.reason,
        "runtime_seconds": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "verifier_evidence_in_source": evidence_ok,
        "parsed": None if result is None else result.model_dump(),
        "prompt": prompt,
        "raw": raw,
    }


def run_semantic_verifier(
    source_dir: Path,
    output_dir: Path,
    repos_dir: Path,
    ground_truth_dir: Path,
    config: BaselineConfig,
    client: LLMClient | None = None,
    evaluate_run: bool = True,
) -> FindingList:
    started_at = _now()
    parent_meta = RunMeta.model_validate_json(
        (source_dir / "run_meta.json").read_text(encoding="utf-8")
    )
    listing = FindingList.model_validate_json(
        (source_dir / "findings.json").read_text(encoding="utf-8")
    )
    llm = client or client_from_config(config)

    surviving, filter_log = apply_filters(list(listing.findings), repos_dir)
    _write(output_dir / "raw" / "filter_log.json", json.dumps(filter_log, indent=2) + "\n")
    _write(output_dir / "raw" / "system_prompt.txt", VERIFIER_SYSTEM_PROMPT)

    kept: list[Finding] = []
    logs: list[dict] = []
    by_repo: dict[str, list[dict]] = {}

    for i, finding in enumerate(surviving):
        repo_root = repos_dir / finding.repository_id
        log = verify_one(finding, repo_root, llm, i)
        logs.append({k: v for k, v in log.items() if k not in {"prompt", "raw"}})
        by_repo.setdefault(finding.repository_id, []).append(log)
        key = f"{finding.repository_id}__{i}"
        _write(output_dir / "raw" / "prompts" / f"{key}.txt", log["prompt"])
        _write(output_dir / "raw" / "responses" / f"{key}.txt", log["raw"])
        _write(
            output_dir / "raw" / "parsed" / f"{key}.json",
            json.dumps({k: v for k, v in log.items() if k not in {"prompt", "raw"}}, indent=2)
            + "\n",
        )
        if log["decision"] == "confirm":
            kept.append(finding)

    confirmed = sum(1 for x in logs if x["decision"] == "confirm")
    rejected = sum(1 for x in logs if x["decision"] == "reject")
    fail_open_n = sum(1 for x in logs if x["fail_open"])
    evidence_yes = sum(1 for x in logs if x["verifier_evidence_in_source"] is True)
    evidence_no = sum(1 for x in logs if x["verifier_evidence_in_source"] is False)
    evidence_na = sum(1 for x in logs if x["verifier_evidence_in_source"] is None)

    qualitative = {
        "definition": (
            "verifier_evidence_in_source is true iff the verifier quote is a substring "
            "of the cited file (window or full file). Count only; not a new F1."
        ),
        "confirmed": confirmed,
        "rejected": rejected,
        "fail_open_confirms": fail_open_n,
        "calls": len(logs),
        "evidence_quote_in_source_true": evidence_yes,
        "evidence_quote_in_source_false": evidence_no,
        "evidence_quote_in_source_na": evidence_na,
        "decisions": logs,
    }
    _write(output_dir / "raw" / "verifier_log.json", json.dumps(logs, indent=2) + "\n")
    _write(
        output_dir / "qualitative_evidence.json",
        json.dumps(qualitative, indent=2) + "\n",
    )

    repo_metas: list[RepoRuntime] = []
    parent_by_id = {r.repository_id: r for r in parent_meta.repos}
    all_ids = sorted(set(parent_by_id) | set(by_repo))
    for repo_id in all_ids:
        calls = by_repo.get(repo_id, [])
        pt = [c["prompt_tokens"] for c in calls if c["prompt_tokens"] is not None]
        ct = [c["completion_tokens"] for c in calls if c["completion_tokens"] is not None]
        times = [c["runtime_seconds"] for c in calls if c["runtime_seconds"] is not None]
        repo_metas.append(
            RepoRuntime(
                repository_id=repo_id,
                runtime_seconds=sum(times) if times else 0.0,
                prompt_tokens=sum(pt) if pt else None,
                completion_tokens=sum(ct) if ct else None,
                parse_status="verified" if calls else "no_candidate",
                error=None,
            )
        )

    out_list = FindingList(system="baseline-filters-verifier", findings=kept)
    run_meta = RunMeta(
        system="baseline-filters-verifier",
        system_id="baseline-filters-verifier",
        experiment_id="EXP-4-semantic-verifier",
        parent_run=str(source_dir),
        provider=config.provider,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        started_at=started_at,
        finished_at=_now(),
        usd_per_million_prompt_tokens=config.usd_per_million_prompt_tokens,
        usd_per_million_completion_tokens=config.usd_per_million_completion_tokens,
        notes=(
            "EXP-4: deterministic filters (unchanged) then one LLM confirm/reject per "
            f"surviving finding. calls={len(logs)} confirm={confirmed} reject={rejected} "
            f"fail_open={fail_open_n}. Filters handle re-raise/lock/test-file; verifier "
            "only leftover semantic candidates. Invalid verifier JSON fail-opens to confirm."
        ),
        repos=repo_metas,
    )
    _write(output_dir / "findings.json", out_list.model_dump_json(indent=2) + "\n")
    _write(output_dir / "run_meta.json", run_meta.model_dump_json(indent=2) + "\n")
    if evaluate_run:
        write_metrics(
            out_list,
            run_meta,
            output_dir / "metrics.json",
            repos_dir,
            ground_truth_dir,
        )
    return out_list
