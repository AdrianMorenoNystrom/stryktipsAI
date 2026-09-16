"""Shared SQLite/WAL transactions and immutable content-addressed raw bytes."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import sqlite3


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Timezone required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


class SQLiteArchive:
    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        try:
            with con:
                yield con
        finally:
            con.close()

    def save_raw(self, raw: bytes) -> str:
        path = self.root / "raw" / (hashlib.sha256(raw).hexdigest() + ".raw")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("Raw content hash collision")
        return str(path.relative_to(self.root))
