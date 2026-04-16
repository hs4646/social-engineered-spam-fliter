from pathlib import Path

from app.services.model_registry import ModelRegistry


def main() -> None:
    dataset_path = Path("whatsapp_dataset.csv")
    registry = ModelRegistry(dataset_path)
    registry.train()
    print("model trained")


if __name__ == "__main__":
    main()
