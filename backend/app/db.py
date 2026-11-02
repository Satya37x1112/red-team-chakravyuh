"""Database engine and session factory."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


# PostgreSQL in Docker; falls back to a local SQLite file if someone points
# DATABASE_URL at sqlite:// for a quick run without Postgres.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. For a real deployment use Alembic migrations instead."""
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
