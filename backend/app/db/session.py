"""Database engine and request-scoped session."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_pre_ping keeps long-lived Supabase pooler connections from going stale.
# SQLite (used by the test suite) takes neither pool sizing nor cross-thread
# connections by default, so those options are applied only to real databases.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_options: dict = (
    {"connect_args": {"check_same_thread": False}}
    if _is_sqlite
    else {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
)

engine = create_engine(settings.DATABASE_URL, **_engine_options)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
