from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.control_plane.errors import ControlPlaneError
from app.control_plane.router import (
    control_plane_error_handler,
    router,
    sanitized_validation_errors,
)
from app.control_plane.security import PurposeKeyring, canonical_json, validate_password
from app.control_plane.service import ROLE_PERMISSIONS, ControlPlaneService
from app.control_plane.store import LOGICAL_SCHEMA_VERSION

ORIGIN = "https://manage.test"
PASSWORDS = {
    username: f"test-only-{secrets.token_urlsafe(18)}"
    for username in ("admin-a", "admin-b", "implementation", "auditor")
}


@pytest.fixture()
def control_plane(tmp_path: Path) -> tuple[FastAPI, ControlPlaneService, Path]:
    database_path = tmp_path / "control-plane.db"
    root_key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    service = ControlPlaneService(
        str(database_path),
        root_key,
        preview_mode=True,
    )
    service.initialize_preview(
        tenant_id="tenant-test",
        deployment_id="deployment-test",
        screen_id="screen-trust-fixture",
        identities=[
            {
                "username": "admin-a",
                "display_name": "Admin A",
                "role_id": "platform_admin",
                "password": PASSWORDS["admin-a"],
            },
            {
                "username": "admin-b",
                "display_name": "Admin B",
                "role_id": "platform_admin",
                "password": PASSWORDS["admin-b"],
            },
            {
                "username": "implementation",
                "display_name": "Implementation",
                "role_id": "implementation_engineer",
                "password": PASSWORDS["implementation"],
            },
            {
                "username": "auditor",
                "display_name": "Auditor",
                "role_id": "auditor",
                "password": PASSWORDS["auditor"],
            },
        ],
    )
    app = FastAPI()
    app.state.control_plane_service = service
    app.state.control_plane_allowed_origins = (ORIGIN,)
    app.include_router(router)
    app.add_exception_handler(ControlPlaneError, control_plane_error_handler)

    async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "details": sanitized_validation_errors(exc)}},
        )

    app.add_exception_handler(RequestValidationError, validation_handler)
    return app, service, database_path


def login(app: FastAPI, username: str) -> tuple[TestClient, str]:
    client = TestClient(app, base_url="https://manage.test")
    response = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": username, "password": PASSWORDS[username]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["normalized_username"] == username
    assert "__Host-shuziren_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    csrf = response.headers["x-csrf-token"]
    assert csrf
    assert csrf not in response.text
    return client, csrf


def mutation_headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}


def request_action(
    client: TestClient,
    csrf: str,
    path: str,
    payload: dict[str, Any],
    key: str,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = mutation_headers(csrf, **{"Idempotency-Key": key})
    headers.update(extra_headers or {})
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 202, response.text
    result = response.json()
    assert result["state"] == "PENDING"
    return result


def approve_action(
    client: TestClient,
    csrf: str,
    action: dict[str, Any],
    *,
    key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=mutation_headers(
            csrf,
            **{
                "Idempotency-Key": key,
                "If-Match": action["etag"],
            },
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "independent approval",
        },
    )
    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["state"] == "APPROVED"
    return approved


def test_schema_is_repeatable_and_preview_is_explicit(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
    tmp_path: Path,
) -> None:
    _, service, database_path = control_plane
    service.store.initialize(service.clock())
    assert service.status()["logical_schema_version"] == LOGICAL_SCHEMA_VERSION
    assert service.status()["profile"] == "DEVELOPMENT_PREVIEW"
    assert service.status()["production_ready"] is False
    with pytest.raises(ValueError):
        service.initialize_preview(
            tenant_id="tenant-test",
            deployment_id="deployment-test",
            screen_id="screen-trust-fixture",
            identities=[],
        )
    assert database_path.exists()
    production_like = ControlPlaneService(
        str(tmp_path / "uninitialized.db"),
        PurposeKeyring.generate_root_base64(),
        preview_mode=False,
    )
    assert production_like.status()["initialized"] is False
    with pytest.raises(ControlPlaneError) as disabled_preview:
        production_like.initialize_preview(
            tenant_id="must-not-exist",
            deployment_id="must-not-exist",
            screen_id="must-not-exist",
            identities=[],
        )
    assert disabled_preview.value.code == "FORBIDDEN"
    with production_like.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM control_plane_metadata").fetchone()[0] == 0
    with sqlite3.connect(database_path) as connection:
        verifier = connection.execute(
            "SELECT password_verifier FROM users WHERE normalized_username = 'admin-a'"
        ).fetchone()[0]
        assert verifier.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
        event_id = connection.execute(
            "SELECT event_id FROM security_audit_events ORDER BY sequence LIMIT 1"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE security_audit_events SET reason = 'tamper' WHERE event_id = ?",
                (event_id,),
            )


@pytest.mark.parametrize(
    "password",
    ["short", "password123456", "admin1234567890", "printing-only-but-not\n"],
)
def test_password_policy_rejects_short_common_or_nonprinting_values(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password(password)
    with pytest.raises(ValueError):
        validate_password("long-user-name-for-login", username="long-user-name-for-login")


def test_exact_origin_secure_session_csrf_rbac_and_lockout(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = control_plane
    client = TestClient(app, base_url="https://manage.test")
    missing_origin = client.post(
        "/api/v1/control-plane/auth/sessions",
        json={"username": "admin-a", "password": PASSWORDS["admin-a"]},
    )
    assert missing_origin.status_code == 403
    assert missing_origin.json()["error"]["code"] == "FORBIDDEN"

    admin, admin_csrf = login(app, "admin-a")
    role_catalog = admin.get("/api/v1/control-plane/role-definitions")
    assert role_catalog.status_code == 200
    assert {
        item["role_id"]: tuple(item["permissions"]) for item in role_catalog.json()["items"]
    } == ROLE_PERMISSIONS
    session = admin.get("/api/v1/control-plane/auth/session")
    assert session.status_code == 200
    assert "csrf" not in session.text.casefold()
    assert PASSWORDS["admin-a"] not in session.text
    reauthenticated = admin.post(
        "/api/v1/control-plane/auth/session:reauthenticate",
        headers=mutation_headers(
            admin_csrf,
            **{
                "Idempotency-Key": "reauthenticate-session",
                "If-Match": session.json()["etag"],
            },
        ),
        json={"password": PASSWORDS["admin-a"]},
    )
    assert reauthenticated.status_code == 200, reauthenticated.text
    assert reauthenticated.json()["auth_session_id"] != session.json()["auth_session_id"]
    admin_csrf = reauthenticated.headers["x-csrf-token"]

    no_csrf = admin.post(
        "/api/v1/control-plane/users",
        headers={"Origin": ORIGIN, "Idempotency-Key": "missing-csrf"},
        json={
            "normalized_username": "candidate",
            "display_name": "Candidate",
            "reason": "test missing csrf",
        },
    )
    assert no_csrf.status_code == 403

    auditor, _ = login(app, "auditor")
    assert auditor.get("/api/v1/control-plane/audit-events").status_code == 200
    forbidden = auditor.get("/api/v1/control-plane/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    for attempt in range(5):
        denied = client.post(
            "/api/v1/control-plane/auth/sessions",
            headers={"Origin": ORIGIN},
            json={"username": "implementation", "password": f"wrong-password-{attempt}"},
        )
        assert denied.status_code == 401
    locked = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": "implementation", "password": PASSWORDS["implementation"]},
    )
    unknown = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": "account-does-not-exist", "password": PASSWORDS["implementation"]},
    )
    assert locked.status_code == 401
    assert locked.json()["error"] == unknown.json()["error"]
    assert locked.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "lock" not in locked.text.casefold()

    with sqlite3.connect(database_path) as connection:
        first_lock = connection.execute(
            """
            SELECT lock_level, locked_until - last_lock_at
            FROM users WHERE normalized_username = 'implementation'
            """
        ).fetchone()
        assert first_lock == (1, 15 * 60)
        connection.execute("UPDATE users SET locked_until = 0 WHERE normalized_username = 'implementation'")
        connection.commit()
    for attempt in range(5):
        assert (
            client.post(
                "/api/v1/control-plane/auth/sessions",
                headers={"Origin": ORIGIN},
                json={"username": "implementation", "password": f"second-lock-{attempt}"},
            ).status_code
            == 401
        )
    with sqlite3.connect(database_path) as connection:
        second_lock = connection.execute(
            """
            SELECT lock_level, locked_until - last_lock_at
            FROM users WHERE normalized_username = 'implementation'
            """
        ).fetchone()
        assert second_lock == (2, 30 * 60)

    sign_out = admin.delete(
        "/api/v1/control-plane/auth/session",
        headers=mutation_headers(admin_csrf),
    )
    assert sign_out.status_code == 200
    assert admin.get("/api/v1/control-plane/auth/session").status_code == 401


def test_session_rotation_duplicate_cookie_and_terminal_expiry(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = control_plane
    client, original_csrf = login(app, "admin-a")
    current = client.get("/api/v1/control-plane/auth/session").json()

    refreshed = client.post(
        "/api/v1/control-plane/auth/session:refresh-csrf",
        headers={"Origin": ORIGIN},
    )
    assert refreshed.status_code == 200
    rotated_csrf = refreshed.headers["x-csrf-token"]
    assert rotated_csrf != original_csrf
    rejected_old_csrf = client.delete(
        "/api/v1/control-plane/auth/session",
        headers=mutation_headers(original_csrf),
    )
    assert rejected_old_csrf.status_code == 403

    duplicate_cookie = TestClient(app, base_url="https://manage.test").get(
        "/api/v1/control-plane/auth/session",
        headers={"Cookie": ("__Host-shuziren_session=first; __Host-shuziren_session=second")},
    )
    assert duplicate_cookie.status_code == 401

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE auth_sessions SET idle_expires_at = 0 WHERE auth_session_id = ?",
            (current["auth_session_id"],),
        )
        connection.commit()
    assert client.get("/api/v1/control-plane/auth/session").status_code == 401
    with sqlite3.connect(database_path) as connection:
        state = connection.execute(
            "SELECT state FROM auth_sessions WHERE auth_session_id = ?",
            (current["auth_session_id"],),
        ).fetchone()[0]
        assert state == "IDLE_EXPIRED"

    absolute_client, _ = login(app, "admin-b")
    absolute = absolute_client.get("/api/v1/control-plane/auth/session").json()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE auth_sessions SET absolute_expires_at = 0 WHERE auth_session_id = ?",
            (absolute["auth_session_id"],),
        )
        connection.commit()
    assert absolute_client.get("/api/v1/control-plane/auth/session").status_code == 401
    with sqlite3.connect(database_path) as connection:
        state = connection.execute(
            "SELECT state FROM auth_sessions WHERE auth_session_id = ?",
            (absolute["auth_session_id"],),
        ).fetchone()[0]
        assert state == "ABSOLUTE_EXPIRED"


def test_different_user_approval_binds_exact_user_creation(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    payload = {
        "normalized_username": "new-auditor",
        "display_name": "New Auditor",
        "reason": "create a separately governed user",
    }
    action = request_action(
        admin_a,
        csrf_a,
        "/api/v1/control-plane/users",
        payload,
        "create-user-request",
    )
    with sqlite3.connect(database_path) as connection:
        stored_idempotency = connection.execute(
            """
            SELECT idempotency_key_digest, idempotency_hmac_key_id
            FROM idempotency_records
            WHERE phase = 'request:createUser'
            """
        ).fetchone()
    stored_key_digest = stored_idempotency[0]
    assert stored_key_digest == service.keys.digest(
        "SENSITIVE_IDEMPOTENCY_HMAC",
        "create-user-request",
    )
    assert stored_idempotency[1] == service.keys.key_id("SENSITIVE_IDEMPOTENCY_HMAC")
    assert stored_key_digest != hashlib.sha256(b"create-user-request").hexdigest()
    changed_idempotency = admin_a.post(
        "/api/v1/control-plane/users",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "create-user-request"},
        ),
        json={**payload, "display_name": "Different idempotent content"},
    )
    assert changed_idempotency.status_code == 409
    assert changed_idempotency.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    before = admin_a.get("/api/v1/control-plane/users").json()["items"]
    assert all(user["normalized_username"] != "new-auditor" for user in before)

    self_approval = admin_a.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "self-approval", "If-Match": action["etag"]},
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "must fail self approval",
        },
    )
    assert self_approval.status_code == 403

    stale_approval = admin_b.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=mutation_headers(
            csrf_b,
            **{
                "Idempotency-Key": "stale-approval",
                "If-Match": '"high-risk-action:999"',
            },
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "must reject a stale action version",
        },
    )
    assert stale_approval.status_code == 409
    assert stale_approval.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    approved = approve_action(admin_b, csrf_b, action, key="approve-user")
    approval_replay = admin_b.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=mutation_headers(
            csrf_b,
            **{"Idempotency-Key": "approve-user", "If-Match": action["etag"]},
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "independent approval",
        },
    )
    assert approval_replay.status_code == 200
    assert approval_replay.json() == approved
    changed = admin_a.post(
        "/api/v1/control-plane/users",
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "execute-user-changed",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json={**payload, "display_name": "Changed After Approval"},
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "HIGH_RISK_ACTION_MISMATCH"

    executed = admin_a.post(
        "/api/v1/control-plane/users",
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "execute-user",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert executed.status_code == 201, executed.text
    created = executed.json()["user"]
    assert created["account_state"] == "PROVISIONING"
    assert created["role_assignments"] == []
    assert "password" not in executed.text.casefold()

    with sqlite3.connect(database_path) as connection:
        stored = connection.execute(
            "SELECT password_verifier FROM users WHERE user_id = ?",
            (created["user_id"],),
        ).fetchone()
        assert stored == (None,)

    expiring_action = request_action(
        admin_a,
        csrf_a,
        "/api/v1/control-plane/users",
        {
            "normalized_username": "must-expire",
            "display_name": "Must Expire",
            "reason": "prove terminal action expiry",
        },
        "request-expiring-user",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE high_risk_actions SET expires_at = 0
            WHERE high_risk_action_id = ?
            """,
            (expiring_action["high_risk_action_id"],),
        )
        connection.commit()
    expired_approval = admin_b.post(
        (f"/api/v1/control-plane/high-risk-actions/{expiring_action['high_risk_action_id']}:approve"),
        headers=mutation_headers(
            csrf_b,
            **{
                "Idempotency-Key": "approve-expired-user",
                "If-Match": expiring_action["etag"],
            },
        ),
        json={
            "expected_request_digest": expiring_action["request_digest"],
            "reason": "must remain expired",
        },
    )
    assert expired_approval.status_code == 409
    assert expired_approval.json()["error"]["code"] == "HIGH_RISK_ACTION_EXPIRED"
    with sqlite3.connect(database_path) as connection:
        expired_state = connection.execute(
            """
            SELECT state FROM high_risk_actions
            WHERE high_risk_action_id = ?
            """,
            (expiring_action["high_risk_action_id"],),
        ).fetchone()[0]
        assert expired_state == "EXPIRED"


def test_device_enrollment_rotation_activation_and_family_revoke(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")

    wrong_screen_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/other-screen/device-enrollments",
        {"reason": "prove a client-selected screen fails closed"},
        "request-wrong-screen",
    )
    approve_action(admin_a, csrf_a, wrong_screen_action, key="approve-wrong-screen")
    wrong_screen_execution = implementation.post(
        "/api/v1/control-plane/screen-instances/other-screen/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-wrong-screen",
                "High-Risk-Action-ID": wrong_screen_action["high_risk_action_id"],
            },
        ),
        json={"reason": "prove a client-selected screen fails closed"},
    )
    assert wrong_screen_execution.status_code == 404

    enrollment_payload = {"reason": "enroll trust-only screen fixture"}
    enrollment_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        enrollment_payload,
        "request-enrollment",
    )
    approve_action(admin_a, csrf_a, enrollment_action, key="approve-enrollment")
    execute_headers = mutation_headers(
        csrf_impl,
        **{
            "Idempotency-Key": "execute-enrollment",
            "High-Risk-Action-ID": enrollment_action["high_risk_action_id"],
        },
    )
    issued = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=execute_headers,
        json=enrollment_payload,
    )
    assert issued.status_code == 201, issued.text
    enrollment_token = issued.json()["enrollment_token"]
    replay = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=execute_headers,
        json=enrollment_payload,
    )
    assert replay.status_code == 201
    assert replay.json()["enrollment_token"] == enrollment_token

    device = TestClient(app, base_url="https://device.test")
    forbidden_scope = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-with-client-scope"},
        json={
            "enrollment_token": enrollment_token,
            "screen_id": "screen-selected-by-client",
        },
    )
    assert forbidden_scope.status_code == 422
    assert enrollment_token not in forbidden_scope.text
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-enrollment"},
        json={"enrollment_token": enrollment_token},
    )
    assert claimed.status_code == 200, claimed.text
    credential = claimed.json()["credential"]
    credential_id = claimed.json()["credential_id"]
    claim_replay = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-enrollment"},
        json={"enrollment_token": enrollment_token},
    )
    assert claim_replay.status_code == 200
    assert claim_replay.json()["credential"] == credential
    second_claim = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-enrollment-again"},
        json={"enrollment_token": enrollment_token},
    )
    assert second_claim.status_code == 409

    active = device.get(
        "/api/v1/device/runtime-binding",
        headers={"Authorization": f"DeviceCredential {credential}"},
    )
    assert active.status_code == 200
    assert active.json()["screen_id"] == "screen-trust-fixture"
    assert active.json()["runtime_binding_status"] == "NOT_IMPLEMENTED_P1_2"

    expiring_rotation = device.post(
        "/api/v1/device/credentials:rotate",
        headers={
            "Authorization": f"DeviceCredential {credential}",
            "Idempotency-Key": "rotate-expiring-credential",
        },
    )
    assert expiring_rotation.status_code == 200, expiring_rotation.text
    expiring_successor = expiring_rotation.json()["credential"]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE device_credentials SET activation_expires_at = 0
            WHERE credential_id = ?
            """,
            (expiring_rotation.json()["credential_id"],),
        )
        connection.commit()
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {expiring_successor}"},
        ).status_code
        == 401
    )
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {credential}"},
        ).status_code
        == 200
    )

    rotated = device.post(
        "/api/v1/device/credentials:rotate",
        headers={
            "Authorization": f"DeviceCredential {credential}",
            "Idempotency-Key": "rotate-credential",
        },
    )
    assert rotated.status_code == 200, rotated.text
    successor = rotated.json()["credential"]
    successor_id = rotated.json()["credential_id"]
    assert rotated.json()["state"] == "PENDING_ACTIVATION"

    activated = device.get(
        "/api/v1/device/runtime-binding",
        headers={"Authorization": f"DeviceCredential {successor}"},
    )
    assert activated.status_code == 200
    assert activated.json()["credential_id"] == successor_id
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {credential}"},
        ).status_code
        == 401
    )

    pending_at_revoke_response = device.post(
        "/api/v1/device/credentials:rotate",
        headers={
            "Authorization": f"DeviceCredential {successor}",
            "Idempotency-Key": "rotate-before-family-revoke",
        },
    )
    assert pending_at_revoke_response.status_code == 200
    pending_at_revoke = pending_at_revoke_response.json()["credential"]

    metadata = admin_a.get(
        f"/api/v1/control-plane/screen-instances/screen-trust-fixture/device-credentials/{successor_id}"
    )
    assert metadata.status_code == 200
    family_etag = metadata.json()["family_etag"]
    credential_epoch = metadata.json()["credential_epoch"]
    revoke_payload = {
        "expected_credential_epoch": credential_epoch,
        "reason": "revoke compromised fixture device",
    }
    revoke_action = request_action(
        admin_a,
        csrf_a,
        (
            "/api/v1/control-plane/screen-instances/screen-trust-fixture/"
            f"device-credentials/{successor_id}:revoke"
        ),
        revoke_payload,
        "request-device-revoke",
        extra_headers={"If-Match": family_etag},
    )
    approve_action(admin_b, csrf_b, revoke_action, key="approve-device-revoke")
    revoked = admin_a.post(
        (
            "/api/v1/control-plane/screen-instances/screen-trust-fixture/"
            f"device-credentials/{successor_id}:revoke"
        ),
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "execute-device-revoke",
                "High-Risk-Action-ID": revoke_action["high_risk_action_id"],
                "If-Match": family_etag,
            },
        ),
        json=revoke_payload,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["state"] == "REVOKED"
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {successor}"},
        ).status_code
        == 401
    )
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {pending_at_revoke}"},
        ).status_code
        == 401
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE idempotency_records SET response_expires_at = 0
            WHERE phase = 'claimDeviceEnrollment'
            """
        )
        connection.commit()
    expired_claim_replay = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-enrollment"},
        json={"enrollment_token": enrollment_token},
    )
    assert expired_claim_replay.status_code == 409
    assert expired_claim_replay.json()["error"]["code"] == "ONE_TIME_RESPONSE_REPLAY_EXPIRED"
    with sqlite3.connect(database_path) as connection:
        replay_material = connection.execute(
            """
            SELECT response_nonce, response_ciphertext FROM idempotency_records
            WHERE phase = 'claimDeviceEnrollment'
            """
        ).fetchone()
        assert replay_material == (None, None)

    database_bytes = database_path.read_bytes()
    for secret_value in (
        enrollment_token,
        credential,
        expiring_successor,
        successor,
        pending_at_revoke,
        PASSWORDS["admin-a"],
    ):
        assert secret_value.encode() not in database_bytes

    auditor, _ = login(app, "auditor")
    audit_response = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit_response.status_code == 200
    audit_text = audit_response.text
    for secret_value in (
        enrollment_token,
        credential,
        expiring_successor,
        successor,
        pending_at_revoke,
        PASSWORDS["admin-a"],
    ):
        assert secret_value not in audit_text
    forbidden_metadata = auditor.get(
        f"/api/v1/control-plane/screen-instances/screen-trust-fixture/device-credentials/{credential_id}"
    )
    assert forbidden_metadata.status_code == 403

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        events = connection.execute("SELECT * FROM security_audit_events ORDER BY sequence").fetchall()
    previous_hash = None
    for event in events:
        assert event["previous_event_hash"] == previous_hash
        payload = canonical_json(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "actor_type": event["actor_type"],
                "actor_id": event["actor_id"],
                "target_type": event["target_type"],
                "target_id": event["target_id"],
                "outcome": event["outcome"],
                "reason": event["reason"],
                "details": json.loads(event["details_json"]),
                "previous_event_hash": event["previous_event_hash"],
                "created_at": event["created_at"],
            }
        )
        assert event["event_hash"] == service.keys.digest(
            "AUDIT_EVENT_CHAIN_HMAC",
            payload,
        )
        previous_hash = event["event_hash"]
