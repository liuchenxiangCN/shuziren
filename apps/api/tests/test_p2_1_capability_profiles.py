from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from test_control_plane import (
    ORIGIN,
    PASSWORDS,
    approve_action,
    create_p1_3_release,
    login,
    mutation_headers,
    request_action,
)
from test_control_plane import (
    control_plane as _shared_control_plane,
)

from app.control_plane import store as store_module
from app.control_plane.errors import ControlPlaneError
from app.control_plane.recovery import BackupIntegrityError, BackupManager
from app.control_plane.router import (
    control_plane_error_handler,
    router,
    sanitized_validation_errors,
)
from app.control_plane.security import PurposeKeyring, canonical_json
from app.control_plane.service import ControlPlaneService

CAPABILITIES = {
    "dora",
    "knowledge",
    "direct_llm",
    "asr",
    "tts",
    "querying",
    "fvs_control",
}
STATES = {"disabled", "mock", "unverified", "available", "degraded"}
PROVIDERS = {
    ("local_rules", "dora", "available"),
    ("mock_dora", "dora", "mock"),
    ("dora_gateway", "dora", "unverified"),
    ("local_extractive", "knowledge", "available"),
    ("mock_knowledge", "knowledge", "mock"),
    ("dora_ragflow", "knowledge", "unverified"),
    ("ragflow_gateway", "knowledge", "unverified"),
    ("fixed_template", "direct_llm", "available"),
    ("mock_llm", "direct_llm", "mock"),
    ("direct_llm_gateway", "direct_llm", "unverified"),
    ("mock_asr", "asr", "mock"),
    ("vendor_asr", "asr", "unverified"),
    ("mock_tts", "tts", "mock"),
    ("browser_text_fallback", "tts", "degraded"),
    ("vendor_tts", "tts", "unverified"),
    ("mock_query", "querying", "mock"),
    ("finereport_ai_plugin", "querying", "unverified"),
    ("controlled_query", "querying", "unverified"),
    ("mock_fvs", "fvs_control", "mock"),
    ("fvs_page_number", "fvs_control", "unverified"),
    ("fvs_post_message", "fvs_control", "unverified"),
}
ALLOWED_FALLBACK_REASONS = {"timeout", "unavailable", "unsupported"}
TERMINAL_FALLBACK_REASONS = {
    "permission_denied",
    "invalid_request",
    "unauthorized_template",
    "cancelled",
}


@pytest.fixture()
def p21_control_plane(tmp_path: Path) -> tuple[FastAPI, ControlPlaneService, Path]:
    return _shared_control_plane.__wrapped__(tmp_path)


def _build_app(service: ControlPlaneService) -> FastAPI:
    app = FastAPI()
    app.state.control_plane_service = service
    app.state.control_plane_allowed_origins = (ORIGIN,)
    app.include_router(router)
    app.add_exception_handler(ControlPlaneError, control_plane_error_handler)

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

    app.add_exception_handler(RequestValidationError, validation_handler)
    return app


def _create_profile(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    preset_id: str,
    suffix: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": f"p21-profile-create-{suffix}"},
        ),
        json={
            "site_id": site_id,
            "name": f"P2.1 profile {suffix}",
            "description": f"Test-only profile copied from {preset_id}",
            "source_preset_id": preset_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_p2_1_release(
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    screen_id: str,
    profile_version_id: str,
    suffix: str,
) -> dict[str, Any]:
    created = implementation.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": f"p21-draft-create-{suffix}"},
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
            "welcome_text": f"P2.1 screen {suffix}",
            "fvs_binding_ref": f"https://fvs.example.test/p2-1/{suffix}",
        },
    )
    assert replaced.status_code == 200, replaced.text
    draft = replaced.json()
    assigned = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/capability-profile",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p21-draft-assign-{suffix}",
            },
        ),
        json={"profile_version_id": profile_version_id},
    )
    assert assigned.status_code == 200, assigned.text
    draft = assigned.json()
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p21-draft-validate-{suffix}",
            },
        ),
    )
    assert validated.status_code == 200, validated.text
    draft = validated.json()
    assert draft["validation"]["outcome"] == "VALID"
    previewed = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p21-draft-preview-{suffix}",
            },
        ),
    )
    assert previewed.status_code == 200, previewed.text
    draft = previewed.json()
    assert draft["preview"]["outcome"] == "MOCK_PASSED"
    capability_evidence = draft["preview"]["evidence"]["capabilities"]
    assert capability_evidence["external_calls_made"] is False
    assert capability_evidence["real_provider_verified"] is False
    assert capability_evidence["disabled_zero_provider"] is True
    submitted = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:submit-for-approval",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p21-draft-submit-{suffix}",
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
                "Idempotency-Key": f"p21-draft-approve-{suffix}",
            },
        ),
        json={"reason": "independent P2.1 approval"},
    )
    assert approved.status_code == 200, approved.text
    draft = approved.json()
    released = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:release",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p21-release-create-{suffix}",
            },
        ),
        json={"reason": "create immutable P2.1 release"},
    )
    assert released.status_code == 201, released.text
    result = released.json()
    assert len(result["targets"]) == 1
    assert result["targets"][0]["capability_snapshot"]["profile_version_id"] == profile_version_id
    return result


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
    payload = {"reason": f"enroll P2.1 device {suffix}"}
    action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        payload,
        f"p21-enroll-request-{suffix}",
    )
    approve_action(
        approver,
        csrf_approver,
        action,
        key=f"p21-enroll-approve-{suffix}",
    )
    issued = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": f"p21-enroll-execute-{suffix}",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert issued.status_code == 201, issued.text
    device = TestClient(app, base_url="https://device.test")
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": f"p21-device-claim-{suffix}"},
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
        "reason": f"publish P2.1 release {suffix}",
    }
    action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        payload,
        f"p21-publish-request-{suffix}",
        extra_headers={"If-Match": binding["etag"]},
    )
    approve_action(
        approver,
        csrf_approver,
        action,
        key=f"p21-publish-approve-{suffix}",
    )
    published = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": f"p21-publish-execute-{suffix}",
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
        headers={
            **device_headers,
            "Idempotency-Key": f"p21-ack-{suffix}",
        },
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    assert acknowledged.status_code == 200, acknowledged.text


def test_provider_registry_and_fallback_decision_are_closed(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    from app.control_plane.p2_1 import fallback_decision

    app, _, _ = p21_control_plane
    implementation, _ = login(app, "implementation")
    catalog_response = implementation.get("/api/v1/control-plane/capability-providers")
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = catalog_response.json()

    assert catalog["registry_version"] == "p2_provider_registry_001"
    assert set(catalog["state_definitions"]) == STATES
    assert {
        (item["provider_id"], item["capability"], item["state"]) for item in catalog["items"]
    } == PROVIDERS
    assert {item["capability"] for item in catalog["items"]} == CAPABILITIES
    assert all(item["permission_scope"] == "screen_bound" for item in catalog["items"])
    assert set(catalog["fallback_policy"]["allowed_reasons"]) == ALLOWED_FALLBACK_REASONS
    assert set(catalog["fallback_policy"]["terminal_reasons"]) == TERMINAL_FALLBACK_REASONS

    for reason in ALLOWED_FALLBACK_REASONS:
        assert (
            fallback_decision(
                error_code=reason,
                permission_equivalent=True,
                fallback_provider_state="mock",
            )["fallback_allowed"]
            is True
        )
        assert (
            fallback_decision(
                error_code=reason,
                permission_equivalent=False,
                fallback_provider_state="mock",
            )["fallback_allowed"]
            is False
        )
        assert (
            fallback_decision(
                error_code=reason,
                permission_equivalent=True,
                fallback_provider_state="unverified",
            )["fallback_allowed"]
            is False
        )

    for reason in TERMINAL_FALLBACK_REASONS:
        decision = fallback_decision(
            error_code=reason,
            permission_equivalent=True,
            fallback_provider_state="available",
        )
        assert decision["fallback_allowed"] is False
        assert decision["terminal"] is True

    for reason in ("unknown", "", "network_error"):
        assert (
            fallback_decision(
                error_code=reason,
                permission_equivalent=True,
                fallback_provider_state="available",
            )["fallback_allowed"]
            is False
        )


def test_profile_versions_are_immutable_strong_and_secret_closed(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = p21_control_plane
    implementation, csrf_impl = login(app, "implementation")
    auditor, csrf_auditor = login(app, "auditor")
    site_id = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]["site_id"]

    profile = _create_profile(
        implementation,
        csrf_impl,
        site_id=site_id,
        preset_id="text_only",
        suffix="immutable",
    )
    create_payload = {
        "site_id": site_id,
        "name": "P2.1 profile immutable",
        "description": "Test-only profile copied from text_only",
        "source_preset_id": "text_only",
    }
    replay = implementation.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p21-profile-create-immutable"},
        ),
        json=create_payload,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json() == profile
    changed_replay = implementation.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p21-profile-create-immutable"},
        ),
        json={**create_payload, "name": "changed command"},
    )
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    assert set(profile["head_version"]["spec"]) == CAPABILITIES
    assert profile["head_version"]["activation_eligible"] is True
    disabled_entries = [
        entry for entry in profile["head_version"]["spec"].values() if entry["enabled"] is False
    ]
    assert disabled_entries
    assert all(entry["primary_provider_id"] is None for entry in disabled_entries)
    assert all(entry["fallback_provider_ids"] == [] for entry in disabled_entries)
    diagnostics = profile["head_version"]["capability_diagnostics"]["capabilities"]
    assert all(
        item["selected_provider_id"] is None and item["provider_execution_allowed"] is False
        for item in diagnostics.values()
        if item["state"] == "disabled"
    )

    version_one = profile["head_version"]
    version_two_spec = {
        key: {**value, "timeout_ms": value["timeout_ms"] + 100} for key, value in version_one["spec"].items()
    }
    created_version = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-profile-version-two",
            },
        ),
        json={"spec": version_two_spec},
    )
    assert created_version.status_code == 201, created_version.text
    profile_v2 = created_version.json()
    assert profile_v2["head_version_number"] == 2
    assert profile_v2["head_version"]["profile_version_id"] != version_one["profile_version_id"]
    assert profile_v2["head_version"]["content_hash"] != version_one["content_hash"]

    replay_version = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-profile-version-two",
            },
        ),
        json={"spec": version_two_spec},
    )
    assert replay_version.status_code == 201, replay_version.text
    assert replay_version.json() == profile_v2
    changed_version_replay = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-profile-version-two",
            },
        ),
        json={
            "spec": {
                **version_two_spec,
                "dora": {**version_two_spec["dora"], "timeout_ms": 1234},
            }
        },
    )
    assert changed_version_replay.status_code == 409
    assert changed_version_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    stale_version = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-profile-version-stale",
            },
        ),
        json={"spec": version_two_spec},
    )
    assert stale_version.status_code == 412
    assert stale_version.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    persisted = implementation.get(f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}")
    assert persisted.status_code == 200, persisted.text
    versions = persisted.json()["versions"]
    assert [item["version_number"] for item in versions] == [2, 1]
    persisted_v1 = next(item for item in versions if item["version_number"] == 1)
    assert persisted_v1 == version_one

    with (
        sqlite3.connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
    ):
        connection.execute(
            """
            UPDATE capability_profile_versions
            SET content_hash = ?
            WHERE profile_version_id = ?
            """,
            ("0" * 64, version_one["profile_version_id"]),
        )

    auditor_read = auditor.get(f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}")
    assert auditor_read.status_code == 200, auditor_read.text
    auditor_mutation = auditor.post(
        "/api/v1/control-plane/capability-profiles",
        headers=mutation_headers(
            csrf_auditor,
            **{"Idempotency-Key": "p21-auditor-create-forbidden"},
        ),
        json={
            "site_id": site_id,
            "name": "Auditor must not mutate",
            "description": "RBAC negative",
            "source_preset_id": "text_only",
        },
    )
    assert auditor_mutation.status_code == 403
    assert auditor_mutation.json()["error"]["code"] == "FORBIDDEN"

    for index, secret_value in enumerate(
        (
            "password=not-allowed",
            "postgresql://user:secret@db.example.test/app",
            "Bearer should-never-enter-a-profile",
        )
    ):
        rejected = implementation.post(
            "/api/v1/control-plane/capability-profiles",
            headers=mutation_headers(
                csrf_impl,
                **{"Idempotency-Key": f"p21-secret-reject-{index}"},
            ),
            json={
                "site_id": site_id,
                "name": f"Secret rejection {index}",
                "description": secret_value,
                "source_preset_id": "text_only",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "SECRET_MATERIAL_FORBIDDEN"


def test_unverified_profile_is_inspectable_but_cannot_validate(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, _ = p21_control_plane
    implementation, csrf_impl = login(app, "implementation")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    screen = screens[0]
    profile = _create_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        preset_id="text_only",
        suffix="unverified",
    )
    unverified_spec = {
        **profile["head_version"]["spec"],
        "querying": {
            "enabled": True,
            "primary_provider_id": "finereport_ai_plugin",
            "fallback_provider_ids": [],
            "timeout_ms": 5000,
        },
    }
    version_response = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-create-unverified-version",
            },
        ),
        json={"spec": unverified_spec},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()["head_version"]
    assert version["activation_eligible"] is False
    assert version["state_summary"]["querying"] == "unverified"
    assert any(
        finding["capability"] == "querying" and finding["code"] == "UNVERIFIED_PROVIDER_BLOCKS_ACTIVATION"
        for finding in version["dependency_findings"]
    )

    created = implementation.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "p21-unverified-draft-create"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": screen["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    replaced = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=mutation_headers(csrf_impl, **{"If-Match": draft["etag"]}),
        json={
            "welcome_text": "Unverified provider must remain blocked",
            "fvs_binding_ref": "https://fvs.example.test/p2-1/unverified",
        },
    )
    assert replaced.status_code == 200, replaced.text
    draft = replaced.json()
    assigned = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/capability-profile",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "p21-unverified-draft-assign",
            },
        ),
        json={"profile_version_id": version["profile_version_id"]},
    )
    assert assigned.status_code == 200, assigned.text
    draft = assigned.json()
    assert draft["capability_profile"]["activation_eligible"] is False
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "p21-unverified-draft-validate",
            },
        ),
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["validation"]["outcome"] == "INVALID"
    assert validated.json()["state"] == "DRAFT"


def test_legacy_applied_release_resolves_not_configured_after_004_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "legacy-p1-3.db"
    root_key = PurposeKeyring.generate_root_base64()
    full_migrations = store_module.MIGRATIONS
    monkeypatch.setattr(store_module, "MIGRATIONS", full_migrations[:3])
    legacy_service = ControlPlaneService(
        str(database_path),
        root_key,
        preview_mode=True,
    )
    legacy_service.initialize_preview(
        tenant_id="tenant-p21-legacy",
        deployment_id="deployment-p21-legacy",
        screen_id="screen-trust-fixture",
        identities=[
            {
                "username": username,
                "display_name": username,
                "role_id": role_id,
                "password": PASSWORDS[username],
            }
            for username, role_id in (
                ("admin-a", "platform_admin"),
                ("admin-b", "platform_admin"),
                ("implementation", "implementation_engineer"),
                ("auditor", "auditor"),
            )
        ],
    )
    legacy_app = _build_app(legacy_service)
    implementation, csrf_impl = login(legacy_app, "implementation")
    admin_a, csrf_a = login(legacy_app, "admin-a")
    admin_b, csrf_b = login(legacy_app, "admin-b")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN",
        target_id=screen["screen_id"],
        expected_target_count=1,
        welcome_text="Accepted P1.3 legacy release",
        suffix="p21-legacy",
    )
    device, device_headers = _enroll_device(
        legacy_app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screen["screen_id"],
        suffix="legacy",
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
        suffix="legacy",
    )

    monkeypatch.setattr(store_module, "MIGRATIONS", full_migrations)
    upgraded_service = ControlPlaneService(
        str(database_path),
        root_key,
        preview_mode=True,
    )
    assert upgraded_service.status()["migration_version"] == "004_capability_profiles"
    upgraded_app = _build_app(upgraded_service)
    upgraded_device = TestClient(upgraded_app, base_url="https://device.test")
    current = upgraded_device.get(
        "/api/v1/device/capabilities/current",
        headers=device_headers,
    )
    assert current.status_code == 200, current.text
    assert current.json()["state"] == "NOT_CONFIGURED_P2_1"
    assert current.json()["capabilities"] is None
    upgraded_implementation, _ = login(upgraded_app, "implementation")
    effective = upgraded_implementation.get(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/effective-capabilities"
    )
    assert effective.status_code == 200, effective.text
    assert effective.json()["state"] == "NOT_CONFIGURED_P2_1"
    assert effective.json()["effective"] is None


def test_three_screens_resolve_distinct_profiles_and_session_isolation(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, _ = p21_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    assert len(screens) == 3

    profiles = [
        _create_profile(
            implementation,
            csrf_impl,
            site_id=screen["site_id"],
            preset_id=preset_id,
            suffix=f"screen-{index}",
        )
        for index, (screen, preset_id) in enumerate(
            zip(screens, ("text_only", "mock_voice", "mock_presenter"), strict=True),
            start=1,
        )
    ]
    assert {profile["head_version"]["state_summary"]["dora"] for profile in profiles} == {
        "available",
        "mock",
    }
    assert profiles[0]["head_version"]["state_summary"]["asr"] == "disabled"
    assert profiles[1]["head_version"]["state_summary"]["asr"] == "mock"
    assert profiles[2]["head_version"]["state_summary"]["fvs_control"] == "mock"

    releases = [
        _create_p2_1_release(
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            screen_id=screen["screen_id"],
            profile_version_id=profile["head_version_id"],
            suffix=f"screen-{index}",
        )
        for index, (screen, profile) in enumerate(
            zip(screens, profiles, strict=True),
            start=1,
        )
    ]
    devices_and_headers = [
        _enroll_device(
            app,
            implementation,
            csrf_impl,
            admin_b,
            csrf_b,
            screen_id=screen["screen_id"],
            suffix=f"screen-{index}",
        )
        for index, screen in enumerate(screens, start=1)
    ]
    for index, (screen, release, (device, device_headers)) in enumerate(
        zip(screens, releases, devices_and_headers, strict=True),
        start=1,
    ):
        _publish_and_ack(
            implementation,
            csrf_impl,
            admin_b,
            csrf_b,
            device,
            device_headers,
            screen_id=screen["screen_id"],
            release=release,
            suffix=f"screen-{index}",
        )

    sibling_target = releases[1]["targets"][0]
    wrong_screen = devices_and_headers[0][0].post(
        f"/api/v1/device/config-releases/{sibling_target['release_target_id']}:ack",
        headers={
            **devices_and_headers[0][1],
            "Idempotency-Key": "p21-wrong-screen-credential",
        },
        json={
            "binding_generation": 1,
            "content_hash": sibling_target["content_hash"],
        },
    )
    assert wrong_screen.status_code == 404
    assert wrong_screen.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    def resolve(index: int) -> dict[str, Any]:
        device, device_headers = devices_and_headers[index]
        response = device.get(
            "/api/v1/device/capabilities/current",
            headers={
                **device_headers,
                "X-Runtime-Session-ID": "same-caller-session-label",
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    with ThreadPoolExecutor(max_workers=3) as executor:
        current = list(executor.map(resolve, range(3)))

    assert {item["screen_id"] for item in current} == {screen["screen_id"] for screen in screens}
    assert {item["capabilities"]["profile_version_id"] for item in current} == {
        profile["head_version_id"] for profile in profiles
    }
    assert {item["state"] for item in current} == {"APPLIED"}
    assert {item["runtime_context"]["session_id"] for item in current} == {"same-caller-session-label"}
    assert len({item["runtime_context"]["isolation_key_sha256"] for item in current}) == 3
    assert all(len(item["runtime_context"]["isolation_key_sha256"]) == 64 for item in current)

    effective = [
        implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/effective-capabilities"
        )
        for screen in screens
    ]
    assert all(response.status_code == 200 for response in effective)
    effective_payloads = [response.json() for response in effective]
    assert {item["screen_id"] for item in effective_payloads} == {screen["screen_id"] for screen in screens}
    assert {item["effective"]["profile_version_id"] for item in effective_payloads} == {
        profile["head_version_id"] for profile in profiles
    }
    assert all(item["state"] == "APPLIED" for item in effective_payloads)


def test_p21_backup_restore_tamper_and_retention_preserve_sidecars(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = p21_control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    profile = _create_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        preset_id="mock_presenter",
        suffix="backup-restore",
    )
    release = _create_p2_1_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screen["screen_id"],
        profile_version_id=profile["head_version_id"],
        suffix="backup-restore",
    )
    immutable_replace_attempts = (
        (
            """
            INSERT OR REPLACE INTO capability_profile_versions
            SELECT * FROM capability_profile_versions
            WHERE profile_version_id = ?
            """,
            (profile["head_version_id"],),
        ),
        (
            """
            INSERT OR REPLACE INTO config_draft_capability_assignments
            SELECT * FROM config_draft_capability_assignments
            WHERE draft_id = ? AND draft_revision = ?
            """,
            (
                release["normal_provenance"]["draft_id"],
                release["normal_provenance"]["draft_revision"],
            ),
        ),
        (
            """
            INSERT OR REPLACE INTO release_target_capability_snapshots
            SELECT * FROM release_target_capability_snapshots
            WHERE release_target_id = ?
            """,
            (release["targets"][0]["release_target_id"],),
        ),
    )
    for sql, parameters in immutable_replace_attempts:
        connection = service.store.connect()
        try:
            assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(sql, parameters)
            connection.rollback()
        finally:
            connection.close()

    protected_tables = (
        "users",
        "device_enrollments",
        "device_credential_families",
        "device_credentials",
        "config_releases",
        "release_targets",
        "publications",
        "publication_targets",
        "capability_profiles",
        "capability_profile_versions",
        "config_draft_capability_assignments",
        "release_target_capability_snapshots",
        "security_audit_events",
    )
    with service.store.connect() as connection:
        protected_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in protected_tables
        }
    retention = service.p1_3.record_runtime_detail_retention(
        retention_days=3,
        deleted_runtime_detail_count=7,
    )
    assert retention["recorded"] is True
    assert (
        retention["protected_control_plane_counts_hash"]
        == hashlib.sha256(canonical_json(protected_counts).encode()).hexdigest()
    )
    with service.store.connect() as connection:
        assert {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in protected_tables
            if table != "security_audit_events"
        } == {table: count for table, count in protected_counts.items() if table != "security_audit_events"}

    created = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p21-backup-create"},
        ),
        json={"reason": "preserve P2.1 immutable sidecars"},
    )
    assert created.status_code == 201, created.text
    backup = created.json()
    for table in (
        "capability_profiles",
        "capability_profile_versions",
        "config_draft_capability_assignments",
        "release_target_capability_snapshots",
    ):
        assert backup["safe_row_counts"][table] >= 1
    verified = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p21-backup-verify"},
        ),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["outcome"] == "VERIFIED"

    for column, value in (
        ("capability_envelope_hash", "0" * 64),
        ("profile_version_id", "cpv_missing_reference"),
    ):
        tampered_path = database_path.parent / f"tampered-{column}.db"
        source = service.store.connect()
        target = sqlite3.connect(tampered_path)
        try:
            source.backup(target)
            target.execute("DROP TRIGGER release_target_capability_snapshots_no_update")
            target.execute(
                f"""
                UPDATE release_target_capability_snapshots
                SET {column} = ?
                WHERE release_target_id = ?
                """,
                (value, release["targets"][0]["release_target_id"]),
            )
            target.commit()
        finally:
            target.close()
            source.close()
        with pytest.raises(BackupIntegrityError):
            BackupManager._validate_snapshot(tampered_path.read_bytes())

    changed_spec = profile["head_version"]["spec"]
    changed_spec["dora"]["timeout_ms"] = 6000
    changed = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-post-backup-version",
            },
        ),
        json={"spec": changed_spec},
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["head_version_id"] != profile["head_version_id"]

    plan_response = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p21-restore-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    restore_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "restore P2.1 profile sidecars",
    }
    action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        restore_payload,
        "p21-restore-request",
        extra_headers={"If-Match": plan["etag"]},
    )
    approve_action(
        admin_b,
        csrf_b,
        action,
        key="p21-restore-approve",
    )
    restored = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p21-restore-execute",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["kind"] == "RESTORE_COMPLETED"

    relogged, _ = login(app, "admin-a")
    restored_profile = relogged.get(f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}")
    assert restored_profile.status_code == 200, restored_profile.text
    assert restored_profile.json()["head_version_id"] == profile["head_version_id"]
    restored_release = relogged.get(f"/api/v1/control-plane/config-releases/{release['release_id']}")
    assert restored_release.status_code == 200, restored_release.text
    assert (
        restored_release.json()["targets"][0]["capability_snapshot"]["profile_version_id"]
        == profile["head_version_id"]
    )
