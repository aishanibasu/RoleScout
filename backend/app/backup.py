"""Create a consistent local SQLite backup, retaining the latest 14 snapshots."""

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .db import database_path
from .locks import process_lock


def backup(path=None, destination=None, keep=14):
    if keep < 1:
        raise ValueError("Keep at least one backup")
    source = database_path(path)
    if not source.is_file():
        raise FileNotFoundError("Database does not exist; nothing to back up")
    directory = Path(destination) if destination else source.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with process_lock(source, "backup"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = directory / f"roles-{stamp}.sqlite3"
        fd, temporary = tempfile.mkstemp(prefix=".backup-", dir=directory)
        os.close(fd)
        try:
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(temporary)) as snapshot:
                    original.backup(snapshot)
                    if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Backup integrity check failed")
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        snapshots = sorted(directory.glob("roles-????????T????????????Z.sqlite3"), reverse=True)
        for old in snapshots[keep:]:
            old.unlink()
        return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()
    print(backup(destination=args.destination, keep=args.keep))


if __name__ == "__main__":
    main()
