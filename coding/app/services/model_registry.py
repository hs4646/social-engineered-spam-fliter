from pathlib import Path

from app.services.learning_engine import score_text, setup_security_models


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

        return score_text(text, bundle)
