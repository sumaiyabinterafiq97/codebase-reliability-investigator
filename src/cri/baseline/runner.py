from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cri.baseline.collect import CollectedRepo, collect_repository, list_repository_dirs
from cri.baseline.config import BaselineConfig
from cri.baseline.llm import LLMClient, LLMError, client_from_config
from cri.baseline.parse import parse_findings
from cri.baseline.variants import ORIGINAL, BaselineVariant
from cri.evaluation.write import write_metrics
from cri.models.finding import Finding, FindingList
from cri.models.run_meta import RepoRuntime, RunMeta


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def analyze_repository(
    collected: CollectedRepo,
    client: LLMClient,
    config: BaselineConfig,
    variant: BaselineVariant = ORIGINAL,
) -> tuple[list[Finding], RepoRuntime, str, str]:
    started = datetime.now(timezone.utc)
    make_user = variant.user_prompt_fn
    if len(collected.bundle) > config.max_bundle_chars:
        runtime = RepoRuntime(
            repository_id=collected.repository_id,
            runtime_seconds=0.0,
            parse_status="over_limit",
            error=(
                f"bundle is {len(collected.bundle)} chars; "
                f"limit is {config.max_bundle_chars}. No truncation; skipped LLM."
            ),
            input_sha256=collected.bundle_sha256,
            file_count=len(collected.files),
            bundle_chars=len(collected.bundle),
        )
        return [], runtime, make_user(collected.repository_id, collected.bundle), ""

    prompt = make_user(collected.repository_id, collected.bundle)
    error: str | None = None
    raw_text = ""
    prompt_tokens = completion_tokens = None
    try:
        response = client.complete(prompt, system_prompt=variant.system_prompt)
        raw_text = response.text
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        parsed = parse_findings(raw_text, collected.repository_id)
        findings = parsed.findings
        status = parsed.status
        error = parsed.error
        invalid_count = parsed.invalid_finding_count
    except LLMError as exc:
        findings = []
        status = "llm_error"
        error = str(exc)
        invalid_count = 0

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    runtime = RepoRuntime(
        repository_id=collected.repository_id,
        runtime_seconds=elapsed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        parse_status=status,
        error=error,
        invalid_finding_count=invalid_count,
        input_sha256=collected.bundle_sha256,
        file_count=len(collected.files),
        bundle_chars=len(collected.bundle),
    )
    return findings, runtime, prompt, raw_text


def run_baseline(
    benchmark_dir: Path,
    output_dir: Path,
    config: BaselineConfig,
    client: LLMClient | None = None,
    ground_truth_dir: Path | None = None,
    evaluate_run: bool = True,
    variant: BaselineVariant = ORIGINAL,
) -> tuple[FindingList, RunMeta]:
    output_dir.mkdir(parents=True, exist_ok=True)
    llm = client or client_from_config(config)
    all_findings: list[Finding] = []
    repo_metas: list[RepoRuntime] = []
    started_at = _now()

    for repo_dir in list_repository_dirs(benchmark_dir):
        collected = collect_repository(repo_dir)
        findings, meta, prompt, raw = analyze_repository(
            collected, llm, config, variant=variant
        )
        all_findings.extend(findings)
        repo_metas.append(meta)
        _write(output_dir / "raw" / "prompts" / f"{collected.repository_id}.txt", prompt)
        _write(output_dir / "raw" / "system_prompt.txt", variant.system_prompt)
        _write(output_dir / "raw" / "responses" / f"{collected.repository_id}.txt", raw)
        _write(output_dir / "raw" / "bundles" / f"{collected.repository_id}.txt", collected.bundle)
        manifest = {
            "repository_id": collected.repository_id,
            "bundle_sha256": collected.bundle_sha256,
            "files": [
                {
                    "path": f.relative_path,
                    "sha256": f.sha256,
                    "line_count": f.line_count,
                }
                for f in collected.files
            ],
            "excluded": list(collected.excluded),
        }
        _write(
            output_dir / "raw" / "manifests" / f"{collected.repository_id}.json",
            json.dumps(manifest, indent=2) + "\n",
        )

    finding_list = FindingList(system=variant.system_id, findings=all_findings)
    run_meta = RunMeta(
        system=variant.system_id,
        system_id=variant.system_id,
        experiment_id=variant.experiment_id,
        provider=config.provider,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        max_bundle_chars=config.max_bundle_chars,
        source_suffixes=[".py"],
        started_at=started_at,
        finished_at=_now(),
        usd_per_million_prompt_tokens=config.usd_per_million_prompt_tokens,
        usd_per_million_completion_tokens=config.usd_per_million_completion_tokens,
        notes=variant.notes,
        repos=repo_metas,
    )
    _write(output_dir / "findings.json", finding_list.model_dump_json(indent=2) + "\n")
    _write(output_dir / "run_meta.json", run_meta.model_dump_json(indent=2) + "\n")

    if evaluate_run and ground_truth_dir is not None and ground_truth_dir.is_dir():
        write_metrics(
            finding_list,
            run_meta,
            output_dir / "metrics.json",
            benchmark_dir,
            ground_truth_dir,
        )

    return finding_list, run_meta
