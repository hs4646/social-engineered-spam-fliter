from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    template_dir: Path
    static_dir: Path
    runtime_dir: Path
    risk_events_db_path: Path


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[2]
    return Settings(
        base_dir=base_dir,
        template_dir=base_dir / "templates",
        static_dir=base_dir / "static",
        runtime_dir=base_dir / ".tmp",
        risk_events_db_path=base_dir / ".tmp" / "risk-events.db",
    )
