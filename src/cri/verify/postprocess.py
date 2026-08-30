from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cri.evaluation.write import write_metrics
from cri.models.finding import FindingList
from cri.models.run_meta import RunMeta
from cri.verify.evidence import apply_evidence
from cri.verify.filters import apply_filters


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def postprocess_run(
    source_dir: Path,
    output_dir: Path,
    repos_dir: Path,
    ground_truth_dir: Path,
    *,
    system_id: str,
    experiment_id: str,
    notes: str,
    apply_det_filters: bool,
    apply_evidence_repair: bool,
    evaluate_run: bool = True,
) -> FindingList:
    started = datetime.now(timezone.utc)
    findings_path = source_dir / "findings.json"
    parent_meta = RunMeta.model_validate_json(
        (source_dir / "run_meta.json").read_text(encoding="utf-8")
    )
    listing = FindingList.model_validate_json(findings_path.read_text(encoding="utf-8"))
    findings = list(listing.findings)
    filter_log: list[dict] = []
    evidence_log: list[dict] = []

    if apply_det_filters:
        findings, filter_log = apply_filters(findings, repos_dir)
        _write(output_dir / "raw" / "filter_log.json", json.dumps(filter_log, indent=2) + "\n")
    if apply_evidence_repair:
        findings, evidence_log = apply_evidence(findings, repos_dir)
        _write(output_dir / "raw" / "evidence_log.json", json.dumps(evidence_log, indent=2) + "\n")

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    out_list = FindingList(system=system_id, findings=findings)
    run_meta = RunMeta(
        system=system_id,
        system_id=system_id,
        experiment_id=experiment_id,
        parent_run=str(source_dir),
        provider=parent_meta.provider,
        model=parent_meta.model,
        temperature=parent_meta.temperature,
        max_tokens=parent_meta.max_tokens,
        started_at=started.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        usd_per_million_prompt_tokens=None,
        usd_per_million_completion_tokens=None,
        notes=notes,
        repos=[
            r.model_copy(
                update={
                    "runtime_seconds": elapsed / max(len(parent_meta.repos), 1),
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "parse_status": "postprocess",
                }
            )
            for r in parent_meta.repos
        ],
    )
    _write(output_dir / "findings.json", out_list.model_dump_json(indent=2) + "\n")
    _write(output_dir / "run_meta.json", run_meta.model_dump_json(indent=2) + "\n")
    _write(
        output_dir / "raw" / "source.json",
        json.dumps({"parent": str(source_dir), "elapsed_seconds": elapsed}, indent=2) + "\n",
    )
    if evaluate_run:
        write_metrics(
            out_list,
            run_meta,
            output_dir / "metrics.json",
            repos_dir,
            ground_truth_dir,
        )
    return out_list
