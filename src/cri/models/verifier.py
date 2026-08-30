from typing import Literal

from pydantic import BaseModel, Field, model_validator


class VerifierEvidence(BaseModel):
    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str

    @model_validator(mode="after")
    def line_order(self) -> "VerifierEvidence":
        if self.start_line > self.end_line:
            raise ValueError("start_line must be <= end_line")
        return self


class VerifierResult(BaseModel):
    decision: Literal["confirm", "reject"]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: VerifierEvidence
