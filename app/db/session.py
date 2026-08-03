"""
SKONGA Library API — Database Session
=======================================
Creates the SQLAlchemy engine and a per-request session factory.
Uses psycopg3 (psycopg) driver — compatible with Termux and Render.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# Ensure DATABASE_URL is present and looks like a string before calling .replace()
_db_url_raw = getattr(settings, "DATABASE_URL", None)
if not _db_url_raw or not isinstance(_db_url_raw, str):
    raise RuntimeError("DATABASE_URL is not set or invalid. Set the DATABASE_URL environment variable.")

# psycopg3 requires postgresql+psycopg:// dialect prefix.
# We normalise both postgresql:// and postgres:// (Supabase uses both).
_db_url = (
    _db_url_raw
    .replace("postgresql://", "postgresql+psycopg://")
    .replace("postgres://", "postgresql+psycopg://")
)

try:
    engine = create_engine(
        _db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
except Exception as exc:
    # Surface a helpful error during startup rather than a confusing stacktrace later
    raise RuntimeError(f"Failed to create DB engine: {exc}") from exc

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency — yields a database session for one request,
    then closes it cleanly whether or not an exception was raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
