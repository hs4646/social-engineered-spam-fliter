"""Test cases for legitimate Malaysian university messages that should not be flagged as threats."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.model_registry import ModelRegistry


def _write_dataset(rows: list[tuple[str, int]]) -> Path:
    """Create a temporary dataset for testing."""
    from uuid import uuid4
    dataset_path = Path(".tmp") / f"dataset-{uuid4().hex}.csv"
    dataset_path.parent.mkdir(exist_ok=True)
    lines = ["content,label"]
    for content, label in rows:
        escaped = content.replace('"', '""')
        lines.append(f'"{escaped}",{label}')
    dataset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dataset_path


# Shared dataset for all tests - needs at least 10 rows and both labels
SHARED_DATASET = [
    # Safe messages (label=0)
    ("kelas esok pindah bilik", 0),
    ("meeting FYP moved to 3pm", 0),
    ("jom mamak malam ni lepas class", 0),
    ("wei bro jom minum mamak malam ni", 0),
    ("aku dah submit PSM proposal kat U-Learn", 0),
    ("siapa ada jumpa pendrive kat lab FTMK tingkat 2?", 0),
    ("korang dah daftar subjek untuk sem depan belum?", 0),
    ("jom main Valorant malam ni aku on lepas pukul 10", 0),
    ("Semak status PTPTN anda di https://www.ptptn.gov.my", 0),
    ("Tutorial CSM3023 pukul 2 petang kat makmal 3", 0),
    ("Jom diskusikan assignment kat cafe", 0),
    ("Meeting FYP via Google Meet: https://meet.google.com/abc-defg-hij", 0),
    # Scam messages (label=1)
    ("urgent wei akaun bank u kena sekat verify now at https://bit.ly/kemaskini-sekarang", 1),
    ("pls update your payroll profile at https://secure-payroll-check.example", 1),
    ("akaun anda akan ditamatkan sila klik https://rb.gy/abc123", 1),
    ("please verify your account at https://bit.ly/check-now", 1),
    ("Maybank alert: verify now at https://maybank-secure-check.example", 1),
    ("PTPTN final reminder: legal action may start at https://ptptn-settlement.example", 1),
    ("CIMB Alerts: Your account has been restricted. Verify immediately: http://cimb-clicks-verify.net", 1),
    ("恭喜你中奖了！点击链接领取：https://bit.ly/fake-prize", 1),
]


def test_class_meeting_link_not_flagged():
    """Class meeting links with Google Meet/Zoom should not be flagged."""
    dataset_path = _write_dataset(SHARED_DATASET)
    registry = ModelRegistry(dataset_path)
    registry.train()
    
    safe_messages = [
        "Meeting FYP via Google Meet: https://meet.google.com/abc-defg-hij",
        "Kelas Dr Megat esok ganti bilik baru",
        "Tutorial CSM3023 pukul 2 petang kat makmal 3",
        "Jom diskusikan assignment kat cafe",
    ]
    
    for msg in safe_messages:
        result = registry.score(msg)
        assert result["risk_score"] < 0.5, f"False positive: '{msg}' scored {result['risk_score']}"


def test_government_portal_links_not_flagged():
    """Government portal links (PTPTN, LHDN, etc.) should not be flagged."""
    dataset_path = _write_dataset(SHARED_DATASET)
    registry = ModelRegistry(dataset_path)
    registry.train()
    
    safe_messages = [
        "Semak status PTPTN anda di https://www.ptptn.gov.my",
        "Portal rasmi LHDN di https://www.lhdn.gov.my",
        "Check EPF balance at https://www.kwsp.gov.my",
        "MyEG services at https://www.myeg.com.my",
    ]
    
    for msg in safe_messages:
        result = registry.score(msg)
        assert result["risk_score"] < 0.5, f"False positive: '{msg}' scored {result['risk_score']}"


def test_chinese_scam_detected():
    """Chinese scam messages with obvious signals should be detected."""
    dataset_path = _write_dataset(SHARED_DATASET)
    registry = ModelRegistry(dataset_path)
    registry.train()
    
    # Chinese scam messages with clear scam signals (URLs, action phrases)
    scam_messages = [
        "恭喜你中奖了！点击链接领取：https://bit.ly/fake-prize",
        "您的账户异常，请立即验证：https://fake-bank.com",
        "恭喜您获得RM10000奖励，请点击链接领取：http://fake-reward.com",
        "紧急：您的账户将被关闭，请立即验证：http://account-verify.com",
        "您的银行账户异常，请立即验证：http://bank-verify.com",
    ]
    
    for msg in scam_messages:
        result = registry.score(msg)
        assert result["risk_score"] > 0.4, f"Missed scam: '{msg}' scored {result['risk_score']}"


def test_manglish_informal_chat_not_flagged():
    """Informal Manglish chat should not be flagged."""
    dataset_path = _write_dataset(SHARED_DATASET)
    registry = ModelRegistry(dataset_path)
    registry.train()
    
    safe_messages = [
        "wei bro jom minum mamak malam ni",
        "aku dah submit PSM proposal kat U-Learn",
        "siapa ada jumpa pendrive kat lab FTMK tingkat 2?",
        "korang dah daftar subjek untuk sem depan belum?",
        "jom main Valorant malam ni aku on lepas pukul 10",
    ]
    
    for msg in safe_messages:
        result = registry.score(msg)
        assert result["risk_score"] < 0.5, f"False positive: '{msg}' scored {result['risk_score']}"


def test_phishing_with_brand_spoofing_detected():
    """Phishing messages with brand spoofing should be detected."""
    dataset_path = _write_dataset(SHARED_DATASET)
    registry = ModelRegistry(dataset_path)
    registry.train()
    
    scam_messages = [
        "Maybank alert: verify now at https://maybank-secure-check.example",
        "PTPTN final reminder: legal action may start at https://ptptn-settlement.example",
        "CIMB Alerts: Your account has been restricted. Verify immediately: http://cimb-clicks-verify.net",
    ]
    
    for msg in scam_messages:
        result = registry.score(msg)
        assert result["risk_score"] > 0.5, f"Missed scam: '{msg}' scored {result['risk_score']}"
