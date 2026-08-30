from pydantic import BaseModel, Field


class RepoRuntime(BaseModel):
    repository_id: str
    runtime_seconds: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    parse_status: str | None = None
    error: str | None = None
    invalid_finding_count: int = 0
    input_sha256: str | None = None
    file_count: int | None = None
    bundle_chars: int | None = None


class RunMeta(BaseModel):
    system: str
    system_id: str = "baseline"
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_bundle_chars: int | None = None
    source_suffixes: list[str] | None = None
    started_at: str | None = None
    finished_at: str | None = None
    usd_per_million_prompt_tokens: float | None = None
    usd_per_million_completion_tokens: float | None = None
    notes: str | None = None
    parent_run: str | None = None
    experiment_id: str | None = None
    repos: list[RepoRuntime] = Field(default_factory=list)
