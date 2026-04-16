from pathlib import Path

from learning_engine import setup_security_models


class ModelRegistry:
    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = Path(dataset_path)
        self._bundle: dict[str, object] | None = None

    def train(self) -> None:
        self._bundle = setup_security_models(dataset_path=self._dataset_path)

    def score(self, text: str) -> dict[str, object]:
        bundle = self._bundle
        if bundle is None:
            bundle = setup_security_models(dataset_path=self._dataset_path)
            self._bundle = bundle

        vector = bundle["vectorizer"].transform([text])
        rf_score = float(bundle["rf_model"].predict_proba(vector)[0][1])
        svm_score = float(bundle["svm_model"].predict_proba(vector)[0][1])
        return {
            "risk_score": (rf_score + svm_score) / 2,
            "rf_score": rf_score,
            "svm_score": svm_score,
            "model_version": bundle["metrics"]["model_version"],
        }
