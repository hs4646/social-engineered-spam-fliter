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


def test_model_registry_downranks_trusted_legal_notice_links() -> None:
    dataset_path = _write_dataset(
        [
            ("kelas esok pindah ke makmal 2", 0),
            ("rujuk portal rasmi JPJ di https://www.jpj.gov.my", 0),
            ("PTPTN final reminder: review payment notice at https://www.ptptn.gov.my", 0),
            ("HEP survey rasmi UTeM ada di https://hep.utem.edu.my/survey", 0),
            ("Maybank alert: verify now at https://maybank-secure-check.example", 1),
            ("PTPTN final reminder: legal action may start at https://ptptn-settlement.example", 1),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
            ("please verify your account at https://bit.ly/check-now", 1),
            ("meeting FYP moved to 3pm", 0),
            ("nota kuliah dah upload dekat portal", 0),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    trusted = registry.score(
        "PTPTN final reminder: legal action may start. Review payment notice at https://www.ptptn.gov.my"
    )
    fake = registry.score(
        "PTPTN final reminder: legal action may start. Review payment notice at https://ptptn-settlement.example"
    )

    assert trusted["risk_score"] < fake["risk_score"]
    assert trusted["feature_signals"]["has_brand_domain_mismatch"] == 0.0
    assert fake["feature_signals"]["has_brand_domain_mismatch"] == 1.0


def test_model_registry_marks_trusted_domains_and_brand_matches() -> None:
    dataset_path = _write_dataset(
        [
            ("makmal rangkaian buka pukul 9 pagi", 0),
            ("portal rasmi hasil di https://www.hasil.gov.my", 0),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
            ("maybank verify now di https://maybank-secure-check.example", 1),
            ("kelas ganti hari khamis", 0),
            ("please verify your account at https://bit.ly/check-now", 1),
            ("info rasmi UTeM di https://utem.edu.my", 0),
            ("rhb update profile at https://secure-rhb-check.example", 1),
            ("group meeting moved to 8pm", 0),
            ("pls verify shopee account immediately", 1),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    trusted = registry.score("I renewed my roadtax already, the JPJ portal link is here https://www.jpj.gov.my")
    matched = registry.score("Official Maybank portal is https://www.maybank2u.com.my")
    fake = registry.score("Maybank alert: verify now at https://maybank-secure-check.example")

    assert trusted["feature_signals"]["has_trusted_domain"] == 1.0
    assert matched["feature_signals"]["has_brand_domain_match"] == 1.0
    assert matched["feature_signals"]["has_brand_domain_mismatch"] == 0.0
    assert fake["feature_signals"]["has_brand_domain_mismatch"] == 1.0


def test_model_registry_downranks_legitimate_telegram_invites() -> None:
    dataset_path = _write_dataset(
        [
            ("kelas ganti di makmal petang ini", 0),
            ("Join the Telegram discussion at https://t.me/+mkJQGPjQaLg1OTk9 for industrial training updates", 0),
            ("Telegram rasmi fakulti akan kongsi info latihan industri", 0),
            ("Maybank alert: verify now at https://maybank-secure-check.example", 1),
            ("please verify your account at https://bit.ly/check-now", 1),
            ("Urgent parcel fee payment via https://rb.gy/pay-now", 1),
            ("meeting FYP moved to 3pm", 0),
            ("Pelajar diminta semak jadual pembentangan", 0),
            ("PTPTN final reminder: legal action may start at https://ptptn-settlement.example", 1),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    legit = registry.score(
        "Dear students, join this Telegram group for Industry Training updates: https://t.me/+mkJQGPjQaLg1OTk9"
    )
    fake = registry.score("Telegram security alert: verify your account now at https://telegram-secure-check.example")

    assert legit["risk_score"] < fake["risk_score"]
    assert legit["feature_signals"]["has_trusted_domain"] == 1.0
    assert legit["feature_signals"]["has_brand_domain_match"] == 1.0
    assert fake["feature_signals"]["has_brand_domain_mismatch"] == 1.0


def test_model_registry_downranks_event_registration_forms_without_trusting_payment_forms() -> None:
    dataset_path = _write_dataset(
        [
            ("Pendaftaran program dibuka untuk pelajar tahun 1", 0),
            ("Daftar program melalui https://forms.gle/Qa9U7ACm8ZLKRVu17", 0),
            ("Maklumat lokasi dan tarikh akan diumumkan kemudian", 0),
            ("Google Form rasmi kelab akan kongsi senarai peserta", 0),
            ("Maybank alert: verify now at https://maybank-secure-check.example", 1),
            ("Complete your account verification at https://forms.gle/VerifyBankNow", 1),
            ("Bayar yuran segera di https://forms.gle/PayNowFast", 1),
            ("akaun anda disekat sila klik https://tinyurl.com/buka-akaun", 1),
            ("meeting FYP moved to 3pm", 0),
            ("class replacement tomorrow at BK3", 0),
        ]
    )

    registry = ModelRegistry(dataset_path)
    registry.train()

    event_form = registry.score(
        "Pendaftaran Program Mahasiswa Negara kini dibuka. Lokasi Kem PLK Ulu Sepri, tarikh 15-17 Mei 2026. Daftar sekarang melalui https://forms.gle/Qa9U7ACm8ZLKRVu17"
    )
    payment_form = registry.score(
        "Bayar yuran tertunggak segera untuk elak tindakan. Sahkan bayaran di https://forms.gle/PayNowFast"
    )

    assert event_form["risk_score"] < payment_form["risk_score"]
    assert event_form["feature_signals"]["has_trusted_domain"] == 1.0
    assert event_form["feature_signals"]["has_event_context"] == 1.0
    assert payment_form["feature_signals"]["has_event_context"] == 0.0
