from pathlib import Path
from uuid import uuid4

from app.services.model_registry import ModelRegistry


def test_model_registry_returns_risk_breakdown() -> None:
    dataset_path = Path(".tmp") / f"dataset-{uuid4().hex}.csv"
    dataset_path.parent.mkdir(exist_ok=True)
    dataset_path.write_text(
        "content,label\n"
        "\"Please review the lecture notes in Google Classroom\",0\n"
        "\"URGENT: verify your student portal at fake-link\",1\n"
        "\"Class replacement is on Friday in BK3\",0\n"
        "\"Click now to avoid account suspension\",1\n"
        "\"Tomorrow lab starts at 2pm\",0\n"
        "\"Claim your reward before midnight\",1\n"
        "\"Assignment submission closes on Sunday\",0\n"
        "\"Your account will be locked unless you confirm now\",1\n"
        "\"The lecturer shared the Zoom link in Teams\",0\n"
        "\"Tap here to restore your mailbox access\",1\n",
        encoding="utf-8",
    )

    registry = ModelRegistry(dataset_path)
    registry.train()
    result = registry.score("Telegram invite link for Software Security lecture")

    assert set(result) >= {"risk_score", "rf_score", "svm_score", "model_version"}
