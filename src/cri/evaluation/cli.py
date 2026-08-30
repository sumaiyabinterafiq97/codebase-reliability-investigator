from __future__ import annotations

import argparse
import json
from pathlib import Path

from cri.evaluation.load import load_ground_truth_dir
from cri.evaluation.metrics import evaluate
from cri.models.finding import FindingList
from cri.models.run_meta import RunMeta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate CRI findings against ground truth.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=Path("benchmark/ground_truth"),
    )
    parser.add_argument(
        "--repos-dir",
        type=Path,
        default=Path("benchmark/repositories"),
    )
    parser.add_argument("--run-meta", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = json.loads(args.predictions.read_text(encoding="utf-8"))
    finding_list = FindingList.model_validate(payload)
    gold = load_ground_truth_dir(args.ground_truth_dir)
    roots = {repo_id: args.repos_dir / repo_id for repo_id in gold}
    meta = None
    if args.run_meta is not None:
        meta = RunMeta.model_validate_json(args.run_meta.read_text(encoding="utf-8"))

    metrics = evaluate(finding_list.findings, gold, repo_roots=roots, run_meta=meta)
    text = metrics.model_dump_json(indent=2)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
