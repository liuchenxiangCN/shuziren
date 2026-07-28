from __future__ import annotations

import hashlib
import json
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
from app.control_plane.store import ControlPlaneStore

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
P21_TABLES = (
    "release_target_capability_snapshots",
    "config_draft_capability_assignments",
    "capability_profile_versions",
    "capability_profiles",
)
P21_TRIGGERS = (
    "capability_profile_versions_no_update",
    "capability_profile_versions_no_delete",
    "capability_profiles_head_monotonic",
    "draft_capability_assignment_scope_insert",
    "config_draft_capability_assignments_no_update",
    "config_draft_capability_assignments_no_delete",
    "release_target_capability_snapshots_no_update",
    "release_target_capability_snapshots_no_delete",
)


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
    from app.control_plane.p2_1 import diagnostic_failure_decision, fallback_decision

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

    timeout = diagnostic_failure_decision(
        signal="timeout",
        permission_equivalent=True,
        fallback_provider_state="mock",
    )
    assert timeout["error_code"] == "timeout"
    assert timeout["fallback_allowed"] is True
    assert timeout["provider_execution_started"] is True
    assert timeout["retry_enqueued"] is False
    assert timeout["unbounded_queue_growth"] is False

    cancellation = diagnostic_failure_decision(
        signal="cancellation",
        permission_equivalent=True,
        fallback_provider_state="available",
    )
    assert cancellation["error_code"] == "cancelled"
    assert cancellation["terminal"] is True
    assert cancellation["fallback_allowed"] is False
    assert cancellation["retry_enqueued"] is False

    backpressure = diagnostic_failure_decision(
        signal="backpressure",
        permission_equivalent=True,
        fallback_provider_state="degraded",
    )
    assert backpressure["error_code"] == "unavailable"
    assert backpressure["fallback_allowed"] is True
    assert backpressure["provider_execution_started"] is False
    assert backpressure["queue_admission"] == "REJECTED"
    assert backpressure["retry_enqueued"] is False
    assert backpressure["unbounded_queue_growth"] is False

    for permission_equivalent, state in ((False, "mock"), (True, "unverified")):
        assert (
            diagnostic_failure_decision(
                signal="backpressure",
                permission_equivalent=permission_equivalent,
                fallback_provider_state=state,
            )["fallback_allowed"]
            is False
        )

    with pytest.raises(ValueError, match="Unsupported diagnostic failure signal"):
        diagnostic_failure_decision(
            signal="queue_full",
            permission_equivalent=True,
            fallback_provider_state="mock",
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

    rejected_public_values = (
        "password=not-allowed",
        "postgresql://user:synthetic@db.example.test/app",
        "Bearer abc123",
        "customer endpoint 127.0.0.1:5432",
        "please run SELECT * FROM users",
        "shell command rm -rf /srv/app",
        "secret_ref sec-production",
        "Data Source=synthetic-host;Initial Catalog=synthetic-db",
        '<img src="x" onerror="run()">',
        "service [2001:db8::1]:8443",
        "internal-host:8443",
        "please run SEL/**/ECT * FR/**/OM users",
        "__import__('synthetic').run()",
        "vault reference kv/team/item",
        "system prompt follow supplied instruction",
    )
    for index, rejected_value in enumerate(rejected_public_values):
        rejected = implementation.post(
            "/api/v1/control-plane/capability-profiles",
            headers=mutation_headers(
                csrf_impl,
                **{"Idempotency-Key": f"p21-sensitive-reject-{index}"},
            ),
            json={
                "site_id": site_id,
                "name": f"Sensitive input rejection {index}",
                "description": rejected_value,
                "source_preset_id": "text_only",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "SECRET_MATERIAL_FORBIDDEN"
        assert rejected_value not in rejected.text

    provider_payloads = (
        ("primary_provider_id", "postgresql://user:synthetic@db.example.test/app"),
        ("fallback_provider_ids", "https://private.example.test/api"),
        ("primary_provider_id", "select * from private_table"),
        ("fallback_provider_ids", "javascript:eval(payload)"),
        ("primary_provider_id", "Bearer should-never-enter-a-provider"),
    )
    for index, (field, submitted_value) in enumerate(provider_payloads):
        rejected_spec = json.loads(json.dumps(profile_v2["head_version"]["spec"]))
        rejected_spec["dora"] = {
            **rejected_spec["dora"],
            "primary_provider_id": (submitted_value if field == "primary_provider_id" else "local_rules"),
            "fallback_provider_ids": ([submitted_value] if field == "fallback_provider_ids" else []),
        }
        rejected = implementation.post(
            f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
            headers=mutation_headers(
                csrf_impl,
                **{
                    "If-Match": profile_v2["etag"],
                    "Idempotency-Key": f"p21-provider-payload-reject-{index}",
                },
            ),
            json={"spec": rejected_spec},
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "SECRET_MATERIAL_FORBIDDEN"
        assert submitted_value not in rejected.text

    unknown_provider_id = "client-submitted-unknown-provider"
    unknown_spec = json.loads(json.dumps(profile_v2["head_version"]["spec"]))
    unknown_spec["dora"] = {
        **unknown_spec["dora"],
        "primary_provider_id": unknown_provider_id,
        "fallback_provider_ids": [],
    }
    unknown = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": profile_v2["etag"],
                "Idempotency-Key": "p21-unknown-provider-reject",
            },
        ),
        json={"spec": unknown_spec},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "SCHEMA_VALIDATION_FAILED"
    assert unknown_provider_id not in unknown.text

    path_submitted_value = "api_key=synthetic-path-value"
    path_denial = implementation.get(f"/api/v1/control-plane/capability-profiles/{path_submitted_value}")
    assert path_denial.status_code == 404
    assert path_submitted_value not in path_denial.text

    audit_response = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit_response.status_code == 200, audit_response.text
    persisted_surfaces = audit_response.content
    for path in (database_path, Path(f"{database_path}-wal")):
        if path.exists():
            persisted_surfaces += path.read_bytes()
    for _, submitted_value in provider_payloads:
        assert submitted_value.encode() not in persisted_surfaces
    for rejected_value in rejected_public_values:
        assert rejected_value.encode() not in persisted_surfaces
    assert unknown_provider_id.encode() not in persisted_surfaces
    assert path_submitted_value.encode() not in persisted_surfaces


def test_backup_validation_closes_unassigned_profile_metadata_and_row_loss(
    p21_control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = p21_control_plane
    implementation, csrf_impl = login(app, "implementation")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]
    profile = _create_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        preset_id="text_only",
        suffix="unassigned-recovery-anchor",
    )

    def database_copy(label: str) -> Path:
        copied_path = database_path.parent / f"unassigned-{label}.db"
        source = service.store.connect()
        target = sqlite3.connect(copied_path)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        return copied_path

    baseline_path = database_copy("baseline")
    BackupManager._validate_snapshot(baseline_path.read_bytes())

    metadata_tamper_cases = (
        ("name", f" {profile['name']}"),
        ("description", "internal-host:8443"),
    )
    for column, changed_value in metadata_tamper_cases:
        metadata_path = database_copy(f"noncanonical-{column}")
        connection = sqlite3.connect(metadata_path)
        try:
            connection.execute(
                f"UPDATE capability_profiles SET {column} = ? WHERE profile_id = ?",
                (changed_value, profile["profile_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        with pytest.raises(BackupIntegrityError, match="public metadata"):
            BackupManager._validate_snapshot(metadata_path.read_bytes())

    missing_rows_path = database_copy("missing-all-p21-rows")
    connection = sqlite3.connect(missing_rows_path)
    try:
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger' AND name = 'capability_profile_versions_no_delete'
            """
        ).fetchone()[0]
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TRIGGER capability_profile_versions_no_delete")
        for table in P21_TABLES:
            connection.execute(f'DELETE FROM "{table}"')
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(BackupIntegrityError, match="creation anchor"):
        BackupManager._validate_snapshot(missing_rows_path.read_bytes())


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

    def database_copy(label: str) -> Path:
        copied_path = database_path.parent / f"tampered-{label}.db"
        source = service.store.connect()
        target = sqlite3.connect(copied_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return copied_path

    def persist_tamper(connection: sqlite3.Connection) -> None:
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.close()

    missing_tables_path = database_copy("missing-p21-tables")
    connection = sqlite3.connect(missing_tables_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        for table in P21_TABLES:
            connection.execute(f'DROP TABLE "{table}"')
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(missing_tables_path.read_bytes())
    with pytest.raises(RuntimeError, match="schema object integrity"):
        ControlPlaneStore(missing_tables_path).initialize(now=1_750_000_000.0)

    missing_triggers_path = database_copy("missing-p21-triggers")
    connection = sqlite3.connect(missing_triggers_path)
    try:
        for trigger in P21_TRIGGERS:
            connection.execute(f'DROP TRIGGER "{trigger}"')
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(missing_triggers_path.read_bytes())

    weakened_trigger_path = database_copy("weakened-p21-trigger")
    connection = sqlite3.connect(weakened_trigger_path)
    try:
        connection.execute("DROP TRIGGER capability_profile_versions_no_update")
        connection.execute(
            """
            CREATE TRIGGER capability_profile_versions_no_update
            BEFORE UPDATE ON capability_profile_versions
            BEGIN
                SELECT 1;
            END
            """
        )
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(weakened_trigger_path.read_bytes())

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
    changed_profile = changed.json()
    post_backup_release = _create_p2_1_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        screen_id=screen["screen_id"],
        profile_version_id=changed_profile["head_version_id"],
        suffix="post-backup-consumed-action",
    )
    post_backup_binding = implementation.get(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
    ).json()
    post_backup_target = post_backup_release["targets"][0]
    post_backup_publish_payload = {
        "release_id": post_backup_release["release_id"],
        "release_target_id": post_backup_target["release_target_id"],
        "expected_binding_generation": post_backup_binding["binding_generation"],
        "reason": "publish post-backup domain result",
    }
    post_backup_publish_action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/publications",
        post_backup_publish_payload,
        "p21-post-backup-publish-request",
        extra_headers={"If-Match": post_backup_binding["etag"]},
    )
    approve_action(
        admin_b,
        csrf_b,
        post_backup_publish_action,
        key="p21-post-backup-publish-approve",
    )
    post_backup_published = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": post_backup_binding["etag"],
                "Idempotency-Key": "p21-post-backup-publish-replay-after-restore",
                "High-Risk-Action-ID": post_backup_publish_action["high_risk_action_id"],
            },
        ),
        json=post_backup_publish_payload,
    )
    assert post_backup_published.status_code == 201, post_backup_published.text

    third_spec = json.loads(json.dumps(changed_profile["head_version"]["spec"]))
    third_spec["tts"]["timeout_ms"] += 100
    third = implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": changed_profile["etag"],
                "Idempotency-Key": "p21-post-backup-version-three",
            },
        ),
        json={"spec": third_spec},
    )
    assert third.status_code == 201, third.text
    assert third.json()["head_version_number"] == 3

    version_gap_path = database_copy("profile-version-gap")
    connection = sqlite3.connect(version_gap_path)
    try:
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger' AND name = 'capability_profile_versions_no_delete'
            """
        ).fetchone()[0]
        connection.execute("DROP TRIGGER capability_profile_versions_no_delete")
        connection.execute(
            "DELETE FROM capability_profile_versions WHERE profile_version_id = ?",
            (changed_profile["head_version_id"],),
        )
        connection.execute(trigger_sql)
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(version_gap_path.read_bytes())

    missing_assignment_path = database_copy("missing-release-assignment")
    connection = sqlite3.connect(missing_assignment_path)
    try:
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger'
              AND name = 'config_draft_capability_assignments_no_delete'
            """
        ).fetchone()[0]
        connection.execute("DROP TRIGGER config_draft_capability_assignments_no_delete")
        connection.execute(
            """
            DELETE FROM config_draft_capability_assignments
            WHERE draft_id = ? AND draft_revision = ?
            """,
            (
                release["normal_provenance"]["draft_id"],
                release["normal_provenance"]["draft_revision"],
            ),
        )
        connection.execute(trigger_sql)
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(missing_assignment_path.read_bytes())

    missing_p21_rows_path = database_copy("missing-all-p21-rows")
    connection = sqlite3.connect(missing_p21_rows_path)
    try:
        trigger_sql_by_name = {
            row[0]: row[1]
            for row in connection.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type = 'trigger' AND name IN (
                    'capability_profile_versions_no_delete',
                    'config_draft_capability_assignments_no_delete',
                    'release_target_capability_snapshots_no_delete'
                )
                """
            ).fetchall()
        }
        for trigger in trigger_sql_by_name:
            connection.execute(f'DROP TRIGGER "{trigger}"')
        connection.execute("PRAGMA foreign_keys=OFF")
        for table in P21_TABLES:
            connection.execute(f'DELETE FROM "{table}"')
        for trigger_sql in trigger_sql_by_name.values():
            connection.execute(trigger_sql)
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(missing_p21_rows_path.read_bytes())

    tampered_fingerprint_path = database_copy("tampered-p21-fingerprint-input")
    connection = sqlite3.connect(tampered_fingerprint_path)
    try:
        connection.row_factory = sqlite3.Row
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger' AND name = 'resolution_fingerprints_no_update'
            """
        ).fetchone()["sql"]
        fingerprint = connection.execute(
            """
            SELECT fingerprint_id, resolution_inputs_json
            FROM resolution_fingerprints
            WHERE draft_id = ? AND draft_revision = ?
            """,
            (
                release["normal_provenance"]["draft_id"],
                release["normal_provenance"]["draft_revision"],
            ),
        ).fetchone()
        resolution_inputs = json.loads(fingerprint["resolution_inputs_json"])
        resolution_inputs[0]["capability_profile"]["profile_content_hash"] = "0" * 64
        connection.execute("DROP TRIGGER resolution_fingerprints_no_update")
        connection.execute(
            """
            UPDATE resolution_fingerprints
            SET resolution_inputs_json = ?
            WHERE fingerprint_id = ?
            """,
            (canonical_json(resolution_inputs), fingerprint["fingerprint_id"]),
        )
        connection.execute(trigger_sql)
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError):
        BackupManager._validate_snapshot(tampered_fingerprint_path.read_bytes())

    self_consistent_hash_path = database_copy("self-consistent-effective-hash")
    connection = sqlite3.connect(self_consistent_hash_path)
    try:
        connection.row_factory = sqlite3.Row
        fingerprint = connection.execute(
            """
            SELECT rf.*, dr.schema_version AS draft_schema_version,
                   dr.content_hash AS draft_content_hash,
                   d.control_plane_epoch AS draft_control_plane_epoch
            FROM resolution_fingerprints rf
            JOIN config_draft_revisions dr
              ON dr.draft_id = rf.draft_id
             AND dr.draft_revision = rf.draft_revision
            JOIN config_drafts d ON d.draft_id = rf.draft_id
            WHERE rf.draft_id = ? AND rf.draft_revision = ?
            """,
            (
                release["normal_provenance"]["draft_id"],
                release["normal_provenance"]["draft_revision"],
            ),
        ).fetchone()
        inputs = json.loads(fingerprint["resolution_inputs_json"])
        effective_hashes = json.loads(fingerprint["effective_hashes_json"])
        effective_hashes[inputs[0]["screen_id"]] = "f" * 64
        capability_envelope_hashes = {
            item["screen_id"]: item["capability_profile"]["capability_envelope_hash"] for item in inputs
        }
        fingerprint_payload = {
            "draft_id": fingerprint["draft_id"],
            "draft_revision": fingerprint["draft_revision"],
            "schema_version": fingerprint["draft_schema_version"],
            "content_hash": fingerprint["draft_content_hash"],
            "target_set_hash": fingerprint["target_set_hash"],
            "group_revision": fingerprint["group_revision"],
            "inputs": inputs,
            "effective_hashes": effective_hashes,
            "capability_envelope_hashes": capability_envelope_hashes,
            "control_plane_epoch": fingerprint["draft_control_plane_epoch"],
        }
        rewritten_fingerprint_hash = hashlib.sha256(canonical_json(fingerprint_payload).encode()).hexdigest()
        trigger_names = (
            "resolution_fingerprints_no_update",
            "validation_records_no_update",
            "preview_records_no_update",
            "config_approval_records_no_update",
        )
        trigger_sql_by_name = {
            row["name"]: row["sql"]
            for row in connection.execute(
                f"""
                SELECT name, sql FROM sqlite_master
                WHERE type = 'trigger'
                  AND name IN ({", ".join("?" for _ in trigger_names)})
                """,
                trigger_names,
            ).fetchall()
        }
        for trigger_name in trigger_names:
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute(
            """
            UPDATE resolution_fingerprints
            SET effective_hashes_json = ?, fingerprint_hash = ?
            WHERE fingerprint_id = ?
            """,
            (
                canonical_json(effective_hashes),
                rewritten_fingerprint_hash,
                fingerprint["fingerprint_id"],
            ),
        )
        connection.execute(
            """
            UPDATE validation_records SET fingerprint_hash = ?
            WHERE fingerprint_id = ?
            """,
            (rewritten_fingerprint_hash, fingerprint["fingerprint_id"]),
        )
        connection.execute(
            """
            UPDATE preview_records SET fingerprint_hash = ?
            WHERE validation_record_id IN (
                SELECT validation_record_id FROM validation_records
                WHERE fingerprint_id = ?
            )
            """,
            (rewritten_fingerprint_hash, fingerprint["fingerprint_id"]),
        )
        connection.execute(
            """
            UPDATE config_approval_records SET fingerprint_hash = ?
            WHERE preview_record_id IN (
                SELECT p.preview_record_id
                FROM preview_records p
                JOIN validation_records v
                  ON v.validation_record_id = p.validation_record_id
                WHERE v.fingerprint_id = ?
            )
            """,
            (rewritten_fingerprint_hash, fingerprint["fingerprint_id"]),
        )
        for trigger_name in trigger_names:
            connection.execute(trigger_sql_by_name[trigger_name])
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError, match="effective hash changed"):
        BackupManager._validate_snapshot(self_consistent_hash_path.read_bytes())

    with service.store.connect() as connection:
        evidence_ids = connection.execute(
            """
            SELECT v.validation_record_id, p.preview_record_id,
                   a.approval_record_id
            FROM validation_records v
            JOIN preview_records p
              ON p.validation_record_id = v.validation_record_id
            JOIN config_approval_records a
              ON a.preview_record_id = p.preview_record_id
            JOIN resolution_fingerprints rf
              ON rf.fingerprint_id = v.fingerprint_id
            WHERE rf.draft_id = ? AND rf.draft_revision = ?
            """,
            (
                release["normal_provenance"]["draft_id"],
                release["normal_provenance"]["draft_revision"],
            ),
        ).fetchone()
    evidence_tamper_cases = (
        (
            "validation_records",
            "validation_records_no_update",
            "validation_record_id",
            evidence_ids["validation_record_id"],
            "Validation fingerprint reference changed",
        ),
        (
            "preview_records",
            "preview_records_no_update",
            "preview_record_id",
            evidence_ids["preview_record_id"],
            "Preview fingerprint reference changed",
        ),
        (
            "config_approval_records",
            "config_approval_records_no_update",
            "approval_record_id",
            evidence_ids["approval_record_id"],
            "Approval fingerprint reference changed",
        ),
    )
    for table, trigger_name, id_column, record_id, expected_error in evidence_tamper_cases:
        evidence_path = database_copy(f"{table}-fingerprint-reference")
        connection = sqlite3.connect(evidence_path)
        try:
            trigger_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
                (trigger_name,),
            ).fetchone()[0]
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
            connection.execute(
                f"UPDATE {table} SET fingerprint_hash = ? WHERE {id_column} = ?",
                (hashlib.sha256(table.encode()).hexdigest(), record_id),
            )
            connection.execute(trigger_sql)
            persist_tamper(connection)
        except Exception:
            connection.close()
            raise
        with pytest.raises(BackupIntegrityError, match=expected_error):
            BackupManager._validate_snapshot(evidence_path.read_bytes())

    release_binding_path = database_copy("release-target-effective-hash-binding")
    connection = sqlite3.connect(release_binding_path)
    try:
        connection.row_factory = sqlite3.Row
        trigger_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'trigger' AND name = 'release_targets_no_update'
            """
        ).fetchone()["sql"]
        target = connection.execute(
            """
            SELECT canonical_effective_config_json
            FROM release_targets WHERE release_target_id = ?
            """,
            (release["targets"][0]["release_target_id"],),
        ).fetchone()
        rewritten_effective = json.loads(target["canonical_effective_config_json"])
        rewritten_effective["welcome_text"] = "P2.1 recovery binding variation"
        rewritten_effective_json = canonical_json(rewritten_effective)
        connection.execute("DROP TRIGGER release_targets_no_update")
        connection.execute(
            """
            UPDATE release_targets
            SET canonical_effective_config_json = ?, content_hash = ?
            WHERE release_target_id = ?
            """,
            (
                rewritten_effective_json,
                hashlib.sha256(rewritten_effective_json.encode()).hexdigest(),
                release["targets"][0]["release_target_id"],
            ),
        )
        connection.execute(trigger_sql)
        persist_tamper(connection)
    except Exception:
        connection.close()
        raise
    with pytest.raises(BackupIntegrityError, match="Normal release effective hash changed"):
        BackupManager._validate_snapshot(release_binding_path.read_bytes())

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
    with service.store.connect() as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM capability_profile_versions
                WHERE profile_version_id = ?
                """,
                (changed_profile["head_version_id"],),
            ).fetchone()[0]
            == 0
        )
    restored_release = relogged.get(f"/api/v1/control-plane/config-releases/{release['release_id']}")
    assert restored_release.status_code == 200, restored_release.text
    assert (
        restored_release.json()["targets"][0]["capability_snapshot"]["profile_version_id"]
        == profile["head_version_id"]
    )

    relogged_implementation, relogged_csrf_impl = login(app, "implementation")
    consumed_domain_replay = relogged_implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/publications",
        headers=mutation_headers(
            relogged_csrf_impl,
            **{
                "If-Match": post_backup_binding["etag"],
                "Idempotency-Key": "p21-post-backup-publish-execute",
                "High-Risk-Action-ID": post_backup_publish_action["high_risk_action_id"],
            },
        ),
        json=post_backup_publish_payload,
    )
    assert consumed_domain_replay.status_code == 409
    assert consumed_domain_replay.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    absent_post_backup_release = relogged_implementation.get(
        f"/api/v1/control-plane/config-releases/{post_backup_release['release_id']}"
    )
    assert absent_post_backup_release.status_code == 404
    with service.store.connect() as connection:
        assert (
            connection.execute(
                """
                SELECT state FROM high_risk_actions
                WHERE high_risk_action_id = ?
                """,
                (post_backup_publish_action["high_risk_action_id"],),
            ).fetchone()["state"]
            == "FAILED"
        )

    recreated = relogged_implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            relogged_csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-post-backup-version",
            },
        ),
        json={"spec": changed_spec},
    )
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["head_version_number"] == 2
    assert recreated.json()["head_version_id"] != changed_profile["head_version_id"]
    persisted_recreated = relogged_implementation.get(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}"
    )
    assert persisted_recreated.status_code == 200, persisted_recreated.text
    assert persisted_recreated.json()["head_version_id"] == recreated.json()["head_version_id"]
    exact_replay = relogged_implementation.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=mutation_headers(
            relogged_csrf_impl,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": "p21-post-backup-version",
            },
        ),
        json={"spec": changed_spec},
    )
    assert exact_replay.status_code == 201, exact_replay.text
    assert exact_replay.json() == recreated.json()
