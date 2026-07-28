from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
from pathlib import Path
from time import perf_counter
from typing import Any

from app.control_plane.errors import ControlPlaneError
from app.control_plane.recovery import BackupIntegrityError, BackupManager
from app.control_plane.security import canonical_json, opaque_id
from app.control_plane.store import LOGICAL_SCHEMA_VERSION, MIGRATIONS, ControlPlaneStore

CONFIG_SCHEMA_VERSION = "p1_screen_config_v1"
CONFIG_FIELDS = {"welcome_text", "fvs_binding_ref"}
LEGAL_REVISE_STATES = {
    "VALIDATED",
    "PREVIEWED",
    "APPROVAL_PENDING",
    "REJECTED",
}
LEGAL_ABANDON_STATES = {"DRAFT", "VALIDATED", "PREVIEWED", "REJECTED"}
SECURITY_RECONCILIATION_TABLES = (
    "users",
    "role_assignments",
    "device_enrollments",
    "device_credential_families",
    "device_credentials",
    "high_risk_actions",
    "backup_records",
    "restore_plans",
    "restore_executions",
    "query_secret_records",
    "query_sources",
    "query_datasets",
)
LIVE_RECONCILED_IDEMPOTENCY_PHASES = (
    "approveHighRiskAction",
    "claimDeviceEnrollment",
    "createBackup",
    "createRestorePlan",
    "execute:issueDeviceEnrollment",
    "rejectHighRiskAction",
    "request:createUser",
    "request:executeRestorePlan",
    "request:issueDeviceEnrollment",
    "request:revokeDeviceCredential",
    "rotateDeviceCredential",
    "verifyBackup",
)
SESSION_IDEMPOTENCY_PHASES = ("reauthenticateAuthSession",)
RESTORE_INVALIDATED_DOMAIN_ACTIONS = (
    "publishToScreen",
    "publishToScreenGroup",
    "rollbackScreen",
    "rollbackScreenGroup",
)


class DraftValidationFailure(ControlPlaneError):
    def __init__(self, finding_code: str, message: str) -> None:
        super().__init__(422, "SCHEMA_VALIDATION_FAILED", message)
        self.finding_code = finding_code


class P13ControlPlane:
    def __init__(self, owner: Any, backup_root: str | Path) -> None:
        self.owner = owner
        self.backups = BackupManager(owner.store, owner.keys, backup_root)
        self._backup_lock = threading.RLock()
        self._restore_lock = threading.RLock()

    # Draft and immutable release lifecycle.

    def create_config_draft(
        self,
        principal: Any,
        *,
        target_type: str,
        target_id: str,
        schema_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if schema_version != CONFIG_SCHEMA_VERSION:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Unsupported config schema")
        target_type = target_type.strip().upper()
        if target_type not in {"SCREEN", "SCREEN_GROUP"}:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Unsupported draft target")
        self._require_any_edit_permission(principal)
        command = {
            "target_type": target_type,
            "target_id": target_id,
            "schema_version": schema_version,
        }
        request_digest = self.owner._sensitive_request_digest("createConfigDraft", command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase="createConfigDraft",
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            screen_id: str | None = None
            screen_group_id: str | None = None
            if target_type == "SCREEN":
                screen = self.owner._screen_row(
                    connection,
                    principal,
                    target_id,
                    self._available_edit_permission(principal),
                )
                screen_id = screen["screen_id"]
            else:
                group = self._group_row(
                    connection,
                    principal,
                    target_id,
                    self._available_edit_permission(principal),
                )
                screen_group_id = group["screen_group_id"]
            metadata = self.owner._metadata(connection)
            draft_id = opaque_id("drf")
            empty_json = canonical_json({})
            connection.execute(
                """
                INSERT INTO config_drafts(
                    draft_id, tenant_id, deployment_id, target_type,
                    screen_id, screen_group_id, schema_version,
                    working_spec_json, content_hash, state, current_revision,
                    last_editor_user_id, control_plane_epoch,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', 0, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    target_type,
                    screen_id,
                    screen_group_id,
                    schema_version,
                    empty_json,
                    hashlib.sha256(empty_json.encode("utf-8")).hexdigest(),
                    principal.user_id,
                    metadata["revision"],
                    now,
                    now,
                ),
            )
            row = self._load_draft(connection, principal, draft_id, "config.read")
            result = self._draft_response(connection, row)
            self.owner._idempotency_store(
                connection,
                phase="createConfigDraft",
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            self.owner._append_audit(
                connection,
                event_type="CONFIG_DRAFT_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "target_type": target_type,
                    "target_id": target_id,
                    "schema_version": schema_version,
                },
                now=now,
            )
            return result

    def get_config_draft(self, principal: Any, draft_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            row = self._load_draft(connection, principal, draft_id, "config.read")
            return self._draft_response(connection, row)

    def replace_config_draft_spec(
        self,
        principal: Any,
        draft_id: str,
        *,
        spec: dict[str, Any],
        if_match: str,
    ) -> dict[str, Any]:
        self._require_any_edit_permission(principal)
        canonical_spec = self._validate_spec(spec)
        normalized_spec = json.loads(canonical_spec)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            draft = self._load_draft(
                connection,
                principal,
                draft_id,
                self._available_edit_permission(principal),
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] != "DRAFT":
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Draft content is editable only in DRAFT",
                )
            current_spec = json.loads(draft["working_spec_json"])
            changed_fields = sorted(
                field for field in CONFIG_FIELDS if current_spec.get(field) != normalized_spec[field]
            )
            required_permissions = {
                "welcome_text": "config.edit_business",
                "fvs_binding_ref": "config.edit_technical",
            }
            for field in changed_fields:
                self.owner.require_permission(principal, required_permissions[field])
            if not changed_fields:
                return self._draft_response(connection, draft)
            next_draft_revision = draft["current_revision"] + 1
            content_hash = hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO config_draft_revisions(
                    draft_id, draft_revision, schema_version,
                    canonical_spec_json, content_hash,
                    created_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    next_draft_revision,
                    CONFIG_SCHEMA_VERSION,
                    canonical_spec,
                    content_hash,
                    principal.user_id,
                    now,
                ),
            )
            self.owner.p2_1.copy_draft_assignment_forward(
                connection,
                draft_id=draft_id,
                source_revision=draft["current_revision"],
                target_revision=next_draft_revision,
            )
            self.owner.p2_2.copy_draft_assignment_forward(
                connection,
                draft_id=draft_id,
                source_revision=draft["current_revision"],
                target_revision=next_draft_revision,
            )
            connection.execute(
                """
                UPDATE config_drafts SET
                    working_spec_json = ?, content_hash = ?,
                    current_revision = ?, last_editor_user_id = ?,
                    validation_record_id = NULL, preview_record_id = NULL,
                    approval_record_id = NULL, updated_at = ?,
                    revision = revision + 1
                WHERE draft_id = ?
                """,
                (
                    canonical_spec,
                    content_hash,
                    next_draft_revision,
                    principal.user_id,
                    now,
                    draft_id,
                ),
            )
            self.owner._append_audit(
                connection,
                event_type="CONFIG_DRAFT_SPEC_REPLACED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "draft_revision": next_draft_revision,
                    "content_hash": content_hash,
                    "field_paths": [f"/{field}" for field in changed_fields],
                },
                now=now,
            )
            updated = self._load_draft(connection, principal, draft_id, "config.read")
            return self._draft_response(connection, updated)

    def validate_config_draft(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.validate")
        return self._record_validation_or_preview(
            principal,
            draft_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            phase="validateConfigDraft",
        )

    def preview_config_draft(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.preview")
        return self._record_validation_or_preview(
            principal,
            draft_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            phase="previewConfigDraft",
        )

    def submit_config_draft(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_all_spec_edit_permissions(principal)
        return self._simple_draft_transition(
            principal,
            draft_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            operation_id="submitConfigDraftApproval",
            expected_states={"PREVIEWED"},
            next_state="APPROVAL_PENDING",
            event_type="CONFIG_DRAFT_APPROVAL_SUBMITTED",
        )

    def decide_config_draft(
        self,
        context: Any,
        draft_id: str,
        *,
        decision: str,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(context.principal, "config.approve")
        self.owner._require_recent_reauthentication(context)
        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Invalid approval decision")
        reason = self._reason(reason)
        operation_id = "approveConfigDraft" if decision == "APPROVED" else "rejectConfigDraft"
        command = {
            "draft_id": draft_id,
            "decision": decision,
            "reason": reason,
            "if_match": if_match,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            draft = self._load_draft(
                connection,
                context.principal,
                draft_id,
                "config.approve",
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] != "APPROVAL_PENDING":
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Draft is not awaiting approval",
                )
            if draft["last_editor_user_id"] == context.principal.user_id:
                raise ControlPlaneError(
                    403,
                    "FORBIDDEN",
                    "The last content editor cannot approve the draft",
                )
            fingerprint = self._ensure_fingerprint_current(
                connection,
                context.principal,
                draft,
            )
            preview = connection.execute(
                """
                SELECT * FROM preview_records
                WHERE preview_record_id = ? AND draft_id = ?
                """,
                (draft["preview_record_id"], draft_id),
            ).fetchone()
            if preview is None:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Draft preview evidence is unavailable",
                )
            approval_id = opaque_id("apr")
            connection.execute(
                """
                INSERT INTO config_approval_records(
                    approval_record_id, draft_id, draft_revision,
                    preview_record_id, fingerprint_hash,
                    control_plane_epoch, decision, approver_user_id,
                    last_editor_user_id, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    draft_id,
                    draft["current_revision"],
                    preview["preview_record_id"],
                    fingerprint["fingerprint_hash"],
                    draft["control_plane_epoch"],
                    decision,
                    context.principal.user_id,
                    draft["last_editor_user_id"],
                    reason,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE config_drafts SET state = ?, approval_record_id = ?,
                    updated_at = ?, revision = revision + 1
                WHERE draft_id = ?
                """,
                (decision, approval_id, now, draft_id),
            )
            self.owner._append_audit(
                connection,
                event_type=f"CONFIG_DRAFT_{decision}",
                actor_type="USER",
                actor_id=context.principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome="APPROVED" if decision == "APPROVED" else "REJECTED",
                reason=reason,
                details={
                    "draft_revision": draft["current_revision"],
                    "fingerprint_hash": fingerprint["fingerprint_hash"],
                    "last_editor_user_id": draft["last_editor_user_id"],
                },
                now=now,
            )
            updated = self._load_draft(
                connection,
                context.principal,
                draft_id,
                "config.read",
            )
            result = self._draft_response(connection, updated)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=context.principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def revise_config_draft(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_all_spec_edit_permissions(principal)
        operation_id = "reviseConfigDraft"
        command = {"draft_id": draft_id, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            draft = self._load_draft(
                connection,
                principal,
                draft_id,
                "config.edit_business",
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            allowed = draft["state"] in LEGAL_REVISE_STATES
            if draft["state"] == "APPROVED":
                try:
                    self._ensure_fingerprint_current(connection, principal, draft)
                except ControlPlaneError as exc:
                    if exc.code == "RESOLUTION_FINGERPRINT_STALE":
                        allowed = True
                    else:
                        raise
            if not allowed:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Draft cannot be revised from its current state",
                )
            next_revision = draft["current_revision"] + 1
            connection.execute(
                """
                INSERT INTO config_draft_revisions(
                    draft_id, draft_revision, schema_version,
                    canonical_spec_json, content_hash,
                    created_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    next_revision,
                    draft["schema_version"],
                    draft["working_spec_json"],
                    draft["content_hash"],
                    principal.user_id,
                    now,
                ),
            )
            self.owner.p2_1.copy_draft_assignment_forward(
                connection,
                draft_id=draft_id,
                source_revision=draft["current_revision"],
                target_revision=next_revision,
            )
            self.owner.p2_2.copy_draft_assignment_forward(
                connection,
                draft_id=draft_id,
                source_revision=draft["current_revision"],
                target_revision=next_revision,
            )
            metadata = self.owner._metadata(connection)
            connection.execute(
                """
                UPDATE config_drafts SET state = 'DRAFT',
                    current_revision = ?, last_editor_user_id = ?,
                    validation_record_id = NULL, preview_record_id = NULL,
                    approval_record_id = NULL, control_plane_epoch = ?,
                    updated_at = ?, revision = revision + 1
                WHERE draft_id = ?
                """,
                (
                    next_revision,
                    principal.user_id,
                    metadata["revision"],
                    now,
                    draft_id,
                ),
            )
            self.owner._append_audit(
                connection,
                event_type="CONFIG_DRAFT_REVISED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "source_state": draft["state"],
                    "new_draft_revision": next_revision,
                },
                now=now,
            )
            updated = self._load_draft(connection, principal, draft_id, "config.read")
            result = self._draft_response(connection, updated)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def abandon_config_draft(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_all_spec_edit_permissions(principal)
        return self._simple_draft_transition(
            principal,
            draft_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            operation_id="abandonConfigDraft",
            expected_states=LEGAL_ABANDON_STATES,
            next_state="ABANDONED",
            event_type="CONFIG_DRAFT_ABANDONED",
        )

    def create_config_release(
        self,
        principal: Any,
        draft_id: str,
        *,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "release.publish")
        reason = self._reason(reason)
        operation_id = "createConfigRelease"
        command = {"draft_id": draft_id, "reason": reason, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            draft = self._load_draft(
                connection,
                principal,
                draft_id,
                "release.publish",
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] != "APPROVED":
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Only an approved draft can create a release",
                )
            fingerprint = self._ensure_fingerprint_current(connection, principal, draft)
            approval = connection.execute(
                """
                SELECT * FROM config_approval_records
                WHERE approval_record_id = ? AND decision = 'APPROVED'
                """,
                (draft["approval_record_id"],),
            ).fetchone()
            if approval is None:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Approved draft evidence is unavailable",
                )
            resolution = self._resolve_draft(connection, principal, draft)
            self.owner.p2_2.require_release_validation(
                connection,
                draft=draft,
                base_validation_record_id=draft["validation_record_id"],
                query_resolution=resolution["query_resolution"],
            )
            release_id = opaque_id("rel")
            release_sequence = self._next_release_sequence(connection, principal)
            connection.execute(
                """
                INSERT INTO config_releases(
                    release_id, tenant_id, deployment_id, release_sequence,
                    creation_kind, schema_version, normal_draft_id,
                    normal_draft_revision, normal_fingerprint_id,
                    normal_approval_record_id, target_set_hash, group_revision,
                    created_by_user_id, reason, created_at
                ) VALUES (?, ?, ?, ?, 'NORMAL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    release_sequence,
                    CONFIG_SCHEMA_VERSION,
                    draft_id,
                    draft["current_revision"],
                    fingerprint["fingerprint_id"],
                    approval["approval_record_id"],
                    resolution["target_set_hash"],
                    resolution["group_revision"],
                    principal.user_id,
                    reason,
                    now,
                ),
            )
            for target in resolution["targets"]:
                release_target_id = opaque_id("rlt")
                connection.execute(
                    """
                    INSERT INTO release_targets(
                        release_target_id, tenant_id, deployment_id,
                        release_id, screen_id,
                        canonical_effective_config_json, content_hash,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        release_target_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        release_id,
                        target["screen_id"],
                        target["canonical_effective_config_json"],
                        target["content_hash"],
                        now,
                    ),
                )
                self.owner.p2_1.insert_release_snapshot(
                    connection,
                    release_target_id=release_target_id,
                    target=target,
                    capability_resolution=resolution["capability_resolution"],
                    now=now,
                )
                self.owner.p2_2.insert_release_snapshot(
                    connection,
                    release_target_id=release_target_id,
                    target=target,
                    query_resolution=resolution["query_resolution"],
                    now=now,
                )
            connection.execute(
                """
                UPDATE config_drafts SET state = 'RELEASED',
                    updated_at = ?, revision = revision + 1
                WHERE draft_id = ?
                """,
                (now, draft_id),
            )
            self.owner._append_audit(
                connection,
                event_type="CONFIG_RELEASE_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_RELEASE",
                target_id=release_id,
                outcome="SUCCESS",
                reason=reason,
                details={
                    "creation_kind": "NORMAL",
                    "draft_id": draft_id,
                    "draft_revision": draft["current_revision"],
                    "target_set_hash": resolution["target_set_hash"],
                    "target_count": len(resolution["targets"]),
                },
                now=now,
            )
            result = self._release_response(connection, principal, release_id)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def get_config_release(self, principal: Any, release_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            return self._release_response(connection, principal, release_id)

    def diff_config_releases(
        self,
        principal: Any,
        from_release_id: str,
        to_release_id: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            source = self._release_response(connection, principal, from_release_id)
            target = self._release_response(connection, principal, to_release_id)
        source_targets = {item["screen_id"]: item for item in source["targets"]}
        target_targets = {item["screen_id"]: item for item in target["targets"]}
        screen_ids = sorted(set(source_targets) | set(target_targets))
        changes: list[dict[str, Any]] = []
        for screen_id in screen_ids:
            old = source_targets.get(screen_id)
            new = target_targets.get(screen_id)
            if old is None:
                changes.append({"screen_id": screen_id, "change": "ADDED"})
                continue
            if new is None:
                changes.append({"screen_id": screen_id, "change": "REMOVED"})
                continue
            old_config = old["effective_config"]
            new_config = new["effective_config"]
            field_changes = [
                {
                    "path": f"/{field}",
                    "from": old_config.get(field),
                    "to": new_config.get(field),
                }
                for field in sorted(set(old_config) | set(new_config))
                if old_config.get(field) != new_config.get(field)
            ]
            changes.append(
                {
                    "screen_id": screen_id,
                    "change": "CHANGED" if field_changes else "UNCHANGED",
                    "field_changes": field_changes,
                    "from_content_hash": old["content_hash"],
                    "to_content_hash": new["content_hash"],
                }
            )
        return {
            "api_version": "v1",
            "from_release_id": from_release_id,
            "to_release_id": to_release_id,
            "changes": changes,
        }

    # Publication, device acknowledgement and forward rollback.

    def publish_to_screen(
        self,
        context: Any,
        screen_id: str,
        *,
        release_id: str,
        release_target_id: str,
        expected_binding_generation: int,
        runtime_if_match: str,
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        command = {
            "screen_id": screen_id,
            "release_id": release_id,
            "release_target_id": release_target_id,
            "expected_binding_generation": expected_binding_generation,
            "runtime_if_match": runtime_if_match,
        }
        if high_risk_action_id is None:
            with self.owner.store.connect() as connection:
                self._preflight_publication(
                    connection,
                    context.principal,
                    "publishToScreen",
                    command,
                )
        return self.owner._request_or_execute_protected(
            context,
            operation_id="publishToScreen",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def publish_to_group(
        self,
        context: Any,
        screen_group_id: str,
        *,
        release_id: str,
        group_if_match: str,
        targets: list[dict[str, Any]],
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        command = {
            "screen_group_id": screen_group_id,
            "release_id": release_id,
            "group_if_match": group_if_match,
            "targets": sorted(targets, key=lambda item: item["screen_id"]),
        }
        if high_risk_action_id is None:
            with self.owner.store.connect() as connection:
                self._preflight_publication(
                    connection,
                    context.principal,
                    "publishToScreenGroup",
                    command,
                )
        return self.owner._request_or_execute_protected(
            context,
            operation_id="publishToScreenGroup",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def rollback_screen(
        self,
        context: Any,
        screen_id: str,
        *,
        source_release_target_id: str,
        expected_binding_generation: int,
        runtime_if_match: str,
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        command = {
            "screen_id": screen_id,
            "source_release_target_id": source_release_target_id,
            "expected_binding_generation": expected_binding_generation,
            "runtime_if_match": runtime_if_match,
        }
        if high_risk_action_id is None:
            with self.owner.store.connect() as connection:
                self._preflight_rollback(
                    connection,
                    context.principal,
                    "rollbackScreen",
                    command,
                )
        return self.owner._request_or_execute_protected(
            context,
            operation_id="rollbackScreen",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def rollback_group(
        self,
        context: Any,
        screen_group_id: str,
        *,
        source_targets: list[dict[str, str]],
        group_if_match: str,
        targets: list[dict[str, Any]],
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        command = {
            "screen_group_id": screen_group_id,
            "source_targets": sorted(
                source_targets,
                key=lambda item: item["screen_id"],
            ),
            "group_if_match": group_if_match,
            "targets": sorted(targets, key=lambda item: item["screen_id"]),
        }
        if high_risk_action_id is None:
            with self.owner.store.connect() as connection:
                self._preflight_rollback(
                    connection,
                    context.principal,
                    "rollbackScreenGroup",
                    command,
                )
        return self.owner._request_or_execute_protected(
            context,
            operation_id="rollbackScreenGroup",
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    def execute_protected_effect(
        self,
        connection: sqlite3.Connection,
        operation_id: str,
        command: dict[str, Any],
        principal: Any,
        now: float,
        high_risk_action_id: str,
    ) -> dict[str, Any]:
        if operation_id in {"publishToScreen", "publishToScreenGroup"}:
            self._preflight_publication(connection, principal, operation_id, command)
            return self._execute_publication(
                connection,
                principal,
                operation_id=operation_id,
                command=command,
                high_risk_action_id=high_risk_action_id,
                reason=self._action_reason(connection, high_risk_action_id),
                now=now,
            )
        if operation_id in {"rollbackScreen", "rollbackScreenGroup"}:
            self._preflight_rollback(connection, principal, operation_id, command)
            return self._execute_rollback(
                connection,
                principal,
                operation_id=operation_id,
                command=command,
                high_risk_action_id=high_risk_action_id,
                reason=self._action_reason(connection, high_risk_action_id),
                now=now,
            )
        raise ControlPlaneError(501, "NOT_IMPLEMENTED", "P1.3 protected operation is unavailable")

    def get_publication(self, principal: Any, publication_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            return self._publication_response(connection, principal, publication_id)

    def get_device_current_release(self, context: Any) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            binding = connection.execute(
                """
                SELECT * FROM runtime_bindings
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (context.tenant_id, context.deployment_id, context.screen_id),
            ).fetchone()
            if binding is None:
                raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Runtime binding was not found")
            if binding["desired_release_target_id"] is None:
                return {
                    "api_version": "v1",
                    "screen_id": context.screen_id,
                    "state": "NOT_CONFIGURED_P1_3",
                    "binding_generation": binding["binding_generation"],
                    "release_target": None,
                }
            target = connection.execute(
                """
                SELECT rt.*, r.release_sequence, r.creation_kind
                FROM release_targets rt
                JOIN config_releases r ON r.release_id = rt.release_id
                WHERE rt.release_target_id = ?
                  AND rt.tenant_id = ? AND rt.deployment_id = ?
                  AND rt.screen_id = ?
                """,
                (
                    binding["desired_release_target_id"],
                    context.tenant_id,
                    context.deployment_id,
                    context.screen_id,
                ),
            ).fetchone()
            if target is None:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    "Desired release target is unavailable",
                    retryable=False,
                )
            return {
                "api_version": "v1",
                "screen_id": context.screen_id,
                "state": "DESIRED_AVAILABLE",
                "binding_generation": binding["binding_generation"],
                "release_target": self._release_target_response(
                    connection,
                    target,
                ),
            }

    def acknowledge_device_release(
        self,
        context: Any,
        release_target_id: str,
        *,
        binding_generation: int,
        content_hash: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        operation_id = "acknowledgeDeviceRelease"
        command = {
            "release_target_id": release_target_id,
            "binding_generation": binding_generation,
            "content_hash": content_hash,
            "screen_id": context.screen_id,
            "credential_id": context.credential_id,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=context.credential_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            binding = connection.execute(
                """
                SELECT * FROM runtime_bindings
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (context.tenant_id, context.deployment_id, context.screen_id),
            ).fetchone()
            target = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND release_target_id = ?
                """,
                (
                    context.tenant_id,
                    context.deployment_id,
                    context.screen_id,
                    release_target_id,
                ),
            ).fetchone()
            if binding is None or target is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Release target was not found",
                )
            if (
                binding["desired_release_target_id"] != release_target_id
                or binding["binding_generation"] != binding_generation
                or target["content_hash"] != content_hash
            ):
                raise ControlPlaneError(
                    412,
                    "ACTIVE_RELEASE_CHANGED",
                    "Desired release generation or hash changed",
                )
            publication_target = connection.execute(
                """
                SELECT * FROM publication_targets
                WHERE release_target_id = ? AND screen_id = ?
                  AND state IN ('WAITING_FOR_DEVICE', 'APPLYING')
                ORDER BY created_at DESC LIMIT 1
                """,
                (release_target_id, context.screen_id),
            ).fetchone()
            if publication_target is None:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Publication target is not awaiting acknowledgement",
                )
            if binding["applied_release_target_id"] is not None:
                connection.execute(
                    """
                    UPDATE publication_targets SET state = 'SUPERSEDED',
                        updated_at = ?, revision = revision + 1
                    WHERE release_target_id = ? AND screen_id = ?
                      AND state = 'ACTIVE'
                    """,
                    (
                        now,
                        binding["applied_release_target_id"],
                        context.screen_id,
                    ),
                )
            marker = f"ack-{release_target_id[-12:]}-{binding_generation}"
            connection.execute(
                """
                UPDATE runtime_bindings SET
                    applied_release_target_id = ?,
                    last_acknowledged_marker = ?,
                    last_acknowledged_at = ?,
                    inventory_status = 'ACTIVE',
                    updated_at = ?, revision = revision + 1
                WHERE screen_id = ?
                """,
                (
                    release_target_id,
                    marker,
                    now,
                    now,
                    context.screen_id,
                ),
            )
            connection.execute(
                """
                UPDATE publication_targets SET state = 'ACTIVE',
                    updated_at = ?, revision = revision + 1
                WHERE publication_id = ? AND screen_id = ?
                """,
                (
                    now,
                    publication_target["publication_id"],
                    context.screen_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO runtime_binding_history(
                    history_id, tenant_id, deployment_id, site_id,
                    screen_id, publication_id, event_type,
                    old_desired_release_target_id, new_desired_release_target_id,
                    old_applied_release_target_id, new_applied_release_target_id,
                    binding_generation, actor_type, actor_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'APPLIED_ACKNOWLEDGED',
                    ?, ?, ?, ?, ?, 'DEVICE', ?, ?)
                """,
                (
                    opaque_id("rbh"),
                    context.tenant_id,
                    context.deployment_id,
                    binding["site_id"],
                    context.screen_id,
                    publication_target["publication_id"],
                    binding["desired_release_target_id"],
                    binding["desired_release_target_id"],
                    binding["applied_release_target_id"],
                    release_target_id,
                    binding_generation,
                    context.credential_id,
                    now,
                ),
            )
            result = {
                "api_version": "v1",
                "screen_id": context.screen_id,
                "release_target_id": release_target_id,
                "state": "ACTIVE",
                "binding_generation": binding_generation,
                "content_hash": content_hash,
                "acknowledgement_marker": marker,
            }
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=context.credential_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            self.owner._append_audit(
                connection,
                event_type="DEVICE_RELEASE_ACKNOWLEDGED",
                actor_type="DEVICE",
                actor_id=context.credential_id,
                target_type="SCREEN",
                target_id=context.screen_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "release_target_id": release_target_id,
                    "binding_generation": binding_generation,
                    "content_hash": content_hash,
                },
                now=now,
            )
            return result

    # Encrypted backup and online-source staged restore.

    def get_storage_profile(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "screen.read")
        return {"api_version": "v1", **self.backups.storage_profile()}

    def record_runtime_detail_retention(
        self,
        *,
        retention_days: int,
        deleted_runtime_detail_count: int,
    ) -> dict[str, Any]:
        if retention_days < 1 or deleted_runtime_detail_count < 0:
            raise ValueError("Invalid runtime-detail retention result")
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
            "query_secret_records",
            "query_secret_versions",
            "query_sources",
            "query_source_versions",
            "query_datasets",
            "query_dataset_versions",
            "config_draft_query_assignments",
            "query_validation_records",
            "release_target_query_snapshots",
            "security_audit_events",
        )
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            metadata = connection.execute(
                "SELECT * FROM control_plane_metadata WHERE singleton = 1"
            ).fetchone()
            if metadata is None:
                return {
                    "recorded": False,
                    "reason": "CONTROL_PLANE_NOT_INITIALIZED",
                }
            existing_tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            counts = {
                table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in protected_tables
                if table in existing_tables
            }
            protected_hash = hashlib.sha256(canonical_json(counts).encode("utf-8")).hexdigest()
            retention_run_id = opaque_id("rtn")
            connection.execute(
                """
                INSERT INTO retention_runs(
                    retention_run_id, retention_days,
                    deleted_runtime_detail_count,
                    protected_control_plane_counts_hash, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    retention_run_id,
                    retention_days,
                    deleted_runtime_detail_count,
                    protected_hash,
                    now,
                ),
            )
            self.owner._append_audit(
                connection,
                event_type="RUNTIME_DETAIL_RETENTION_COMPLETED",
                actor_type="SYSTEM",
                actor_id=None,
                target_type="RETENTION_RUN",
                target_id=retention_run_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "retention_days": retention_days,
                    "deleted_runtime_detail_count": deleted_runtime_detail_count,
                    "protected_control_plane_counts_hash": protected_hash,
                },
                now=now,
            )
            return {
                "recorded": True,
                "retention_run_id": retention_run_id,
                "retention_days": retention_days,
                "deleted_runtime_detail_count": deleted_runtime_detail_count,
                "protected_control_plane_counts_hash": protected_hash,
            }

    def create_backup(
        self,
        principal: Any,
        *,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_deployment_permission(principal, "backup.create")
        reason = self._reason(reason)
        operation_id = "createBackup"
        request_digest = self.owner._sensitive_request_digest(
            operation_id,
            {"reason": reason},
        )
        with self._backup_lock, self.owner.store.mutation_lock:
            with self.owner.store.connect() as connection:
                replay = self.owner._idempotency_lookup(
                    connection,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                )
                if replay is not None:
                    return json.loads(replay["result_json"])
                metadata = self.owner._metadata(connection)
                tenant_id = metadata["tenant_id"]
                deployment_id = metadata["deployment_id"]
            now = self.owner.clock()
            backup_id = opaque_id("bak")
            try:
                created = self.backups.create_bundle(
                    backup_id=backup_id,
                    tenant_id=tenant_id,
                    deployment_id=deployment_id,
                    created_at=now,
                )
            except BackupIntegrityError as exc:
                raise ControlPlaneError(
                    503,
                    "STORAGE_UNAVAILABLE",
                    str(exc),
                    retryable=False,
                ) from exc
            with self.owner.store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO backup_records(
                        backup_id, tenant_id, deployment_id, state,
                        bundle_name, manifest_hash, ciphertext_hash,
                        recovery_encryption_key_id, logical_schema_version,
                        migration_versions_json, safe_row_counts_json,
                        audit_head_hash, ciphertext_size, duration_ms,
                        reason, created_by_user_id, created_at, verified_at
                    ) VALUES (?, ?, ?, 'VERIFIED', ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        backup_id,
                        tenant_id,
                        deployment_id,
                        created["bundle_name"],
                        created["manifest_hash"],
                        created["ciphertext_hash"],
                        created["recovery_encryption_key_id"],
                        created["logical_schema_version"],
                        canonical_json(created["migration_versions"]),
                        canonical_json(created["safe_row_counts"]),
                        created["audit_head_hash"],
                        created["ciphertext_size"],
                        created["duration_ms"],
                        reason,
                        principal.user_id,
                        now,
                        now,
                    ),
                )
                result = self._backup_response(
                    connection,
                    principal,
                    backup_id,
                )
                self.owner._idempotency_store(
                    connection,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                self.owner._append_audit(
                    connection,
                    event_type="BACKUP_CREATED_AND_VERIFIED",
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type="BACKUP",
                    target_id=backup_id,
                    outcome="SUCCESS",
                    reason=reason,
                    details={
                        "manifest_hash": created["manifest_hash"],
                        "ciphertext_hash": created["ciphertext_hash"],
                        "logical_schema_version": LOGICAL_SCHEMA_VERSION,
                    },
                    now=now,
                )
                return result

    def get_backup(self, principal: Any, backup_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "operation.read")
        with self.owner.store.connect() as connection:
            return self._backup_response(connection, principal, backup_id)

    def verify_backup(
        self,
        principal: Any,
        backup_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_deployment_permission(principal, "backup.create")
        operation_id = "verifyBackup"
        request_digest = self.owner._sensitive_request_digest(
            operation_id,
            {"backup_id": backup_id},
        )
        with self._backup_lock:
            with self.owner.store.connect() as connection:
                replay = self.owner._idempotency_lookup(
                    connection,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                )
                if replay is not None:
                    return json.loads(replay["result_json"])
                backup = self._backup_row(connection, principal, backup_id)
            try:
                verified = self.backups.verify_bundle(backup["bundle_name"])
                self._require_backup_record_match(
                    backup,
                    manifest=verified["manifest"],
                    manifest_hash=verified["manifest_hash"],
                    ciphertext_hash=verified["ciphertext_hash"],
                    safe_row_counts=verified["safe_row_counts"],
                )
            except BackupIntegrityError as exc:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    str(exc),
                    retryable=False,
                ) from exc
            now = self.owner.clock()
            with self.owner.store.transaction() as connection:
                result = {
                    "api_version": "v1",
                    "backup_id": backup_id,
                    "outcome": verified["outcome"],
                    "manifest_hash": backup["manifest_hash"],
                    "duration_ms": verified["duration_ms"],
                    "safe_row_counts": verified["safe_row_counts"],
                }
                self.owner._idempotency_store(
                    connection,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                self.owner._append_audit(
                    connection,
                    event_type="BACKUP_VERIFIED",
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type="BACKUP",
                    target_id=backup_id,
                    outcome="SUCCESS",
                    reason=None,
                    details={
                        "manifest_hash": backup["manifest_hash"],
                        "duration_ms": verified["duration_ms"],
                    },
                    now=now,
                )
                return result

    def create_restore_plan(
        self,
        context: Any,
        *,
        backup_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_deployment_permission(context.principal, "backup.restore")
        self.owner._require_recent_reauthentication(context)
        operation_id = "createRestorePlan"
        command = {"backup_id": backup_id, "recovery_source_mode": "ONLINE_ACTIVE_STORE"}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        with self._restore_lock:
            with self.owner.store.connect() as connection:
                replay = self.owner._idempotency_lookup(
                    connection,
                    phase=operation_id,
                    principal_key=context.principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                )
                if replay is not None:
                    return json.loads(replay["result_json"])
                backup = self._backup_row(connection, context.principal, backup_id)
                metadata = self.owner._metadata(connection)
            try:
                verified = self.backups.verify_bundle(backup["bundle_name"])
                self._require_backup_record_match(
                    backup,
                    manifest=verified["manifest"],
                    manifest_hash=verified["manifest_hash"],
                    ciphertext_hash=verified["ciphertext_hash"],
                    safe_row_counts=verified["safe_row_counts"],
                )
            except BackupIntegrityError as exc:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    str(exc),
                    retryable=False,
                ) from exc
            now = self.owner.clock()
            with self.owner.store.transaction() as connection:
                restore_plan_id = opaque_id("rsp")
                findings = {
                    "outcome": "VALID",
                    "backup_manifest_hash": backup["manifest_hash"],
                    "logical_schema_version": LOGICAL_SCHEMA_VERSION,
                    "migration_versions": [version for version, _, _ in MIGRATIONS],
                    "runtime_bindings_complete": verified["safe_row_counts"]["runtime_bindings_complete"],
                    "recovery_source_mode": "ONLINE_ACTIVE_STORE",
                    "production_recovery_certified": False,
                }
                connection.execute(
                    """
                    INSERT INTO restore_plans(
                        restore_plan_id, tenant_id, deployment_id,
                        backup_id, backup_manifest_hash,
                        recovery_source_mode, authorization_mode,
                        expected_metadata_revision, findings_json, state,
                        created_by_user_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'ONLINE_ACTIVE_STORE',
                        'STANDARD_HIGH_RISK', ?, ?, 'READY', ?, ?, ?)
                    """,
                    (
                        restore_plan_id,
                        context.principal.tenant_id,
                        context.principal.deployment_id,
                        backup_id,
                        backup["manifest_hash"],
                        metadata["revision"],
                        canonical_json(findings),
                        context.principal.user_id,
                        now,
                        now,
                    ),
                )
                result = self._restore_plan_response(
                    connection,
                    context.principal,
                    restore_plan_id,
                )
                self.owner._idempotency_store(
                    connection,
                    phase=operation_id,
                    principal_key=context.principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                self.owner._append_audit(
                    connection,
                    event_type="RESTORE_PLAN_VALIDATED",
                    actor_type="USER",
                    actor_id=context.principal.user_id,
                    target_type="RESTORE_PLAN",
                    target_id=restore_plan_id,
                    outcome="SUCCESS",
                    reason=None,
                    details=findings,
                    now=now,
                )
                return result

    def execute_restore_plan(
        self,
        context: Any,
        restore_plan_id: str,
        *,
        confirmation: str,
        reason: str,
        if_match: str,
        idempotency_key: str,
        high_risk_action_id: str | None,
    ) -> dict[str, Any]:
        self.owner.require_deployment_permission(context.principal, "backup.restore")
        self.owner._require_recent_reauthentication(context)
        if confirmation != "RESTORE_VERIFIED_BACKUP":
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Restore confirmation is invalid",
            )
        command = {
            "restore_plan_id": restore_plan_id,
            "confirmation": confirmation,
            "if_match": if_match,
        }
        if high_risk_action_id is None:
            with self.owner.store.connect() as connection:
                plan = self._restore_plan_row(
                    connection,
                    context.principal,
                    restore_plan_id,
                )
                self.owner._require_resource_etag(
                    if_match,
                    "restore-plan",
                    restore_plan_id,
                    plan["revision"],
                )
                if plan["state"] != "READY":
                    raise ControlPlaneError(
                        409,
                        "INVALID_STATE_TRANSITION",
                        "Restore plan is not ready",
                    )
            return self.owner._request_or_execute_protected(
                context,
                operation_id="executeRestorePlan",
                command=command,
                reason=reason,
                idempotency_key=idempotency_key,
                high_risk_action_id=None,
            )
        return self._execute_approved_restore(
            context,
            command=command,
            reason=reason,
            idempotency_key=idempotency_key,
            high_risk_action_id=high_risk_action_id,
        )

    # Internal draft helpers.

    def _record_validation_or_preview(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
        phase: str,
    ) -> dict[str, Any]:
        command = {"draft_id": draft_id, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(phase, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=phase,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            draft = self._load_draft(
                connection,
                principal,
                draft_id,
                "config.validate" if phase == "validateConfigDraft" else "config.preview",
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if phase == "validateConfigDraft":
                if draft["state"] != "DRAFT" or draft["current_revision"] < 1:
                    raise ControlPlaneError(
                        409,
                        "INVALID_STATE_TRANSITION",
                        "Only a populated DRAFT can be validated",
                    )
                try:
                    resolution = self._resolve_draft(connection, principal, draft)
                except ControlPlaneError as failure:
                    if not isinstance(failure, DraftValidationFailure) and failure.status_code != 422:
                        raise
                    finding_code = (
                        failure.finding_code if isinstance(failure, DraftValidationFailure) else failure.code
                    )
                    findings = [
                        {
                            "severity": "ERROR",
                            "code": finding_code,
                            "message": failure.message,
                        }
                    ]
                    findings_json = canonical_json(findings)
                    validation_id = opaque_id("val")
                    connection.execute(
                        """
                        INSERT INTO validation_records(
                            validation_record_id, draft_id, draft_revision,
                            fingerprint_id, fingerprint_hash, outcome,
                            findings_json, findings_hash, validator_version,
                            created_by_user_id, created_at
                        ) VALUES (?, ?, ?, NULL, NULL, 'INVALID', ?, ?, ?, ?, ?)
                        """,
                        (
                            validation_id,
                            draft_id,
                            draft["current_revision"],
                            findings_json,
                            hashlib.sha256(findings_json.encode("utf-8")).hexdigest(),
                            "p1_3_preview_validator_v1",
                            principal.user_id,
                            now,
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE config_drafts SET state = 'DRAFT',
                            validation_record_id = ?, preview_record_id = NULL,
                            approval_record_id = NULL, updated_at = ?,
                            revision = revision + 1
                        WHERE draft_id = ?
                        """,
                        (validation_id, now, draft_id),
                    )
                    event_type = "CONFIG_DRAFT_VALIDATION_FAILED"
                    event_details = {
                        "draft_revision": draft["current_revision"],
                        "finding_codes": [finding_code],
                        "outcome": "INVALID",
                    }
                    audit_outcome = "REJECTED"
                else:
                    fingerprint_id = opaque_id("rfp")
                    fingerprint_hash = resolution["fingerprint_hash"]
                    connection.execute(
                        """
                        INSERT INTO resolution_fingerprints(
                            fingerprint_id, draft_id, draft_revision,
                            fingerprint_hash, target_set_json, target_set_hash,
                            group_revision, resolution_inputs_json,
                            effective_hashes_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fingerprint_id,
                            draft_id,
                            draft["current_revision"],
                            fingerprint_hash,
                            canonical_json(resolution["target_set"]),
                            resolution["target_set_hash"],
                            resolution["group_revision"],
                            canonical_json(resolution["inputs"]),
                            canonical_json(resolution["effective_hashes"]),
                            now,
                        ),
                    )
                    findings = [
                        {
                            "severity": "WARNING",
                            "code": "FVS_UNVERIFIED_MOCK_PREVIEW_ONLY",
                            "message": "FVS remains unverified; preview uses Mock evidence only.",
                        }
                    ]
                    capability_resolution = resolution["capability_resolution"]
                    query_resolution = resolution["query_resolution"]
                    if capability_resolution is not None:
                        for finding in capability_resolution["dependency_findings"]:
                            if (
                                query_resolution is not None
                                and query_resolution["activation_eligible"]
                                and finding.get("severity") == "ERROR"
                                and finding.get("capability") == "querying"
                                and finding.get("provider_id") == "controlled_query"
                            ):
                                findings.append(
                                    {
                                        "severity": "INFO",
                                        "code": "P2_2_QUERY_SIDECAR_QUALIFIED",
                                        "capability": "querying",
                                        "provider_id": "controlled_query",
                                        "message": (
                                            "The frozen P2.2 dataset sidecar "
                                            "qualifies controlled_query for this draft."
                                        ),
                                    }
                                )
                            else:
                                findings.append(finding)
                    findings_json = canonical_json(findings)
                    validation_id = opaque_id("val")
                    connection.execute(
                        """
                        INSERT INTO validation_records(
                            validation_record_id, draft_id, draft_revision,
                            fingerprint_id, fingerprint_hash, outcome,
                            findings_json, findings_hash, validator_version,
                            created_by_user_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, 'VALID', ?, ?, ?, ?, ?)
                        """,
                        (
                            validation_id,
                            draft_id,
                            draft["current_revision"],
                            fingerprint_id,
                            fingerprint_hash,
                            findings_json,
                            hashlib.sha256(findings_json.encode("utf-8")).hexdigest(),
                            (
                                "p2_1_capability_profile_validator_v1"
                                if capability_resolution is not None
                                else "p1_3_preview_validator_v1"
                            ),
                            principal.user_id,
                            now,
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE config_drafts SET state = 'VALIDATED',
                            validation_record_id = ?, updated_at = ?,
                            revision = revision + 1
                        WHERE draft_id = ?
                        """,
                        (validation_id, now, draft_id),
                    )
                    self.owner.p2_2.record_validation(
                        connection,
                        principal=principal,
                        draft=draft,
                        base_validation_record_id=validation_id,
                        query_resolution=query_resolution,
                        now=now,
                    )
                    event_type = "CONFIG_DRAFT_VALIDATED"
                    event_details = {
                        "draft_revision": draft["current_revision"],
                        "fingerprint_hash": fingerprint_hash,
                        "target_set_hash": resolution["target_set_hash"],
                        "outcome": "VALID",
                    }
                    audit_outcome = "SUCCESS"
            else:
                if draft["state"] != "VALIDATED" or not draft["validation_record_id"]:
                    raise ControlPlaneError(
                        409,
                        "INVALID_STATE_TRANSITION",
                        "Only a validated draft can be previewed",
                    )
                fingerprint = self._ensure_fingerprint_current(connection, principal, draft)
                validation = connection.execute(
                    """
                    SELECT * FROM validation_records
                    WHERE validation_record_id = ? AND outcome = 'VALID'
                    """,
                    (draft["validation_record_id"],),
                ).fetchone()
                if validation is None:
                    raise ControlPlaneError(
                        409,
                        "INVALID_STATE_TRANSITION",
                        "Passed validation evidence is unavailable",
                    )
                resolution = self._resolve_draft(connection, principal, draft)
                self.owner.p2_2.require_release_validation(
                    connection,
                    draft=draft,
                    base_validation_record_id=validation["validation_record_id"],
                    query_resolution=resolution["query_resolution"],
                )
                evidence = {
                    "provider": "MOCK_FVS",
                    "outcome": "MOCK_PASSED",
                    "real_provider_verified": False,
                    "capabilities": self.owner.p2_1.preview_capability_evidence(
                        resolution["capability_resolution"]
                    ),
                    "controlled_querying": (
                        {
                            "provider": "controlled_query",
                            "outcome": "DEPLOYMENT_LOCAL_AVAILABLE",
                            "dataset_count": len(resolution["query_resolution"]["dataset_refs"]),
                            "assignment_hash": resolution["query_resolution"]["assignment"][
                                "assignment_hash"
                            ],
                            "real_query_execution_made": False,
                            "external_calls_made": False,
                            "product_certification": "UNVERIFIED",
                        }
                        if resolution["query_resolution"] is not None
                        else None
                    ),
                    "targets": [
                        {
                            "screen_id": target["screen_id"],
                            "welcome_text": target["effective_config"]["welcome_text"],
                            "fvs_binding_ref": target["effective_config"]["fvs_binding_ref"],
                            "content_hash": target["content_hash"],
                        }
                        for target in resolution["targets"]
                    ],
                }
                evidence_json = canonical_json(evidence)
                preview_id = opaque_id("prv")
                connection.execute(
                    """
                    INSERT INTO preview_records(
                        preview_record_id, draft_id, draft_revision,
                        validation_record_id, fingerprint_hash, outcome,
                        evidence_json, evidence_hash,
                        created_by_user_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'MOCK_PASSED', ?, ?, ?, ?)
                    """,
                    (
                        preview_id,
                        draft_id,
                        draft["current_revision"],
                        validation["validation_record_id"],
                        fingerprint["fingerprint_hash"],
                        evidence_json,
                        hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
                        principal.user_id,
                        now,
                    ),
                )
                connection.execute(
                    """
                    UPDATE config_drafts SET state = 'PREVIEWED',
                        preview_record_id = ?, updated_at = ?,
                        revision = revision + 1
                    WHERE draft_id = ?
                    """,
                    (preview_id, now, draft_id),
                )
                event_type = "CONFIG_DRAFT_MOCK_PREVIEWED"
                event_details = {
                    "draft_revision": draft["current_revision"],
                    "fingerprint_hash": fingerprint["fingerprint_hash"],
                    "outcome": "MOCK_PASSED",
                    "real_provider_verified": False,
                }
                audit_outcome = "SUCCESS"
            self.owner._append_audit(
                connection,
                event_type=event_type,
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome=audit_outcome,
                reason=None,
                details=event_details,
                now=now,
            )
            updated = self._load_draft(connection, principal, draft_id, "config.read")
            result = self._draft_response(connection, updated)
            if phase == "validateConfigDraft":
                result["outcome"] = result["validation"]["outcome"]
                result["findings"] = result["validation"]["findings"]
            self.owner._idempotency_store(
                connection,
                phase=phase,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def _simple_draft_transition(
        self,
        principal: Any,
        draft_id: str,
        *,
        if_match: str,
        idempotency_key: str,
        operation_id: str,
        expected_states: set[str],
        next_state: str,
        event_type: str,
    ) -> dict[str, Any]:
        command = {"draft_id": draft_id, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            draft = self._load_draft(
                connection,
                principal,
                draft_id,
                self._available_edit_permission(principal),
            )
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] not in expected_states:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Draft cannot perform this transition",
                )
            connection.execute(
                """
                UPDATE config_drafts SET state = ?, updated_at = ?,
                    revision = revision + 1 WHERE draft_id = ?
                """,
                (next_state, now, draft_id),
            )
            self.owner._append_audit(
                connection,
                event_type=event_type,
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CONFIG_DRAFT",
                target_id=draft_id,
                outcome="PENDING" if next_state == "APPROVAL_PENDING" else "SUCCESS",
                reason=None,
                details={
                    "source_state": draft["state"],
                    "target_state": next_state,
                    "draft_revision": draft["current_revision"],
                },
                now=now,
            )
            updated = self._load_draft(connection, principal, draft_id, "config.read")
            result = self._draft_response(connection, updated)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def _resolve_draft(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        draft: sqlite3.Row,
    ) -> dict[str, Any]:
        spec = json.loads(draft["working_spec_json"])
        if set(spec) != CONFIG_FIELDS:
            raise DraftValidationFailure(
                "DRAFT_SPEC_INCOMPLETE",
                "Draft spec is incomplete",
            )
        group_revision: int | None = None
        if draft["target_type"] == "SCREEN":
            screen_rows = [
                self.owner._screen_row(
                    connection,
                    principal,
                    draft["screen_id"],
                    "config.read",
                )
            ]
        else:
            group = self._group_row(
                connection,
                principal,
                draft["screen_group_id"],
                "config.read",
            )
            group_revision = group["revision"]
            screen_rows = connection.execute(
                """
                SELECT * FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ?
                  AND site_id = ? AND screen_group_id = ?
                ORDER BY screen_id
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    group["site_id"],
                    group["screen_group_id"],
                ),
            ).fetchall()
            if not screen_rows:
                raise DraftValidationFailure(
                    "TARGET_GROUP_EMPTY",
                    "Screen group has no targets",
                )
            for screen in screen_rows:
                if not self.owner._can_access_screen(
                    principal,
                    screen["site_id"],
                    screen["screen_id"],
                    "config.read",
                ):
                    raise ControlPlaneError(
                        404,
                        "RESOURCE_NOT_FOUND",
                        "Draft target was not found",
                    )
        metadata = self.owner._metadata(connection)
        targets: list[dict[str, Any]] = []
        inputs: list[dict[str, Any]] = []
        for screen in screen_rows:
            binding = connection.execute(
                """
                SELECT * FROM runtime_bindings
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                ),
            ).fetchone()
            digital_human = connection.execute(
                """
                SELECT * FROM digital_human_instances
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND status = 'ACTIVE'
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                ),
            ).fetchone()
            if (
                binding is None
                or digital_human is None
                or binding["digital_human_instance_id"] != digital_human["digital_human_instance_id"]
            ):
                raise DraftValidationFailure(
                    "TARGET_INVENTORY_INCOMPLETE",
                    "Draft target inventory is incomplete",
                )
            effective = {
                "schema_version": CONFIG_SCHEMA_VERSION,
                "screen_id": screen["screen_id"],
                "digital_human_instance_id": digital_human["digital_human_instance_id"],
                "welcome_text": spec["welcome_text"],
                "fvs_binding_ref": spec["fvs_binding_ref"],
                "fvs_status": "UNVERIFIED",
                "preview_provider": "MOCK_FVS",
            }
            effective_json = canonical_json(effective)
            content_hash = hashlib.sha256(effective_json.encode("utf-8")).hexdigest()
            targets.append(
                {
                    "screen_id": screen["screen_id"],
                    "site_id": screen["site_id"],
                    "digital_human_instance_id": digital_human["digital_human_instance_id"],
                    "effective_config": effective,
                    "canonical_effective_config_json": effective_json,
                    "content_hash": content_hash,
                }
            )
            inputs.append(
                {
                    "screen_id": screen["screen_id"],
                    "screen_revision": screen["revision"],
                    "runtime_binding_revision": binding["revision"],
                    "binding_generation": binding["binding_generation"],
                    "digital_human_instance_id": digital_human["digital_human_instance_id"],
                    "digital_human_revision": digital_human["revision"],
                }
            )
        capability_resolution = self.owner.p2_1.resolve_draft_capabilities(
            connection,
            draft_id=draft["draft_id"],
            draft_revision=draft["current_revision"],
            targets=targets,
        )
        query_resolution = self.owner.p2_2.resolve_draft_queries(
            connection,
            draft_id=draft["draft_id"],
            draft_revision=draft["current_revision"],
            targets=targets,
            capability_resolution=capability_resolution,
        )
        if capability_resolution is not None:
            if not self.owner.p2_2.composite_capability_activation_eligible(
                capability_resolution,
                query_resolution,
            ):
                raise DraftValidationFailure(
                    "CAPABILITY_PROFILE_NOT_ACTIVATION_ELIGIBLE",
                    "Assigned capability profile contains an unverified Provider",
                )
            assignment = capability_resolution["assignment"]
            for item in inputs:
                item["capability_profile"] = {
                    "profile_id": assignment["profile_id"],
                    "profile_version_id": assignment["profile_version_id"],
                    "version_number": assignment["version_number"],
                    "profile_content_hash": assignment["profile_content_hash"],
                    "provider_registry_version": assignment["provider_registry_version"],
                    "provider_registry_hash": assignment["provider_registry_hash"],
                    "capability_envelope_hash": capability_resolution["envelope_hashes"][item["screen_id"]],
                }
        target_set = sorted(target["screen_id"] for target in targets)
        target_set_hash = hashlib.sha256(canonical_json(target_set).encode("utf-8")).hexdigest()
        effective_hashes = {target["screen_id"]: target["content_hash"] for target in targets}
        fingerprint_payload = {
            "draft_id": draft["draft_id"],
            "draft_revision": draft["current_revision"],
            "schema_version": draft["schema_version"],
            "content_hash": draft["content_hash"],
            "target_set_hash": target_set_hash,
            "group_revision": group_revision,
            "inputs": inputs,
            "effective_hashes": effective_hashes,
            "capability_envelope_hashes": (
                capability_resolution["envelope_hashes"] if capability_resolution is not None else {}
            ),
            "control_plane_epoch": metadata["revision"],
        }
        return {
            "target_set": target_set,
            "target_set_hash": target_set_hash,
            "group_revision": group_revision,
            "inputs": inputs,
            "effective_hashes": effective_hashes,
            "targets": targets,
            "capability_resolution": capability_resolution,
            "query_resolution": query_resolution,
            "fingerprint_hash": hashlib.sha256(
                canonical_json(fingerprint_payload).encode("utf-8")
            ).hexdigest(),
        }

    def _ensure_fingerprint_current(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        draft: sqlite3.Row,
    ) -> sqlite3.Row:
        if not draft["validation_record_id"]:
            raise ControlPlaneError(
                409,
                "INVALID_STATE_TRANSITION",
                "Draft validation evidence is unavailable",
            )
        validation = connection.execute(
            """
            SELECT * FROM validation_records
            WHERE validation_record_id = ?
            """,
            (draft["validation_record_id"],),
        ).fetchone()
        fingerprint = connection.execute(
            """
            SELECT * FROM resolution_fingerprints
            WHERE fingerprint_id = ?
            """,
            (validation["fingerprint_id"],),
        ).fetchone()
        metadata = self.owner._metadata(connection)
        resolution = self._resolve_draft(connection, principal, draft)
        if (
            fingerprint is None
            or fingerprint["fingerprint_hash"] != resolution["fingerprint_hash"]
            or draft["control_plane_epoch"] != metadata["revision"]
        ):
            raise ControlPlaneError(
                409,
                "RESOLUTION_FINGERPRINT_STALE",
                "Draft resolution changed and must be revised",
            )
        return fingerprint

    # Internal publication and rollback helpers.

    def _preflight_publication(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        operation_id: str,
        command: dict[str, Any],
    ) -> None:
        self.owner.require_permission(principal, "release.publish")
        release = connection.execute(
            """
            SELECT * FROM config_releases
            WHERE release_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (
                command["release_id"],
                principal.tenant_id,
                principal.deployment_id,
            ),
        ).fetchone()
        if release is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Release was not found")
        if operation_id == "publishToScreen":
            screen = self.owner._screen_row(
                connection,
                principal,
                command["screen_id"],
                "release.publish",
            )
            target = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE release_id = ? AND release_target_id = ?
                  AND tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (
                    command["release_id"],
                    command["release_target_id"],
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                ),
            ).fetchone()
            if target is None:
                raise ControlPlaneError(
                    409,
                    "PUBLISH_TARGET_CHANGED",
                    "Release target does not belong to the screen",
                )
            self._require_runtime_precondition(
                connection,
                principal,
                screen["screen_id"],
                command["runtime_if_match"],
                command["expected_binding_generation"],
            )
            return
        group = self._group_row(
            connection,
            principal,
            command["screen_group_id"],
            "release.publish",
        )
        self.owner._require_resource_etag(
            command["group_if_match"],
            "screen-group",
            group["screen_group_id"],
            group["revision"],
        )
        if release["group_revision"] != group["revision"]:
            raise ControlPlaneError(
                409,
                "PUBLISH_TARGET_CHANGED",
                "Release group revision changed",
            )
        members = {
            row["screen_id"]
            for row in connection.execute(
                """
                SELECT screen_id FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ?
                  AND site_id = ? AND screen_group_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    group["site_id"],
                    group["screen_group_id"],
                ),
            ).fetchall()
        }
        release_targets = {
            row["screen_id"]: row
            for row in connection.execute(
                """
                SELECT * FROM release_targets
                WHERE release_id = ? AND tenant_id = ? AND deployment_id = ?
                """,
                (
                    command["release_id"],
                    principal.tenant_id,
                    principal.deployment_id,
                ),
            ).fetchall()
        }
        command_targets = {item["screen_id"]: item for item in command["targets"]}
        if (
            not members
            or members != set(release_targets)
            or members != set(command_targets)
            or len(command_targets) != len(command["targets"])
        ):
            raise ControlPlaneError(
                409,
                "PUBLISH_TARGET_CHANGED",
                "Group publication target set changed",
            )
        for screen_id in sorted(members):
            item = command_targets[screen_id]
            if item["release_target_id"] != release_targets[screen_id]["release_target_id"]:
                raise ControlPlaneError(
                    409,
                    "PUBLISH_TARGET_CHANGED",
                    "Group release target changed",
                )
            self._require_runtime_precondition(
                connection,
                principal,
                screen_id,
                item["runtime_if_match"],
                item["expected_binding_generation"],
            )

    def _preflight_rollback(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        operation_id: str,
        command: dict[str, Any],
    ) -> None:
        self.owner.require_permission(principal, "release.rollback")
        if operation_id == "rollbackScreen":
            screen = self.owner._screen_row(
                connection,
                principal,
                command["screen_id"],
                "release.rollback",
            )
            source = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND release_target_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["screen_id"],
                    command["source_release_target_id"],
                ),
            ).fetchone()
            if source is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Rollback source was not found",
                )
            self._require_runtime_precondition(
                connection,
                principal,
                screen["screen_id"],
                command["runtime_if_match"],
                command["expected_binding_generation"],
            )
            return
        group = self._group_row(
            connection,
            principal,
            command["screen_group_id"],
            "release.rollback",
        )
        self.owner._require_resource_etag(
            command["group_if_match"],
            "screen-group",
            group["screen_group_id"],
            group["revision"],
        )
        members = {
            row["screen_id"]
            for row in connection.execute(
                """
                SELECT screen_id FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ?
                  AND site_id = ? AND screen_group_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    group["site_id"],
                    group["screen_group_id"],
                ),
            ).fetchall()
        }
        source_map = {item["screen_id"]: item for item in command["source_targets"]}
        target_map = {item["screen_id"]: item for item in command["targets"]}
        if (
            not members
            or members != set(source_map)
            or members != set(target_map)
            or len(source_map) != len(command["source_targets"])
            or len(target_map) != len(command["targets"])
        ):
            raise ControlPlaneError(
                409,
                "PUBLISH_TARGET_CHANGED",
                "Rollback group target set changed",
            )
        for screen_id in sorted(members):
            source = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND release_target_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    screen_id,
                    source_map[screen_id]["source_release_target_id"],
                ),
            ).fetchone()
            if source is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Rollback source was not found",
                )
            self._require_runtime_precondition(
                connection,
                principal,
                screen_id,
                target_map[screen_id]["runtime_if_match"],
                target_map[screen_id]["expected_binding_generation"],
            )

    def _execute_publication(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        *,
        operation_id: str,
        command: dict[str, Any],
        high_risk_action_id: str,
        reason: str,
        now: float,
    ) -> dict[str, Any]:
        if operation_id == "publishToScreen":
            target_commands = [
                {
                    "screen_id": command["screen_id"],
                    "release_target_id": command["release_target_id"],
                    "runtime_if_match": command["runtime_if_match"],
                    "expected_binding_generation": command["expected_binding_generation"],
                }
            ]
            screen_group_id = None
            group_revision = None
        else:
            target_commands = command["targets"]
            screen_group_id = command["screen_group_id"]
            group = connection.execute(
                "SELECT revision FROM screen_groups WHERE screen_group_id = ?",
                (screen_group_id,),
            ).fetchone()
            group_revision = group["revision"]
        target_set = sorted(item["screen_id"] for item in target_commands)
        target_set_hash = hashlib.sha256(canonical_json(target_set).encode("utf-8")).hexdigest()
        publication_id = opaque_id("pub")
        connection.execute(
            """
            INSERT INTO publications(
                publication_id, tenant_id, deployment_id, release_id,
                screen_group_id, target_set_hash, group_revision,
                actor_user_id, high_risk_action_id, reason, state, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCEEDED', ?)
            """,
            (
                publication_id,
                principal.tenant_id,
                principal.deployment_id,
                command["release_id"],
                screen_group_id,
                target_set_hash,
                group_revision,
                principal.user_id,
                high_risk_action_id,
                reason,
                now,
            ),
        )
        for item in target_commands:
            binding = self._require_runtime_precondition(
                connection,
                principal,
                item["screen_id"],
                item["runtime_if_match"],
                item["expected_binding_generation"],
            )
            target = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE release_id = ? AND release_target_id = ?
                  AND tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (
                    command["release_id"],
                    item["release_target_id"],
                    principal.tenant_id,
                    principal.deployment_id,
                    item["screen_id"],
                ),
            ).fetchone()
            if target is None:
                raise ControlPlaneError(
                    409,
                    "PUBLISH_TARGET_CHANGED",
                    "Release target changed",
                )
            connection.execute(
                """
                UPDATE publication_targets SET state = 'FAILED',
                    failure_code = 'SUPERSEDED_BEFORE_ACK',
                    updated_at = ?, revision = revision + 1
                WHERE screen_id = ?
                  AND state IN ('QUEUED', 'WAITING_FOR_DEVICE', 'APPLYING')
                """,
                (now, item["screen_id"]),
            )
            family = connection.execute(
                """
                SELECT family_id FROM device_credential_families
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND state = 'ACTIVE'
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    item["screen_id"],
                ),
            ).fetchone()
            target_state = "APPLYING" if family is not None else "WAITING_FOR_DEVICE"
            connection.execute(
                """
                INSERT INTO publication_targets(
                    publication_id, release_id, release_target_id,
                    tenant_id, deployment_id, screen_id,
                    expected_runtime_revision, expected_binding_generation,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication_id,
                    command["release_id"],
                    item["release_target_id"],
                    principal.tenant_id,
                    principal.deployment_id,
                    item["screen_id"],
                    binding["revision"],
                    binding["binding_generation"],
                    target_state,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE runtime_bindings SET desired_release_target_id = ?,
                    binding_generation = binding_generation + 1,
                    inventory_status = 'PUBLISH_PENDING',
                    updated_at = ?, revision = revision + 1
                WHERE screen_id = ?
                """,
                (item["release_target_id"], now, item["screen_id"]),
            )
            connection.execute(
                """
                INSERT INTO runtime_binding_history(
                    history_id, tenant_id, deployment_id, site_id,
                    screen_id, publication_id, event_type,
                    old_desired_release_target_id, new_desired_release_target_id,
                    old_applied_release_target_id, new_applied_release_target_id,
                    binding_generation, actor_type, actor_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'DESIRED_CHANGED',
                    ?, ?, ?, ?, ?, 'USER', ?, ?)
                """,
                (
                    opaque_id("rbh"),
                    principal.tenant_id,
                    principal.deployment_id,
                    binding["site_id"],
                    item["screen_id"],
                    publication_id,
                    binding["desired_release_target_id"],
                    item["release_target_id"],
                    binding["applied_release_target_id"],
                    binding["applied_release_target_id"],
                    binding["binding_generation"] + 1,
                    principal.user_id,
                    now,
                ),
            )
        self.owner._append_audit(
            connection,
            event_type="CONFIG_RELEASE_PUBLISHED",
            actor_type="USER",
            actor_id=principal.user_id,
            target_type="PUBLICATION",
            target_id=publication_id,
            outcome="SUCCESS",
            reason=reason,
            details={
                "release_id": command["release_id"],
                "target_set_hash": target_set_hash,
                "target_count": len(target_commands),
                "high_risk_action_id": high_risk_action_id,
            },
            now=now,
        )
        return {
            "kind": "CONFIG_RELEASE_PUBLISHED",
            "publication": self._publication_response(
                connection,
                principal,
                publication_id,
            ),
        }

    def _execute_rollback(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        *,
        operation_id: str,
        command: dict[str, Any],
        high_risk_action_id: str,
        reason: str,
        now: float,
    ) -> dict[str, Any]:
        if operation_id == "rollbackScreen":
            source_items = [
                {
                    "screen_id": command["screen_id"],
                    "source_release_target_id": command["source_release_target_id"],
                }
            ]
            runtime_items = [
                {
                    "screen_id": command["screen_id"],
                    "runtime_if_match": command["runtime_if_match"],
                    "expected_binding_generation": command["expected_binding_generation"],
                }
            ]
            screen_group_id = None
            group_revision = None
        else:
            source_items = command["source_targets"]
            runtime_items = command["targets"]
            screen_group_id = command["screen_group_id"]
            group_revision = connection.execute(
                "SELECT revision FROM screen_groups WHERE screen_group_id = ?",
                (screen_group_id,),
            ).fetchone()["revision"]
        source_map = []
        source_rows = []
        for item in source_items:
            source = connection.execute(
                """
                SELECT * FROM release_targets
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_id = ? AND release_target_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    item["screen_id"],
                    item["source_release_target_id"],
                ),
            ).fetchone()
            if source is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Rollback source was not found",
                )
            source_rows.append(source)
            source_map.append(
                {
                    "screen_id": item["screen_id"],
                    "source_release_id": source["release_id"],
                    "source_release_target_id": source["release_target_id"],
                }
            )
        source_map = sorted(source_map, key=lambda item: item["screen_id"])
        source_map_json = canonical_json(source_map)
        source_map_hash = hashlib.sha256(source_map_json.encode("utf-8")).hexdigest()
        target_set = sorted(item["screen_id"] for item in source_map)
        target_set_hash = hashlib.sha256(canonical_json(target_set).encode("utf-8")).hexdigest()
        release_id = opaque_id("rel")
        release_sequence = self._next_release_sequence(connection, principal)
        connection.execute(
            """
            INSERT INTO config_releases(
                release_id, tenant_id, deployment_id, release_sequence,
                creation_kind, schema_version, rollback_source_map_json,
                rollback_source_map_hash, rollback_high_risk_action_id,
                target_set_hash, group_revision, created_by_user_id,
                reason, created_at
            ) VALUES (?, ?, ?, ?, 'ROLLBACK', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                principal.tenant_id,
                principal.deployment_id,
                release_sequence,
                CONFIG_SCHEMA_VERSION,
                source_map_json,
                source_map_hash,
                high_risk_action_id,
                target_set_hash,
                group_revision,
                principal.user_id,
                reason,
                now,
            ),
        )
        new_targets: list[dict[str, Any]] = []
        for source in source_rows:
            target_id = opaque_id("rlt")
            connection.execute(
                """
                INSERT INTO release_targets(
                    release_target_id, tenant_id, deployment_id,
                    release_id, screen_id,
                    canonical_effective_config_json, content_hash,
                    rollback_source_release_id, rollback_source_target_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    release_id,
                    source["screen_id"],
                    source["canonical_effective_config_json"],
                    source["content_hash"],
                    source["release_id"],
                    source["release_target_id"],
                    now,
                ),
            )
            self.owner.p2_1.copy_release_snapshot_forward(
                connection,
                source_release_target_id=source["release_target_id"],
                target_release_target_id=target_id,
                now=now,
            )
            self.owner.p2_2.copy_release_snapshot_forward(
                connection,
                source_release_target_id=source["release_target_id"],
                target_release_target_id=target_id,
                now=now,
            )
            new_targets.append(
                {
                    "screen_id": source["screen_id"],
                    "release_target_id": target_id,
                }
            )
        runtime_by_screen = {item["screen_id"]: item for item in runtime_items}
        publish_command: dict[str, Any]
        if screen_group_id is None:
            target = new_targets[0]
            runtime = runtime_by_screen[target["screen_id"]]
            publish_command = {
                "screen_id": target["screen_id"],
                "release_id": release_id,
                "release_target_id": target["release_target_id"],
                "runtime_if_match": runtime["runtime_if_match"],
                "expected_binding_generation": runtime["expected_binding_generation"],
            }
            publish_operation = "publishToScreen"
        else:
            publish_command = {
                "screen_group_id": screen_group_id,
                "release_id": release_id,
                "targets": [
                    {
                        **target,
                        "runtime_if_match": runtime_by_screen[target["screen_id"]]["runtime_if_match"],
                        "expected_binding_generation": runtime_by_screen[target["screen_id"]][
                            "expected_binding_generation"
                        ],
                    }
                    for target in new_targets
                ],
            }
            publish_operation = "publishToScreenGroup"
        published = self._execute_publication(
            connection,
            principal,
            operation_id=publish_operation,
            command=publish_command,
            high_risk_action_id=high_risk_action_id,
            reason=reason,
            now=now,
        )
        self.owner._append_audit(
            connection,
            event_type="CONFIG_ROLLBACK_RELEASE_CREATED",
            actor_type="USER",
            actor_id=principal.user_id,
            target_type="CONFIG_RELEASE",
            target_id=release_id,
            outcome="SUCCESS",
            reason=reason,
            details={
                "creation_kind": "ROLLBACK",
                "source_map_hash": source_map_hash,
                "target_set_hash": target_set_hash,
                "high_risk_action_id": high_risk_action_id,
            },
            now=now,
        )
        return {
            "kind": "CONFIG_ROLLBACK_PUBLISHED",
            "release": self._release_response(connection, principal, release_id),
            "publication": published["publication"],
        }

    # Internal recovery helpers.

    def _execute_approved_restore(
        self,
        context: Any,
        *,
        command: dict[str, Any],
        reason: str,
        idempotency_key: str,
        high_risk_action_id: str,
    ) -> dict[str, Any]:
        reason = self._reason(reason)
        operation_id = "executeRestorePlan"
        digest = self.owner._protected_digest(operation_id, command, reason)
        with self._restore_lock, self.owner.store.mutation_lock:
            with self.owner.store.connect() as connection:
                action = connection.execute(
                    """
                    SELECT * FROM high_risk_actions
                    WHERE high_risk_action_id = ?
                    """,
                    (high_risk_action_id,),
                ).fetchone()
                if action is None:
                    raise ControlPlaneError(
                        404,
                        "RESOURCE_NOT_FOUND",
                        "High-risk action was not found",
                    )
                if action["state"] == "CONSUMED":
                    if action["initiator_user_id"] != context.principal.user_id:
                        raise ControlPlaneError(
                            403,
                            "FORBIDDEN",
                            "Only the initiator may replay this restore",
                        )
                    return json.loads(action["result_json"])
                self._validate_restore_action(
                    connection,
                    context,
                    action,
                    digest,
                    command,
                )
                plan = self._restore_plan_row(
                    connection,
                    context.principal,
                    command["restore_plan_id"],
                )
                backup = self._backup_row(
                    connection,
                    context.principal,
                    plan["backup_id"],
                )
                live_security = self._capture_live_reconciliation(connection)
            started = perf_counter()
            try:
                with self.backups.staged_snapshot(backup["bundle_name"]) as (
                    staged_path,
                    snapshot,
                ):
                    self._require_backup_record_match(
                        backup,
                        manifest=snapshot.manifest,
                        manifest_hash=snapshot.manifest_hash,
                        ciphertext_hash=snapshot.ciphertext_hash,
                        safe_row_counts=snapshot.safe_row_counts,
                    )
                    now = self.owner.clock()
                    self._prepare_staged_restore(
                        staged_path,
                        live_security=live_security,
                        principal=context.principal,
                        plan=plan,
                        backup=backup,
                        action=action,
                        command=command,
                        reason=reason,
                        high_risk_action_id=high_risk_action_id,
                        idempotency_key=idempotency_key,
                        snapshot_manifest=snapshot.manifest,
                        started=started,
                        now=now,
                    )
                    result = self._cut_over_staged_store(
                        staged_path,
                        restore_plan_id=plan["restore_plan_id"],
                        high_risk_action_id=high_risk_action_id,
                        now=now,
                    )
            except BackupIntegrityError as exc:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    str(exc),
                    retryable=False,
                ) from exc
            return result

    def _validate_restore_action(
        self,
        connection: sqlite3.Connection,
        context: Any,
        action: sqlite3.Row,
        digest: str,
        command: dict[str, Any],
    ) -> None:
        if action["state"] != "APPROVED":
            raise ControlPlaneError(
                409,
                "INVALID_STATE_TRANSITION",
                "Restore action is not approved",
            )
        if action["initiator_user_id"] != context.principal.user_id:
            raise ControlPlaneError(403, "FORBIDDEN", "Only the initiator may execute restore")
        if action["operation_id"] != "executeRestorePlan" or not secrets.compare_digest(
            action["request_digest"], digest
        ):
            raise ControlPlaneError(
                409,
                "HIGH_RISK_ACTION_MISMATCH",
                "Restore command changed after approval",
            )
        if (
            action["initiator_authentication_epoch"] != context.principal.authentication_epoch
            or action["initiator_authorization_epoch"] != context.principal.authorization_epoch
        ):
            raise ControlPlaneError(
                409,
                "HIGH_RISK_ACTION_MISMATCH",
                "Restore initiator authorization changed",
            )
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
            raise ControlPlaneError(
                409,
                "HIGH_RISK_ACTION_MISMATCH",
                "Restore approver authorization changed",
            )
        plan = self._restore_plan_row(
            connection,
            context.principal,
            command["restore_plan_id"],
        )
        self.owner._require_resource_etag(
            command["if_match"],
            "restore-plan",
            plan["restore_plan_id"],
            plan["revision"],
        )
        metadata = self.owner._metadata(connection)
        if plan["state"] != "READY" or plan["expected_metadata_revision"] != metadata["revision"]:
            raise ControlPlaneError(
                412,
                "RESOURCE_VERSION_CONFLICT",
                "Restore plan or control-plane epoch changed",
            )

    def _capture_live_reconciliation(
        self,
        connection: sqlite3.Connection,
    ) -> dict[str, Any]:
        tables: dict[str, dict[str, Any]] = {}
        for table in SECURITY_RECONCILIATION_TABLES:
            columns = [row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
            rows = [
                {column: row[column] for column in columns}
                for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()
            ]
            tables[table] = {"columns": columns, "rows": rows}
        idempotency_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(idempotency_records)").fetchall()
        ]
        idempotency_rows = []
        placeholders = ", ".join("?" for _ in LIVE_RECONCILED_IDEMPOTENCY_PHASES)
        for row in connection.execute(
            f"""
            SELECT * FROM idempotency_records
            WHERE phase IN ({placeholders})
            """,
            LIVE_RECONCILED_IDEMPOTENCY_PHASES,
        ).fetchall():
            item = {column: row[column] for column in idempotency_columns}
            for name in (
                "response_nonce",
                "response_ciphertext",
                "response_encryption_key_id",
                "response_aad_json",
                "response_aad_hash",
                "response_expires_at",
            ):
                item[name] = None
            idempotency_rows.append(item)
        audit_rows = [
            dict(row)
            for row in connection.execute("SELECT * FROM security_audit_events ORDER BY sequence").fetchall()
        ]
        return {
            "tables": tables,
            "idempotency_columns": idempotency_columns,
            "idempotency_rows": idempotency_rows,
            "audit_rows": audit_rows,
        }

    def _prepare_staged_restore(
        self,
        staged_path: Path,
        *,
        live_security: dict[str, Any],
        principal: Any,
        plan: sqlite3.Row,
        backup: sqlite3.Row,
        action: sqlite3.Row,
        command: dict[str, Any],
        reason: str,
        high_risk_action_id: str,
        idempotency_key: str,
        snapshot_manifest: dict[str, Any],
        started: float,
        now: float,
    ) -> None:
        staged_store = ControlPlaneStore(staged_path)
        staged_store.initialize(now)
        with staged_store.transaction() as connection:
            self._reconcile_table(
                connection,
                "users",
                live_security["tables"]["users"],
                delete_existing=False,
            )
            self._reconcile_table(
                connection,
                "role_assignments",
                live_security["tables"]["role_assignments"],
                delete_existing=True,
            )
            connection.execute("DELETE FROM device_credentials")
            connection.execute("DELETE FROM device_enrollments")
            connection.execute("DELETE FROM device_credential_families")
            self._insert_rows(
                connection,
                "device_credential_families",
                live_security["tables"]["device_credential_families"],
            )
            self._insert_rows(
                connection,
                "device_enrollments",
                live_security["tables"]["device_enrollments"],
            )
            self._insert_rows(
                connection,
                "device_credentials",
                live_security["tables"]["device_credentials"],
            )
            connection.execute(
                """
                UPDATE device_enrollments
                SET state = 'REVOKED', revoked_at = ?,
                    revision = revision + 1
                WHERE state = 'ISSUED'
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE device_credentials
                SET state = 'REVOKED', revoked_at = ?,
                    revision = revision + 1
                WHERE state = 'PENDING_ACTIVATION'
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE device_credential_families
                SET pending_credential_id = NULL, updated_at = ?,
                    revision = revision + 1
                WHERE pending_credential_id IS NOT NULL
                """,
                (now,),
            )
            self._reconcile_table(
                connection,
                "high_risk_actions",
                live_security["tables"]["high_risk_actions"],
                delete_existing=False,
            )
            for table in ("backup_records", "restore_plans"):
                self._reconcile_table(
                    connection,
                    table,
                    live_security["tables"][table],
                    delete_existing=False,
                )
            self._insert_missing_rows(
                connection,
                "restore_executions",
                live_security["tables"]["restore_executions"],
            )
            query_authority_columns = {
                "query_secret_records": (
                    "current_version_id",
                    "state",
                    "updated_at",
                    "revision",
                ),
                "query_sources": (
                    "state",
                    "qualification_state",
                    "qualification_code",
                    "last_tested_at",
                    "updated_at",
                    "revision",
                ),
                "query_datasets": (
                    "state",
                    "updated_at",
                    "revision",
                ),
            }
            for table, update_columns in query_authority_columns.items():
                self._update_existing_rows(
                    connection,
                    table,
                    live_security["tables"][table],
                    update_columns=update_columns,
                )
            connection.execute("DELETE FROM auth_sessions")
            idempotency_phases_to_replace = (
                *LIVE_RECONCILED_IDEMPOTENCY_PHASES,
                *SESSION_IDEMPOTENCY_PHASES,
            )
            placeholders = ", ".join("?" for _ in idempotency_phases_to_replace)
            connection.execute(
                f"""
                DELETE FROM idempotency_records
                WHERE phase IN ({placeholders})
                """,
                idempotency_phases_to_replace,
            )
            self._insert_rows(
                connection,
                "idempotency_records",
                {
                    "columns": live_security["idempotency_columns"],
                    "rows": live_security["idempotency_rows"],
                },
            )
            invalidated_action_placeholders = ", ".join("?" for _ in RESTORE_INVALIDATED_DOMAIN_ACTIONS)
            connection.execute(
                f"""
                UPDATE high_risk_actions SET state = 'FAILED',
                    result_json = ?, revision = revision + 1
                WHERE (
                    state IN ('PENDING', 'APPROVED')
                    OR (
                        state = 'CONSUMED'
                        AND operation_id IN ({invalidated_action_placeholders})
                    )
                )
                  AND high_risk_action_id != ?
                """,
                (
                    canonical_json(
                        {
                            "code": "FAILED_RESTORE_EPOCH_CHANGED",
                            "state_effect": "NO_DOMAIN_EFFECT",
                        }
                    ),
                    *RESTORE_INVALIDATED_DOMAIN_ACTIONS,
                    high_risk_action_id,
                ),
            )
            self._append_audit_suffix(connection, live_security["audit_rows"])
            metadata = connection.execute(
                "SELECT * FROM control_plane_metadata WHERE singleton = 1"
            ).fetchone()
            connection.execute(
                """
                UPDATE control_plane_metadata
                SET revision = revision + 1
                WHERE singleton = 1
                """
            )
            connection.execute(
                """
                UPDATE restore_plans SET state = 'EXECUTED',
                    updated_at = ?, revision = revision + 1
                WHERE restore_plan_id = ?
                """,
                (now, plan["restore_plan_id"]),
            )
            duration_ms = max(0, int((perf_counter() - started) * 1000))
            binding_hash = self._runtime_binding_hash(connection)
            security_hash = self._security_state_hash(connection)
            retained_name = f"restore-{plan['restore_plan_id']}-previous.db"
            restore_execution_id = opaque_id("rex")
            result = {
                "api_version": "v1",
                "kind": "RESTORE_COMPLETED",
                "restore_plan_id": plan["restore_plan_id"],
                "restore_execution_id": restore_execution_id,
                "backup_id": backup["backup_id"],
                "backup_manifest_hash": backup["manifest_hash"],
                "state": "COMPLETED",
                "recovery_source_mode": "ONLINE_ACTIVE_STORE",
                "retained_previous_store": True,
                "runtime_binding_hash": binding_hash,
                "reconciled_security_hash": security_hash,
                "duration_ms": duration_ms,
                "production_recovery_certified": False,
            }
            connection.execute(
                """
                INSERT INTO restore_executions(
                    restore_execution_id, tenant_id, deployment_id,
                    restore_plan_id, backup_id, high_risk_action_id,
                    retained_previous_store_name,
                    restored_runtime_binding_hash,
                    reconciled_security_hash, duration_ms, result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?)
                """,
                (
                    restore_execution_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    plan["restore_plan_id"],
                    backup["backup_id"],
                    high_risk_action_id,
                    retained_name,
                    binding_hash,
                    security_hash,
                    duration_ms,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE high_risk_actions SET state = 'CONSUMED',
                    consumed_at = ?, result_json = ?, revision = revision + 1
                WHERE high_risk_action_id = ?
                """,
                (now, canonical_json(result), high_risk_action_id),
            )
            self.owner._append_audit(
                connection,
                event_type="RESTORE_COMPLETED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="RESTORE_PLAN",
                target_id=plan["restore_plan_id"],
                outcome="SUCCESS",
                reason=reason,
                details={
                    "backup_id": backup["backup_id"],
                    "backup_manifest_hash": backup["manifest_hash"],
                    "runtime_binding_hash": binding_hash,
                    "reconciled_security_hash": security_hash,
                    "previous_store_retained": True,
                    "source_manifest_audit_head": snapshot_manifest["authenticated_header"][
                        "audit_head_hash"
                    ],
                    "production_recovery_certified": False,
                },
                now=now,
            )
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_keys:
                raise BackupIntegrityError("Staged restore foreign-key verification failed")
            self._validate_release_hashes(connection)
            if metadata is None:
                raise BackupIntegrityError("Staged restore metadata is unavailable")
        self._checkpoint_database(staged_path)

    def _cut_over_staged_store(
        self,
        staged_path: Path,
        *,
        restore_plan_id: str,
        high_risk_action_id: str,
        now: float,
    ) -> dict[str, Any]:
        live_path = self.owner.store.path.resolve()
        retained = self.backups.backup_root / f"restore-{restore_plan_id}-previous.db"
        if retained.exists():
            raise BackupIntegrityError("Retained pre-restore store already exists")
        self._checkpoint_database(staged_path)
        staged_connection = sqlite3.connect(staged_path)
        try:
            staged_connection.row_factory = sqlite3.Row
            action = staged_connection.execute(
                """
                SELECT result_json FROM high_risk_actions
                WHERE high_risk_action_id = ?
                  AND operation_id = 'executeRestorePlan'
                  AND state = 'CONSUMED'
                  AND result_json IS NOT NULL
                """,
                (high_risk_action_id,),
            ).fetchone()
            if action is None:
                raise BackupIntegrityError("Restored result evidence is unavailable")
            result = json.loads(action["result_json"])
            if result["restore_plan_id"] != restore_plan_id:
                raise BackupIntegrityError("Restored result evidence changed")
            if staged_connection.execute("PRAGMA foreign_key_check").fetchall():
                raise BackupIntegrityError("Cut-over store foreign-key verification failed")
        finally:
            staged_connection.close()
        source = self.owner.store.connect()
        target = sqlite3.connect(retained)
        try:
            source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        self._unlink_sidecars(live_path)
        os.replace(staged_path, live_path)
        self._unlink_sidecars(live_path)
        return result

    @staticmethod
    def _reconcile_table(
        connection: sqlite3.Connection,
        table: str,
        snapshot: dict[str, Any],
        *,
        delete_existing: bool,
    ) -> None:
        if delete_existing:
            connection.execute(f'DELETE FROM "{table}"')
            P13ControlPlane._insert_rows(connection, table, snapshot)
            return
        columns = snapshot["columns"]
        if not snapshot["rows"]:
            return
        primary_keys = [
            row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall() if row["pk"]
        ]
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        update_columns = [column for column in columns if column not in primary_keys]
        conflict = ", ".join(f'"{column}"' for column in primary_keys)
        updates = ", ".join(f'"{column}" = excluded."{column}"' for column in update_columns)
        sql = (
            f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders}) '
            f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
        )
        for row in snapshot["rows"]:
            connection.execute(sql, tuple(row[column] for column in columns))

    @staticmethod
    def _insert_rows(
        connection: sqlite3.Connection,
        table: str,
        snapshot: dict[str, Any],
    ) -> None:
        columns = snapshot["columns"]
        if not snapshot["rows"]:
            return
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})'
        for row in snapshot["rows"]:
            connection.execute(sql, tuple(row[column] for column in columns))

    @staticmethod
    def _insert_missing_rows(
        connection: sqlite3.Connection,
        table: str,
        snapshot: dict[str, Any],
    ) -> None:
        columns = snapshot["columns"]
        if not snapshot["rows"]:
            return
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = f'INSERT OR IGNORE INTO "{table}" ({quoted_columns}) VALUES ({placeholders})'
        for row in snapshot["rows"]:
            connection.execute(sql, tuple(row[column] for column in columns))

    @staticmethod
    def _update_existing_rows(
        connection: sqlite3.Connection,
        table: str,
        snapshot: dict[str, Any],
        *,
        update_columns: tuple[str, ...],
    ) -> None:
        columns = snapshot["columns"]
        primary_keys = [
            row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall() if row["pk"]
        ]
        if any(column not in columns or column in primary_keys for column in update_columns):
            raise BackupIntegrityError("Restore authority snapshot is invalid")
        assignments = ", ".join(f'"{column}" = ?' for column in update_columns)
        predicates = " AND ".join(f'"{column}" = ?' for column in primary_keys)
        sql = f'UPDATE "{table}" SET {assignments} WHERE {predicates}'
        for row in snapshot["rows"]:
            connection.execute(
                sql,
                tuple(row[column] for column in (*update_columns, *primary_keys)),
            )

    @staticmethod
    def _append_audit_suffix(
        connection: sqlite3.Connection,
        live_rows: list[dict[str, Any]],
    ) -> None:
        staged = connection.execute(
            """
            SELECT sequence, event_hash FROM security_audit_events
            ORDER BY sequence DESC LIMIT 1
            """
        ).fetchone()
        staged_sequence = staged["sequence"] if staged else 0
        staged_hash = staged["event_hash"] if staged else None
        if staged_sequence:
            matching = next(
                (row for row in live_rows if row["sequence"] == staged_sequence),
                None,
            )
            if matching is None or matching["event_hash"] != staged_hash:
                raise BackupIntegrityError("Live audit history does not extend the backup")
        columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(security_audit_events)").fetchall()
        ]
        quoted = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        for row in live_rows:
            if row["sequence"] <= staged_sequence:
                continue
            connection.execute(
                f"INSERT INTO security_audit_events ({quoted}) VALUES ({placeholders})",
                tuple(row[column] for column in columns),
            )

    @staticmethod
    def _checkpoint_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.commit()
        finally:
            connection.close()
        P13ControlPlane._unlink_sidecars(path)

    @staticmethod
    def _unlink_sidecars(path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)

    # Shared row/response/validation helpers.

    def _load_draft(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        draft_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = connection.execute(
            """
            SELECT * FROM config_drafts
            WHERE draft_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (draft_id, principal.tenant_id, principal.deployment_id),
        ).fetchone()
        if row is None or not self._can_access_draft_target(
            connection,
            principal,
            row,
            permission,
        ):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Config draft was not found")
        return row

    def _can_access_draft_target(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        draft: sqlite3.Row,
        permission: str,
    ) -> bool:
        if draft["target_type"] == "SCREEN":
            screen = connection.execute(
                "SELECT site_id FROM screen_instances WHERE screen_id = ?",
                (draft["screen_id"],),
            ).fetchone()
            return bool(
                screen
                and self.owner._can_access_screen(
                    principal,
                    screen["site_id"],
                    draft["screen_id"],
                    permission,
                )
            )
        group = connection.execute(
            "SELECT site_id FROM screen_groups WHERE screen_group_id = ?",
            (draft["screen_group_id"],),
        ).fetchone()
        return bool(
            group
            and self.owner._can_access_site(
                principal,
                group["site_id"],
                permission,
            )
        )

    def _group_row(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        screen_group_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = connection.execute(
            """
            SELECT * FROM screen_groups
            WHERE screen_group_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (
                screen_group_id,
                principal.tenant_id,
                principal.deployment_id,
            ),
        ).fetchone()
        if row is None or not self.owner._can_access_site(
            principal,
            row["site_id"],
            permission,
        ):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Screen group was not found")
        return row

    def _draft_response(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        validation = (
            connection.execute(
                "SELECT * FROM validation_records WHERE validation_record_id = ?",
                (row["validation_record_id"],),
            ).fetchone()
            if row["validation_record_id"]
            else None
        )
        preview = (
            connection.execute(
                "SELECT * FROM preview_records WHERE preview_record_id = ?",
                (row["preview_record_id"],),
            ).fetchone()
            if row["preview_record_id"]
            else None
        )
        approval = (
            connection.execute(
                """
                SELECT * FROM config_approval_records
                WHERE approval_record_id = ?
                """,
                (row["approval_record_id"],),
            ).fetchone()
            if row["approval_record_id"]
            else None
        )
        return {
            "api_version": "v1",
            "draft_id": row["draft_id"],
            "target": {
                "type": row["target_type"],
                "screen_id": row["screen_id"],
                "screen_group_id": row["screen_group_id"],
            },
            "schema_version": row["schema_version"],
            "spec": json.loads(row["working_spec_json"]),
            "capability_profile": self.owner.p2_1.draft_assignment_response(
                connection,
                row["draft_id"],
                row["current_revision"],
            ),
            "query_datasets": self.owner.p2_2.draft_assignment_response(
                connection,
                row["draft_id"],
                row["current_revision"],
            ),
            "content_hash": row["content_hash"],
            "state": row["state"],
            "draft_revision": row["current_revision"],
            "resource_revision": row["revision"],
            "control_plane_epoch": row["control_plane_epoch"],
            "last_editor_user_id": row["last_editor_user_id"],
            "validation": (
                {
                    "validation_record_id": validation["validation_record_id"],
                    "outcome": validation["outcome"],
                    "findings": json.loads(validation["findings_json"]),
                    "fingerprint_hash": validation["fingerprint_hash"],
                }
                if validation
                else None
            ),
            "preview": (
                {
                    "preview_record_id": preview["preview_record_id"],
                    "outcome": preview["outcome"],
                    "evidence": json.loads(preview["evidence_json"]),
                    "fingerprint_hash": preview["fingerprint_hash"],
                }
                if preview
                else None
            ),
            "approval": (
                {
                    "approval_record_id": approval["approval_record_id"],
                    "decision": approval["decision"],
                    "approver_user_id": approval["approver_user_id"],
                    "last_editor_user_id": approval["last_editor_user_id"],
                    "reason": approval["reason"],
                }
                if approval
                else None
            ),
            "etag": self.owner._resource_etag(
                "config-draft",
                row["draft_id"],
                row["revision"],
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _release_response(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        release_id: str,
    ) -> dict[str, Any]:
        release = connection.execute(
            """
            SELECT * FROM config_releases
            WHERE release_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (release_id, principal.tenant_id, principal.deployment_id),
        ).fetchone()
        if release is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Release was not found")
        rows = connection.execute(
            """
            SELECT rt.*, s.site_id FROM release_targets rt
            JOIN screen_instances s ON s.screen_id = rt.screen_id
            WHERE rt.release_id = ?
            ORDER BY rt.screen_id
            """,
            (release_id,),
        ).fetchall()
        if not rows or any(
            not self.owner._can_access_screen(
                principal,
                row["site_id"],
                row["screen_id"],
                "config.read",
            )
            for row in rows
        ):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Release was not found")
        return {
            "api_version": "v1",
            "release_id": release["release_id"],
            "release_sequence": release["release_sequence"],
            "creation_kind": release["creation_kind"],
            "schema_version": release["schema_version"],
            "target_set_hash": release["target_set_hash"],
            "group_revision": release["group_revision"],
            "normal_provenance": (
                {
                    "draft_id": release["normal_draft_id"],
                    "draft_revision": release["normal_draft_revision"],
                    "fingerprint_id": release["normal_fingerprint_id"],
                    "approval_record_id": release["normal_approval_record_id"],
                }
                if release["creation_kind"] == "NORMAL"
                else None
            ),
            "rollback_provenance": (
                {
                    "source_map": json.loads(release["rollback_source_map_json"]),
                    "source_map_hash": release["rollback_source_map_hash"],
                    "high_risk_action_id": release["rollback_high_risk_action_id"],
                }
                if release["creation_kind"] == "ROLLBACK"
                else None
            ),
            "targets": [self._release_target_response(connection, row) for row in rows],
            "reason": release["reason"],
            "created_by_user_id": release["created_by_user_id"],
            "created_at": release["created_at"],
            "etag": self.owner._resource_etag("config-release", release_id, 1),
            "immutable": True,
        }

    def _release_target_response(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        return {
            "release_target_id": row["release_target_id"],
            "release_id": row["release_id"],
            "screen_id": row["screen_id"],
            "effective_config": json.loads(row["canonical_effective_config_json"]),
            "content_hash": row["content_hash"],
            "capability_snapshot": self.owner.p2_1.release_snapshot_response(
                connection,
                row["release_target_id"],
            ),
            "query_snapshot": self.owner.p2_2.release_snapshot_response(
                connection,
                row["release_target_id"],
            ),
            "rollback_source_release_id": row["rollback_source_release_id"],
            "rollback_source_target_id": row["rollback_source_target_id"],
            "created_at": row["created_at"],
            "immutable": True,
        }

    def _publication_response(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        publication_id: str,
    ) -> dict[str, Any]:
        publication = connection.execute(
            """
            SELECT * FROM publications
            WHERE publication_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (
                publication_id,
                principal.tenant_id,
                principal.deployment_id,
            ),
        ).fetchone()
        if publication is None:
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Publication was not found",
            )
        targets = connection.execute(
            """
            SELECT pt.*, s.site_id FROM publication_targets pt
            JOIN screen_instances s ON s.screen_id = pt.screen_id
            WHERE pt.publication_id = ?
            ORDER BY pt.screen_id
            """,
            (publication_id,),
        ).fetchall()
        if any(
            not self.owner._can_access_screen(
                principal,
                target["site_id"],
                target["screen_id"],
                "config.read",
            )
            for target in targets
        ):
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Publication was not found",
            )
        return {
            "publication_id": publication_id,
            "release_id": publication["release_id"],
            "screen_group_id": publication["screen_group_id"],
            "target_set_hash": publication["target_set_hash"],
            "group_revision": publication["group_revision"],
            "state": publication["state"],
            "reason": publication["reason"],
            "created_at": publication["created_at"],
            "immutable_plan": True,
            "targets": [
                {
                    "screen_id": target["screen_id"],
                    "release_target_id": target["release_target_id"],
                    "state": target["state"],
                    "failure_code": target["failure_code"],
                    "expected_binding_generation": target["expected_binding_generation"],
                    "resource_revision": target["revision"],
                    "etag": self.owner._resource_etag(
                        "publication-target",
                        f"{publication_id}:{target['screen_id']}",
                        target["revision"],
                    ),
                }
                for target in targets
            ],
        }

    def _require_runtime_precondition(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        screen_id: str,
        etag: str,
        generation: int,
    ) -> sqlite3.Row:
        self.owner._screen_row(
            connection,
            principal,
            screen_id,
            "release.publish" if "release.publish" in principal.permissions else "release.rollback",
        )
        binding = connection.execute(
            """
            SELECT * FROM runtime_bindings
            WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
            """,
            (principal.tenant_id, principal.deployment_id, screen_id),
        ).fetchone()
        if binding is None:
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Runtime binding was not found",
            )
        self.owner._require_resource_etag(
            etag,
            "runtime-binding",
            screen_id,
            binding["revision"],
        )
        if binding["binding_generation"] != generation:
            raise ControlPlaneError(
                412,
                "RESOURCE_VERSION_CONFLICT",
                "Runtime binding generation changed",
            )
        if binding["digital_human_instance_id"] is None:
            raise ControlPlaneError(
                409,
                "PUBLISH_TARGET_CHANGED",
                "Runtime inventory is incomplete",
            )
        return binding

    def _backup_row(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        backup_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM backup_records
            WHERE backup_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (backup_id, principal.tenant_id, principal.deployment_id),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Backup was not found")
        return row

    @staticmethod
    def _require_backup_record_match(
        backup: sqlite3.Row,
        *,
        manifest: dict[str, Any],
        manifest_hash: str,
        ciphertext_hash: str,
        safe_row_counts: dict[str, int],
    ) -> None:
        header = manifest.get("authenticated_header")
        encryption = manifest.get("encryption")
        if not isinstance(header, dict) or not isinstance(encryption, dict):
            raise BackupIntegrityError("Backup registered identity is unavailable")
        migrations = header.get("migration_versions")
        if not isinstance(migrations, list) or not all(isinstance(item, dict) for item in migrations):
            raise BackupIntegrityError("Backup registered migration identity is invalid")
        try:
            registered_migrations = json.loads(backup["migration_versions_json"])
            registered_row_counts = json.loads(backup["safe_row_counts_json"])
            observed_migrations = [item["version"] for item in migrations]
            registered_identity = {
                "backup_id": backup["backup_id"],
                "tenant_id": backup["tenant_id"],
                "deployment_id": backup["deployment_id"],
                "logical_schema_version": backup["logical_schema_version"],
                "migration_versions": registered_migrations,
                "safe_row_counts": registered_row_counts,
                "audit_head_hash": backup["audit_head_hash"],
                "recovery_encryption_key_id": backup["recovery_encryption_key_id"],
                "ciphertext_size": backup["ciphertext_size"],
                "created_at": backup["created_at"],
            }
            observed_identity = {
                "backup_id": header["backup_id"],
                "tenant_id": header["tenant_id"],
                "deployment_id": header["deployment_id"],
                "logical_schema_version": header["logical_schema_version"],
                "migration_versions": observed_migrations,
                "safe_row_counts": safe_row_counts,
                "audit_head_hash": header["audit_head_hash"],
                "recovery_encryption_key_id": header["recovery_encryption_key_id"],
                "ciphertext_size": encryption["ciphertext_size"],
                "created_at": header["created_at"],
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BackupIntegrityError("Backup registered identity is invalid") from exc
        if (
            not secrets.compare_digest(manifest_hash, backup["manifest_hash"])
            or not secrets.compare_digest(ciphertext_hash, backup["ciphertext_hash"])
            or canonical_json(observed_identity) != canonical_json(registered_identity)
        ):
            raise BackupIntegrityError("Backup bundle does not match its registered record")

    def _backup_response(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        backup_id: str,
    ) -> dict[str, Any]:
        row = self._backup_row(connection, principal, backup_id)
        return {
            "api_version": "v1",
            "backup_id": row["backup_id"],
            "state": row["state"],
            "manifest_hash": row["manifest_hash"],
            "ciphertext_hash": row["ciphertext_hash"],
            "recovery_encryption_key_id": row["recovery_encryption_key_id"],
            "logical_schema_version": row["logical_schema_version"],
            "migration_versions": json.loads(row["migration_versions_json"]),
            "safe_row_counts": json.loads(row["safe_row_counts_json"]),
            "audit_head_hash": row["audit_head_hash"],
            "ciphertext_size": row["ciphertext_size"],
            "duration_ms": row["duration_ms"],
            "reason": row["reason"],
            "created_at": row["created_at"],
            "verified_at": row["verified_at"],
            "recovery_key_in_bundle": False,
            "production_recovery_certified": False,
        }

    def _restore_plan_row(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        restore_plan_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM restore_plans
            WHERE restore_plan_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (
                restore_plan_id,
                principal.tenant_id,
                principal.deployment_id,
            ),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Restore plan was not found",
            )
        return row

    def _restore_plan_response(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        restore_plan_id: str,
    ) -> dict[str, Any]:
        row = self._restore_plan_row(connection, principal, restore_plan_id)
        return {
            "api_version": "v1",
            "restore_plan_id": row["restore_plan_id"],
            "backup_id": row["backup_id"],
            "backup_manifest_hash": row["backup_manifest_hash"],
            "recovery_source_mode": row["recovery_source_mode"],
            "authorization_mode": row["authorization_mode"],
            "findings": json.loads(row["findings_json"]),
            "state": row["state"],
            "resource_revision": row["revision"],
            "etag": self.owner._resource_etag(
                "restore-plan",
                restore_plan_id,
                row["revision"],
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _validate_spec(self, spec: dict[str, Any]) -> str:
        if set(spec) != CONFIG_FIELDS:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Config spec must contain exactly welcome_text and fvs_binding_ref",
            )
        welcome = spec["welcome_text"]
        if not isinstance(welcome, str) or not 1 <= len(welcome.strip()) <= 500 or not welcome.isprintable():
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "welcome_text must be a printable string of 1 to 500 characters",
            )
        try:
            fvs_ref = self.owner._validate_fvs_binding_ref(spec["fvs_binding_ref"])
        except (TypeError, ValueError) as exc:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "fvs_binding_ref is invalid or sensitive",
            ) from exc
        if not fvs_ref:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "fvs_binding_ref is required",
            )
        return canonical_json(
            {
                "welcome_text": welcome.strip(),
                "fvs_binding_ref": fvs_ref,
            }
        )

    def _require_any_edit_permission(self, principal: Any) -> None:
        if (
            not {
                "config.edit_business",
                "config.edit_technical",
            }
            & principal.permissions
        ):
            raise ControlPlaneError(403, "FORBIDDEN", "Permission denied")

    def _available_edit_permission(self, principal: Any) -> str:
        if "config.edit_business" in principal.permissions:
            return "config.edit_business"
        return "config.edit_technical"

    def _require_all_spec_edit_permissions(self, principal: Any) -> None:
        self.owner.require_permission(principal, "config.edit_business")
        self.owner.require_permission(principal, "config.edit_technical")

    @staticmethod
    def _reason(value: str) -> str:
        reason = value.strip()
        if not 3 <= len(reason) <= 500:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Reason must contain 3 to 500 characters",
            )
        return reason

    @staticmethod
    def _action_reason(
        connection: sqlite3.Connection,
        high_risk_action_id: str,
    ) -> str:
        row = connection.execute(
            "SELECT reason FROM high_risk_actions WHERE high_risk_action_id = ?",
            (high_risk_action_id,),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "High-risk action was not found",
            )
        return row["reason"]

    @staticmethod
    def _next_release_sequence(
        connection: sqlite3.Connection,
        principal: Any,
    ) -> int:
        row = connection.execute(
            """
            SELECT MAX(release_sequence) AS sequence FROM config_releases
            WHERE tenant_id = ? AND deployment_id = ?
            """,
            (principal.tenant_id, principal.deployment_id),
        ).fetchone()
        return int(row["sequence"] or 0) + 1

    @staticmethod
    def _runtime_binding_hash(connection: sqlite3.Connection) -> str:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT screen_id, digital_human_instance_id,
                    desired_release_target_id, applied_release_target_id,
                    binding_generation, last_acknowledged_marker,
                    last_acknowledged_at, inventory_status, revision
                FROM runtime_bindings ORDER BY screen_id
                """
            ).fetchall()
        ]
        return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()

    @staticmethod
    def _security_state_hash(connection: sqlite3.Connection) -> str:
        state = {
            "users": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT user_id, account_state, credential_generation,
                        authentication_epoch, authorization_epoch,
                        account_state_generation, revision
                    FROM users ORDER BY user_id
                    """
                ).fetchall()
            ],
            "roles": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT user_id, role_id, scope_type, scope_id
                    FROM role_assignments
                    ORDER BY user_id, role_id, scope_type, scope_id
                    """
                ).fetchall()
            ],
            "device_families": [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT family_id, screen_id, state, credential_epoch,
                        active_credential_id, pending_credential_id, revision
                    FROM device_credential_families ORDER BY family_id
                    """
                ).fetchall()
            ],
        }
        return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_release_hashes(connection: sqlite3.Connection) -> None:
        for row in connection.execute(
            """
            SELECT canonical_effective_config_json, content_hash
            FROM release_targets
            """
        ).fetchall():
            actual = hashlib.sha256(row["canonical_effective_config_json"].encode("utf-8")).hexdigest()
            if actual != row["content_hash"]:
                raise BackupIntegrityError("Staged restore release hash changed")
        BackupManager._validate_p21_capability_data(connection)
        BackupManager._validate_p22_query_data(connection)
