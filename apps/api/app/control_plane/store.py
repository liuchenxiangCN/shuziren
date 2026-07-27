from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOGICAL_SCHEMA_VERSION = "p1_control_plane_001"


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS control_plane_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    profile TEXT NOT NULL CHECK (profile IN ('UNINITIALIZED', 'DEVELOPMENT_PREVIEW')),
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    fixture_screen_id TEXT,
    created_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    normalized_username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    account_state TEXT NOT NULL CHECK (
        account_state IN ('PROVISIONING', 'ACTIVE', 'DISABLED')
    ),
    password_verifier TEXT,
    credential_generation INTEGER NOT NULL DEFAULT 0,
    authentication_epoch INTEGER NOT NULL DEFAULT 1,
    authorization_epoch INTEGER NOT NULL DEFAULT 1,
    account_state_generation INTEGER NOT NULL DEFAULT 1,
    failed_window_started_at REAL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    lock_level INTEGER NOT NULL DEFAULT 0,
    last_lock_at REAL,
    locked_until REAL,
    last_login_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, deployment_id, normalized_username),
    CHECK (
        (account_state = 'PROVISIONING' AND password_verifier IS NULL)
        OR (account_state IN ('ACTIVE', 'DISABLED') AND password_verifier IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS role_assignments (
    assignment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    role_id TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('DEPLOYMENT', 'SITE', 'SCREEN')),
    scope_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (user_id, role_id, scope_type, scope_id)
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    auth_session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    verifier_hmac TEXT NOT NULL UNIQUE,
    verifier_key_id TEXT NOT NULL,
    csrf_verifier_hmac TEXT NOT NULL,
    csrf_verifier_key_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('ACTIVE', 'IDLE_EXPIRED', 'ABSOLUTE_EXPIRED', 'REVOKED')
    ),
    authentication_epoch INTEGER NOT NULL,
    authorization_epoch INTEGER NOT NULL,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    idle_expires_at REAL NOT NULL,
    absolute_expires_at REAL NOT NULL,
    recent_reauthentication_at REAL,
    revoked_at REAL,
    revision INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON auth_sessions(user_id, state, created_at DESC);

CREATE TABLE IF NOT EXISTS high_risk_actions (
    high_risk_action_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    initiator_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    approver_user_id TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (
        state IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'CONSUMED', 'FAILED')
    ),
    request_digest TEXT NOT NULL,
    request_hmac_key_id TEXT NOT NULL,
    command_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    target_id TEXT,
    initiator_authentication_epoch INTEGER NOT NULL,
    initiator_authorization_epoch INTEGER NOT NULL,
    approver_authentication_epoch INTEGER,
    approver_authorization_epoch INTEGER,
    requested_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    approved_at REAL,
    consumed_at REAL,
    result_json TEXT,
    revision INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_high_risk_state
    ON high_risk_actions(state, requested_at DESC);

CREATE TABLE IF NOT EXISTS device_enrollments (
    enrollment_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    token_verifier_hmac TEXT NOT NULL UNIQUE,
    verifier_key_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ISSUED', 'CLAIMED', 'EXPIRED', 'REVOKED')),
    issued_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    claimed_at REAL,
    revoked_at REAL,
    revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS device_credential_families (
    family_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'REVOKED', 'REENROLL_REQUIRED')),
    credential_epoch INTEGER NOT NULL DEFAULT 1,
    active_credential_id TEXT,
    pending_credential_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, deployment_id, screen_id)
);

CREATE TABLE IF NOT EXISTS device_credentials (
    credential_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL REFERENCES device_credential_families(family_id) ON DELETE RESTRICT,
    credential_version INTEGER NOT NULL,
    verifier_hmac TEXT NOT NULL UNIQUE,
    verifier_key_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('PENDING_ACTIVATION', 'ACTIVE', 'EXPIRED', 'REVOKED')),
    issued_at REAL NOT NULL,
    activation_expires_at REAL,
    activated_at REAL,
    revoked_at REAL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (family_id, credential_version)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    record_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL,
    principal_key TEXT NOT NULL,
    idempotency_key_digest TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    result_json TEXT,
    response_nonce BLOB,
    response_ciphertext BLOB,
    response_expires_at REAL,
    created_at REAL NOT NULL,
    UNIQUE (phase, principal_key, idempotency_key_digest)
);

CREATE TABLE IF NOT EXISTS security_audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    target_type TEXT,
    target_id TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS', 'DENIED', 'PENDING', 'APPROVED', 'REJECTED')),
    reason TEXT,
    details_json TEXT NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE,
    event_hmac_key_id TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TRIGGER IF NOT EXISTS security_audit_events_no_update
BEFORE UPDATE ON security_audit_events
BEGIN
    SELECT RAISE(ABORT, 'security audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS security_audit_events_no_delete
BEFORE DELETE ON security_audit_events
BEGIN
    SELECT RAISE(ABORT, 'security audit events are immutable');
END;
"""


class ControlPlaneStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self, now: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (LOGICAL_SCHEMA_VERSION, now),
            )
            connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, factory=ClosingConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection
