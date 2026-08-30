from __future__ import annotations

import argparse
from pathlib import Path

from cri.baseline.config import BaselineConfig, BaselineConfigError, load_env_file
from cri.verify.gated_run import run_gated_semantic
from cri.verify.verifier_run import run_semantic_verifier


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "EXP-4 (default): filter then one LLM verifier call per surviving finding. "
            "EXP-5: pass --gated for the fail-open gated enclosing_block review."
        )
    )
    parser.add_argument("--source", type=Path, default=Path("outputs/baseline-001"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, default=Path("benchmark/repositories"))
    parser.add_argument("--ground-truth-dir", type=Path, default=Path("benchmark/ground_truth"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--no-eval", action="store_true")
    parser.add_argument(
        "--gated",
        action="store_true",
        help="EXP-5: after EXP-2 filters, review only structurally inconsistent findings",
    )
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    try:
        config = BaselineConfig.from_env()
    except BaselineConfigError as exc:
        raise SystemExit(str(exc)) from exc
    if args.gated:
        listing = run_gated_semantic(
            args.source,
            args.output,
            args.benchmark,
            args.ground_truth_dir,
            config,
            evaluate_run=not args.no_eval,
        )
        print(
            f"system=baseline-filters-gated-verifier findings={len(listing.findings)} "
            f"output={args.output}"
        )
        return
    listing = run_semantic_verifier(
        args.source,
        args.output,
        args.benchmark,
        args.ground_truth_dir,
        config,
        evaluate_run=not args.no_eval,
    )
    print(f"system=baseline-filters-verifier findings={len(listing.findings)} output={args.output}")


if __name__ == "__main__":
    main()
