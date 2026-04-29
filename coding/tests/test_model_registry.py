from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.model_registry import ModelRegistry


def _write_dataset(rows: list[tuple[str, int]]) -> Path:
    dataset_path = Path(".tmp") / f"dataset-{uuid4().hex}.csv"
    dataset_path.parent.mkdir(exist_ok=True)
    lines = ["content,label"]
    for content, label in rows:
        escaped = content.replace('"', '""')
        lines.append(f'"{escaped}",{label}')
    dataset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dataset_path


def test_model_registry_scores_shortlink_manglish_scam_higher_than_normal_chat() -> None:
    dataset_path = _write_dataset(
        [
            ("wei bro kelas esok pindah bilik ya", 0),
            ("tolong semak nota kat https://bit.ly/kelas-notes", 0),
            ("urgent wei akaun bank u kena sekat verify now at https://bit.ly/kemaskini-sekarang", 1),
            ("pls update your payroll profile at https://secure-payroll-check.example", 1),
            ("jom mamak malam ni lepas class", 0),
            ("sy x sempat join meeting pagi tadi", 0),
            ("akaun anda akan ditamatkan sila klik https://rb.gy/abc123", 1),
            ("official portal is https://www.maybank2u.com.my", 0),
            ("ur parcel pending pay fee at http://tinyurl.com/claim-parcel", 1),
            ("presentation FYP start pukul 2 nanti", 0),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    scam = registry.score("wei urgent akaun u kena block, klik https://bit.ly/verify-now")
    safe = registry.score("wei jom tengok nota class kat https://bit.ly/kelas-notes")

    assert scam["risk_score"] > safe["risk_score"]
    assert scam["risk_score"] >= 0.5
    assert safe["risk_score"] < 0.75


def test_model_registry_exposes_feature_details() -> None:
    dataset_path = _write_dataset(
        [
            ("class replacement tomorrow at BK3", 0),
            ("please verify your account at https://bit.ly/check-now", 1),
            ("boleh share slide lecture malam ni", 0),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
            ("official info at https://www.hasil.gov.my", 0),
            ("urgent action required update TAC profile now", 1),
            ("jom print poster petang ni", 0),
            ("pembayaran gagal kemaskini bank di https://rb.gy/pay-now", 1),
            ("meeting FYP moved to 3pm", 0),
            ("pls verify shopee account immediately", 1),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()
    result = registry.score("urgent akaun bank u kena sekat klik https://bit.ly/kemaskini")

    assert set(result) >= {
        "risk_score",
        "rf_score",
        "svm_score",
        "model_version",
        "feature_signals",
    }
    assert result["feature_signals"]["has_shortlink"] == 1.0
    assert result["feature_signals"]["has_url"] == 1.0
