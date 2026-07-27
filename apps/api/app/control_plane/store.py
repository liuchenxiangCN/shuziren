from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.control_plane.security import canonical_json, uuid7

LOGICAL_SCHEMA_VERSION = "p1_control_plane_001"
MIGRATION_001_VERSION = "001_initial_identity_device_trust"
MIGRATION_002_VERSION = "002_three_screen_inventory"
MIGRATION_003_VERSION = "003_publish_rollback_recovery"


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    checksum_sha256 TEXT NOT NULL,
    applied_at REAL NOT NULL
);
"""

SCHEMA_SQL = """
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
    family_precondition_state TEXT NOT NULL CHECK (
        family_precondition_state IN ('ABSENT', 'REVOKED', 'REENROLL_REQUIRED')
    ),
    family_precondition_id TEXT REFERENCES device_credential_families(family_id) ON DELETE RESTRICT,
    family_precondition_revision INTEGER,
    token_verifier_hmac TEXT NOT NULL UNIQUE,
    verifier_key_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ISSUED', 'CLAIMED', 'EXPIRED', 'REVOKED')),
    issued_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    claimed_at REAL,
    revoked_at REAL,
    revision INTEGER NOT NULL DEFAULT 1,
    CHECK (
        (
            family_precondition_state = 'ABSENT'
            AND family_precondition_id IS NULL
            AND family_precondition_revision IS NULL
        )
        OR (
            family_precondition_state IN ('REVOKED', 'REENROLL_REQUIRED')
            AND family_precondition_id IS NOT NULL
            AND family_precondition_revision >= 1
        )
    )
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
    revision INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_device_credential_family_active_screen
    ON device_credential_families(tenant_id, deployment_id, screen_id)
    WHERE state = 'ACTIVE';

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
    last_authenticated_at REAL,
    revoked_at REAL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (family_id, credential_version)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    record_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL,
    principal_key TEXT NOT NULL,
    idempotency_key_digest TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    canonical_route TEXT NOT NULL,
    sensitive_request_digest TEXT NOT NULL,
    sensitive_digest_key_id TEXT NOT NULL,
    result_json TEXT,
    response_nonce BLOB,
    response_ciphertext BLOB,
    response_encryption_key_id TEXT,
    response_aad_json TEXT,
    response_aad_hash TEXT,
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
    event_hash_schema_version TEXT NOT NULL,
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

MIGRATION_001_CHECKSUM_SHA256 = hashlib.sha256(SCHEMA_SQL.encode("utf-8")).hexdigest()

INVENTORY_SCHEMA_SQL = """
CREATE TABLE sites (
    site_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'ACTIVE'),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, deployment_id, site_id),
    UNIQUE (tenant_id, deployment_id, slug)
);

CREATE TABLE screen_groups (
    screen_group_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, deployment_id, site_id, screen_group_id),
    UNIQUE (tenant_id, deployment_id, site_id, slug),
    FOREIGN KEY (tenant_id, deployment_id, site_id)
        REFERENCES sites(tenant_id, deployment_id, site_id) ON DELETE RESTRICT
);

CREATE TABLE screen_instances (
    screen_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    screen_group_id TEXT,
    slug TEXT NOT NULL,
    display_name TEXT NOT NULL,
    fvs_binding_ref TEXT,
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state = 'ACTIVE'),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (tenant_id, deployment_id, site_id, screen_id),
    UNIQUE (tenant_id, deployment_id, site_id, slug),
    FOREIGN KEY (tenant_id, deployment_id, site_id)
        REFERENCES sites(tenant_id, deployment_id, site_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, site_id, screen_group_id)
        REFERENCES screen_groups(tenant_id, deployment_id, site_id, screen_group_id)
        ON DELETE RESTRICT
);

CREATE TABLE digital_human_instances (
    digital_human_instance_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'ACTIVE'),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ),
    FOREIGN KEY (tenant_id, deployment_id, site_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, site_id, screen_id)
        ON DELETE RESTRICT
);
CREATE UNIQUE INDEX idx_digital_human_active_screen
    ON digital_human_instances(tenant_id, deployment_id, screen_id)
    WHERE status = 'ACTIVE';

CREATE TABLE runtime_bindings (
    screen_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    digital_human_instance_id TEXT,
    desired_release_target_id TEXT,
    applied_release_target_id TEXT,
    binding_generation INTEGER NOT NULL DEFAULT 0 CHECK (binding_generation = 0),
    last_acknowledged_marker TEXT,
    last_acknowledged_at REAL,
    inventory_status TEXT NOT NULL CHECK (
        inventory_status IN ('INVENTORY_INCOMPLETE', 'NOT_CONFIGURED_P1_3')
    ),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE (
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ),
    FOREIGN KEY (tenant_id, deployment_id, site_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, site_id, screen_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ) REFERENCES digital_human_instances(
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ) ON DELETE RESTRICT,
    CHECK (
        desired_release_target_id IS NULL
        AND applied_release_target_id IS NULL
        AND last_acknowledged_marker IS NULL
        AND last_acknowledged_at IS NULL
    ),
    CHECK (
        (digital_human_instance_id IS NULL AND inventory_status = 'INVENTORY_INCOMPLETE')
        OR (
            digital_human_instance_id IS NOT NULL
            AND inventory_status = 'NOT_CONFIGURED_P1_3'
        )
    )
);

CREATE TABLE list_snapshots (
    cursor_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    principal_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    resource_kind TEXT NOT NULL CHECK (
        resource_kind IN ('SITE', 'SCREEN_GROUP', 'SCREEN_INSTANCE')
    ),
    ordered_ids_json TEXT NOT NULL,
    page_offset INTEGER NOT NULL CHECK (page_offset >= 0),
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX idx_list_snapshots_expiry ON list_snapshots(expires_at);

CREATE TRIGGER device_enrollments_inventory_insert
BEFORE INSERT ON device_enrollments
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM screen_instances s
        WHERE s.tenant_id = NEW.tenant_id
          AND s.deployment_id = NEW.deployment_id
          AND s.screen_id = NEW.screen_id
    ) THEN RAISE(ABORT, 'device enrollment screen ownership mismatch') END;
END;

CREATE TRIGGER device_enrollments_inventory_update
BEFORE UPDATE OF tenant_id, deployment_id, screen_id ON device_enrollments
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM screen_instances s
        WHERE s.tenant_id = NEW.tenant_id
          AND s.deployment_id = NEW.deployment_id
          AND s.screen_id = NEW.screen_id
    ) THEN RAISE(ABORT, 'device enrollment screen ownership mismatch') END;
END;

CREATE TRIGGER device_families_inventory_insert
BEFORE INSERT ON device_credential_families
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM screen_instances s
        WHERE s.tenant_id = NEW.tenant_id
          AND s.deployment_id = NEW.deployment_id
          AND s.screen_id = NEW.screen_id
    ) THEN RAISE(ABORT, 'device family screen ownership mismatch') END;
END;

CREATE TRIGGER device_families_inventory_update
BEFORE UPDATE OF tenant_id, deployment_id, screen_id ON device_credential_families
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM screen_instances s
        WHERE s.tenant_id = NEW.tenant_id
          AND s.deployment_id = NEW.deployment_id
          AND s.screen_id = NEW.screen_id
    ) THEN RAISE(ABORT, 'device family screen ownership mismatch') END;
END;
"""

MIGRATION_002_CHECKSUM_SHA256 = hashlib.sha256(INVENTORY_SCHEMA_SQL.encode("utf-8")).hexdigest()

PUBLISH_RECOVERY_SCHEMA_SQL = """
CREATE UNIQUE INDEX idx_screen_instances_tenant_deployment_screen
    ON screen_instances(tenant_id, deployment_id, screen_id);
CREATE UNIQUE INDEX idx_screen_groups_tenant_deployment_group
    ON screen_groups(tenant_id, deployment_id, screen_group_id);

CREATE TABLE config_drafts (
    draft_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('SCREEN', 'SCREEN_GROUP')),
    screen_id TEXT,
    screen_group_id TEXT,
    schema_version TEXT NOT NULL CHECK (schema_version = 'p1_screen_config_v1'),
    working_spec_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN (
            'DRAFT', 'VALIDATED', 'PREVIEWED', 'APPROVAL_PENDING',
            'APPROVED', 'REJECTED', 'RELEASED', 'ABANDONED'
        )
    ),
    current_revision INTEGER NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    last_editor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    validation_record_id TEXT,
    preview_record_id TEXT,
    approval_record_id TEXT,
    control_plane_epoch INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    CHECK (
        (
            target_type = 'SCREEN'
            AND screen_id IS NOT NULL
            AND screen_group_id IS NULL
        )
        OR (
            target_type = 'SCREEN_GROUP'
            AND screen_id IS NULL
            AND screen_group_id IS NOT NULL
        )
    ),
    UNIQUE (tenant_id, deployment_id, draft_id),
    FOREIGN KEY (tenant_id, deployment_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, screen_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, screen_group_id)
        REFERENCES screen_groups(tenant_id, deployment_id, screen_group_id)
        ON DELETE RESTRICT
);

CREATE TABLE config_draft_revisions (
    draft_id TEXT NOT NULL REFERENCES config_drafts(draft_id) ON DELETE RESTRICT,
    draft_revision INTEGER NOT NULL CHECK (draft_revision >= 1),
    schema_version TEXT NOT NULL CHECK (schema_version = 'p1_screen_config_v1'),
    canonical_spec_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    PRIMARY KEY (draft_id, draft_revision)
);

CREATE TABLE resolution_fingerprints (
    fingerprint_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    fingerprint_hash TEXT NOT NULL UNIQUE,
    target_set_json TEXT NOT NULL,
    target_set_hash TEXT NOT NULL,
    group_revision INTEGER,
    resolution_inputs_json TEXT NOT NULL,
    effective_hashes_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (fingerprint_id, draft_id, draft_revision),
    FOREIGN KEY (draft_id, draft_revision)
        REFERENCES config_draft_revisions(draft_id, draft_revision)
        ON DELETE RESTRICT
);

CREATE TABLE validation_records (
    validation_record_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    fingerprint_id TEXT,
    fingerprint_hash TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('VALID', 'INVALID')),
    findings_json TEXT NOT NULL,
    findings_hash TEXT NOT NULL,
    validator_version TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    CHECK (
        (outcome = 'VALID' AND fingerprint_id IS NOT NULL AND fingerprint_hash IS NOT NULL)
        OR (outcome = 'INVALID' AND fingerprint_id IS NULL AND fingerprint_hash IS NULL)
    ),
    UNIQUE (validation_record_id, draft_id, draft_revision),
    FOREIGN KEY (fingerprint_id, draft_id, draft_revision)
        REFERENCES resolution_fingerprints(
            fingerprint_id, draft_id, draft_revision
        ) ON DELETE RESTRICT
);

CREATE TABLE preview_records (
    preview_record_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    validation_record_id TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome = 'MOCK_PASSED'),
    evidence_json TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    UNIQUE (preview_record_id, draft_id, draft_revision),
    FOREIGN KEY (validation_record_id, draft_id, draft_revision)
        REFERENCES validation_records(
            validation_record_id, draft_id, draft_revision
        ) ON DELETE RESTRICT
);

CREATE TABLE config_approval_records (
    approval_record_id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    preview_record_id TEXT NOT NULL,
    fingerprint_hash TEXT NOT NULL,
    control_plane_epoch INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
    approver_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    last_editor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL,
    CHECK (approver_user_id != last_editor_user_id),
    UNIQUE (approval_record_id, draft_id, draft_revision),
    FOREIGN KEY (preview_record_id, draft_id, draft_revision)
        REFERENCES preview_records(
            preview_record_id, draft_id, draft_revision
        ) ON DELETE RESTRICT
);

CREATE TABLE config_releases (
    release_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    release_sequence INTEGER NOT NULL CHECK (release_sequence >= 1),
    creation_kind TEXT NOT NULL CHECK (creation_kind IN ('NORMAL', 'ROLLBACK')),
    schema_version TEXT NOT NULL CHECK (schema_version = 'p1_screen_config_v1'),
    normal_draft_id TEXT,
    normal_draft_revision INTEGER,
    normal_fingerprint_id TEXT,
    normal_approval_record_id TEXT,
    rollback_source_map_json TEXT,
    rollback_source_map_hash TEXT,
    rollback_high_risk_action_id TEXT,
    target_set_hash TEXT NOT NULL,
    group_revision INTEGER,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL,
    CHECK (
        (
            creation_kind = 'NORMAL'
            AND normal_draft_id IS NOT NULL
            AND normal_draft_revision IS NOT NULL
            AND normal_fingerprint_id IS NOT NULL
            AND normal_approval_record_id IS NOT NULL
            AND rollback_source_map_json IS NULL
            AND rollback_source_map_hash IS NULL
            AND rollback_high_risk_action_id IS NULL
        )
        OR (
            creation_kind = 'ROLLBACK'
            AND normal_draft_id IS NULL
            AND normal_draft_revision IS NULL
            AND normal_fingerprint_id IS NULL
            AND normal_approval_record_id IS NULL
            AND rollback_source_map_json IS NOT NULL
            AND rollback_source_map_hash IS NOT NULL
            AND rollback_high_risk_action_id IS NOT NULL
        )
    ),
    UNIQUE (tenant_id, deployment_id, release_id),
    UNIQUE (tenant_id, deployment_id, release_sequence),
    FOREIGN KEY (normal_fingerprint_id, normal_draft_id, normal_draft_revision)
        REFERENCES resolution_fingerprints(
            fingerprint_id, draft_id, draft_revision
        ) ON DELETE RESTRICT,
    FOREIGN KEY (
        normal_approval_record_id, normal_draft_id, normal_draft_revision
    ) REFERENCES config_approval_records(
        approval_record_id, draft_id, draft_revision
    ) ON DELETE RESTRICT,
    FOREIGN KEY (rollback_high_risk_action_id)
        REFERENCES high_risk_actions(high_risk_action_id) ON DELETE RESTRICT
);

CREATE TABLE release_targets (
    release_target_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    canonical_effective_config_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    rollback_source_release_id TEXT,
    rollback_source_target_id TEXT,
    created_at REAL NOT NULL,
    CHECK (
        (
            rollback_source_release_id IS NULL
            AND rollback_source_target_id IS NULL
        )
        OR (
            rollback_source_release_id IS NOT NULL
            AND rollback_source_target_id IS NOT NULL
        )
    ),
    UNIQUE (release_id, screen_id),
    UNIQUE (
        tenant_id, deployment_id, screen_id, release_target_id
    ),
    UNIQUE (
        tenant_id, deployment_id, release_id, release_target_id, screen_id
    ),
    FOREIGN KEY (tenant_id, deployment_id, release_id)
        REFERENCES config_releases(tenant_id, deployment_id, release_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, screen_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, screen_id, rollback_source_target_id
    ) REFERENCES release_targets(
        tenant_id, deployment_id, screen_id, release_target_id
    ) ON DELETE RESTRICT
);

ALTER TABLE runtime_bindings RENAME TO runtime_bindings_p1_2;

CREATE TABLE runtime_bindings (
    screen_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    digital_human_instance_id TEXT,
    desired_release_target_id TEXT,
    applied_release_target_id TEXT,
    binding_generation INTEGER NOT NULL DEFAULT 0 CHECK (binding_generation >= 0),
    last_acknowledged_marker TEXT,
    last_acknowledged_at REAL,
    inventory_status TEXT NOT NULL CHECK (
        inventory_status IN (
            'INVENTORY_INCOMPLETE', 'NOT_CONFIGURED_P1_3',
            'PUBLISH_PENDING', 'ACTIVE'
        )
    ),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    UNIQUE (
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ),
    FOREIGN KEY (tenant_id, deployment_id, site_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, site_id, screen_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ) REFERENCES digital_human_instances(
        tenant_id, deployment_id, site_id, screen_id, digital_human_instance_id
    ) ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, screen_id, desired_release_target_id
    ) REFERENCES release_targets(
        tenant_id, deployment_id, screen_id, release_target_id
    ) ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, screen_id, applied_release_target_id
    ) REFERENCES release_targets(
        tenant_id, deployment_id, screen_id, release_target_id
    ) ON DELETE RESTRICT,
    CHECK (
        (
            digital_human_instance_id IS NULL
            AND inventory_status = 'INVENTORY_INCOMPLETE'
            AND desired_release_target_id IS NULL
            AND applied_release_target_id IS NULL
            AND binding_generation = 0
            AND last_acknowledged_marker IS NULL
            AND last_acknowledged_at IS NULL
        )
        OR (
            digital_human_instance_id IS NOT NULL
            AND (
                (
                    inventory_status = 'NOT_CONFIGURED_P1_3'
                    AND desired_release_target_id IS NULL
                    AND applied_release_target_id IS NULL
                    AND binding_generation = 0
                    AND last_acknowledged_marker IS NULL
                    AND last_acknowledged_at IS NULL
                )
                OR (
                    inventory_status = 'PUBLISH_PENDING'
                    AND desired_release_target_id IS NOT NULL
                    AND desired_release_target_id IS NOT applied_release_target_id
                    AND binding_generation >= 1
                )
                OR (
                    inventory_status = 'ACTIVE'
                    AND desired_release_target_id IS NOT NULL
                    AND desired_release_target_id = applied_release_target_id
                    AND binding_generation >= 1
                    AND last_acknowledged_marker IS NOT NULL
                    AND last_acknowledged_at IS NOT NULL
                )
            )
        )
    )
);

INSERT INTO runtime_bindings(
    screen_id, tenant_id, deployment_id, site_id,
    digital_human_instance_id, desired_release_target_id,
    applied_release_target_id, binding_generation,
    last_acknowledged_marker, last_acknowledged_at,
    inventory_status, created_at, updated_at, revision
)
SELECT
    screen_id, tenant_id, deployment_id, site_id,
    digital_human_instance_id, desired_release_target_id,
    applied_release_target_id, binding_generation,
    last_acknowledged_marker, last_acknowledged_at,
    inventory_status, created_at, updated_at, revision
FROM runtime_bindings_p1_2;

DROP TABLE runtime_bindings_p1_2;

CREATE TABLE publications (
    publication_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    screen_group_id TEXT,
    target_set_hash TEXT NOT NULL,
    group_revision INTEGER,
    actor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    high_risk_action_id TEXT NOT NULL
        REFERENCES high_risk_actions(high_risk_action_id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('SUCCEEDED', 'PARTIAL_FAILURE', 'FAILED', 'CANCELLED')
    ),
    created_at REAL NOT NULL,
    UNIQUE (tenant_id, deployment_id, publication_id),
    FOREIGN KEY (tenant_id, deployment_id, release_id)
        REFERENCES config_releases(tenant_id, deployment_id, release_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, screen_group_id)
        REFERENCES screen_groups(tenant_id, deployment_id, screen_group_id)
        ON DELETE RESTRICT
);

CREATE TABLE publication_targets (
    publication_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    release_target_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    expected_runtime_revision INTEGER NOT NULL CHECK (expected_runtime_revision >= 1),
    expected_binding_generation INTEGER NOT NULL CHECK (expected_binding_generation >= 0),
    state TEXT NOT NULL CHECK (
        state IN (
            'QUEUED', 'WAITING_FOR_DEVICE', 'APPLYING',
            'ACTIVE', 'SUPERSEDED', 'FAILED', 'CANCELLED'
        )
    ),
    failure_code TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    PRIMARY KEY (publication_id, screen_id),
    FOREIGN KEY (tenant_id, deployment_id, publication_id)
        REFERENCES publications(tenant_id, deployment_id, publication_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (
        tenant_id, deployment_id, release_id, release_target_id, screen_id
    ) REFERENCES release_targets(
        tenant_id, deployment_id, release_id, release_target_id, screen_id
    ) ON DELETE RESTRICT
);

CREATE INDEX idx_publication_targets_release_target
    ON publication_targets(release_target_id, state);

CREATE TABLE runtime_binding_history (
    history_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    screen_id TEXT NOT NULL,
    publication_id TEXT,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('DESIRED_CHANGED', 'APPLIED_ACKNOWLEDGED')
    ),
    old_desired_release_target_id TEXT,
    new_desired_release_target_id TEXT,
    old_applied_release_target_id TEXT,
    new_applied_release_target_id TEXT,
    binding_generation INTEGER NOT NULL CHECK (binding_generation >= 1),
    actor_type TEXT NOT NULL CHECK (actor_type IN ('USER', 'DEVICE')),
    actor_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (tenant_id, deployment_id, publication_id)
        REFERENCES publications(tenant_id, deployment_id, publication_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, site_id, screen_id)
        REFERENCES screen_instances(tenant_id, deployment_id, site_id, screen_id)
        ON DELETE RESTRICT
);

CREATE TABLE backup_records (
    backup_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('VERIFIED', 'FAILED')),
    bundle_name TEXT NOT NULL UNIQUE,
    manifest_hash TEXT NOT NULL UNIQUE,
    ciphertext_hash TEXT NOT NULL,
    recovery_encryption_key_id TEXT NOT NULL,
    logical_schema_version TEXT NOT NULL,
    migration_versions_json TEXT NOT NULL,
    safe_row_counts_json TEXT NOT NULL,
    audit_head_hash TEXT,
    ciphertext_size INTEGER NOT NULL CHECK (ciphertext_size >= 0),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    reason TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    verified_at REAL,
    UNIQUE (tenant_id, deployment_id, backup_id)
);

CREATE TABLE restore_plans (
    restore_plan_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    backup_id TEXT NOT NULL,
    backup_manifest_hash TEXT NOT NULL,
    recovery_source_mode TEXT NOT NULL CHECK (
        recovery_source_mode = 'ONLINE_ACTIVE_STORE'
    ),
    authorization_mode TEXT NOT NULL CHECK (
        authorization_mode = 'STANDARD_HIGH_RISK'
    ),
    expected_metadata_revision INTEGER NOT NULL CHECK (expected_metadata_revision >= 1),
    findings_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('READY', 'EXECUTED', 'ABORTED', 'FAILED')
    ),
    created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    UNIQUE (tenant_id, deployment_id, restore_plan_id),
    FOREIGN KEY (tenant_id, deployment_id, backup_id)
        REFERENCES backup_records(tenant_id, deployment_id, backup_id)
        ON DELETE RESTRICT
);

CREATE TABLE restore_executions (
    restore_execution_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    deployment_id TEXT NOT NULL,
    restore_plan_id TEXT NOT NULL,
    backup_id TEXT NOT NULL,
    high_risk_action_id TEXT NOT NULL,
    retained_previous_store_name TEXT NOT NULL,
    restored_runtime_binding_hash TEXT NOT NULL,
    reconciled_security_hash TEXT NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    result TEXT NOT NULL CHECK (result = 'COMPLETED'),
    created_at REAL NOT NULL,
    FOREIGN KEY (tenant_id, deployment_id, restore_plan_id)
        REFERENCES restore_plans(tenant_id, deployment_id, restore_plan_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, deployment_id, backup_id)
        REFERENCES backup_records(tenant_id, deployment_id, backup_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (high_risk_action_id)
        REFERENCES high_risk_actions(high_risk_action_id) ON DELETE RESTRICT
);

CREATE TABLE retention_runs (
    retention_run_id TEXT PRIMARY KEY,
    retention_days INTEGER NOT NULL CHECK (retention_days >= 1),
    deleted_runtime_detail_count INTEGER NOT NULL CHECK (
        deleted_runtime_detail_count >= 0
    ),
    protected_control_plane_counts_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TRIGGER config_draft_revisions_no_update
BEFORE UPDATE ON config_draft_revisions
BEGIN
    SELECT RAISE(ABORT, 'config draft revisions are immutable');
END;

CREATE TRIGGER config_draft_revisions_no_delete
BEFORE DELETE ON config_draft_revisions
BEGIN
    SELECT RAISE(ABORT, 'config draft revisions are immutable');
END;

CREATE TRIGGER resolution_fingerprints_no_update
BEFORE UPDATE ON resolution_fingerprints
BEGIN
    SELECT RAISE(ABORT, 'resolution fingerprints are immutable');
END;

CREATE TRIGGER resolution_fingerprints_no_delete
BEFORE DELETE ON resolution_fingerprints
BEGIN
    SELECT RAISE(ABORT, 'resolution fingerprints are immutable');
END;

CREATE TRIGGER validation_records_no_update
BEFORE UPDATE ON validation_records
BEGIN
    SELECT RAISE(ABORT, 'validation records are immutable');
END;

CREATE TRIGGER validation_records_no_delete
BEFORE DELETE ON validation_records
BEGIN
    SELECT RAISE(ABORT, 'validation records are immutable');
END;

CREATE TRIGGER preview_records_no_update
BEFORE UPDATE ON preview_records
BEGIN
    SELECT RAISE(ABORT, 'preview records are immutable');
END;

CREATE TRIGGER preview_records_no_delete
BEFORE DELETE ON preview_records
BEGIN
    SELECT RAISE(ABORT, 'preview records are immutable');
END;

CREATE TRIGGER config_approval_records_no_update
BEFORE UPDATE ON config_approval_records
BEGIN
    SELECT RAISE(ABORT, 'config approval records are immutable');
END;

CREATE TRIGGER config_approval_records_no_delete
BEFORE DELETE ON config_approval_records
BEGIN
    SELECT RAISE(ABORT, 'config approval records are immutable');
END;

CREATE TRIGGER config_releases_no_update
BEFORE UPDATE ON config_releases
BEGIN
    SELECT RAISE(ABORT, 'config releases are immutable');
END;

CREATE TRIGGER config_releases_no_delete
BEFORE DELETE ON config_releases
BEGIN
    SELECT RAISE(ABORT, 'config releases are immutable');
END;

CREATE TRIGGER release_targets_no_update
BEFORE UPDATE ON release_targets
BEGIN
    SELECT RAISE(ABORT, 'release targets are immutable');
END;

CREATE TRIGGER release_targets_no_delete
BEFORE DELETE ON release_targets
BEGIN
    SELECT RAISE(ABORT, 'release targets are immutable');
END;

CREATE TRIGGER publications_plan_fields_immutable
BEFORE UPDATE OF
    release_id, screen_group_id, target_set_hash, group_revision,
    actor_user_id, high_risk_action_id, reason, created_at
ON publications
BEGIN
    SELECT RAISE(ABORT, 'publication plans are immutable');
END;

CREATE TRIGGER publications_no_delete
BEFORE DELETE ON publications
BEGIN
    SELECT RAISE(ABORT, 'publication plans are immutable');
END;

CREATE TRIGGER runtime_binding_history_no_update
BEFORE UPDATE ON runtime_binding_history
BEGIN
    SELECT RAISE(ABORT, 'runtime binding history is immutable');
END;

CREATE TRIGGER runtime_binding_history_no_delete
BEFORE DELETE ON runtime_binding_history
BEGIN
    SELECT RAISE(ABORT, 'runtime binding history is immutable');
END;

CREATE TRIGGER backup_records_no_delete
BEFORE DELETE ON backup_records
BEGIN
    SELECT RAISE(ABORT, 'backup records are retained');
END;

CREATE TRIGGER restore_executions_no_update
BEFORE UPDATE ON restore_executions
BEGIN
    SELECT RAISE(ABORT, 'restore executions are immutable');
END;

CREATE TRIGGER restore_executions_no_delete
BEFORE DELETE ON restore_executions
BEGIN
    SELECT RAISE(ABORT, 'restore executions are immutable');
END;
"""

MIGRATION_003_CHECKSUM_SHA256 = hashlib.sha256(PUBLISH_RECOVERY_SCHEMA_SQL.encode("utf-8")).hexdigest()
MIGRATIONS = (
    (MIGRATION_001_VERSION, MIGRATION_001_CHECKSUM_SHA256, SCHEMA_SQL),
    (MIGRATION_002_VERSION, MIGRATION_002_CHECKSUM_SHA256, INVENTORY_SCHEMA_SQL),
    (
        MIGRATION_003_VERSION,
        MIGRATION_003_CHECKSUM_SHA256,
        PUBLISH_RECOVERY_SCHEMA_SQL,
    ),
)
MIGRATION_VERSION = MIGRATION_003_VERSION
MIGRATION_CHECKSUM_SHA256 = MIGRATION_003_CHECKSUM_SHA256


class ControlPlaneStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.mutation_lock = threading.RLock()

    def initialize(self, now: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                migration_table = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'schema_migrations'
                    """
                ).fetchone()
                if migration_table is None:
                    existing_objects = connection.execute(
                        """
                        SELECT type, name FROM sqlite_master
                        WHERE name NOT LIKE 'sqlite_%'
                        ORDER BY type, name
                        """
                    ).fetchall()
                    if existing_objects:
                        raise RuntimeError("Existing control-plane schema is missing the migration registry")
                    self._execute_script(connection, SCHEMA_MIGRATIONS_SQL)
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(schema_migrations)").fetchall()
                }
                if columns != {"version", "checksum_sha256", "applied_at"}:
                    raise RuntimeError(
                        "Unsupported pre-candidate P1.1 database; archive it and initialize a fresh preview"
                    )
                applied = connection.execute(
                    "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
                ).fetchall()
                if not applied:
                    existing_objects = connection.execute(
                        """
                        SELECT type, name FROM sqlite_master
                        WHERE name NOT LIKE 'sqlite_%' AND name != 'schema_migrations'
                        ORDER BY type, name
                        """
                    ).fetchall()
                    if existing_objects:
                        raise RuntimeError("Existing control-plane schema is missing the migration registry")
                if len(applied) > len(MIGRATIONS):
                    raise RuntimeError("Unknown control-plane migration registry")
                for index, row in enumerate(applied):
                    expected_version, expected_checksum, _ = MIGRATIONS[index]
                    if row["version"] != expected_version:
                        raise RuntimeError(f"Control-plane migration registry mismatch: {row['version']}")
                    if row["checksum_sha256"] != expected_checksum:
                        raise RuntimeError("Control-plane migration checksum mismatch")
                for version, checksum, script in MIGRATIONS[len(applied) :]:
                    self._execute_script(connection, script)
                    if version == MIGRATION_002_VERSION:
                        self._backfill_preview_inventory(connection, now)
                    if version == MIGRATION_003_VERSION:
                        self._append_p13_migration_audit(connection, now)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations(version, checksum_sha256, applied_at)
                        VALUES (?, ?, ?)
                        """,
                        (version, checksum, now),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def backfill_preview_inventory(
        self,
        connection: sqlite3.Connection,
        now: float,
    ) -> dict[str, object] | None:
        return self._backfill_preview_inventory(connection, now)

    @staticmethod
    def _execute_script(connection: sqlite3.Connection, script: str) -> None:
        statement = ""
        for line in script.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                sql = statement.strip()
                if sql:
                    connection.execute(sql)
                statement = ""
        if statement.strip():
            raise RuntimeError("Incomplete control-plane migration statement")

    def _backfill_preview_inventory(
        self,
        connection: sqlite3.Connection,
        now: float,
    ) -> dict[str, object] | None:
        metadata = connection.execute("SELECT * FROM control_plane_metadata WHERE singleton = 1").fetchone()
        if metadata is None:
            return None
        existing = connection.execute(
            """
            SELECT screen_id FROM screen_instances
            WHERE tenant_id = ? AND deployment_id = ?
            ORDER BY slug, screen_id
            """,
            (metadata["tenant_id"], metadata["deployment_id"]),
        ).fetchall()
        if existing:
            fixture = connection.execute(
                """
                SELECT screen_id FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (
                    metadata["tenant_id"],
                    metadata["deployment_id"],
                    metadata["fixture_screen_id"],
                ),
            ).fetchone()
            if fixture is None:
                raise RuntimeError("P1.2 inventory does not preserve the accepted fixture screen")
            return {
                "site_id": connection.execute(
                    """
                    SELECT site_id FROM screen_instances
                    WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                    """,
                    (
                        metadata["tenant_id"],
                        metadata["deployment_id"],
                        metadata["fixture_screen_id"],
                    ),
                ).fetchone()["site_id"],
                "screen_ids": [row["screen_id"] for row in existing],
                "created": False,
            }

        fixture_screen_id = metadata["fixture_screen_id"]
        if not fixture_screen_id:
            raise RuntimeError("P1.2 migration requires the accepted P1.1 fixture screen ID")
        for table in ("device_enrollments", "device_credential_families"):
            mismatch = connection.execute(
                f"""
                SELECT 1 FROM {table}
                WHERE tenant_id != ? OR deployment_id != ? OR screen_id != ?
                LIMIT 1
                """,
                (metadata["tenant_id"], metadata["deployment_id"], fixture_screen_id),
            ).fetchone()
            if mismatch is not None:
                raise RuntimeError("P1.1 device history ownership mismatch blocks P1.2 migration")

        site_id = uuid7()
        group_id = uuid7()
        screen_ids = (fixture_screen_id, uuid7(), uuid7())
        connection.execute(
            """
            INSERT INTO sites(
                site_id, tenant_id, deployment_id, slug, display_name, timezone,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, 'site-default', '默认站点', 'Asia/Shanghai', 'ACTIVE', ?, ?)
            """,
            (site_id, metadata["tenant_id"], metadata["deployment_id"], now, now),
        )
        connection.execute(
            """
            INSERT INTO screen_groups(
                screen_group_id, tenant_id, deployment_id, site_id, slug,
                display_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'group-main', '默认大屏组', ?, ?)
            """,
            (
                group_id,
                metadata["tenant_id"],
                metadata["deployment_id"],
                site_id,
                now,
                now,
            ),
        )
        digital_human_ids: list[str] = []
        for number, screen_id in enumerate(screen_ids, start=1):
            digital_human_id = uuid7()
            digital_human_ids.append(digital_human_id)
            connection.execute(
                """
                INSERT INTO screen_instances(
                    screen_id, tenant_id, deployment_id, site_id, screen_group_id,
                    slug, display_name, fvs_binding_ref, lifecycle_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (
                    screen_id,
                    metadata["tenant_id"],
                    metadata["deployment_id"],
                    site_id,
                    group_id,
                    f"screen-{number}",
                    f"大屏 {number}",
                    f"fvs-inventory-screen-{number}",
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO digital_human_instances(
                    digital_human_instance_id, tenant_id, deployment_id,
                    site_id, screen_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (
                    digital_human_id,
                    metadata["tenant_id"],
                    metadata["deployment_id"],
                    site_id,
                    screen_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO runtime_bindings(
                    screen_id, tenant_id, deployment_id, site_id,
                    digital_human_instance_id, inventory_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'NOT_CONFIGURED_P1_3', ?, ?)
                """,
                (
                    screen_id,
                    metadata["tenant_id"],
                    metadata["deployment_id"],
                    site_id,
                    digital_human_id,
                    now,
                    now,
                ),
            )
        self._append_inventory_migration_audit(
            connection,
            deployment_id=metadata["deployment_id"],
            fixture_screen_id=fixture_screen_id,
            site_id=site_id,
            screen_count=3,
            now=now,
        )
        return {
            "site_id": site_id,
            "screen_group_id": group_id,
            "screen_ids": list(screen_ids),
            "digital_human_instance_ids": digital_human_ids,
            "created": True,
        }

    @staticmethod
    def _append_inventory_migration_audit(
        connection: sqlite3.Connection,
        *,
        deployment_id: str,
        fixture_screen_id: str,
        site_id: str,
        screen_count: int,
        now: float,
    ) -> None:
        previous = connection.execute(
            "SELECT event_hash FROM security_audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_id = uuid7()
        details = {
            "migration_version": MIGRATION_002_VERSION,
            "preserved_fixture_screen_id": fixture_screen_id,
            "site_id": site_id,
            "screen_count": screen_count,
        }
        payload = canonical_json(
            {
                "event_id": event_id,
                "event_type": "THREE_SCREEN_INVENTORY_MIGRATED",
                "actor_type": "LOCAL_MIGRATION",
                "actor_id": None,
                "target_type": "DEPLOYMENT",
                "target_id": deployment_id,
                "outcome": "SUCCESS",
                "reason": "named forward migration",
                "details": details,
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
            ) VALUES (?, 'THREE_SCREEN_INVENTORY_MIGRATED', 'LOCAL_MIGRATION', NULL,
                'DEPLOYMENT', ?, 'SUCCESS', 'named forward migration', ?, ?, ?,
                'p1_security_audit_event_hash_v1', ?)
            """,
            (
                event_id,
                deployment_id,
                json.dumps(details, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                previous_hash,
                event_hash,
                now,
            ),
        )

    @staticmethod
    def _append_p13_migration_audit(
        connection: sqlite3.Connection,
        now: float,
    ) -> None:
        metadata = connection.execute("SELECT * FROM control_plane_metadata WHERE singleton = 1").fetchone()
        if metadata is None:
            return
        previous = connection.execute(
            "SELECT event_hash FROM security_audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else None
        event_id = uuid7()
        details = {
            "migration_version": MIGRATION_003_VERSION,
            "preserved_screen_count": connection.execute(
                """
                SELECT COUNT(*) AS count FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ?
                """,
                (metadata["tenant_id"], metadata["deployment_id"]),
            ).fetchone()["count"],
            "runtime_bindings_enabled_for_release": True,
        }
        payload = canonical_json(
            {
                "event_id": event_id,
                "event_type": "PUBLISH_ROLLBACK_RECOVERY_SCHEMA_MIGRATED",
                "actor_type": "LOCAL_MIGRATION",
                "actor_id": None,
                "target_type": "DEPLOYMENT",
                "target_id": metadata["deployment_id"],
                "outcome": "SUCCESS",
                "reason": "named forward migration",
                "details": details,
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
            ) VALUES (
                ?, 'PUBLISH_ROLLBACK_RECOVERY_SCHEMA_MIGRATED',
                'LOCAL_MIGRATION', NULL, 'DEPLOYMENT', ?, 'SUCCESS',
                'named forward migration', ?, ?, ?,
                'p1_security_audit_event_hash_v1', ?
            )
            """,
            (
                event_id,
                metadata["deployment_id"],
                json.dumps(
                    details,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                previous_hash,
                event_hash,
                now,
            ),
        )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.mutation_lock:
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
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection
