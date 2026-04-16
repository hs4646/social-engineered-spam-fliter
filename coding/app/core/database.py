from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabaseSettings:
    url: str = "sqlite:///soc.db"
    path: Path = Path("soc.db")
