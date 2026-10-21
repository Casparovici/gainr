"""The migrations build the same schema the models describe.

app.main builds missing tables with create_all, and the deploy runs `alembic upgrade head`, so the
real database has tables from both. These tests keep the two in step: a database migrated from
nothing must match the models, and the newest migrations must also apply to one create_all built.
"""

import importlib
import pkgutil
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

import app.models
from app.db import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALIGN_REVISION = "d9e3f1a6c2b8"
BEFORE_ALIGN = "c4f8e2a7b1d6"


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = url
    return config


def _drift(engine: sa.Engine) -> list:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


def test_every_model_module_is_registered_by_the_models_package():
    # Alembic's env.py imports only `app.models`; a model module that package doesn't import is
    # invisible to it, and autogenerate then proposes dropping that model's table.
    registered = set(Base.metadata.tables)
    for module in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{module.name}")
    assert set(Base.metadata.tables) == registered


def test_migrating_an_empty_database_builds_the_models_schema(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(url), "head")
    assert _drift(sa.create_engine(url)) == []


def test_aligning_a_create_all_database_changes_nothing(tmp_path):
    url = f"sqlite:///{tmp_path / 'created.db'}"
    engine = sa.create_engine(url)
    Base.metadata.create_all(engine)
    config = _alembic_config(url)
    command.stamp(config, BEFORE_ALIGN)
    command.upgrade(config, ALIGN_REVISION)
    assert _drift(engine) == []


@pytest.fixture()
def before_align(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    config = _alembic_config(url)
    command.upgrade(config, BEFORE_ALIGN)
    return config, sa.create_engine(url)


def test_aligning_keeps_rows_and_fills_missing_timestamps(before_align):
    config, engine = before_align
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO grecipe_lists (id, name, is_archived, created_at, updated_at) VALUES (1, 'Weekly', 0, NULL, NULL)"))
        # An orphan: the copy that adds the foreign key mustn't trip over it.
        connection.execute(sa.text("INSERT INTO grecipe_items (id, name, category_id, default_unit, is_archived) VALUES (1, 'Milk', 999, 'l', 0)"))
    command.upgrade(config, ALIGN_REVISION)
    with engine.connect() as connection:
        created, updated = connection.execute(sa.text("SELECT created_at, updated_at FROM grecipe_lists WHERE id = 1")).one()
        assert created is not None and updated is not None
        assert connection.execute(sa.text("SELECT category_id FROM grecipe_items WHERE id = 1")).scalar() == 999
    command.upgrade(config, "head")  # what came after the alignment must leave the schema aligned too
    assert _drift(engine) == []


def test_aligning_leaves_a_not_null_the_data_breaks(before_align):
    config, engine = before_align
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO portfolio_settings (id, portfolio_id) VALUES (99, NULL)"))
    command.upgrade(config, ALIGN_REVISION)
    columns = {c["name"]: c for c in sa.inspect(engine).get_columns("portfolio_settings")}
    assert columns["portfolio_id"]["nullable"]
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM portfolio_settings")).scalar() == 1


def test_the_journal_moves_into_notr_with_its_ids_dates_labels_and_positions(tmp_path):
    url = f"sqlite:///{tmp_path / 'journal.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "f3b8d2a6c4e1")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO assets (id, ticker, name, asset_class, native_currency, price_scale) VALUES (5, 'ACME', 'Acme', 'equity', 'EUR', 1)"))
        connection.execute(sa.text("INSERT INTO position_note_labels (id, name, sort_order, color, is_archived) VALUES (3, 'Thesis', 1, '#112233', 0)"))
        connection.execute(sa.text(
            "INSERT INTO position_notes (id, title, body, created_at, updated_at) "
            "VALUES (7, 'Why I hold it', '**moat**', '2026-01-02 03:04:05', '2026-02-03 04:05:06')"
        ))
        connection.execute(sa.text("INSERT INTO position_note_assets (note_id, asset_id) VALUES (7, 5)"))
        connection.execute(sa.text("INSERT INTO position_note_label_links (note_id, label_id) VALUES (7, 3)"))

    command.upgrade(config, "head")

    with engine.connect() as connection:
        note = connection.execute(sa.text("SELECT id, title, body, pinned, is_archived, created_at, updated_at FROM notr_notes")).one()
        assert tuple(note[:5]) == (7, "Why I hold it", "**moat**", 0, 0)
        assert str(note[5]).startswith("2026-01-02 03:04:05") and str(note[6]).startswith("2026-02-03 04:05:06")
        assert tuple(connection.execute(sa.text("SELECT id, name, color FROM notr_labels")).one()) == (3, "Thesis", "#112233")
        assert tuple(connection.execute(sa.text("SELECT note_id, asset_id FROM notr_note_assets")).one()) == (7, 5)
        assert tuple(connection.execute(sa.text("SELECT note_id, label_id FROM notr_note_label_links")).one()) == (7, 3)
    tables = set(sa.inspect(engine).get_table_names())
    assert not {"position_notes", "position_note_assets", "position_note_labels", "position_note_label_links"} & tables
    assert _drift(engine) == []


def test_downgrading_notr_puts_the_notes_about_positions_back(tmp_path):
    url = f"sqlite:///{tmp_path / 'back.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "head")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO assets (id, ticker, name, asset_class, native_currency, price_scale) VALUES (5, 'ACME', 'Acme', 'equity', 'EUR', 1)"))
        for note_id, title in ((1, "About a position"), (2, "Plain note")):
            connection.execute(sa.text(
                f"INSERT INTO notr_notes (id, title, body, pinned, is_archived) VALUES ({note_id}, '{title}', '', 0, 0)"
            ))
        connection.execute(sa.text("INSERT INTO notr_note_assets (note_id, asset_id) VALUES (1, 5)"))

    command.downgrade(config, "f3b8d2a6c4e1")

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT title FROM position_notes")).scalars().all() == ["About a position"]
        assert connection.execute(sa.text("SELECT asset_id FROM position_note_assets")).scalars().all() == [5]
