"""EXP-5: EXP-2 filters, then a gated fail-open one-tool LLM review.

EXP-4 remains in verifier_run.py and is unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMClient, LLMError, client_from_config
from cri.evaluation.write import write_metrics
from cri.models.finding import Finding, FindingList
from cri.models.run_meta import RepoRuntime, RunMeta
from cri.models.trajectory import TrajectoryEvent, TrajectoryLog
from cri.verify.enclosing_block import enclosing_block
from cri.verify.filters import apply_filters
from cri.verify.gate import needs_semantic_review
from cri.verify.gated_prompt import GATED_SYSTEM_PROMPT, build_gated_user_prompt
from cri.verify.verifier_parse import parse_verifier_response

SYSTEM_ID = "baseline-filters-gated-verifier"
EXPERIMENT_ID = "EXP-5-gated-semantic"

EnclosingBlockFn = Callable[..., dict[str, Any]]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def _trajectory(
    repository_id: str,
    events: list[TrajectoryEvent],
) -> TrajectoryLog:
    numbered = []
    for i, event in enumerate(events, start=1):
        numbered.append(event.model_copy(update={"sequence": i}))
    return TrajectoryLog(repository_id=repository_id, system=SYSTEM_ID, events=numbered)


def review_gated_finding(
    finding: Finding,
    repo_root: Path,
    client: LLMClient,
    index: int,
    *,
    enclosing_block_fn: EnclosingBlockFn | None = None,
) -> dict[str, Any]:
    """One tool call + one LLM call. Fail-open: only a valid reject drops the finding."""
    started = datetime.now(timezone.utc)
    block_fn = enclosing_block_fn or enclosing_block
    events: list[TrajectoryEvent] = [
        TrajectoryEvent(
            sequence=0,
            kind="instruction",
            content=GATED_SYSTEM_PROMPT,
        ),
        TrajectoryEvent(
            sequence=0,
            kind="action",
            content=_dump(
                {
                    "category": finding.category,
                    "file": finding.file,
                    "description": finding.description,
                    "evidence": finding.evidence.model_dump(),
                    "span": list(finding.location_span()),
                }
            ),
        ),
    ]
    start, end = finding.location_span()
    tool_args = {"path": finding.file, "start_line": start, "end_line": end}
    events.append(
        TrajectoryEvent(
            sequence=0,
            kind="action",
            content="enclosing_block",
            tool_name="enclosing_block",
            tool_args=tool_args,
        )
    )

    raw = ""
    prompt = ""
    prompt_tokens = completion_tokens = None
    parse_status = "ok"
    error = None
    result = None
    llm_calls = 0
    fail_open = False
    block: dict[str, Any] | None = None

    try:
        block = block_fn(
            finding.file,
            start,
            end,
            repo_root=repo_root,
        )
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="tool_result",
                content=_dump(block),
                tool_name="enclosing_block",
                tool_args=tool_args,
                ok=True,
            )
        )
    except Exception as exc:
        error = f"tool_error: {exc}"
        parse_status = "tool_error"
        fail_open = True
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="tool_result",
                content=error,
                tool_name="enclosing_block",
                tool_args=tool_args,
                ok=False,
            )
        )
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content="fail_open: tool failure; keep finding",
                ok=False,
            )
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        trajectory = _trajectory(finding.repository_id, events)
        return {
            "index": index,
            "repository_id": finding.repository_id,
            "category": finding.category,
            "file": finding.file,
            "line": finding.line,
            "gated": True,
            "semantic_review": "fail_open",
            "decision": "confirm",
            "kept": True,
            "fail_open": True,
            "parse_status": parse_status,
            "error": error,
            "confidence": None,
            "reason": None,
            "runtime_seconds": elapsed,
            "prompt_tokens": None,
            "completion_tokens": None,
            "llm_calls": 0,
            "parsed": None,
            "prompt": "",
            "raw": "",
            "block": None,
            "trajectory": trajectory,
        }

    prompt = build_gated_user_prompt(finding, block)
    try:
        response = client.complete(prompt, system_prompt=GATED_SYSTEM_PROMPT)
        llm_calls = 1
        raw = response.text
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="action",
                content="llm_complete",
            )
        )
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content=raw,
                ok=True,
            )
        )
        result, parse_status = parse_verifier_response(raw)
        if result is None:
            error = parse_status
            parse_status = "parse_error"
            fail_open = True
    except LLMError as exc:
        parse_status = "llm_error"
        error = str(exc)
        fail_open = True
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content=f"llm_error: {exc}",
                ok=False,
            )
        )
    except Exception as exc:
        parse_status = "unexpected_error"
        error = str(exc)
        fail_open = True
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content=f"unexpected_error: {exc}",
                ok=False,
            )
        )

    if result is None:
        decision = "confirm"
        fail_open = True
        kept = True
        semantic_review = "fail_open"
        reason = None
        confidence = None
        parsed = None
    else:
        decision = result.decision
        kept = decision != "reject"
        semantic_review = decision
        reason = result.reason
        confidence = result.confidence
        parsed = result.model_dump()
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content=_dump(
                    {
                        "decision": decision,
                        "reason": reason,
                        "confidence": confidence,
                        "kept": kept,
                    }
                ),
                ok=True,
            )
        )

    if fail_open:
        events.append(
            TrajectoryEvent(
                sequence=0,
                kind="feedback",
                content=f"fail_open: {error}; keep finding",
                ok=False,
            )
        )

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    trajectory = _trajectory(finding.repository_id, events)
    return {
        "index": index,
        "repository_id": finding.repository_id,
        "category": finding.category,
        "file": finding.file,
        "line": finding.line,
        "gated": True,
        "semantic_review": semantic_review,
        "decision": decision,
        "kept": kept,
        "fail_open": fail_open,
        "parse_status": parse_status,
        "error": error,
        "confidence": confidence,
        "reason": reason,
        "runtime_seconds": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "llm_calls": llm_calls,
        "parsed": parsed,
        "prompt": prompt,
        "raw": raw,
        "block": block,
        "trajectory": trajectory,
    }


def run_gated_semantic(
    source_dir: Path,
    output_dir: Path,
    repos_dir: Path,
    ground_truth_dir: Path,
    config: BaselineConfig,
    client: LLMClient | None = None,
    evaluate_run: bool = True,
    enclosing_block_fn: EnclosingBlockFn | None = None,
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
    _write(output_dir / "raw" / "system_prompt.txt", GATED_SYSTEM_PROMPT)

    kept: list[Finding] = []
    logs: list[dict] = []
    gate_log: list[dict] = []
    trajectories: list[dict] = []
    by_repo: dict[str, list[dict]] = {}

    for i, finding in enumerate(surviving):
        repo_root = repos_dir / finding.repository_id
        gated = needs_semantic_review(finding, repo_root)
        gate_row = {
            "index": i,
            "repository_id": finding.repository_id,
            "category": finding.category,
            "file": finding.file,
            "line": finding.line,
            "gated": gated,
        }
        if not gated:
            gate_row["semantic_review"] = "bypassed"
            gate_log.append(gate_row)
            logs.append(
                {
                    "index": i,
                    "repository_id": finding.repository_id,
                    "category": finding.category,
                    "file": finding.file,
                    "line": finding.line,
                    "gated": False,
                    "semantic_review": "bypassed",
                    "decision": "confirm",
                    "kept": True,
                    "fail_open": False,
                    "parse_status": "bypassed",
                    "error": None,
                    "confidence": None,
                    "reason": None,
                    "runtime_seconds": 0.0,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "llm_calls": 0,
                }
            )
            kept.append(finding)
            continue

        log = review_gated_finding(
            finding,
            repo_root,
            llm,
            i,
            enclosing_block_fn=enclosing_block_fn,
        )
        gate_row["semantic_review"] = log["semantic_review"]
        gate_log.append(gate_row)
        trajectory: TrajectoryLog = log["trajectory"]
        trajectories.append(trajectory.model_dump())
        _write(
            output_dir / "raw" / "trajectories" / f"{finding.repository_id}__{i}.json",
            trajectory.model_dump_json(indent=2) + "\n",
        )
        _write(output_dir / "raw" / "prompts" / f"{finding.repository_id}__{i}.txt", log["prompt"])
        _write(output_dir / "raw" / "responses" / f"{finding.repository_id}__{i}.txt", log["raw"])
        slim = {k: v for k, v in log.items() if k not in {"prompt", "raw", "trajectory", "block"}}
        _write(
            output_dir / "raw" / "parsed" / f"{finding.repository_id}__{i}.json",
            json.dumps(slim, indent=2) + "\n",
        )
        logs.append(slim)
        by_repo.setdefault(finding.repository_id, []).append(log)
        if log["kept"]:
            kept.append(finding)

    confirmed = sum(1 for x in logs if x["decision"] == "confirm" and x["gated"])
    rejected = sum(1 for x in logs if x["decision"] == "reject")
    fail_open_n = sum(1 for x in logs if x["fail_open"])
    gated_n = sum(1 for x in gate_log if x["gated"])
    bypassed_n = sum(1 for x in gate_log if not x["gated"])
    llm_calls = sum(x.get("llm_calls", 0) for x in logs)

    status = {
        "parent_run": str(source_dir),
        "system_id": SYSTEM_ID,
        "experiment_id": EXPERIMENT_ID,
        "gated": gated_n,
        "bypassed": bypassed_n,
        "llm_calls": llm_calls,
        "confirmed": confirmed,
        "rejected": rejected,
        "fail_open": fail_open_n,
        "gate": gate_log,
        "semantic_review": logs,
    }
    _write(output_dir / "raw" / "gate_log.json", json.dumps(gate_log, indent=2) + "\n")
    _write(output_dir / "raw" / "review_log.json", json.dumps(logs, indent=2) + "\n")
    _write(output_dir / "raw" / "trajectories.json", json.dumps(trajectories, indent=2) + "\n")
    _write(output_dir / "raw" / "exp5_status.json", json.dumps(status, indent=2) + "\n")

    repo_metas: list[RepoRuntime] = []
    parent_by_id = {r.repository_id: r for r in parent_meta.repos}
    all_ids = sorted(set(parent_by_id) | {f.repository_id for f in surviving})
    for repo_id in all_ids:
        calls = by_repo.get(repo_id, [])
        pt = [c["prompt_tokens"] for c in calls if c["prompt_tokens"] is not None]
        ct = [c["completion_tokens"] for c in calls if c["completion_tokens"] is not None]
        times = [c["runtime_seconds"] for c in calls if c["runtime_seconds"] is not None]
        gate_rows = [g for g in gate_log if g["repository_id"] == repo_id]
        if not gate_rows:
            parse_status = "filtered"
        elif any(g["gated"] for g in gate_rows):
            parse_status = gate_rows[0].get("semantic_review") or "gated_review"
        else:
            parse_status = "bypassed"
        repo_metas.append(
            RepoRuntime(
                repository_id=repo_id,
                runtime_seconds=sum(times) if times else 0.0,
                prompt_tokens=sum(pt) if pt else None,
                completion_tokens=sum(ct) if ct else None,
                parse_status=parse_status,
                error=None,
            )
        )

    out_list = FindingList(system=SYSTEM_ID, findings=kept)
    run_meta = RunMeta(
        system=SYSTEM_ID,
        system_id=SYSTEM_ID,
        experiment_id=EXPERIMENT_ID,
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
            "EXP-5: unchanged EXP-2 filters, then needs_semantic_review gate, then one "
            "enclosing_block tool + one CONFIRM-unless-prevented LLM call per gated "
            f"finding. survivors={len(surviving)} gated={gated_n} bypassed={bypassed_n} "
            f"llm_calls={llm_calls} confirm={confirmed} reject={rejected} "
            f"fail_open={fail_open_n}. Invalid JSON / tool / LLM errors fail-open to keep."
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
