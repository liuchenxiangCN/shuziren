from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
from time import perf_counter
from typing import Any

from app.control_plane.errors import ControlPlaneError
from app.control_plane.p2_1 import (
    CAPABILITY_KEYS,
    FALLBACK_TERMINAL_REASONS,
    PROVIDER_BY_ID,
    fallback_decision,
)
from app.control_plane.p2_2 import (
    EXECUTOR_WORKERS,
    MAX_GLOBAL_INFLIGHT,
    MAX_PER_SCREEN_INFLIGHT,
    MAX_RETAINED_JOBS,
)
from app.control_plane.security import opaque_id

MAX_RETAINED_DRILLS = 128
DRILL_SIGNALS = (
    "timeout",
    "unavailable",
    "unsupported",
    "permission_denied",
    "invalid_request",
    "unauthorized_template",
    "cancelled",
    "backpressure",
)
_EXECUTION_ERROR_STATES = {"FAILED", "TIMED_OUT", "CANCELLED", "REJECTED_BACKPRESSURE"}

# Mirrors the diagnostic failure contract of P2.1: technical failures and
# terminal failures start provider execution, backpressure never does.
_DRILL_SIGNAL_CONTRACT: dict[str, dict[str, Any]] = {
    **{
        signal: {
            "error_code": signal,
            "provider_execution_started": True,
            "queue_admission": "N/A",
        }
        for signal in (
            "timeout",
            "unavailable",
            "unsupported",
            "permission_denied",
            "invalid_request",
            "unauthorized_template",
            "cancelled",
        )
    },
    "backpressure": {
        "error_code": "unavailable",
        "provider_execution_started": False,
        "queue_admission": "REJECTED",
    },
}


class P23ControlPlane:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self._drills: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._drills_lock = threading.RLock()

    # Screen-bound execution observability.

    def list_screen_executions(
        self,
        principal: Any,
        screen_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "limit must be from 1 through 100",
            )
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
            rows = connection.execute(
                """
                SELECT e.*, d.display_name AS dataset_label
                FROM query_executions e
                LEFT JOIN query_datasets d
                  ON d.tenant_id = e.tenant_id
                 AND d.deployment_id = e.deployment_id
                 AND d.dataset_id = e.dataset_id
                WHERE e.tenant_id = ? AND e.deployment_id = ? AND e.screen_id = ?
                ORDER BY e.created_at DESC, e.execution_id DESC
                LIMIT ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                    limit,
                ),
            ).fetchall()
        return {
            "api_version": "v1",
            "screen_instance_id": screen["screen_id"],
            "items": [self._execution_list_item(row) for row in rows],
        }

    def screen_queue_status(
        self,
        principal: Any,
        screen_id: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
            rejected = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM query_executions
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                  AND state = 'REJECTED_BACKPRESSURE'
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                ),
            ).fetchone()["count"]
        with self.owner.p2_2._jobs_lock:
            inflight = self.owner.p2_2._screen_inflight.get(screen["screen_id"], 0)
        return {
            "api_version": "v1",
            "screen_instance_id": screen["screen_id"],
            "screen": {
                "inflight": inflight,
                "per_screen_limit": MAX_PER_SCREEN_INFLIGHT,
            },
            "capacity": {
                "global_inflight_limit": MAX_GLOBAL_INFLIGHT,
                "per_screen_inflight_limit": MAX_PER_SCREEN_INFLIGHT,
                "executor_workers": EXECUTOR_WORKERS,
                "retained_terminal_jobs": MAX_RETAINED_JOBS,
            },
            "counters": {
                "rejected_backpressure": rejected,
            },
        }

    # Screen-bound resilience drill: a deterministic in-process simulation of
    # the P2.1 fallback decision path. No provider execution, no external call.

    def start_resilience_drill(
        self,
        principal: Any,
        screen_id: str,
        *,
        capability: str,
        signal: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if capability not in CAPABILITY_KEYS or signal not in _DRILL_SIGNAL_CONTRACT:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Unknown resilience drill capability or signal",
            )
        operation_phase = "runResilienceDrill"
        command = {
            "screen_id": screen_id,
            "capability": capability,
            "signal": signal,
        }
        request_digest = self.owner._sensitive_request_digest(operation_phase, command)
        started = perf_counter()
        with self.owner.store.transaction() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_phase,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            snapshot = self._applied_capability_snapshot(
                connection,
                principal=principal,
                screen_id=screen["screen_id"],
            )
            result = self._run_drill(
                screen_id=screen["screen_id"],
                capability=capability,
                signal=signal,
                snapshot=snapshot,
                started=started,
            )
            with self._drills_lock:
                self._drills[result["drill_id"]] = result
                while len(self._drills) > MAX_RETAINED_DRILLS:
                    self._drills.popitem(last=False)
            self.owner._idempotency_store(
                connection,
                phase=operation_phase,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=self.owner.clock(),
            )
            self.owner._append_audit(
                connection,
                event_type="RESILIENCE_DRILL_RUN",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="RESILIENCE_DRILL",
                target_id=result["drill_id"],
                outcome="SUCCESS",
                reason=None,
                details={
                    "screen_id": result["screen_instance_id"],
                    "capability": capability,
                    "signal": signal,
                    "primary_provider_id": result["primary_provider_id"],
                    "resolved_provider_id": result["resolved_provider_id"],
                    "permission_equivalent": result["permission_equivalent"],
                    "provider_execution_started": result["provider_execution_started"],
                    "queue_admission": result["queue_admission"],
                    "decision": result["decision"],
                    "outcome": result["outcome"],
                    "terminal": result["terminal"],
                    "fallback_allowed": result["fallback_allowed"],
                    "latency_ms": result["latency_ms"],
                },
                now=self.owner.clock(),
            )
            return result

    def get_resilience_drill(
        self,
        principal: Any,
        screen_id: str,
        drill_id: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
        with self._drills_lock:
            drill = self._drills.get(drill_id)
        if drill is None or drill["screen_instance_id"] != screen["screen_id"]:
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Resilience drill was not found",
            )
        return dict(drill)

    def _applied_capability_snapshot(
        self,
        connection: sqlite3.Connection,
        *,
        principal: Any,
        screen_id: str,
    ) -> dict[str, Any] | None:
        binding = connection.execute(
            """
            SELECT * FROM runtime_bindings
            WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
            """,
            (principal.tenant_id, principal.deployment_id, screen_id),
        ).fetchone()
        if binding is None or binding["applied_release_target_id"] is None:
            return None
        return self.owner.p2_1.release_snapshot_response(
            connection,
            binding["applied_release_target_id"],
        )

    def _run_drill(
        self,
        *,
        screen_id: str,
        capability: str,
        signal: str,
        snapshot: dict[str, Any] | None,
        started: float,
    ) -> dict[str, Any]:
        contract = _DRILL_SIGNAL_CONTRACT[signal]
        selection = None
        if snapshot is not None:
            selection = snapshot["spec"][capability]
        if selection is None or not selection["enabled"]:
            return self._drill_response(
                screen_id=screen_id,
                capability=capability,
                signal=signal,
                primary_provider_id=None,
                fallback_provider_ids=[],
                permission_equivalent=None,
                provider_execution_started=False,
                queue_admission="N/A",
                decision=None,
                resolved_provider_id=None,
                outcome="CAPABILITY_DISABLED",
                terminal=True,
                fallback_allowed=False,
                started=started,
            )
        primary_provider_id = selection["primary_provider_id"]
        fallback_provider_ids = list(selection["fallback_provider_ids"])
        if not fallback_provider_ids:
            decision = "TERMINAL" if contract["error_code"] in FALLBACK_TERMINAL_REASONS else "NOT_ALLOWED"
            return self._drill_response(
                screen_id=screen_id,
                capability=capability,
                signal=signal,
                primary_provider_id=primary_provider_id,
                fallback_provider_ids=fallback_provider_ids,
                permission_equivalent=None,
                provider_execution_started=contract["provider_execution_started"],
                queue_admission=contract["queue_admission"],
                decision=decision,
                resolved_provider_id=None,
                outcome="NO_FALLBACK_CONFIGURED",
                terminal=True,
                fallback_allowed=False,
                started=started,
            )
        fallback_provider_id = fallback_provider_ids[0]
        primary_provider = PROVIDER_BY_ID.get(primary_provider_id)
        fallback_provider = PROVIDER_BY_ID.get(fallback_provider_id)
        permission_equivalent = (
            primary_provider is not None
            and fallback_provider is not None
            and primary_provider["permission_scope"] == fallback_provider["permission_scope"]
        )
        fallback_provider_state = fallback_provider["state"] if fallback_provider is not None else "disabled"
        evaluation = fallback_decision(
            contract["error_code"],
            permission_equivalent,
            fallback_provider_state,
        )
        if evaluation["fallback_allowed"]:
            outcome = "FALLBACK_RESOLVED"
            resolved_provider_id: str | None = fallback_provider_id
        else:
            outcome = "TERMINAL_NO_FALLBACK"
            resolved_provider_id = None
        return self._drill_response(
            screen_id=screen_id,
            capability=capability,
            signal=signal,
            primary_provider_id=primary_provider_id,
            fallback_provider_ids=fallback_provider_ids,
            permission_equivalent=permission_equivalent,
            provider_execution_started=contract["provider_execution_started"],
            queue_admission=contract["queue_admission"],
            decision=evaluation["decision"],
            resolved_provider_id=resolved_provider_id,
            outcome=outcome,
            terminal=not evaluation["fallback_allowed"],
            fallback_allowed=evaluation["fallback_allowed"],
            started=started,
        )

    def _drill_response(
        self,
        *,
        screen_id: str,
        capability: str,
        signal: str,
        primary_provider_id: str | None,
        fallback_provider_ids: list[str],
        permission_equivalent: bool | None,
        provider_execution_started: bool,
        queue_admission: str,
        decision: str | None,
        resolved_provider_id: str | None,
        outcome: str,
        terminal: bool,
        fallback_allowed: bool,
        started: float,
    ) -> dict[str, Any]:
        return {
            "api_version": "v1",
            "drill_id": opaque_id("drill"),
            "screen_instance_id": screen_id,
            "capability": capability,
            "signal": signal,
            "primary_provider_id": primary_provider_id,
            "fallback_provider_ids": fallback_provider_ids,
            "permission_equivalent": permission_equivalent,
            "provider_execution_started": provider_execution_started,
            "queue_admission": queue_admission,
            "decision": decision,
            "resolved_provider_id": resolved_provider_id,
            "outcome": outcome,
            "terminal": terminal,
            "fallback_allowed": fallback_allowed,
            "created_at": self.owner.clock(),
            "latency_ms": max(0, int((perf_counter() - started) * 1000)),
        }

    def _execution_list_item(self, row: sqlite3.Row) -> dict[str, Any]:
        item: dict[str, Any] = {
            "execution_id": row["execution_id"],
            "dataset_id": row["dataset_id"],
            "dataset_label": row["dataset_label"],
            "state": row["state"],
            "request_id": row["request_id"],
            "latency_ms": row["latency_ms"],
            "row_count": row["row_count"],
            "result_retained": self._result_retained(row),
            "error": None,
            "created_at": row["created_at"],
            "terminal_at": row["completed_at"],
        }
        if row["state"] in _EXECUTION_ERROR_STATES:
            item["error"] = self.owner.p2_2._execution_response_from_row(row)["error"]
        return item

    def _result_retained(self, row: sqlite3.Row) -> bool:
        if row["state"] != "SUCCEEDED":
            return False
        with self.owner.p2_2._jobs_lock:
            job = self.owner.p2_2._jobs.get(row["execution_id"])
        if job is None:
            return False
        with job.lock:
            return job.result is not None and "rows" in job.result
