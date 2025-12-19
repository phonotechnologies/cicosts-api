"""
CICosts API - Database Connection

Uses SQLAlchemy 2.0 with sync support (Lambda-optimized).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


# Lazy engine creation to handle missing DATABASE_URL at startup
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL is not configured")
        _engine = create_engine(
            settings.DATABASE_URL,
            poolclass=NullPool,  # Lambda creates new connections each invocation
            echo=settings.ENVIRONMENT == "development",
        )
    return _engine


def get_session_local():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


def get_db():
    """Dependency for database session."""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
