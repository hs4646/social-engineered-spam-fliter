from dataclasses import dataclass


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
