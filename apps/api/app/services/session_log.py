import json
import sqlite3
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class SessionLogStore:
    def __init__(self, sqlite_path: str | Path) -> None:
        self.sqlite_path = Path(sqlite_path)

    def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    user_text TEXT,
                    intent_type TEXT NOT NULL,
                    dora_response_json TEXT,
                    screen_action_json TEXT,
                    error_json TEXT,
                    latency_total_ms INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def log_chat(
        self,
        *,
        session_id: str,
        message_id: str,
        user_text: str,
        intent_type: str,
        dora_response: BaseModel | dict[str, Any],
        screen_action: dict[str, Any] | None,
        error: dict[str, Any] | None,
        started_at: float,
    ) -> None:
        latency_ms = int((perf_counter() - started_at) * 1000)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO session_logs (
                    session_id,
                    message_id,
                    created_at,
                    user_text,
                    intent_type,
                    dora_response_json,
                    screen_action_json,
                    error_json,
                    latency_total_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    message_id,
                    self._now(),
                    user_text,
                    intent_type,
                    self._to_json(dora_response),
                    self._to_json(screen_action),
                    self._to_json(error),
                    latency_ms,
                ),
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

    @staticmethod
    def _to_json(value: BaseModel | dict[str, Any] | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, BaseModel):
            return value.model_dump_json(exclude_none=True)
        return json.dumps(value, ensure_ascii=False)

