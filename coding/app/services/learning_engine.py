from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC


DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "merged_dataset.csv"
REQUIRED_COLUMNS = {"content", "label"}
SHORTLINK_DOMAINS = {
    "bit.ly",
    "cutt.ly",
    "goo.gl",
    "rb.gy",
    "shorturl.at",
    "t.co",
    "tinyurl.com",
}
SUSPICIOUS_TLDS = {"click", "gq", "info", "live", "site", "top", "vip", "xyz"}
BRAND_DOMAIN_HINTS = {
    "airasia": ("airasia.com",),
    "bank islam": ("bankislam.com",),
    "cimb": ("cimb.com", "cimbclicks.com", "cimbclicks.com.my"),
    "grab": ("grab.com",),
    "hasil": ("hasil.gov.my",),
    "icloud": ("apple.com", "icloud.com"),
    "j&t": ("jtexpress.my", "jtexpress.com"),
    "kwsp": ("kwsp.gov.my",),
    "lazada": ("lazada.com", "lazada.com.my"),
    "lhdn": ("hasil.gov.my",),
    "maybank": ("maybank2u.com.my", "maybank.com"),
    "netflix": ("netflix.com",),
    "pos malaysia": ("pos.com.my",),
    "ptptn": ("ptptn.gov.my",),
    "public bank": ("publicbank.com.my",),
    "rhb": ("rhbgroup.com", "rhb.com.my"),
    "shopee": ("shopee.com", "shopee.com.my"),
    "spotify": ("spotify.com",),
    "telegram": ("telegram.org",),
    "touch n go": ("touchngo.com.my",),
    "unifi": ("unifi.com.my", "tm.com.my"),
    "utem": ("utem.edu.my",),
    "whatsapp": ("whatsapp.com",),
}
MANGGLISH_MAP = {
    "aq": "saya",
    "blh": "boleh",
    "jer": "sahaja",
    "je": "sahaja",
    "jgn": "jangan",
    "kene": "kena",
    "nnti": "nanti",
    "ni": "ini",
    "pls": "please",
    "sy": "saya",
    "sya": "saya",
    "u": "you",
    "ur": "your",
    "x": "tak",
}
FEATURE_COLUMNS = [
    "has_url",
    "url_count",
    "has_shortlink",
    "shortlink_count",
    "has_suspicious_tld",
    "has_ip_address_url",
    "has_non_http_like_link_pattern",
    "has_brand_name",
    "has_brand_domain_mismatch",
    "has_urgent_phrase",
    "has_money_phrase",
    "has_account_threat_phrase",
    "has_action_phrase",
]
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.|wa\.me/)[^\s]+")
BARE_LINK_RE = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?")
IP_URL_RE = re.compile(r"(?i)\b(?:https?://)?(?:\d{1,3}\.){3}\d{1,3}(?:/[^\s]*)?")
WHITESPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"(?u)\b[\w']+\b")


def _build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_df=0.98,
        min_df=1,
    )


def _build_rf_model() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=250, random_state=42)


def _build_svm_model() -> SVC:
    return SVC(probability=True, kernel="linear", random_state=42)


def _normalize_spacing(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text.strip().lower())


def normalize_message_text(text: str) -> str:
    cleaned = _normalize_spacing(text)
    if not cleaned:
        return ""

    tokens: list[str] = []
    for token in cleaned.split(" "):
        if URL_RE.fullmatch(token) or BARE_LINK_RE.fullmatch(token):
            tokens.append(token)
            continue

        match = WORD_RE.search(token)
        if match is None:
            tokens.append(token)
            continue

        raw_word = match.group(0)
        replacement = MANGGLISH_MAP.get(raw_word, raw_word)
        tokens.append(token.replace(raw_word, replacement, 1))

    return " ".join(tokens)


def _compose_vector_text(text: str) -> str:
    cleaned = _normalize_spacing(text)
    normalized = normalize_message_text(text)
    if normalized and normalized != cleaned:
        return f"{cleaned} {normalized}"
    return normalized or cleaned


def _extract_urls(text: str) -> list[str]:
    urls = URL_RE.findall(text)
    normalized_text = text
    for url in urls:
        normalized_text = normalized_text.replace(url, " ")

    bare_links = [
        candidate
        for candidate in BARE_LINK_RE.findall(normalized_text)
        if "." in candidate and "@" not in candidate
    ]
    return urls + bare_links


def _normalize_domain(url: str) -> str:
    candidate = url if "://" in url else f"https://{url}"
    parsed = urlparse(candidate)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_feature_signals(text: str) -> dict[str, float]:
    lowered = _normalize_spacing(text)
    urls = _extract_urls(lowered)
    domains = [_normalize_domain(url) for url in urls]

    has_shortlink = any(domain in SHORTLINK_DOMAINS for domain in domains)
    shortlink_count = sum(1 for domain in domains if domain in SHORTLINK_DOMAINS)
    has_suspicious_tld = any(
        domain.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS for domain in domains if "." in domain
    )
    has_brand_name = any(brand in lowered for brand in BRAND_DOMAIN_HINTS)
    has_brand_domain_mismatch = 0.0

    if has_brand_name and domains:
        for brand, allowed_domains in BRAND_DOMAIN_HINTS.items():
            if brand not in lowered:
                continue
            if any(not any(allowed in domain for allowed in allowed_domains) for domain in domains):
                has_brand_domain_mismatch = 1.0
                break

    urgent_phrases = (
        "urgent",
        "immediately",
        "segera",
        "final reminder",
        "tindakan segera",
        "today",
        "24 jam",
    )
    money_phrases = (
        "rm",
        "refund",
        "prize",
        "reward",
        "cash",
        "bayar",
        "payment",
        "claim",
    )
    account_threat_phrases = (
        "account",
        "akaun",
        "blocked",
        "disekat",
        "ditamatkan",
        "restricted",
        "suspend",
        "verify",
    )
    action_phrases = (
        "click",
        "klik",
        "update",
        "kemaskini",
        "confirm",
        "sahkan",
        "login",
        "log masuk",
    )

    has_non_http_like_link_pattern = 1.0 if any("://" not in url for url in urls) else 0.0
    features = {
        "has_url": float(bool(urls)),
        "url_count": float(len(urls)),
        "has_shortlink": float(has_shortlink),
        "shortlink_count": float(shortlink_count),
        "has_suspicious_tld": float(has_suspicious_tld),
        "has_ip_address_url": float(bool(IP_URL_RE.search(lowered))),
        "has_non_http_like_link_pattern": has_non_http_like_link_pattern,
        "has_brand_name": float(has_brand_name),
        "has_brand_domain_mismatch": has_brand_domain_mismatch,
        "has_urgent_phrase": float(any(phrase in lowered for phrase in urgent_phrases)),
        "has_money_phrase": float(any(phrase in lowered for phrase in money_phrases)),
        "has_account_threat_phrase": float(
            any(phrase in lowered for phrase in account_threat_phrases)
        ),
        "has_action_phrase": float(any(phrase in lowered for phrase in action_phrases)),
    }
    return features


def prepare_training_frame(dataset_path: Path | None = None) -> pd.DataFrame:
    resolved_dataset_path = dataset_path or DATASET_PATH
    if not resolved_dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {resolved_dataset_path}. Ensure merged_dataset.csv exists."
        )

    df = pd.read_csv(resolved_dataset_path, encoding="utf-8")
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {missing_text}")

    df["content"] = df["content"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[df["content"].ne("")].copy()

    if len(df) < 10:
        raise ValueError("Dataset is too small to train a reliable model.")

    if set(df["label"]) != {"0", "1"}:
        raise ValueError("Dataset labels must contain both '0' and '1'.")

    df["vector_text"] = df["content"].map(_compose_vector_text)
    feature_frame = pd.DataFrame(df["content"].map(extract_feature_signals).tolist())
    return pd.concat([df, feature_frame], axis=1)


def _build_feature_matrix(texts: Sequence[str], feature_frame: pd.DataFrame) -> csr_matrix:
    feature_rows = feature_frame[FEATURE_COLUMNS].astype(float).to_numpy()
    return csr_matrix(feature_rows)


def _vectorize_messages(vectorizer: TfidfVectorizer, texts: Sequence[str]):
    vector_texts = [_compose_vector_text(text) for text in texts]
    return vectorizer.transform(vector_texts)


def _apply_shortlink_boost(base_score: float, feature_signals: dict[str, float]) -> float:
    boost = 0.0
    if feature_signals["has_shortlink"] and feature_signals["has_action_phrase"]:
        boost += 0.08
    if feature_signals["has_shortlink"] and feature_signals["has_account_threat_phrase"]:
        boost += 0.08
    if feature_signals["has_shortlink"] and feature_signals["has_brand_domain_mismatch"]:
        boost += 0.1
    if feature_signals["has_suspicious_tld"] and feature_signals["has_urgent_phrase"]:
        boost += 0.05
    return min(0.99, base_score + boost)


def score_text(text: str, bundle: dict[str, object]) -> dict[str, object]:
    feature_signals = extract_feature_signals(text)
    vector = _vectorize_messages(bundle["vectorizer"], [text])
    dense = csr_matrix([[feature_signals[name] for name in FEATURE_COLUMNS]])
    combined = hstack([vector, dense], format="csr")
    rf_score = float(bundle["rf_model"].predict_proba(combined)[0][1])
    svm_score = float(bundle["svm_model"].predict_proba(combined)[0][1])
    base_score = (rf_score + svm_score) / 2
    return {
        "risk_score": _apply_shortlink_boost(base_score, feature_signals),
        "rf_score": rf_score,
        "svm_score": svm_score,
        "feature_signals": feature_signals,
        "model_version": bundle["metrics"]["model_version"],
    }


@lru_cache(maxsize=None)
def setup_security_models(dataset_path: Path | None = None) -> dict[str, object]:
    resolved_dataset_path = dataset_path or DATASET_PATH
    training_frame = prepare_training_frame(resolved_dataset_path)
    labels = training_frame["label"]
    class_counts = labels.value_counts()

    if class_counts.min() < 2:
        raise ValueError("Each label needs at least two rows for model training.")

    x_train, x_test, y_train, y_test = train_test_split(
        training_frame,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )

    eval_vectorizer = _build_vectorizer()
    x_train_text = eval_vectorizer.fit_transform(x_train["vector_text"])
    x_test_text = eval_vectorizer.transform(x_test["vector_text"])
    x_train_dense = _build_feature_matrix(x_train["content"], x_train)
    x_test_dense = _build_feature_matrix(x_test["content"], x_test)
    x_train_features = hstack([x_train_text, x_train_dense], format="csr")
    x_test_features = hstack([x_test_text, x_test_dense], format="csr")

    eval_rf_model = _build_rf_model()
    eval_rf_model.fit(x_train_features, y_train)
    rf_accuracy = accuracy_score(y_test, eval_rf_model.predict(x_test_features))

    eval_svm_model = _build_svm_model()
    eval_svm_model.fit(x_train_features, y_train)
    svm_accuracy = accuracy_score(y_test, eval_svm_model.predict(x_test_features))

    final_vectorizer = _build_vectorizer()
    full_text_features = final_vectorizer.fit_transform(training_frame["vector_text"])
    full_dense_features = _build_feature_matrix(training_frame["content"], training_frame)
    full_features = hstack([full_text_features, full_dense_features], format="csr")

    rf_model = _build_rf_model()
    rf_model.fit(full_features, labels)

    svm_model = _build_svm_model()
    svm_model.fit(full_features, labels)

    metrics = {
        "dataset_rows": int(len(training_frame)),
        "safe_rows": int(class_counts["0"]),
        "threat_rows": int(class_counts["1"]),
        "rf_accuracy": float(rf_accuracy),
        "svm_accuracy": float(svm_accuracy),
        "model_version": f"tfidf-rf-svm-manglish-shortlink::{resolved_dataset_path.name}",
    }

    return {
        "vectorizer": final_vectorizer,
        "rf_model": rf_model,
        "svm_model": svm_model,
        "feature_columns": FEATURE_COLUMNS,
        "metrics": metrics,
    }
