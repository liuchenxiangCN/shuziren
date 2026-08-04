from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import sqlite3
from pathlib import PurePosixPath
from typing import Any

from app.control_plane.errors import ControlPlaneError
from app.control_plane.security import canonical_json, opaque_id

RENDERER_REGISTRY_VERSION = "p3_renderer_registry_001"
AVATAR_SCHEMA_VERSION = "p3_avatar_package_v1"
TEST_RENDERER_TYPE = "test_card"
TEST_RENDERER_VERSION = "1.0.0"
TEST_RENDERER_RANGE = "^1.0.0"
TEST_RESOURCE_MEDIA_TYPE = "application/vnd.shuziren.test-avatar+json"
TEST_PREVIEW_SCHEMA_VERSION = "p3_test_avatar_preview_v1"
MAX_PACKAGE_BYTES = 2 * 1024 * 1024
MAX_RESOURCE_FILES = 16
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REQUIRED_STATES = ("idle", "listening", "thinking", "speaking", "error")

RENDERERS = (
    {
        "renderer_type": TEST_RENDERER_TYPE,
        "display_name": "内置测试卡片 Renderer",
        "renderer_version": TEST_RENDERER_VERSION,
        "registry_version": RENDERER_REGISTRY_VERSION,
        "contract_version": TEST_RENDERER_VERSION,
        "state": "available",
        "test_only": True,
        "supported_avatar_types": ["test"],
        "supported_manifest_schema_versions": [AVATAR_SCHEMA_VERSION],
        "supported_media_types": [TEST_RESOURCE_MEDIA_TYPE],
        "production_eligible": False,
        "compatibility_note": "仅验证扩展、预览和安全切换契约，不代表真实 2D/3D 支持",
    },
)


class P3ControlPlane:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def list_renderers(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        return {
            "api_version": "v1",
            "registry_version": RENDERER_REGISTRY_VERSION,
            "items": [dict(item) for item in RENDERERS],
        }

    def list_packages(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM avatar_packages
                WHERE tenant_id = ? AND deployment_id = ?
                ORDER BY site_id, display_name, package_id
                """,
                (principal.tenant_id, principal.deployment_id),
            ).fetchall()
            return {
                "api_version": "v1",
                "items": [
                    self._package_response(connection, row)
                    for row in rows
                    if self.owner._can_access_site(principal, row["site_id"], "config.read")
                ],
            }

    def create_package_version(
        self,
        principal: Any,
        *,
        site_id: str,
        manifest: dict[str, Any],
        files: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        validated = self._validate_package(manifest, files)
        command = {
            "site_id": site_id,
            "manifest": validated["manifest"],
            "resource_digests": [
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "size_bytes": item["size_bytes"],
                }
                for item in validated["resources"]
            ],
        }
        operation_id = "createAvatarPackageVersion"
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            self.owner._site_row(connection, principal, site_id, "config.edit_technical")
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])

            package = connection.execute(
                """
                SELECT * FROM avatar_packages
                WHERE tenant_id = ? AND deployment_id = ? AND site_id = ? AND avatar_id = ?
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    site_id,
                    validated["manifest"]["avatar_id"],
                ),
            ).fetchone()
            if package is None:
                package_id = opaque_id("avp")
                connection.execute(
                    """
                    INSERT INTO avatar_packages(
                        package_id, tenant_id, deployment_id, site_id, avatar_id,
                        display_name, created_by_user_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        package_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        site_id,
                        validated["manifest"]["avatar_id"],
                        validated["manifest"]["display_name"],
                        principal.user_id,
                        now,
                    ),
                )
            else:
                package_id = package["package_id"]
                if package["display_name"] != validated["manifest"]["display_name"]:
                    raise ControlPlaneError(
                        409,
                        "IMMUTABLE_RESOURCE_CONFLICT",
                        "Avatar display name is immutable across versions",
                    )
            duplicate = connection.execute(
                """
                SELECT 1 FROM avatar_package_versions
                WHERE package_id = ? AND version = ?
                """,
                (package_id, validated["manifest"]["version"]),
            ).fetchone()
            if duplicate is not None:
                raise ControlPlaneError(
                    409,
                    "IMMUTABLE_RESOURCE_CONFLICT",
                    "Avatar package version already exists",
                )
            package_version_id = opaque_id("avv")
            connection.execute(
                """
                INSERT INTO avatar_package_versions(
                    package_version_id, package_id, tenant_id, deployment_id, site_id,
                    version, schema_version, renderer_type, renderer_contract_version,
                    avatar_type, canonical_manifest_json, manifest_hash, content_hash,
                    canonical_preview_json, total_bytes, created_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    package_version_id,
                    package_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    site_id,
                    validated["manifest"]["version"],
                    AVATAR_SCHEMA_VERSION,
                    TEST_RENDERER_TYPE,
                    TEST_RENDERER_VERSION,
                    "test",
                    validated["canonical_manifest"],
                    validated["manifest_hash"],
                    validated["content_hash"],
                    canonical_json(validated["preview"]),
                    validated["total_bytes"],
                    principal.user_id,
                    now,
                ),
            )
            for resource in validated["resources"]:
                connection.execute(
                    """
                    INSERT INTO avatar_package_resources(
                        package_version_id, resource_path, media_type,
                        size_bytes, sha256, content_blob
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        package_version_id,
                        resource["path"],
                        resource["media_type"],
                        resource["size_bytes"],
                        resource["sha256"],
                        resource["content"],
                    ),
                )
            version = connection.execute(
                "SELECT * FROM avatar_package_versions WHERE package_version_id = ?",
                (package_version_id,),
            ).fetchone()
            result = self._version_response(connection, version)
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
                event_type="AVATAR_PACKAGE_VERSION_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="AVATAR_PACKAGE_VERSION",
                target_id=package_version_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "site_id": site_id,
                    "package_id": package_id,
                    "version": validated["manifest"]["version"],
                    "renderer_type": TEST_RENDERER_TYPE,
                    "content_hash": validated["content_hash"],
                    "test_only": True,
                },
                now=now,
            )
            return result

    def get_package_preview(
        self,
        principal: Any,
        package_version_id: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            row = self._load_version(
                connection,
                principal,
                package_version_id,
                "config.read",
            )
            response = self._version_response(connection, row)
            return {
                "api_version": "v1",
                "package_version_id": package_version_id,
                "renderer_type": response["renderer_type"],
                "renderer_version": response["renderer_contract_version"],
                "test_only": True,
                "production_eligible": False,
                "manifest_hash": response["manifest_hash"],
                "content_hash": response["content_hash"],
                "resources": response["resources"],
                "preview_model": response["preview_model"],
            }

    def prefetch(
        self,
        principal: Any,
        screen_id: str,
        package_version_id: str,
        *,
        expected_content_hash: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.preview")
        expected_content_hash = expected_content_hash.strip().lower()
        if not SHA256_RE.fullmatch(expected_content_hash):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Content hash is invalid")
        operation_id = "prefetchAvatarPackage"
        command = {
            "screen_id": screen_id,
            "package_version_id": package_version_id,
            "expected_content_hash": expected_content_hash,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            screen = self.owner._screen_row(connection, principal, screen_id, "config.preview")
            version = self._load_version(
                connection,
                principal,
                package_version_id,
                "config.preview",
            )
            if version["site_id"] != screen["site_id"]:
                raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Avatar package was not found")
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])

            verified = self._verified_version(connection, version)
            if expected_content_hash == verified["content_hash"]:
                outcome = "READY"
                failure_code = None
            else:
                outcome = "FAILED"
                failure_code = "CONTENT_HASH_MISMATCH"
            prefetch_id = opaque_id("avf")
            connection.execute(
                """
                INSERT INTO avatar_prefetch_records(
                    prefetch_id, tenant_id, deployment_id, site_id, screen_id,
                    package_version_id, expected_content_hash, outcome, failure_code,
                    requested_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prefetch_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    screen["site_id"],
                    screen_id,
                    package_version_id,
                    expected_content_hash,
                    outcome,
                    failure_code,
                    principal.user_id,
                    now,
                ),
            )
            result = {
                "api_version": "v1",
                "prefetch_id": prefetch_id,
                "screen_id": screen_id,
                "package_version_id": package_version_id,
                "expected_content_hash": expected_content_hash,
                "verified_content_hash": verified["content_hash"],
                "outcome": outcome,
                "failure": (
                    None
                    if failure_code is None
                    else {
                        "code": failure_code,
                        "message": "资源指纹不匹配；当前形象未发生变化",
                    }
                ),
                "created_at": now,
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
                event_type="AVATAR_PACKAGE_PREFETCHED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="SCREEN",
                target_id=screen_id,
                outcome="SUCCESS" if outcome == "READY" else "DENIED",
                reason=failure_code,
                details={
                    "package_version_id": package_version_id,
                    "content_hash": verified["content_hash"],
                    "prefetch_outcome": outcome,
                },
                now=now,
            )
            return result

    def get_binding(self, principal: Any, screen_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            self.owner._screen_row(connection, principal, screen_id, "config.read")
            return self._binding_response(connection, screen_id)

    def publish(
        self,
        principal: Any,
        screen_id: str,
        *,
        package_version_id: str,
        expected_binding_generation: int,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._switch(
            principal,
            screen_id,
            package_version_id=package_version_id,
            expected_binding_generation=expected_binding_generation,
            reason=reason,
            if_match=if_match,
            idempotency_key=idempotency_key,
            operation="PUBLISH",
        )

    def rollback(
        self,
        principal: Any,
        screen_id: str,
        *,
        expected_binding_generation: int,
        reason: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "release.rollback")
        reason = self._public_text(reason, "Reason", minimum=3, maximum=500)
        operation_id = "rollbackAvatarOnScreen"
        command = {
            "screen_id": screen_id,
            "expected_binding_generation": expected_binding_generation,
            "reason": reason,
            "if_match": if_match,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            self.owner._screen_row(connection, principal, screen_id, "release.rollback")
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            binding = connection.execute(
                "SELECT * FROM screen_avatar_bindings WHERE screen_id = ?",
                (screen_id,),
            ).fetchone()
            if binding is None or binding["previous_package_version_id"] is None:
                raise ControlPlaneError(
                    409,
                    "ROLLBACK_TARGET_UNAVAILABLE",
                    "No previous verified avatar version is available",
                )
            self._require_binding_version(
                binding,
                screen_id,
                expected_binding_generation,
                if_match,
            )
            target_version_id = binding["previous_package_version_id"]
            target = connection.execute(
                "SELECT * FROM avatar_package_versions WHERE package_version_id = ?",
                (target_version_id,),
            ).fetchone()
            if target is None:
                raise ControlPlaneError(
                    503, "CRYPTOGRAPHIC_INTEGRITY_FAILURE", "Avatar rollback target is unavailable"
                )
            self._verified_version(connection, target)
            self._require_ready_prefetch(connection, screen_id, target)
            generation = binding["binding_generation"] + 1
            from_version_id = binding["current_package_version_id"]
            connection.execute(
                """
                UPDATE screen_avatar_bindings
                SET current_package_version_id = ?, previous_package_version_id = ?,
                    binding_generation = ?, updated_by_user_id = ?, updated_at = ?
                WHERE screen_id = ?
                """,
                (
                    target_version_id,
                    from_version_id,
                    generation,
                    principal.user_id,
                    now,
                    screen_id,
                ),
            )
            self._record_switch(
                connection,
                principal,
                screen_id=screen_id,
                site_id=binding["site_id"],
                from_version_id=from_version_id,
                to_version_id=target_version_id,
                operation="ROLLBACK",
                generation=generation,
                reason=reason,
                now=now,
            )
            result = self._binding_response(connection, screen_id)
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

    def get_device_current_avatar(self, context: Any) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            screen = connection.execute(
                """
                SELECT * FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (context.tenant_id, context.deployment_id, context.screen_id),
            ).fetchone()
            if screen is None:
                raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Screen was not found")
            response = self._binding_response(connection, context.screen_id, include_history=False)
            return {
                "api_version": "v1",
                "screen_id": context.screen_id,
                "state": response["state"],
                "binding_generation": response["binding_generation"],
                "current": response["current"],
                "etag": response["etag"],
            }

    def _switch(
        self,
        principal: Any,
        screen_id: str,
        *,
        package_version_id: str,
        expected_binding_generation: int,
        reason: str,
        if_match: str,
        idempotency_key: str,
        operation: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "release.publish")
        reason = self._public_text(reason, "Reason", minimum=3, maximum=500)
        operation_id = "publishAvatarToScreen"
        command = {
            "screen_id": screen_id,
            "package_version_id": package_version_id,
            "expected_binding_generation": expected_binding_generation,
            "reason": reason,
            "if_match": if_match,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            screen = self.owner._screen_row(connection, principal, screen_id, "release.publish")
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            version = self._load_version(
                connection,
                principal,
                package_version_id,
                "release.publish",
            )
            if version["site_id"] != screen["site_id"]:
                raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Avatar package was not found")
            self._verified_version(connection, version)
            self._require_ready_prefetch(connection, screen_id, version)
            binding = connection.execute(
                "SELECT * FROM screen_avatar_bindings WHERE screen_id = ?",
                (screen_id,),
            ).fetchone()
            self._require_binding_version(
                binding,
                screen_id,
                expected_binding_generation,
                if_match,
            )
            from_version_id = binding["current_package_version_id"] if binding else None
            if from_version_id == package_version_id:
                raise ControlPlaneError(409, "INVALID_STATE_TRANSITION", "Avatar version is already active")
            generation = expected_binding_generation + 1
            if binding is None:
                connection.execute(
                    """
                    INSERT INTO screen_avatar_bindings(
                        screen_id, tenant_id, deployment_id, site_id,
                        current_package_version_id, previous_package_version_id,
                        binding_generation, updated_by_user_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        screen_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        screen["site_id"],
                        package_version_id,
                        generation,
                        principal.user_id,
                        now,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE screen_avatar_bindings
                    SET current_package_version_id = ?, previous_package_version_id = ?,
                        binding_generation = ?, updated_by_user_id = ?, updated_at = ?
                    WHERE screen_id = ?
                    """,
                    (
                        package_version_id,
                        from_version_id,
                        generation,
                        principal.user_id,
                        now,
                        screen_id,
                    ),
                )
            self._record_switch(
                connection,
                principal,
                screen_id=screen_id,
                site_id=screen["site_id"],
                from_version_id=from_version_id,
                to_version_id=package_version_id,
                operation=operation,
                generation=generation,
                reason=reason,
                now=now,
            )
            result = self._binding_response(connection, screen_id)
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

    def _record_switch(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        *,
        screen_id: str,
        site_id: str,
        from_version_id: str | None,
        to_version_id: str,
        operation: str,
        generation: int,
        reason: str,
        now: float,
    ) -> None:
        switch_id = opaque_id("avs")
        connection.execute(
            """
            INSERT INTO avatar_switch_records(
                switch_id, tenant_id, deployment_id, site_id, screen_id,
                from_package_version_id, to_package_version_id, operation,
                outcome, binding_generation, reason, actor_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUCCEEDED', ?, ?, ?, ?)
            """,
            (
                switch_id,
                principal.tenant_id,
                principal.deployment_id,
                site_id,
                screen_id,
                from_version_id,
                to_version_id,
                operation,
                generation,
                reason,
                principal.user_id,
                now,
            ),
        )
        self.owner._append_audit(
            connection,
            event_type=f"AVATAR_{operation}_SUCCEEDED",
            actor_type="USER",
            actor_id=principal.user_id,
            target_type="SCREEN",
            target_id=screen_id,
            outcome="SUCCESS",
            reason=reason,
            details={
                "switch_id": switch_id,
                "from_package_version_id": from_version_id,
                "to_package_version_id": to_version_id,
                "binding_generation": generation,
                "test_only": True,
            },
            now=now,
        )

    def _require_ready_prefetch(
        self,
        connection: sqlite3.Connection,
        screen_id: str,
        version: sqlite3.Row,
    ) -> None:
        row = connection.execute(
            """
            SELECT * FROM avatar_prefetch_records
            WHERE screen_id = ? AND package_version_id = ?
              AND outcome = 'READY' AND expected_content_hash = ?
            ORDER BY created_at DESC, prefetch_id DESC LIMIT 1
            """,
            (screen_id, version["package_version_id"], version["content_hash"]),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(
                409,
                "AVATAR_PREFETCH_REQUIRED",
                "The exact avatar package must be prefetched successfully before publishing",
            )

    def _require_binding_version(
        self,
        binding: sqlite3.Row | None,
        screen_id: str,
        expected_generation: int,
        if_match: str,
    ) -> None:
        actual_generation = binding["binding_generation"] if binding else 0
        if expected_generation != actual_generation:
            raise ControlPlaneError(
                409,
                "RESOURCE_VERSION_CONFLICT",
                "Avatar binding generation changed",
                details={"expected_binding_generation": actual_generation},
            )
        self.owner._require_resource_etag(
            if_match,
            "avatar-binding",
            screen_id,
            actual_generation,
        )

    def _load_version(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        package_version_id: str,
        permission: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM avatar_package_versions
            WHERE package_version_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (package_version_id, principal.tenant_id, principal.deployment_id),
        ).fetchone()
        if row is None or not self.owner._can_access_site(principal, row["site_id"], permission):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Avatar package was not found")
        return row

    def _package_response(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        versions = connection.execute(
            """
            SELECT * FROM avatar_package_versions
            WHERE package_id = ? ORDER BY created_at DESC, package_version_id DESC
            """,
            (row["package_id"],),
        ).fetchall()
        return {
            "api_version": "v1",
            "package_id": row["package_id"],
            "site_id": row["site_id"],
            "avatar_id": row["avatar_id"],
            "display_name": row["display_name"],
            "test_only": True,
            "immutable": True,
            "versions": [self._version_response(connection, version) for version in versions],
            "created_at": row["created_at"],
        }

    def _version_response(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        verified = self._verified_version(connection, row)
        manifest = verified["manifest"]
        return {
            "api_version": "v1",
            "package_version_id": row["package_version_id"],
            "package_id": row["package_id"],
            "site_id": row["site_id"],
            "avatar_id": manifest["avatar_id"],
            "display_name": manifest["display_name"],
            "version": row["version"],
            "schema_version": row["schema_version"],
            "renderer_type": row["renderer_type"],
            "renderer_contract_version": row["renderer_contract_version"],
            "avatar_type": row["avatar_type"],
            "manifest_hash": row["manifest_hash"],
            "content_hash": row["content_hash"],
            "total_bytes": row["total_bytes"],
            "resources": verified["resources"],
            "preview_model": verified["preview"],
            "test_only": True,
            "production_eligible": False,
            "immutable": True,
            "created_at": row["created_at"],
        }

    def _binding_response(
        self,
        connection: sqlite3.Connection,
        screen_id: str,
        *,
        include_history: bool = True,
    ) -> dict[str, Any]:
        binding = connection.execute(
            "SELECT * FROM screen_avatar_bindings WHERE screen_id = ?",
            (screen_id,),
        ).fetchone()
        generation = binding["binding_generation"] if binding else 0
        result: dict[str, Any] = {
            "api_version": "v1",
            "screen_id": screen_id,
            "state": "ACTIVE" if binding else "UNBOUND",
            "binding_generation": generation,
            "current": None,
            "previous": None,
            "etag": self.owner._resource_etag("avatar-binding", screen_id, generation),
        }
        if binding:
            current = connection.execute(
                "SELECT * FROM avatar_package_versions WHERE package_version_id = ?",
                (binding["current_package_version_id"],),
            ).fetchone()
            previous = (
                connection.execute(
                    "SELECT * FROM avatar_package_versions WHERE package_version_id = ?",
                    (binding["previous_package_version_id"],),
                ).fetchone()
                if binding["previous_package_version_id"]
                else None
            )
            if current is None:
                raise ControlPlaneError(
                    503, "CRYPTOGRAPHIC_INTEGRITY_FAILURE", "Avatar binding target is unavailable"
                )
            result["current"] = self._version_response(connection, current)
            result["previous"] = self._version_response(connection, previous) if previous else None
            result["updated_at"] = binding["updated_at"]
        if include_history:
            history = connection.execute(
                """
                SELECT * FROM avatar_switch_records
                WHERE screen_id = ? ORDER BY created_at DESC, switch_id DESC LIMIT 20
                """,
                (screen_id,),
            ).fetchall()
            result["history"] = [
                {
                    "switch_id": row["switch_id"],
                    "from_package_version_id": row["from_package_version_id"],
                    "to_package_version_id": row["to_package_version_id"],
                    "operation": row["operation"],
                    "outcome": row["outcome"],
                    "binding_generation": row["binding_generation"],
                    "reason": row["reason"],
                    "created_at": row["created_at"],
                }
                for row in history
            ]
        return result

    def _verified_version(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        try:
            manifest = json.loads(row["canonical_manifest_json"])
            preview = json.loads(row["canonical_preview_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Avatar package metadata failed integrity validation",
                retryable=False,
            ) from exc
        canonical_manifest = canonical_json(manifest)
        if hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest() != row["manifest_hash"]:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Avatar manifest failed integrity validation",
                retryable=False,
            )
        resources = connection.execute(
            """
            SELECT * FROM avatar_package_resources
            WHERE package_version_id = ? ORDER BY resource_path
            """,
            (row["package_version_id"],),
        ).fetchall()
        if not resources:
            raise ControlPlaneError(
                503, "CRYPTOGRAPHIC_INTEGRITY_FAILURE", "Avatar resources are unavailable", retryable=False
            )
        resource_digests = []
        resource_metadata = []
        total_bytes = 0
        for resource in resources:
            content = bytes(resource["content_blob"])
            digest = hashlib.sha256(content).hexdigest()
            if digest != resource["sha256"] or len(content) != resource["size_bytes"]:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    "Avatar resource failed integrity validation",
                    retryable=False,
                )
            total_bytes += len(content)
            resource_digests.append(
                {
                    "path": resource["resource_path"],
                    "sha256": digest,
                    "size_bytes": len(content),
                }
            )
            resource_metadata.append(
                {
                    "path": resource["resource_path"],
                    "media_type": resource["media_type"],
                    "size_bytes": len(content),
                    "sha256": digest,
                }
            )
        content_hash = self._content_hash(manifest, resource_digests)
        if content_hash != row["content_hash"] or total_bytes != row["total_bytes"]:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Avatar package failed integrity validation",
                retryable=False,
            )
        if canonical_json(preview) != row["canonical_preview_json"]:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Avatar preview failed integrity validation",
                retryable=False,
            )
        return {
            "manifest": manifest,
            "preview": preview,
            "content_hash": content_hash,
            "resources": resource_metadata,
        }

    def _validate_package(
        self,
        manifest: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if manifest.get("schema_version") != AVATAR_SCHEMA_VERSION:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Unsupported avatar manifest schema")
        avatar_id = str(manifest.get("avatar_id", "")).strip()
        if not IDENTIFIER_RE.fullmatch(avatar_id):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar ID is invalid")
        version = str(manifest.get("version", "")).strip()
        if not SEMVER_RE.fullmatch(version):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar version must be semantic x.y.z")
        manifest["avatar_id"] = avatar_id
        manifest["version"] = version
        manifest["display_name"] = self._public_text(
            str(manifest.get("display_name", "")),
            "Display name",
            minimum=1,
            maximum=128,
        )
        if manifest.get("avatar_type") != "test":
            raise ControlPlaneError(
                422, "UNSUPPORTED_AVATAR_TYPE", "Only the test avatar type is available in P3"
            )
        if manifest.get("renderer_type") != TEST_RENDERER_TYPE:
            raise ControlPlaneError(422, "UNKNOWN_RENDERER", "Renderer is not registered")
        if manifest.get("renderer_version_range") != TEST_RENDERER_RANGE:
            raise ControlPlaneError(422, "INCOMPATIBLE_RENDERER", "Renderer version range is not compatible")
        if manifest.get("lip_sync_mode") != "volume":
            raise ControlPlaneError(
                422, "SCHEMA_VALIDATION_FAILED", "Only volume-driven test lip sync is supported"
            )
        entry_asset = self._safe_resource_path(str(manifest.get("entry_asset", "")))
        manifest["entry_asset"] = entry_asset
        states = manifest.get("states")
        if not isinstance(states, dict) or set(states) != set(REQUIRED_STATES):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar state mapping is incomplete")
        normalized_states = {state: self._safe_resource_path(str(states[state])) for state in REQUIRED_STATES}
        if any(path != entry_asset for path in normalized_states.values()):
            raise ControlPlaneError(
                422, "SCHEMA_VALIDATION_FAILED", "Test avatar states must use the entry asset"
            )
        manifest["states"] = normalized_states
        license_info = manifest.get("license")
        if not isinstance(license_info, dict) or license_info.get("kind") != "TEST_ONLY":
            raise ControlPlaneError(422, "LICENSE_NOT_ELIGIBLE", "P3 accepts only generated test-only assets")
        if license_info.get("usage_scope") != "DEVELOPMENT_PREVIEW":
            raise ControlPlaneError(422, "LICENSE_NOT_ELIGIBLE", "Test asset usage scope is invalid")
        resources_manifest = manifest.get("resources")
        if not isinstance(resources_manifest, list) or not resources_manifest:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar resources are required")
        if len(resources_manifest) > MAX_RESOURCE_FILES or len(files) > MAX_RESOURCE_FILES:
            raise ControlPlaneError(413, "PACKAGE_TOO_LARGE", "Avatar package contains too many resources")
        if len(resources_manifest) != len(files):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Manifest and uploaded resources differ")

        file_map: dict[str, bytes] = {}
        for item in files:
            path = self._safe_resource_path(str(item.get("path", "")))
            if path in file_map:
                raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Duplicate avatar resource path")
            encoded = item.get("content_base64")
            if not isinstance(encoded, str) or len(encoded) > (MAX_PACKAGE_BYTES * 2):
                raise ControlPlaneError(413, "PACKAGE_TOO_LARGE", "Avatar resource is too large")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ControlPlaneError(
                    422, "SCHEMA_VALIDATION_FAILED", "Avatar resource encoding is invalid"
                ) from exc
            if not content:
                raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar resource is empty")
            file_map[path] = content

        normalized_resources: list[dict[str, Any]] = []
        manifest_paths: set[str] = set()
        total_bytes = 0
        for item in resources_manifest:
            if not isinstance(item, dict):
                raise ControlPlaneError(
                    422, "SCHEMA_VALIDATION_FAILED", "Avatar resource metadata is invalid"
                )
            path = self._safe_resource_path(str(item.get("path", "")))
            if path in manifest_paths:
                raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Duplicate avatar resource path")
            manifest_paths.add(path)
            if item.get("media_type") != TEST_RESOURCE_MEDIA_TYPE:
                raise ControlPlaneError(
                    422, "EXECUTABLE_RESOURCE_REJECTED", "Avatar resource media type is not allowed"
                )
            content = file_map.get(path)
            if content is None:
                raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Manifest resource was not uploaded")
            size_bytes = item.get("size_bytes")
            sha256 = str(item.get("sha256", "")).lower()
            if size_bytes != len(content) or not SHA256_RE.fullmatch(sha256):
                raise ControlPlaneError(
                    422, "RESOURCE_INTEGRITY_FAILED", "Avatar resource metadata does not match"
                )
            actual_sha256 = hashlib.sha256(content).hexdigest()
            if actual_sha256 != sha256:
                raise ControlPlaneError(
                    422, "RESOURCE_INTEGRITY_FAILED", "Avatar resource hash does not match"
                )
            total_bytes += len(content)
            if total_bytes > MAX_PACKAGE_BYTES:
                raise ControlPlaneError(413, "PACKAGE_TOO_LARGE", "Avatar package exceeds the byte limit")
            normalized_resources.append(
                {
                    "path": path,
                    "media_type": TEST_RESOURCE_MEDIA_TYPE,
                    "size_bytes": len(content),
                    "sha256": actual_sha256,
                    "content": content,
                }
            )
        if set(file_map) != manifest_paths or entry_asset not in manifest_paths:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Avatar resource set is invalid")
        if len(normalized_resources) != 1 or entry_asset != "avatar.json":
            raise ControlPlaneError(
                422, "EXECUTABLE_RESOURCE_REJECTED", "The P3 test Renderer accepts only avatar.json"
            )
        preview = self._parse_preview(file_map[entry_asset])
        manifest["resources"] = [
            {key: item[key] for key in ("path", "media_type", "size_bytes", "sha256")}
            for item in normalized_resources
        ]
        canonical_manifest = canonical_json(manifest)
        resource_digests = [
            {key: item[key] for key in ("path", "sha256", "size_bytes")} for item in normalized_resources
        ]
        return {
            "manifest": manifest,
            "canonical_manifest": canonical_manifest,
            "manifest_hash": hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest(),
            "content_hash": self._content_hash(manifest, resource_digests),
            "resources": normalized_resources,
            "preview": preview,
            "total_bytes": total_bytes,
        }

    @staticmethod
    def _parse_preview(content: bytes) -> dict[str, Any]:
        try:
            preview = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlPlaneError(
                422, "SCHEMA_VALIDATION_FAILED", "Test avatar preview JSON is invalid"
            ) from exc
        if not isinstance(preview, dict) or set(preview) != {
            "schema_version",
            "label",
            "background",
            "accent",
        }:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Test avatar preview schema is invalid")
        if preview["schema_version"] != TEST_PREVIEW_SCHEMA_VERSION:
            raise ControlPlaneError(
                422, "SCHEMA_VALIDATION_FAILED", "Test avatar preview version is unsupported"
            )
        label = P3ControlPlane._public_text(str(preview["label"]), "Preview label", minimum=1, maximum=64)
        if not COLOR_RE.fullmatch(str(preview["background"])) or not COLOR_RE.fullmatch(
            str(preview["accent"])
        ):
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Test avatar preview color is invalid")
        return {
            "schema_version": TEST_PREVIEW_SCHEMA_VERSION,
            "label": label,
            "background": str(preview["background"]).upper(),
            "accent": str(preview["accent"]).upper(),
        }

    @staticmethod
    def _safe_resource_path(value: str) -> str:
        path = value.strip()
        lowered = path.casefold()
        blocked_suffixes = (
            ".js",
            ".mjs",
            ".cjs",
            ".wasm",
            ".html",
            ".htm",
            ".css",
            ".svg",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dll",
            ".ps1",
            ".sh",
        )
        candidate = PurePosixPath(path)
        if (
            not path
            or len(path) > 128
            or "\\" in path
            or "%" in path
            or path.startswith("/")
            or path != candidate.as_posix()
            or any(part in {"", ".", ".."} for part in candidate.parts)
            or lowered.endswith(blocked_suffixes)
            or not lowered.endswith(".json")
        ):
            raise ControlPlaneError(
                422, "EXECUTABLE_RESOURCE_REJECTED", "Avatar resource path or type is not allowed"
            )
        return path

    @staticmethod
    def _content_hash(manifest: dict[str, Any], resources: list[dict[str, Any]]) -> str:
        payload = canonical_json(
            {
                "manifest": manifest,
                "resources": sorted(resources, key=lambda item: item["path"]),
            }
        )
        return hashlib.sha256(b"shuziren:p3:avatar-package:v1\0" + payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_text(value: str, label: str, *, minimum: int, maximum: int) -> str:
        normalized = value.strip()
        if len(normalized) < minimum or len(normalized) > maximum:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", f"{label} length is invalid")
        if any(ord(character) < 32 for character in normalized) or "<" in normalized or ">" in normalized:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", f"{label} contains unsafe characters")
        return normalized
