from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All models' tables live in this metadata,
    which Alembic's env.py imports as target_metadata."""
