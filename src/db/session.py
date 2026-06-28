"""Configuración de SQLAlchemy: engine y session factory."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from operaciones.settings import get_settings


settings = get_settings()
DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def get_session() -> Session:
    """Para uso en scripts. Cerrar al terminar."""
    return SessionLocal()
