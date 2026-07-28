from __future__ import annotations

import base64
import io
import json
import sqlite3
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Self

import pytest
from cryptography.exceptions import InvalidTag
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from test_control_plane import (
    approve_action,
    login,
    mutation_headers,
    request_action,
)
from test_control_plane import control_plane as _shared_control_plane
from test_p2_1_capability_profiles import _enroll_device, _publish_and_ack

from app.control_plane import store as store_module
from app.control_plane.p2_2 import QueryExecutionFailure
from app.control_plane.security import Ciphertext, PurposeKeyring
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import MIGRATION_004_VERSION


@pytest.fixture()
def p22_control_plane(tmp_path: Path) -> tuple[FastAPI, ControlPlaneService, Path]:
    return _shared_control_plane.__wrapped__(tmp_path)


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


def _formula_workbook_base64() -> str:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Metrics"
    worksheet.append(["shift", "output"])
    worksheet.append(["A", "=1+1"])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return base64.b64encode(output.getvalue()).decode("ascii")


def _workbook_with_archive_entry_base64(name: str) -> str:
    output = io.BytesIO(base64.b64decode(_workbook_base64()))
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, b"forbidden")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _workbook_with_external_hyperlink_base64() -> str:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Metrics"
    worksheet.append(["business_date", "shift", "output", "quality_rate"])
    worksheet.append(["2026-07-28", "A", 120, 0.98])
    worksheet["A2"].hyperlink = "https://example.invalid/external"
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return base64.b64encode(output.getvalue()).decode("ascii")


def _create_excel_source(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p22-source-create-{suffix}"},
        ),
        json={
            "site_id": site_id,
            "display_name": f"Reference workbook {suffix}",
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
        headers=mutation_headers(
            csrf,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": f"p22-source-test-{suffix}",
            },
        ),
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["qualification_state"] == "AVAILABLE"
    fetched = client.get(f"/api/v1/control-plane/query-sources/{source['source_id']}")
    assert fetched.status_code == 200, fetched.text
    source = fetched.json()
    listed = client.get("/api/v1/control-plane/query-sources")
    assert listed.status_code == 200, listed.text
    assert source in listed.json()["items"]
    return source


def _create_excel_dataset(
    client: TestClient,
    csrf: str,
    *,
    source_id: str,
    suffix: str,
    timeout_ms: int = 5_000,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-datasets",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p22-dataset-create-{suffix}"},
        ),
        json={
            "source_id": source_id,
            "display_name": f"Shift output {suffix}",
            "metric_definition": "Finished units by business date and shift",
            "time_scope_description": "Rows in the approved reference workbook",
            "freshness_label": "Reference fixture generated for P2.2",
            "parameters": [
                {"name": "shift", "type": "string", "required": True},
            ],
            "output_fields": [
                "business_date",
                "shift",
                "output",
                "quality_rate",
            ],
            "definition": {
                "worksheet": "Metrics",
                "parameter_columns": {"shift": "shift"},
            },
            "row_limit": 20,
            "timeout_ms": timeout_ms,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _create_controlled_query_profile(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p22-profile-create-{suffix}"},
        ),
        json={
            "site_id": site_id,
            "name": f"Controlled query {suffix}",
            "description": "P2.2 controlled-query profile",
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
        headers=mutation_headers(
            csrf,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": f"p22-profile-version-{suffix}",
            },
        ),
        json={"spec": spec},
    )
    assert versioned.status_code == 201, versioned.text
    result = versioned.json()
    assert result["head_version"]["activation_eligible"] is False
    return result


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
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": f"p22-draft-create-{suffix}"},
        ),
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
        headers=mutation_headers(csrf_impl, **{"If-Match": draft["etag"]}),
        json={
            "welcome_text": f"P2.2 controlled query {suffix}",
            "fvs_binding_ref": f"https://fvs.example.test/p2-2/{suffix}",
        },
    )
    assert replaced.status_code == 200, replaced.text
    draft = replaced.json()
    assigned_profile = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/capability-profile",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-profile-assign-{suffix}",
            },
        ),
        json={"profile_version_id": profile_version_id},
    )
    assert assigned_profile.status_code == 200, assigned_profile.text
    draft = assigned_profile.json()
    assigned_query = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/query-datasets",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-query-assign-{suffix}",
            },
        ),
        json={"dataset_version_ids": dataset_version_ids},
    )
    assert assigned_query.status_code == 200, assigned_query.text
    draft = assigned_query.json()
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-validate-{suffix}",
            },
        ),
    )
    assert validated.status_code == 200, validated.text
    draft = validated.json()
    assert draft["validation"]["outcome"] == "VALID"
    assert any(
        finding["code"] == "P2_2_QUERY_SIDECAR_QUALIFIED" for finding in draft["validation"]["findings"]
    )
    previewed = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-preview-{suffix}",
            },
        ),
    )
    assert previewed.status_code == 200, previewed.text
    draft = previewed.json()
    assert draft["preview"]["evidence"]["controlled_querying"]["real_query_execution_made"] is False
    submitted = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:submit-for-approval",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-submit-{suffix}",
            },
        ),
    )
    assert submitted.status_code == 200, submitted.text
    draft = submitted.json()
    approved = approver.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_approver,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-approve-{suffix}",
            },
        ),
        json={"reason": "independent P2.2 approval"},
    )
    assert approved.status_code == 200, approved.text
    draft = approved.json()
    released = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:release",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p22-release-{suffix}",
            },
        ),
        json={"reason": "create immutable P2.2 release"},
    )
    assert released.status_code == 201, released.text
    release = released.json()
    assert release["targets"][0]["query_snapshot"]["querying_enabled"] is True
    return release


def _publish_excel_runtime(
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
    timeout_ms: int = 5_000,
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
        timeout_ms=timeout_ms,
    )
    profile = _create_controlled_query_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix=suffix,
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
        suffix=f"p22-{suffix}",
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
        suffix=f"p22-{suffix}",
    )
    return {
        "source": source,
        "dataset": dataset,
        "profile": profile,
        "release": release,
        "device": device,
        "device_headers": device_headers,
    }


def _poll_execution(
    client: TestClient,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    for _ in range(100):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["state"] not in {"QUEUED", "RUNNING"}:
            return result
        time.sleep(0.01)
    raise AssertionError("Controlled query did not reach a terminal state")


def test_excel_release_user_and_device_execution_are_screen_bound_and_closed(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    auditor, _ = login(app, "auditor")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    screen = screens[0]
    other_screen = screens[1]
    source = _create_excel_source(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix="e2e",
    )
    assert source["credential"]["configured"] is False
    assert source["workbook"] == {
        "configured": True,
        "content_readable": False,
    }
    dataset = _create_excel_dataset(
        implementation,
        csrf_impl,
        source_id=source["source_id"],
        suffix="e2e",
    )
    assert dataset["definition"]["query_template_readable"] is False
    profile = _create_controlled_query_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix="e2e",
    )
    release = _create_query_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screen["screen_id"],
        profile_version_id=profile["head_version_id"],
        dataset_version_ids=[dataset["dataset_version_id"]],
        suffix="e2e",
    )
    device, device_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screen["screen_id"],
        suffix="p22-e2e",
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
        suffix="p22-e2e",
    )

    user_catalog = implementation.get(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/query-datasets"
    )
    assert user_catalog.status_code == 200, user_catalog.text
    assert [item["dataset_id"] for item in user_catalog.json()["items"]] == [dataset["dataset_id"]]
    device_catalog = device.get(
        "/api/v1/device/query-datasets",
        headers=device_headers,
    )
    assert device_catalog.status_code == 200, device_catalog.text
    assert device_catalog.json()["items"] == user_catalog.json()["items"]
    assert "query_template" not in json.dumps(device_catalog.json())

    started = implementation.post(
        (
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}"
            f"/query-datasets/{dataset['dataset_id']}:execute"
        ),
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p22-user-query-e2e"},
        ),
        json={"parameters": {"shift": "A"}},
    )
    assert started.status_code == 202, started.text
    user_result = _poll_execution(
        implementation,
        (
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}"
            f"/query-executions/{started.json()['execution_id']}"
        ),
    )
    assert user_result["state"] == "SUCCEEDED"
    assert user_result["fields"] == [
        "business_date",
        "shift",
        "output",
        "quality_rate",
    ]
    assert user_result["row_count"] == 2
    assert {row["output"] for row in user_result["rows"]} == {110, 120}
    assert user_result["permission_subject"]["screen_id"] == screen["screen_id"]

    cross_screen = implementation.get(
        f"/api/v1/control-plane/screen-instances/{other_screen['screen_id']}"
        f"/query-executions/{started.json()['execution_id']}"
    )
    assert cross_screen.status_code == 404
    assert cross_screen.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    injection = device.post(
        f"/api/v1/device/query-datasets/{dataset['dataset_id']}:execute",
        headers={
            **device_headers,
            "Idempotency-Key": "p22-device-query-injection",
        },
        json={"parameters": {"shift": "A' OR '1'='1"}},
    )
    assert injection.status_code == 202, injection.text
    injection_result = _poll_execution(
        device,
        f"/api/v1/device/query-executions/{injection.json()['execution_id']}",
        headers=device_headers,
    )
    assert injection_result["state"] == "SUCCEEDED"
    assert injection_result["row_count"] == 0
    assert injection_result["rows"] == []

    runtime_sql = device.post(
        f"/api/v1/device/query-datasets/{dataset['dataset_id']}:execute",
        headers={
            **device_headers,
            "Idempotency-Key": "p22-device-query-sql-field",
        },
        json={
            "parameters": {"shift": "A"},
            "query_template": "SELECT * FROM forbidden",
        },
    )
    assert runtime_sql.status_code == 422
    assert runtime_sql.json()["error"]["code"] == "VALIDATION_ERROR"

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT parameter_names_json, parameter_digest, state
            FROM query_executions WHERE execution_id = ?
            """,
            (started.json()["execution_id"],),
        ).fetchone()
        assert row[0] == '["shift"]'
        assert len(row[1]) == 64
        assert row[2] == "SUCCEEDED"
        stored_workbook = connection.execute(
            """
            SELECT workbook_content FROM query_source_versions
            WHERE source_version_id = ?
            """,
            (source["source_version_id"],),
        ).fetchone()[0]
        assert stored_workbook
    audit = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit.status_code == 200, audit.text
    audit_text = audit.text
    assert "A' OR '1'='1" not in audit_text
    assert "SELECT * FROM forbidden" not in audit_text
    service.p2_2._executor.shutdown(wait=True)


@pytest.mark.parametrize(
    ("engine", "query_template"),
    (
        ("POSTGRESQL", "SELECT * FROM approved_metrics; DELETE FROM approved_metrics"),
        ("POSTGRESQL", "SELECT * FROM approved_metrics -- comment"),
        ("POSTGRESQL", "INSERT INTO approved_metrics(value) VALUES (1)"),
        ("POSTGRESQL", "UPDATE approved_metrics SET value = 1"),
        ("POSTGRESQL", "DELETE FROM approved_metrics"),
        ("POSTGRESQL", "DROP TABLE approved_metrics"),
        ("POSTGRESQL", "CALL refresh_metrics()"),
        ("POSTGRESQL", "EXECUTE unsafe_plan"),
        (
            "POSTGRESQL",
            "SELECT shift, output FROM unapproved_metrics WHERE shift = :shift",
        ),
        (
            "POSTGRESQL",
            "SELECT shift, output FROM approved_metrics WHERE shift = :undeclared",
        ),
        (
            "POSTGRESQL",
            "SELECT pg_read_file('/etc/passwd') AS output FROM approved_metrics",
        ),
        ("MYSQL", "SELECT LOAD_FILE('/etc/passwd') AS output FROM approved_metrics"),
        (
            "ORACLE",
            "SELECT UTL_HTTP.REQUEST('https://example.invalid') AS output FROM approved_metrics",
        ),
        (
            "POSTGRESQL",
            "SELECT shift, output FROM approved_metrics WHERE shift = :shift FOR UPDATE",
        ),
        (
            "MYSQL",
            "SELECT shift, output FROM approved_metrics # comment\nWHERE shift = :shift",
        ),
        (
            "MYSQL",
            "SELECT @p22_probe := output AS output, shift FROM approved_metrics WHERE shift = :shift",
        ),
        (
            "ORACLE",
            "SELECT shift, myseq.NEXTVAL AS output FROM approved_metrics WHERE shift = :shift",
        ),
        (
            "ORACLE",
            "SELECT shift, myseq.CURRVAL AS output FROM approved_metrics WHERE shift = :shift",
        ),
        (
            "POSTGRESQL",
            "SELECT shift, (:shift OPERATOR(public.##) shift) AS output FROM approved_metrics",
        ),
        (
            "POSTGRESQL",
            "SELECT shift, CAST(:shift AS public.evil_type) AS output FROM approved_metrics",
        ),
        (
            "ORACLE",
            "SELECT shift, CAST(:shift AS MY_OBJECT_TYPE) AS output FROM approved_metrics",
        ),
    ),
)
def test_database_dataset_sql_contract_fails_closed(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    engine: str,
    query_template: str,
) -> None:
    app, _, _ = p22_control_plane
    administrator, csrf_admin = login(app, "admin-a")
    site_id = administrator.get("/api/v1/control-plane/screen-instances").json()["items"][0]["site_id"]
    password = "Never-Return-This-P2.2-Password!"
    source_response = administrator.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": "p22-db-source-sql-negative"},
        ),
        json={
            "site_id": site_id,
            "display_name": f"Unverified {engine} reference",
            "engine": engine,
            "read_only_account_confirmed": True,
            "connection": {
                "host": "127.0.0.1",
                "port": 1,
                "database": "reference",
                "username": "readonly",
                "password": password,
            },
        },
    )
    assert source_response.status_code == 201, source_response.text
    assert password not in source_response.text
    assert "127.0.0.1" not in source_response.text
    source = source_response.json()
    created = administrator.post(
        "/api/v1/control-plane/query-datasets",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": ("p22-sql-negative-" + str(abs(hash(query_template))))},
        ),
        json={
            "source_id": source["source_id"],
            "display_name": "Rejected SQL contract",
            "metric_definition": "Rejected metric definition",
            "time_scope_description": "Rejected time scope",
            "freshness_label": "Unverified reference",
            "parameters": [{"name": "shift", "type": "string", "required": True}],
            "output_fields": ["shift", "output"],
            "definition": {
                "query_template": query_template,
                "allowed_relations": ["approved_metrics"],
            },
            "row_limit": 20,
            "timeout_ms": 5_000,
        },
    )
    assert created.status_code == 422, created.text
    assert created.json()["error"]["code"] in {
        "OUTPUT_FIELD_ALLOWLIST_REQUIRED",
        "PARAMETER_BINDING_MISMATCH",
        "READ_ONLY_TEMPLATE_REQUIRED",
        "RELATION_NOT_ALLOWLISTED",
        "SQL_TEMPLATE_INVALID",
    }
    assert password not in created.text


def test_database_secret_is_encrypted_write_only_and_source_test_is_sanitized(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = p22_control_plane
    administrator, csrf_admin = login(app, "admin-a")
    site_id = administrator.get("/api/v1/control-plane/screen-instances").json()["items"][0]["site_id"]
    password = "P2.2-Secret-Plaintext-Must-Not-Exist!"
    payload = {
        "site_id": site_id,
        "display_name": "Unavailable MySQL reference",
        "engine": "MYSQL",
        "read_only_account_confirmed": True,
        "connection": {
            "host": "127.0.0.1",
            "port": 1,
            "database": "reference",
            "username": "readonly",
            "password": password,
        },
    }
    created = administrator.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": "p22-secret-source-create"},
        ),
        json=payload,
    )
    assert created.status_code == 201, created.text
    source = created.json()
    replay = administrator.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": "p22-secret-source-create"},
        ),
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.json() == source
    changed = administrator.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": "p22-secret-source-create"},
        ),
        json={
            **payload,
            "connection": {
                **payload["connection"],
                "password": "different-secret",
            },
        },
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    tested = administrator.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_admin,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p22-secret-source-test",
            },
        ),
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["qualification_state"] == "FAILED"
    assert tested.json()["code"] == "QUERY_SOURCE_UNAVAILABLE"
    visible = administrator.get(f"/api/v1/control-plane/query-sources/{source['source_id']}")
    assert visible.status_code == 200
    assert visible.json()["credential"]["configured"] is True
    combined = created.text + replay.text + changed.text + tested.text + visible.text
    assert password not in combined
    assert "127.0.0.1" not in combined
    assert "readonly" not in combined

    raw = database_path.read_bytes()
    assert password.encode("utf-8") not in raw
    with sqlite3.connect(database_path) as connection:
        secret = connection.execute(
            """
            SELECT envelope_nonce, envelope_ciphertext, envelope_aad_json,
                   envelope_aad_hash, fingerprint_suffix
            FROM query_secret_versions
            """
        ).fetchone()
        assert secret is not None
        assert secret[0] and secret[1]
        assert password not in secret[2]
        assert len(secret[3]) == 64
        assert len(secret[4]) == 12
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE query_secret_versions SET envelope_ciphertext = X'00'
                """
            )


def test_excel_registration_rejects_formula_active_content_and_paths(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    site_id = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]["site_id"]
    cases = (
        ("formula", "reference.xlsx", _formula_workbook_base64(), "WORKBOOK_FORMULA_FORBIDDEN"),
        (
            "macro",
            "reference.xlsx",
            _workbook_with_archive_entry_base64("xl/vbaProject.bin"),
            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
        ),
        (
            "external",
            "reference.xlsx",
            _workbook_with_archive_entry_base64("xl/externalLinks/externalLink1.xml"),
            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
        ),
        (
            "external-hyperlink",
            "reference.xlsx",
            _workbook_with_external_hyperlink_base64(),
            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
        ),
        (
            "activex",
            "reference.xlsx",
            _workbook_with_archive_entry_base64("xl/activeX/activeX1.bin"),
            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
        ),
        (
            "traversal-entry",
            "reference.xlsx",
            _workbook_with_archive_entry_base64("../escape.bin"),
            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
        ),
        ("path", "../reference.xlsx", _workbook_base64(), "WORKBOOK_TYPE_FORBIDDEN"),
        ("extension", "reference.xls", _workbook_base64(), "WORKBOOK_TYPE_FORBIDDEN"),
        ("base64", "reference.xlsx", "not-valid-base64", "WORKBOOK_INVALID"),
    )
    for suffix, file_name, workbook_base64, expected_code in cases:
        response = implementation.post(
            "/api/v1/control-plane/query-sources",
            headers=mutation_headers(
                csrf_impl,
                **{"Idempotency-Key": f"p22-workbook-negative-{suffix}"},
            ),
            json={
                "site_id": site_id,
                "display_name": f"Rejected workbook {suffix}",
                "engine": "EXCEL",
                "read_only_account_confirmed": True,
                "excel_file_name": file_name,
                "excel_workbook_base64": workbook_base64,
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == expected_code


def test_encrypted_backup_restore_preserves_current_query_authority(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    site_id = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]["site_id"]
    source = _create_excel_source(
        implementation,
        csrf_impl,
        site_id=site_id,
        suffix="backup",
    )
    database_password = "P2.2-Backup-Secret-Plaintext-Sentinel!"
    database_source_response = admin_a.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-backup-db-source"},
        ),
        json={
            "site_id": site_id,
            "display_name": "Backup PostgreSQL Secret",
            "engine": "POSTGRESQL",
            "read_only_account_confirmed": True,
            "connection": {
                "host": "127.0.0.1",
                "port": 5432,
                "database": "reference",
                "username": "readonly",
                "password": database_password,
            },
        },
    )
    assert database_source_response.status_code == 201, database_source_response.text
    database_source = database_source_response.json()
    dataset = _create_excel_dataset(
        implementation,
        csrf_impl,
        source_id=source["source_id"],
        suffix="backup",
    )

    created = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-backup-create"},
        ),
        json={"reason": "preserve P2.2 controlled-query sidecars"},
    )
    assert created.status_code == 201, created.text
    backup = created.json()
    for table in (
        "query_sources",
        "query_source_versions",
    ):
        assert backup["safe_row_counts"][table] == 2
    for table in ("query_datasets", "query_dataset_versions", "query_secret_records"):
        assert backup["safe_row_counts"][table] == 1
    verified = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-backup-verify"},
        ),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["outcome"] == "VERIFIED"
    with service.store.connect() as connection:
        secret = connection.execute(
            """
            SELECT qsv.secret_version_id, qsv.envelope_nonce, qsv.envelope_ciphertext,
                   qsv.envelope_aad_json
            FROM query_source_versions sv
            JOIN query_secret_versions qsv
              ON qsv.secret_version_id = sv.secret_version_id
            WHERE sv.source_id = ?
            """,
            (database_source["source_id"],),
        ).fetchone()
        bundle_name = connection.execute(
            "SELECT bundle_name FROM backup_records WHERE backup_id = ?",
            (backup["backup_id"],),
        ).fetchone()["bundle_name"]
    ciphertext = Ciphertext(nonce=secret["envelope_nonce"], value=secret["envelope_ciphertext"])
    with pytest.raises(InvalidTag):
        service.keys.decrypt_for(
            "SECRET_ENVELOPE_ENCRYPTION",
            ciphertext,
            b'{"wrong":"aad"}',
        )
    wrong_keys = PurposeKeyring.from_base64(PurposeKeyring.generate_root_base64())
    with pytest.raises(InvalidTag):
        wrong_keys.decrypt_for(
            "SECRET_ENVELOPE_ENCRYPTION",
            ciphertext,
            secret["envelope_aad_json"].encode("utf-8"),
        )
    bundle_path = service.p1_3.backups.backup_root / bundle_name
    assert bundle_path.is_dir()
    assert all(
        database_password.encode("utf-8") not in path.read_bytes()
        for path in bundle_path.rglob("*")
        if path.is_file()
    )

    disabled_dataset = implementation.post(
        f"/api/v1/control-plane/query-datasets/{dataset['dataset_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": dataset["etag"],
                "Idempotency-Key": "p22-disable-dataset-after-backup",
            },
        ),
    )
    assert disabled_dataset.status_code == 200, disabled_dataset.text
    disabled_source = implementation.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p22-disable-source-after-backup",
            },
        ),
    )
    assert disabled_source.status_code == 200, disabled_source.text
    disabled_database_source = implementation.post(
        f"/api/v1/control-plane/query-sources/{database_source['source_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": database_source["etag"],
                "Idempotency-Key": "p22-disable-db-source-after-backup",
            },
        ),
    )
    assert disabled_database_source.status_code == 200, disabled_database_source.text

    plan_response = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-restore-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    restore_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "restore P2.2 while preserving current authority",
    }
    action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        restore_payload,
        "p22-restore-request",
        extra_headers={"If-Match": plan["etag"]},
    )
    approve_action(
        admin_b,
        csrf_b,
        action,
        key="p22-restore-approve",
    )
    restored = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p22-restore-execute",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["kind"] == "RESTORE_COMPLETED"

    relogged, _ = login(app, "implementation")
    restored_source = relogged.get(f"/api/v1/control-plane/query-sources/{source['source_id']}")
    restored_dataset = relogged.get(f"/api/v1/control-plane/query-datasets/{dataset['dataset_id']}")
    restored_database_source = relogged.get(
        f"/api/v1/control-plane/query-sources/{database_source['source_id']}"
    )
    assert restored_source.status_code == 200, restored_source.text
    assert restored_dataset.status_code == 200, restored_dataset.text
    assert restored_database_source.status_code == 200, restored_database_source.text
    assert restored_source.json()["state"] == "DISABLED"
    assert restored_dataset.json()["state"] == "DISABLED"
    assert restored_database_source.json()["state"] == "DISABLED"
    with service.store.connect() as connection:
        workbook = connection.execute(
            """
            SELECT workbook_content, workbook_sha256
            FROM query_source_versions WHERE source_version_id = ?
            """,
            (source["source_version_id"],),
        ).fetchone()
        assert workbook["workbook_content"]
        assert len(workbook["workbook_sha256"]) == 64
        restored_secret = connection.execute(
            """
            SELECT qsec.state, qsec.current_version_id, qsv.envelope_ciphertext
            FROM query_secret_records qsec
            JOIN query_secret_versions qsv
              ON qsv.secret_version_id = qsec.current_version_id
            """
        ).fetchone()
        assert restored_secret["state"] == "ACTIVE"
        assert restored_secret["current_version_id"] == secret["secret_version_id"]
        assert restored_secret["envelope_ciphertext"]
    assert database_password.encode("utf-8") not in service.store.path.read_bytes()


def test_restore_rejects_live_workers_and_terminalizes_restored_orphans(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
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
        suffix="restore-orphan",
    )
    adapter_started = threading.Event()

    def blocking_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        adapter_started.set()
        assert job.cancel_event.wait(5)
        raise service.p2_2._cancellation_failure(job)

    monkeypatch.setattr(service.p2_2, "_execute_excel", blocking_excel)
    started = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-restore-orphan-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert started.status_code == 202, started.text
    assert adapter_started.wait(2)
    execution_id = started.json()["execution_id"]
    with service.store.connect() as connection:
        assert (
            connection.execute(
                "SELECT state FROM query_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()["state"]
            == "RUNNING"
        )

    backup_response = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-orphan-backup"},
        ),
        json={"reason": "capture a nonterminal controlled-query row"},
    )
    assert backup_response.status_code == 201, backup_response.text
    backup = backup_response.json()
    verified = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-orphan-backup-verify"},
        ),
    )
    assert verified.status_code == 200, verified.text
    plan_response = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-orphan-restore-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    restore_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "restore an orphan-safe controlled-query snapshot",
    }
    action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        restore_payload,
        "p22-orphan-restore-request",
        extra_headers={"If-Match": plan["etag"]},
    )
    approve_action(admin_b, csrf_b, action, key="p22-orphan-restore-approve")
    blocked = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p22-orphan-restore-blocked",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "ACTIVE_QUERY_RESTORE_FORBIDDEN"

    cancelled = runtime["device"].post(
        f"/api/v1/device/query-executions/{execution_id}:cancel",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-orphan-cancel-live",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    live_result = _poll_execution(
        runtime["device"],
        f"/api/v1/device/query-executions/{execution_id}",
        headers=runtime["device_headers"],
    )
    assert live_result["state"] == "CANCELLED"
    job = service.p2_2._jobs[execution_id]
    assert job.future is not None
    job.future.result(timeout=2)

    restored = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p22-orphan-restore-execute",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert restored.status_code == 200, restored.text
    with service.store.connect() as connection:
        orphan = connection.execute(
            """
            SELECT state, error_code, completed_at
            FROM query_executions WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()
        assert orphan["state"] == "FAILED"
        assert orphan["error_code"] == "QUERY_RESTORE_INTERRUPTED"
        assert orphan["completed_at"] is not None
    assert service.p2_2._jobs == {}
    assert service.p2_2._screen_inflight == {}


def test_three_screen_releases_execute_concurrently_with_failure_isolation(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][:3]
    assert len(screens) == 3
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
            suffix=f"three-{index}",
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
    starts: list[dict[str, Any]] = []
    for index, runtime in enumerate(runtimes):
        catalog = runtime["device"].get(
            "/api/v1/device/query-datasets",
            headers=runtime["device_headers"],
        )
        assert catalog.status_code == 200, catalog.text
        assert [item["dataset_id"] for item in catalog.json()["items"]] == [runtime["dataset"]["dataset_id"]]
        started = runtime["device"].post(
            f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
            headers={
                **runtime["device_headers"],
                "Idempotency-Key": f"p22-three-execute-{index}",
            },
            json={"parameters": {"shift": "A"}},
        )
        assert started.status_code == 202, started.text
        starts.append(started.json())
    assert len({item["request_id"] for item in starts}) == 3
    wrong_dataset = runtimes[0]["device"].post(
        f"/api/v1/device/query-datasets/{runtimes[1]['dataset']['dataset_id']}:execute",
        headers={
            **runtimes[0]["device_headers"],
            "Idempotency-Key": "p22-three-wrong-dataset",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert wrong_dataset.status_code == 404
    cross_cancel = runtimes[0]["device"].post(
        f"/api/v1/device/query-executions/{starts[1]['execution_id']}:cancel",
        headers={
            **runtimes[0]["device_headers"],
            "Idempotency-Key": "p22-three-cross-cancel",
        },
    )
    assert cross_cancel.status_code == 404

    results = [
        _poll_execution(
            runtime["device"],
            f"/api/v1/device/query-executions/{start['execution_id']}",
            headers=runtime["device_headers"],
        )
        for runtime, start in zip(runtimes, starts, strict=True)
    ]
    assert [result["state"] for result in results] == [
        "SUCCEEDED",
        "FAILED",
        "SUCCEEDED",
    ]
    assert results[1]["error"]["code"] == "QUERY_SOURCE_UNAVAILABLE"
    assert results[0]["rows"][0]["output"] == 100
    assert results[2]["rows"][0]["output"] == 102
    assert all("fallback" not in json.dumps(result).casefold() for result in results)


def test_excel_and_database_execution_timeouts_are_terminal_without_fallback(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    excel_runtime = _publish_excel_runtime(
        app,
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        screen=screens[0],
        suffix="timeout-excel",
        timeout_ms=100,
    )

    def timeout_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        assert job.cancel_event.wait(2)
        raise service.p2_2._cancellation_failure(job)

    monkeypatch.setattr(service.p2_2, "_execute_excel", timeout_excel)
    excel_started_at = time.perf_counter()
    excel_started = excel_runtime["device"].post(
        f"/api/v1/device/query-datasets/{excel_runtime['dataset']['dataset_id']}:execute",
        headers={
            **excel_runtime["device_headers"],
            "Idempotency-Key": "p22-timeout-excel-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert excel_started.status_code == 202, excel_started.text
    excel_result = _poll_execution(
        excel_runtime["device"],
        f"/api/v1/device/query-executions/{excel_started.json()['execution_id']}",
        headers=excel_runtime["device_headers"],
    )
    assert time.perf_counter() - excel_started_at < 1
    assert excel_result["state"] == "TIMED_OUT"
    assert excel_result["error"]["code"] == "QUERY_TIMED_OUT"
    assert "rows" not in excel_result
    assert "fallback" not in json.dumps(excel_result).casefold()

    database_password = "P2.2-Database-Timeout-Secret!"
    source_response = admin_a.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-timeout-db-source"},
        ),
        json={
            "site_id": screens[1]["site_id"],
            "display_name": "Timeout PostgreSQL",
            "engine": "POSTGRESQL",
            "read_only_account_confirmed": True,
            "connection": {
                "host": "127.0.0.1",
                "port": 5432,
                "database": "reference",
                "username": "readonly",
                "password": database_password,
            },
        },
    )
    assert source_response.status_code == 201, source_response.text
    database_source = source_response.json()
    database_dataset_response = admin_a.post(
        "/api/v1/control-plane/query-datasets",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p22-timeout-db-dataset"},
        ),
        json={
            "source_id": database_source["source_id"],
            "display_name": "Timeout dataset",
            "metric_definition": "Approved output by shift",
            "time_scope_description": "Approved fixture",
            "freshness_label": "Test fixture",
            "parameters": [{"name": "shift", "type": "string", "required": True}],
            "output_fields": ["shift", "output"],
            "definition": {
                "query_template": ("SELECT shift, output FROM approved_metrics WHERE shift = :shift"),
                "allowed_relations": ["approved_metrics"],
            },
            "row_limit": 20,
            "timeout_ms": 100,
        },
    )
    assert database_dataset_response.status_code == 201, database_dataset_response.text
    database_dataset = database_dataset_response.json()
    with service.store.transaction() as connection:
        connection.execute(
            """
            UPDATE query_sources
            SET qualification_state = 'AVAILABLE',
                qualification_code = 'CONNECTION_TEST_PASSED',
                last_tested_at = ?, updated_at = ?, revision = revision + 1
            WHERE source_id = ?
            """,
            (service.clock(), service.clock(), database_source["source_id"]),
        )
    database_profile = _create_controlled_query_profile(
        implementation,
        csrf_impl,
        site_id=screens[1]["site_id"],
        suffix="timeout-db",
    )
    database_release = _create_query_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screens[1]["screen_id"],
        profile_version_id=database_profile["head_version_id"],
        dataset_version_ids=[database_dataset["dataset_version_id"]],
        suffix="timeout-db",
    )
    database_device, database_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screens[1]["screen_id"],
        suffix="p22-timeout-db",
    )
    _publish_and_ack(
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        database_device,
        database_headers,
        screen_id=screens[1]["screen_id"],
        release=database_release,
        suffix="p22-timeout-db",
    )

    database_cancelled = threading.Event()

    class FakeConnection:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, *_: object, **__: object) -> None:
            assert database_cancelled.wait(2)
            raise OSError("database statement cancelled")

    class FakeEngine:
        def connect(self) -> FakeConnection:
            return FakeConnection()

        def dispose(self) -> None:
            return None

    def configure_timeout_adapter(
        engine_name: str,
        connection: Any,
        *,
        timeout_ms: int,
        job: Any,
    ) -> None:
        del engine_name, connection, timeout_ms
        with job.lock:
            job.cancel_adapter = database_cancelled.set

    monkeypatch.setattr(service.p2_2, "_database_engine", lambda *args, **kwargs: FakeEngine())
    monkeypatch.setattr(
        service.p2_2,
        "_configure_database_connection",
        configure_timeout_adapter,
    )
    database_started_at = time.perf_counter()
    database_started = database_device.post(
        f"/api/v1/device/query-datasets/{database_dataset['dataset_id']}:execute",
        headers={
            **database_headers,
            "Idempotency-Key": "p22-timeout-db-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert database_started.status_code == 202, database_started.text
    database_result = _poll_execution(
        database_device,
        f"/api/v1/device/query-executions/{database_started.json()['execution_id']}",
        headers=database_headers,
    )
    assert time.perf_counter() - database_started_at < 1
    assert database_result["state"] == "TIMED_OUT"
    assert database_result["error"]["code"] == "QUERY_TIMED_OUT"
    assert "rows" not in database_result
    assert "fallback" not in json.dumps(database_result).casefold()
    assert database_password not in json.dumps(database_result)


def test_queued_cancel_and_current_authority_rechecks_recover_capacity(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
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
        suffix="authority-race",
    )
    adapter_calls: list[str] = []

    def never_execute(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del job, parameters
        adapter_calls.append(dataset_row["dataset_id"])
        return [], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", never_execute)

    def occupy_workers(suffix: str) -> tuple[threading.Event, list[Any]]:
        release = threading.Event()
        started = threading.Event()
        lock = threading.Lock()
        count = 0

        def blocker() -> None:
            nonlocal count
            with lock:
                count += 1
                if count == 3:
                    started.set()
            assert release.wait(5), suffix

        futures = [service.p2_2._executor.submit(blocker) for _ in range(3)]
        assert started.wait(2)
        return release, futures

    release_first, first_blockers = occupy_workers("first")
    queued_cancel = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-queued-cancel-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert queued_cancel.status_code == 202, queued_cancel.text
    cancelled = runtime["device"].post(
        f"/api/v1/device/query-executions/{queued_cancel.json()['execution_id']}:cancel",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-queued-cancel",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "CANCELLED"
    cancelled_job = service.p2_2._jobs[queued_cancel.json()["execution_id"]]
    assert cancelled_job.future is not None and cancelled_job.future.cancelled()
    assert cancelled_job.slot_released is True
    assert service.p2_2._screen_inflight == {}

    queued_recheck = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-queued-recheck-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert queued_recheck.status_code == 202, queued_recheck.text
    with service.store.transaction() as connection:
        connection.execute(
            """
            UPDATE query_sources
            SET qualification_state = 'UNVERIFIED', qualification_code = NULL,
                last_tested_at = NULL, updated_at = ?, revision = revision + 1
            WHERE source_id = ?
            """,
            (service.clock(), runtime["source"]["source_id"]),
        )
    release_first.set()
    for future in first_blockers:
        future.result(timeout=2)
    rechecked = _poll_execution(
        runtime["device"],
        f"/api/v1/device/query-executions/{queued_recheck.json()['execution_id']}",
        headers=runtime["device_headers"],
    )
    assert rechecked["state"] == "FAILED"
    assert rechecked["error"]["code"] == "QUERY_SOURCE_NOT_AVAILABLE"
    assert adapter_calls == []
    with service.store.transaction() as connection:
        connection.execute(
            """
            UPDATE query_sources
            SET qualification_state = 'AVAILABLE',
                qualification_code = 'CONNECTION_TEST_PASSED',
                last_tested_at = ?, updated_at = ?, revision = revision + 1
            WHERE source_id = ?
            """,
            (service.clock(), service.clock(), runtime["source"]["source_id"]),
        )

    release_second, second_blockers = occupy_workers("second")
    queued_disable = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-queued-disable-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert queued_disable.status_code == 202, queued_disable.text
    current_dataset = implementation.get(
        f"/api/v1/control-plane/query-datasets/{runtime['dataset']['dataset_id']}"
    ).json()
    disabled = implementation.post(
        f"/api/v1/control-plane/query-datasets/{runtime['dataset']['dataset_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": current_dataset["etag"],
                "Idempotency-Key": "p22-queued-disable-dataset",
            },
        ),
    )
    assert disabled.status_code == 200, disabled.text
    disabled_result = _poll_execution(
        runtime["device"],
        f"/api/v1/device/query-executions/{queued_disable.json()['execution_id']}",
        headers=runtime["device_headers"],
    )
    assert disabled_result["state"] == "FAILED"
    assert disabled_result["error"]["code"] == "QUERY_DATASET_NOT_AVAILABLE"
    assert service.p2_2._jobs[queued_disable.json()["execution_id"]].slot_released is True
    assert adapter_calls == []
    release_second.set()
    for future in second_blockers:
        future.result(timeout=2)

    disabled_start = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-disabled-dataset-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert disabled_start.status_code == 409
    assert disabled_start.json()["error"]["code"] == "QUERY_DATASET_NOT_AVAILABLE"
    with service.store.transaction() as connection:
        connection.execute(
            """
            UPDATE query_datasets
            SET state = 'ACTIVE', updated_at = ?, revision = revision + 1
            WHERE dataset_id = ?
            """,
            (service.clock(), runtime["dataset"]["dataset_id"]),
        )
    current_source = implementation.get(
        f"/api/v1/control-plane/query-sources/{runtime['source']['source_id']}"
    ).json()
    disabled_source = implementation.post(
        f"/api/v1/control-plane/query-sources/{runtime['source']['source_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": current_source["etag"],
                "Idempotency-Key": "p22-disabled-source",
            },
        ),
    )
    assert disabled_source.status_code == 200, disabled_source.text
    disabled_source_start = runtime["device"].post(
        f"/api/v1/device/query-datasets/{runtime['dataset']['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-disabled-source-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert disabled_source_start.status_code == 409
    assert disabled_source_start.json()["error"]["code"] == "QUERY_SOURCE_NOT_AVAILABLE"
    unbound = _create_excel_dataset(
        implementation,
        csrf_impl,
        source_id=runtime["source"]["source_id"],
        suffix="unbound",
    )
    unbound_start = runtime["device"].post(
        f"/api/v1/device/query-datasets/{unbound['dataset_id']}:execute",
        headers={
            **runtime["device_headers"],
            "Idempotency-Key": "p22-unbound-dataset-start",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert unbound_start.status_code == 404
    assert adapter_calls == []


def test_p22_etag_replay_and_immutable_sidecars_fail_closed(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = p22_control_plane
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
        suffix="etag-immutable",
    )
    source = implementation.get(
        f"/api/v1/control-plane/query-sources/{runtime['source']['source_id']}"
    ).json()
    tested = implementation.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p22-etag-source-test",
            },
        ),
    )
    assert tested.status_code == 200, tested.text
    replay = implementation.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p22-etag-source-test",
            },
        ),
    )
    assert replay.status_code == 200
    assert replay.json() == tested.json()
    current_source = implementation.get(f"/api/v1/control-plane/query-sources/{source['source_id']}").json()
    changed_reuse = implementation.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": current_source["etag"],
                "Idempotency-Key": "p22-etag-source-test",
            },
        ),
    )
    assert changed_reuse.status_code == 409
    assert changed_reuse.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    stale_source = implementation.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p22-stale-source-test",
            },
        ),
    )
    assert stale_source.status_code == 412
    assert stale_source.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"
    stale_dataset = implementation.post(
        f"/api/v1/control-plane/query-datasets/{runtime['dataset']['dataset_id']}:disable",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": '"query-dataset-stale"',
                "Idempotency-Key": "p22-stale-dataset-disable",
            },
        ),
    )
    assert stale_dataset.status_code == 412
    assert stale_dataset.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    mutation_cases = (
        (
            "query_source_versions",
            "canonical_config_json = '{}'",
            "source_version_id",
            runtime["source"]["source_version_id"],
        ),
        (
            "query_dataset_versions",
            "metric_definition = 'tampered'",
            "dataset_version_id",
            runtime["dataset"]["dataset_version_id"],
        ),
        (
            "config_draft_query_assignments",
            "assignment_hash = 'tampered'",
            "rowid",
            None,
        ),
        (
            "release_target_query_snapshots",
            "query_snapshot_hash = 'tampered'",
            "release_target_id",
            runtime["release"]["targets"][0]["release_target_id"],
        ),
    )
    with sqlite3.connect(database_path) as connection:
        original_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table, *_ in mutation_cases
        }
        for table, assignment, key_column, key_value in mutation_cases:
            where = (
                f"{key_column} = ?"
                if key_value is not None
                else "rowid = (SELECT MIN(rowid) FROM config_draft_query_assignments)"
            )
            parameters = (key_value,) if key_value is not None else ()
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    f"UPDATE {table} SET {assignment} WHERE {where}",
                    parameters,
                )
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    f"DELETE FROM {table} WHERE {where}",
                    parameters,
                )
        assert {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table, *_ in mutation_cases
        } == original_counts


def test_screen_queue_is_bounded_and_cancellation_is_terminal(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    auditor, _ = login(app, "auditor")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    source = _create_excel_source(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix="queue",
    )
    dataset = _create_excel_dataset(
        implementation,
        csrf_impl,
        source_id=source["source_id"],
        suffix="queue",
    )
    profile = _create_controlled_query_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix="queue",
    )
    release = _create_query_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screen["screen_id"],
        profile_version_id=profile["head_version_id"],
        dataset_version_ids=[dataset["dataset_version_id"]],
        suffix="queue",
    )
    device, device_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screen["screen_id"],
        suffix="p22-queue",
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
        suffix="p22-queue",
    )

    release_workers = threading.Event()
    worker_started = threading.Event()

    def blocking_excel(
        job: Any,
        dataset_row: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del dataset_row, parameters
        worker_started.set()
        while not release_workers.wait(0.01):
            if job.cancel_event.is_set():
                raise QueryExecutionFailure(
                    "QUERY_CANCELLED",
                    "The query was cancelled",
                )
        return [], ["business_date", "shift", "output", "quality_rate"]

    monkeypatch.setattr(service.p2_2, "_execute_excel", blocking_excel)
    starts: list[dict[str, Any]] = []
    for index in range(3):
        response = device.post(
            f"/api/v1/device/query-datasets/{dataset['dataset_id']}:execute",
            headers={
                **device_headers,
                "Idempotency-Key": f"p22-queue-start-{index}",
            },
            json={"parameters": {"shift": "A"}},
        )
        assert response.status_code == 202, response.text
        starts.append(response.json())
    assert worker_started.wait(1)
    assert starts[2]["state"] == "REJECTED_BACKPRESSURE"
    assert starts[2]["error"]["code"] == "SCREEN_QUERY_BACKPRESSURE"

    cancelled = device.post(
        f"/api/v1/device/query-executions/{starts[0]['execution_id']}:cancel",
        headers={
            **device_headers,
            "Idempotency-Key": "p22-queue-cancel-first",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["state"] == "CANCELLED"
    replay = device.post(
        f"/api/v1/device/query-executions/{starts[0]['execution_id']}:cancel",
        headers={
            **device_headers,
            "Idempotency-Key": "p22-queue-cancel-first",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == cancelled.json()
    conflicting_reuse = device.post(
        f"/api/v1/device/query-executions/{starts[1]['execution_id']}:cancel",
        headers={
            **device_headers,
            "Idempotency-Key": "p22-queue-cancel-first",
        },
    )
    release_workers.set()
    assert conflicting_reuse.status_code == 409, conflicting_reuse.text
    assert conflicting_reuse.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    second = _poll_execution(
        device,
        f"/api/v1/device/query-executions/{starts[1]['execution_id']}",
        headers=device_headers,
    )
    assert second["state"] == "SUCCEEDED"
    first = _poll_execution(
        device,
        f"/api/v1/device/query-executions/{starts[0]['execution_id']}",
        headers=device_headers,
    )
    assert first["state"] == "CANCELLED"
    assert first["error"]["code"] == "QUERY_CANCELLED"
    assert all("fallback" not in json.dumps(item).casefold() for item in starts)
    audit = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit.status_code == 200, audit.text
    rejection_events = [
        item
        for item in audit.json()["items"]
        if item["event_type"] == "CONTROLLED_QUERY_COMPLETED"
        and item["target_id"] == starts[2]["execution_id"]
    ]
    assert len(rejection_events) == 1
    assert rejection_events[0]["outcome"] == "DENIED"
    assert rejection_events[0]["details"]["state"] == "REJECTED_BACKPRESSURE"


def test_exact_p21_upgrade_to_005_is_repeatable_and_pre005_copy_is_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "accepted-p2-1.db"
    rollback_path = tmp_path / "accepted-p2-1.pre-005.db"
    root_key = PurposeKeyring.generate_root_base64()
    full_migrations = store_module.MIGRATIONS
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "MIGRATIONS", full_migrations[:4])
        p21 = ControlPlaneService(
            str(database_path),
            root_key,
            preview_mode=True,
        )
        p21.initialize_preview(
            tenant_id="tenant-p22-upgrade",
            deployment_id="deployment-p22-upgrade",
            screen_id="screen-p22-upgrade",
            identities=[
                {
                    "username": username,
                    "display_name": username,
                    "role_id": role_id,
                    "password": "P22-Upgrade-Test!42",
                }
                for username, role_id in (
                    ("admin-a", "platform_admin"),
                    ("admin-b", "platform_admin"),
                    ("implementation", "implementation_engineer"),
                    ("auditor", "auditor"),
                )
            ],
        )
        source = p21.store.connect()
        target = sqlite3.connect(rollback_path)
        try:
            source.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        assert p21.status()["migration_version"] == MIGRATION_004_VERSION

    upgraded = ControlPlaneService(
        str(database_path),
        root_key,
        preview_mode=True,
    )
    assert upgraded.status()["migration_version"] == full_migrations[-1][0]
    repeated = ControlPlaneService(
        str(database_path),
        root_key,
        preview_mode=True,
    )
    assert repeated.status()["migration_version"] == full_migrations[-1][0]
    with repeated.store.connect() as connection:
        assert (
            connection.execute(
                """
            SELECT COUNT(*) FROM schema_migrations
            WHERE version = '005_controlled_querying'
            """
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                """
            SELECT COUNT(*) FROM security_audit_events
            WHERE event_type = 'CONTROLLED_QUERY_SCHEMA_MIGRATED'
            """
            ).fetchone()[0]
            == 1
        )

    with monkeypatch.context() as patch:
        patch.setattr(store_module, "MIGRATIONS", full_migrations[:4])
        rollback = ControlPlaneService(
            str(rollback_path),
            root_key,
            preview_mode=True,
        )
        assert rollback.status()["migration_version"] == MIGRATION_004_VERSION
        with rollback.store.connect() as connection:
            assert (
                connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'query_sources'
                    """
                ).fetchone()
                is None
            )
