from pathlib import Path

from app.services.model_registry import ModelRegistry


def main() -> None:
    dataset_path = Path(__file__).resolve().parents[1] / "data" / "final_dataset.csv"
    registry = ModelRegistry(dataset_path)
    registry.train()
    print("model trained")


if __name__ == "__main__":
    main()
