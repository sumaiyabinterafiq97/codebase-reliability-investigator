from typing import Literal

from pydantic import BaseModel, Field

from cri.models.finding import Category, Severity


class Issue(BaseModel):
    issue_id: str
    category: Category
    severity: Severity
    file: str
    line: int = Field(ge=1)
    function_name: str | None = None
    description: str
    why_reliability: str
    expected_evidence: str
    present: bool
    difficulty: Literal["easy", "medium", "hard"]


class GroundTruthFile(BaseModel):
    repository_id: str
    language: str
    issues: list[Issue] = Field(default_factory=list)
    red_herrings: list[Issue] = Field(default_factory=list)

    def positive_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.present]

    def fp_anchors(self) -> list[Issue]:
        return list(self.red_herrings) + [i for i in self.issues if not i.present]
