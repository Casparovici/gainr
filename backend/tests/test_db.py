"""The per-connection SQLite settings app.db applies (docs/adr/0039)."""

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db import Base, configure_sqlite
from app.models import GriprTransaction


def test_a_file_database_uses_wal_and_enforces_foreign_keys(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    configure_sqlite(engine)
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1


def test_a_row_pointing_at_nothing_is_refused(db_session):
    db_session.add(GriprTransaction(date=sa.func.current_date(), type="expense", amount=1, account_id=999))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_without_the_settings_sqlite_leaves_foreign_keys_off(tmp_path):
    # What Alembic's own engine gets: its batch migrations copy and drop tables.
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'plain.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 0
