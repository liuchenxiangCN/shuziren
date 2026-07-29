from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_control_plane import ORIGIN, login, mutation_headers
from test_control_plane import control_plane as _shared_control_plane
from test_p2_1_capability_profiles import _enroll_device, _publish_and_ack
from test_p2_2_controlled_querying import (
    _create_excel_dataset,
    _create_excel_source,
    _create_query_release,
    _poll_execution,
    _publish_excel_runtime,
)

import app.control_plane.p2_1 as p2_1_module
import app.control_plane.p2_3 as p2_3_module
from app.control_plane.p2_2 import (
    EXECUTOR_WORKERS,
    MAX_GLOBAL_INFLIGHT,
    MAX_PER_SCREEN_INFLIGHT,
    MAX_RETAINED_JOBS,
    QueryExecutionFailure,
)
from app.control_plane.security import opaque_id
from app.control_plane.service import ControlPlaneService

TECHNICAL_SIGNALS = ("timeout", "unavailable", "unsupported")
TERMINAL_SIGNALS = (
    "permission_denied",
    "invalid_request",
    "unauthorized_template",
    "cancelled",
)
ALL_SIGNALS = (*TECHNICAL_SIGNALS, *TERMINAL_SIGNALS, "backpressure")
EXECUTION_ITEM_KEYS = {
    "execution_id",
    "dataset_id",
    "dataset_label",
    "state",
    "request_id",
    "latency_ms",
    "row_count",
    "result_retained",
    "error",
    "created_at",
    "terminal_at",
}


@pytest.fixture()
def p23_control_plane(tmp_path: Path) -> tuple[FastAPI, ControlPlaneService, Path]:
    return _shared_control_plane.__wrapped__(tmp_path)


def _screen_path(screen_id: str, suffix: str = "") -> str:
    return f"/api/v1/control-plane/screen-instances/{screen_id}{suffix}"


def _execution_path(screen_id: str, execution_id: str) -> str:
    return _screen_path(screen_id, f"/query-executions/{execution_id}")


def _create_screen(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        f"/api/v1/control-plane/sites/{site_id}/screen-instances",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p23-screen-create-{suffix}"},
        ),
        json={
            "slug": f"screen-{suffix}",
            "display_name": f"P2.3 screen {suffix}",
            "fvs_binding_ref": f"fvs-p23-{suffix}",
        },
    )
    assert created.status_code == 201, created.text
    screen = created.json()
    digital_human = client.post(
        _screen_path(screen["screen_id"], "/digital-human-instances"),
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p23-dh-create-{suffix}"},
        ),
        json={},
    )
    assert digital_human.status_code == 201, digital_human.text
    return screen


def _create_drill_profile(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
    tts: dict[str, Any],
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p23-profile-create-{suffix}"},
        ),
        json={
            "site_id": site_id,
            "name": f"P2.3 drill profile {suffix}",
            "description": "P2.3 resilience drill profile",
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
    spec["tts"] = tts
    versioned = client.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": f"p23-profile-version-{suffix}",
            },
        ),
        json={"spec": spec},
    )
    assert versioned.status_code == 201, versioned.text
    return versioned.json()


def _publish_drill_runtime(
    app: FastAPI,
    implementation: TestClient,
    csrf_impl: str,
    admin_a: TestClient,
    csrf_a: str,
    admin_b: TestClient,
    csrf_b: str,
    *,
    screen: dict[str, Any],
    suffix: str,
    tts: dict[str, Any],
) -> dict[str, Any]:
    source = _create_excel_source(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix=suffix,
    )
    dataset = _create_excel_dataset(
        implementation,
        csrf_impl,
        source_id=source["source_id"],
        suffix=suffix,
    )
    profile = _create_drill_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix=suffix,
        tts=tts,
    )
    release = _create_query_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screen["screen_id"],
        profile_version_id=profile["head_version_id"],
        dataset_version_ids=[dataset["dataset_version_id"]],
        suffix=suffix,
    )
    device, device_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screen["screen_id"],
        suffix=f"p23-{suffix}",
    )
    _publish_and_ack(
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        device,
        device_headers,
        screen_id=screen["screen_id"],
        release=release,
        suffix=f"p23-{suffix}",
    )
    return {
        "source": source,
        "dataset": dataset,
        "profile": profile,
        "release": release,
        "device": device,
        "device_headers": device_headers,
    }


def _start_execution(
    client: TestClient,
    csrf: str,
    *,
    screen_id: str,
    dataset_id: str,
    key: str,
    shift: str = "A",
) -> dict[str, Any]:
    response = client.post(
        _screen_path(screen_id, f"/query-datasets/{dataset_id}:execute"),
        headers=mutation_headers(csrf, **{"Idempotency-Key": key}),
        json={"parameters": {"shift": shift}},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _run_drill(
    client: TestClient,
    csrf: str,
    *,
    screen_id: str,
    capability: str,
    signal: str,
    key: str,
) -> dict[str, Any]:
    response = client.post(
        _screen_path(screen_id, "/resilience-drills"),
        headers=mutation_headers(csrf, **{"Idempotency-Key": key}),
        json={"capability": capability, "signal": signal},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_roleless_user(app: FastAPI, service: ControlPlaneService) -> TestClient:
    now = service.clock()
    with service.store.transaction() as connection:
        owner = connection.execute("SELECT tenant_id, deployment_id FROM users LIMIT 1").fetchone()
        connection.execute(
            """
            INSERT INTO users(
                user_id, tenant_id, deployment_id, normalized_username, display_name,
                account_state, password_verifier, credential_generation, created_at, updated_at
            ) VALUES (?, ?, ?, 'p23roleless', 'P2.3 Roleless', 'ACTIVE', ?, 1, ?, ?)
            """,
            (
                opaque_id("usr"),
                owner["tenant_id"],
                owner["deployment_id"],
                service.passwords.hash("P23-Roleless-Test!42", username="p23roleless"),
                now,
                now,
            ),
        )
    client = TestClient(app, base_url="https://manage.test")
    response = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": "p23roleless", "password": "P23-Roleless-Test!42"},
    )
    assert response.status_code == 200, response.text
    return client


def test_global_queue_saturation_across_four_screens_rejects_and_recovers(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    fourth = _create_screen(
        implementation,
        csrf_impl,
        site_id=screens[0]["site_id"],
        suffix="four",
    )
    screens = [*screens, fourth]
    runtimes = [
        _publish_excel_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"sat-{index}",
        )
        for index, screen in enumerate(screens)
    ]
    release_workers = threading.Event()

    def blocking_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        while not release_workers.wait(0.01):
            if job.cancel_event.is_set():
                raise QueryExecutionFailure(
                    "QUERY_CANCELLED",
                    "The query was cancelled",
                )
        return [
            {
                "business_date": "2026-07-28",
                "shift": "A",
                "output": 1,
                "quality_rate": 0.98,
            }
        ], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", blocking_excel)

    def start(index: int, key: str) -> dict[str, Any]:
        return _start_execution(
            implementation,
            csrf_impl,
            screen_id=screens[index]["screen_id"],
            dataset_id=runtimes[index]["dataset"]["dataset_id"],
            key=key,
        )

    accepted: list[tuple[int, dict[str, Any]]] = [
        (0, start(0, "p23-sat-s0-1")),
        (0, start(0, "p23-sat-s0-2")),
    ]
    per_screen = start(0, "p23-sat-s0-3")
    assert per_screen["state"] == "REJECTED_BACKPRESSURE"
    assert per_screen["error"]["code"] == "SCREEN_QUERY_BACKPRESSURE"
    assert per_screen["error"]["retryable"] is True
    for index in (1, 2):
        accepted.append((index, start(index, f"p23-sat-s{index}-1")))
        accepted.append((index, start(index, f"p23-sat-s{index}-2")))
    global_rejected = start(3, "p23-sat-s3-1")
    assert global_rejected["state"] == "REJECTED_BACKPRESSURE"
    assert global_rejected["error"]["code"] == "GLOBAL_QUERY_BACKPRESSURE"
    assert global_rejected["error"]["retryable"] is True

    status0 = implementation.get(_screen_path(screens[0]["screen_id"], "/queue-status"))
    assert status0.status_code == 200, status0.text
    assert status0.json()["screen"]["inflight"] == MAX_PER_SCREEN_INFLIGHT
    assert status0.json()["counters"]["rejected_backpressure"] == 1
    status3 = implementation.get(_screen_path(screens[3]["screen_id"], "/queue-status"))
    assert status3.json()["screen"]["inflight"] == 0
    assert status3.json()["counters"]["rejected_backpressure"] == 1

    release_workers.set()
    for index, started in accepted:
        result = _poll_execution(
            implementation,
            _execution_path(screens[index]["screen_id"], started["execution_id"]),
        )
        assert result["state"] == "SUCCEEDED"

    recovered = start(3, "p23-sat-s3-2")
    assert recovered["state"] == "QUEUED"
    recovered_result = _poll_execution(
        implementation,
        _execution_path(screens[3]["screen_id"], recovered["execution_id"]),
    )
    assert recovered_result["state"] == "SUCCEEDED"
    assert service.p2_2._screen_inflight == {}

    listed = implementation.get(_screen_path(screens[0]["screen_id"], "/query-executions"))
    assert listed.status_code == 200, listed.text
    rejected_item = next(item for item in listed.json()["items"] if item["state"] == "REJECTED_BACKPRESSURE")
    assert rejected_item["error"]["code"] == "SCREEN_QUERY_BACKPRESSURE"
    assert rejected_item["error"]["retryable"] is True
    assert rejected_item["terminal_at"] is not None


def test_executor_starvation_queued_cancel_recovers_workers(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    runtime = _publish_excel_runtime(
        app,
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        screen=screen,
        suffix="starve",
    )
    release = threading.Event()
    started = threading.Event()
    lock = threading.Lock()
    count = 0

    def blocker() -> None:
        nonlocal count
        with lock:
            count += 1
            if count == EXECUTOR_WORKERS:
                started.set()
        assert release.wait(5)

    futures = [service.p2_2._executor.submit(blocker) for _ in range(EXECUTOR_WORKERS)]
    assert started.wait(2)

    queued = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        dataset_id=runtime["dataset"]["dataset_id"],
        key="p23-starve-start",
    )
    assert queued["state"] == "QUEUED"
    time.sleep(0.2)
    current = implementation.get(_execution_path(screen["screen_id"], queued["execution_id"]))
    assert current.status_code == 200, current.text
    assert current.json()["state"] == "QUEUED"

    cancelled = implementation.post(
        _execution_path(screen["screen_id"], queued["execution_id"]) + ":cancel",
        headers=mutation_headers(csrf_impl, **{"Idempotency-Key": "p23-starve-cancel"}),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "CANCELLED"
    job = service.p2_2._jobs[queued["execution_id"]]
    assert job.future is not None and job.future.cancelled()
    assert job.slot_released is True
    assert service.p2_2._screen_inflight == {}

    release.set()
    for future in futures:
        future.result(timeout=2)
    recovered = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        dataset_id=runtime["dataset"]["dataset_id"],
        key="p23-starve-recover",
    )
    result = _poll_execution(
        implementation,
        _execution_path(screen["screen_id"], recovered["execution_id"]),
    )
    assert result["state"] == "SUCCEEDED"


def test_timeout_cancel_race_settles_single_terminal_state(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    runtime = _publish_excel_runtime(
        app,
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        screen=screen,
        suffix="race",
        timeout_ms=100,
    )

    def slow_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        job.cancel_event.wait(2)
        raise service.p2_2._cancellation_failure(job)

    monkeypatch.setattr(service.p2_2, "_execute_excel", slow_excel)
    states: list[str] = []
    for round_index in range(6):
        started_execution = _start_execution(
            implementation,
            csrf_impl,
            screen_id=screen["screen_id"],
            dataset_id=runtime["dataset"]["dataset_id"],
            key=f"p23-race-start-{round_index}",
        )
        if round_index % 2 == 1:
            time.sleep(0.25)
        cancelled = implementation.post(
            _execution_path(screen["screen_id"], started_execution["execution_id"]) + ":cancel",
            headers=mutation_headers(
                csrf_impl,
                **{"Idempotency-Key": f"p23-race-cancel-{round_index}"},
            ),
        )
        assert cancelled.status_code == 200, cancelled.text
        result = _poll_execution(
            implementation,
            _execution_path(screen["screen_id"], started_execution["execution_id"]),
        )
        assert result["state"] in {"TIMED_OUT", "CANCELLED"}
        expected_error = "QUERY_TIMED_OUT" if result["state"] == "TIMED_OUT" else "QUERY_CANCELLED"
        assert result["error"]["code"] == expected_error
        assert "rows" not in result
        assert "fallback" not in json.dumps(result).casefold()
        states.append(result["state"])
        time.sleep(0.2)
        settled = implementation.get(_execution_path(screen["screen_id"], started_execution["execution_id"]))
        assert settled.json()["state"] == result["state"]
    assert "TIMED_OUT" in states
    assert service.p2_2._screen_inflight == {}


def test_resilience_drill_decision_matrix(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    fallback_tts = {
        "enabled": True,
        "primary_provider_id": "mock_tts",
        "fallback_provider_ids": ["browser_text_fallback"],
        "timeout_ms": 5_000,
    }
    plain_tts = {
        "enabled": True,
        "primary_provider_id": "mock_tts",
        "fallback_provider_ids": [],
        "timeout_ms": 5_000,
    }
    profiles = (fallback_tts, plain_tts)
    suffixes = ("fallback", "plain")
    runtimes = {
        suffix: _publish_drill_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"matrix-{suffix}",
            tts=profile,
        )
        for suffix, profile, screen in zip(suffixes, profiles, screens[:2], strict=True)
    }
    fallback_screen = screens[0]["screen_id"]
    plain_screen = screens[1]["screen_id"]
    assert runtimes["fallback"]["profile"]["profile_id"] != runtimes["plain"]["profile"]["profile_id"]

    for signal in ALL_SIGNALS:
        drill = _run_drill(
            implementation,
            csrf_impl,
            screen_id=fallback_screen,
            capability="tts",
            signal=signal,
            key=f"p23-matrix-fallback-{signal}",
        )
        assert drill["latency_ms"] < 50
        assert drill["permission_equivalent"] is True
        assert drill["primary_provider_id"] == "mock_tts"
        assert drill["fallback_provider_ids"] == ["browser_text_fallback"]
        assert drill["provider_execution_started"] is (signal != "backpressure")
        assert drill["queue_admission"] == ("REJECTED" if signal == "backpressure" else "N/A")
        fetched = implementation.get(_screen_path(fallback_screen, f"/resilience-drills/{drill['drill_id']}"))
        assert fetched.status_code == 200, fetched.text
        assert fetched.json() == drill
        if signal in TERMINAL_SIGNALS:
            assert drill["outcome"] == "TERMINAL_NO_FALLBACK"
            assert drill["decision"] == "TERMINAL"
            assert drill["resolved_provider_id"] is None
            assert drill["terminal"] is True
            assert drill["fallback_allowed"] is False
        else:
            assert drill["outcome"] == "FALLBACK_RESOLVED"
            assert drill["decision"] == "FALLBACK_ALLOWED"
            assert drill["resolved_provider_id"] == "browser_text_fallback"
            assert drill["terminal"] is False
            assert drill["fallback_allowed"] is True

    for signal in ALL_SIGNALS:
        drill = _run_drill(
            implementation,
            csrf_impl,
            screen_id=plain_screen,
            capability="tts",
            signal=signal,
            key=f"p23-matrix-plain-{signal}",
        )
        assert drill["outcome"] == "NO_FALLBACK_CONFIGURED"
        assert drill["fallback_provider_ids"] == []
        assert drill["resolved_provider_id"] is None
        assert drill["terminal"] is True
        assert drill["fallback_allowed"] is False
        assert drill["provider_execution_started"] is (signal != "backpressure")
        expected_decision = "TERMINAL" if signal in TERMINAL_SIGNALS else "NOT_ALLOWED"
        assert drill["decision"] == expected_decision

    # Every registry Provider that is not activatable is also unverified and
    # blocks draft validation, so the not-activatable branch is driven through
    # an activatable-state override on the published fallback profile instead.
    monkeypatch.setattr(
        p2_1_module,
        "ACTIVATABLE_PROVIDER_STATES",
        {"available", "mock"},
    )
    not_activatable = _run_drill(
        implementation,
        csrf_impl,
        screen_id=fallback_screen,
        capability="tts",
        signal="timeout",
        key="p23-matrix-not-activatable-timeout",
    )
    assert not_activatable["outcome"] == "TERMINAL_NO_FALLBACK"
    assert not_activatable["decision"] == "FALLBACK_NOT_ACTIVATABLE"
    assert not_activatable["permission_equivalent"] is True
    assert not_activatable["terminal"] is True
    assert not_activatable["fallback_allowed"] is False
    monkeypatch.undo()

    disabled = _run_drill(
        implementation,
        csrf_impl,
        screen_id=plain_screen,
        capability="knowledge",
        signal="timeout",
        key="p23-matrix-disabled",
    )
    assert disabled["outcome"] == "CAPABILITY_DISABLED"
    assert disabled["provider_execution_started"] is False
    assert disabled["primary_provider_id"] is None
    assert disabled["resolved_provider_id"] is None
    assert disabled["terminal"] is True

    unpublished = _create_screen(
        implementation,
        csrf_impl,
        site_id=screens[0]["site_id"],
        suffix="unpublished",
    )
    unpublished_drill = _run_drill(
        implementation,
        csrf_impl,
        screen_id=unpublished["screen_id"],
        capability="tts",
        signal="timeout",
        key="p23-matrix-unpublished",
    )
    assert unpublished_drill["outcome"] == "CAPABILITY_DISABLED"
    assert unpublished_drill["provider_execution_started"] is False

    invalid_signal = implementation.post(
        _screen_path(plain_screen, "/resilience-drills"),
        headers=mutation_headers(csrf_impl, **{"Idempotency-Key": "p23-matrix-bad-signal"}),
        json={"capability": "tts", "signal": "explode"},
    )
    assert invalid_signal.status_code == 422
    invalid_capability = implementation.post(
        _screen_path(plain_screen, "/resilience-drills"),
        headers=mutation_headers(csrf_impl, **{"Idempotency-Key": "p23-matrix-bad-capability"}),
        json={"capability": "free_sql", "signal": "timeout"},
    )
    assert invalid_capability.status_code == 422


def test_resilience_drill_isolation_audit_and_idempotency(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    auditor, _ = login(app, "auditor")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:2]
    for index, screen in enumerate(screens):
        _publish_excel_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"hygiene-{index}",
        )
    screen_a = screens[0]["screen_id"]
    screen_b = screens[1]["screen_id"]

    drill = _run_drill(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        capability="tts",
        signal="timeout",
        key="p23-hygiene-drill",
    )
    cross_screen = implementation.get(_screen_path(screen_b, f"/resilience-drills/{drill['drill_id']}"))
    assert cross_screen.status_code == 404
    own = implementation.get(_screen_path(screen_a, f"/resilience-drills/{drill['drill_id']}"))
    assert own.status_code == 200, own.text
    assert own.json() == drill
    payload = json.dumps(drill).casefold()
    for forbidden in ("password", "secret", "token", "dsn", "select ", "credential"):
        assert forbidden not in payload

    replay = _run_drill(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        capability="tts",
        signal="timeout",
        key="p23-hygiene-drill",
    )
    assert replay == drill
    conflicting = implementation.post(
        _screen_path(screen_a, "/resilience-drills"),
        headers=mutation_headers(csrf_impl, **{"Idempotency-Key": "p23-hygiene-drill"}),
        json={"capability": "tts", "signal": "cancelled"},
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    audit = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit.status_code == 200, audit.text
    drill_events = [
        item
        for item in audit.json()["items"]
        if item["event_type"] == "RESILIENCE_DRILL_RUN" and item["target_id"] == drill["drill_id"]
    ]
    assert len(drill_events) == 1
    event_payload = json.dumps(drill_events[0]).casefold()
    assert drill["drill_id"] in event_payload
    for forbidden in ("password", "secret", "token", "dsn", "credential"):
        assert forbidden not in event_payload

    monkeypatch.setattr(p2_3_module, "MAX_RETAINED_DRILLS", 2)
    evicted = drill
    for index in range(2):
        drill = _run_drill(
            implementation,
            csrf_impl,
            screen_id=screen_a,
            capability="tts",
            signal="unavailable",
            key=f"p23-hygiene-evict-{index}",
        )
    gone = implementation.get(_screen_path(screen_a, f"/resilience-drills/{evicted['drill_id']}"))
    assert gone.status_code == 404
    retained = implementation.get(_screen_path(screen_a, f"/resilience-drills/{drill['drill_id']}"))
    assert retained.status_code == 200, retained.text


def test_screen_executions_list_is_metadata_only_and_screen_scoped(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:2]
    runtimes = [
        _publish_excel_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"list-{index}",
        )
        for index, screen in enumerate(screens)
    ]
    release_workers = threading.Event()

    def blocking_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        while not release_workers.wait(0.01):
            if job.cancel_event.is_set():
                raise QueryExecutionFailure(
                    "QUERY_CANCELLED",
                    "The query was cancelled",
                )
        return [], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", blocking_excel)
    screen_a = screens[0]["screen_id"]
    screen_b = screens[1]["screen_id"]
    marker = "p23-marker-value"
    succeeded = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        dataset_id=runtimes[0]["dataset"]["dataset_id"],
        key="p23-list-succeeded",
        shift=marker,
    )
    cancelled_start = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        dataset_id=runtimes[0]["dataset"]["dataset_id"],
        key="p23-list-cancelled",
    )
    cancelled = implementation.post(
        _execution_path(screen_a, cancelled_start["execution_id"]) + ":cancel",
        headers=mutation_headers(csrf_impl, **{"Idempotency-Key": "p23-list-cancel"}),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "CANCELLED"
    other = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_b,
        dataset_id=runtimes[1]["dataset"]["dataset_id"],
        key="p23-list-other",
    )
    release_workers.set()
    for screen_id, started in ((screen_a, succeeded), (screen_b, other)):
        result = _poll_execution(implementation, _execution_path(screen_id, started["execution_id"]))
        assert result["state"] == "SUCCEEDED"

    listed = implementation.get(_screen_path(screen_a, "/query-executions"))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["screen_instance_id"] == screen_a
    items = payload["items"]
    assert len(items) == 2
    assert [item["execution_id"] for item in items] == [
        cancelled_start["execution_id"],
        succeeded["execution_id"],
    ]
    assert other["execution_id"] not in {item["execution_id"] for item in items}
    for item in items:
        assert set(item) == EXECUTION_ITEM_KEYS
        assert item["dataset_label"] == runtimes[0]["dataset"]["display_name"]
    assert marker not in json.dumps(payload)
    assert "rows" not in json.dumps(payload)
    succeeded_item = next(item for item in items if item["execution_id"] == succeeded["execution_id"])
    assert succeeded_item["state"] == "SUCCEEDED"
    assert succeeded_item["error"] is None
    assert succeeded_item["result_retained"] is True
    assert succeeded_item["row_count"] == 0
    assert succeeded_item["terminal_at"] is not None
    cancelled_item = next(item for item in items if item["execution_id"] == cancelled_start["execution_id"])
    assert cancelled_item["state"] == "CANCELLED"
    assert cancelled_item["error"]["code"] == "QUERY_CANCELLED"
    assert cancelled_item["error"]["retryable"] is False

    limited = implementation.get(_screen_path(screen_a, "/query-executions?limit=1"))
    assert limited.status_code == 200, limited.text
    assert len(limited.json()["items"]) == 1
    assert limited.json()["items"][0]["execution_id"] == cancelled_start["execution_id"]
    for bound in ("0", "101"):
        rejected = implementation.get(_screen_path(screen_a, f"/query-executions?limit={bound}"))
        assert rejected.status_code == 422

    other_listed = implementation.get(_screen_path(screen_b, "/query-executions"))
    assert {item["execution_id"] for item in other_listed.json()["items"]} == {other["execution_id"]}
    missing_screen = implementation.get(_screen_path("screen-missing", "/query-executions"))
    assert missing_screen.status_code == 404
    cross_execution = implementation.get(_execution_path(screen_b, succeeded["execution_id"]))
    assert cross_execution.status_code == 404

    roleless = _create_roleless_user(app, service)
    denied = roleless.get(_screen_path(screen_a, "/query-executions"))
    assert denied.status_code == 404
    unauthenticated = TestClient(app, base_url="https://manage.test")
    anonymous = unauthenticated.get(_screen_path(screen_a, "/query-executions"))
    assert anonymous.status_code == 401


def test_screen_queue_status_shape_and_isolation(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:2]
    runtimes = [
        _publish_excel_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"status-{index}",
        )
        for index, screen in enumerate(screens)
    ]
    release_workers = threading.Event()

    def blocking_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        while not release_workers.wait(0.01):
            if job.cancel_event.is_set():
                raise QueryExecutionFailure(
                    "QUERY_CANCELLED",
                    "The query was cancelled",
                )
        return [], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", blocking_excel)
    screen_a = screens[0]["screen_id"]
    screen_b = screens[1]["screen_id"]
    first = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        dataset_id=runtimes[0]["dataset"]["dataset_id"],
        key="p23-status-first",
    )
    second = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        dataset_id=runtimes[0]["dataset"]["dataset_id"],
        key="p23-status-second",
    )
    rejected = _start_execution(
        implementation,
        csrf_impl,
        screen_id=screen_a,
        dataset_id=runtimes[0]["dataset"]["dataset_id"],
        key="p23-status-rejected",
    )
    assert rejected["state"] == "REJECTED_BACKPRESSURE"

    status = implementation.get(_screen_path(screen_a, "/queue-status"))
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload == {
        "api_version": "v1",
        "screen_instance_id": screen_a,
        "screen": {
            "inflight": 2,
            "per_screen_limit": MAX_PER_SCREEN_INFLIGHT,
        },
        "capacity": {
            "global_inflight_limit": MAX_GLOBAL_INFLIGHT,
            "per_screen_inflight_limit": MAX_PER_SCREEN_INFLIGHT,
            "executor_workers": EXECUTOR_WORKERS,
            "retained_terminal_jobs": MAX_RETAINED_JOBS,
        },
        "counters": {"rejected_backpressure": 1},
    }
    assert screen_b not in json.dumps(payload)
    assert '"global_inflight":' not in json.dumps(payload)

    sibling = implementation.get(_screen_path(screen_b, "/queue-status"))
    assert sibling.status_code == 200, sibling.text
    assert sibling.json()["screen"]["inflight"] == 0
    assert sibling.json()["counters"]["rejected_backpressure"] == 0
    assert screen_a not in json.dumps(sibling.json())

    release_workers.set()
    for started in (first, second):
        result = _poll_execution(
            implementation,
            _execution_path(screen_a, started["execution_id"]),
        )
        assert result["state"] == "SUCCEEDED"
    drained = implementation.get(_screen_path(screen_a, "/queue-status"))
    assert drained.json()["screen"]["inflight"] == 0

    missing = implementation.get(_screen_path("screen-missing", "/queue-status"))
    assert missing.status_code == 404
    roleless = _create_roleless_user(app, service)
    denied = roleless.get(_screen_path(screen_a, "/queue-status"))
    assert denied.status_code == 404


def test_three_screens_distinct_profiles_mixed_load_and_failure_isolation(
    p23_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p23_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:3]
    tts_profiles = (
        {
            "enabled": True,
            "primary_provider_id": "mock_tts",
            "fallback_provider_ids": ["browser_text_fallback"],
            "timeout_ms": 5_000,
        },
        {
            "enabled": True,
            "primary_provider_id": "mock_tts",
            "fallback_provider_ids": [],
            "timeout_ms": 5_000,
        },
        {
            "enabled": False,
            "primary_provider_id": None,
            "fallback_provider_ids": [],
            "timeout_ms": 5_000,
        },
    )
    runtimes = [
        _publish_drill_runtime(
            app,
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            admin_b,
            csrf_b,
            screen=screen,
            suffix=f"mix-{index}",
            tts=tts_profiles[index],
        )
        for index, screen in enumerate(screens)
    ]
    barrier = threading.Barrier(3, timeout=3)
    source_index = {runtime["source"]["source_id"]: index for index, runtime in enumerate(runtimes)}

    def isolated_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del job, parameters
        index = source_index[dataset_row["source_id"]]
        barrier.wait()
        if index == 1:
            raise QueryExecutionFailure(
                "QUERY_SOURCE_UNAVAILABLE",
                "The source failed safely",
            )
        return [
            {
                "business_date": "2026-07-28",
                "shift": "A",
                "output": 100 + index,
                "quality_rate": 0.98,
            }
        ], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", isolated_excel)
    starts = [
        _start_execution(
            implementation,
            csrf_impl,
            screen_id=screens[index]["screen_id"],
            dataset_id=runtimes[index]["dataset"]["dataset_id"],
            key=f"p23-mix-start-{index}",
        )
        for index in range(3)
    ]
    assert len({item["request_id"] for item in starts}) == 3

    drill = _run_drill(
        implementation,
        csrf_impl,
        screen_id=screens[2]["screen_id"],
        capability="tts",
        signal="timeout",
        key="p23-mix-drill",
    )
    assert drill["outcome"] == "CAPABILITY_DISABLED"

    results = [
        _poll_execution(
            implementation,
            _execution_path(screens[index]["screen_id"], starts[index]["execution_id"]),
        )
        for index in range(3)
    ]
    assert [result["state"] for result in results] == [
        "SUCCEEDED",
        "FAILED",
        "SUCCEEDED",
    ]
    assert results[1]["error"]["code"] == "QUERY_SOURCE_UNAVAILABLE"
    assert results[1]["error"]["retryable"] is True
    assert results[0]["rows"][0]["output"] == 100
    assert results[2]["rows"][0]["output"] == 102
    assert all("fallback" not in json.dumps(result).casefold() for result in results)

    for index in range(3):
        listed = implementation.get(_screen_path(screens[index]["screen_id"], "/query-executions"))
        assert listed.status_code == 200, listed.text
        execution_ids = {item["execution_id"] for item in listed.json()["items"]}
        assert starts[index]["execution_id"] in execution_ids
        for other in range(3):
            if other != index:
                assert starts[other]["execution_id"] not in execution_ids
