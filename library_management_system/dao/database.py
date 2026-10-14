import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from library_management_system.dao.models import Base


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a PostgreSQL engine from a URL or the DATABASE_URL environment variable."""
    configured_url = database_url or os.getenv("DATABASE_URL")
    if not configured_url:
        raise RuntimeError("Set DATABASE_URL before connecting to the database.")

    url = make_url(configured_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver.")

    return create_engine(url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Commit on success, roll back on error, and always close the session."""
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def initialize_database(engine: Engine) -> None:
    """Enable pgvector and create missing tables for local development."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
