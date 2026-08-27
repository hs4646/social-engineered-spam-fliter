from pathlib import Path

from app.services.learning_engine import score_text, setup_security_models


class ModelRegistry:
    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = Path(dataset_path)
        self._bundle: dict[str, object] | None = None

    def _get_bundle(self) -> dict[str, object]:
        bundle = self._bundle
        if bundle is None:
            # setup_security_models is lru_cached by dataset_path, so repeated
            # train()/score() calls never retrain or build a second model.
            bundle = setup_security_models(dataset_path=self._dataset_path)
            self._bundle = bundle
        return bundle

    def train(self) -> None:
        self._get_bundle()

    def score(self, text: str) -> dict[str, object]:
        return score_text(text, self._get_bundle())
