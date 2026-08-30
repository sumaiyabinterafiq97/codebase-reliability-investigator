import json
from pathlib import Path


def load_settings(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def max_connections(path: str) -> int:
    settings = load_settings(path)
    return int(settings["max_connections"])
