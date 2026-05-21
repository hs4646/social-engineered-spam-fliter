from dataclasses import dataclass

from typing import Literal

from pydantic import BaseModel, Field, constr


@dataclass(frozen=True)
class RiskEvent:
    id: int
    message_text: str
    source_group: str
    sender_name: str
    risk_score: float
    model_version: str
    decision: str | None
    reviewer: str | None


class ManualAnalyzeRequest(BaseModel):
    text: constr(strip_whitespace=True, min_length=1)


class ManualReviewRequest(BaseModel):
    message_text: constr(strip_whitespace=True, min_length=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    decision: Literal["scam", "safe", "needs_review"]
    reviewer: constr(strip_whitespace=True, min_length=1)
