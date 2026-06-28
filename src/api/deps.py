"""Dependencias de FastAPI."""
from __future__ import annotations
from typing import Generator

from sqlalchemy.orm import Session

from db.session import SessionLocal


def db_session() -> Generator[Session, None, None]:
    """Provee una sesión de DB por request; la cierra al terminar."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
