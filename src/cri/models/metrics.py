from typing import Literal

from pydantic import BaseModel, Field


class MatchRecord(BaseModel):
    repository_id: str
    predicted_index: int | None = None
    gold_issue_id: str | None = None
    kind: Literal["tp", "fp", "fn", "fp_red_herring"]
    severity_match: bool | None = None
    evidence_grounded: bool | None = None


class RepoMetrics(BaseModel):
    repository_id: str
    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None


class EvalMetrics(BaseModel):
    """Computed from a real FindingList. Fields stay null when inputs are missing."""

    micro_precision: float | None = None
    micro_recall: float | None = None
    micro_f1: float | None = None
    macro_f1: float | None = None
    false_positive_count: int = 0
    negative_repo_count: int = 0
    negative_repos_with_findings: int = 0
    repo_level_fpr: float | None = None
    severity_accuracy: float | None = None
    evidence_grounding_accuracy: float | None = None
    runtime_seconds_total: float | None = None
    prompt_tokens_total: int | None = None
    completion_tokens_total: int | None = None
    estimated_cost_usd: float | None = None
    per_repo: list[RepoMetrics] = Field(default_factory=list)
    matches: list[MatchRecord] = Field(default_factory=list)
