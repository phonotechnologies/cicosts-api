"""
CICosts API - Database Connection

Uses SQLAlchemy 2.0 with async support.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


# Create engine (sync for now, can add async later)
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,  # Lambda creates new connections each invocation
    echo=settings.ENVIRONMENT == "development",
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
