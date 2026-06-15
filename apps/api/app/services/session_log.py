import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel


_SECRET_PATTERNS = [
    re.compile(
        r"\b(api[_-]?key|access[_-]?key|secret|token|password)\b\s*[:=]\s*[\"']?[^,\s\"'&]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"\b(?:sk|ak)-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
]


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

    def is_available(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

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

    def list_sessions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        limit = self._clamp_limit(limit)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, COUNT(*) AS turns, MAX(id) AS last_id
                FROM session_logs
                GROUP BY session_id
                ORDER BY MAX(id) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            sessions: list[dict[str, Any]] = []
            for row in rows:
                latest = connection.execute(
                    "SELECT * FROM session_logs WHERE id = ?",
                    (row["last_id"],),
                ).fetchone()
                if latest is None:
                    continue
                sessions.append(
                    {
                        "session_id": latest["session_id"],
                        "last_message_at": latest["created_at"],
                        "turns": int(row["turns"]),
                        "last_intent_type": latest["intent_type"],
                        "last_user_text": self._redact_and_truncate(latest["user_text"], max_chars=100),
                        "last_error": self._public_error(latest),
                        "last_latency_ms": latest["latency_total_ms"],
                    }
                )
            return sessions

    def list_session_events(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = self._clamp_limit(limit, max_limit=200)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM session_logs
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def list_errors(self, *, limit: int = 30) -> list[dict[str, Any]]:
        limit = self._clamp_limit(limit, max_limit=100)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM session_logs
                WHERE error_json IS NOT NULL OR intent_type = 'fallback'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        errors: list[dict[str, Any]] = []
        for row in rows:
            error = self._public_error(row)
            if error is None:
                continue
            errors.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "message_id": row["message_id"],
                    "created_at": row["created_at"],
                    "intent_type": row["intent_type"],
                    "code": error.get("code") or "UNKNOWN_ERROR",
                    "message": error.get("message") or "未记录错误摘要",
                    "user_text": self._redact_and_truncate(row["user_text"], max_chars=100),
                    "latency_total_ms": row["latency_total_ms"],
                }
            )
        return errors

    def metrics(self, *, recent_limit: int = 30) -> dict[str, Any]:
        recent_limit = self._clamp_limit(recent_limit, max_limit=100)
        with self._connect() as connection:
            summary = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_events,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    AVG(latency_total_ms) AS avg_latency_ms,
                    MAX(latency_total_ms) AS max_latency_ms,
                    SUM(CASE WHEN error_json IS NOT NULL OR intent_type = 'fallback' THEN 1 ELSE 0 END)
                        AS error_events
                FROM session_logs
                """
            ).fetchone()
            latency_rows = connection.execute(
                "SELECT latency_total_ms FROM session_logs ORDER BY latency_total_ms ASC"
            ).fetchall()
            bucket_rows = connection.execute(
                """
                SELECT
                    intent_type AS name,
                    COUNT(*) AS count,
                    AVG(latency_total_ms) AS avg_latency_ms,
                    MAX(latency_total_ms) AS max_latency_ms,
                    SUM(CASE WHEN error_json IS NOT NULL OR intent_type = 'fallback' THEN 1 ELSE 0 END)
                        AS error_count
                FROM session_logs
                GROUP BY intent_type
                ORDER BY count DESC, name ASC
                """
            ).fetchall()
            recent_rows = connection.execute(
                """
                SELECT created_at, session_id, intent_type, latency_total_ms
                FROM session_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (recent_limit,),
            ).fetchall()

        latencies = [int(row["latency_total_ms"]) for row in latency_rows]
        return {
            "total_events": int(summary["total_events"] or 0),
            "total_sessions": int(summary["total_sessions"] or 0),
            "error_events": int(summary["error_events"] or 0),
            "avg_latency_ms": self._nullable_int(summary["avg_latency_ms"]),
            "p50_latency_ms": self._percentile(latencies, 50),
            "p95_latency_ms": self._percentile(latencies, 95),
            "max_latency_ms": self._nullable_int(summary["max_latency_ms"]),
            "by_intent": [
                {
                    "name": row["name"],
                    "count": int(row["count"] or 0),
                    "avg_latency_ms": self._nullable_int(row["avg_latency_ms"]),
                    "max_latency_ms": self._nullable_int(row["max_latency_ms"]),
                    "error_count": int(row["error_count"] or 0),
                }
                for row in bucket_rows
            ],
            "recent_latency": [
                {
                    "created_at": row["created_at"],
                    "session_id": row["session_id"],
                    "intent_type": row["intent_type"],
                    "latency_total_ms": row["latency_total_ms"],
                }
                for row in recent_rows
            ],
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        try:
            tz = ZoneInfo("Asia/Shanghai")
        except ZoneInfoNotFoundError:
            tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
        return datetime.now(tz).isoformat(timespec="seconds")

    @staticmethod
    def _to_json(value: BaseModel | dict[str, Any] | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, BaseModel):
            return value.model_dump_json(exclude_none=True)
        return json.dumps(value, ensure_ascii=False)

    def _event_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "message_id": row["message_id"],
            "created_at": row["created_at"],
            "user_text": self._redact_and_truncate(row["user_text"], max_chars=120),
            "intent_type": row["intent_type"],
            "response_summary": self._response_summary(row["dora_response_json"]),
            "screen_action": self._safe_json(row["screen_action_json"]),
            "error": self._public_error(row),
            "latency_total_ms": row["latency_total_ms"],
        }

    def _public_error(self, row: sqlite3.Row) -> dict[str, Any] | None:
        error = self._safe_json(row["error_json"])
        if not isinstance(error, dict) and row["intent_type"] == "fallback":
            response = self._safe_json(row["dora_response_json"])
            if isinstance(response, dict):
                response_error = response.get("error")
                error = response_error if isinstance(response_error, dict) else None
                if error is None:
                    error = {
                        "code": response.get("reason") or "FALLBACK",
                        "message": response.get("speak_text") or "服务已返回兜底回答。",
                    }
        if not isinstance(error, dict):
            return None
        code = self._redact_and_truncate(str(error.get("code") or "UNKNOWN_ERROR"), max_chars=80)
        message = self._redact_and_truncate(str(error.get("message") or "未记录错误摘要"), max_chars=180)
        return {"code": code, "message": message}

    def _response_summary(self, value: str | None) -> str | None:
        response = self._safe_json(value)
        if not isinstance(response, dict):
            return None
        text = response.get("speak_text") or response.get("title")
        if text is None:
            return None
        return self._redact_and_truncate(str(text), max_chars=160)

    @staticmethod
    def _safe_json(value: str | None) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _redact_and_truncate(value: str | None, *, max_chars: int) -> str | None:
        if value is None:
            return None
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        for pattern in _SECRET_PATTERNS:
            if "api" in pattern.pattern:
                text = pattern.sub(lambda match: f"{match.group(1)}=<redacted>", text)
            else:
                text = pattern.sub("<redacted>", text)
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 1]}…"

    @staticmethod
    def _clamp_limit(limit: int, *, max_limit: int = 100) -> int:
        return max(1, min(int(limit), max_limit))

    @staticmethod
    def _nullable_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _percentile(values: list[int], percentile: int) -> int | None:
        if not values:
            return None
        rank = round((percentile / 100) * (len(values) - 1))
        return values[max(0, min(rank, len(values) - 1))]
