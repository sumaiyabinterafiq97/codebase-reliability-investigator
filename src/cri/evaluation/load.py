from pathlib import Path

import yaml

from cri.models.ground_truth import GroundTruthFile


def load_ground_truth_dir(directory: Path) -> dict[str, GroundTruthFile]:
    out: dict[str, GroundTruthFile] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        gt = GroundTruthFile.model_validate(data)
        out[gt.repository_id] = gt
    return out
