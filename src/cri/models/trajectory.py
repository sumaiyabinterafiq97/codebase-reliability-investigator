from typing import Any, Literal

from pydantic import BaseModel, Field


class TrajectoryEvent(BaseModel):
    """One step in an agent run. Populate when the advanced system exists."""

    sequence: int
    kind: Literal[
        "instruction",
        "action",
        "tool_result",
        "retry",
        "feedback",
        "human_checkpoint",
    ]
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    ok: bool | None = None


class TrajectoryLog(BaseModel):
    repository_id: str
    system: str
    events: list[TrajectoryEvent] = Field(default_factory=list)
