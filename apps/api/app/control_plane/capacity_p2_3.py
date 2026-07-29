"""P2.3 deployment-local capacity measurement for controlled querying.

Builds an isolated in-process control-plane service on a temporary database
(never the repository ``data/`` directory), publishes three screens on
distinct capability profiles with one generated non-customer Excel dataset
each, and measures sequential, concurrent and saturation behavior of the
accepted P2.2/P2.3 runtime.

The output is a deployment-local reference measurement: it is not an SLA,
not a throughput promise for any other environment and not a
customer-environment certification.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import platform
import secrets
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.control_plane.errors import ControlPlaneError
from app.control_plane.p2_2 import (
    EXECUTOR_WORKERS,
    MAX_GLOBAL_INFLIGHT,
    MAX_PER_SCREEN_INFLIGHT,
    MAX_RETAINED_JOBS,
)
from app.control_plane.router import (
    control_plane_error_handler,
    router,
    sanitized_validation_errors,
)
from app.control_plane.service import ControlPlaneService

SCHEMA_VERSION = "p2_3_capacity_measurement_v1"
ORIGIN = "https://manage.test"
DEVICE_ORIGIN = "https://device.test"
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "REJECTED_BACKPRESSURE"}
POLL_INTERVAL_S = 0.01
POLL_TIMEOUT_S = 30.0
SATURATION_SUBMISSIONS_PER_SCREEN = 4
DISCLAIMER = (
    "Deployment-local reference measurement on this machine only. "
    "It is not an SLA, not a throughput promise for any other environment "
    "and not a customer-environment certification."
)


# Fixture construction (mirrors the accepted P2.2 test fixtures, kept
# self-contained so the CLI does not import the test suite).


def _workbook_base64() -> str:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Metrics"
    worksheet.append(["business_date", "shift", "output", "quality_rate"])
    worksheet.append(["2026-07-28", "A", 120, 0.98])
    worksheet.append(["2026-07-28", "B", 95, 0.96])
    worksheet.append(["2026-07-27", "A", 110, 0.97])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return base64.b64encode(output.getvalue()).decode("ascii")


def _mutation_headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}


def _login(app: FastAPI, username: str, password: str) -> tuple[TestClient, str]:
    client = TestClient(app, base_url=ORIGIN)
    response = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return client, response.headers["x-csrf-token"]


def _clone_client(app: FastAPI, source: TestClient) -> TestClient:
    # Each worker thread gets its own TestClient sharing the same session.
    clone = TestClient(app, base_url=ORIGIN)
    clone.cookies.update(source.cookies)
    return clone


def _request_action(
    client: TestClient,
    csrf: str,
    path: str,
    payload: dict[str, Any],
    key: str,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = _mutation_headers(csrf, **{"Idempotency-Key": key})
    headers.update(extra_headers or {})
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["state"] == "PENDING"
    return result


def _approve_action(
    client: TestClient,
    csrf: str,
    action: dict[str, Any],
    *,
    key: str,
) -> None:
    response = client.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=_mutation_headers(
            csrf,
            **{"Idempotency-Key": key, "If-Match": action["etag"]},
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "independent approval",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "APPROVED"


def _create_excel_source(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-sources",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": f"cap-source-create-{suffix}"}),
        json={
            "site_id": site_id,
            "display_name": f"Capacity reference workbook {suffix}",
            "engine": "EXCEL",
            "read_only_account_confirmed": True,
            "excel_file_name": "reference.xlsx",
            "excel_workbook_base64": _workbook_base64(),
        },
    )
    assert created.status_code == 201, created.text
    source = created.json()
    tested = client.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=_mutation_headers(
            csrf,
            **{"If-Match": source["etag"], "Idempotency-Key": f"cap-source-test-{suffix}"},
        ),
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["qualification_state"] == "AVAILABLE"
    fetched = client.get(f"/api/v1/control-plane/query-sources/{source['source_id']}")
    assert fetched.status_code == 200, fetched.text
    return fetched.json()


def _create_excel_dataset(
    client: TestClient,
    csrf: str,
    *,
    source_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-datasets",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": f"cap-dataset-create-{suffix}"}),
        json={
            "source_id": source_id,
            "display_name": f"Capacity shift output {suffix}",
            "metric_definition": "Finished units by business date and shift",
            "time_scope_description": "Rows in the generated reference workbook",
            "freshness_label": "Generated non-customer capacity fixture",
            "parameters": [{"name": "shift", "type": "string", "required": True}],
            "output_fields": ["business_date", "shift", "output", "quality_rate"],
            "definition": {
                "worksheet": "Metrics",
                "parameter_columns": {"shift": "shift"},
            },
            "row_limit": 20,
            "timeout_ms": 5_000,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _create_query_profile(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/capability-profiles",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": f"cap-profile-create-{suffix}"}),
        json={
            "site_id": site_id,
            "name": f"Capacity controlled query {suffix}",
            "description": "P2.3 capacity-measurement controlled-query profile",
            "source_preset_id": "mock_presenter",
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    spec = profile["head_version"]["spec"]
    spec["querying"] = {
        "enabled": True,
        "primary_provider_id": "controlled_query",
        "fallback_provider_ids": [],
        "timeout_ms": 5_000,
    }
    versioned = client.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=_mutation_headers(
            csrf,
            **{"If-Match": profile["etag"], "Idempotency-Key": f"cap-profile-version-{suffix}"},
        ),
        json={"spec": spec},
    )
    assert versioned.status_code == 201, versioned.text
    return versioned.json()


def _create_query_release(
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    screen_id: str,
    profile_version_id: str,
    dataset_version_ids: list[str],
    suffix: str,
) -> dict[str, Any]:
    created = implementation.post(
        "/api/v1/control-plane/config-drafts",
        headers=_mutation_headers(csrf_impl, **{"Idempotency-Key": f"cap-draft-create-{suffix}"}),
        json={
            "target_type": "SCREEN",
            "target_id": screen_id,
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    replaced = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=_mutation_headers(csrf_impl, **{"If-Match": draft["etag"]}),
        json={
            "welcome_text": f"P2.3 capacity measurement {suffix}",
            "fvs_binding_ref": f"https://fvs.example.test/p2-3-capacity/{suffix}",
        },
    )
    assert replaced.status_code == 200, replaced.text
    draft = replaced.json()
    assigned_profile = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/capability-profile",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-profile-assign-{suffix}"},
        ),
        json={"profile_version_id": profile_version_id},
    )
    assert assigned_profile.status_code == 200, assigned_profile.text
    draft = assigned_profile.json()
    assigned_query = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/query-datasets",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-query-assign-{suffix}"},
        ),
        json={"dataset_version_ids": dataset_version_ids},
    )
    assert assigned_query.status_code == 200, assigned_query.text
    draft = assigned_query.json()
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-validate-{suffix}"},
        ),
    )
    assert validated.status_code == 200, validated.text
    draft = validated.json()
    assert draft["validation"]["outcome"] == "VALID"
    previewed = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-preview-{suffix}"},
        ),
    )
    assert previewed.status_code == 200, previewed.text
    draft = previewed.json()
    submitted = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:submit-for-approval",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-submit-{suffix}"},
        ),
    )
    assert submitted.status_code == 200, submitted.text
    draft = submitted.json()
    approved = approver.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=_mutation_headers(
            csrf_approver,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-approve-{suffix}"},
        ),
        json={"reason": "independent P2.3 capacity approval"},
    )
    assert approved.status_code == 200, approved.text
    draft = approved.json()
    released = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:release",
        headers=_mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"], "Idempotency-Key": f"cap-release-{suffix}"},
        ),
        json={"reason": "create immutable P2.3 capacity release"},
    )
    assert released.status_code == 201, released.text
    return released.json()


def _enroll_device(
    app: FastAPI,
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    screen_id: str,
    suffix: str,
) -> tuple[TestClient, dict[str, str]]:
    payload = {"reason": f"enroll P2.3 capacity device {suffix}"}
    action = _request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        payload,
        f"cap-enroll-request-{suffix}",
    )
    _approve_action(approver, csrf_approver, action, key=f"cap-enroll-approve-{suffix}")
    issued = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": f"cap-enroll-execute-{suffix}",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert issued.status_code == 201, issued.text
    device = TestClient(app, base_url=DEVICE_ORIGIN)
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": f"cap-device-claim-{suffix}"},
        json={"enrollment_token": issued.json()["enrollment_token"]},
    )
    assert claimed.status_code == 200, claimed.text
    return device, {"Authorization": f"DeviceCredential {claimed.json()['credential']}"}


def _publish_and_ack(
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    device: TestClient,
    device_headers: dict[str, str],
    *,
    screen_id: str,
    release: dict[str, Any],
    suffix: str,
) -> None:
    binding = implementation.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
    target = release["targets"][0]
    payload = {
        "release_id": release["release_id"],
        "release_target_id": target["release_target_id"],
        "expected_binding_generation": binding["binding_generation"],
        "reason": f"publish P2.3 capacity release {suffix}",
    }
    action = _request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        payload,
        f"cap-publish-request-{suffix}",
        extra_headers={"If-Match": binding["etag"]},
    )
    _approve_action(approver, csrf_approver, action, key=f"cap-publish-approve-{suffix}")
    published = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": f"cap-publish-execute-{suffix}",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert published.status_code == 201, published.text
    current = device.get("/api/v1/device/config-releases/current", headers=device_headers)
    assert current.status_code == 200, current.text
    acknowledged = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": f"cap-ack-{suffix}"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    assert acknowledged.status_code == 200, acknowledged.text


class _MeasurementContext:
    """Isolated in-process control plane plus the three published screens."""

    def __init__(self, work_dir: Path) -> None:
        self._passwords = {
            username: f"capacity-only-{secrets.token_urlsafe(18)}"
            for username in ("admin-a", "admin-b", "implementation", "auditor")
        }
        database_path = work_dir / "control-plane.db"
        root_key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        self.service = ControlPlaneService(str(database_path), root_key, preview_mode=True)
        self.service.initialize_preview(
            tenant_id="tenant-capacity",
            deployment_id="deployment-capacity",
            screen_id="screen-capacity-fixture",
            identities=[
                {
                    "username": "admin-a",
                    "display_name": "Capacity Admin A",
                    "role_id": "platform_admin",
                    "password": self._passwords["admin-a"],
                },
                {
                    "username": "admin-b",
                    "display_name": "Capacity Admin B",
                    "role_id": "platform_admin",
                    "password": self._passwords["admin-b"],
                },
                {
                    "username": "implementation",
                    "display_name": "Capacity Implementation",
                    "role_id": "implementation_engineer",
                    "password": self._passwords["implementation"],
                },
                {
                    "username": "auditor",
                    "display_name": "Capacity Auditor",
                    "role_id": "auditor",
                    "password": self._passwords["auditor"],
                },
            ],
        )
        self.app = FastAPI()
        self.app.state.control_plane_service = self.service
        self.app.state.control_plane_allowed_origins = (ORIGIN,)
        self.app.include_router(router)
        self.app.add_exception_handler(ControlPlaneError, control_plane_error_handler)

        async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "details": sanitized_validation_errors(exc),
                    }
                },
            )

        self.app.add_exception_handler(RequestValidationError, validation_handler)
        self.implementation, self.csrf_impl = _login(
            self.app, "implementation", self._passwords["implementation"]
        )
        self.approver, self.csrf_approver = _login(self.app, "admin-a", self._passwords["admin-a"])
        self.runtimes = self._build_screens()

    def _build_screens(self) -> list[dict[str, Any]]:
        screens = self.implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:3]
        assert len(screens) == 3
        runtimes = []
        for index, screen in enumerate(screens):
            suffix = f"screen-{index}"
            source = _create_excel_source(
                self.implementation,
                self.csrf_impl,
                site_id=screen["site_id"],
                suffix=suffix,
            )
            dataset = _create_excel_dataset(
                self.implementation,
                self.csrf_impl,
                source_id=source["source_id"],
                suffix=suffix,
            )
            profile = _create_query_profile(
                self.implementation,
                self.csrf_impl,
                site_id=screen["site_id"],
                suffix=suffix,
            )
            release = _create_query_release(
                self.implementation,
                self.csrf_impl,
                self.approver,
                self.csrf_approver,
                screen_id=screen["screen_id"],
                profile_version_id=profile["head_version_id"],
                dataset_version_ids=[dataset["dataset_version_id"]],
                suffix=suffix,
            )
            device, device_headers = _enroll_device(
                self.app,
                self.implementation,
                self.csrf_impl,
                self.approver,
                self.csrf_approver,
                screen_id=screen["screen_id"],
                suffix=suffix,
            )
            _publish_and_ack(
                self.implementation,
                self.csrf_impl,
                self.approver,
                self.csrf_approver,
                device,
                device_headers,
                screen_id=screen["screen_id"],
                release=release,
                suffix=suffix,
            )
            runtimes.append(
                {
                    "screen_id": screen["screen_id"],
                    "dataset_id": dataset["dataset_id"],
                    "profile_id": profile["profile_id"],
                }
            )
        return runtimes

    def user_client(self) -> TestClient:
        return _clone_client(self.app, self.implementation)


# Execution helpers.


def _start_execution(
    client: TestClient,
    csrf: str,
    runtime: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/control-plane/screen-instances/{runtime['screen_id']}"
        f"/query-datasets/{runtime['dataset_id']}:execute",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": key}),
        json={"parameters": {"shift": "A"}},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _await_terminal(
    client: TestClient,
    screen_id: str,
    execution_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/control-plane/screen-instances/{screen_id}/query-executions/{execution_id}"
        )
        assert response.status_code == 200, response.text
        result = response.json()
        if result["state"] in TERMINAL_STATES:
            return result
        time.sleep(POLL_INTERVAL_S)
    raise AssertionError(f"Execution {execution_id} did not reach a terminal state")


def _run_timed_execution(
    context: _MeasurementContext,
    runtime: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    client = context.user_client()
    started_at = time.perf_counter()
    submitted = _start_execution(client, context.csrf_impl, runtime, key)
    if submitted["state"] in TERMINAL_STATES:
        terminal = submitted
    else:
        terminal = _await_terminal(client, runtime["screen_id"], submitted["execution_id"])
    latency_ms = (time.perf_counter() - started_at) * 1000.0
    return {
        "execution_id": terminal["execution_id"],
        "request_id": terminal["request_id"],
        "state": terminal["state"],
        "latency_ms": round(latency_ms, 3),
        "rows": len(terminal.get("rows") or []),
    }


def _queue_status(client: TestClient, screen_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/control-plane/screen-instances/{screen_id}/queue-status")
    assert response.status_code == 200, response.text
    return response.json()


def _latency_stats(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "min_ms": round(ordered[0], 3),
        "median_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "max_ms": round(ordered[-1], 3),
        "mean_ms": round(statistics.fmean(ordered), 3),
    }


def _environment_facts() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        # Only the executable basename is recorded; no host paths or usernames.
        "python_executable": Path(sys.executable).name,
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }


# Measurement phases.


def _phase_warmup(context: _MeasurementContext, warmup: int) -> int:
    completed = 0
    for index in range(warmup):
        for runtime in context.runtimes:
            result = _run_timed_execution(context, runtime, f"cap-warmup-{index}-{runtime['screen_id']}")
            assert result["state"] == "SUCCEEDED", result
            completed += 1
    return completed


def _phase_sequential_baseline(
    context: _MeasurementContext,
    rounds: int,
) -> dict[str, Any]:
    screens = []
    for runtime in context.runtimes:
        executions = [
            _run_timed_execution(context, runtime, f"cap-seq-{round_index}-{runtime['screen_id']}")
            for round_index in range(rounds)
        ]
        latencies = [item["latency_ms"] for item in executions]
        screens.append(
            {
                "screen_id": runtime["screen_id"],
                "dataset_id": runtime["dataset_id"],
                "latency_ms": latencies,
                "stats": _latency_stats(latencies),
                "states": [item["state"] for item in executions],
                "rows": [item["rows"] for item in executions],
                "all_succeeded": all(item["state"] == "SUCCEEDED" for item in executions),
            }
        )
    return {
        "rounds_per_screen": rounds,
        "screens": screens,
        "all_succeeded": all(screen["all_succeeded"] for screen in screens),
    }


def _phase_three_screen_concurrent(
    context: _MeasurementContext,
    rounds: int,
) -> dict[str, Any]:
    per_screen_latencies: dict[str, list[float]] = {runtime["screen_id"]: [] for runtime in context.runtimes}
    round_wall_ms: list[float] = []
    states: list[str] = []
    for round_index in range(rounds):
        barrier = threading.Barrier(len(context.runtimes))
        results: list[dict[str, Any] | None] = [None] * len(context.runtimes)

        def worker(
            index: int,
            runtime: dict[str, Any],
            round_barrier: threading.Barrier,
            round_results: list[dict[str, Any] | None],
            key: str,
        ) -> None:
            round_barrier.wait(timeout=POLL_TIMEOUT_S)
            round_results[index] = _run_timed_execution(context, runtime, key)

        threads = [
            threading.Thread(
                target=worker,
                args=(
                    index,
                    runtime,
                    barrier,
                    results,
                    f"cap-conc-{round_index}-{runtime['screen_id']}",
                ),
                daemon=True,
            )
            for index, runtime in enumerate(context.runtimes)
        ]
        started_at = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=POLL_TIMEOUT_S + 5.0)
        round_wall_ms.append((time.perf_counter() - started_at) * 1000.0)
        assert all(item is not None for item in results)
        for runtime, item in zip(context.runtimes, results, strict=True):
            assert item is not None
            per_screen_latencies[runtime["screen_id"]].append(item["latency_ms"])
            states.append(item["state"])
    total_wall_s = sum(round_wall_ms) / 1000.0
    completed = sum(1 for state in states if state == "SUCCEEDED")
    return {
        "rounds": rounds,
        "round_wall_ms": [round(value, 3) for value in round_wall_ms],
        "per_screen": [
            {
                "screen_id": runtime["screen_id"],
                "latency_ms": per_screen_latencies[runtime["screen_id"]],
                "stats": _latency_stats(per_screen_latencies[runtime["screen_id"]]),
            }
            for runtime in context.runtimes
        ],
        "completed": completed,
        "failed": len(states) - completed,
        "states": states,
        "throughput_completed_per_second": (round(completed / total_wall_s, 3) if total_wall_s > 0 else None),
        "all_succeeded": completed == len(states),
    }


def _phase_saturation(context: _MeasurementContext) -> dict[str, Any]:
    # The measurement temporarily wraps the Excel executor with a blocking
    # gate so slot admission is deterministic; the original executor is
    # restored before recovery is measured. No runtime code is changed.
    service = context.service.p2_2
    original_execute = service._execute_excel
    occupied = 0
    occupied_lock = threading.Lock()
    workers_occupied = threading.Event()
    release_workers = threading.Event()

    def blocking_execute(
        job: Any,
        dataset: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        nonlocal occupied
        with occupied_lock:
            occupied += 1
            if occupied >= EXECUTOR_WORKERS:
                workers_occupied.set()
        if not release_workers.wait(timeout=POLL_TIMEOUT_S):
            raise TimeoutError("capacity measurement saturation gate was not released")
        return original_execute(job, dataset, parameters)

    submissions_per_screen = SATURATION_SUBMISSIONS_PER_SCREEN
    total_submissions = submissions_per_screen * len(context.runtimes)
    responses: list[dict[str, Any] | None] = [None] * total_submissions
    service._execute_excel = blocking_execute
    try:
        barrier = threading.Barrier(total_submissions)

        def submit(index: int, runtime: dict[str, Any], slot: int) -> None:
            client = context.user_client()
            barrier.wait(timeout=POLL_TIMEOUT_S)
            responses[index] = _start_execution(
                client,
                context.csrf_impl,
                runtime,
                f"cap-sat-{slot}-{runtime['screen_id']}",
            )

        threads = []
        index = 0
        for runtime in context.runtimes:
            for slot in range(submissions_per_screen):
                threads.append(threading.Thread(target=submit, args=(index, runtime, slot), daemon=True))
                index += 1
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=POLL_TIMEOUT_S + 5.0)
        assert all(item is not None for item in responses)
        assert workers_occupied.wait(timeout=POLL_TIMEOUT_S)
        # Observe queue occupancy while the executor is saturated.
        observed_status = [
            _queue_status(context.user_client(), runtime["screen_id"]) for runtime in context.runtimes
        ]
    finally:
        release_workers.set()
        service._execute_excel = original_execute

    admitted = [item for item in responses if item is not None and item["state"] != "REJECTED_BACKPRESSURE"]
    rejected = [item for item in responses if item is not None and item["state"] == "REJECTED_BACKPRESSURE"]
    terminals = []
    for item in admitted:
        client = context.user_client()
        terminals.append(_await_terminal(client, item["screen_id"], item["execution_id"]))
    terminal_states = [item["state"] for item in terminals] + ["REJECTED_BACKPRESSURE"] * len(rejected)
    all_terminal = all(state in TERMINAL_STATES for state in terminal_states)

    # Recovery: after the drain, fresh submissions must succeed again.
    recovery_results = [
        _run_timed_execution(context, runtime, f"cap-recovery-{runtime['screen_id']}")
        for runtime in context.runtimes
    ]
    recovery_ok = all(item["state"] == "SUCCEEDED" for item in recovery_results)

    retryable_rejections = all((item.get("error") or {}).get("retryable") is True for item in rejected)
    return {
        "submitted": total_submissions,
        "submissions_per_screen": submissions_per_screen,
        "admitted": len(admitted),
        "completed": sum(1 for state in terminal_states if state == "SUCCEEDED"),
        "rejected_backpressure": len(rejected),
        "all_rejections_retryable": retryable_rejections,
        "terminal_states": terminal_states,
        "all_terminal": all_terminal,
        "observed_queue_status": [
            {
                "screen_id": status["screen_instance_id"],
                "inflight": status["screen"]["inflight"],
                "per_screen_limit": status["screen"]["per_screen_limit"],
                "rejected_backpressure": status["counters"]["rejected_backpressure"],
            }
            for status in observed_status
        ],
        "recovery": {
            "attempted": len(recovery_results),
            "succeeded": sum(1 for item in recovery_results if item["state"] == "SUCCEEDED"),
            "verdict": recovery_ok,
        },
        "bounded": len(admitted) <= MAX_GLOBAL_INFLIGHT and len(rejected) > 0,
    }


def run_measurement(output_dir: Path, *, rounds: int = 5, warmup: int = 1) -> dict[str, Any]:
    """Run the full capacity measurement and write both report files."""
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    if warmup < 0:
        raise ValueError("warmup must not be negative")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p2-3-capacity-") as temp_root:
        context = _MeasurementContext(Path(temp_root))
        warmup_completed = _phase_warmup(context, warmup)
        sequential = _phase_sequential_baseline(context, rounds)
        concurrent = _phase_three_screen_concurrent(context, rounds)
        saturation = _phase_saturation(context)

    report = {
        "schema_version": SCHEMA_VERSION,
        "disclaimer": DISCLAIMER,
        "environment": _environment_facts(),
        "config_limits": {
            "max_global_inflight": MAX_GLOBAL_INFLIGHT,
            "max_per_screen_inflight": MAX_PER_SCREEN_INFLIGHT,
            "executor_workers": EXECUTOR_WORKERS,
            "max_retained_jobs": MAX_RETAINED_JOBS,
        },
        "parameters": {
            "rounds": rounds,
            "warmup": warmup,
            "warmup_completed": warmup_completed,
            "screens": len(context.runtimes),
        },
        "phases": {
            "sequential_baseline": sequential,
            "three_screen_concurrent": concurrent,
            "saturation": saturation,
        },
        "counters": {
            "sequential_executions": sum(screen["stats"]["count"] for screen in sequential["screens"]),
            "concurrent_completed": concurrent["completed"],
            "concurrent_failed": concurrent["failed"],
            "saturation_submitted": saturation["submitted"],
            "saturation_rejected_backpressure": saturation["rejected_backpressure"],
            "saturation_completed": saturation["completed"],
        },
        "verdicts": {
            "sequential_baseline_ok": sequential["all_succeeded"],
            "three_screen_concurrent_ok": concurrent["all_succeeded"],
            "saturation_bounded": saturation["bounded"],
            "saturation_all_terminal": saturation["all_terminal"],
            "rejections_retryable": saturation["all_rejections_retryable"],
            "recovery_after_saturation": saturation["recovery"]["verdict"],
        },
    }

    json_path = output_dir / "capacity-measurement.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path = output_dir / "capacity-measurement.md"
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    environment = report["environment"]
    limits = report["config_limits"]
    sequential = report["phases"]["sequential_baseline"]
    concurrent = report["phases"]["three_screen_concurrent"]
    saturation = report["phases"]["saturation"]
    verdicts = report["verdicts"]
    lines = [
        "# P2.3 Capacity Measurement (Deployment-Local Reference)",
        "",
        f"> {report['disclaimer']}",
        "",
        "## Environment",
        "",
        f"- OS/platform: {environment['platform']} ({environment['machine']})",
        f"- CPU count: {environment['cpu_count']}",
        f"- Python: {environment['python_version']} ({environment['python_executable']})",
        f"- Timestamp (UTC): {environment['timestamp_utc']}",
        "",
        "## Runtime Limits Under Measurement",
        "",
        f"- Global inflight limit: {limits['max_global_inflight']}",
        f"- Per-screen inflight limit: {limits['max_per_screen_inflight']}",
        f"- Executor workers: {limits['executor_workers']}",
        f"- Retained terminal jobs: {limits['max_retained_jobs']}",
        "",
        "## Sequential Baseline",
        "",
        "| Screen | Rounds | Median ms | p95 ms | Max ms | All Succeeded |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for screen in sequential["screens"]:
        stats = screen["stats"]
        lines.append(
            f"| {screen['screen_id']} | {stats['count']} | {stats['median_ms']} "
            f"| {stats['p95_ms']} | {stats['max_ms']} | {screen['all_succeeded']} |"
        )
    lines += [
        "",
        "## Three-Screen Concurrent",
        "",
        f"- Rounds: {concurrent['rounds']} (all three screens execute once per round)",
        f"- Completed: {concurrent['completed']}, failed: {concurrent['failed']}",
        (
            "- Throughput (completed/second, this machine only): "
            f"{concurrent['throughput_completed_per_second']}"
        ),
        "",
        "## Saturation And Recovery",
        "",
        (
            f"- Submitted simultaneously: {saturation['submitted']} "
            f"({saturation['submissions_per_screen']} per screen)"
        ),
        (
            f"- Admitted: {saturation['admitted']}, "
            f"rejected with retryable REJECTED_BACKPRESSURE: {saturation['rejected_backpressure']}"
        ),
        f"- All submissions reached a terminal state: {saturation['all_terminal']}",
        (
            "- Recovery after drain: "
            f"{saturation['recovery']['succeeded']}/{saturation['recovery']['attempted']} succeeded"
        ),
        "",
        "## Verdicts",
        "",
    ]
    lines += [f"- {name}: {value}" for name, value in verdicts.items()]
    lines += [
        "",
        (
            "These numbers describe this deployment-local reference run only. They "
            "must not be quoted as an SLA, a sizing promise or a certification of "
            "any other environment."
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "P2.3 deployment-local capacity measurement for the three-screen "
            "controlled-querying runtime. Not an SLA; not valid for other environments."
        )
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for the report files")
    parser.add_argument("--rounds", type=int, default=5, help="Rounds per phase (default: 5)")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup rounds per screen (default: 1)")
    args = parser.parse_args(argv)
    report = run_measurement(args.output_dir, rounds=args.rounds, warmup=args.warmup)
    saturation = report["phases"]["saturation"]
    concurrent = report["phases"]["three_screen_concurrent"]
    print(f"Wrote {args.output_dir / 'capacity-measurement.json'}")
    print(f"Wrote {args.output_dir / 'capacity-measurement.md'}")
    print(
        "Headline: concurrent throughput "
        f"{concurrent['throughput_completed_per_second']} completed/s; saturation "
        f"{saturation['submitted']} submitted, {saturation['rejected_backpressure']} rejected, "
        f"recovery {saturation['recovery']['succeeded']}/{saturation['recovery']['attempted']}."
    )
    print(DISCLAIMER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
