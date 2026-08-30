from __future__ import annotations

from pathlib import Path

from cri.evaluation.load import load_ground_truth_dir
from cri.evaluation.metrics import evaluate
from cri.models.finding import FindingList
from cri.models.run_meta import RunMeta


def write_metrics(
    finding_list: FindingList,
    run_meta: RunMeta,
    output_path: Path,
    benchmark_dir: Path,
    ground_truth_dir: Path,
) -> None:
    gold = load_ground_truth_dir(ground_truth_dir)
    roots = {repo_id: benchmark_dir / repo_id for repo_id in gold}
    metrics = evaluate(
        finding_list.findings,
        gold,
        repo_roots=roots,
        run_meta=run_meta,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(metrics.model_dump_json(indent=2) + "\n", encoding="utf-8")
