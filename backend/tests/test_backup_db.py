import gzip
import sqlite3

import pytest

from scripts import backup_db


@pytest.fixture()
def database(tmp_path, monkeypatch):
    db = tmp_path / "portfolio.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
    monkeypatch.setattr(backup_db.config, "DATABASE_URL", f"sqlite:///{db}")
    monkeypatch.setattr(backup_db, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_db, "_upload", lambda path: pytest.fail("--no-upload must not upload"))
    return tmp_path


def test_a_tagged_local_backup_is_a_readable_copy(database):
    backup_db.main(["--tag", "pre-migrate-1a2b3c4", "--no-upload"])

    [path] = (database / "backups").glob("portfolio-*-pre-migrate-1a2b3c4.db.gz")
    restored = database / "restored.db"
    restored.write_bytes(gzip.decompress(path.read_bytes()))
    with sqlite3.connect(restored) as conn:
        assert conn.execute("SELECT x FROM t").fetchone() == (42,)


def test_a_tag_that_could_leave_the_backup_folder_is_refused(database):
    with pytest.raises(SystemExit):
        backup_db.main(["--tag", "../../etc", "--no-upload"])
