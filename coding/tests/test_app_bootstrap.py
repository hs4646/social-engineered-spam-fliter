from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_exposes_health_and_static_mount() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_manual_analyze_endpoint_scores_selected_message(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        "app.main.setup_security_models",
        lambda: {
            "metrics": {
                "dataset_rows": 10,
                "rf_accuracy": 0.9,
                "svm_accuracy": 0.9,
                "model_version": "test-model",
            },
        },
    )
    monkeypatch.setattr(
        "app.main.score_text",
        lambda text, _bundle: {"risk_score": 0.77 if text == "please verify account now" else 0.1},
    )

    response = client.post(
        "/api/messages/analyze",
        json={"text": "please verify account now"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "message": {
            "text": "please verify account now",
            "type": "manual-analysis",
            "risk": 0.77,
        },
    }


def test_manual_analyze_endpoint_rejects_blank_message() -> None:
    client = TestClient(create_app())

    response = client.post("/api/messages/analyze", json={"text": "   "})

    assert response.status_code == 422


def test_manual_review_endpoint_persists_decision(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)
    db_path = Path(".tmp") / f"review-events-{uuid4().hex}.db"
    db_path.parent.mkdir(exist_ok=True)

    monkeypatch.setattr("app.main.get_risk_event_repository", lambda: None)

    from app.repositories.risk_events import RiskEventRepository

    repository = RiskEventRepository(db_path)
    monkeypatch.setattr("app.main.get_risk_event_repository", lambda: repository)

    response = client.post(
        "/api/messages/review",
        json={
            "message_text": "please verify account now",
            "risk_score": 0.77,
            "decision": "scam",
            "reviewer": "Han Shen",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["event"]["decision"] == "scam"
    assert payload["event"]["reviewer"] == "Han Shen"

    stored = repository.get_event(payload["event"]["event_id"])
    assert stored["message_text"] == "please verify account now"
    assert stored["risk_score"] == 0.77
    assert stored["decision"] == "scam"
    assert stored["reviewer"] == "Han Shen"


def test_manual_review_endpoint_rejects_blank_reviewer() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/messages/review",
        json={
            "message_text": "please verify account now",
            "risk_score": 0.77,
            "decision": "safe",
            "reviewer": "   ",
        },
    )

    assert response.status_code == 422


def test_manual_review_endpoint_rejects_invalid_decision() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/messages/review",
        json={
            "message_text": "please verify account now",
            "risk_score": 0.77,
            "decision": "allow",
            "reviewer": "Han Shen",
        },
    )

    assert response.status_code == 422
