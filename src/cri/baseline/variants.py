from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cri.baseline.prompt import (
    ABSTENTION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    abstention_user_prompt,
    user_prompt,
)


@dataclass(frozen=True)
class BaselineVariant:
    system_id: str
    experiment_id: str | None
    system_prompt: str
    user_prompt_fn: Callable[[str, str], str]
    notes: str


ORIGINAL = BaselineVariant(
    system_id="baseline",
    experiment_id=None,
    system_prompt=SYSTEM_PROMPT,
    user_prompt_fn=user_prompt,
    notes=(
        "Single LLM call per repository. Includes all .py files (including tests). "
        "Excludes README.md and non-Python files. Does not truncate under the char limit."
    ),
)

ABSTENTION = BaselineVariant(
    system_id="baseline-abstention",
    experiment_id="EXP-1-abstention",
    system_prompt=ABSTENTION_SYSTEM_PROMPT,
    user_prompt_fn=abstention_user_prompt,
    notes=(
        "EXP-1: same single-call baseline with stronger abstention. "
        "Empty findings is the default; does not instruct the model to find at least one issue."
    ),
)

VARIANTS = {ORIGINAL.system_id: ORIGINAL, ABSTENTION.system_id: ABSTENTION}
