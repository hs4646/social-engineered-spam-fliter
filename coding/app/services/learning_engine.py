from functools import lru_cache
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC


DATASET_PATH = Path(__file__).resolve().parents[3] / "data" / "whatsapp_dataset.csv"
REQUIRED_COLUMNS = {"content", "label"}


def _build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        stop_words="english",
        lowercase=True,
        ngram_range=(1, 2),
        max_df=0.95,
    )


def _build_rf_model() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=200, random_state=42)


def _build_svm_model() -> SVC:
    return SVC(probability=True, kernel="linear", random_state=42)


def _load_dataset(dataset_path: Path | None = None) -> tuple[pd.Series, pd.Series]:
    resolved_dataset_path = dataset_path or DATASET_PATH
    if not resolved_dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {resolved_dataset_path}. Ensure whatsapp_dataset.csv exists."
        )

    df = pd.read_csv(resolved_dataset_path, encoding="utf-8")
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {missing_text}")

    df["content"] = df["content"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[df["content"].ne("")]

    if len(df) < 10:
        raise ValueError("Dataset is too small to train a reliable model.")

    if set(df["label"]) != {"0", "1"}:
        raise ValueError("Dataset labels must contain both '0' and '1'.")

    return df["content"], df["label"]


@lru_cache(maxsize=None)
def setup_security_models(dataset_path: Path | None = None) -> dict[str, object]:
    resolved_dataset_path = dataset_path or DATASET_PATH
    texts, labels = _load_dataset(resolved_dataset_path)
    class_counts = labels.value_counts()

    if class_counts.min() < 2:
        raise ValueError("Each label needs at least two rows for model training.")

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )

    eval_vectorizer = _build_vectorizer()
    x_train_features = eval_vectorizer.fit_transform(x_train)
    x_test_features = eval_vectorizer.transform(x_test)

    eval_rf_model = _build_rf_model()
    eval_rf_model.fit(x_train_features, y_train)
    rf_accuracy = accuracy_score(y_test, eval_rf_model.predict(x_test_features))

    eval_svm_model = _build_svm_model()
    eval_svm_model.fit(x_train_features, y_train)
    svm_accuracy = accuracy_score(y_test, eval_svm_model.predict(x_test_features))

    final_vectorizer = _build_vectorizer()
    full_features = final_vectorizer.fit_transform(texts)

    rf_model = _build_rf_model()
    rf_model.fit(full_features, labels)

    svm_model = _build_svm_model()
    svm_model.fit(full_features, labels)

    metrics = {
        "dataset_rows": int(len(texts)),
        "safe_rows": int(class_counts["0"]),
        "threat_rows": int(class_counts["1"]),
        "rf_accuracy": float(rf_accuracy),
        "svm_accuracy": float(svm_accuracy),
        "model_version": f"tfidf-rf-svm::{resolved_dataset_path.name}",
    }

    return {
        "vectorizer": final_vectorizer,
        "rf_model": rf_model,
        "svm_model": svm_model,
        "metrics": metrics,
    }
