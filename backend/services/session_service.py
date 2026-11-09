import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.config import DATABASE_PATH, DATA_DIR, DetectionSettings


class SessionService:
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        self._lock = threading.Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    alert_count INTEGER NOT NULL DEFAULT 0,
                    settings_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def start(self, settings: DetectionSettings):
        started = datetime.now(timezone.utc)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sessions (started_at, settings_json) VALUES (?, ?)",
                (started.isoformat(), settings.model_dump_json()),
            )
            return cursor.lastrowid, started

    def record_alert(self, session_id):
        occurred = datetime.now(timezone.utc)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO alerts (session_id, occurred_at) VALUES (?, ?)",
                (session_id, occurred.isoformat()),
            )
            connection.execute(
                "UPDATE sessions SET alert_count = alert_count + 1 WHERE id = ?",
                (session_id,),
            )
        return occurred

    def stop(self, session_id):
        if session_id is None:
            return
        ended = datetime.now(timezone.utc)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET ended_at = COALESCE(ended_at, ?) WHERE id = ?",
                (ended.isoformat(), session_id),
            )

    def list_sessions(self, limit=100):
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._as_dict(connection, row) for row in rows]

    def get_session(self, session_id):
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._as_dict(connection, row) if row else None

    def clear(self):
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM alerts")
            connection.execute("DELETE FROM sessions")
            connection.execute("DELETE FROM sqlite_sequence WHERE name IN ('alerts', 'sessions')")

    def _as_dict(self, connection, row):
        ended = datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None
        started = datetime.fromisoformat(row["started_at"])
        alerts = connection.execute(
            "SELECT occurred_at FROM alerts WHERE session_id = ? ORDER BY occurred_at",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": max(
                0.0, ((ended or datetime.now(timezone.utc)) - started).total_seconds()
            ),
            "alert_count": row["alert_count"],
            "alert_timestamps": [datetime.fromisoformat(item["occurred_at"]) for item in alerts],
            "settings": DetectionSettings.model_validate_json(row["settings_json"]),
        }
