from typing import Literal

from pydantic import BaseModel, Field, model_validator

Category = Literal[
    "error_handling",
    "input_validation",
    "resource_lifecycle",
    "state_concurrency",
    "testing_coverage",
]

Severity = Literal["low", "medium", "high"]


class Evidence(BaseModel):
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = ""

    @model_validator(mode="after")
    def line_order(self) -> "Evidence":
        if self.line_start > self.line_end:
            raise ValueError("line_start must be <= line_end")
        return self


class Finding(BaseModel):
    repository_id: str
    category: Category
    severity: Severity
    file: str
    line: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    function_name: str | None = None
    description: str
    evidence: Evidence

    @model_validator(mode="after")
    def location_present(self) -> "Finding":
        if self.line is None and self.line_start is None:
            raise ValueError("either line or line_start is required")
        return self

    def location_span(self) -> tuple[int, int]:
        if self.line_start is not None:
            end = self.line_end if self.line_end is not None else self.line_start
            return self.line_start, end
        assert self.line is not None
        return self.line, self.line


class FindingList(BaseModel):
    system: Literal["baseline", "advanced"] | str
    findings: list[Finding] = Field(default_factory=list)
