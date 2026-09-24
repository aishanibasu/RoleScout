import sqlite3

import pytest

from app.backup import backup
from app.services import write_agents


def test_snapshot_is_consistent_and_can_be_restored(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE notes (text TEXT)")
        connection.execute("INSERT INTO notes VALUES ('Interview Friday')")
        connection.commit()
        snapshot = backup(source)
        connection.execute("DELETE FROM notes")
        connection.commit()
    with sqlite3.connect(snapshot) as restored:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT text FROM notes").fetchone()[0] == "Interview Friday"
    assert snapshot.stat().st_mode & 0o777 == 0o600


def test_retention_only_removes_owned_snapshots(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE test (id INT)")
    folder = tmp_path / "backups"
    first = backup(source, folder, keep=2)
    unrelated = folder / "manual.sqlite3"
    unrelated.write_text("preserve")
    second = backup(source, folder, keep=2)
    third = backup(source, folder, keep=2)
    assert not first.exists()
    assert second.exists() and third.exists() and unrelated.exists()


def test_missing_database_and_invalid_retention(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup(tmp_path / "absent.sqlite3")
    with pytest.raises(ValueError):
        backup(tmp_path / "absent.sqlite3", keep=0)


def test_login_agents_use_absolute_paths_and_separate_schedules(tmp_path):
    import plistlib

    backend = tmp_path / "Project with spaces" / "backend"
    paths = write_agents(tmp_path / "agents", backend, "/example/.venv/bin/python")
    scheduler, snapshots = [plistlib.loads(path.read_bytes()) for path in paths]
    assert scheduler["WorkingDirectory"] == str(backend)
    assert scheduler["ProgramArguments"] == ["/example/.venv/bin/python", "-m", "app.scheduler"]
    assert scheduler["KeepAlive"] and scheduler["ThrottleInterval"] == 60
    assert snapshots["StartCalendarInterval"] == {"Hour": 10, "Minute": 0}
    assert "KeepAlive" not in snapshots
    assert all(config["RunAtLoad"] for config in (scheduler, snapshots))
