from __future__ import annotations

import argparse
from pathlib import Path

from cri.baseline.config import BaselineConfig, BaselineConfigError, load_env_file
from cri.baseline.runner import run_baseline
from cri.baseline.variants import VARIANTS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CRI single-prompt baseline runner.")
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("benchmark/repositories"),
        help="Directory containing one subdirectory per repository.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Run directory, e.g. outputs/baseline-001",
    )
    parser.add_argument(
        "--system",
        choices=sorted(VARIANTS),
        default="baseline",
        help="baseline keeps the original prompt; baseline-abstention is EXP-1.",
    )
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=Path("benchmark/ground_truth"),
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Write findings and metadata only; skip metrics.json",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
    )
    args = parser.parse_args(argv)

    load_env_file(args.env_file)
    try:
        config = BaselineConfig.from_env()
    except BaselineConfigError as exc:
        raise SystemExit(str(exc)) from exc

    findings, meta = run_baseline(
        benchmark_dir=args.benchmark,
        output_dir=args.output,
        config=config,
        ground_truth_dir=None if args.no_eval else args.ground_truth_dir,
        evaluate_run=not args.no_eval,
        variant=VARIANTS[args.system],
    )
    print(f"system={meta.system_id} model={meta.model} repos={len(meta.repos)}")
    print(f"findings={len(findings.findings)} output={args.output}")


if __name__ == "__main__":
    main()
