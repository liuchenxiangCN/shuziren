from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag

from app.control_plane.errors import ControlPlaneError
from app.control_plane.security import (
    Ciphertext,
    PasswordPolicy,
    PurposeKeyring,
    canonical_json,
    normalize_username,
    opaque_id,
    opaque_secret,
)
from app.control_plane.store import LOGICAL_SCHEMA_VERSION, ControlPlaneStore

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "platform_admin": (
        "user.manage",
        "role.assign",
        "deployment.manage",
        "screen.read",
        "screen.manage",
        "device.enroll",
        "device.revoke",
        "config.read",
        "config.edit_business",
        "config.edit_technical",
        "config.validate",
        "config.preview",
        "config.approve",
        "release.publish",
        "release.rollback",
        "secret.metadata.read",
        "secret.write",
        "finereport.binding.manage",
        "operation.read",
        "backup.create",
        "backup.restore",
        "risk.approve",
        "audit.read",
    ),
    "implementation_engineer": (
        "screen.read",
        "screen.manage",
        "device.enroll",
        "config.read",
        "config.edit_business",
        "config.edit_technical",
        "config.validate",
        "config.preview",
        "release.publish",
        "release.rollback",
        "secret.metadata.read",
        "operation.read",
    ),
    "business_operator": (
        "screen.read",
        "config.read",
        "config.edit_business",
        "config.validate",
        "config.preview",
        "operation.read",
    ),
    "operations_engineer": (
        "screen.read",
        "config.read",
        "operation.read",
        "backup.create",
        "audit.read",
    ),
    "auditor": (
        "screen.read",
        "config.read",
        "operation.read",
        "audit.read",
    ),
}

OPERATION_PERMISSION = {
    "createUser": "user.manage",
    "issueDeviceEnrollment": "device.enroll",
    "revokeDeviceCredential": "device.revoke",
}

IDEMPOTENCY_OPERATION_ROUTES = {
    "reauthenticateAuthSession": (
        "reauthenticateAuthSession",
        "/api/v1/control-plane/auth/session:reauthenticate",
    ),
    "approveHighRiskAction": (
        "approveHighRiskAction",
        "/api/v1/control-plane/high-risk-actions/{high_risk_action_id}:approve",
    ),
    "rejectHighRiskAction": (
        "rejectHighRiskAction",
        "/api/v1/control-plane/high-risk-actions/{high_risk_action_id}:reject",
    ),
    "request:createUser": ("createUser", "/api/v1/control-plane/users"),
    "request:issueDeviceEnrollment": (
        "issueDeviceEnrollment",
        "/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
    ),
    "execute:issueDeviceEnrollment": (
        "issueDeviceEnrollment",
        "/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
    ),
    "request:revokeDeviceCredential": (
        "revokeDeviceCredential",
        "/api/v1/control-plane/screen-instances/{screen_id}/device-credentials/{credential_id}:revoke",
    ),
    "claimDeviceEnrollment": (
        "claimDeviceEnrollment",
        "/api/v1/device/enrollments:claim",
    ),
    "rotateDeviceCredential": (
        "rotateDeviceCredential",
        "/api/v1/device/credentials:rotate",
    ),
}

ONE_TIME_AAD_REQUIRED_FIELDS = {
    "execute:issueDeviceEnrollment": (
        "device_enrollment_id",
        "screen_id",
        "installation_channel_id",
    ),
    "claimDeviceEnrollment": (
        "device_enrollment_id",
        "device_credential_family_id",
        "device_credential_id",
        "claiming_device_channel_id",
    ),
    "rotateDeviceCredential": (
        "device_credential_family_id",
        "predecessor_credential_id",
        "successor_credential_id",
        "rotating_device_channel_id",
    ),
}

SENSITIVE_DETAIL_KEYS = (
    "password",
    "secret",
    "token",
    "cookie",
    "csrf",
    "verifier",
    "credential_value",
    "authorization",
)


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    tenant_id: str
    deployment_id: str
    permissions: frozenset[str]
    roles: tuple[str, ...]
    authentication_epoch: int
    authorization_epoch: int


@dataclass(frozen=True)
class SessionContext:
    principal: Principal
    auth_session_id: str
    revision: int
    recent_reauthentication_at: float | None


@dataclass(frozen=True)
class SessionIssue:
    cookie_value: str
    csrf_token: str
    response: dict[str, Any]


@dataclass(frozen=True)
class ReauthenticationResult:
    cookie_value: str | None
    csrf_token: str | None
    response: dict[str, Any]
    replayed: bool


@dataclass(frozen=True)
class DeviceContext:
    credential_id: str
    credential_version: int
    family_id: str
    family_revision: int
    credential_epoch: int
    tenant_id: str
    deployment_id: str
    screen_id: str


class ControlPlaneService:
    def __init__(
        self,
        database_path: str,
        root_key_b64: str,
        *,
        preview_mode: bool,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = ControlPlaneStore(database_path)
        self.keys = PurposeKeyring.from_base64(root_key_b64)
        self.passwords = PasswordPolicy()
        self._dummy_password_verifier = self.passwords.hash(opaque_secret())
        self.preview_mode = preview_mode
        self.clock = clock
        self.store.initialize(self.clock())

    def status(self) -> dict[str, Any]:
        with self.store.connect() as connection:
            metadata = connection.execute(
                "SELECT * FROM control_plane_metadata WHERE singleton = 1"
            ).fetchone()
            migration = connection.execute(
                """
                SELECT version, checksum_sha256, applied_at
                FROM schema_migrations ORDER BY applied_at DESC LIMIT 1
                """
            ).fetchone()
        return {
            "available": True,
            "initialized": metadata is not None,
            "profile": metadata["profile"] if metadata else "UNINITIALIZED",
            "logical_schema_version": LOGICAL_SCHEMA_VERSION,
            "migration_version": migration["version"] if migration else None,
            "migration_checksum_sha256": migration["checksum_sha256"] if migration else None,
            "production_ready": False,
            "production_readiness_reason": "P1.1 development preview is not production activation evidence",
        }

    def initialize_preview(
        self,
        *,
        tenant_id: str,
        deployment_id: str,
        screen_id: str,
        identities: list[dict[str, str]],
    ) -> dict[str, Any]:
        if not self.preview_mode:
            raise ControlPlaneError(
                403,
                "FORBIDDEN",
                "Development preview initialization is disabled",
            )
        expected_roles = (
            "platform_admin",
            "platform_admin",
            "implementation_engineer",
            "auditor",
        )
        if tuple(identity["role_id"] for identity in identities) != expected_roles:
            raise ValueError(
                "Preview initializer requires two admins, one implementation user and one auditor"
            )
        now = self.clock()
        with self.store.transaction() as connection:
            existing = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            if existing:
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Preview is already initialized")
            connection.execute(
                """
                INSERT INTO control_plane_metadata(
                    singleton, profile, tenant_id, deployment_id, fixture_screen_id, created_at
                ) VALUES (1, 'DEVELOPMENT_PREVIEW', ?, ?, ?, ?)
                """,
                (tenant_id, deployment_id, screen_id, now),
            )
            created_users: list[dict[str, Any]] = []
            for identity in identities:
                user_id = opaque_id("usr")
                username = normalize_username(identity["username"])
                connection.execute(
                    """
                    INSERT INTO users(
                        user_id, tenant_id, deployment_id, normalized_username, display_name,
                        account_state, password_verifier, credential_generation, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        tenant_id,
                        deployment_id,
                        username,
                        identity["display_name"].strip(),
                        self.passwords.hash(identity["password"], username=username),
                        now,
                        now,
                    ),
                )
                role_id = identity["role_id"]
                connection.execute(
                    """
                    INSERT INTO role_assignments(
                        assignment_id, user_id, role_id, scope_type, scope_id, created_at
                    ) VALUES (?, ?, ?, 'DEPLOYMENT', ?, ?)
                    """,
                    (opaque_id("rla"), user_id, role_id, deployment_id, now),
                )
                created_users.append(
                    {"user_id": user_id, "normalized_username": username, "role_id": role_id}
                )
            self._append_audit(
                connection,
                event_type="PREVIEW_INITIALIZED",
                actor_type="LOCAL_SETUP",
                actor_id=None,
                target_type="DEPLOYMENT",
                target_id=deployment_id,
                outcome="SUCCESS",
                reason="explicit development-only initialization",
                details={"identity_count": len(created_users), "fixture_screen_id": screen_id},
                now=now,
            )
        return {
            "profile": "DEVELOPMENT_PREVIEW",
            "tenant_id": tenant_id,
            "deployment_id": deployment_id,
            "fixture_screen_id": screen_id,
            "users": created_users,
        }

    def login(self, username: str, password: str) -> SessionIssue:
        try:
            normalized_username = normalize_username(username)
        except ValueError:
            normalized_username = ""
        now = self.clock()
        failure: ControlPlaneError | None = None
        issue: SessionIssue | None = None
        with self.store.transaction() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE normalized_username = ?",
                (normalized_username,),
            ).fetchone()
            verifier = (
                user["password_verifier"]
                if user is not None and user["password_verifier"]
                else self._dummy_password_verifier
            )
            password_matches = self.passwords.verify(verifier, password)
            if user is None:
                self._append_audit(
                    connection,
                    event_type="AUTHENTICATION",
                    actor_type="USER",
                    actor_id=None,
                    target_type="USER",
                    target_id=None,
                    outcome="DENIED",
                    reason="invalid credentials",
                    details={
                        "normalized_username_hash": hashlib.sha256(normalized_username.encode()).hexdigest()
                    },
                    now=now,
                )
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Invalid username or password",
                )
            elif user["locked_until"] and user["locked_until"] > now:
                self._append_audit(
                    connection,
                    event_type="AUTHENTICATION",
                    actor_type="USER",
                    actor_id=user["user_id"],
                    target_type="USER",
                    target_id=user["user_id"],
                    outcome="DENIED",
                    reason="account temporarily locked",
                    details={},
                    now=now,
                )
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Invalid username or password",
                )
            elif user["account_state"] != "ACTIVE" or not user["password_verifier"]:
                self._append_audit(
                    connection,
                    event_type="AUTHENTICATION",
                    actor_type="USER",
                    actor_id=user["user_id"],
                    target_type="USER",
                    target_id=user["user_id"],
                    outcome="DENIED",
                    reason="invalid credentials",
                    details={},
                    now=now,
                )
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Invalid username or password",
                )
            elif not password_matches:
                self._record_login_failure(connection, user, now)
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Invalid username or password",
                )
            else:
                connection.execute(
                    """
                    UPDATE users SET failed_window_started_at = NULL, failed_attempts = 0,
                        locked_until = NULL, last_login_at = ?, updated_at = ?, revision = revision + 1
                    WHERE user_id = ?
                    """,
                    (now, now, user["user_id"]),
                )
                issue = self._issue_session(connection, user["user_id"], now)
                self._append_audit(
                    connection,
                    event_type="AUTHENTICATION",
                    actor_type="USER",
                    actor_id=user["user_id"],
                    target_type="AUTH_SESSION",
                    target_id=issue.response["auth_session_id"],
                    outcome="SUCCESS",
                    reason=None,
                    details={},
                    now=now,
                )
        if failure is not None:
            raise failure
        if issue is None:
            raise RuntimeError("Authentication transaction produced no result")
        return issue

    def authenticate_session(self, cookie_value: str) -> SessionContext:
        now = self.clock()
        verifier = self.keys.digest("AUTH_SESSION_VERIFIER_PEPPER", cookie_value)
        failure: ControlPlaneError | None = None
        context: SessionContext | None = None
        with self.store.transaction() as connection:
            session = connection.execute(
                "SELECT * FROM auth_sessions WHERE verifier_hmac = ?",
                (verifier,),
            ).fetchone()
            if session is None or session["state"] != "ACTIVE":
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Authentication is required",
                )
            elif session["absolute_expires_at"] <= now:
                connection.execute(
                    """
                    UPDATE auth_sessions SET state = 'ABSOLUTE_EXPIRED', revision = revision + 1
                    WHERE auth_session_id = ?
                    """,
                    (session["auth_session_id"],),
                )
                failure = ControlPlaneError(401, "AUTHENTICATION_REQUIRED", "Session expired")
            elif session["idle_expires_at"] <= now:
                connection.execute(
                    """
                    UPDATE auth_sessions SET state = 'IDLE_EXPIRED', revision = revision + 1
                    WHERE auth_session_id = ?
                    """,
                    (session["auth_session_id"],),
                )
                failure = ControlPlaneError(401, "AUTHENTICATION_REQUIRED", "Session expired")
            else:
                user = connection.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (session["user_id"],),
                ).fetchone()
                if (
                    user is None
                    or user["account_state"] != "ACTIVE"
                    or user["authentication_epoch"] != session["authentication_epoch"]
                    or user["authorization_epoch"] != session["authorization_epoch"]
                ):
                    connection.execute(
                        """
                        UPDATE auth_sessions SET state = 'REVOKED', revoked_at = ?,
                            revision = revision + 1 WHERE auth_session_id = ?
                        """,
                        (now, session["auth_session_id"]),
                    )
                    failure = ControlPlaneError(
                        401,
                        "AUTHENTICATION_REQUIRED",
                        "Session is no longer valid",
                    )
                else:
                    connection.execute(
                        """
                        UPDATE auth_sessions SET last_seen_at = ?, idle_expires_at = ?
                        WHERE auth_session_id = ?
                        """,
                        (
                            now,
                            min(now + 30 * 60, session["absolute_expires_at"]),
                            session["auth_session_id"],
                        ),
                    )
                    principal = self._principal(connection, user)
                    context = SessionContext(
                        principal=principal,
                        auth_session_id=session["auth_session_id"],
                        revision=session["revision"],
                        recent_reauthentication_at=session["recent_reauthentication_at"],
                    )
        if failure is not None:
            raise failure
        if context is None:
            raise RuntimeError("Session authentication produced no result")
        return context

    def verify_csrf(self, session_id: str, csrf_token: str) -> None:
        with self.store.connect() as connection:
            session = connection.execute(
                "SELECT csrf_verifier_hmac, state FROM auth_sessions WHERE auth_session_id = ?",
                (session_id,),
            ).fetchone()
        if (
            session is None
            or session["state"] != "ACTIVE"
            or not self.keys.verify("CSRF_TOKEN_VERIFIER_PEPPER", csrf_token, session["csrf_verifier_hmac"])
        ):
            raise ControlPlaneError(403, "FORBIDDEN", "CSRF validation failed")

    def current_session(self, context: SessionContext) -> dict[str, Any]:
        return self._session_response(context)

    def refresh_csrf(self, context: SessionContext) -> tuple[str, dict[str, Any]]:
        token = opaque_secret()
        now = self.clock()
        with self.store.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE auth_sessions SET csrf_verifier_hmac = ?, csrf_verifier_key_id = ?,
                    revision = revision + 1 WHERE auth_session_id = ? AND state = 'ACTIVE'
                """,
                (
                    self.keys.digest("CSRF_TOKEN_VERIFIER_PEPPER", token),
                    self.keys.key_id("CSRF_TOKEN_VERIFIER_PEPPER"),
                    context.auth_session_id,
                ),
            )
            if updated.rowcount != 1:
                raise ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Session is no longer valid",
                )
        refreshed_context = SessionContext(
            principal=context.principal,
            auth_session_id=context.auth_session_id,
            revision=context.revision + 1,
            recent_reauthentication_at=context.recent_reauthentication_at,
        )
        return token, {**self._session_response(refreshed_context), "refreshed_at": now}

    def reauthenticate(
        self,
        context: SessionContext,
        password: str,
        if_match: str,
        idempotency_key: str,
    ) -> ReauthenticationResult:
        request_digest = self._sensitive_request_digest(
            "reauthenticateAuthSession",
            {
                "user_id": context.principal.user_id,
                "password": password,
                "if_match": if_match,
            },
        )
        now = self.clock()
        result: ReauthenticationResult | None = None
        failure: ControlPlaneError | None = None
        with self.store.transaction() as connection:
            replay = self._idempotency_lookup(
                connection,
                phase="reauthenticateAuthSession",
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                replay_result = json.loads(replay["result_json"])
                if replay_result["successor_session_id"] != context.auth_session_id:
                    failure = ControlPlaneError(
                        409,
                        "IDEMPOTENCY_KEY_REUSED",
                        "Reauthentication result belongs to a different session",
                    )
                else:
                    result = ReauthenticationResult(
                        cookie_value=None,
                        csrf_token=None,
                        response=self._session_response(context),
                        replayed=True,
                    )
            session = connection.execute(
                """
                SELECT state, revision FROM auth_sessions
                WHERE auth_session_id = ?
                """,
                (context.auth_session_id,),
            ).fetchone()
            user = connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (context.principal.user_id,)
            ).fetchone()
            if result is not None and (
                session is None
                or session["state"] != "ACTIVE"
                or user is None
                or user["account_state"] != "ACTIVE"
                or user["authentication_epoch"] != context.principal.authentication_epoch
                or user["authorization_epoch"] != context.principal.authorization_epoch
            ):
                result = None
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Session is no longer valid",
                )
            elif result is not None and session["revision"] != context.revision:
                result = None
                failure = ControlPlaneError(
                    409,
                    "RESOURCE_VERSION_CONFLICT",
                    "Session changed",
                )
            if result is not None or failure is not None:
                pass
            elif session is None or session["state"] != "ACTIVE":
                self._append_audit(
                    connection,
                    event_type="SESSION_REAUTHENTICATION",
                    actor_type="USER",
                    actor_id=context.principal.user_id,
                    target_type="AUTH_SESSION",
                    target_id=context.auth_session_id,
                    outcome="DENIED",
                    reason="session no longer active",
                    details={},
                    now=now,
                )
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Session is no longer valid",
                )
            elif (
                user is None
                or user["account_state"] != "ACTIVE"
                or user["authentication_epoch"] != context.principal.authentication_epoch
                or user["authorization_epoch"] != context.principal.authorization_epoch
            ):
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Session is no longer valid",
                )
            elif session["revision"] != context.revision:
                failure = ControlPlaneError(
                    409,
                    "RESOURCE_VERSION_CONFLICT",
                    "Session changed",
                )
            else:
                try:
                    self._require_etag(if_match, "session", context.revision)
                except ControlPlaneError as exc:
                    failure = exc
            if (
                result is None
                and failure is None
                and (
                    user is None
                    or user["account_state"] != "ACTIVE"
                    or not user["password_verifier"]
                    or not self.passwords.verify(user["password_verifier"], password)
                )
            ):
                self._append_audit(
                    connection,
                    event_type="SESSION_REAUTHENTICATION",
                    actor_type="USER",
                    actor_id=context.principal.user_id,
                    target_type="AUTH_SESSION",
                    target_id=context.auth_session_id,
                    outcome="DENIED",
                    reason="invalid credentials",
                    details={},
                    now=now,
                )
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Password confirmation failed",
                )
            if result is None and failure is None:
                updated = connection.execute(
                    """
                    UPDATE auth_sessions SET state = 'REVOKED', revoked_at = ?,
                        revision = revision + 1
                    WHERE auth_session_id = ? AND state = 'ACTIVE' AND revision = ?
                    """,
                    (now, context.auth_session_id, context.revision),
                )
                if updated.rowcount != 1:
                    failure = ControlPlaneError(
                        401,
                        "AUTHENTICATION_REQUIRED",
                        "Session is no longer valid",
                    )
            if result is None and failure is None:
                issue = self._issue_session(connection, user["user_id"], now)
                self._idempotency_store(
                    connection,
                    phase="reauthenticateAuthSession",
                    principal_key=context.principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result={
                        "predecessor_session_id": context.auth_session_id,
                        "successor_session_id": issue.response["auth_session_id"],
                    },
                    now=now,
                )
                result = ReauthenticationResult(
                    cookie_value=issue.cookie_value,
                    csrf_token=issue.csrf_token,
                    response=issue.response,
                    replayed=False,
                )
                self._append_audit(
                    connection,
                    event_type="SESSION_REAUTHENTICATED",
                    actor_type="USER",
                    actor_id=user["user_id"],
                    target_type="AUTH_SESSION",
                    target_id=issue.response["auth_session_id"],
                    outcome="SUCCESS",
                    reason=None,
                    details={"predecessor_session_id": context.auth_session_id},
                    now=now,
                )
        if failure is not None:
            raise failure
        if result is None:
            raise RuntimeError("Reauthentication transaction produced no result")
        return result

    def logout(self, context: SessionContext) -> None:
        now = self.clock()
        with self.store.transaction() as connection:
            connection.execute(
                """
                UPDATE auth_sessions SET state = 'REVOKED', revoked_at = ?, revision = revision + 1
                WHERE auth_session_id = ? AND state = 'ACTIVE'
                """,
                (now, context.auth_session_id),
            )
            self._append_audit(
                connection,
                event_type="SESSION_REVOKED",
                actor_type="USER",
                actor_id=context.principal.user_id,
                target_type="AUTH_SESSION",
                target_id=context.auth_session_id,
                outcome="SUCCESS",
                reason="self logout",
                details={},
                now=now,
            )

    def list_users(self, principal: Principal) -> list[dict[str, Any]]:
        self.require_permission(principal, "user.manage")
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM users WHERE tenant_id = ? AND deployment_id = ?
                ORDER BY normalized_username
                """,
                (principal.tenant_id, principal.deployment_id),
            ).fetchall()
            return [self._user_response(connection, row) for row in rows]

    def role_definitions(self, principal: Principal) -> list[dict[str, Any]]:
        self.require_permission(principal, "role.assign")
        return [
            {"role_id": role_id, "permissions": list(permissions), "catalog_version": "p1_roles_v1"}
            for role_id, permissions in ROLE_PERMISSIONS.items()
        ]

    def request_or_execute_user_creation(
        self,
        context: SessionContext,
        *,
        normalized_username: str,
        display_name: str,
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        try:
            username = normalize_username(normalized_username)
        except ValueError as exc:
            raise ControlPlaneError(422, "VALIDATION_ERROR", str(exc)) from exc
        command = {
            "normalized_username": username,
            "display_name": display_name.strip(),
        }
        if not command["display_name"] or len(command["display_name"]) > 128:
            raise ControlPlaneError(422, "VALIDATION_ERROR", "Display name must contain 1 to 128 characters")
        return self._request_or_execute_protected(
            context,
            operation_id="createUser",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def request_or_execute_enrollment(
        self,
        context: SessionContext,
        *,
        screen_id: str,
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        command = self._device_enrollment_command(
            context.principal,
            screen_id=screen_id,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )
        return self._request_or_execute_protected(
            context,
            operation_id="issueDeviceEnrollment",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def request_or_execute_device_revoke(
        self,
        context: SessionContext,
        *,
        screen_id: str,
        credential_id: str,
        expected_credential_epoch: int,
        if_match: str,
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        return self._request_or_execute_protected(
            context,
            operation_id="revokeDeviceCredential",
            command={
                "screen_id": screen_id,
                "credential_id": credential_id,
                "expected_credential_epoch": expected_credential_epoch,
                "family_etag": if_match,
            },
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def approve_action(
        self,
        context: SessionContext,
        action_id: str,
        *,
        expected_request_digest: str,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.require_permission(context.principal, "risk.approve")
        self._require_recent_reauthentication(context)
        now = self.clock()
        self._expire_due_actions(now, action_id=action_id)
        request_digest = self._sensitive_request_digest(
            "approveHighRiskAction",
            {
                "decision": "APPROVE",
                "action_id": action_id,
                "expected_request_digest": expected_request_digest,
                "reason": reason,
                "if_match": if_match,
            },
        )
        with self.store.transaction() as connection:
            replay = self._idempotency_lookup(
                connection,
                phase="approveHighRiskAction",
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            action = self._load_action(connection, action_id, now)
            self.require_permission(context.principal, OPERATION_PERMISSION[action["operation_id"]])
            self._require_etag(if_match, "high-risk-action", action["revision"])
            if action["state"] != "PENDING":
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Action is not pending")
            if action["initiator_user_id"] == context.principal.user_id:
                raise ControlPlaneError(403, "FORBIDDEN", "A high-risk action requires a different approver")
            if not secrets.compare_digest(action["request_digest"], expected_request_digest):
                raise ControlPlaneError(
                    409, "HIGH_RISK_ACTION_MISMATCH", "Expected request digest does not match"
                )
            connection.execute(
                """
                UPDATE high_risk_actions SET state = 'APPROVED', approver_user_id = ?,
                    approver_authentication_epoch = ?, approver_authorization_epoch = ?,
                    approved_at = ?, revision = revision + 1
                WHERE high_risk_action_id = ?
                """,
                (
                    context.principal.user_id,
                    context.principal.authentication_epoch,
                    context.principal.authorization_epoch,
                    now,
                    action_id,
                ),
            )
            self._append_audit(
                connection,
                event_type="HIGH_RISK_ACTION_APPROVED",
                actor_type="USER",
                actor_id=context.principal.user_id,
                target_type="HIGH_RISK_ACTION",
                target_id=action_id,
                outcome="APPROVED",
                reason=reason,
                details={"operation_id": action["operation_id"], "request_digest": action["request_digest"]},
                now=now,
            )
            updated = connection.execute(
                "SELECT * FROM high_risk_actions WHERE high_risk_action_id = ?",
                (action_id,),
            ).fetchone()
            result = self._action_response(updated)
            self._idempotency_store(
                connection,
                phase="approveHighRiskAction",
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def reject_action(
        self,
        context: SessionContext,
        action_id: str,
        *,
        expected_request_digest: str,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.require_permission(context.principal, "risk.approve")
        self._require_recent_reauthentication(context)
        now = self.clock()
        self._expire_due_actions(now, action_id=action_id)
        request_digest = self._sensitive_request_digest(
            "rejectHighRiskAction",
            {
                "decision": "REJECT",
                "action_id": action_id,
                "expected_request_digest": expected_request_digest,
                "reason": reason,
                "if_match": if_match,
            },
        )
        with self.store.transaction() as connection:
            replay = self._idempotency_lookup(
                connection,
                phase="rejectHighRiskAction",
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            action = self._load_action(connection, action_id, now)
            self.require_permission(context.principal, OPERATION_PERMISSION[action["operation_id"]])
            self._require_etag(if_match, "high-risk-action", action["revision"])
            if action["state"] != "PENDING":
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Action is not pending")
            if action["initiator_user_id"] == context.principal.user_id:
                raise ControlPlaneError(403, "FORBIDDEN", "A high-risk action requires a different reviewer")
            if not secrets.compare_digest(action["request_digest"], expected_request_digest):
                raise ControlPlaneError(
                    409, "HIGH_RISK_ACTION_MISMATCH", "Expected request digest does not match"
                )
            connection.execute(
                """
                UPDATE high_risk_actions SET state = 'REJECTED', approver_user_id = ?,
                    approved_at = ?, revision = revision + 1 WHERE high_risk_action_id = ?
                """,
                (context.principal.user_id, now, action_id),
            )
            self._append_audit(
                connection,
                event_type="HIGH_RISK_ACTION_REJECTED",
                actor_type="USER",
                actor_id=context.principal.user_id,
                target_type="HIGH_RISK_ACTION",
                target_id=action_id,
                outcome="REJECTED",
                reason=reason,
                details={"operation_id": action["operation_id"]},
                now=now,
            )
            updated = connection.execute(
                "SELECT * FROM high_risk_actions WHERE high_risk_action_id = ?",
                (action_id,),
            ).fetchone()
            result = self._action_response(updated)
            self._idempotency_store(
                connection,
                phase="rejectHighRiskAction",
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def get_action(self, principal: Principal, action_id: str) -> dict[str, Any]:
        self._expire_due_actions(self.clock(), action_id=action_id)
        with self.store.connect() as connection:
            action = connection.execute(
                "SELECT * FROM high_risk_actions WHERE high_risk_action_id = ?",
                (action_id,),
            ).fetchone()
        if action is None:
            raise ControlPlaneError(404, "NOT_FOUND", "High-risk action was not found")
        if action["initiator_user_id"] != principal.user_id:
            self.require_permission(principal, "risk.approve")
            self.require_permission(principal, OPERATION_PERMISSION[action["operation_id"]])
        return self._action_response(action)

    def list_pending_actions(self, principal: Principal) -> list[dict[str, Any]]:
        self.require_permission(principal, "risk.approve")
        self._expire_due_actions(self.clock())
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM high_risk_actions WHERE state = 'PENDING' ORDER BY requested_at"
            ).fetchall()
        return [
            self._action_response(row)
            for row in rows
            if OPERATION_PERMISSION[row["operation_id"]] in principal.permissions
        ]

    def get_enrollment(self, principal: Principal, enrollment_id: str) -> dict[str, Any]:
        self.require_permission(principal, "screen.read")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM device_enrollments WHERE enrollment_id = ?",
                (enrollment_id,),
            ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "NOT_FOUND", "Enrollment was not found")
        return self._enrollment_response(row)

    def claim_enrollment(self, enrollment_token: str, idempotency_key: str) -> dict[str, Any]:
        enrollment_id, token_secret = self._parse_bound_secret(enrollment_token, "enrollment")
        principal_key = enrollment_id
        request_digest = self._sensitive_request_digest(
            "claimDeviceEnrollment",
            {"enrollment_token": enrollment_token},
        )
        replay = self._load_one_time_replay(
            "claimDeviceEnrollment", principal_key, idempotency_key, request_digest
        )
        if replay is not None:
            return replay
        now = self.clock()
        self._expire_enrollment_if_needed(enrollment_id, now)
        with self.store.transaction() as connection:
            enrollment = connection.execute(
                "SELECT * FROM device_enrollments WHERE enrollment_id = ?",
                (enrollment_id,),
            ).fetchone()
            if enrollment is None or not self.keys.verify(
                "ONE_TIME_TOKEN_VERIFIER_PEPPER",
                token_secret,
                enrollment["token_verifier_hmac"],
            ):
                raise ControlPlaneError(401, "AUTHENTICATION_REQUIRED", "Enrollment token is invalid")
            if enrollment["state"] != "ISSUED" or enrollment["expires_at"] <= now:
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Enrollment is no longer claimable")
            family = self._current_screen_family(
                connection,
                enrollment["tenant_id"],
                enrollment["deployment_id"],
                enrollment["screen_id"],
            )
            if family is not None and family["state"] == "ACTIVE":
                raise ControlPlaneError(
                    409,
                    "ACTIVE_DEVICE_FAMILY_EXISTS",
                    "An active device family already exists",
                )
            if not self._family_precondition_matches(
                family,
                state=enrollment["family_precondition_state"],
                family_id=enrollment["family_precondition_id"],
                revision=enrollment["family_precondition_revision"],
            ):
                raise ControlPlaneError(
                    409,
                    "RESOURCE_VERSION_CONFLICT",
                    "Device family changed after enrollment issuance",
                )
            family_id = opaque_id("dcf")
            credential_id = opaque_id("dvc")
            credential_secret = opaque_secret()
            credential_value = f"{credential_id}.{credential_secret}"
            credential_version = 1
            family_revision = 1
            credential_epoch = 1
            connection.execute(
                """
                INSERT INTO device_credential_families(
                    family_id, tenant_id, deployment_id, screen_id, state, credential_epoch,
                    active_credential_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'ACTIVE', 1, ?, ?, ?)
                """,
                (
                    family_id,
                    enrollment["tenant_id"],
                    enrollment["deployment_id"],
                    enrollment["screen_id"],
                    credential_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO device_credentials(
                    credential_id, family_id, credential_version, verifier_hmac, verifier_key_id,
                    state, issued_at, activated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (
                    credential_id,
                    family_id,
                    credential_version,
                    self.keys.digest("DEVICE_CREDENTIAL_VERIFIER_PEPPER", credential_secret),
                    self.keys.key_id("DEVICE_CREDENTIAL_VERIFIER_PEPPER"),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE device_enrollments SET state = 'CLAIMED', claimed_at = ?,
                    revision = revision + 1 WHERE enrollment_id = ?
                """,
                (now, enrollment_id),
            )
            result = {
                "credential": credential_value,
                "credential_id": credential_id,
                "credential_version": credential_version,
                "screen_id": enrollment["screen_id"],
                "family_etag": self._etag("device-family", family_revision),
                "credential_epoch": credential_epoch,
            }
            self._store_one_time_replay(
                connection,
                phase="claimDeviceEnrollment",
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                aad_context={
                    "device_enrollment_id": enrollment_id,
                    "device_credential_family_id": family_id,
                    "device_credential_id": credential_id,
                    "claiming_device_channel_id": principal_key,
                },
                now=now,
            )
            self._append_audit(
                connection,
                event_type="DEVICE_ENROLLMENT_CLAIMED",
                actor_type="DEVICE",
                actor_id=credential_id,
                target_type="SCREEN",
                target_id=enrollment["screen_id"],
                outcome="SUCCESS",
                reason=None,
                details={"enrollment_id": enrollment_id, "credential_version": credential_version},
                now=now,
            )
            return result

    def authenticate_device(self, authorization: str) -> DeviceContext:
        credential_id, secret_value = self._parse_device_authorization(authorization)
        now = self.clock()
        failure: ControlPlaneError | None = None
        context: DeviceContext | None = None
        with self.store.transaction() as connection:
            credential = connection.execute(
                """
                SELECT c.*, f.tenant_id, f.deployment_id, f.screen_id, f.state AS family_state,
                    f.credential_epoch, f.active_credential_id, f.pending_credential_id,
                    f.revision AS family_revision
                FROM device_credentials c
                JOIN device_credential_families f ON f.family_id = c.family_id
                WHERE c.credential_id = ?
                """,
                (credential_id,),
            ).fetchone()
            if (
                credential is None
                or not self.keys.verify(
                    "DEVICE_CREDENTIAL_VERIFIER_PEPPER",
                    secret_value,
                    credential["verifier_hmac"],
                )
                or credential["family_state"] != "ACTIVE"
            ):
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Device credential is invalid",
                )
            elif credential["state"] == "PENDING_ACTIVATION":
                if credential["activation_expires_at"] is None or credential["activation_expires_at"] <= now:
                    connection.execute(
                        """
                        UPDATE device_credentials SET state = 'EXPIRED', revision = revision + 1
                        WHERE credential_id = ?
                        """,
                        (credential_id,),
                    )
                    connection.execute(
                        """
                        UPDATE device_credential_families SET pending_credential_id = NULL,
                            updated_at = ?, revision = revision + 1 WHERE family_id = ?
                        """,
                        (now, credential["family_id"]),
                    )
                    self._append_audit(
                        connection,
                        event_type="DEVICE_CREDENTIAL_SUCCESSOR_EXPIRED",
                        actor_type="DEVICE",
                        actor_id=credential_id,
                        target_type="SCREEN",
                        target_id=credential["screen_id"],
                        outcome="DENIED",
                        reason="activation window expired",
                        details={"credential_version": credential["credential_version"]},
                        now=now,
                    )
                    failure = ControlPlaneError(
                        401,
                        "AUTHENTICATION_REQUIRED",
                        "Device credential is invalid",
                    )
                else:
                    predecessor = credential["active_credential_id"]
                    connection.execute(
                        """
                        UPDATE device_credentials SET state = 'REVOKED', revoked_at = ?,
                            revision = revision + 1 WHERE credential_id = ? AND state = 'ACTIVE'
                        """,
                        (now, predecessor),
                    )
                    connection.execute(
                        """
                        UPDATE device_credentials SET state = 'ACTIVE', activated_at = ?,
                            last_authenticated_at = ?, revision = revision + 1
                        WHERE credential_id = ?
                        """,
                        (now, now, credential_id),
                    )
                    connection.execute(
                        """
                        UPDATE device_credential_families SET active_credential_id = ?,
                            pending_credential_id = NULL, updated_at = ?, revision = revision + 1
                        WHERE family_id = ?
                        """,
                        (credential_id, now, credential["family_id"]),
                    )
                    self._append_audit(
                        connection,
                        event_type="DEVICE_CREDENTIAL_SUCCESSOR_ACTIVATED",
                        actor_type="DEVICE",
                        actor_id=credential_id,
                        target_type="SCREEN",
                        target_id=credential["screen_id"],
                        outcome="SUCCESS",
                        reason=None,
                        details={"credential_version": credential["credential_version"]},
                        now=now,
                    )
                    family_revision = credential["family_revision"] + 1
            elif credential["state"] != "ACTIVE":
                failure = ControlPlaneError(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Device credential is invalid",
                )
            else:
                connection.execute(
                    """
                    UPDATE device_credentials SET last_authenticated_at = ?
                    WHERE credential_id = ?
                    """,
                    (now, credential_id),
                )
                family_revision = credential["family_revision"]
            if failure is None:
                context = DeviceContext(
                    credential_id=credential_id,
                    credential_version=credential["credential_version"],
                    family_id=credential["family_id"],
                    family_revision=family_revision,
                    credential_epoch=credential["credential_epoch"],
                    tenant_id=credential["tenant_id"],
                    deployment_id=credential["deployment_id"],
                    screen_id=credential["screen_id"],
                )
        if failure is not None:
            raise failure
        if context is None:
            raise RuntimeError("Device authentication transaction produced no result")
        return context

    def rotate_device(
        self,
        context: DeviceContext,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        principal_key = context.credential_id
        request_digest = self._sensitive_request_digest(
            "rotateDeviceCredential",
            {
                "credential_id": context.credential_id,
                "credential_epoch": context.credential_epoch,
            },
        )
        replay = self._load_one_time_replay(
            "rotateDeviceCredential", principal_key, idempotency_key, request_digest
        )
        if replay is not None:
            return replay
        now = self.clock()
        with self.store.transaction() as connection:
            family = connection.execute(
                "SELECT * FROM device_credential_families WHERE family_id = ?",
                (context.family_id,),
            ).fetchone()
            if (
                family is None
                or family["state"] != "ACTIVE"
                or family["active_credential_id"] != context.credential_id
                or family["credential_epoch"] != context.credential_epoch
                or family["revision"] != context.family_revision
            ):
                raise ControlPlaneError(409, "RESOURCE_VERSION_CONFLICT", "Device family changed")
            family_revision = family["revision"]
            if family["pending_credential_id"]:
                pending = connection.execute(
                    """
                    SELECT state, activation_expires_at, credential_version
                    FROM device_credentials WHERE credential_id = ? AND family_id = ?
                    """,
                    (family["pending_credential_id"], context.family_id),
                ).fetchone()
                if (
                    pending is None
                    or pending["state"] != "PENDING_ACTIVATION"
                    or pending["activation_expires_at"] is None
                    or pending["activation_expires_at"] > now
                ):
                    raise ControlPlaneError(
                        409,
                        "SUCCESSOR_ALREADY_PENDING",
                        "A successor is already pending",
                    )
                connection.execute(
                    """
                    UPDATE device_credentials SET state = 'EXPIRED', revision = revision + 1
                    WHERE credential_id = ? AND state = 'PENDING_ACTIVATION'
                    """,
                    (family["pending_credential_id"],),
                )
                cleared = connection.execute(
                    """
                    UPDATE device_credential_families SET pending_credential_id = NULL,
                        updated_at = ?, revision = revision + 1
                    WHERE family_id = ? AND pending_credential_id = ? AND revision = ?
                    """,
                    (
                        now,
                        context.family_id,
                        family["pending_credential_id"],
                        family_revision,
                    ),
                )
                if cleared.rowcount != 1:
                    raise ControlPlaneError(
                        409,
                        "RESOURCE_VERSION_CONFLICT",
                        "Device family changed",
                    )
                self._append_audit(
                    connection,
                    event_type="DEVICE_CREDENTIAL_SUCCESSOR_EXPIRED",
                    actor_type="SYSTEM",
                    actor_id=None,
                    target_type="SCREEN",
                    target_id=context.screen_id,
                    outcome="DENIED",
                    reason="activation window expired",
                    details={"credential_version": pending["credential_version"]},
                    now=now,
                )
                family_revision += 1
            current = connection.execute(
                """
                SELECT MAX(credential_version) AS credential_version
                FROM device_credentials WHERE family_id = ?
                """,
                (context.family_id,),
            ).fetchone()
            successor_id = opaque_id("dvc")
            successor_secret = opaque_secret()
            successor_value = f"{successor_id}.{successor_secret}"
            successor_version = current["credential_version"] + 1
            connection.execute(
                """
                INSERT INTO device_credentials(
                    credential_id, family_id, credential_version, verifier_hmac, verifier_key_id,
                    state, issued_at, activation_expires_at
                ) VALUES (?, ?, ?, ?, ?, 'PENDING_ACTIVATION', ?, ?)
                """,
                (
                    successor_id,
                    context.family_id,
                    successor_version,
                    self.keys.digest("DEVICE_CREDENTIAL_VERIFIER_PEPPER", successor_secret),
                    self.keys.key_id("DEVICE_CREDENTIAL_VERIFIER_PEPPER"),
                    now,
                    now + 10 * 60,
                ),
            )
            pending_update = connection.execute(
                """
                UPDATE device_credential_families SET pending_credential_id = ?, updated_at = ?,
                    revision = revision + 1 WHERE family_id = ? AND revision = ?
                """,
                (successor_id, now, context.family_id, family_revision),
            )
            if pending_update.rowcount != 1:
                raise ControlPlaneError(
                    409,
                    "RESOURCE_VERSION_CONFLICT",
                    "Device family changed",
                )
            result = {
                "credential": successor_value,
                "credential_id": successor_id,
                "credential_version": successor_version,
                "state": "PENDING_ACTIVATION",
                "activation_expires_at": now + 10 * 60,
                "screen_id": context.screen_id,
                "family_etag": self._etag("device-family", family_revision + 1),
                "credential_epoch": family["credential_epoch"],
            }
            self._store_one_time_replay(
                connection,
                phase="rotateDeviceCredential",
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                aad_context={
                    "device_credential_family_id": context.family_id,
                    "predecessor_credential_id": context.credential_id,
                    "successor_credential_id": successor_id,
                    "rotating_device_channel_id": principal_key,
                },
                now=now,
            )
            self._append_audit(
                connection,
                event_type="DEVICE_CREDENTIAL_ROTATION_REQUESTED",
                actor_type="DEVICE",
                actor_id=context.credential_id,
                target_type="SCREEN",
                target_id=context.screen_id,
                outcome="SUCCESS",
                reason=None,
                details={"successor_credential_id": successor_id, "credential_version": successor_version},
                now=now,
            )
            return result

    def device_trust_status(self, context: DeviceContext) -> dict[str, Any]:
        return {
            "screen_id": context.screen_id,
            "credential_id": context.credential_id,
            "credential_version": context.credential_version,
            "trust_state": "ACTIVE",
            "runtime_binding_status": "NOT_IMPLEMENTED_P1_2",
        }

    def credential_metadata(
        self,
        principal: Principal,
        screen_id: str,
        credential_id: str,
    ) -> dict[str, Any]:
        self.require_permission(principal, "device.revoke")
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT c.credential_id, c.credential_version, c.state, c.issued_at,
                    c.activation_expires_at, c.activated_at, c.revoked_at,
                    f.family_id, f.screen_id, f.state AS family_state,
                    f.credential_epoch, f.revision AS family_revision
                FROM device_credentials c
                JOIN device_credential_families f ON f.family_id = c.family_id
                WHERE c.credential_id = ? AND f.screen_id = ?
                """,
                (credential_id, screen_id),
            ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "NOT_FOUND", "Device credential was not found")
        return {
            "credential_id": row["credential_id"],
            "credential_version": row["credential_version"],
            "state": row["state"],
            "issued_at": row["issued_at"],
            "activation_expires_at": row["activation_expires_at"],
            "activated_at": row["activated_at"],
            "revoked_at": row["revoked_at"],
            "family_id": row["family_id"],
            "family_state": row["family_state"],
            "credential_epoch": row["credential_epoch"],
            "family_etag": self._etag("device-family", row["family_revision"]),
            "screen_id": row["screen_id"],
        }

    def list_audit_events(self, principal: Principal, limit: int = 100) -> list[dict[str, Any]]:
        self.require_permission(principal, "audit.read")
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_id, event_type, actor_type, actor_id,
                    target_type, target_id, outcome, reason, details_json,
                    previous_event_hash, event_hash, created_at
                FROM security_audit_events ORDER BY sequence DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "actor_type": row["actor_type"],
                "actor_id": row["actor_id"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "outcome": row["outcome"],
                "reason": row["reason"],
                "details": json.loads(row["details_json"]),
                "previous_event_hash": row["previous_event_hash"],
                "event_hash": row["event_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def record_denial(
        self,
        *,
        actor_type: str,
        actor_id: str | None,
        target_id: str,
        code: str,
    ) -> None:
        now = self.clock()
        with self.store.transaction() as connection:
            self._append_audit(
                connection,
                event_type="API_REQUEST_DENIED",
                actor_type=actor_type,
                actor_id=actor_id,
                target_type="API_OPERATION",
                target_id=target_id,
                outcome="DENIED",
                reason=code,
                details={},
                now=now,
            )

    def require_permission(self, principal: Principal, permission: str) -> None:
        if permission not in principal.permissions:
            raise ControlPlaneError(403, "FORBIDDEN", "Permission denied")

    def _request_or_execute_protected(
        self,
        context: SessionContext,
        *,
        operation_id: str,
        command: dict[str, Any],
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        permission = OPERATION_PERMISSION[operation_id]
        self.require_permission(context.principal, permission)
        self._require_recent_reauthentication(context)
        reason = reason.strip()
        if len(reason) < 3 or len(reason) > 500:
            raise ControlPlaneError(422, "VALIDATION_ERROR", "Reason must contain 3 to 500 characters")
        digest = self._protected_digest(operation_id, command, reason)
        sensitive_digest = self._sensitive_request_digest(
            operation_id,
            {"command": command, "reason": reason},
        )
        one_time_phase = f"execute:{operation_id}"
        one_time_principal = (
            f"{context.principal.user_id}:{high_risk_action_id}" if high_risk_action_id is not None else None
        )
        if operation_id == "issueDeviceEnrollment" and one_time_principal is not None:
            replay = self._load_one_time_replay(
                one_time_phase,
                one_time_principal,
                idempotency_key,
                sensitive_digest,
            )
            if replay is not None:
                return replay
        now = self.clock()
        if high_risk_action_id is not None:
            self._expire_due_actions(now, action_id=high_risk_action_id)
        with self.store.transaction() as connection:
            if high_risk_action_id is None:
                record = self._idempotency_lookup(
                    connection,
                    phase=f"request:{operation_id}",
                    principal_key=context.principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=sensitive_digest,
                )
                if record is not None:
                    return json.loads(record["result_json"])
                action_id = opaque_id("hra")
                connection.execute(
                    """
                    INSERT INTO high_risk_actions(
                        high_risk_action_id, operation_id, initiator_user_id, state,
                        request_digest, request_hmac_key_id, command_json, reason, target_id,
                        initiator_authentication_epoch, initiator_authorization_epoch,
                        requested_at, expires_at
                    ) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id,
                        operation_id,
                        context.principal.user_id,
                        digest,
                        self.keys.key_id("HIGH_RISK_REQUEST_HMAC"),
                        canonical_json(command),
                        reason,
                        command.get("screen_id") or command.get("normalized_username"),
                        context.principal.authentication_epoch,
                        context.principal.authorization_epoch,
                        now,
                        now + 15 * 60,
                    ),
                )
                action = connection.execute(
                    "SELECT * FROM high_risk_actions WHERE high_risk_action_id = ?",
                    (action_id,),
                ).fetchone()
                result = self._action_response(action)
                self._idempotency_store(
                    connection,
                    phase=f"request:{operation_id}",
                    principal_key=context.principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=sensitive_digest,
                    result=result,
                    now=now,
                )
                self._append_audit(
                    connection,
                    event_type="HIGH_RISK_ACTION_REQUESTED",
                    actor_type="USER",
                    actor_id=context.principal.user_id,
                    target_type="HIGH_RISK_ACTION",
                    target_id=action_id,
                    outcome="PENDING",
                    reason=reason,
                    details={"operation_id": operation_id, "request_digest": digest},
                    now=now,
                )
                return result
            action = self._load_action(connection, high_risk_action_id, now)
            if action["state"] == "CONSUMED":
                if action["initiator_user_id"] != context.principal.user_id:
                    raise ControlPlaneError(403, "FORBIDDEN", "Only the initiator may execute this action")
                if operation_id == "issueDeviceEnrollment":
                    raise ControlPlaneError(
                        409,
                        "ONE_TIME_RESPONSE_REPLAY_EXPIRED",
                        "Use the original execution idempotency key during the five-minute replay window",
                    )
                return json.loads(action["result_json"])
            if action["state"] != "APPROVED":
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Action is not approved")
            if action["initiator_user_id"] != context.principal.user_id:
                raise ControlPlaneError(403, "FORBIDDEN", "Only the initiator may execute this action")
            if action["operation_id"] != operation_id or not secrets.compare_digest(
                action["request_digest"], digest
            ):
                raise ControlPlaneError(
                    409, "HIGH_RISK_ACTION_MISMATCH", "Protected command changed after approval"
                )
            if (
                action["initiator_authentication_epoch"] != context.principal.authentication_epoch
                or action["initiator_authorization_epoch"] != context.principal.authorization_epoch
            ):
                raise ControlPlaneError(409, "HIGH_RISK_ACTION_MISMATCH", "Initiator authorization changed")
            approver = connection.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (action["approver_user_id"],),
            ).fetchone()
            if (
                approver is None
                or approver["account_state"] != "ACTIVE"
                or approver["authentication_epoch"] != action["approver_authentication_epoch"]
                or approver["authorization_epoch"] != action["approver_authorization_epoch"]
            ):
                raise ControlPlaneError(409, "HIGH_RISK_ACTION_MISMATCH", "Approver authorization changed")
            result = self._execute_protected_effect(connection, operation_id, command, context.principal, now)
            stored_result = result
            if operation_id == "issueDeviceEnrollment" and one_time_principal is not None:
                self._store_one_time_replay(
                    connection,
                    phase=one_time_phase,
                    principal_key=one_time_principal,
                    idempotency_key=idempotency_key,
                    request_digest=sensitive_digest,
                    result=result,
                    aad_context={
                        "device_enrollment_id": result["enrollment"]["enrollment_id"],
                        "screen_id": result["enrollment"]["screen_id"],
                        "installation_channel_id": one_time_principal,
                    },
                    now=now,
                )
                stored_result = {
                    "kind": result["kind"],
                    "enrollment": result["enrollment"],
                    "one_time_response": "ENCRYPTED_REPLAY_ONLY",
                }
            connection.execute(
                """
                UPDATE high_risk_actions SET state = 'CONSUMED', consumed_at = ?,
                    result_json = ?, revision = revision + 1 WHERE high_risk_action_id = ?
                """,
                (now, canonical_json(stored_result), high_risk_action_id),
            )
            self._append_audit(
                connection,
                event_type="HIGH_RISK_ACTION_CONSUMED",
                actor_type="USER",
                actor_id=context.principal.user_id,
                target_type="HIGH_RISK_ACTION",
                target_id=high_risk_action_id,
                outcome="SUCCESS",
                reason=reason,
                details={"operation_id": operation_id, "request_digest": digest},
                now=now,
            )
            return result

    def _execute_protected_effect(
        self,
        connection: sqlite3.Connection,
        operation_id: str,
        command: dict[str, Any],
        principal: Principal,
        now: float,
    ) -> dict[str, Any]:
        if operation_id == "createUser":
            user_id = opaque_id("usr")
            try:
                connection.execute(
                    """
                    INSERT INTO users(
                        user_id, tenant_id, deployment_id, normalized_username, display_name,
                        account_state, password_verifier, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'PROVISIONING', NULL, ?, ?)
                    """,
                    (
                        user_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        command["normalized_username"],
                        command["display_name"],
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ControlPlaneError(409, "RESOURCE_ALREADY_EXISTS", "Username already exists") from exc
            row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return {"kind": "USER_CREATED", "user": self._user_response(connection, row)}
        if operation_id == "issueDeviceEnrollment":
            metadata = self._metadata(connection)
            if command["screen_id"] != metadata["fixture_screen_id"]:
                raise ControlPlaneError(404, "NOT_FOUND", "Screen trust target was not found")
            family = self._current_screen_family(
                connection,
                principal.tenant_id,
                principal.deployment_id,
                command["screen_id"],
            )
            if family is not None and family["state"] == "ACTIVE":
                raise ControlPlaneError(
                    409,
                    "ACTIVE_DEVICE_FAMILY_EXISTS",
                    "An active device family already exists",
                )
            if not self._family_precondition_matches(
                family,
                state=command["family_precondition_state"],
                family_id=command["family_precondition_id"],
                revision=command["family_precondition_revision"],
            ):
                raise ControlPlaneError(
                    409,
                    "RESOURCE_VERSION_CONFLICT",
                    "Device family changed after four-eyes approval",
                )
            enrollment_id = opaque_id("enr")
            token_secret = opaque_secret()
            enrollment_token = f"{enrollment_id}.{token_secret}"
            connection.execute(
                """
                INSERT INTO device_enrollments(
                    enrollment_id, tenant_id, deployment_id, screen_id,
                    family_precondition_state, family_precondition_id,
                    family_precondition_revision, token_verifier_hmac,
                    verifier_key_id, state, issued_by_user_id, issued_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?, ?)
                """,
                (
                    enrollment_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    command["screen_id"],
                    command["family_precondition_state"],
                    command["family_precondition_id"],
                    command["family_precondition_revision"],
                    self.keys.digest("ONE_TIME_TOKEN_VERIFIER_PEPPER", token_secret),
                    self.keys.key_id("ONE_TIME_TOKEN_VERIFIER_PEPPER"),
                    principal.user_id,
                    now,
                    now + 15 * 60,
                ),
            )
            return {
                "kind": "DEVICE_ENROLLMENT_ISSUED",
                "enrollment_token": enrollment_token,
                "enrollment": {
                    "enrollment_id": enrollment_id,
                    "screen_id": command["screen_id"],
                    "state": "ISSUED",
                    "expires_at": now + 15 * 60,
                    "etag": self._etag("device-enrollment", 1),
                },
            }
        if operation_id == "revokeDeviceCredential":
            row = connection.execute(
                """
                SELECT c.credential_id, f.* FROM device_credentials c
                JOIN device_credential_families f ON f.family_id = c.family_id
                WHERE c.credential_id = ? AND f.screen_id = ?
                """,
                (command["credential_id"], command["screen_id"]),
            ).fetchone()
            if row is None:
                raise ControlPlaneError(404, "NOT_FOUND", "Device credential was not found")
            self._require_etag(command["family_etag"], "device-family", row["revision"])
            if row["credential_epoch"] != command["expected_credential_epoch"]:
                raise ControlPlaneError(409, "RESOURCE_VERSION_CONFLICT", "Credential epoch changed")
            if row["state"] != "ACTIVE":
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Device family is not active")
            connection.execute(
                """
                UPDATE device_credentials SET state = 'REVOKED', revoked_at = ?,
                    revision = revision + 1
                WHERE family_id = ? AND state IN ('ACTIVE', 'PENDING_ACTIVATION')
                """,
                (now, row["family_id"]),
            )
            connection.execute(
                """
                UPDATE device_credential_families SET state = 'REVOKED',
                    credential_epoch = credential_epoch + 1, active_credential_id = NULL,
                    pending_credential_id = NULL, updated_at = ?, revision = revision + 1
                WHERE family_id = ?
                """,
                (now, row["family_id"]),
            )
            return {
                "kind": "DEVICE_CREDENTIAL_FAMILY_REVOKED",
                "family_id": row["family_id"],
                "screen_id": row["screen_id"],
                "credential_epoch": row["credential_epoch"] + 1,
                "family_etag": self._etag("device-family", row["revision"] + 1),
                "state": "REVOKED",
            }
        raise ControlPlaneError(501, "NOT_IMPLEMENTED", "Protected operation is not implemented in P1.1")

    def _issue_session(self, connection: sqlite3.Connection, user_id: str, now: float) -> SessionIssue:
        user = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        cookie_value = opaque_secret()
        csrf_token = opaque_secret()
        session_id = opaque_id("ses")
        absolute_expires_at = now + 8 * 60 * 60
        connection.execute(
            """
            INSERT INTO auth_sessions(
                auth_session_id, user_id, verifier_hmac, verifier_key_id,
                csrf_verifier_hmac, csrf_verifier_key_id, state,
                authentication_epoch, authorization_epoch, created_at, last_seen_at,
                idle_expires_at, absolute_expires_at, recent_reauthentication_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                self.keys.digest("AUTH_SESSION_VERIFIER_PEPPER", cookie_value),
                self.keys.key_id("AUTH_SESSION_VERIFIER_PEPPER"),
                self.keys.digest("CSRF_TOKEN_VERIFIER_PEPPER", csrf_token),
                self.keys.key_id("CSRF_TOKEN_VERIFIER_PEPPER"),
                user["authentication_epoch"],
                user["authorization_epoch"],
                now,
                now,
                now + 30 * 60,
                absolute_expires_at,
                now,
            ),
        )
        principal = self._principal(connection, user)
        context = SessionContext(principal, session_id, 1, now)
        return SessionIssue(cookie_value, csrf_token, self._session_response(context))

    def _record_login_failure(self, connection: sqlite3.Connection, user: sqlite3.Row, now: float) -> None:
        window_start = user["failed_window_started_at"]
        attempts = user["failed_attempts"]
        if window_start is None or now - window_start > 15 * 60:
            window_start = now
            attempts = 0
        attempts += 1
        lock_level = user["lock_level"]
        if user["last_lock_at"] is None or now - user["last_lock_at"] > 24 * 60 * 60:
            lock_level = 0
        locked_until = None
        last_lock_at = user["last_lock_at"]
        if attempts >= 5:
            lock_level = min(lock_level + 1, 3)
            duration = (15, 30, 60)[lock_level - 1]
            locked_until = now + duration * 60
            last_lock_at = now
            attempts = 0
            window_start = None
        connection.execute(
            """
            UPDATE users SET failed_window_started_at = ?, failed_attempts = ?,
                lock_level = ?, last_lock_at = ?, locked_until = ?,
                updated_at = ?, revision = revision + 1
            WHERE user_id = ?
            """,
            (
                window_start,
                attempts,
                lock_level,
                last_lock_at,
                locked_until,
                now,
                user["user_id"],
            ),
        )
        self._append_audit(
            connection,
            event_type="AUTHENTICATION",
            actor_type="USER",
            actor_id=user["user_id"],
            target_type="USER",
            target_id=user["user_id"],
            outcome="DENIED",
            reason="invalid credentials",
            details={"lock_applied": locked_until is not None, "lock_level": lock_level},
            now=now,
        )

    def _principal(self, connection: sqlite3.Connection, user: sqlite3.Row) -> Principal:
        assignments = connection.execute(
            "SELECT role_id FROM role_assignments WHERE user_id = ? ORDER BY role_id",
            (user["user_id"],),
        ).fetchall()
        roles = tuple(row["role_id"] for row in assignments)
        permissions = frozenset(permission for role in roles for permission in ROLE_PERMISSIONS.get(role, ()))
        return Principal(
            user_id=user["user_id"],
            username=user["normalized_username"],
            display_name=user["display_name"],
            tenant_id=user["tenant_id"],
            deployment_id=user["deployment_id"],
            permissions=permissions,
            roles=roles,
            authentication_epoch=user["authentication_epoch"],
            authorization_epoch=user["authorization_epoch"],
        )

    def _session_response(self, context: SessionContext) -> dict[str, Any]:
        return {
            "auth_session_id": context.auth_session_id,
            "etag": self._etag("session", context.revision),
            "user": {
                "user_id": context.principal.user_id,
                "normalized_username": context.principal.username,
                "display_name": context.principal.display_name,
                "roles": list(context.principal.roles),
                "permissions": sorted(context.principal.permissions),
            },
            "profile": "DEVELOPMENT_PREVIEW",
            "production_ready": False,
        }

    def _user_response(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        assignments = connection.execute(
            """
            SELECT role_id, scope_type, scope_id FROM role_assignments
            WHERE user_id = ? ORDER BY role_id, scope_type, scope_id
            """,
            (row["user_id"],),
        ).fetchall()
        return {
            "user_id": row["user_id"],
            "normalized_username": row["normalized_username"],
            "display_name": row["display_name"],
            "account_state": row["account_state"],
            "credential_generation": row["credential_generation"],
            "authentication_epoch": row["authentication_epoch"],
            "authorization_epoch": row["authorization_epoch"],
            "account_state_generation": row["account_state_generation"],
            "locked_until": row["locked_until"],
            "last_login_at": row["last_login_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "etag": self._etag("user", row["revision"]),
            "role_assignments": [dict(assignment) for assignment in assignments],
        }

    def _action_response(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "high_risk_action_id": row["high_risk_action_id"],
            "operation_id": row["operation_id"],
            "state": row["state"],
            "request_digest": row["request_digest"],
            "reason": row["reason"],
            "target_id": row["target_id"],
            "initiator_user_id": row["initiator_user_id"],
            "approver_user_id": row["approver_user_id"],
            "requested_at": row["requested_at"],
            "expires_at": row["expires_at"],
            "approved_at": row["approved_at"],
            "consumed_at": row["consumed_at"],
            "etag": self._etag("high-risk-action", row["revision"]),
        }

    def _enrollment_response(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "enrollment_id": row["enrollment_id"],
            "screen_id": row["screen_id"],
            "state": row["state"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "claimed_at": row["claimed_at"],
            "revoked_at": row["revoked_at"],
            "etag": self._etag("device-enrollment", row["revision"]),
        }

    def _protected_digest(self, operation_id: str, command: dict[str, Any], reason: str) -> str:
        return self.keys.digest(
            "HIGH_RISK_REQUEST_HMAC",
            canonical_json({"operation_id": operation_id, "command": command, "reason": reason}),
        )

    def _load_action(self, connection: sqlite3.Connection, action_id: str, now: float) -> sqlite3.Row:
        action = connection.execute(
            "SELECT * FROM high_risk_actions WHERE high_risk_action_id = ?",
            (action_id,),
        ).fetchone()
        if action is None:
            raise ControlPlaneError(404, "NOT_FOUND", "High-risk action was not found")
        if action["state"] in ("PENDING", "APPROVED") and action["expires_at"] <= now:
            raise ControlPlaneError(409, "HIGH_RISK_ACTION_EXPIRED", "High-risk action expired")
        if action["state"] == "EXPIRED":
            raise ControlPlaneError(409, "HIGH_RISK_ACTION_EXPIRED", "High-risk action expired")
        return action

    def _expire_due_actions(self, now: float, *, action_id: str | None = None) -> None:
        with self.store.transaction() as connection:
            if action_id is None:
                rows = connection.execute(
                    """
                    SELECT high_risk_action_id, operation_id
                    FROM high_risk_actions
                    WHERE state IN ('PENDING', 'APPROVED') AND expires_at <= ?
                    """,
                    (now,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT high_risk_action_id, operation_id
                    FROM high_risk_actions
                    WHERE high_risk_action_id = ?
                        AND state IN ('PENDING', 'APPROVED') AND expires_at <= ?
                    """,
                    (action_id, now),
                ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE high_risk_actions SET state = 'EXPIRED', revision = revision + 1
                    WHERE high_risk_action_id = ?
                    """,
                    (row["high_risk_action_id"],),
                )
                self._append_audit(
                    connection,
                    event_type="HIGH_RISK_ACTION_EXPIRED",
                    actor_type="SYSTEM",
                    actor_id=None,
                    target_type="HIGH_RISK_ACTION",
                    target_id=row["high_risk_action_id"],
                    outcome="DENIED",
                    reason="approval window expired",
                    details={"operation_id": row["operation_id"]},
                    now=now,
                )

    def _expire_enrollment_if_needed(self, enrollment_id: str, now: float) -> None:
        with self.store.transaction() as connection:
            enrollment = connection.execute(
                """
                SELECT enrollment_id, screen_id FROM device_enrollments
                WHERE enrollment_id = ? AND state = 'ISSUED' AND expires_at <= ?
                """,
                (enrollment_id, now),
            ).fetchone()
            if enrollment is None:
                return
            connection.execute(
                """
                UPDATE device_enrollments SET state = 'EXPIRED', revision = revision + 1
                WHERE enrollment_id = ?
                """,
                (enrollment_id,),
            )
            self._append_audit(
                connection,
                event_type="DEVICE_ENROLLMENT_EXPIRED",
                actor_type="SYSTEM",
                actor_id=None,
                target_type="SCREEN",
                target_id=enrollment["screen_id"],
                outcome="DENIED",
                reason="claim window expired",
                details={"enrollment_id": enrollment_id},
                now=now,
            )

    def _require_recent_reauthentication(self, context: SessionContext) -> None:
        if (
            context.recent_reauthentication_at is None
            or self.clock() - context.recent_reauthentication_at > 10 * 60
        ):
            raise ControlPlaneError(
                403,
                "RECENT_REAUTHENTICATION_REQUIRED",
                "Recent password confirmation is required",
            )

    def _metadata(self, connection: sqlite3.Connection) -> sqlite3.Row:
        metadata = connection.execute("SELECT * FROM control_plane_metadata WHERE singleton = 1").fetchone()
        if metadata is None:
            raise ControlPlaneError(503, "CONTROL_PLANE_NOT_INITIALIZED", "Control plane is not initialized")
        return metadata

    def _device_enrollment_command(
        self,
        principal: Principal,
        *,
        screen_id: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        with self.store.connect() as connection:
            action = None
            replayed_request = False
            if high_risk_action_id is not None:
                action = connection.execute(
                    """
                    SELECT operation_id, command_json FROM high_risk_actions
                    WHERE high_risk_action_id = ?
                    """,
                    (high_risk_action_id,),
                ).fetchone()
            else:
                request_record = connection.execute(
                    """
                    SELECT result_json FROM idempotency_records
                    WHERE phase = 'request:issueDeviceEnrollment'
                        AND principal_key = ? AND idempotency_key_digest = ?
                    """,
                    (principal.user_id, self._idempotency_key_digest(idempotency_key)),
                ).fetchone()
                if request_record is not None:
                    replayed_request = True
                    try:
                        action_id = json.loads(request_record["result_json"])["high_risk_action_id"]
                    except (TypeError, KeyError, json.JSONDecodeError) as exc:
                        raise ControlPlaneError(
                            409,
                            "IDEMPOTENCY_EVIDENCE_INVALID",
                            "Enrollment request evidence is invalid",
                        ) from exc
                    action = connection.execute(
                        """
                        SELECT operation_id, command_json FROM high_risk_actions
                        WHERE high_risk_action_id = ?
                        """,
                        (action_id,),
                    ).fetchone()
                    if action is None:
                        raise ControlPlaneError(
                            409,
                            "IDEMPOTENCY_EVIDENCE_INVALID",
                            "Enrollment request evidence is invalid",
                        )
            if action is not None and action["operation_id"] == "issueDeviceEnrollment":
                try:
                    command = json.loads(action["command_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ControlPlaneError(
                        409,
                        "IDEMPOTENCY_EVIDENCE_INVALID",
                        "Enrollment approval evidence is invalid",
                    ) from exc
                if not isinstance(command, dict) or set(command) != {
                    "screen_id",
                    "family_precondition_state",
                    "family_precondition_id",
                    "family_precondition_revision",
                }:
                    raise ControlPlaneError(
                        409,
                        "IDEMPOTENCY_EVIDENCE_INVALID",
                        "Enrollment approval evidence is invalid",
                    )
                if command["screen_id"] != screen_id:
                    code = "IDEMPOTENCY_KEY_REUSED" if replayed_request else "HIGH_RISK_ACTION_MISMATCH"
                    raise ControlPlaneError(409, code, "Enrollment screen changed")
                return command

            family = self._current_screen_family(
                connection,
                principal.tenant_id,
                principal.deployment_id,
                screen_id,
            )
            if family is not None and family["state"] == "ACTIVE":
                raise ControlPlaneError(
                    409,
                    "ACTIVE_DEVICE_FAMILY_EXISTS",
                    "An active device family already exists",
                )
            if family is None:
                return {
                    "screen_id": screen_id,
                    "family_precondition_state": "ABSENT",
                    "family_precondition_id": None,
                    "family_precondition_revision": None,
                }
            return {
                "screen_id": screen_id,
                "family_precondition_state": family["state"],
                "family_precondition_id": family["family_id"],
                "family_precondition_revision": family["revision"],
            }

    @staticmethod
    def _current_screen_family(
        connection: sqlite3.Connection,
        tenant_id: str,
        deployment_id: str,
        screen_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM device_credential_families
            WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
            ORDER BY
                CASE WHEN state = 'ACTIVE' THEN 0 ELSE 1 END,
                created_at DESC,
                rowid DESC
            LIMIT 1
            """,
            (tenant_id, deployment_id, screen_id),
        ).fetchone()

    @staticmethod
    def _family_precondition_matches(
        family: sqlite3.Row | None,
        *,
        state: str,
        family_id: str | None,
        revision: int | None,
    ) -> bool:
        if state == "ABSENT":
            return family is None and family_id is None and revision is None
        if state not in {"REVOKED", "REENROLL_REQUIRED"} or family is None:
            return False
        return (
            family["state"] == state and family["family_id"] == family_id and family["revision"] == revision
        )

    def _idempotency_lookup(
        self,
        connection: sqlite3.Connection,
        *,
        phase: str,
        principal_key: str,
        idempotency_key: str,
        request_digest: str,
    ) -> sqlite3.Row | None:
        key_digest = self._idempotency_key_digest(idempotency_key)
        row = connection.execute(
            """
            SELECT * FROM idempotency_records
            WHERE phase = ? AND principal_key = ? AND idempotency_key_digest = ?
            """,
            (phase, principal_key, key_digest),
        ).fetchone()
        operation_id, canonical_route = self._idempotency_operation_route(phase)
        if row is not None and (
            row["operation_id"] != operation_id or row["canonical_route"] != canonical_route
        ):
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "Idempotency route evidence is invalid",
            )
        if row is not None and row["sensitive_digest_key_id"] != self.keys.key_id(
            "SENSITIVE_REQUEST_DIGEST_HMAC"
        ):
            raise ControlPlaneError(
                409,
                "REQUEST_DIGEST_KEY_EPOCH_CHANGED",
                "Sensitive request evidence uses an unavailable key generation",
            )
        if row is not None and not secrets.compare_digest(
            row["sensitive_request_digest"],
            request_digest,
        ):
            raise ControlPlaneError(
                409, "IDEMPOTENCY_KEY_REUSED", "Idempotency key was reused with different content"
            )
        return row

    def _idempotency_store(
        self,
        connection: sqlite3.Connection,
        *,
        phase: str,
        principal_key: str,
        idempotency_key: str,
        request_digest: str,
        result: dict[str, Any],
        now: float,
    ) -> None:
        operation_id, canonical_route = self._idempotency_operation_route(phase)
        connection.execute(
            """
            INSERT INTO idempotency_records(
                record_id, phase, principal_key, idempotency_key_digest,
                operation_id, canonical_route, sensitive_request_digest,
                sensitive_digest_key_id, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opaque_id("idem"),
                phase,
                principal_key,
                self._idempotency_key_digest(idempotency_key),
                operation_id,
                canonical_route,
                request_digest,
                self.keys.key_id("SENSITIVE_REQUEST_DIGEST_HMAC"),
                canonical_json(result),
                now,
            ),
        )

    def _load_one_time_replay(
        self,
        phase: str,
        principal_key: str,
        idempotency_key: str,
        request_digest: str,
    ) -> dict[str, Any] | None:
        expired = False
        result: dict[str, Any] | None = None
        now = self.clock()
        with self.store.transaction() as connection:
            row = self._idempotency_lookup(
                connection,
                phase=phase,
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if row is not None:
                result = self._decrypt_one_time_replay(
                    row,
                    phase=phase,
                    principal_key=principal_key,
                    request_digest=request_digest,
                )
            if row is not None and (row["response_expires_at"] is None or row["response_expires_at"] <= now):
                self._cleanup_expired_one_time_replay(
                    connection,
                    phase=phase,
                    result=result,
                    now=now,
                )
                connection.execute(
                    """
                    UPDATE idempotency_records
                    SET response_nonce = NULL, response_ciphertext = NULL,
                        response_aad_json = NULL
                    WHERE record_id = ?
                    """,
                    (row["record_id"],),
                )
                expired = True
        if row is None:
            return None
        if expired:
            raise ControlPlaneError(
                409,
                "ONE_TIME_RESPONSE_REPLAY_EXPIRED",
                "The one-time response replay window expired",
            )
        return result

    def _store_one_time_replay(
        self,
        connection: sqlite3.Connection,
        *,
        phase: str,
        principal_key: str,
        idempotency_key: str,
        request_digest: str,
        result: dict[str, Any],
        aad_context: dict[str, Any],
        now: float,
    ) -> None:
        record_id = opaque_id("idem")
        key_digest = self._idempotency_key_digest(idempotency_key)
        expires_at = now + 5 * 60
        operation_id, canonical_route = self._idempotency_operation_route(phase)
        sensitive_digest_key_id = self.keys.key_id("SENSITIVE_REQUEST_DIGEST_HMAC")
        response_encryption_key_id = self.keys.key_id("ONE_TIME_RESPONSE_ENCRYPTION")
        aad_payload = {
            "schema_version": "p1_one_time_response_aad_v1",
            "record_id": record_id,
            "phase": phase,
            "operation_id": operation_id,
            "canonical_route": canonical_route,
            "principal_key": principal_key,
            "idempotency_key_digest": key_digest,
            "sensitive_request_digest_hmac": request_digest,
            "sensitive_request_digest_hmac_key_id": sensitive_digest_key_id,
            "sensitive_request_digest_schema_version": "p1_sensitive_request_digest_v1",
            "response_encryption_key_id": response_encryption_key_id,
            "delivery_channel_id": principal_key,
            "expires_at": expires_at,
            **aad_context,
        }
        aad_json = canonical_json(aad_payload)
        aad = aad_json.encode("utf-8")
        aad_hash = hashlib.sha256(aad).hexdigest()
        encrypted = self.keys.encrypt(
            canonical_json(result).encode("utf-8"),
            aad,
        )
        connection.execute(
            """
            INSERT INTO idempotency_records(
                record_id, phase, principal_key, idempotency_key_digest,
                operation_id, canonical_route, sensitive_request_digest,
                sensitive_digest_key_id, response_nonce, response_ciphertext,
                response_encryption_key_id, response_aad_json, response_aad_hash,
                response_expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                phase,
                principal_key,
                key_digest,
                operation_id,
                canonical_route,
                request_digest,
                sensitive_digest_key_id,
                encrypted.nonce,
                encrypted.value,
                response_encryption_key_id,
                aad_json,
                aad_hash,
                expires_at,
                now,
            ),
        )

    def _idempotency_key_digest(self, idempotency_key: str) -> str:
        if len(idempotency_key) < 8 or len(idempotency_key) > 200 or not idempotency_key.isprintable():
            raise ControlPlaneError(
                422,
                "VALIDATION_ERROR",
                "Idempotency-Key must contain 8 to 200 printing characters",
            )
        return hashlib.sha256(
            b"shuziren:p1:idempotency-key:v1\0" + idempotency_key.encode("utf-8")
        ).hexdigest()

    def _sensitive_request_digest(self, operation_id: str, value: dict[str, Any]) -> str:
        payload = canonical_json(
            {
                "schema_version": "p1_sensitive_request_digest_v1",
                "operation_id": operation_id,
                "request": value,
            }
        ).encode("utf-8")
        return self.keys.digest(
            "SENSITIVE_REQUEST_DIGEST_HMAC",
            b"shuziren:p1:sensitive-request-digest:v1\0" + payload,
        )

    @staticmethod
    def _idempotency_operation_route(phase: str) -> tuple[str, str]:
        try:
            return IDEMPOTENCY_OPERATION_ROUTES[phase]
        except KeyError as exc:
            raise RuntimeError(f"Missing idempotency route metadata for {phase}") from exc

    def _decrypt_one_time_replay(
        self,
        row: sqlite3.Row,
        *,
        phase: str,
        principal_key: str,
        request_digest: str,
    ) -> dict[str, Any]:
        if row["response_encryption_key_id"] != self.keys.key_id("ONE_TIME_RESPONSE_ENCRYPTION"):
            raise ControlPlaneError(
                503,
                "ONE_TIME_RESPONSE_KEY_UNAVAILABLE",
                "The one-time response key is unavailable",
                retryable=True,
            )
        aad_json = row["response_aad_json"]
        if not aad_json or row["response_nonce"] is None or row["response_ciphertext"] is None:
            raise ControlPlaneError(
                409,
                "ONE_TIME_RESPONSE_REPLAY_EXPIRED",
                "The one-time response replay window expired",
            )
        aad = aad_json.encode("utf-8")
        if not secrets.compare_digest(
            hashlib.sha256(aad).hexdigest(),
            row["response_aad_hash"],
        ):
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response associated-data evidence is invalid",
            )
        try:
            aad_payload = json.loads(aad_json)
        except json.JSONDecodeError as exc:
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response associated-data evidence is invalid",
            ) from exc
        if not isinstance(aad_payload, dict):
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response associated-data evidence is invalid",
            )
        operation_id, canonical_route = self._idempotency_operation_route(phase)
        expected = {
            "schema_version": "p1_one_time_response_aad_v1",
            "record_id": row["record_id"],
            "phase": phase,
            "operation_id": operation_id,
            "canonical_route": canonical_route,
            "principal_key": principal_key,
            "idempotency_key_digest": row["idempotency_key_digest"],
            "sensitive_request_digest_hmac": request_digest,
            "sensitive_request_digest_hmac_key_id": row["sensitive_digest_key_id"],
            "sensitive_request_digest_schema_version": "p1_sensitive_request_digest_v1",
            "response_encryption_key_id": row["response_encryption_key_id"],
            "delivery_channel_id": principal_key,
            "expires_at": row["response_expires_at"],
        }
        for key, value in expected.items():
            if aad_payload.get(key) != value:
                raise ControlPlaneError(
                    409,
                    "IDEMPOTENCY_EVIDENCE_INVALID",
                    "One-time response associated-data binding is invalid",
                )
        required_fields = ONE_TIME_AAD_REQUIRED_FIELDS.get(phase)
        if required_fields is None or any(not aad_payload.get(field) for field in required_fields):
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response operation context is incomplete",
            )
        try:
            plaintext = self.keys.decrypt(
                Ciphertext(
                    nonce=row["response_nonce"],
                    value=row["response_ciphertext"],
                ),
                aad,
            )
            result = json.loads(plaintext)
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response ciphertext evidence is invalid",
            ) from exc
        if not isinstance(result, dict):
            raise ControlPlaneError(
                409,
                "IDEMPOTENCY_EVIDENCE_INVALID",
                "One-time response ciphertext evidence is invalid",
            )
        return result

    def _cleanup_expired_one_time_replay(
        self,
        connection: sqlite3.Connection,
        *,
        phase: str,
        result: dict[str, Any] | None,
        now: float,
    ) -> None:
        if result is None:
            return
        if phase == "execute:issueDeviceEnrollment":
            enrollment_id = result["enrollment"]["enrollment_id"]
            updated = connection.execute(
                """
                UPDATE device_enrollments SET state = 'REVOKED', revoked_at = ?,
                    revision = revision + 1
                WHERE enrollment_id = ? AND state = 'ISSUED'
                """,
                (now, enrollment_id),
            )
            if updated.rowcount == 1:
                self._append_audit(
                    connection,
                    event_type="DEVICE_ENROLLMENT_REPLAY_EXPIRED",
                    actor_type="SYSTEM",
                    actor_id=None,
                    target_type="SCREEN",
                    target_id=result["enrollment"]["screen_id"],
                    outcome="DENIED",
                    reason="one-time response replay window expired",
                    details={"enrollment_id": enrollment_id},
                    now=now,
                )
            return
        if phase == "claimDeviceEnrollment":
            credential = connection.execute(
                """
                SELECT c.credential_id, c.family_id, c.state, c.last_authenticated_at,
                    f.screen_id, f.state AS family_state, f.active_credential_id
                FROM device_credentials c
                JOIN device_credential_families f ON f.family_id = c.family_id
                WHERE c.credential_id = ?
                """,
                (result["credential_id"],),
            ).fetchone()
            if (
                credential is not None
                and credential["state"] == "ACTIVE"
                and credential["last_authenticated_at"] is None
                and credential["family_state"] == "ACTIVE"
                and credential["active_credential_id"] == credential["credential_id"]
            ):
                connection.execute(
                    """
                    UPDATE device_credentials SET state = 'REVOKED', revoked_at = ?,
                        revision = revision + 1
                    WHERE credential_id = ? AND state = 'ACTIVE'
                    """,
                    (now, credential["credential_id"]),
                )
                connection.execute(
                    """
                    UPDATE device_credential_families SET state = 'REENROLL_REQUIRED',
                        credential_epoch = credential_epoch + 1,
                        active_credential_id = NULL, pending_credential_id = NULL,
                        updated_at = ?, revision = revision + 1
                    WHERE family_id = ? AND state = 'ACTIVE'
                    """,
                    (now, credential["family_id"]),
                )
                self._append_audit(
                    connection,
                    event_type="DEVICE_CLAIM_REPLAY_EXPIRED",
                    actor_type="SYSTEM",
                    actor_id=None,
                    target_type="SCREEN",
                    target_id=credential["screen_id"],
                    outcome="DENIED",
                    reason="credential delivery was not proven",
                    details={"credential_id": credential["credential_id"]},
                    now=now,
                )
            return
        if phase == "rotateDeviceCredential":
            successor = connection.execute(
                """
                SELECT c.credential_id, c.family_id, c.state, f.screen_id,
                    f.state AS family_state, f.active_credential_id, f.pending_credential_id
                FROM device_credentials c
                JOIN device_credential_families f ON f.family_id = c.family_id
                WHERE c.credential_id = ?
                """,
                (result["credential_id"],),
            ).fetchone()
            if (
                successor is not None
                and successor["state"] == "PENDING_ACTIVATION"
                and successor["family_state"] == "ACTIVE"
                and successor["pending_credential_id"] == successor["credential_id"]
            ):
                connection.execute(
                    """
                    UPDATE device_credentials SET state = 'REVOKED', revoked_at = ?,
                        revision = revision + 1
                    WHERE credential_id = ? AND state = 'PENDING_ACTIVATION'
                    """,
                    (now, successor["credential_id"]),
                )
                connection.execute(
                    """
                    UPDATE device_credential_families SET pending_credential_id = NULL,
                        updated_at = ?, revision = revision + 1
                    WHERE family_id = ? AND pending_credential_id = ?
                    """,
                    (now, successor["family_id"], successor["credential_id"]),
                )
                self._append_audit(
                    connection,
                    event_type="DEVICE_CREDENTIAL_ROTATION_REPLAY_EXPIRED",
                    actor_type="SYSTEM",
                    actor_id=None,
                    target_type="SCREEN",
                    target_id=successor["screen_id"],
                    outcome="DENIED",
                    reason="successor delivery was not proven",
                    details={"successor_credential_id": successor["credential_id"]},
                    now=now,
                )

    def _append_audit(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str | None,
        target_type: str | None,
        target_id: str | None,
        outcome: str,
        reason: str | None,
        details: dict[str, Any],
        now: float,
    ) -> None:
        sanitized = self._sanitize_details(details)
        previous = connection.execute(
            "SELECT event_hash FROM security_audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_id = opaque_id("aud")
        payload = canonical_json(
            {
                "event_id": event_id,
                "event_type": event_type,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "target_type": target_type,
                "target_id": target_id,
                "outcome": outcome,
                "reason": reason,
                "details": sanitized,
                "previous_event_hash": previous_hash,
                "created_at": now,
            }
        )
        event_hash = hashlib.sha256(
            b"shuziren:p1:security-audit-event:v1\0" + payload.encode("utf-8")
        ).hexdigest()
        connection.execute(
            """
            INSERT INTO security_audit_events(
                event_id, event_type, actor_type, actor_id, target_type, target_id,
                outcome, reason, details_json, previous_event_hash, event_hash,
                event_hash_schema_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                actor_type,
                actor_id,
                target_type,
                target_id,
                outcome,
                reason,
                canonical_json(sanitized),
                previous_hash,
                event_hash,
                "p1_security_audit_event_hash_v1",
                now,
            ),
        )

    def _sanitize_details(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, nested in value.items():
                if any(fragment in key.casefold() for fragment in SENSITIVE_DETAIL_KEYS):
                    continue
                sanitized[key] = self._sanitize_details(nested)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_details(item) for item in value]
        return value

    @staticmethod
    def _parse_bound_secret(value: str, label: str) -> tuple[str, str]:
        identifier, separator, secret_value = value.partition(".")
        if not separator or not identifier or not secret_value:
            raise ControlPlaneError(401, "AUTHENTICATION_REQUIRED", f"{label.title()} token is invalid")
        return identifier, secret_value

    @staticmethod
    def _parse_device_authorization(value: str) -> tuple[str, str]:
        scheme, separator, credential = value.partition(" ")
        if not separator or scheme != "DeviceCredential":
            raise ControlPlaneError(401, "AUTHENTICATION_REQUIRED", "Device credential is required")
        return ControlPlaneService._parse_bound_secret(credential, "device credential")

    @staticmethod
    def _etag(kind: str, revision: int) -> str:
        return f'"{kind}:{revision}"'

    @staticmethod
    def _require_etag(actual: str, kind: str, revision: int) -> None:
        expected = ControlPlaneService._etag(kind, revision)
        if actual != expected:
            raise ControlPlaneError(
                409,
                "RESOURCE_VERSION_CONFLICT",
                "Resource version changed",
                details={"expected_etag": expected},
            )
