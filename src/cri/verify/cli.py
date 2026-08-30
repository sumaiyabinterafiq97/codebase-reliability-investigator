from __future__ import annotations

import argparse
from pathlib import Path

from cri.verify.postprocess import postprocess_run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Deterministic post-process of a CRI findings run.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, default=Path("benchmark/repositories"))
    parser.add_argument("--ground-truth-dir", type=Path, default=Path("benchmark/ground_truth"))
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--filters", action="store_true")
    parser.add_argument("--evidence", action="store_true")
    args = parser.parse_args(argv)
    if not args.filters and not args.evidence:
        raise SystemExit("specify --filters and/or --evidence")
    listing = postprocess_run(
        args.source,
        args.output,
        args.benchmark,
        args.ground_truth_dir,
        system_id=args.system_id,
        experiment_id=args.experiment_id,
        notes=args.notes,
        apply_det_filters=args.filters,
        apply_evidence_repair=args.evidence,
    )
    print(f"system={args.system_id} findings={len(listing.findings)} output={args.output}")


if __name__ == "__main__":
    main()
