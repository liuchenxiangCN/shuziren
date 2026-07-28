from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.control_plane import store as store_module
from app.control_plane.errors import ControlPlaneError
from app.control_plane.recovery import BackupIntegrityError, BackupManager
from app.control_plane.router import (
    control_plane_error_handler,
    router,
    sanitized_validation_errors,
)
from app.control_plane.security import PURPOSES, PurposeKeyring, canonical_json, validate_password
from app.control_plane.service import ROLE_PERMISSIONS, ControlPlaneService
from app.control_plane.store import (
    LOGICAL_SCHEMA_VERSION,
    MIGRATION_001_CHECKSUM_SHA256,
    MIGRATION_001_VERSION,
    MIGRATION_CHECKSUM_SHA256,
    MIGRATION_VERSION,
    MIGRATIONS,
    SCHEMA_MIGRATIONS_SQL,
    SCHEMA_SQL,
)
from app.control_plane.upgrade_preview import copy_sqlite_database
from app.services.session_log import SessionLogStore

ORIGIN = "https://manage.test"
PASSWORDS = {
    username: f"test-only-{secrets.token_urlsafe(18)}"
    for username in ("admin-a", "admin-b", "implementation", "auditor")
}
FROZEN_KEY_PURPOSES = {
    "HIGH_RISK_REQUEST_HMAC",
    "SENSITIVE_REQUEST_DIGEST_HMAC",
    "RESTORE_CONTINUITY_ENVELOPE_HMAC",
    "RECOVERY_LEDGER_CHAIN_HMAC",
    "RECOVERY_LEDGER_RECORD_AEAD",
    "AUTH_SESSION_VERIFIER_PEPPER",
    "CSRF_TOKEN_VERIFIER_PEPPER",
    "ONE_TIME_TOKEN_VERIFIER_PEPPER",
    "ONE_TIME_RESPONSE_ENCRYPTION",
    "DEVICE_CREDENTIAL_VERIFIER_PEPPER",
    "SECRET_ENVELOPE_ENCRYPTION",
    "BACKUP_RECOVERY_ENCRYPTION",
    "OFFLINE_RECOVERY_AUTHENTICATION",
    "HUMAN_OPERATOR_ATTESTATION_SIGNATURE",
    "DISASTER_ENVELOPE_NONCE_HMAC",
    "OPERATIONAL_FENCE_HMAC",
    "PRODUCTION_READINESS_NONCE_HMAC",
    "EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC",
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
    assert service.status()["migration_version"] == MIGRATION_VERSION
    assert service.status()["migration_checksum_sha256"] == MIGRATION_CHECKSUM_SHA256
    assert service.status()["profile"] == "DEVELOPMENT_PREVIEW"
    assert service.status()["production_ready"] is False
    assert set(PURPOSES) <= FROZEN_KEY_PURPOSES
    assert {
        "HIGH_RISK_REQUEST_HMAC",
        "SENSITIVE_REQUEST_DIGEST_HMAC",
        "ONE_TIME_RESPONSE_ENCRYPTION",
    } <= set(PURPOSES)
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
        migrations = connection.execute(
            """
            SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid
            """
        ).fetchall()
        assert migrations == [(version, checksum) for version, checksum, _ in MIGRATIONS]
        active_family_index = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type = 'index'
                AND name = 'idx_device_credential_family_active_screen'
            """
        ).fetchone()
        assert active_family_index is not None
        assert "WHERE state = 'ACTIVE'" in active_family_index[0]
        family_indexes = connection.execute("PRAGMA index_list(device_credential_families)").fetchall()
        assert any(
            row[1] == "idx_device_credential_family_active_screen" and row[2] == 1 and row[4] == 1
            for row in family_indexes
        )
        enrollment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(device_enrollments)").fetchall()
        }
        assert {
            "family_precondition_state",
            "family_precondition_id",
            "family_precondition_revision",
        } <= enrollment_columns
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
    tampered_path = tmp_path / "tampered-migration.db"
    tampered_root_key = PurposeKeyring.generate_root_base64()
    ControlPlaneService(
        str(tampered_path),
        tampered_root_key,
        preview_mode=False,
    )
    with sqlite3.connect(tampered_path) as connection:
        connection.execute(
            "UPDATE schema_migrations SET checksum_sha256 = ?",
            ("0" * 64,),
        )
        connection.commit()
    with pytest.raises(RuntimeError, match="migration checksum mismatch"):
        ControlPlaneService(
            str(tampered_path),
            tampered_root_key,
            preview_mode=False,
        )


def test_sqlite_backup_copy_includes_committed_wal(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    with sqlite3.connect(source_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA wal_autocheckpoint = 0")
        connection.execute("CREATE TABLE wal_probe (value TEXT NOT NULL)")
        connection.commit()
        connection.execute("INSERT INTO wal_probe (value) VALUES (?)", ("committed-in-wal",))
        connection.commit()
        wal_path = Path(f"{source_path}-wal")
        assert wal_path.exists()
        assert wal_path.stat().st_size > 0

        copy_sqlite_database(str(source_path), str(target_path))

    with sqlite3.connect(target_path) as connection:
        assert connection.execute("SELECT value FROM wal_probe").fetchall() == [("committed-in-wal",)]
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        copy_sqlite_database(str(source_path), str(target_path))


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
    app, service, database_path = control_plane
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
    predecessor_cookie = admin.cookies.get("__Host-shuziren_session")
    assert predecessor_cookie
    predecessor_context = service.authenticate_session(predecessor_cookie)
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
    successor_cookie = admin.cookies.get("__Host-shuziren_session")
    assert successor_cookie and successor_cookie != predecessor_cookie
    reauthentication_replay = admin.post(
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
    assert reauthentication_replay.status_code == 200
    assert reauthentication_replay.json()["auth_session_id"] == reauthenticated.json()["auth_session_id"]
    assert "x-csrf-token" not in reauthentication_replay.headers
    assert admin.cookies.get("__Host-shuziren_session") == successor_cookie
    changed_reauthentication_precondition = admin.post(
        "/api/v1/control-plane/auth/session:reauthenticate",
        headers=mutation_headers(
            admin_csrf,
            **{
                "Idempotency-Key": "reauthenticate-session",
                "If-Match": '"session:999"',
            },
        ),
        json={"password": PASSWORDS["admin-a"]},
    )
    assert changed_reauthentication_precondition.status_code == 409
    assert changed_reauthentication_precondition.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    changed_reauthentication = admin.post(
        "/api/v1/control-plane/auth/session:reauthenticate",
        headers=mutation_headers(
            admin_csrf,
            **{
                "Idempotency-Key": "reauthenticate-session",
                "If-Match": session.json()["etag"],
            },
        ),
        json={"password": f"{PASSWORDS['admin-a']}-changed"},
    )
    assert changed_reauthentication.status_code == 409
    assert changed_reauthentication.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    with pytest.raises(ControlPlaneError) as revoked_context:
        service.reauthenticate(
            predecessor_context,
            PASSWORDS["admin-a"],
            session.json()["etag"],
            "reauthenticate-revoked-context",
        )
    assert revoked_context.value.code == "AUTHENTICATION_REQUIRED"

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
            SELECT idempotency_key_digest, sensitive_request_digest,
                sensitive_digest_key_id
            FROM idempotency_records
            WHERE phase = 'request:createUser'
            """
        ).fetchone()
    stored_key_digest = stored_idempotency[0]
    assert (
        stored_key_digest
        == hashlib.sha256(b"shuziren:p1:idempotency-key:v1\0create-user-request").hexdigest()
    )
    assert stored_idempotency[1]
    assert stored_idempotency[2] == service.keys.key_id("SENSITIVE_REQUEST_DIGEST_HMAC")
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


def test_unreachable_one_time_device_material_fails_closed(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin, csrf_admin = login(app, "admin-a")

    first_payload = {"reason": "prove unreachable enrollment cleanup"}
    first_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        first_payload,
        "request-unreachable-enrollment",
    )
    approve_action(admin, csrf_admin, first_action, key="approve-unreachable-enrollment")
    first_headers = mutation_headers(
        csrf_impl,
        **{
            "Idempotency-Key": "execute-unreachable-enrollment",
            "High-Risk-Action-ID": first_action["high_risk_action_id"],
        },
    )
    first_issue = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=first_headers,
        json=first_payload,
    )
    assert first_issue.status_code == 201
    first_enrollment_id = first_issue.json()["enrollment"]["enrollment_id"]
    with sqlite3.connect(database_path) as connection:
        first_response_expires_at = connection.execute(
            """
            SELECT response_expires_at FROM idempotency_records
            WHERE phase = 'execute:issueDeviceEnrollment'
            """
        ).fetchone()[0]
    original_clock = service.clock
    service.clock = lambda: first_response_expires_at + 1
    try:
        expired_issue = implementation.post(
            "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
            headers=first_headers,
            json=first_payload,
        )
    finally:
        service.clock = original_clock
    assert expired_issue.status_code == 409
    assert expired_issue.json()["error"]["code"] == "ONE_TIME_RESPONSE_REPLAY_EXPIRED"
    with sqlite3.connect(database_path) as connection:
        first_state = connection.execute(
            """
            SELECT state FROM device_enrollments WHERE enrollment_id = ?
            """,
            (first_enrollment_id,),
        ).fetchone()
        assert first_state == ("REVOKED",)

    claim_payload = {"reason": "prove unreachable claim cleanup"}
    claim_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        claim_payload,
        "request-unreachable-claim",
    )
    approve_action(admin, csrf_admin, claim_action, key="approve-unreachable-claim")
    claim_issue = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-unreachable-claim",
                "High-Risk-Action-ID": claim_action["high_risk_action_id"],
            },
        ),
        json=claim_payload,
    )
    assert claim_issue.status_code == 201
    enrollment_token = claim_issue.json()["enrollment_token"]
    enrollment_id = claim_issue.json()["enrollment"]["enrollment_id"]
    device = TestClient(app, base_url="https://device.test")
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-unreachable-credential"},
        json={"enrollment_token": enrollment_token},
    )
    assert claimed.status_code == 200
    credential = claimed.json()["credential"]
    credential_id = claimed.json()["credential_id"]
    with sqlite3.connect(database_path) as connection:
        claim_response_expires_at = connection.execute(
            """
            SELECT response_expires_at FROM idempotency_records
            WHERE phase = 'claimDeviceEnrollment' AND principal_key = ?
            """,
            (enrollment_id,),
        ).fetchone()[0]
    service.clock = lambda: claim_response_expires_at + 1
    try:
        expired_claim = device.post(
            "/api/v1/device/enrollments:claim",
            headers={"Idempotency-Key": "claim-unreachable-credential"},
            json={"enrollment_token": enrollment_token},
        )
    finally:
        service.clock = original_clock
    assert expired_claim.status_code == 409
    assert expired_claim.json()["error"]["code"] == "ONE_TIME_RESPONSE_REPLAY_EXPIRED"
    with sqlite3.connect(database_path) as connection:
        terminal = connection.execute(
            """
            SELECT c.state, c.last_authenticated_at, f.state, f.family_id,
                f.active_credential_id, f.pending_credential_id
            FROM device_credentials c
            JOIN device_credential_families f ON f.family_id = c.family_id
            WHERE c.credential_id = ?
            """,
            (credential_id,),
        ).fetchone()
        assert terminal[:3] == ("REVOKED", None, "REENROLL_REQUIRED")
        original_family_id = terminal[3]
        assert terminal[4:] == (None, None)
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {credential}"},
        ).status_code
        == 401
    )

    reenroll_payload = {"reason": "replace an unreachable claimed credential"}
    reenroll_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        reenroll_payload,
        "request-reenroll-after-unreachable-claim",
    )
    approve_action(admin, csrf_admin, reenroll_action, key="approve-reenroll-after-unreachable-claim")
    reenrollment = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-reenroll-after-unreachable-claim",
                "High-Risk-Action-ID": reenroll_action["high_risk_action_id"],
            },
        ),
        json=reenroll_payload,
    )
    assert reenrollment.status_code == 201, reenrollment.text
    reenrolled = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-reenrolled-credential"},
        json={"enrollment_token": reenrollment.json()["enrollment_token"]},
    )
    assert reenrolled.status_code == 200, reenrolled.text
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {reenrolled.json()['credential']}"},
        ).status_code
        == 200
    )
    with sqlite3.connect(database_path) as connection:
        replacement_family = connection.execute(
            """
            SELECT c.family_id, f.state
            FROM device_credentials c
            JOIN device_credential_families f ON f.family_id = c.family_id
            WHERE c.credential_id = ?
            """,
            (reenrolled.json()["credential_id"],),
        ).fetchone()
        preserved_terminal = connection.execute(
            """
            SELECT state, active_credential_id, pending_credential_id
            FROM device_credential_families WHERE family_id = ?
            """,
            (original_family_id,),
        ).fetchone()
        assert replacement_family[0] != original_family_id
        assert replacement_family[1] == "ACTIVE"
        assert preserved_terminal == ("REENROLL_REQUIRED", None, None)


def test_device_enrollment_rotation_activation_and_family_revoke(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")

    wrong_screen_request = implementation.post(
        "/api/v1/control-plane/screen-instances/other-screen/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": "request-wrong-screen"},
        ),
        json={"reason": "prove a client-selected screen fails closed"},
    )
    assert wrong_screen_request.status_code == 404
    assert wrong_screen_request.json()["error"]["code"] == "NOT_FOUND"

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

    terminal_enrollment_payload = {"reason": "prove a pre-issued token cannot reopen a terminal family"}
    terminal_enrollment_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        terminal_enrollment_payload,
        "request-terminal-enrollment",
    )
    approve_action(
        admin_b,
        csrf_b,
        terminal_enrollment_action,
        key="approve-terminal-enrollment",
    )
    terminal_enrollment = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-terminal-enrollment",
                "High-Risk-Action-ID": terminal_enrollment_action["high_risk_action_id"],
            },
        ),
        json=terminal_enrollment_payload,
    )
    assert terminal_enrollment.status_code == 201
    terminal_enrollment_token = terminal_enrollment.json()["enrollment_token"]

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
    with sqlite3.connect(database_path) as connection:
        original_family_id = connection.execute(
            "SELECT family_id FROM device_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()[0]
    claim_replay = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-enrollment"},
        json={"enrollment_token": enrollment_token},
    )
    assert claim_replay.status_code == 200
    assert claim_replay.json()["credential"] == credential
    with sqlite3.connect(database_path) as connection:
        replay_evidence = connection.execute(
            """
            SELECT response_encryption_key_id, response_aad_json,
                response_aad_hash, sensitive_digest_key_id
            FROM idempotency_records
            WHERE phase = 'claimDeviceEnrollment'
            """
        ).fetchone()
    assert replay_evidence[0] == service.keys.key_id("ONE_TIME_RESPONSE_ENCRYPTION")
    assert replay_evidence[1]
    assert hashlib.sha256(replay_evidence[1].encode("utf-8")).hexdigest() == replay_evidence[2]
    assert replay_evidence[3] == service.keys.key_id("SENSITIVE_REQUEST_DIGEST_HMAC")
    replay_aad = json.loads(replay_evidence[1])
    assert replay_aad["operation_id"] == "claimDeviceEnrollment"
    assert replay_aad["device_enrollment_id"] == issued.json()["enrollment"]["enrollment_id"]
    assert replay_aad["device_credential_id"] == credential_id
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
    assert active.json()["runtime_binding_status"] == "NOT_CONFIGURED_P1_3"

    expiring_rotation = device.post(
        "/api/v1/device/credentials:rotate",
        headers={
            "Authorization": f"DeviceCredential {credential}",
            "Idempotency-Key": "rotate-expiring-credential",
        },
    )
    assert expiring_rotation.status_code == 200, expiring_rotation.text
    expiring_successor = expiring_rotation.json()["credential"]
    rotation_replay = device.post(
        "/api/v1/device/credentials:rotate",
        headers={
            "Authorization": f"DeviceCredential {credential}",
            "Idempotency-Key": "rotate-expiring-credential",
        },
    )
    assert rotation_replay.status_code == 200
    assert rotation_replay.json()["credential"] == expiring_successor
    with sqlite3.connect(database_path) as connection:
        rotation_response_expires_at = connection.execute(
            """
            SELECT response_expires_at FROM idempotency_records
            WHERE phase = 'rotateDeviceCredential'
                AND principal_key = ?
            """,
            (credential_id,),
        ).fetchone()[0]
    original_clock = service.clock
    service.clock = lambda: rotation_response_expires_at + 1
    try:
        expired_rotation_replay = device.post(
            "/api/v1/device/credentials:rotate",
            headers={
                "Authorization": f"DeviceCredential {credential}",
                "Idempotency-Key": "rotate-expiring-credential",
            },
        )
    finally:
        service.clock = original_clock
    assert expired_rotation_replay.status_code == 409
    assert expired_rotation_replay.json()["error"]["code"] == "ONE_TIME_RESPONSE_REPLAY_EXPIRED"

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
    with sqlite3.connect(database_path) as connection:
        expired_pending = connection.execute(
            """
            SELECT state FROM device_credentials WHERE credential_id = ?
            """,
            (expiring_rotation.json()["credential_id"],),
        ).fetchone()
        assert expired_pending == ("REVOKED",)

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
    terminal_family_claim = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-terminal-family"},
        json={"enrollment_token": terminal_enrollment_token},
    )
    assert terminal_family_claim.status_code == 409
    assert terminal_family_claim.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    stale_approval_payload = {"reason": "prove approval is bound to the revoked family generation"}
    stale_approval_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        stale_approval_payload,
        "request-stale-family-generation",
    )
    approve_action(
        admin_b,
        csrf_b,
        stale_approval_action,
        key="approve-stale-family-generation",
    )

    terminal_issue_payload = {"reason": "create a fresh family after hard revocation"}
    terminal_issue_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        terminal_issue_payload,
        "request-after-terminal-family",
    )
    approve_action(
        admin_b,
        csrf_b,
        terminal_issue_action,
        key="approve-after-terminal-family",
    )
    terminal_issue = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-after-terminal-family",
                "High-Risk-Action-ID": terminal_issue_action["high_risk_action_id"],
            },
        ),
        json=terminal_issue_payload,
    )
    assert terminal_issue.status_code == 201, terminal_issue.text
    replacement_enrollment_token = terminal_issue.json()["enrollment_token"]
    replacement_claim = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "claim-after-terminal-family"},
        json={"enrollment_token": replacement_enrollment_token},
    )
    assert replacement_claim.status_code == 200, replacement_claim.text
    replacement_credential = replacement_claim.json()["credential"]
    replacement_credential_id = replacement_claim.json()["credential_id"]
    with sqlite3.connect(database_path) as connection:
        replacement_family_id = connection.execute(
            "SELECT family_id FROM device_credentials WHERE credential_id = ?",
            (replacement_credential_id,),
        ).fetchone()[0]
        preserved_old_family = connection.execute(
            """
            SELECT state, active_credential_id, pending_credential_id
            FROM device_credential_families WHERE family_id = ?
            """,
            (original_family_id,),
        ).fetchone()
        active_families = connection.execute(
            """
            SELECT COUNT(*) FROM device_credential_families
            WHERE tenant_id = 'tenant-test' AND deployment_id = 'deployment-test'
                AND screen_id = 'screen-trust-fixture' AND state = 'ACTIVE'
            """
        ).fetchone()[0]
        assert replacement_family_id != original_family_id
        assert preserved_old_family == ("REVOKED", None, None)
        assert active_families == 1
    assert (
        device.get(
            "/api/v1/device/runtime-binding",
            headers={"Authorization": f"DeviceCredential {replacement_credential}"},
        ).status_code
        == 200
    )
    stale_approval_execution = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "execute-stale-family-generation",
                "High-Risk-Action-ID": stale_approval_action["high_risk_action_id"],
            },
        ),
        json=stale_approval_payload,
    )
    assert stale_approval_execution.status_code == 409
    assert stale_approval_execution.json()["error"]["code"] == "ACTIVE_DEVICE_FAMILY_EXISTS"

    with sqlite3.connect(database_path) as connection:
        claim_response_expires_at = connection.execute(
            """
            SELECT response_expires_at FROM idempotency_records
            WHERE phase = 'claimDeviceEnrollment' AND principal_key = ?
            """,
            (issued.json()["enrollment"]["enrollment_id"],),
        ).fetchone()[0]
    service.clock = lambda: claim_response_expires_at + 1
    try:
        expired_claim_replay = device.post(
            "/api/v1/device/enrollments:claim",
            headers={"Idempotency-Key": "claim-enrollment"},
            json={"enrollment_token": enrollment_token},
        )
    finally:
        service.clock = original_clock
    assert expired_claim_replay.status_code == 409
    assert expired_claim_replay.json()["error"]["code"] == "ONE_TIME_RESPONSE_REPLAY_EXPIRED"
    with sqlite3.connect(database_path) as connection:
        replay_material = connection.execute(
            """
            SELECT response_nonce, response_ciphertext, response_aad_json
            FROM idempotency_records
            WHERE phase = 'claimDeviceEnrollment' AND principal_key = ?
            """,
            (issued.json()["enrollment"]["enrollment_id"],),
        ).fetchone()
        assert replay_material == (None, None, None)

    database_bytes = database_path.read_bytes()
    for secret_value in (
        enrollment_token,
        terminal_enrollment_token,
        replacement_enrollment_token,
        credential,
        expiring_successor,
        successor,
        pending_at_revoke,
        replacement_credential,
        PASSWORDS["admin-a"],
    ):
        assert secret_value.encode() not in database_bytes

    auditor, _ = login(app, "auditor")
    audit_response = auditor.get("/api/v1/control-plane/audit-events?limit=200")
    assert audit_response.status_code == 200
    audit_text = audit_response.text
    for secret_value in (
        enrollment_token,
        terminal_enrollment_token,
        replacement_enrollment_token,
        credential,
        expiring_successor,
        successor,
        pending_at_revoke,
        replacement_credential,
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
        assert (
            event["event_hash"]
            == hashlib.sha256(b"shuziren:p1:security-audit-event:v1\0" + payload.encode("utf-8")).hexdigest()
        )
        assert event["event_hash_schema_version"] == "p1_security_audit_event_hash_v1"
        previous_hash = event["event_hash"]


def test_three_screen_inventory_api_isolation_scope_and_idempotency(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    implementation, csrf = login(app, "implementation")

    sites = implementation.get("/api/v1/control-plane/sites").json()["items"]
    groups = implementation.get("/api/v1/control-plane/screen-groups").json()["items"]
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    assert len(sites) == 1
    assert sites[0]["slug"] == "site-default"
    assert sites[0]["screen_count"] == 3
    assert len(groups) == 1
    assert groups[0]["slug"] == "group-main"
    assert len(screens) == 3
    assert screens[0]["screen_id"] == "screen-trust-fixture"
    assert [screen["slug"] for screen in screens] == ["screen-1", "screen-2", "screen-3"]
    for screen in screens[1:]:
        parsed = uuid.UUID(screen["screen_id"])
        assert parsed.version == 7
        assert parsed.variant == uuid.RFC_4122
    assert len({screen["fvs_binding_ref"] for screen in screens}) == 3
    assert len({screen["digital_human_instance"]["digital_human_instance_id"] for screen in screens}) == 3
    assert all(screen["fvs_status"] == "UNVERIFIED" for screen in screens)
    assert all(screen["runtime_binding"]["inventory_status"] == "NOT_CONFIGURED_P1_3" for screen in screens)
    assert all(screen["device_trust"]["state"] == "UNENROLLED" for screen in screens)

    first_page = implementation.get("/api/v1/control-plane/screen-instances?limit=1").json()
    assert len(first_page["items"]) == 1
    cursor = first_page["next_cursor"]
    paged_ids = [first_page["items"][0]["screen_id"]]
    while cursor:
        page = implementation.get(f"/api/v1/control-plane/screen-instances?limit=1&cursor={cursor}").json()
        paged_ids.extend(item["screen_id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert paged_ids == [screen["screen_id"] for screen in screens]

    before = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}"
        ).json()
        for screen in screens
    }
    screen_two = screens[1]
    updated = implementation.patch(
        f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}",
        headers=mutation_headers(csrf, **{"If-Match": screen_two["etag"]}),
        json={
            "display_name": "主展厅大屏 2",
            "fvs_binding_ref": "https://fvs.example.test/show/screen-2",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_name"] == "主展厅大屏 2"
    assert updated.json()["fvs_status"] == "UNVERIFIED"
    stale = implementation.patch(
        f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}",
        headers=mutation_headers(csrf, **{"If-Match": screen_two["etag"]}),
        json={"display_name": "stale write must fail"},
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"
    after = {
        screen_id: implementation.get(f"/api/v1/control-plane/screen-instances/{screen_id}").json()
        for screen_id in before
    }
    for unrelated in (screens[0]["screen_id"], screens[2]["screen_id"]):
        assert after[unrelated] == before[unrelated]

    forbidden_fvs_refs = (
        "https://user:password@fvs.example.test/screen",
        "https://fvs.example.test/view?api_key=synthetic-credential",
        "fvs-ref;apikey=synthetic-credential",
        "fvs-ref;access_key=synthetic-credential",
        "fvs-ref;x-api-key:synthetic-credential",
        "fvs-ref;client_secret=synthetic-credential",
        "fvs-ref;credential=synthetic-credential",
        "https://fvs.example.test/view?api%5Fkey=synthetic-credential",
        "Authorization: Bearer synthetic-credential",
        "Server=db.example;Database=fr;User Id=svc;Pwd=synthetic-credential",
        "Driver={PostgreSQL Unicode};Server=db.example;Uid=svc;Pwd=synthetic-credential",
        "Data Source=db.example;Initial Catalog=fr;Integrated Security=True",
        "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=db.example)(PORT=1521)))",
        "postgresql://svc:synthetic-credential@db.example/fr",
        "mongodb+srv://svc:synthetic-credential@db.example/fr",
        "sk-proj-SYNTHETIC-NOT-REAL-0123456789abcdef",
        "ghp_SYNTHETICNOTREAL0123456789abcdef",
        "AKIASYNTHETICNOTREAL01",
        "eyJsyntheticHeader.eyJsyntheticPayload.syntheticSignature",
    )
    for forbidden_fvs_ref in forbidden_fvs_refs:
        secret_ref = implementation.patch(
            f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}",
            headers=mutation_headers(csrf, **{"If-Match": updated.json()["etag"]}),
            json={"fvs_binding_ref": forbidden_fvs_ref},
        )
        assert secret_ref.status_code == 422
        assert secret_ref.json()["error"]["code"] == "SECRET_MATERIAL_FORBIDDEN"
    after_secret_rejections = implementation.get(
        f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}"
    ).json()
    assert after_secret_rejections["etag"] == updated.json()["etag"]
    assert after_secret_rejections["fvs_binding_ref"] == "https://fvs.example.test/show/screen-2"

    create_key = "create-screen-idempotency"
    create_payload = {
        "slug": "screen-4",
        "display_name": "大屏 4",
        "fvs_binding_ref": "fvs-inventory-screen-4",
    }
    created = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(csrf, **{"Idempotency-Key": create_key}),
        json=create_payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["runtime_binding"]["inventory_status"] == "INVENTORY_INCOMPLETE"
    assert created.json()["digital_human_instance"] is None
    replay = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(csrf, **{"Idempotency-Key": create_key}),
        json=create_payload,
    )
    assert replay.status_code == 201
    assert replay.json()["screen_id"] == created.json()["screen_id"]
    mismatch = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(csrf, **{"Idempotency-Key": create_key}),
        json={**create_payload, "display_name": "changed command"},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    duplicate_screen_slug = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "duplicate-screen-slug"},
        ),
        json={**create_payload, "display_name": "duplicate slug must fail"},
    )
    assert duplicate_screen_slug.status_code == 409
    assert duplicate_screen_slug.json()["error"]["code"] == "DUPLICATE_RESOURCE"

    digital_key = "create-digital-human-idempotency"
    digital = implementation.post(
        (f"/api/v1/control-plane/screen-instances/{created.json()['screen_id']}/digital-human-instances"),
        headers=mutation_headers(csrf, **{"Idempotency-Key": digital_key}),
        json={},
    )
    assert digital.status_code == 201, digital.text
    digital_replay = implementation.post(
        (f"/api/v1/control-plane/screen-instances/{created.json()['screen_id']}/digital-human-instances"),
        headers=mutation_headers(csrf, **{"Idempotency-Key": digital_key}),
        json={},
    )
    assert digital_replay.status_code == 201
    assert digital_replay.json()["digital_human_instance_id"] == digital.json()["digital_human_instance_id"]
    duplicate_digital = implementation.post(
        (f"/api/v1/control-plane/screen-instances/{created.json()['screen_id']}/digital-human-instances"),
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "create-second-digital-human"},
        ),
        json={},
    )
    assert duplicate_digital.status_code == 409
    assert duplicate_digital.json()["error"]["code"] == "DUPLICATE_RESOURCE"
    binding = implementation.get(
        f"/api/v1/control-plane/screen-instances/{created.json()['screen_id']}/runtime-binding"
    ).json()
    assert binding["digital_human_instance_id"] == digital.json()["digital_human_instance_id"]
    assert binding["inventory_status"] == "NOT_CONFIGURED_P1_3"
    assert binding["binding_generation"] == 0

    group = implementation.get(f"/api/v1/control-plane/screen-groups/{groups[0]['screen_group_id']}").json()
    create_group_payload = {
        "slug": "group-secondary",
        "display_name": "辅助大屏组",
    }
    created_group = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "create-group-idempotency"},
        ),
        json=create_group_payload,
    )
    assert created_group.status_code == 201, created_group.text
    assert created_group.json()["member_screen_ids"] == []
    replayed_group = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "create-group-idempotency"},
        ),
        json=create_group_payload,
    )
    assert replayed_group.status_code == 201
    assert replayed_group.json()["screen_group_id"] == created_group.json()["screen_group_id"]
    changed_group_replay = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "create-group-idempotency"},
        ),
        json={**create_group_payload, "display_name": "changed command"},
    )
    assert changed_group_replay.status_code == 409
    assert changed_group_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    duplicate_group_slug = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "duplicate-group-slug"},
        ),
        json={**create_group_payload, "display_name": "duplicate slug must fail"},
    )
    assert duplicate_group_slug.status_code == 409
    assert duplicate_group_slug.json()["error"]["code"] == "DUPLICATE_RESOURCE"

    pre_group_screens = {
        item["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{item['screen_id']}"
        ).json()
        for item in [*screens, created.json()]
    }
    next_members = sorted([*group["member_screen_ids"], created.json()["screen_id"]])
    group_update = implementation.patch(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}",
        headers=mutation_headers(csrf, **{"If-Match": group["etag"]}),
        json={"member_screen_ids": next_members},
    )
    assert group_update.status_code == 200, group_update.text
    assert group_update.json()["member_screen_ids"] == next_members
    post_group_screens = {
        screen_id: implementation.get(f"/api/v1/control-plane/screen-instances/{screen_id}").json()
        for screen_id in pre_group_screens
    }
    for unchanged_id in group["member_screen_ids"]:
        assert post_group_screens[unchanged_id] == pre_group_screens[unchanged_id]
    newly_grouped_before = pre_group_screens[created.json()["screen_id"]]
    newly_grouped_after = post_group_screens[created.json()["screen_id"]]
    assert newly_grouped_after["screen_group_id"] == group["screen_group_id"]
    assert newly_grouped_after["resource_revision"] == newly_grouped_before["resource_revision"] + 1
    assert newly_grouped_after["device_trust"] == newly_grouped_before["device_trust"]
    assert newly_grouped_after["digital_human_instance"] == newly_grouped_before["digital_human_instance"]
    assert newly_grouped_after["runtime_binding"] == newly_grouped_before["runtime_binding"]
    stale_group = implementation.patch(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}",
        headers=mutation_headers(csrf, **{"If-Match": group["etag"]}),
        json={"member_screen_ids": group["member_screen_ids"]},
    )
    assert stale_group.status_code == 412

    with service.store.transaction() as connection:
        now = service.clock()
        other_site_id = str(uuid.uuid4())
        other_screen_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO sites(
                site_id, tenant_id, deployment_id, slug, display_name, timezone,
                status, created_at, updated_at
            ) VALUES (?, 'tenant-test', 'deployment-test', 'site-other',
                'Other', 'Asia/Shanghai', 'ACTIVE', ?, ?)
            """,
            (other_site_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO screen_instances(
                screen_id, tenant_id, deployment_id, site_id, slug, display_name,
                lifecycle_state, created_at, updated_at
            ) VALUES (?, 'tenant-test', 'deployment-test', ?, 'screen-other',
                'Other', 'ACTIVE', ?, ?)
            """,
            (other_screen_id, other_site_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO runtime_bindings(
                screen_id, tenant_id, deployment_id, site_id,
                inventory_status, created_at, updated_at
            ) VALUES (?, 'tenant-test', 'deployment-test', ?,
                'INVENTORY_INCOMPLETE', ?, ?)
            """,
            (other_screen_id, other_site_id, now, now),
        )
    cross_site = implementation.patch(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}",
        headers=mutation_headers(
            csrf,
            **{"If-Match": group_update.json()["etag"]},
        ),
        json={"member_screen_ids": [*next_members, other_screen_id]},
    )
    assert cross_site.status_code == 404
    assert (
        implementation.get(f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}").json()[
            "member_screen_ids"
        ]
        == next_members
    )

    pre_narrow_cursor = implementation.get("/api/v1/control-plane/screen-instances?limit=1").json()[
        "next_cursor"
    ]
    assert pre_narrow_cursor
    with service.store.transaction() as connection:
        connection.execute(
            """
            UPDATE role_assignments
            SET scope_type = 'SCREEN', scope_id = ?
            WHERE user_id = (
                SELECT user_id FROM users
                WHERE tenant_id = 'tenant-test'
                  AND deployment_id = 'deployment-test'
                  AND normalized_username = 'implementation'
            )
            """,
            (screens[2]["screen_id"],),
        )
    narrowed_cursor = implementation.get(
        f"/api/v1/control-plane/screen-instances?limit=1&cursor={pre_narrow_cursor}"
    )
    assert narrowed_cursor.status_code == 400
    assert narrowed_cursor.json()["error"]["code"] == "INVALID_CURSOR"
    assert screens[1]["screen_id"] not in narrowed_cursor.text
    narrowed_screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    assert [item["screen_id"] for item in narrowed_screens] == [screens[2]["screen_id"]]

    narrowed_group_replay = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": "create-group-idempotency"},
        ),
        json=create_group_payload,
    )
    assert narrowed_group_replay.status_code == 404
    narrowed_screen_replay = implementation.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": create_key},
        ),
        json=create_payload,
    )
    assert narrowed_screen_replay.status_code == 404
    narrowed_digital_replay = implementation.post(
        (f"/api/v1/control-plane/screen-instances/{created.json()['screen_id']}/digital-human-instances"),
        headers=mutation_headers(
            csrf,
            **{"Idempotency-Key": digital_key},
        ),
        json={},
    )
    assert narrowed_digital_replay.status_code == 404
    for denied_replay in (
        narrowed_group_replay,
        narrowed_screen_replay,
        narrowed_digital_replay,
    ):
        assert created.json()["screen_id"] not in denied_replay.text

    auditor, auditor_csrf = login(app, "auditor")
    assert len(auditor.get("/api/v1/control-plane/screen-instances").json()["items"]) == 5
    auditor_create = auditor.post(
        f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-instances",
        headers=mutation_headers(
            auditor_csrf,
            **{"Idempotency-Key": "auditor-create-screen"},
        ),
        json={
            "slug": "auditor-screen",
            "display_name": "Denied",
            "fvs_binding_ref": None,
        },
    )
    assert auditor_create.status_code == 403
    assert (
        auditor.post(
            f"/api/v1/control-plane/sites/{sites[0]['site_id']}/screen-groups",
            headers=mutation_headers(
                auditor_csrf,
                **{"Idempotency-Key": "auditor-create-group"},
            ),
            json={"slug": "auditor-group", "display_name": "Denied"},
        ).status_code
        == 403
    )
    assert (
        auditor.patch(
            f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}",
            headers=mutation_headers(
                auditor_csrf,
                **{"If-Match": group_update.json()["etag"]},
            ),
            json={"display_name": "Denied"},
        ).status_code
        == 403
    )
    assert (
        auditor.patch(
            f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}",
            headers=mutation_headers(
                auditor_csrf,
                **{"If-Match": updated.json()["etag"]},
            ),
            json={"display_name": "Denied"},
        ).status_code
        == 403
    )
    assert (
        auditor.post(
            (f"/api/v1/control-plane/screen-instances/{screen_two['screen_id']}/digital-human-instances"),
            headers=mutation_headers(
                auditor_csrf,
                **{"Idempotency-Key": "auditor-create-digital-human"},
            ),
            json={},
        ).status_code
        == 403
    )
    selector = auditor.get(
        "/api/v1/control-plane/screen-instances",
        headers={"X-Tenant-ID": "tenant-test"},
    )
    assert selector.status_code == 400
    assert selector.json()["error"]["code"] == "INVALID_REQUEST"

    scoped_password = f"test-only-{secrets.token_urlsafe(18)}"
    scoped_admin_password = f"test-only-{secrets.token_urlsafe(18)}"
    PASSWORDS["screen-auditor"] = scoped_password
    PASSWORDS["screen-admin"] = scoped_admin_password
    with service.store.transaction() as connection:
        now = service.clock()
        user_id = "usr_screen_auditor"
        connection.execute(
            """
            INSERT INTO users(
                user_id, tenant_id, deployment_id, normalized_username, display_name,
                account_state, password_verifier, credential_generation, created_at, updated_at
            ) VALUES (?, 'tenant-test', 'deployment-test', 'screen-auditor',
                'Screen Auditor', 'ACTIVE', ?, 1, ?, ?)
            """,
            (
                user_id,
                service.passwords.hash(scoped_password, username="screen-auditor"),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO role_assignments(
                assignment_id, user_id, role_id, scope_type, scope_id, created_at
            ) VALUES ('rla_screen_auditor', ?, 'auditor', 'SCREEN', ?, ?)
            """,
            (user_id, screen_two["screen_id"], now),
        )
        connection.execute(
            """
            INSERT INTO users(
                user_id, tenant_id, deployment_id, normalized_username, display_name,
                account_state, password_verifier, credential_generation, created_at, updated_at
            ) VALUES ('usr_screen_admin', 'tenant-test', 'deployment-test', 'screen-admin',
                'Screen Admin', 'ACTIVE', ?, 1, ?, ?)
            """,
            (
                service.passwords.hash(scoped_admin_password, username="screen-admin"),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO role_assignments(
                assignment_id, user_id, role_id, scope_type, scope_id, created_at
            ) VALUES ('rla_screen_admin', 'usr_screen_admin', 'platform_admin',
                'SCREEN', ?, ?)
            """,
            (screen_two["screen_id"], now),
        )
    scoped, _ = login(app, "screen-auditor")
    scoped_screens = scoped.get("/api/v1/control-plane/screen-instances").json()["items"]
    assert [item["screen_id"] for item in scoped_screens] == [screen_two["screen_id"]]
    assert scoped.get("/api/v1/control-plane/sites").json()["items"] == []
    assert scoped.get("/api/v1/control-plane/screen-groups").json()["items"] == []
    assert scoped.get(f"/api/v1/control-plane/screen-instances/{screens[0]['screen_id']}").status_code == 404
    scoped_audit = scoped.get("/api/v1/control-plane/audit-events")
    assert scoped_audit.status_code == 403
    assert screens[0]["screen_id"] not in scoped_audit.text
    sibling_digital_human_id = screens[0]["digital_human_instance"]["digital_human_instance_id"]
    assert (
        scoped.get(f"/api/v1/control-plane/digital-human-instances/{sibling_digital_human_id}").status_code
        == 404
    )
    assert (
        scoped.get(
            f"/api/v1/control-plane/screen-instances/{screens[0]['screen_id']}/runtime-binding"
        ).status_code
        == 404
    )

    screen_admin, screen_admin_csrf = login(app, "screen-admin")
    for deployment_only_path in (
        "/api/v1/control-plane/users",
        "/api/v1/control-plane/role-definitions",
        "/api/v1/control-plane/high-risk-actions",
        "/api/v1/control-plane/audit-events",
    ):
        response = screen_admin.get(deployment_only_path)
        assert response.status_code == 403
        assert screens[0]["screen_id"] not in response.text
    screen_admin_create_user = screen_admin.post(
        "/api/v1/control-plane/users",
        headers=mutation_headers(
            screen_admin_csrf,
            **{"Idempotency-Key": "screen-admin-create-user"},
        ),
        json={
            "normalized_username": "scope-bypass-user",
            "display_name": "Must Not Exist",
            "reason": "screen scope cannot administer deployment users",
        },
    )
    assert screen_admin_create_user.status_code == 403

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO runtime_bindings(
                    screen_id, tenant_id, deployment_id, site_id,
                    inventory_status, created_at, updated_at
                ) VALUES ('missing-screen', 'tenant-test', 'deployment-test', ?,
                    'INVENTORY_INCOMPLETE', 1, 1)
                """,
                (sites[0]["site_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM screen_instances WHERE screen_id = ?",
                (screens[0]["screen_id"],),
            )


def test_accepted_p1_1_copy_upgrade_and_failed_migration_are_recoverable(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "accepted-p1-1.db"
    with sqlite3.connect(legacy_path) as connection:
        connection.executescript(SCHEMA_MIGRATIONS_SQL)
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            """
            INSERT INTO schema_migrations(version, checksum_sha256, applied_at)
            VALUES (?, ?, 1)
            """,
            (MIGRATION_001_VERSION, MIGRATION_001_CHECKSUM_SHA256),
        )
        connection.execute(
            """
            INSERT INTO control_plane_metadata(
                singleton, profile, tenant_id, deployment_id, fixture_screen_id, created_at
            ) VALUES (1, 'DEVELOPMENT_PREVIEW', 'tenant-upgrade',
                'deployment-upgrade', 'screen-trust-fixture', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO device_credential_families(
                family_id, tenant_id, deployment_id, screen_id, state,
                credential_epoch, active_credential_id, created_at, updated_at, revision
            ) VALUES ('family-preserved', 'tenant-upgrade', 'deployment-upgrade',
                'screen-trust-fixture', 'ACTIVE', 7, 'credential-preserved', 2, 3, 5)
            """
        )
        connection.execute(
            """
            INSERT INTO device_credentials(
                credential_id, family_id, credential_version, verifier_hmac,
                verifier_key_id, state, issued_at, activated_at,
                last_authenticated_at, revision
            ) VALUES ('credential-preserved', 'family-preserved', 4, 'verifier-preserved',
                'key-preserved', 'ACTIVE', 2, 2, 3, 6)
            """
        )
        connection.execute(
            """
            INSERT INTO security_audit_events(
                event_id, event_type, actor_type, actor_id, target_type, target_id,
                outcome, reason, details_json, previous_event_hash, event_hash,
                event_hash_schema_version, created_at
            ) VALUES ('audit-preserved', 'P1_1_ACCEPTED', 'SYSTEM', NULL,
                'SCREEN', 'screen-trust-fixture', 'SUCCESS', NULL, '{}', NULL,
                'audit-preserved-hash', 'p1_security_audit_event_hash_v1', 4)
            """
        )
        connection.commit()
    pre_migration_copy = tmp_path / "accepted-p1-1.pre-002.db"
    shutil.copy2(legacy_path, pre_migration_copy)

    root_key = PurposeKeyring.generate_root_base64()
    service = ControlPlaneService(
        str(legacy_path),
        root_key,
        preview_mode=True,
    )
    with service.store.connect() as connection:
        migrations = connection.execute(
            "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
        ).fetchall()
        assert [tuple(row) for row in migrations] == [
            (version, checksum) for version, checksum, _ in MIGRATIONS
        ]
        assert tuple(
            connection.execute(
                """
                SELECT state, credential_epoch, active_credential_id,
                    created_at, updated_at, revision
                FROM device_credential_families WHERE family_id = 'family-preserved'
                """
            ).fetchone()
        ) == ("ACTIVE", 7, "credential-preserved", 2, 3, 5)
        assert tuple(
            connection.execute(
                """
                SELECT credential_version, verifier_hmac, verifier_key_id, state,
                    issued_at, activated_at, last_authenticated_at, revision
                FROM device_credentials WHERE credential_id = 'credential-preserved'
                """
            ).fetchone()
        ) == (4, "verifier-preserved", "key-preserved", "ACTIVE", 2, 2, 3, 6)
        screens = connection.execute("SELECT screen_id, slug FROM screen_instances ORDER BY slug").fetchall()
        assert tuple(screens[0]) == ("screen-trust-fixture", "screen-1")
        assert len(screens) == 3
        assert connection.execute("SELECT COUNT(*) FROM security_audit_events").fetchone()[0] == 5
        assert [
            row[0]
            for row in connection.execute(
                """
                SELECT event_type FROM security_audit_events
                WHERE event_type IN (
                    'THREE_SCREEN_INVENTORY_MIGRATED',
                    'PUBLISH_ROLLBACK_RECOVERY_SCHEMA_MIGRATED',
                    'CAPABILITY_PROFILE_SCHEMA_MIGRATED',
                    'CONTROLLED_QUERY_SCHEMA_MIGRATED'
                )
                ORDER BY sequence
                """
            ).fetchall()
        ] == [
            "THREE_SCREEN_INVENTORY_MIGRATED",
            "PUBLISH_ROLLBACK_RECOVERY_SCHEMA_MIGRATED",
            "CAPABILITY_PROFILE_SCHEMA_MIGRATED",
            "CONTROLLED_QUERY_SCHEMA_MIGRATED",
        ]
    ControlPlaneService(str(legacy_path), root_key, preview_mode=True)
    with service.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM security_audit_events").fetchone()[0] == 5

    with sqlite3.connect(pre_migration_copy) as connection:
        assert connection.execute("SELECT version, checksum_sha256 FROM schema_migrations").fetchone() == (
            MIGRATION_001_VERSION,
            MIGRATION_001_CHECKSUM_SHA256,
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sites'"
            ).fetchone()
            is None
        )
        assert connection.execute(
            """
            SELECT state, credential_epoch, active_credential_id, revision
            FROM device_credential_families WHERE family_id = 'family-preserved'
            """
        ).fetchone() == ("ACTIVE", 7, "credential-preserved", 5)

    failed_path = tmp_path / "failed-upgrade.db"
    shutil.copy2(pre_migration_copy, failed_path)
    with sqlite3.connect(failed_path) as connection:
        connection.execute(
            """
            UPDATE device_credential_families
            SET tenant_id = 'wrong-tenant'
            WHERE family_id = 'family-preserved'
            """
        )
        connection.commit()
    with pytest.raises(RuntimeError, match="ownership mismatch"):
        ControlPlaneService(
            str(failed_path),
            PurposeKeyring.generate_root_base64(),
            preview_mode=True,
        )
    with sqlite3.connect(failed_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sites'"
            ).fetchone()
            is None
        )
        assert connection.execute("SELECT state, revision FROM device_credential_families").fetchone() == (
            "ACTIVE",
            5,
        )

    orphan_path = tmp_path / "orphan-screen-upgrade.db"
    shutil.copy2(pre_migration_copy, orphan_path)
    with sqlite3.connect(orphan_path) as connection:
        connection.execute(
            """
            UPDATE device_credential_families
            SET screen_id = 'rogue-screen'
            WHERE family_id = 'family-preserved'
            """
        )
        connection.commit()
    with pytest.raises(RuntimeError, match="ownership mismatch"):
        ControlPlaneService(
            str(orphan_path),
            PurposeKeyring.generate_root_base64(),
            preview_mode=True,
        )
    with sqlite3.connect(orphan_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT screen_id FROM device_credential_families WHERE family_id = 'family-preserved'"
            ).fetchone()[0]
            == "rogue-screen"
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sites'"
            ).fetchone()
            is None
        )

    reordered_path = tmp_path / "reordered-registry.db"
    shutil.copy2(legacy_path, reordered_path)
    with sqlite3.connect(reordered_path) as connection:
        rows = connection.execute(
            "SELECT version, checksum_sha256, applied_at FROM schema_migrations ORDER BY rowid"
        ).fetchall()
        connection.execute("DELETE FROM schema_migrations")
        connection.executemany(
            """
            INSERT INTO schema_migrations(version, checksum_sha256, applied_at)
            VALUES (?, ?, ?)
            """,
            list(reversed(rows)),
        )
        connection.commit()
    with pytest.raises(RuntimeError, match="registry mismatch"):
        ControlPlaneService(
            str(reordered_path),
            PurposeKeyring.generate_root_base64(),
            preview_mode=True,
        )

    empty_registry_path = tmp_path / "empty-registry.db"
    shutil.copy2(pre_migration_copy, empty_registry_path)
    with sqlite3.connect(empty_registry_path) as connection:
        connection.execute("DELETE FROM schema_migrations")
        connection.commit()
    with pytest.raises(RuntimeError, match="missing the migration registry"):
        ControlPlaneService(
            str(empty_registry_path),
            PurposeKeyring.generate_root_base64(),
            preview_mode=True,
        )
    with sqlite3.connect(empty_registry_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM device_credential_families").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sites'"
            ).fetchone()
            is None
        )

    missing_registry_path = tmp_path / "missing-registry.db"
    shutil.copy2(pre_migration_copy, missing_registry_path)
    with sqlite3.connect(missing_registry_path) as connection:
        connection.execute("DROP TABLE schema_migrations")
        connection.commit()
    with pytest.raises(RuntimeError, match="missing the migration registry"):
        ControlPlaneService(
            str(missing_registry_path),
            PurposeKeyring.generate_root_base64(),
            preview_mode=True,
        )
    with sqlite3.connect(missing_registry_path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            is None
        )
        assert connection.execute("SELECT COUNT(*) FROM device_credential_families").fetchone()[0] == 1


def test_concurrent_group_membership_uses_one_winning_etag(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, _ = control_plane
    first_client, first_csrf = login(app, "implementation")
    second_client, second_csrf = login(app, "implementation")
    group = first_client.get("/api/v1/control-plane/screen-groups").json()["items"][0]
    members = group["member_screen_ids"]
    assert len(members) == 3

    def update(client: TestClient, csrf: str, next_members: list[str]) -> int:
        return client.patch(
            f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}",
            headers=mutation_headers(csrf, **{"If-Match": group["etag"]}),
            json={"member_screen_ids": next_members},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(update, first_client, first_csrf, members[:2])
        second = executor.submit(update, second_client, second_csrf, members[1:])
        statuses = sorted((first.result(), second.result()))
    assert statuses == [200, 412]
    final_members = first_client.get(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}"
    ).json()["member_screen_ids"]
    assert final_members in (members[:2], members[1:])


def test_accepted_p1_2_copy_upgrades_to_p1_3_and_source_is_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted_path = tmp_path / "accepted-p1-2.db"
    upgraded_path = tmp_path / "p1-3-candidate.db"
    root_key = PurposeKeyring.generate_root_base64()
    full_migrations = store_module.MIGRATIONS
    monkeypatch.setattr(store_module, "MIGRATIONS", full_migrations[:2])
    accepted = ControlPlaneService(
        str(accepted_path),
        root_key,
        preview_mode=True,
    )
    accepted.initialize_preview(
        tenant_id="tenant-p1-2-copy",
        deployment_id="deployment-p1-2-copy",
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
    with sqlite3.connect(accepted_path) as connection:
        assert (
            connection.execute(
                "SELECT version FROM schema_migrations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
            == full_migrations[1][0]
        )
        source_hash = hashlib.sha256(accepted_path.read_bytes()).hexdigest()
    copy_sqlite_database(str(accepted_path), str(upgraded_path))
    p1_3_migrations = full_migrations[:3]
    monkeypatch.setattr(store_module, "MIGRATIONS", p1_3_migrations)
    upgraded = ControlPlaneService(
        str(upgraded_path),
        root_key,
        preview_mode=True,
        backup_root=tmp_path / "p1-3-backups",
    )
    assert upgraded.status()["migration_version"] == full_migrations[2][0]
    with upgraded.store.connect() as connection:
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
            ).fetchall()
        ] == [(version, checksum) for version, checksum, _ in p1_3_migrations]
        bindings = connection.execute(
            """
            SELECT desired_release_target_id, applied_release_target_id,
                binding_generation
            FROM runtime_bindings ORDER BY screen_id
            """
        ).fetchall()
        assert len(bindings) == 3
        assert all(tuple(row) == (None, None, 0) for row in bindings)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert hashlib.sha256(accepted_path.read_bytes()).hexdigest() == source_hash
    with sqlite3.connect(accepted_path) as connection:
        assert (
            connection.execute(
                "SELECT version FROM schema_migrations ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
            == full_migrations[1][0]
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'config_releases'"
            ).fetchone()
            is None
        )


def create_p1_3_release(
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    target_type: str,
    target_id: str,
    expected_target_count: int,
    welcome_text: str,
    suffix: str,
) -> dict[str, Any]:
    created = implementation.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_impl,
            **{"Idempotency-Key": f"draft-create-{suffix}"},
        ),
        json={
            "target_type": target_type,
            "target_id": target_id,
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    replaced = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=mutation_headers(
            csrf_impl,
            **{"If-Match": draft["etag"]},
        ),
        json={
            "welcome_text": welcome_text,
            "fvs_binding_ref": f"https://fvs.example.test/{target_id}/{suffix}",
        },
    )
    assert replaced.status_code == 200, replaced.text
    draft = replaced.json()
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"draft-validate-{suffix}",
            },
        ),
    )
    assert validated.status_code == 200, validated.text
    draft = validated.json()
    assert draft["state"] == "VALIDATED"
    assert draft["validation"]["outcome"] == "VALID"
    previewed = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"draft-preview-{suffix}",
            },
        ),
    )
    assert previewed.status_code == 200, previewed.text
    draft = previewed.json()
    assert draft["state"] == "PREVIEWED"
    assert draft["preview"]["outcome"] == "MOCK_PASSED"
    submitted = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:submit-for-approval",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"draft-submit-{suffix}",
            },
        ),
    )
    assert submitted.status_code == 200, submitted.text
    draft = submitted.json()
    assert draft["state"] == "APPROVAL_PENDING"
    approved = approver.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_approver,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"draft-approve-{suffix}",
            },
        ),
        json={"reason": "independent release approval"},
    )
    assert approved.status_code == 200, approved.text
    draft = approved.json()
    assert draft["state"] == "APPROVED"
    assert draft["approval"]["last_editor_user_id"] != draft["approval"]["approver_user_id"]
    released = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:release",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"release-create-{suffix}",
            },
        ),
        json={"reason": "create immutable accepted candidate"},
    )
    assert released.status_code == 201, released.text
    result = released.json()
    assert result["creation_kind"] == "NORMAL"
    assert result["immutable"] is True
    assert len(result["targets"]) == expected_target_count
    return result


def publish_p1_3_group_release(
    requester: TestClient,
    csrf_requester: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    group: dict[str, Any],
    release: dict[str, Any],
    suffix: str,
) -> dict[str, Any]:
    targets_by_screen = {target["screen_id"]: target for target in release["targets"]}
    targets = []
    for screen_id in sorted(targets_by_screen):
        binding = requester.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        targets.append(
            {
                "screen_id": screen_id,
                "release_target_id": targets_by_screen[screen_id]["release_target_id"],
                "runtime_if_match": binding["etag"],
                "expected_binding_generation": binding["binding_generation"],
            }
        )
    payload = {
        "release_id": release["release_id"],
        "targets": targets,
        "reason": f"publish exact group release {suffix}",
    }
    action = request_action(
        requester,
        csrf_requester,
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        payload,
        f"group-request-{suffix}",
        extra_headers={"If-Match": group["etag"]},
    )
    approve_action(
        approver,
        csrf_approver,
        action,
        key=f"group-approve-{suffix}",
    )
    result = requester.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        headers=mutation_headers(
            csrf_requester,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": f"group-execute-{suffix}",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_p1_3_draft_release_publish_ack_and_forward_rollback(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    screen_id = screens[1]["screen_id"]

    first_release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN",
        target_id=screen_id,
        expected_target_count=1,
        welcome_text="第一版欢迎语",
        suffix="first",
    )
    second_release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN",
        target_id=screen_id,
        expected_target_count=1,
        welcome_text="第二版欢迎语",
        suffix="second",
    )
    sibling_release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN",
        target_id=screens[0]["screen_id"],
        expected_target_count=1,
        welcome_text="兄弟屏幕版本",
        suffix="sibling",
    )
    enrollment_payload = {"reason": "enroll device for release acknowledgement"}
    enrollment_action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        enrollment_payload,
        "p13-enroll-request",
    )
    approve_action(admin_b, csrf_b, enrollment_action, key="p13-enroll-approve")
    issued = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "p13-enroll-execute",
                "High-Risk-Action-ID": enrollment_action["high_risk_action_id"],
            },
        ),
        json=enrollment_payload,
    )
    assert issued.status_code == 201, issued.text
    device = TestClient(app, base_url="https://device.test")
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "p13-device-claim"},
        json={"enrollment_token": issued.json()["enrollment_token"]},
    )
    assert claimed.status_code == 200, claimed.text
    device_headers = {"Authorization": f"DeviceCredential {claimed.json()['credential']}"}
    difference = implementation.get(
        "/api/v1/control-plane/config-release-diffs",
        params={
            "from": first_release["release_id"],
            "to": second_release["release_id"],
        },
    )
    assert difference.status_code == 200, difference.text
    field_changes = difference.json()["changes"][0]["field_changes"]
    assert {item["path"] for item in field_changes} == {
        "/fvs_binding_ref",
        "/welcome_text",
    }

    bindings_before = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    }
    binding = bindings_before[screen_id]
    target = second_release["targets"][0]
    publish_payload = {
        "release_id": second_release["release_id"],
        "release_target_id": target["release_target_id"],
        "expected_binding_generation": binding["binding_generation"],
        "reason": "publish second release",
    }
    action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        publish_payload,
        "publish-request-second",
        extra_headers={"If-Match": binding["etag"]},
    )
    approve_action(admin_b, csrf_b, action, key="publish-approve-second")
    published = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": "publish-execute-second",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=publish_payload,
    )
    assert published.status_code == 201, published.text
    assert published.json()["kind"] == "CONFIG_RELEASE_PUBLISHED"
    assert published.json()["publication"]["targets"][0]["state"] == "APPLYING"
    current = device.get(
        "/api/v1/device/config-releases/current",
        headers=device_headers,
    )
    assert current.status_code == 200, current.text
    assert current.json()["state"] == "DESIRED_AVAILABLE"
    assert current.json()["release_target"]["release_target_id"] == target["release_target_id"]
    wrong_screen_ack = device.post(
        (f"/api/v1/device/config-releases/{sibling_release['targets'][0]['release_target_id']}:ack"),
        headers={**device_headers, "Idempotency-Key": "p13-ack-wrong-screen"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": sibling_release["targets"][0]["content_hash"],
        },
    )
    assert wrong_screen_ack.status_code == 404
    assert wrong_screen_ack.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    wrong_ack = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-wrong-hash"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": "0" * 64,
        },
    )
    assert wrong_ack.status_code == 412
    assert wrong_ack.json()["error"]["code"] == "ACTIVE_RELEASE_CHANGED"
    stale_generation_ack = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-stale-generation"},
        json={
            "binding_generation": current.json()["binding_generation"] + 1,
            "content_hash": target["content_hash"],
        },
    )
    assert stale_generation_ack.status_code == 412
    assert stale_generation_ack.json()["error"]["code"] == "ACTIVE_RELEASE_CHANGED"
    acknowledged = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-second"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["state"] == "ACTIVE"
    acknowledgement_replay = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-second"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    assert acknowledgement_replay.status_code == 200
    assert acknowledgement_replay.json() == acknowledged.json()
    changed_ack_replay = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-second"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": "1" * 64,
        },
    )
    assert changed_ack_replay.status_code == 409
    assert changed_ack_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    bindings_after_ack = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    }
    for sibling_id in set(bindings_before) - {screen_id}:
        assert bindings_after_ack[sibling_id] == bindings_before[sibling_id]
    assert bindings_after_ack[screen_id]["binding_generation"] == (
        bindings_before[screen_id]["binding_generation"] + 1
    )
    assert bindings_after_ack[screen_id]["applied_release_target_id"] == target["release_target_id"]

    credential_id = claimed.json()["credential_id"]
    credential_metadata = admin_a.get(
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-credentials/{credential_id}"
    )
    assert credential_metadata.status_code == 200
    revoke_payload = {
        "expected_credential_epoch": credential_metadata.json()["credential_epoch"],
        "reason": "revoked credential must not acknowledge a release",
    }
    revoke_path = (
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-credentials/{credential_id}:revoke"
    )
    revoke_action = request_action(
        admin_a,
        csrf_a,
        revoke_path,
        revoke_payload,
        "p13-ack-revoke-request",
        extra_headers={"If-Match": credential_metadata.json()["family_etag"]},
    )
    approve_action(admin_b, csrf_b, revoke_action, key="p13-ack-revoke-approve")
    revoked = admin_a.post(
        revoke_path,
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": credential_metadata.json()["family_etag"],
                "Idempotency-Key": "p13-ack-revoke-execute",
                "High-Risk-Action-ID": revoke_action["high_risk_action_id"],
            },
        ),
        json=revoke_payload,
    )
    assert revoked.status_code == 200, revoked.text
    revoked_ack = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={**device_headers, "Idempotency-Key": "p13-ack-revoked"},
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    assert revoked_ack.status_code == 401

    stale_publish = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": "publish-stale-request",
            },
        ),
        json={
            **publish_payload,
            "release_id": first_release["release_id"],
            "release_target_id": first_release["targets"][0]["release_target_id"],
        },
    )
    assert stale_publish.status_code == 412
    assert stale_publish.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"

    current_binding = implementation.get(
        f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding"
    ).json()
    rollback_payload = {
        "source_release_target_id": first_release["targets"][0]["release_target_id"],
        "expected_binding_generation": current_binding["binding_generation"],
        "reason": "forward rollback to first release content",
    }
    rollback_action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/rollbacks",
        rollback_payload,
        "rollback-request-first",
        extra_headers={"If-Match": current_binding["etag"]},
    )
    approve_action(admin_b, csrf_b, rollback_action, key="rollback-approve-first")
    rollback = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/rollbacks",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": current_binding["etag"],
                "Idempotency-Key": "rollback-execute-first",
                "High-Risk-Action-ID": rollback_action["high_risk_action_id"],
            },
        ),
        json=rollback_payload,
    )
    assert rollback.status_code == 201, rollback.text
    rollback_result = rollback.json()
    assert rollback_result["kind"] == "CONFIG_ROLLBACK_PUBLISHED"
    assert rollback_result["release"]["creation_kind"] == "ROLLBACK"
    assert rollback_result["release"]["release_id"] not in {
        first_release["release_id"],
        second_release["release_id"],
    }
    with sqlite3.connect(database_path) as connection:
        immutable_update = pytest.raises(
            sqlite3.IntegrityError,
            connection.execute,
            "UPDATE config_releases SET reason = 'tampered' WHERE release_id = ?",
            (first_release["release_id"],),
        )
        assert "immutable" in str(immutable_update.value).lower()


def test_p1_3_group_publication_is_atomic_and_scope_bound(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, _, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    auditor, csrf_auditor = login(app, "auditor")
    group = implementation.get("/api/v1/control-plane/screen-groups").json()["items"][0]
    release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN_GROUP",
        target_id=group["screen_group_id"],
        expected_target_count=3,
        welcome_text="三屏统一发布",
        suffix="group",
    )
    alternate_release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN_GROUP",
        target_id=group["screen_group_id"],
        expected_target_count=3,
        welcome_text="三屏混合历史回退源",
        suffix="group-alternate",
    )
    screens = implementation.get("/api/v1/control-plane/screen-instances").json()["items"]
    bindings_before = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    }
    targets_by_screen = {target["screen_id"]: target for target in release["targets"]}
    targets = [
        {
            "screen_id": screen_id,
            "release_target_id": targets_by_screen[screen_id]["release_target_id"],
            "runtime_if_match": binding["etag"],
            "expected_binding_generation": binding["binding_generation"],
        }
        for screen_id, binding in sorted(bindings_before.items())
    ]
    stale_targets = [dict(item) for item in targets]
    stale_targets[1]["expected_binding_generation"] += 1
    stale = implementation.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": "group-publish-stale",
            },
        ),
        json={
            "release_id": release["release_id"],
            "targets": stale_targets,
            "reason": "stale group publication must fail",
        },
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "RESOURCE_VERSION_CONFLICT"
    assert {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    } == bindings_before

    crossed_targets = [dict(item) for item in targets]
    crossed_targets[0]["release_target_id"], crossed_targets[1]["release_target_id"] = (
        crossed_targets[1]["release_target_id"],
        crossed_targets[0]["release_target_id"],
    )
    crossed = implementation.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": "group-publish-crossed",
            },
        ),
        json={
            "release_id": release["release_id"],
            "targets": crossed_targets,
            "reason": "cross-screen target mapping must fail",
        },
    )
    assert crossed.status_code in {409, 422}
    assert crossed.json()["error"]["code"] in {
        "PUBLISH_TARGET_CHANGED",
        "SCHEMA_VALIDATION_FAILED",
    }

    payload = {
        "release_id": release["release_id"],
        "targets": targets,
        "reason": "publish exact frozen three-screen release",
    }
    action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        payload,
        "group-publish-request",
        extra_headers={"If-Match": group["etag"]},
    )
    approve_action(admin_b, csrf_b, action, key="group-publish-approve")
    published = implementation.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": "group-publish-execute",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    assert published.status_code == 201, published.text
    result_targets = published.json()["publication"]["targets"]
    assert len(result_targets) == 3
    assert {item["state"] for item in result_targets} == {"WAITING_FOR_DEVICE"}
    bindings_after = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    }
    for screen_id in bindings_before:
        assert bindings_after[screen_id]["binding_generation"] == (
            bindings_before[screen_id]["binding_generation"] + 1
        )
        assert (
            bindings_after[screen_id]["desired_release_target_id"]
            == (targets_by_screen[screen_id]["release_target_id"])
        )
        assert (
            bindings_after[screen_id]["digital_human_instance_id"]
            == (bindings_before[screen_id]["digital_human_instance_id"])
        )
        assert bindings_after[screen_id]["applied_release_target_id"] is None
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM publication_targets WHERE publication_id = ?",
                (published.json()["publication"]["publication_id"],),
            ).fetchone()[0]
            == 3
        )

    alternate_by_screen = {target["screen_id"]: target for target in alternate_release["targets"]}
    sorted_screen_ids = sorted(bindings_after)
    crossed_sources = [
        {
            "screen_id": screen_id,
            "source_release_target_id": targets_by_screen[
                sorted_screen_ids[(index + 1) % len(sorted_screen_ids)]
            ]["release_target_id"],
        }
        for index, screen_id in enumerate(sorted_screen_ids)
    ]
    rollback_targets = [
        {
            "screen_id": screen_id,
            "release_target_id": targets_by_screen[screen_id]["release_target_id"],
            "runtime_if_match": bindings_after[screen_id]["etag"],
            "expected_binding_generation": bindings_after[screen_id]["binding_generation"],
        }
        for screen_id in sorted_screen_ids
    ]
    crossed_rollback = implementation.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/rollbacks",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": "group-rollback-crossed",
            },
        ),
        json={
            "source_targets": crossed_sources,
            "targets": rollback_targets,
            "reason": "cross-screen rollback sources must fail",
        },
    )
    assert crossed_rollback.status_code == 404
    assert crossed_rollback.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    mixed_sources = [
        {
            "screen_id": screen_id,
            "source_release_target_id": (
                alternate_by_screen[screen_id]["release_target_id"]
                if index == 1
                else targets_by_screen[screen_id]["release_target_id"]
            ),
        }
        for index, screen_id in enumerate(sorted_screen_ids)
    ]
    rollback_payload = {
        "source_targets": mixed_sources,
        "targets": rollback_targets,
        "reason": "rollback group from an explicit mixed historical source map",
    }
    rollback_action = request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/rollbacks",
        rollback_payload,
        "group-rollback-request",
        extra_headers={"If-Match": group["etag"]},
    )
    approve_action(admin_b, csrf_b, rollback_action, key="group-rollback-approve")
    rolled_back = implementation.post(
        f"/api/v1/control-plane/screen-groups/{group['screen_group_id']}/rollbacks",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": group["etag"],
                "Idempotency-Key": "group-rollback-execute",
                "High-Risk-Action-ID": rollback_action["high_risk_action_id"],
            },
        ),
        json=rollback_payload,
    )
    assert rolled_back.status_code == 201, rolled_back.text
    rollback_result = rolled_back.json()
    assert rollback_result["kind"] == "CONFIG_ROLLBACK_PUBLISHED"
    assert rollback_result["release"]["creation_kind"] == "ROLLBACK"
    provenance_by_screen = {target["screen_id"]: target for target in rollback_result["release"]["targets"]}
    assert {
        screen_id: provenance_by_screen[screen_id]["rollback_source_target_id"]
        for screen_id in sorted_screen_ids
    } == {item["screen_id"]: item["source_release_target_id"] for item in mixed_sources}
    bindings_after_rollback = {
        screen["screen_id"]: implementation.get(
            f"/api/v1/control-plane/screen-instances/{screen['screen_id']}/runtime-binding"
        ).json()
        for screen in screens
    }
    for screen_id in sorted_screen_ids:
        assert bindings_after_rollback[screen_id]["binding_generation"] == (
            bindings_after[screen_id]["binding_generation"] + 1
        )
        assert (
            bindings_after_rollback[screen_id]["desired_release_target_id"]
            == provenance_by_screen[screen_id]["release_target_id"]
        )

    denied_draft = auditor.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_auditor,
            **{"Idempotency-Key": "auditor-draft-denied"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": screens[0]["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert denied_draft.status_code == 403
    denied_backup = auditor.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_auditor,
            **{"Idempotency-Key": "auditor-backup-denied"},
        ),
        json={"reason": "auditor mutation must fail"},
    )
    assert denied_backup.status_code == 403


def test_p1_3_draft_guards_stale_fingerprint_self_approval_and_idempotency(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = control_plane
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    auditor, csrf_auditor = login(app, "auditor")
    screens = admin_a.get("/api/v1/control-plane/screen-instances").json()["items"]
    business_password = f"test-only-{secrets.token_urlsafe(18)}"
    PASSWORDS["business-only"] = business_password
    with service.store.transaction() as connection:
        now = service.clock()
        connection.execute(
            """
            INSERT INTO users(
                user_id, tenant_id, deployment_id, normalized_username,
                display_name, account_state, password_verifier,
                credential_generation, created_at, updated_at
            ) VALUES (
                'usr_business_only', 'tenant-test', 'deployment-test',
                'business-only', 'Business Only', 'ACTIVE', ?, 1, ?, ?
            )
            """,
            (
                service.passwords.hash(
                    business_password,
                    username="business-only",
                ),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO role_assignments(
                assignment_id, user_id, role_id, scope_type, scope_id, created_at
            ) VALUES (
                'rla_business_only', 'usr_business_only', 'business_operator',
                'DEPLOYMENT', 'deployment-test', ?
            )
            """,
            (now,),
        )
    business, csrf_business = login(app, "business-only")
    business_draft = business.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_business,
            **{"Idempotency-Key": "business-only-draft"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": screens[0]["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert business_draft.status_code == 201
    mixed_field_denied = business.put(
        f"/api/v1/control-plane/config-drafts/{business_draft.json()['draft_id']}/spec",
        headers=mutation_headers(
            csrf_business,
            **{"If-Match": business_draft.json()["etag"]},
        ),
        json={
            "welcome_text": "business-visible text",
            "fvs_binding_ref": "https://fvs.example.test/business-denied",
        },
    )
    assert mixed_field_denied.status_code == 403
    assert mixed_field_denied.json()["error"]["code"] == "FORBIDDEN"
    admin_populated = admin_a.put(
        f"/api/v1/control-plane/config-drafts/{business_draft.json()['draft_id']}/spec",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": business_draft.json()["etag"]},
        ),
        json={
            "welcome_text": "implementation-owned initial text",
            "fvs_binding_ref": "https://fvs.example.test/business-leaf-diff",
        },
    )
    assert admin_populated.status_code == 200, admin_populated.text
    business_leaf_edit = business.put(
        f"/api/v1/control-plane/config-drafts/{business_draft.json()['draft_id']}/spec",
        headers=mutation_headers(
            csrf_business,
            **{"If-Match": admin_populated.json()["etag"]},
        ),
        json={
            "welcome_text": "business-owned text only",
            "fvs_binding_ref": "https://fvs.example.test/business-leaf-diff",
        },
    )
    assert business_leaf_edit.status_code == 200, business_leaf_edit.text
    assert business_leaf_edit.json()["spec"]["welcome_text"] == "business-owned text only"
    technical_leaf_denied = business.put(
        f"/api/v1/control-plane/config-drafts/{business_draft.json()['draft_id']}/spec",
        headers=mutation_headers(
            csrf_business,
            **{"If-Match": business_leaf_edit.json()["etag"]},
        ),
        json={
            "welcome_text": "business-owned text only",
            "fvs_binding_ref": "https://fvs.example.test/technical-denied",
        },
    )
    assert technical_leaf_denied.status_code == 403
    unchanged_leaf_draft = business.get(
        f"/api/v1/control-plane/config-drafts/{business_draft.json()['draft_id']}"
    )
    assert unchanged_leaf_draft.json()["etag"] == business_leaf_edit.json()["etag"]
    assert (
        unchanged_leaf_draft.json()["spec"]["fvs_binding_ref"]
        == "https://fvs.example.test/business-leaf-diff"
    )
    target_screen = screens[2]
    created = admin_a.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "draft-guard-create"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": target_screen["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    changed_replay = admin_a.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "draft-guard-create"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": screens[1]["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    early_preview = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-early-preview",
            },
        ),
    )
    assert early_preview.status_code == 409
    assert early_preview.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    replaced = admin_a.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": draft["etag"]},
        ),
        json={
            "welcome_text": "审批护栏验证",
            "fvs_binding_ref": "https://fvs.example.test/guard",
        },
    )
    assert replaced.status_code == 200, replaced.text
    stale_edit = admin_a.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": draft["etag"]},
        ),
        json={
            "welcome_text": "stale edit",
            "fvs_binding_ref": "https://fvs.example.test/stale",
        },
    )
    assert stale_edit.status_code == 412
    draft = replaced.json()
    for operation, key in (
        ("validate", "draft-guard-validate"),
        ("preview", "draft-guard-preview"),
        ("submit-for-approval", "draft-guard-submit"),
    ):
        response = admin_a.post(
            f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:{operation}",
            headers=mutation_headers(
                csrf_a,
                **{
                    "If-Match": draft["etag"],
                    "Idempotency-Key": key,
                },
            ),
        )
        assert response.status_code == 200, response.text
        draft = response.json()
    target_current = admin_a.get(
        f"/api/v1/control-plane/screen-instances/{target_screen['screen_id']}"
    ).json()
    changed_target = admin_a.patch(
        f"/api/v1/control-plane/screen-instances/{target_screen['screen_id']}",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": target_current["etag"]},
        ),
        json={"display_name": "changed after preview"},
    )
    assert changed_target.status_code == 200, changed_target.text
    stale_approval = admin_b.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_b,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-stale-approve",
            },
        ),
        json={"reason": "stale fingerprint must fail"},
    )
    assert stale_approval.status_code == 409
    assert stale_approval.json()["error"]["code"] == "RESOLUTION_FINGERPRINT_STALE"
    revised = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:revise",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-revise",
            },
        ),
    )
    assert revised.status_code == 200, revised.text
    draft = revised.json()
    assert draft["state"] == "DRAFT"
    for operation, key in (
        ("validate", "draft-guard-revalidate"),
        ("preview", "draft-guard-repreview"),
        ("submit-for-approval", "draft-guard-resubmit"),
    ):
        response = admin_a.post(
            f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:{operation}",
            headers=mutation_headers(
                csrf_a,
                **{
                    "If-Match": draft["etag"],
                    "Idempotency-Key": key,
                },
            ),
        )
        assert response.status_code == 200, response.text
        draft = response.json()
    self_approval = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-self-approve",
            },
        ),
        json={"reason": "self approval must fail"},
    )
    assert self_approval.status_code == 403
    denied_approval = auditor.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_auditor,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-auditor-approve",
            },
        ),
        json={"reason": "auditor approval must fail"},
    )
    assert denied_approval.status_code == 403
    approved = admin_b.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=mutation_headers(
            csrf_b,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": "draft-guard-valid-approve",
            },
        ),
        json={"reason": "independent approval after refresh"},
    )
    assert approved.status_code == 200, approved.text
    terminal_edit = admin_a.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": approved.json()["etag"]},
        ),
        json={
            "welcome_text": "approved draft cannot be edited",
            "fvs_binding_ref": "https://fvs.example.test/terminal",
        },
    )
    assert terminal_edit.status_code == 409
    assert terminal_edit.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_p1_3_validation_failure_is_recorded_as_invalid_draft(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, _ = control_plane
    admin_a, csrf_a = login(app, "admin-a")
    site = admin_a.get("/api/v1/control-plane/sites").json()["items"][0]
    created_screen = admin_a.post(
        f"/api/v1/control-plane/sites/{site['site_id']}/screen-instances",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "invalid-validation-screen"},
        ),
        json={
            "slug": "invalid-validation-screen",
            "display_name": "Invalid validation screen",
            "fvs_binding_ref": "fvs-invalid-validation-screen",
        },
    )
    assert created_screen.status_code == 201, created_screen.text
    assert created_screen.json()["digital_human_instance"] is None
    created_draft = admin_a.post(
        "/api/v1/control-plane/config-drafts",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "invalid-validation-draft"},
        ),
        json={
            "target_type": "SCREEN",
            "target_id": created_screen.json()["screen_id"],
            "schema_version": "p1_screen_config_v1",
        },
    )
    assert created_draft.status_code == 201, created_draft.text
    populated = admin_a.put(
        f"/api/v1/control-plane/config-drafts/{created_draft.json()['draft_id']}/spec",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": created_draft.json()["etag"]},
        ),
        json={
            "welcome_text": "valid fields on an incomplete target",
            "fvs_binding_ref": "https://fvs.example.test/invalid-target",
        },
    )
    assert populated.status_code == 200, populated.text
    validation_headers = mutation_headers(
        csrf_a,
        **{
            "If-Match": populated.json()["etag"],
            "Idempotency-Key": "invalid-validation-attempt",
        },
    )
    invalid = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{created_draft.json()['draft_id']}:validate",
        headers=validation_headers,
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["state"] == "DRAFT"
    assert invalid.json()["outcome"] == "INVALID"
    assert invalid.json()["validation"]["outcome"] == "INVALID"
    assert invalid.json()["validation"]["fingerprint_hash"] is None
    assert invalid.json()["findings"] == [
        {
            "severity": "ERROR",
            "code": "TARGET_INVENTORY_INCOMPLETE",
            "message": "Draft target inventory is incomplete",
        }
    ]
    replay = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{created_draft.json()['draft_id']}:validate",
        headers=validation_headers,
    )
    assert replay.status_code == 200
    assert replay.json() == invalid.json()
    persisted = admin_a.get(f"/api/v1/control-plane/config-drafts/{created_draft.json()['draft_id']}")
    assert persisted.status_code == 200
    assert persisted.json()["state"] == "DRAFT"
    assert persisted.json()["validation"] == invalid.json()["validation"]
    denied_preview = admin_a.post(
        f"/api/v1/control-plane/config-drafts/{created_draft.json()['draft_id']}:preview",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": persisted.json()["etag"],
                "Idempotency-Key": "invalid-validation-preview-denied",
            },
        ),
    )
    assert denied_preview.status_code == 409
    with service.store.connect() as connection:
        record = connection.execute(
            """
            SELECT outcome, fingerprint_id, fingerprint_hash
            FROM validation_records WHERE validation_record_id = ?
            """,
            (invalid.json()["validation"]["validation_record_id"],),
        ).fetchone()
        assert tuple(record) == ("INVALID", None, None)


def test_p1_3_backup_creation_rejects_invalid_source_snapshot(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
) -> None:
    app, service, database_path = control_plane
    admin_a, csrf_a = login(app, "admin-a")
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            """
            INSERT INTO role_assignments(
                assignment_id, user_id, role_id, scope_type, scope_id, created_at
            ) VALUES (
                'rla_orphan_backup_source', 'usr_missing_backup_source',
                'auditor', 'DEPLOYMENT', 'deployment-test', ?
            )
            """,
            (service.clock(),),
        )
        connection.commit()
    rejected = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "invalid-source-backup"},
        ),
        json={"reason": "invalid source snapshot must fail before verified"},
    )
    assert rejected.status_code == 503
    assert rejected.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    with service.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM backup_records").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall()
    assert not list(service.p1_3.backups.backup_root.glob("backup-*"))
    assert not list(service.p1_3.backups.backup_root.glob(".*.tmp-*"))


def test_p1_3_encrypted_backup_tamper_wrong_key_and_staged_restore(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, service, database_path = control_plane
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen_before = admin_a.get("/api/v1/control-plane/screen-instances/screen-trust-fixture").json()
    group = admin_a.get("/api/v1/control-plane/screen-groups").json()["items"][0]
    backup_release = create_p1_3_release(
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        target_type="SCREEN_GROUP",
        target_id=group["screen_group_id"],
        expected_target_count=3,
        welcome_text="备份中的三屏版本",
        suffix="restore-backup",
    )
    publish_p1_3_group_release(
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        group=group,
        release=backup_release,
        suffix="restore-backup",
    )
    backup_bindings = {
        screen_id: admin_a.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        for screen_id in group["member_screen_ids"]
    }

    created = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-backup-create"},
        ),
        json={"reason": "verified restore candidate"},
    )
    assert created.status_code == 201, created.text
    backup = created.json()
    assert backup["state"] == "VERIFIED"
    assert backup["recovery_key_in_bundle"] is False
    bundle_name = f"backup-{backup['backup_id']}"
    bundle_dir = service.p1_3.backups.backup_root / bundle_name
    assert {item.name for item in bundle_dir.iterdir() if item.is_file()} == {
        "manifest.json",
        "payload.aes256gcm",
        "checksums.sha256",
        "verification.json",
    }
    payload_path = bundle_dir / "payload.aes256gcm"
    original_payload = payload_path.read_bytes()
    payload_path.write_bytes(bytes([original_payload[0] ^ 1]) + original_payload[1:])
    tampered = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-backup-tampered"},
        ),
    )
    assert tampered.status_code == 503
    assert tampered.json()["error"]["code"] == "CRYPTOGRAPHIC_INTEGRITY_FAILURE"
    payload_path.write_bytes(original_payload)

    wrong_key_manager = BackupManager(
        service.store,
        PurposeKeyring.from_base64(PurposeKeyring.generate_root_base64()),
        service.p1_3.backups.backup_root,
    )
    with pytest.raises(BackupIntegrityError, match="key is unavailable|authentication failed"):
        wrong_key_manager.verify_bundle(bundle_name)
    verified = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-backup-verified"},
        ),
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["outcome"] == "VERIFIED"
    original_bundle_files = {
        name: (bundle_dir / name).read_bytes()
        for name in (
            "manifest.json",
            "payload.aes256gcm",
            "checksums.sha256",
            "verification.json",
        )
    }
    pre_substitution_plan = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-pre-substitution-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert pre_substitution_plan.status_code == 201, pre_substitution_plan.text
    pre_substitution_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "prove registered backup identity is enforced",
    }
    pre_substitution_action = request_action(
        admin_a,
        csrf_a,
        (f"/api/v1/control-plane/restore-plans/{pre_substitution_plan.json()['restore_plan_id']}:execute"),
        pre_substitution_payload,
        "p13-pre-substitution-request",
        extra_headers={"If-Match": pre_substitution_plan.json()["etag"]},
    )
    approve_action(
        admin_b,
        csrf_b,
        pre_substitution_action,
        key="p13-pre-substitution-approve",
    )
    second_backup_response = admin_a.post(
        "/api/v1/control-plane/backups",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-second-valid-backup"},
        ),
        json={"reason": "valid bundle used for substitution negative test"},
    )
    assert second_backup_response.status_code == 201, second_backup_response.text
    second_bundle_dir = (
        service.p1_3.backups.backup_root / f"backup-{second_backup_response.json()['backup_id']}"
    )
    for name in original_bundle_files:
        shutil.copy2(second_bundle_dir / name, bundle_dir / name)
    substituted_verify = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-substituted-verify"},
        ),
    )
    assert substituted_verify.status_code == 503
    assert substituted_verify.json()["error"]["code"] == "CRYPTOGRAPHIC_INTEGRITY_FAILURE"
    substituted_plan = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-substituted-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert substituted_plan.status_code == 503
    assert substituted_plan.json()["error"]["code"] == "CRYPTOGRAPHIC_INTEGRITY_FAILURE"
    substituted_restore = admin_a.post(
        (f"/api/v1/control-plane/restore-plans/{pre_substitution_plan.json()['restore_plan_id']}:execute"),
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": pre_substitution_plan.json()["etag"],
                "Idempotency-Key": "p13-pre-substitution-execute",
                "High-Risk-Action-ID": pre_substitution_action["high_risk_action_id"],
            },
        ),
        json=pre_substitution_payload,
    )
    assert substituted_restore.status_code == 503
    assert substituted_restore.json()["error"]["code"] == "CRYPTOGRAPHIC_INTEGRITY_FAILURE"
    assert {
        screen_id: admin_a.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        for screen_id in group["member_screen_ids"]
    } == backup_bindings
    for name, content in original_bundle_files.items():
        (bundle_dir / name).write_bytes(content)
    restored_identity_verify = admin_a.post(
        f"/api/v1/control-plane/backups/{backup['backup_id']}:verify",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-restored-identity-verify"},
        ),
    )
    assert restored_identity_verify.status_code == 200, restored_identity_verify.text
    changed_release = create_p1_3_release(
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        target_type="SCREEN_GROUP",
        target_id=group["screen_group_id"],
        expected_target_count=3,
        welcome_text="恢复前必须被替换的三屏版本",
        suffix="restore-changed",
    )
    publish_p1_3_group_release(
        admin_a,
        csrf_a,
        admin_b,
        csrf_b,
        group=group,
        release=changed_release,
        suffix="restore-changed",
    )
    changed_bindings = {
        screen_id: admin_a.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        for screen_id in group["member_screen_ids"]
    }
    assert all(
        changed_bindings[screen_id]["desired_release_target_id"]
        != backup_bindings[screen_id]["desired_release_target_id"]
        for screen_id in group["member_screen_ids"]
    )

    user_payload = {
        "normalized_username": "post-backup-user",
        "display_name": "Post Backup User",
        "reason": "prove newer live identity survives restore",
    }
    user_action = request_action(
        admin_a,
        csrf_a,
        "/api/v1/control-plane/users",
        user_payload,
        "restore-live-user-request",
    )
    approve_action(admin_b, csrf_b, user_action, key="restore-live-user-approve")
    user_created = admin_a.post(
        "/api/v1/control-plane/users",
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "restore-live-user-execute",
                "High-Risk-Action-ID": user_action["high_risk_action_id"],
            },
        ),
        json=user_payload,
    )
    assert user_created.status_code == 201, user_created.text
    post_backup_user_id = user_created.json()["user"]["user_id"]

    screens = admin_a.get("/api/v1/control-plane/screen-instances").json()["items"]
    active_screen_id = screens[1]["screen_id"]
    active_enrollment_payload = {"reason": "new live device must survive restore"}
    active_enrollment_action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/screen-instances/{active_screen_id}/device-enrollments",
        active_enrollment_payload,
        "restore-live-device-request",
    )
    approve_action(
        admin_b,
        csrf_b,
        active_enrollment_action,
        key="restore-live-device-approve",
    )
    active_issued = admin_a.post(
        f"/api/v1/control-plane/screen-instances/{active_screen_id}/device-enrollments",
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "restore-live-device-execute",
                "High-Risk-Action-ID": active_enrollment_action["high_risk_action_id"],
            },
        ),
        json=active_enrollment_payload,
    )
    assert active_issued.status_code == 201, active_issued.text
    device = TestClient(app, base_url="https://device.test")
    active_claim = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "restore-live-device-claim"},
        json={"enrollment_token": active_issued.json()["enrollment_token"]},
    )
    assert active_claim.status_code == 200, active_claim.text
    active_device_credential = active_claim.json()["credential"]

    pending_screen_id = screens[2]["screen_id"]
    pending_enrollment_payload = {"reason": "one-time enrollment must be revoked by restore"}
    pending_enrollment_action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/screen-instances/{pending_screen_id}/device-enrollments",
        pending_enrollment_payload,
        "restore-pending-token-request",
    )
    approve_action(
        admin_b,
        csrf_b,
        pending_enrollment_action,
        key="restore-pending-token-approve",
    )
    pending_issued = admin_a.post(
        f"/api/v1/control-plane/screen-instances/{pending_screen_id}/device-enrollments",
        headers=mutation_headers(
            csrf_a,
            **{
                "Idempotency-Key": "restore-pending-token-execute",
                "High-Risk-Action-ID": pending_enrollment_action["high_risk_action_id"],
            },
        ),
        json=pending_enrollment_payload,
    )
    assert pending_issued.status_code == 201, pending_issued.text
    pending_token = pending_issued.json()["enrollment_token"]
    unfinished_action = request_action(
        admin_a,
        csrf_a,
        "/api/v1/control-plane/users",
        {
            "normalized_username": "unfinished-user",
            "display_name": "Unfinished User",
            "reason": "unfinished action must fail after restore",
        },
        "restore-unfinished-action",
    )

    plan_response = admin_a.post(
        "/api/v1/control-plane/restore-plans",
        headers=mutation_headers(
            csrf_a,
            **{"Idempotency-Key": "p13-restore-plan"},
        ),
        json={"backup_id": backup["backup_id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    assert plan["state"] == "READY"
    changed = admin_a.patch(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture",
        headers=mutation_headers(
            csrf_a,
            **{"If-Match": screen_before["etag"]},
        ),
        json={"display_name": "must disappear after restore"},
    )
    assert changed.status_code == 200, changed.text

    restore_payload = {
        "confirmation": "RESTORE_VERIFIED_BACKUP",
        "reason": "restore the verified online snapshot",
    }
    restore_action = request_action(
        admin_a,
        csrf_a,
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        restore_payload,
        "p13-restore-request",
        extra_headers={"If-Match": plan["etag"]},
    )
    approve_action(admin_b, csrf_b, restore_action, key="p13-restore-approve")
    payload_path.write_bytes(bytes([original_payload[0] ^ 1]) + original_payload[1:])
    failed_restore = admin_a.post(
        f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
        headers=mutation_headers(
            csrf_a,
            **{
                "If-Match": plan["etag"],
                "Idempotency-Key": "p13-restore-execute",
                "High-Risk-Action-ID": restore_action["high_risk_action_id"],
            },
        ),
        json=restore_payload,
    )
    assert failed_restore.status_code == 503
    assert failed_restore.json()["error"]["code"] == "CRYPTOGRAPHIC_INTEGRITY_FAILURE"
    unchanged_after_failure = admin_a.get("/api/v1/control-plane/screen-instances/screen-trust-fixture")
    assert unchanged_after_failure.status_code == 200
    assert unchanged_after_failure.json()["display_name"] == "must disappear after restore"
    assert {
        screen_id: admin_a.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        for screen_id in group["member_screen_ids"]
    } == changed_bindings
    payload_path.write_bytes(original_payload)
    concurrent_admin, csrf_concurrent = login(app, "admin-a")
    race_user_payload = {
        "normalized_username": "restore-race-user",
        "display_name": "Restore Race User",
        "reason": "must commit after restore cutover without being lost",
    }
    race_user_action = request_action(
        concurrent_admin,
        csrf_concurrent,
        "/api/v1/control-plane/users",
        race_user_payload,
        "restore-race-user-request",
    )
    approve_action(admin_b, csrf_b, race_user_action, key="restore-race-user-approve")
    race_cookie = concurrent_admin.cookies.get("__Host-shuziren_session")
    assert race_cookie
    race_context = service.authenticate_session(race_cookie)
    original_capture = service.p1_3._capture_live_reconciliation
    capture_completed = threading.Event()
    release_capture = threading.Event()
    mutation_started = threading.Event()

    def blocking_capture(connection: sqlite3.Connection) -> dict[str, Any]:
        captured = original_capture(connection)
        capture_completed.set()
        assert release_capture.wait(10)
        return captured

    def execute_restore() -> Any:
        return admin_a.post(
            f"/api/v1/control-plane/restore-plans/{plan['restore_plan_id']}:execute",
            headers=mutation_headers(
                csrf_a,
                **{
                    "If-Match": plan["etag"],
                    "Idempotency-Key": "p13-restore-execute",
                    "High-Risk-Action-ID": restore_action["high_risk_action_id"],
                },
            ),
            json=restore_payload,
        )

    def execute_racing_user_creation() -> Any:
        mutation_started.set()
        try:
            return service.request_or_execute_user_creation(
                race_context,
                normalized_username=race_user_payload["normalized_username"],
                display_name=race_user_payload["display_name"],
                reason=race_user_payload["reason"],
                idempotency_key="restore-race-user-execute",
                high_risk_action_id=race_user_action["high_risk_action_id"],
            )
        except ControlPlaneError as exc:
            return exc

    monkeypatch.setattr(service.p1_3, "_capture_live_reconciliation", blocking_capture)
    with ThreadPoolExecutor(max_workers=2) as executor:
        restore_future = executor.submit(execute_restore)
        assert capture_completed.wait(10)
        mutation_future = executor.submit(execute_racing_user_creation)
        assert mutation_started.wait(2)
        threading.Event().wait(0.2)
        assert not mutation_future.done()
        release_capture.set()
        restored = restore_future.result(timeout=30)
        raced_user_created = mutation_future.result(timeout=30)
    monkeypatch.setattr(service.p1_3, "_capture_live_reconciliation", original_capture)
    assert restored.status_code == 200, restored.text
    assert isinstance(raced_user_created, ControlPlaneError)
    assert raced_user_created.status_code == 409
    assert raced_user_created.code == "INVALID_STATE_TRANSITION"
    result = restored.json()
    assert result["kind"] == "RESTORE_COMPLETED"
    assert result["recovery_source_mode"] == "ONLINE_ACTIVE_STORE"
    assert result["retained_previous_store"] is True
    assert len(result["reconciled_security_hash"]) == 64
    assert database_path.is_file()

    invalidated = admin_a.get("/api/v1/control-plane/auth/session")
    assert invalidated.status_code == 401
    relogged, _ = login(app, "admin-a")
    screen_after = relogged.get("/api/v1/control-plane/screen-instances/screen-trust-fixture")
    assert screen_after.status_code == 200, screen_after.text
    assert screen_after.json()["display_name"] == screen_before["display_name"]
    restored_bindings = {
        screen_id: relogged.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding").json()
        for screen_id in group["member_screen_ids"]
    }
    assert restored_bindings == backup_bindings
    users_after = relogged.get("/api/v1/control-plane/users")
    assert users_after.status_code == 200, users_after.text
    user_ids_after = {user["user_id"] for user in users_after.json()["items"]}
    assert post_backup_user_id in user_ids_after
    assert "restore-race-user" not in {user["normalized_username"] for user in users_after.json()["items"]}
    active_device_after = device.get(
        "/api/v1/device/runtime-binding",
        headers={"Authorization": f"DeviceCredential {active_device_credential}"},
    )
    assert active_device_after.status_code == 200, active_device_after.text
    assert active_device_after.json()["screen_id"] == active_screen_id
    pending_claim_after = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "restore-pending-token-claim"},
        json={"enrollment_token": pending_token},
    )
    assert pending_claim_after.status_code == 409
    exact_secrets = (
        active_issued.json()["enrollment_token"],
        active_device_credential,
        pending_token,
        *PASSWORDS.values(),
    )
    database_bytes = database_path.read_bytes()
    safe_bundle_bytes = b"".join(
        (bundle_dir / name).read_bytes()
        for name in (
            "manifest.json",
            "checksums.sha256",
            "verification.json",
            "payload.aes256gcm",
        )
    )
    for secret_value in exact_secrets:
        assert secret_value.encode() not in database_bytes
        assert secret_value.encode() not in safe_bundle_bytes
    plaintext_safe_bundle_text = (
        (bundle_dir / "manifest.json").read_text(encoding="utf-8")
        + (bundle_dir / "verification.json").read_text(encoding="utf-8")
    ).casefold()
    for forbidden_name in (
        '"password_verifier":',
        '"verifier_hmac":',
        '"response_ciphertext":',
        '"enrollment_token":',
        '"credential":',
    ):
        assert forbidden_name not in plaintext_safe_bundle_text
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        audit_text = canonical_json(
            [
                tuple(row)
                for row in connection.execute(
                    """
                    SELECT event_type, actor_id, target_type, target_id,
                        outcome, reason, details_json
                    FROM security_audit_events ORDER BY sequence
                    """
                ).fetchall()
            ]
        )
        for secret_value in exact_secrets:
            assert secret_value not in audit_text
        assert (
            connection.execute(
                """
            SELECT state FROM high_risk_actions
            WHERE high_risk_action_id = ?
            """,
                (unfinished_action["high_risk_action_id"],),
            ).fetchone()[0]
            == "FAILED"
        )
        replay_rows = connection.execute(
            """
            SELECT response_nonce, response_ciphertext,
                response_encryption_key_id, response_aad_json,
                response_aad_hash, response_expires_at
            FROM idempotency_records
            """
        ).fetchall()
        assert replay_rows
        assert all(all(value is None for value in row) for row in replay_rows)
        restore_row = connection.execute(
            """
            SELECT rp.state, re.retained_previous_store_name
            FROM restore_plans rp
            JOIN restore_executions re USING (restore_plan_id)
            WHERE rp.restore_plan_id = ?
            """,
            (plan["restore_plan_id"],),
        ).fetchone()
        assert restore_row[0] == "EXECUTED"
        assert (service.p1_3.backups.backup_root / restore_row[1]).is_file()


def test_p1_3_three_day_runtime_detail_retention_preserves_control_plane(
    control_plane: tuple[FastAPI, ControlPlaneService, Path],
    tmp_path: Path,
) -> None:
    app, service, database_path = control_plane
    implementation, csrf_impl = login(app, "implementation")
    admin_a, csrf_a = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    release = create_p1_3_release(
        implementation,
        csrf_impl,
        admin_a,
        csrf_a,
        target_type="SCREEN",
        target_id="screen-trust-fixture",
        expected_target_count=1,
        welcome_text="保留策略验证",
        suffix="retention",
    )
    binding = implementation.get(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/runtime-binding"
    ).json()
    publish_payload = {
        "release_id": release["release_id"],
        "release_target_id": release["targets"][0]["release_target_id"],
        "expected_binding_generation": binding["binding_generation"],
        "reason": "create protected publication evidence",
    }
    action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/publications",
        publish_payload,
        "retention-publish-request",
        extra_headers={"If-Match": binding["etag"]},
    )
    approve_action(admin_b, csrf_b, action, key="retention-publish-approve")
    published = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/publications",
        headers=mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": "retention-publish-execute",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=publish_payload,
    )
    assert published.status_code == 201, published.text
    enrollment_payload = {"reason": "create protected device-security evidence"}
    enrollment_action = request_action(
        implementation,
        csrf_impl,
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        enrollment_payload,
        "retention-enroll-request",
    )
    approve_action(admin_b, csrf_b, enrollment_action, key="retention-enroll-approve")
    enrollment = implementation.post(
        "/api/v1/control-plane/screen-instances/screen-trust-fixture/device-enrollments",
        headers=mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": "retention-enroll-execute",
                "High-Risk-Action-ID": enrollment_action["high_risk_action_id"],
            },
        ),
        json=enrollment_payload,
    )
    assert enrollment.status_code == 201, enrollment.text
    device = TestClient(app, base_url="https://device.test")
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": "retention-device-claim"},
        json={"enrollment_token": enrollment.json()["enrollment_token"]},
    )
    assert claimed.status_code == 200, claimed.text

    session_path = tmp_path / "runtime-detail.db"
    session_store = SessionLogStore(session_path, retention_days=3)
    session_store.initialize()
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    with sqlite3.connect(session_path) as connection:
        connection.executemany(
            """
            INSERT INTO session_logs(
                session_id, message_id, created_at, user_text, intent_type,
                dora_response_json, screen_action_json, error_json,
                latency_total_ms
            ) VALUES (?, ?, ?, ?, 'chat', '{}', NULL, NULL, 1)
            """,
            [
                (
                    "expired-session",
                    "expired-message",
                    (now - timedelta(days=4)).isoformat(timespec="seconds"),
                    "expired runtime detail",
                ),
                (
                    "retained-session",
                    "retained-message",
                    (now - timedelta(days=2)).isoformat(timespec="seconds"),
                    "retained runtime detail",
                ),
            ],
        )
        connection.commit()
    protected_tables = (
        "users",
        "device_credential_families",
        "config_releases",
        "publications",
        "security_audit_events",
    )
    with sqlite3.connect(database_path) as connection:
        before = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in protected_tables
        }
    assert all(before[table] > 0 for table in protected_tables)

    cleanup = session_store.cleanup_expired(now=now)
    assert cleanup["retention_days"] == 3
    assert cleanup["deleted_runtime_detail_count"] == 1
    recorded = service.p1_3.record_runtime_detail_retention(
        retention_days=cleanup["retention_days"],
        deleted_runtime_detail_count=cleanup["deleted_runtime_detail_count"],
    )
    assert recorded["recorded"] is True
    with sqlite3.connect(session_path) as connection:
        remaining = connection.execute("SELECT session_id FROM session_logs ORDER BY session_id").fetchall()
        assert remaining == [("retained-session",)]
    with sqlite3.connect(database_path) as connection:
        after = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in protected_tables
        }
        assert connection.execute(
            """
            SELECT retention_days, deleted_runtime_detail_count,
                protected_control_plane_counts_hash
            FROM retention_runs WHERE retention_run_id = ?
            """,
            (recorded["retention_run_id"],),
        ).fetchone() == (
            3,
            1,
            recorded["protected_control_plane_counts_hash"],
        )
    assert after["security_audit_events"] == before["security_audit_events"] + 1
    for table in protected_tables[:-1]:
        assert after[table] == before[table]
