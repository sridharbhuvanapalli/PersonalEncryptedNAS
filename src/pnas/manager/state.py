from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ManagerState:
    """SQLite contains only health observations and audit metadata, never secrets."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as database:
            database.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                  recorded_at TEXT NOT NULL,
                  metric TEXT NOT NULL,
                  value REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manager_audit (
                  recorded_at TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  outcome TEXT NOT NULL,
                  details_json TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        database = sqlite3.connect(self.path)
        try:
            with database:
                yield database
        finally:
            database.close()

    def observation(self, metric: str, value: float) -> None:
        with self.connect() as database:
            database.execute(
                "INSERT INTO observations VALUES (?, ?, ?)",
                (datetime.now(UTC).isoformat(), metric, value),
            )

    def audit(self, actor: str, action: str, outcome: str, details: dict[str, Any]) -> None:
        with self.connect() as database:
            database.execute(
                "INSERT INTO manager_audit VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    actor,
                    action,
                    outcome,
                    json.dumps(details, sort_keys=True),
                ),
            )
