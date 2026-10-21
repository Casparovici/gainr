from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

# How long a connection waits for another one's write lock before giving up with "database is
# locked". The daily syncs write for a while; a page load during one should wait, not fail.
SQLITE_BUSY_TIMEOUT_SECONDS = 15


def configure_sqlite(engine: Engine) -> None:
    """Per-connection SQLite settings (see docs/adr/0039-sqlite-schema-and-connection.md):

    - foreign keys enforced, so ON DELETE CASCADE / SET NULL actually happen and nothing can point
      at a row that doesn't exist. SQLite leaves them off unless asked, per connection;
    - write-ahead logging, so the web app keeps reading while a timer script writes, and the
      other way round. WAL is a property of the database file; setting it again is a no-op.

    Alembic's own engine doesn't get this: its batch migrations copy and drop tables, which must
    happen with foreign keys off."""
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        if engine.url.database not in (None, "", ":memory:"):
            cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()


connect_args = (
    {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_SECONDS} if DATABASE_URL.startswith("sqlite") else {}
)
engine = create_engine(DATABASE_URL, connect_args=connect_args)
configure_sqlite(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Commits on clean exit so read endpoints that opportunistically cache fetched prices
    (PriceService) actually persist that cache, not just flush it within the request."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
