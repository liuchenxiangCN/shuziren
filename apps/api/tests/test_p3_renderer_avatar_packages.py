from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_control_plane import approve_action, login, mutation_headers, request_action
from test_control_plane import control_plane as _shared_control_plane
from test_p2_1_capability_profiles import _enroll_device

from app.control_plane.security import PurposeKeyring
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import (
    MIGRATION_006_CHECKSUM_SHA256,
    MIGRATION_006_VERSION,
    MIGRATIONS,
    SCHEMA_MIGRATIONS_SQL,
    ControlPlaneStore,
)


@pytest.fixture()
def p3_control_plane(tmp_path: Path) -> tuple[FastAPI, ControlPlaneService, Path]:
    return _shared_control_plane.__wrapped__(tmp_path)


def _screen_inventory(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/v1/control-plane/screen-instances")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) >= 3
    return items


def _package_payload(
    site_id: str,
    *,
    version: str,
    label: str,
    background: str,
    accent: str,
) -> dict[str, Any]:
    preview = {
        "schema_version": "p3_test_avatar_preview_v1",
        "label": label,
        "background": background,
        "accent": accent,
    }
    content = json.dumps(
        preview,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    return {
        "site_id": site_id,
        "manifest": {
            "schema_version": "p3_avatar_package_v1",
            "avatar_id": "test-guide",
            "version": version,
            "display_name": "测试讲解员",
            "avatar_type": "test",
            "renderer_type": "test_card",
            "renderer_version_range": "^1.0.0",
            "entry_asset": "avatar.json",
            "resources": [
                {
                    "path": "avatar.json",
                    "media_type": "application/vnd.shuziren.test-avatar+json",
                    "size_bytes": len(content),
                    "sha256": digest,
                }
            ],
            "states": {
                "idle": "avatar.json",
                "listening": "avatar.json",
                "thinking": "avatar.json",
                "speaking": "avatar.json",
                "error": "avatar.json",
            },
            "lip_sync_mode": "volume",
            "requirements": {
                "browser": "test-contract",
                "gpu": "not-required",
                "vram_mb": 0,
                "memory_mb": 64,
            },
            "canvas": {
                "aspect_ratio": "1:1",
                "transparent_background": False,
                "safe_area_percent": 8,
            },
            "license": {
                "kind": "TEST_ONLY",
                "rights_holder": "Generated P3 fixture",
                "expires_at": None,
                "usage_scope": "DEVELOPMENT_PREVIEW",
            },
        },
        "files": [
            {
                "path": "avatar.json",
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        ],
    }


def _replace_resource_content(payload: dict[str, Any], content: bytes) -> None:
    payload["files"][0]["content_base64"] = base64.b64encode(content).decode("ascii")
    payload["manifest"]["resources"][0]["size_bytes"] = len(content)
    payload["manifest"]["resources"][0]["sha256"] = hashlib.sha256(content).hexdigest()


def _duplicate_resource(payload: dict[str, Any]) -> None:
    payload["manifest"]["resources"].append(dict(payload["manifest"]["resources"][0]))
    payload["files"].append(dict(payload["files"][0]))


def _append_oversize_resource(payload: dict[str, Any]) -> None:
    content = b"x" * (2 * 1024 * 1024)
    payload["manifest"]["resources"].append(
        {
            "path": "oversize.json",
            "media_type": "application/vnd.shuziren.test-avatar+json",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    )
    payload["files"].append(
        {
            "path": "oversize.json",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
    )


def _create_package(
    client: TestClient,
    csrf: str,
    payload: dict[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/control-plane/avatar-packages",
        headers=mutation_headers(csrf, **{"Idempotency-Key": key}),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _prefetch(
    client: TestClient,
    csrf: str,
    *,
    screen_id: str,
    version: dict[str, Any],
    key: str,
    content_hash: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/"
        f"avatar-package-versions/{version['package_version_id']}:prefetch",
        headers=mutation_headers(csrf, **{"Idempotency-Key": key}),
        json={"expected_content_hash": content_hash or version["content_hash"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _binding(client: TestClient, screen_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/control-plane/screen-instances/{screen_id}/avatar-binding")
    assert response.status_code == 200, response.text
    return response.json()


def _publish(
    client: TestClient,
    csrf: str,
    *,
    screen_id: str,
    version: dict[str, Any],
    binding: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/avatar-publications",
        headers=mutation_headers(
            csrf,
            **{
                "Idempotency-Key": key,
                "If-Match": binding["etag"],
            },
        ),
        json={
            "package_version_id": version["package_version_id"],
            "expected_binding_generation": binding["binding_generation"],
            "reason": f"publish test avatar {key}",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["etag"] == response.json()["etag"]
    return response.json()


def test_renderer_package_preview_prefetch_switch_isolation_and_rollback(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = p3_control_plane
    implementation, csrf_impl = login(app, "implementation")
    screens = _screen_inventory(implementation)
    first, second, third = screens[:3]
    site_id = first["site_id"]

    registry = implementation.get("/api/v1/control-plane/renderer-providers")
    assert registry.status_code == 200
    assert registry.json()["registry_version"] == "p3_renderer_registry_001"
    assert registry.json()["items"] == [
        {
            "renderer_type": "test_card",
            "display_name": "内置测试卡片 Renderer",
            "renderer_version": "1.0.0",
            "registry_version": "p3_renderer_registry_001",
            "contract_version": "1.0.0",
            "state": "available",
            "test_only": True,
            "supported_avatar_types": ["test"],
            "supported_manifest_schema_versions": ["p3_avatar_package_v1"],
            "supported_media_types": ["application/vnd.shuziren.test-avatar+json"],
            "production_eligible": False,
            "compatibility_note": "仅验证扩展、预览和安全切换契约，不代表真实 2D/3D 支持",
        }
    ]

    v1 = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            site_id,
            version="1.0.0",
            label="青色讲解员",
            background="#E8F5F0",
            accent="#147D64",
        ),
        key="p3-create-v1",
    )
    replay = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            site_id,
            version="1.0.0",
            label="青色讲解员",
            background="#E8F5F0",
            accent="#147D64",
        ),
        key="p3-create-v1",
    )
    assert replay == v1
    v2 = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            site_id,
            version="2.0.0",
            label="金色讲解员",
            background="#FFF5D8",
            accent="#A56A00",
        ),
        key="p3-create-v2",
    )
    assert v1["package_id"] == v2["package_id"]
    assert v1["immutable"] is True
    assert v1["test_only"] is True
    assert v1["production_eligible"] is False
    assert len(v1["resources"]) == 1
    assert v1["resources"][0]["path"] == "avatar.json"
    assert v1["resources"][0]["media_type"] == "application/vnd.shuziren.test-avatar+json"
    assert v1["resources"][0]["size_bytes"] == v1["total_bytes"]
    assert len(v1["resources"][0]["sha256"]) == 64
    packages = implementation.get("/api/v1/control-plane/avatar-packages").json()["items"]
    assert len(packages) == 1
    assert {item["version"] for item in packages[0]["versions"]} == {"1.0.0", "2.0.0"}
    preview = implementation.get(
        f"/api/v1/control-plane/avatar-package-versions/{v2['package_version_id']}/preview"
    )
    assert preview.status_code == 200
    assert preview.json()["preview_model"]["label"] == "金色讲解员"
    assert preview.json()["test_only"] is True
    assert preview.json()["manifest_hash"] == v2["manifest_hash"]
    assert preview.json()["content_hash"] == v2["content_hash"]
    assert preview.json()["resources"] == v2["resources"]
    assert preview.json()["renderer_type"] == "test_card"
    assert preview.json()["renderer_version"] == "1.0.0"

    for screen in (first, second):
        ready = _prefetch(
            implementation,
            csrf_impl,
            screen_id=screen["screen_id"],
            version=v1,
            key=f"p3-prefetch-v1-{screen['screen_id']}",
        )
        assert ready["outcome"] == "READY"
        published = _publish(
            implementation,
            csrf_impl,
            screen_id=screen["screen_id"],
            version=v1,
            binding=_binding(implementation, screen["screen_id"]),
            key=f"p3-publish-v1-{screen['screen_id']}",
        )
        assert published["current"]["package_version_id"] == v1["package_version_id"]

    ready_v2 = _prefetch(
        implementation,
        csrf_impl,
        screen_id=second["screen_id"],
        version=v2,
        key="p3-prefetch-v2-second",
    )
    assert ready_v2["outcome"] == "READY"
    second_binding = _publish(
        implementation,
        csrf_impl,
        screen_id=second["screen_id"],
        version=v2,
        binding=_binding(implementation, second["screen_id"]),
        key="p3-publish-v2-second",
    )
    assert second_binding["current"]["package_version_id"] == v2["package_version_id"]
    assert second_binding["previous"]["package_version_id"] == v1["package_version_id"]
    assert (
        _binding(implementation, first["screen_id"])["current"]["package_version_id"]
        == v1["package_version_id"]
    )
    assert _binding(implementation, third["screen_id"])["state"] == "UNBOUND"

    failed = _prefetch(
        implementation,
        csrf_impl,
        screen_id=second["screen_id"],
        version=v1,
        content_hash="0" * 64,
        key="p3-prefetch-corrupt-second",
    )
    assert failed["outcome"] == "FAILED"
    assert failed["failure"]["code"] == "CONTENT_HASH_MISMATCH"
    assert (
        _binding(implementation, second["screen_id"])["current"]["package_version_id"]
        == v2["package_version_id"]
    )

    rollback_source = _binding(implementation, second["screen_id"])
    rollback = implementation.post(
        f"/api/v1/control-plane/screen-instances/{second['screen_id']}/avatar-rollbacks",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "p3-rollback-second",
                "If-Match": rollback_source["etag"],
            },
        ),
        json={
            "expected_binding_generation": rollback_source["binding_generation"],
            "reason": "restore verified P3 test avatar",
        },
    )
    assert rollback.status_code == 200, rollback.text
    rolled_back = rollback.json()
    assert rolled_back["current"]["package_version_id"] == v1["package_version_id"]
    assert rolled_back["previous"]["package_version_id"] == v2["package_version_id"]
    assert rolled_back["binding_generation"] == second_binding["binding_generation"] + 1
    assert rolled_back["history"][0]["operation"] == "ROLLBACK"
    assert (
        _binding(implementation, first["screen_id"])["current"]["package_version_id"]
        == v1["package_version_id"]
    )
    assert _binding(implementation, third["screen_id"])["state"] == "UNBOUND"

    with service.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM avatar_packages").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM avatar_package_versions").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM avatar_switch_records").fetchone()[0] == 4


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda payload: payload["manifest"].__setitem__("renderer_type", "unknown_renderer"),
            "UNKNOWN_RENDERER",
        ),
        (
            lambda payload: payload["manifest"].__setitem__("renderer_version_range", "^2.0.0"),
            "INCOMPATIBLE_RENDERER",
        ),
        (
            lambda payload: (
                payload["manifest"]["resources"][0].__setitem__("path", "../avatar.json"),
                payload["files"][0].__setitem__("path", "../avatar.json"),
            ),
            "EXECUTABLE_RESOURCE_REJECTED",
        ),
        (
            lambda payload: (
                payload["manifest"]["resources"][0].__setitem__("path", "/avatar.json"),
                payload["files"][0].__setitem__("path", "/avatar.json"),
            ),
            "EXECUTABLE_RESOURCE_REJECTED",
        ),
        (
            lambda payload: (
                payload["manifest"]["resources"][0].__setitem__("path", "avatar%2f.json"),
                payload["files"][0].__setitem__("path", "avatar%2f.json"),
            ),
            "EXECUTABLE_RESOURCE_REJECTED",
        ),
        (
            lambda payload: (
                payload["manifest"].__setitem__("entry_asset", "avatar.zip"),
                payload["manifest"].__setitem__(
                    "states",
                    {state: "avatar.zip" for state in ("idle", "listening", "thinking", "speaking", "error")},
                ),
                payload["manifest"]["resources"][0].__setitem__("path", "avatar.zip"),
                payload["files"][0].__setitem__("path", "avatar.zip"),
            ),
            "EXECUTABLE_RESOURCE_REJECTED",
        ),
        (
            lambda payload: (
                payload["manifest"].__setitem__("entry_asset", "avatar.js"),
                payload["manifest"].__setitem__(
                    "states",
                    {state: "avatar.js" for state in ("idle", "listening", "thinking", "speaking", "error")},
                ),
                payload["manifest"]["resources"][0].__setitem__("path", "avatar.js"),
                payload["files"][0].__setitem__("path", "avatar.js"),
            ),
            "EXECUTABLE_RESOURCE_REJECTED",
        ),
        (
            lambda payload: payload["manifest"]["resources"][0].__setitem__("sha256", "0" * 64),
            "RESOURCE_INTEGRITY_FAILED",
        ),
        (
            lambda payload: payload["manifest"]["license"].__setitem__("kind", "COMMERCIAL"),
            "LICENSE_NOT_ELIGIBLE",
        ),
        (_append_oversize_resource, "PACKAGE_TOO_LARGE"),
        (
            lambda payload: _replace_resource_content(payload, b"{malformed"),
            "SCHEMA_VALIDATION_FAILED",
        ),
        (
            _duplicate_resource,
            "SCHEMA_VALIDATION_FAILED",
        ),
    ],
)
def test_package_validation_rejects_unsafe_or_incompatible_content_without_partial_write(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    mutate: Any,
    expected_code: str,
) -> None:
    app, service, _ = p3_control_plane
    implementation, csrf = login(app, "implementation")
    site_id = _screen_inventory(implementation)[0]["site_id"]
    payload = _package_payload(
        site_id,
        version="1.0.0",
        label="安全测试",
        background="#FFFFFF",
        accent="#000000",
    )
    mutate(payload)
    response = implementation.post(
        "/api/v1/control-plane/avatar-packages",
        headers=mutation_headers(csrf, **{"Idempotency-Key": f"unsafe-{expected_code}"}),
        json=payload,
    )
    assert response.status_code in {413, 422}, response.text
    assert response.json()["error"]["code"] == expected_code
    with service.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM avatar_packages").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM avatar_package_versions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM avatar_package_resources").fetchone()[0] == 0


def test_rbac_optimistic_concurrency_prefetch_gate_and_immutable_history(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = p3_control_plane
    implementation, csrf_impl = login(app, "implementation")
    auditor, csrf_auditor = login(app, "auditor")
    screen = _screen_inventory(implementation)[0]
    payload = _package_payload(
        screen["site_id"],
        version="1.0.0",
        label="并发测试",
        background="#F0F0F0",
        accent="#123456",
    )
    denied_create = auditor.post(
        "/api/v1/control-plane/avatar-packages",
        headers=mutation_headers(csrf_auditor, **{"Idempotency-Key": "p3-auditor-create"}),
        json=payload,
    )
    assert denied_create.status_code == 403
    assert denied_create.json()["error"]["code"] == "FORBIDDEN"
    version = _create_package(implementation, csrf_impl, payload, key="p3-create-concurrency")
    initial = _binding(implementation, screen["screen_id"])

    denied_prefetch = auditor.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/"
        f"avatar-package-versions/{version['package_version_id']}:prefetch",
        headers=mutation_headers(csrf_auditor, **{"Idempotency-Key": "p3-auditor-prefetch"}),
        json={"expected_content_hash": version["content_hash"]},
    )
    assert denied_prefetch.status_code == 403
    denied_publish = auditor.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/avatar-publications",
        headers=mutation_headers(
            csrf_auditor,
            **{"Idempotency-Key": "p3-auditor-publish", "If-Match": initial["etag"]},
        ),
        json={
            "package_version_id": version["package_version_id"],
            "expected_binding_generation": 0,
            "reason": "auditor cannot publish",
        },
    )
    assert denied_publish.status_code == 403
    denied_rollback = auditor.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/avatar-rollbacks",
        headers=mutation_headers(
            csrf_auditor,
            **{"Idempotency-Key": "p3-auditor-rollback", "If-Match": initial["etag"]},
        ),
        json={"expected_binding_generation": 1, "reason": "auditor cannot rollback"},
    )
    assert denied_rollback.status_code == 403

    no_prefetch = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/avatar-publications",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p3-publish-no-prefetch", "If-Match": initial["etag"]},
        ),
        json={
            "package_version_id": version["package_version_id"],
            "expected_binding_generation": 0,
            "reason": "must fail without prefetch",
        },
    )
    assert no_prefetch.status_code == 409
    assert no_prefetch.json()["error"]["code"] == "AVATAR_PREFETCH_REQUIRED"
    assert _binding(implementation, screen["screen_id"])["state"] == "UNBOUND"

    _prefetch(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        version=version,
        key="p3-prefetch-concurrency",
    )
    published = _publish(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        version=version,
        binding=initial,
        key="p3-publish-concurrency",
    )
    version_two = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            screen["site_id"],
            version="2.0.0",
            label="并发测试新版",
            background="#EEEEEE",
            accent="#654321",
        ),
        key="p3-create-concurrency-v2",
    )
    _prefetch(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        version=version_two,
        key="p3-prefetch-concurrency-v2",
    )
    stale = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/avatar-publications",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p3-stale-publish", "If-Match": initial["etag"]},
        ),
        json={
            "package_version_id": version_two["package_version_id"],
            "expected_binding_generation": 0,
            "reason": "stale mutation must fail",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"
    assert _binding(implementation, screen["screen_id"])["etag"] == published["etag"]

    with service.store.transaction() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE avatar_package_versions SET version = '9.9.9' WHERE package_version_id = ?",
            (version["package_version_id"],),
        )
    with service.store.transaction() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("DELETE FROM avatar_switch_records")


def test_tenant_deployment_site_ownership_and_restart_persistence(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = p3_control_plane
    implementation, csrf = login(app, "implementation")
    screen = _screen_inventory(implementation)[0]
    package_payload = _package_payload(
        screen["site_id"],
        version="1.0.0",
        label="重启持久化",
        background="#E8F5F0",
        accent="#147D64",
    )
    uploaded_content = package_payload["files"][0]["content_base64"]
    version = _create_package(
        implementation,
        csrf,
        package_payload,
        key="p3-restart-create",
    )
    _prefetch(
        implementation,
        csrf,
        screen_id=screen["screen_id"],
        version=version,
        key="p3-restart-prefetch",
    )
    published = _publish(
        implementation,
        csrf,
        screen_id=screen["screen_id"],
        version=version,
        binding=_binding(implementation, screen["screen_id"]),
        key="p3-restart-publish",
    )

    with service.store.transaction() as connection:
        now = service.clock()
        connection.execute(
            """
            INSERT INTO sites(
                site_id, tenant_id, deployment_id, slug, display_name, timezone,
                status, created_at, updated_at
            ) VALUES ('site-foreign-p3', 'tenant-foreign', 'deployment-foreign',
                'foreign-p3', 'Foreign P3', 'Asia/Shanghai', 'ACTIVE', ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO screen_instances(
                screen_id, tenant_id, deployment_id, site_id, slug, display_name,
                lifecycle_state, created_at, updated_at
            ) VALUES ('screen-foreign-p3', 'tenant-foreign', 'deployment-foreign',
                'site-foreign-p3', 'foreign-screen-p3', 'Foreign Screen P3',
                'ACTIVE', ?, ?)
            """,
            (now, now),
        )

    foreign_site_payload = _package_payload(
        "site-foreign-p3",
        version="2.0.0",
        label="越权形象",
        background="#FFFFFF",
        accent="#000000",
    )
    denied_site = implementation.post(
        "/api/v1/control-plane/avatar-packages",
        headers=mutation_headers(csrf, **{"Idempotency-Key": "p3-foreign-site"}),
        json=foreign_site_payload,
    )
    assert denied_site.status_code == 404
    denied_screen = implementation.post(
        f"/api/v1/control-plane/screen-instances/screen-foreign-p3/"
        f"avatar-package-versions/{version['package_version_id']}:prefetch",
        headers=mutation_headers(csrf, **{"Idempotency-Key": "p3-foreign-screen"}),
        json={"expected_content_hash": version["content_hash"]},
    )
    assert denied_screen.status_code == 404

    restarted = ControlPlaneService(
        str(database_path),
        PurposeKeyring.generate_root_base64(),
        preview_mode=True,
    )
    app.state.control_plane_service = restarted
    after_restart, _ = login(app, "implementation")
    binding = _binding(after_restart, screen["screen_id"])
    assert binding["etag"] == published["etag"]
    assert binding["current"]["package_version_id"] == version["package_version_id"]
    assert (
        after_restart.get("/api/v1/control-plane/avatar-packages").json()["items"][0]["versions"][0][
            "content_hash"
        ]
        == version["content_hash"]
    )

    with restarted.store.connect() as connection:
        audit_text = "\n".join(
            row["details_json"]
            for row in connection.execute("SELECT details_json FROM security_audit_events ORDER BY sequence")
        )
    assert "content_base64" not in audit_text
    assert uploaded_content not in audit_text


def test_device_scope_returns_only_its_screen_avatar(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, _ = p3_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin, csrf_admin = login(app, "admin-a")
    screens = _screen_inventory(implementation)
    first, second = screens[:2]
    version = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            first["site_id"],
            version="1.0.0",
            label="设备隔离",
            background="#101820",
            accent="#FEE715",
        ),
        key="p3-create-device",
    )
    _prefetch(
        implementation,
        csrf_impl,
        screen_id=first["screen_id"],
        version=version,
        key="p3-prefetch-device-first",
    )
    _publish(
        implementation,
        csrf_impl,
        screen_id=first["screen_id"],
        version=version,
        binding=_binding(implementation, first["screen_id"]),
        key="p3-publish-device-first",
    )
    first_device, first_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin,
        csrf_admin,
        screen_id=first["screen_id"],
        suffix="p3-avatar-first",
    )
    second_device, second_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin,
        csrf_admin,
        screen_id=second["screen_id"],
        suffix="p3-avatar-second",
    )
    first_current = first_device.get("/api/v1/device/avatar/current", headers=first_headers)
    second_current = second_device.get("/api/v1/device/avatar/current", headers=second_headers)
    assert first_current.status_code == 200
    assert first_current.json()["current"]["package_version_id"] == version["package_version_id"]
    assert second_current.status_code == 200
    assert second_current.json()["state"] == "UNBOUND"
    assert second_current.json()["current"] is None


def test_p3_avatar_backup_integrity_and_staged_restore(
    p3_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = p3_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen = _screen_inventory(implementation)[0]
    first = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            screen["site_id"],
            version="1.0.0",
            label="backup green",
            background="#E8F5F0",
            accent="#147D64",
        ),
        key="p3-backup-version-1",
    )
    second = _create_package(
        implementation,
        csrf_impl,
        _package_payload(
            screen["site_id"],
            version="2.0.0",
            label="post backup gold",
            background="#FFF3D6",
            accent="#AD6C00",
        ),
        key="p3-backup-version-2",
    )
    assert (
        _prefetch(
            implementation,
            csrf_impl,
            screen_id=screen["screen_id"],
            version=first,
            key="p3-backup-prefetch-1",
        )["outcome"]
        == "READY"
    )
    first_binding = _publish(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        version=first,
        binding=_binding(implementation, screen["screen_id"]),
        key="p3-backup-publish-1",
    )

    created = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(csrf_a, **{"Idempotency-Key": "p3-avatar-backup"}),
        json={"reason": "preserve the verified P3 avatar binding"},
    )
    assert created.status_code == 201, created.text
    backup = created.json()
    assert backup["state"] == "VERIFIED"
    assert backup["migration_versions"][-1] == "006_renderer_avatar_packages"
    assert backup["safe_row_counts"]["avatar_package_versions"] == 2
    assert backup["safe_row_counts"]["screen_avatar_bindings"] == 1
    with service.p1_3.backups.staged_snapshot(f"backup-{backup['backup_id']}") as (
        staged_path,
        verified,
    ):
        assert verified.safe_row_counts["avatar_switch_records"] == 1
        staged = sqlite3.connect(staged_path)
        try:
            assert (
                staged.execute(
                    "SELECT current_package_version_id FROM screen_avatar_bindings WHERE screen_id = ?",
                    (screen["screen_id"],),
                ).fetchone()[0]
                == first["package_version_id"]
            )
        finally:
            staged.close()

    assert (
        _prefetch(
            implementation,
            csrf_impl,
            screen_id=screen["screen_id"],
            version=second,
            key="p3-backup-prefetch-2",
        )["outcome"]
        == "READY"
    )
    changed_binding = _publish(
        implementation,
        csrf_impl,
        screen_id=screen["screen_id"],
        version=second,
        binding=first_binding,
        key="p3-backup-publish-2",
    )
    assert changed_binding["current"]["package_version_id"] == second["package_version_id"]

    plan_response = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(csrf_a, **{"Idempotency-Key": "p3-avatar-restore-plan"}),
        json={"backup_id": backup["backup_id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    restore_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "restore the exact verified P3 avatar binding",
    }
    restore_action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        restore_payload,
        "p3-avatar-restore-request",
        extra_headers={"If-Match": plan["etag"]},
    )
    approve_action(admin_b, csrf_b, restore_action, key="p3-avatar-restore-approve")
    restored = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p3-avatar-restore-execute",
                "High-Risk-Action-ID": restore_action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["kind"] == "RESTORE_COMPLETED"
    relogged, _ = login(app, "implementation")
    restored_binding = _binding(relogged, screen["screen_id"])
    assert restored_binding["binding_generation"] == 1
    assert restored_binding["current"]["package_version_id"] == first["package_version_id"]
    assert restored_binding["previous"] is None


def test_p2_3_schema_upgrades_additively_to_p3(tmp_path: Path) -> None:
    database_path = tmp_path / "accepted-p2-3-copy.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        ControlPlaneStore._execute_script(connection, SCHEMA_MIGRATIONS_SQL)
        for version, checksum, script in MIGRATIONS[:-1]:
            ControlPlaneStore._execute_script(connection, script)
            connection.execute(
                "INSERT INTO schema_migrations(version, checksum_sha256, applied_at) VALUES (?, ?, ?)",
                (version, checksum, 1.0),
            )
        connection.commit()
    finally:
        connection.close()

    service = ControlPlaneService(
        str(database_path),
        PurposeKeyring.generate_root_base64(),
        preview_mode=True,
    )
    status = service.status()
    assert status["migration_version"] == MIGRATION_006_VERSION
    assert status["migration_checksum_sha256"] == MIGRATION_006_CHECKSUM_SHA256
    with service.store.connect() as upgraded:
        versions = [
            row["version"] for row in upgraded.execute("SELECT version FROM schema_migrations ORDER BY rowid")
        ]
        assert versions == [item[0] for item in MIGRATIONS]
        assert upgraded.execute("SELECT COUNT(*) FROM avatar_package_versions").fetchone()[0] == 0
