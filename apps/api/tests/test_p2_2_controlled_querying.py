from __future__ import annotations

import base64
import io
import json
import sqlite3
import threading
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest
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
from app.control_plane.security import PurposeKeyring
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
            "timeout_ms": 5_000,
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
    "query_template",
    (
        "SELECT * FROM approved_metrics; DELETE FROM approved_metrics",
        "SELECT * FROM approved_metrics -- comment",
        "INSERT INTO approved_metrics(value) VALUES (1)",
        "UPDATE approved_metrics SET value = 1",
        "DELETE FROM approved_metrics",
        "DROP TABLE approved_metrics",
        "CALL refresh_metrics()",
        "EXECUTE unsafe_plan",
        "SELECT shift, output FROM unapproved_metrics WHERE shift = :shift",
        "SELECT shift, output FROM approved_metrics WHERE shift = :undeclared",
    ),
)
def test_database_dataset_sql_contract_fails_closed(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
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
            "display_name": "Unverified PostgreSQL reference",
            "engine": "POSTGRESQL",
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
        "query_datasets",
        "query_dataset_versions",
    ):
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
    assert restored_source.status_code == 200, restored_source.text
    assert restored_dataset.status_code == 200, restored_dataset.text
    assert restored_source.json()["state"] == "DISABLED"
    assert restored_dataset.json()["state"] == "DISABLED"
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


def test_screen_queue_is_bounded_and_cancellation_is_terminal(
    p22_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, _ = p22_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
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
