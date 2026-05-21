from pathlib import Path
from uuid import uuid4

from app.repositories.risk_events import RiskEventRepository


def test_repository_persists_message_and_decision() -> None:
    db_path = Path(".tmp") / f"risk-events-{uuid4().hex}.db"
    db_path.parent.mkdir(exist_ok=True)
    repository = RiskEventRepository(db_path)
    event_id = repository.create_event(
        message_text="Telegram class invite for CSM3023",
        source_group="CSM3023 Project",
        sender_name="Dr Megat",
        risk_score=0.41,
        model_version="tfidf-rf-svm-v1",
    )

    repository.record_decision(event_id, decision="allow", reviewer="analyst1")
    event = repository.get_event(event_id)

    assert event["decision"] == "allow"
    assert event["source_group"] == "CSM3023 Project"


def test_repository_keeps_manual_review_metadata() -> None:
    db_path = Path(".tmp") / f"risk-events-{uuid4().hex}.db"
    db_path.parent.mkdir(exist_ok=True)
    repository = RiskEventRepository(db_path)
    event_id = repository.create_event(
        message_text="Please verify your student portal password",
        source_group="Manual Review",
        sender_name="Dashboard Analyst",
        risk_score=0.88,
        model_version="tfidf-rf-svm-v2",
    )

    repository.record_decision(event_id, decision="scam", reviewer="analyst2")
    event = repository.get_event(event_id)

    assert event["message_text"] == "Please verify your student portal password"
    assert event["risk_score"] == 0.88
    assert event["decision"] == "scam"
    assert event["reviewer"] == "analyst2"
