"""Runtime settings shared by API, DB and scripts."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://operaciones:operaciones_dev@localhost:5433/operaciones"
)
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]
    environment: str


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        cors_origins=tuple(_csv(os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS))),
        environment=os.environ.get("APP_ENV", "development"),
    )
