"""
SKONGA Library API — Database Session
=======================================
Creates the SQLAlchemy engine and a per-request session factory.
Uses psycopg3 (psycopg) driver — compatible with Termux and Render.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# psycopg3 requires postgresql+psycopg:// dialect prefix.
# We normalise both postgresql:// and postgres:// (Supabase uses both).
_db_url = (
    settings.DATABASE_URL
    .replace("postgresql://", "postgresql+psycopg://")
    .replace("postgres://", "postgresql+psycopg://")
)

engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

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
