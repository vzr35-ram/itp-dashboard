"""
db/connection.py

Responsible for one thing: creating and returning a SQLAlchemy engine
and session factory pointed at the local SQLite file.

Usage:
    from db.connection import get_session
    with get_session() as session:
        session.add(...)
        session.commit()
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# The SQLite file lives at db/dashboard.db relative to the project root.
# When GitHub Actions clones the repo, this path resolves correctly
# because the runner's working directory is the repo root.
DB_PATH = os.path.join(os.path.dirname(__file__), "dashboard.db")
DB_URL = f"sqlite:///{DB_PATH}"

# echo=False in production — set to True temporarily if you want to see
# every SQL statement printed to the console for debugging.
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + threading
    echo=False,
)

SessionFactory = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """
    All ORM models inherit from this Base.
    Importing Base here (rather than in models.py) means connection.py
    is the single source of truth for the engine — models.py just
    imports Base from here.
    """
    pass


@contextmanager
def get_session():
    """
    Context manager that yields a database session and handles
    commit/rollback/close automatically.

    Use it like:
        with get_session() as session:
            session.add(record)
            # commit happens automatically on exit

    If an exception is raised inside the block, the transaction is
    rolled back and the exception re-raised.
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Creates all tables defined in the ORM models if they don't exist.
    Safe to call repeatedly — it's a no-op if tables already exist.
    Called once at the start of each collector run and by the dashboard.
    """
    # Import here to avoid circular imports — models.py imports Base from
    # this file, so we import models here (after Base is defined) to
    # register all table definitions before calling create_all.
    import db.models  # noqa: F401
    Base.metadata.create_all(engine)
