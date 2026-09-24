"""Local process locks, released by the OS even when a worker crashes (macOS/Linux)."""
import fcntl
from contextlib import contextmanager
from .db import database_path

class AlreadyRunning(RuntimeError):
    pass

@contextmanager
def process_lock(path, name):
    database = database_path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    # Keep the file: unlinking a held lock can permit two owners on different inodes.
    with open(str(database) + '.' + name + '.lock', 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunning(f'{name} is already running for this database') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
