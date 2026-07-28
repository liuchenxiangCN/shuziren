from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

from app.control_plane.errors import ControlPlaneError
from app.control_plane.security import canonical_json, opaque_id

PROFILE_SCHEMA_VERSION = "p2_capability_profile_v1"
PROVIDER_REGISTRY_VERSION = "p2_provider_registry_001"
CAPABILITY_KEYS = (
    "dora",
    "knowledge",
    "direct_llm",
    "asr",
    "tts",
    "querying",
    "fvs_control",
)
CAPABILITY_FIELDS = {
    "enabled",
    "primary_provider_id",
    "fallback_provider_ids",
    "timeout_ms",
}
PROFILE_STATES = ("disabled", "mock", "unverified", "available", "degraded")
FALLBACK_ALLOWED_REASONS = ("timeout", "unavailable", "unsupported")
FALLBACK_TERMINAL_REASONS = (
    "permission_denied",
    "invalid_request",
    "unauthorized_template",
    "cancelled",
)
ACTIVATABLE_PROVIDER_STATES = {"available", "mock", "degraded"}
DEFAULT_RUNTIME_SESSION_ID = "anonymous"

_PROVIDER_ROWS = (
    ("local_rules", "dora", "available", "LOCAL", "NOT_REQUIRED", False, "none", "none"),
    ("mock_dora", "dora", "mock", "MOCK", "MOCK_ONLY", True, "bounded", "screen_bound"),
    ("dora_gateway", "dora", "unverified", "EXTERNAL", "UNVERIFIED", True, "declared", "screen_bound"),
    (
        "local_extractive",
        "knowledge",
        "available",
        "LOCAL",
        "NOT_REQUIRED",
        True,
        "none",
        "screen_bound",
    ),
    (
        "mock_knowledge",
        "knowledge",
        "mock",
        "MOCK",
        "MOCK_ONLY",
        True,
        "bounded",
        "screen_bound",
    ),
    (
        "dora_ragflow",
        "knowledge",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "ragflow_gateway",
        "knowledge",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "fixed_template",
        "direct_llm",
        "available",
        "LOCAL",
        "NOT_REQUIRED",
        False,
        "none",
        "none",
    ),
    (
        "mock_llm",
        "direct_llm",
        "mock",
        "MOCK",
        "MOCK_ONLY",
        True,
        "bounded",
        "screen_bound",
    ),
    (
        "direct_llm_gateway",
        "direct_llm",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    ("mock_asr", "asr", "mock", "MOCK", "MOCK_ONLY", True, "bounded", "screen_bound"),
    (
        "vendor_asr",
        "asr",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    ("mock_tts", "tts", "mock", "MOCK", "MOCK_ONLY", True, "bounded", "screen_bound"),
    (
        "browser_text_fallback",
        "tts",
        "degraded",
        "LOCAL",
        "NOT_REQUIRED",
        True,
        "none",
        "screen_bound",
    ),
    (
        "vendor_tts",
        "tts",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "mock_query",
        "querying",
        "mock",
        "MOCK",
        "MOCK_ONLY",
        True,
        "bounded",
        "screen_bound",
    ),
    (
        "finereport_ai_plugin",
        "querying",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "controlled_query",
        "querying",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "mock_fvs",
        "fvs_control",
        "mock",
        "MOCK",
        "MOCK_ONLY",
        True,
        "bounded",
        "screen_bound",
    ),
    (
        "fvs_page_number",
        "fvs_control",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
    (
        "fvs_post_message",
        "fvs_control",
        "unverified",
        "EXTERNAL",
        "UNVERIFIED",
        True,
        "declared",
        "screen_bound",
    ),
)

PROVIDER_BOUNDARIES = {
    "local_rules": "Deterministic local fixed capability.",
    "mock_dora": "Development preview and failure drill only.",
    "dora_gateway": "No real connection or certification in P2.1.",
    "local_extractive": "Source-bound extractive response only.",
    "mock_knowledge": "Development preview only.",
    "dora_ragflow": "No real connection or certification in P2.1.",
    "ragflow_gateway": "No real connection or certification in P2.1.",
    "fixed_template": "Fixed local response; no model execution.",
    "mock_llm": "Development preview only.",
    "direct_llm_gateway": "No real connection or certification in P2.1.",
    "mock_asr": "Development preview only.",
    "vendor_asr": "No real connection or certification in P2.1.",
    "mock_tts": "Development preview only.",
    "browser_text_fallback": "Text and subtitle fallback; not full TTS.",
    "vendor_tts": "No real connection or certification in P2.1.",
    "mock_query": "Development preview only; executes no query.",
    "finereport_ai_plugin": "P2.4 gate; publication blocked and no call occurs.",
    "controlled_query": "P2.2 gate; no QuerySource execution.",
    "mock_fvs": "Development preview only.",
    "fvs_page_number": "No real FVS call or certification in P2.1.",
    "fvs_post_message": "No real FVS call or certification in P2.1.",
}

PROVIDERS: tuple[dict[str, Any], ...] = tuple(
    {
        "provider_id": provider_id,
        "capability": capability,
        "state": state,
        "adapter_kind": adapter_kind,
        "certification_state": certification_state,
        "permission_scope": "screen_bound",
        "supports_cancellation": supports_cancellation,
        "streaming_mode": streaming_mode,
        "session_mode": session_mode,
        "external_calls_enabled": False,
        "boundary": PROVIDER_BOUNDARIES[provider_id],
    }
    for (
        provider_id,
        capability,
        state,
        adapter_kind,
        certification_state,
        supports_cancellation,
        streaming_mode,
        session_mode,
    ) in _PROVIDER_ROWS
)
PROVIDER_BY_ID = {provider["provider_id"]: provider for provider in PROVIDERS}
PROVIDER_REGISTRY_HASH = hashlib.sha256(
    canonical_json(
        {
            "registry_version": PROVIDER_REGISTRY_VERSION,
            "providers": PROVIDERS,
        }
    ).encode("utf-8")
).hexdigest()

STATE_DEFINITIONS = {
    "disabled": "Capability is explicitly off and selects no Provider.",
    "mock": "Only a built-in development-preview Mock flow is selected.",
    "unverified": "Required external evidence is absent and activation is blocked.",
    "available": "A bounded local Provider is usable in the P2.1 preview boundary.",
    "degraded": "Only a documented reduced behavior remains.",
}

FALLBACK_POLICY = {
    "allowed_reasons": list(FALLBACK_ALLOWED_REASONS),
    "terminal_reasons": list(FALLBACK_TERMINAL_REASONS),
    "permission_scope": "screen_bound",
    "require_permission_equivalence": True,
}

_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(
        api[-_\s]?key|access[-_\s]?key|client[-_\s]?secret|private[-_\s]?key|
        password|passwd|passphrase|pwd|token|cookie|authorization|auth|
        secret|credential|dsn|connection[-_\s]?string
    )(?:[-_\s]?(?:ref|reference))?\s*[:=]
    """
)
_SECRET_VALUE = re.compile(
    r"""(?ix)(
        \bsk-(?:proj-)?[a-z0-9_-]{16,}|
        \bgh[pousr]_[a-z0-9]{16,}|
        \bAKIA[A-Z0-9]{12,}|
        \bAIza[a-z0-9_-]{20,}|
        \bxox[baprs]-[a-z0-9-]{16,}|
        \b(?:sk|rk)_live_[a-z0-9]{16,}|
        \b(?:bearer|basic)\s+[a-z0-9._~+/-]{8,}|
        \b[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\b|
        -----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----
    )"""
)
_DSN_VALUE = re.compile(
    r"(?ix)\b(?:jdbc:|postgres(?:ql)?://|mysql://|oracle://|mongodb(?:\+srv)?://|redis://)"
)
_ENDPOINT_VALUE = re.compile(
    r"""(?ix)(
        \b[a-z][a-z0-9+.-]{1,31}://|
        \b(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d{1,5})?(?:[/?:#][^\s]*)?
    )"""
)
_FREE_SQL_VALUE = re.compile(
    r"""(?isx)(
        (?:^|[;\n])\s*select\b.+?\bfrom\b|
        (?:^|[;\n])\s*insert\s+into\b|
        (?:^|[;\n])\s*update\s+\S+\s+set\b|
        (?:^|[;\n])\s*delete\s+from\b|
        (?:^|[;\n])\s*(?:drop|alter|create)\s+(?:table|database)\b|
        (?:^|[;\n])\s*(?:grant|revoke)\b|
        (?:^|[;\n])\s*merge\s+into\b
    )"""
)
_EXECUTABLE_VALUE = re.compile(
    r"""(?ix)(
        <\s*/?\s*script\b|
        \bjavascript\s*:|
        \beval\s*\(|
        \bnew\s+function\b|
        \b(?:child_process|subprocess)\b
    )"""
)
_OWNERSHIP_SELECTOR = re.compile(
    r"(?ix)\b(?:tenant|deployment|site|screen|digital[-_\s]?human|credential)[-_\s]?id\s*[:=]"
)


def fallback_decision(
    error_code: str,
    permission_equivalent: bool,
    fallback_provider_state: str,
) -> dict[str, Any]:
    normalized_error = error_code.strip().casefold()
    normalized_state = fallback_provider_state.strip().casefold()
    if normalized_error in FALLBACK_TERMINAL_REASONS:
        decision = "TERMINAL"
    elif normalized_error not in FALLBACK_ALLOWED_REASONS:
        decision = "NOT_ALLOWED"
    elif not permission_equivalent:
        decision = "PERMISSION_SCOPE_MISMATCH"
    elif normalized_state not in ACTIVATABLE_PROVIDER_STATES:
        decision = "FALLBACK_NOT_ACTIVATABLE"
    else:
        decision = "FALLBACK_ALLOWED"
    return {
        "error_code": normalized_error,
        "permission_equivalent": bool(permission_equivalent),
        "fallback_provider_state": normalized_state,
        "decision": decision,
        "fallback_allowed": decision == "FALLBACK_ALLOWED",
        "terminal": decision == "TERMINAL",
    }


def _disabled_capability(timeout_ms: int = 5000) -> dict[str, Any]:
    return {
        "enabled": False,
        "primary_provider_id": None,
        "fallback_provider_ids": [],
        "timeout_ms": timeout_ms,
    }


def _enabled_capability(provider_id: str, timeout_ms: int = 5000) -> dict[str, Any]:
    return {
        "enabled": True,
        "primary_provider_id": provider_id,
        "fallback_provider_ids": [],
        "timeout_ms": timeout_ms,
    }


PRESETS: dict[str, dict[str, Any]] = {
    "text_only": {
        "name": "Text only",
        "description": "Local deterministic text response; all other capabilities disabled.",
        "spec": {
            "dora": _enabled_capability("local_rules"),
            "knowledge": _disabled_capability(),
            "direct_llm": _disabled_capability(),
            "asr": _disabled_capability(),
            "tts": _disabled_capability(),
            "querying": _disabled_capability(),
            "fvs_control": _disabled_capability(),
        },
    },
    "mock_voice": {
        "name": "Mock voice",
        "description": "Mock Dora, ASR and TTS for development preview.",
        "spec": {
            "dora": _enabled_capability("mock_dora"),
            "knowledge": _disabled_capability(),
            "direct_llm": _disabled_capability(),
            "asr": _enabled_capability("mock_asr"),
            "tts": _enabled_capability("mock_tts"),
            "querying": _disabled_capability(),
            "fvs_control": _disabled_capability(),
        },
    },
    "mock_presenter": {
        "name": "Mock presenter",
        "description": "Mock Dora, ASR, TTS and FVS control for development preview.",
        "spec": {
            "dora": _enabled_capability("mock_dora"),
            "knowledge": _disabled_capability(),
            "direct_llm": _disabled_capability(),
            "asr": _enabled_capability("mock_asr"),
            "tts": _enabled_capability("mock_tts"),
            "querying": _disabled_capability(),
            "fvs_control": _enabled_capability("mock_fvs"),
        },
    },
}


class P21ControlPlane:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def list_providers(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        return {
            "api_version": "v1",
            "registry_version": PROVIDER_REGISTRY_VERSION,
            "registry_hash": PROVIDER_REGISTRY_HASH,
            "state_definitions": STATE_DEFINITIONS,
            "fallback_policy": FALLBACK_POLICY,
            "items": [dict(provider) for provider in PROVIDERS],
        }

    def list_presets(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        items = []
        for preset_id, preset in PRESETS.items():
            canonical_spec, derived = self._validate_and_derive_spec(preset["spec"])
            items.append(
                {
                    "preset_id": preset_id,
                    "name": preset["name"],
                    "description": preset["description"],
                    "spec": json.loads(canonical_spec),
                    **derived,
                    "immutable": True,
                }
            )
        return {
            "api_version": "v1",
            "schema_version": PROFILE_SCHEMA_VERSION,
            "registry_version": PROVIDER_REGISTRY_VERSION,
            "registry_hash": PROVIDER_REGISTRY_HASH,
            "items": items,
        }

    def list_profiles(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM capability_profiles
                WHERE tenant_id = ? AND deployment_id = ?
                ORDER BY site_id, name, profile_id
                """,
                (principal.tenant_id, principal.deployment_id),
            ).fetchall()
            return {
                "api_version": "v1",
                "items": [
                    self._profile_response(connection, row)
                    for row in rows
                    if self.owner._can_access_site(
                        principal,
                        row["site_id"],
                        "config.read",
                    )
                ],
            }

    def create_profile(
        self,
        principal: Any,
        *,
        site_id: str,
        name: str,
        description: str,
        source_preset_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        name = self._public_text(name, "Profile name", minimum=1, maximum=128)
        description = self._public_text(
            description,
            "Profile description",
            minimum=0,
            maximum=500,
        )
        if source_preset_id not in PRESETS:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Unknown capability profile preset",
            )
        command = {
            "site_id": site_id,
            "name": name,
            "description": description,
            "source_preset_id": source_preset_id,
        }
        operation_id = "createCapabilityProfile"
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            self.owner._site_row(
                connection,
                principal,
                site_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            profile_id = opaque_id("cpf")
            profile_version_id = opaque_id("cpv")
            canonical_spec, derived = self._validate_and_derive_spec(PRESETS[source_preset_id]["spec"])
            content_hash = hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO capability_profiles(
                    profile_id, tenant_id, deployment_id, site_id,
                    name, description, source_preset_id,
                    head_version_id, head_version_number,
                    created_by_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    profile_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    site_id,
                    name,
                    description,
                    source_preset_id,
                    profile_version_id,
                    principal.user_id,
                    now,
                    now,
                ),
            )
            self._insert_profile_version(
                connection,
                principal,
                profile_id=profile_id,
                profile_version_id=profile_version_id,
                site_id=site_id,
                version_number=1,
                canonical_spec=canonical_spec,
                derived=derived,
                now=now,
            )
            row = connection.execute(
                "SELECT * FROM capability_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            result = self._profile_response(connection, row)
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
                event_type="CAPABILITY_PROFILE_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CAPABILITY_PROFILE",
                target_id=profile_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "site_id": site_id,
                    "source_preset_id": source_preset_id,
                    "profile_version_id": profile_version_id,
                    "content_hash": content_hash,
                    "activation_eligible": derived["activation_eligible"],
                },
                now=now,
            )
            return result

    def get_profile(self, principal: Any, profile_id: str) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            row = self._load_profile(
                connection,
                principal,
                profile_id,
                "config.read",
            )
            return self._profile_response(connection, row, include_versions=True)

    def create_profile_version(
        self,
        principal: Any,
        profile_id: str,
        *,
        spec: dict[str, Any],
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        canonical_spec, derived = self._validate_and_derive_spec(spec)
        command = {
            "profile_id": profile_id,
            "spec": json.loads(canonical_spec),
            "if_match": if_match,
        }
        operation_id = "createCapabilityProfileVersion"
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            profile = self._load_profile(
                connection,
                principal,
                profile_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                "capability-profile",
                profile_id,
                profile["revision"],
            )
            version_number = profile["head_version_number"] + 1
            profile_version_id = opaque_id("cpv")
            self._insert_profile_version(
                connection,
                principal,
                profile_id=profile_id,
                profile_version_id=profile_version_id,
                site_id=profile["site_id"],
                version_number=version_number,
                canonical_spec=canonical_spec,
                derived=derived,
                now=now,
            )
            connection.execute(
                """
                UPDATE capability_profiles
                SET head_version_id = ?, head_version_number = ?,
                    updated_at = ?, revision = revision + 1
                WHERE profile_id = ?
                """,
                (profile_version_id, version_number, now, profile_id),
            )
            updated = connection.execute(
                "SELECT * FROM capability_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            result = self._profile_response(connection, updated)
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
                event_type="CAPABILITY_PROFILE_VERSION_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="CAPABILITY_PROFILE",
                target_id=profile_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "profile_version_id": profile_version_id,
                    "version_number": version_number,
                    "content_hash": hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest(),
                    "activation_eligible": derived["activation_eligible"],
                },
                now=now,
            )
            return result

    def assign_draft_profile(
        self,
        principal: Any,
        draft_id: str,
        *,
        profile_version_id: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        operation_id = "assignDraftCapabilityProfile"
        command = {
            "draft_id": draft_id,
            "profile_version_id": profile_version_id,
            "if_match": if_match,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            draft = self.owner.p1_3._load_draft(
                connection,
                principal,
                draft_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] != "DRAFT" or draft["current_revision"] < 1:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Only a populated DRAFT can receive a capability profile",
                )
            site_id = self._draft_site_id(connection, draft)
            version = self._load_profile_version(
                connection,
                principal,
                profile_version_id,
                "config.edit_technical",
            )
            if version["site_id"] != site_id:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Capability profile version was not found",
                )
            current = self._draft_assignment_row(
                connection,
                draft_id,
                draft["current_revision"],
            )
            if current is not None and current["profile_version_id"] == profile_version_id:
                result = self.owner.p1_3._draft_response(connection, draft)
            else:
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
                self._insert_draft_assignment(
                    connection,
                    draft_id=draft_id,
                    draft_revision=next_revision,
                    principal=principal,
                    site_id=site_id,
                    version=version,
                    assigned_by_user_id=principal.user_id,
                    assigned_at=now,
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
                    event_type="CONFIG_DRAFT_CAPABILITY_PROFILE_ASSIGNED",
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type="CONFIG_DRAFT",
                    target_id=draft_id,
                    outcome="SUCCESS",
                    reason=None,
                    details={
                        "draft_revision": next_revision,
                        "profile_id": version["profile_id"],
                        "profile_version_id": profile_version_id,
                        "profile_content_hash": version["content_hash"],
                        "provider_registry_version": version["provider_registry_version"],
                        "activation_eligible": bool(version["activation_eligible"]),
                    },
                    now=now,
                )
                updated = self.owner.p1_3._load_draft(
                    connection,
                    principal,
                    draft_id,
                    "config.read",
                )
                result = self.owner.p1_3._draft_response(connection, updated)
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

    def effective_screen_capabilities(
        self,
        principal: Any,
        screen_id: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
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
            desired = self._binding_target_response(
                connection,
                tenant_id=principal.tenant_id,
                deployment_id=principal.deployment_id,
                screen_id=screen_id,
                release_target_id=binding["desired_release_target_id"],
                binding_generation=binding["binding_generation"],
                digital_human_instance_id=binding["digital_human_instance_id"],
            )
            applied = self._binding_target_response(
                connection,
                tenant_id=principal.tenant_id,
                deployment_id=principal.deployment_id,
                screen_id=screen_id,
                release_target_id=binding["applied_release_target_id"],
                binding_generation=binding["binding_generation"],
                digital_human_instance_id=binding["digital_human_instance_id"],
            )
            if applied is not None and applied["profile_snapshot"] is not None:
                state = "APPLIED"
                effective = applied["profile_snapshot"]
            elif applied is not None:
                state = "NOT_CONFIGURED_P2_1"
                effective = None
            elif binding["desired_release_target_id"] is not None:
                state = "DESIRED_PENDING_ACKNOWLEDGEMENT"
                effective = None
            else:
                state = "NOT_CONFIGURED_P2_1"
                effective = None
            return {
                "api_version": "v1",
                "screen_id": screen_id,
                "digital_human_instance_id": binding["digital_human_instance_id"],
                "binding_generation": binding["binding_generation"],
                "state": state,
                "desired": desired,
                "applied": applied,
                "effective": effective,
                "site_id": screen["site_id"],
            }

    def current_device_capabilities(
        self,
        context: Any,
        runtime_session_id: str | None,
    ) -> dict[str, Any]:
        session_id = self._runtime_session_id(runtime_session_id)
        with self.owner.store.connect() as connection:
            binding = connection.execute(
                """
                SELECT * FROM runtime_bindings
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (context.tenant_id, context.deployment_id, context.screen_id),
            ).fetchone()
            if binding is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Runtime binding was not found",
                )
            target = self._binding_target_response(
                connection,
                tenant_id=context.tenant_id,
                deployment_id=context.deployment_id,
                screen_id=context.screen_id,
                release_target_id=binding["applied_release_target_id"],
                binding_generation=binding["binding_generation"],
                digital_human_instance_id=binding["digital_human_instance_id"],
            )
            snapshot = target["profile_snapshot"] if target is not None else None
            if snapshot is None:
                state = "NOT_CONFIGURED_P2_1"
                release_id = target["release_id"] if target else None
                release_target_id = target["release_target_id"] if target else None
                profile_version_id = None
            else:
                state = "APPLIED"
                release_id = target["release_id"]
                release_target_id = target["release_target_id"]
                profile_version_id = snapshot["profile_version_id"]
            isolation_payload = {
                "schema_version": "p2_runtime_isolation_key_v1",
                "tenant_id": context.tenant_id,
                "deployment_id": context.deployment_id,
                "screen_id": context.screen_id,
                "digital_human_instance_id": binding["digital_human_instance_id"],
                "release_target_id": release_target_id,
                "profile_version_id": profile_version_id,
                "session_id": session_id,
            }
            isolation_key = hashlib.sha256(canonical_json(isolation_payload).encode("utf-8")).hexdigest()
            return {
                "api_version": "v1",
                "screen_id": context.screen_id,
                "digital_human_instance_id": binding["digital_human_instance_id"],
                "binding_generation": binding["binding_generation"],
                "state": state,
                "release_id": release_id,
                "release_target_id": release_target_id,
                "capabilities": snapshot,
                "runtime_context": {
                    "session_id": session_id,
                    "isolation_key_sha256": isolation_key,
                },
            }

    def draft_assignment_response(
        self,
        connection: sqlite3.Connection,
        draft_id: str,
        draft_revision: int,
    ) -> dict[str, Any] | None:
        row = self._draft_assignment_row(connection, draft_id, draft_revision)
        if row is None:
            return None
        version = connection.execute(
            """
            SELECT * FROM capability_profile_versions
            WHERE profile_version_id = ? AND profile_id = ?
            """,
            (row["profile_version_id"], row["profile_id"]),
        ).fetchone()
        if version is None or not self._assignment_matches_version(row, version):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Draft capability assignment integrity check failed",
                retryable=False,
            )
        self._verified_version_data(version)
        return {
            "profile_id": row["profile_id"],
            "profile_version_id": row["profile_version_id"],
            "version_number": row["version_number"],
            "content_hash": row["profile_content_hash"],
            "provider_registry_version": row["provider_registry_version"],
            "provider_registry_hash": row["provider_registry_hash"],
            "state_summary": json.loads(row["state_summary_json"]),
            "dependency_findings": json.loads(row["dependency_findings_json"]),
            "activation_eligible": bool(row["activation_eligible"]),
            "assigned_at": row["assigned_at"],
            "immutable": True,
        }

    def copy_draft_assignment_forward(
        self,
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        source_revision: int,
        target_revision: int,
    ) -> None:
        row = self._draft_assignment_row(connection, draft_id, source_revision)
        if row is None:
            return
        columns = (
            "draft_id",
            "draft_revision",
            "tenant_id",
            "deployment_id",
            "site_id",
            "profile_id",
            "profile_version_id",
            "version_number",
            "profile_content_hash",
            "provider_registry_version",
            "provider_registry_hash",
            "state_summary_json",
            "dependency_findings_json",
            "activation_eligible",
            "assigned_by_user_id",
            "assigned_at",
        )
        values = [row[column] for column in columns]
        values[1] = target_revision
        connection.execute(
            f"""
            INSERT INTO config_draft_capability_assignments(
                {", ".join(columns)}
            ) VALUES ({", ".join("?" for _ in columns)})
            """,
            values,
        )

    def resolve_draft_capabilities(
        self,
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        draft_revision: int,
        targets: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        assignment = self._draft_assignment_row(
            connection,
            draft_id,
            draft_revision,
        )
        if assignment is None:
            return None
        version = connection.execute(
            """
            SELECT * FROM capability_profile_versions
            WHERE profile_version_id = ? AND profile_id = ?
            """,
            (assignment["profile_version_id"], assignment["profile_id"]),
        ).fetchone()
        if version is None or not self._assignment_matches_version(
            assignment,
            version,
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Draft capability assignment integrity check failed",
                retryable=False,
            )
        spec, derived = self._verified_version_data(version)
        state_summary = derived["state_summary"]
        findings = derived["dependency_findings"]
        envelopes: dict[str, dict[str, Any]] = {}
        hashes: dict[str, str] = {}
        for target in targets:
            envelope = {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "screen_id": target["screen_id"],
                "digital_human_instance_id": target["digital_human_instance_id"],
                "profile_id": version["profile_id"],
                "profile_version_id": version["profile_version_id"],
                "version_number": version["version_number"],
                "content_hash": version["content_hash"],
                "provider_registry_version": version["provider_registry_version"],
                "provider_registry_hash": version["provider_registry_hash"],
                "spec": spec,
                "state_summary": state_summary,
                "dependency_findings": findings,
                "activation_eligible": bool(version["activation_eligible"]),
            }
            envelope_json = canonical_json(envelope)
            envelope_hash = hashlib.sha256(envelope_json.encode("utf-8")).hexdigest()
            envelopes[target["screen_id"]] = {
                "envelope": envelope,
                "canonical_json": envelope_json,
                "hash": envelope_hash,
                "site_id": target["site_id"],
            }
            hashes[target["screen_id"]] = envelope_hash
        return {
            "assignment": assignment,
            "profile_version": version,
            "envelopes": envelopes,
            "envelope_hashes": hashes,
            "activation_eligible": bool(version["activation_eligible"]),
            "dependency_findings": findings,
        }

    def insert_release_snapshot(
        self,
        connection: sqlite3.Connection,
        *,
        release_target_id: str,
        target: dict[str, Any],
        capability_resolution: dict[str, Any] | None,
        now: float,
    ) -> None:
        if capability_resolution is None:
            return
        version = capability_resolution["profile_version"]
        resolved = capability_resolution["envelopes"][target["screen_id"]]
        connection.execute(
            """
            INSERT INTO release_target_capability_snapshots(
                release_target_id, tenant_id, deployment_id,
                site_id, screen_id, digital_human_instance_id,
                profile_id, profile_version_id, version_number,
                profile_content_hash, provider_registry_version,
                provider_registry_hash, canonical_capability_snapshot_json,
                capability_envelope_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_target_id,
                version["tenant_id"],
                version["deployment_id"],
                resolved["site_id"],
                target["screen_id"],
                target["digital_human_instance_id"],
                version["profile_id"],
                version["profile_version_id"],
                version["version_number"],
                version["content_hash"],
                version["provider_registry_version"],
                version["provider_registry_hash"],
                resolved["canonical_json"],
                resolved["hash"],
                now,
            ),
        )

    def copy_release_snapshot_forward(
        self,
        connection: sqlite3.Connection,
        *,
        source_release_target_id: str,
        target_release_target_id: str,
        now: float,
    ) -> None:
        if not self._table_exists(
            connection,
            "release_target_capability_snapshots",
        ):
            return
        source = connection.execute(
            """
            SELECT * FROM release_target_capability_snapshots
            WHERE release_target_id = ?
            """,
            (source_release_target_id,),
        ).fetchone()
        if source is None:
            return
        self._verified_snapshot_payload(connection, source)
        connection.execute(
            """
            INSERT INTO release_target_capability_snapshots(
                release_target_id, tenant_id, deployment_id,
                site_id, screen_id, digital_human_instance_id,
                profile_id, profile_version_id, version_number,
                profile_content_hash, provider_registry_version,
                provider_registry_hash, canonical_capability_snapshot_json,
                capability_envelope_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_release_target_id,
                source["tenant_id"],
                source["deployment_id"],
                source["site_id"],
                source["screen_id"],
                source["digital_human_instance_id"],
                source["profile_id"],
                source["profile_version_id"],
                source["version_number"],
                source["profile_content_hash"],
                source["provider_registry_version"],
                source["provider_registry_hash"],
                source["canonical_capability_snapshot_json"],
                source["capability_envelope_hash"],
                now,
            ),
        )

    def release_snapshot_response(
        self,
        connection: sqlite3.Connection,
        release_target_id: str,
    ) -> dict[str, Any] | None:
        if not self._table_exists(
            connection,
            "release_target_capability_snapshots",
        ):
            return None
        row = connection.execute(
            """
            SELECT * FROM release_target_capability_snapshots
            WHERE release_target_id = ?
            """,
            (release_target_id,),
        ).fetchone()
        if row is None:
            return None
        snapshot = self._verified_snapshot_payload(connection, row)
        snapshot["capability_envelope_hash"] = row["capability_envelope_hash"]
        snapshot["immutable"] = True
        return snapshot

    def _verified_snapshot_payload(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        version = connection.execute(
            """
            SELECT * FROM capability_profile_versions
            WHERE profile_version_id = ? AND profile_id = ?
            """,
            (row["profile_version_id"], row["profile_id"]),
        ).fetchone()
        target = connection.execute(
            """
            SELECT rt.tenant_id, rt.deployment_id, rt.screen_id,
                   rt.canonical_effective_config_json, rt.content_hash,
                   s.site_id
            FROM release_targets rt
            JOIN screen_instances s
              ON s.tenant_id = rt.tenant_id
             AND s.deployment_id = rt.deployment_id
             AND s.screen_id = rt.screen_id
            WHERE rt.release_target_id = ?
            """,
            (row["release_target_id"],),
        ).fetchone()
        digital_human = connection.execute(
            """
            SELECT 1 FROM digital_human_instances
            WHERE tenant_id = ? AND deployment_id = ?
              AND site_id = ? AND screen_id = ?
              AND digital_human_instance_id = ?
            """,
            (
                row["tenant_id"],
                row["deployment_id"],
                row["site_id"],
                row["screen_id"],
                row["digital_human_instance_id"],
            ),
        ).fetchone()
        if version is None or target is None or digital_human is None:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            )
        try:
            base_effective = json.loads(target["canonical_effective_config_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            ) from exc
        if not isinstance(base_effective, dict):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            )
        if (
            canonical_json(base_effective) != target["canonical_effective_config_json"]
            or hashlib.sha256(target["canonical_effective_config_json"].encode("utf-8")).hexdigest()
            != target["content_hash"]
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            )
        spec, derived = self._verified_version_data(version)
        try:
            snapshot = json.loads(row["canonical_capability_snapshot_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            ) from exc
        if not isinstance(snapshot, dict):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            )
        expected_keys = {
            "schema_version",
            "screen_id",
            "digital_human_instance_id",
            "profile_id",
            "profile_version_id",
            "version_number",
            "content_hash",
            "provider_registry_version",
            "provider_registry_hash",
            "spec",
            "state_summary",
            "dependency_findings",
            "activation_eligible",
        }
        canonical_snapshot = canonical_json(snapshot)
        if (
            set(snapshot) != expected_keys
            or canonical_snapshot != row["canonical_capability_snapshot_json"]
            or hashlib.sha256(canonical_snapshot.encode("utf-8")).hexdigest()
            != row["capability_envelope_hash"]
            or row["tenant_id"] != target["tenant_id"]
            or row["deployment_id"] != target["deployment_id"]
            or row["site_id"] != target["site_id"]
            or row["screen_id"] != target["screen_id"]
            or row["tenant_id"] != version["tenant_id"]
            or row["deployment_id"] != version["deployment_id"]
            or row["site_id"] != version["site_id"]
            or row["profile_id"] != version["profile_id"]
            or row["profile_version_id"] != version["profile_version_id"]
            or row["version_number"] != version["version_number"]
            or row["profile_content_hash"] != version["content_hash"]
            or row["provider_registry_version"] != version["provider_registry_version"]
            or row["provider_registry_hash"] != version["provider_registry_hash"]
            or snapshot["schema_version"] != PROFILE_SCHEMA_VERSION
            or snapshot["screen_id"] != row["screen_id"]
            or snapshot["digital_human_instance_id"] != row["digital_human_instance_id"]
            or base_effective.get("screen_id") != row["screen_id"]
            or base_effective.get("digital_human_instance_id") != row["digital_human_instance_id"]
            or snapshot["profile_id"] != row["profile_id"]
            or snapshot["profile_version_id"] != row["profile_version_id"]
            or snapshot["version_number"] != row["version_number"]
            or snapshot["content_hash"] != row["profile_content_hash"]
            or snapshot["provider_registry_version"] != row["provider_registry_version"]
            or snapshot["provider_registry_hash"] != row["provider_registry_hash"]
            or snapshot["spec"] != spec
            or snapshot["state_summary"] != derived["state_summary"]
            or snapshot["dependency_findings"] != derived["dependency_findings"]
            or not isinstance(snapshot["activation_eligible"], bool)
            or snapshot["activation_eligible"] != bool(version["activation_eligible"])
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release capability snapshot integrity check failed",
                retryable=False,
            )
        return snapshot

    def preview_capability_evidence(
        self,
        capability_resolution: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if capability_resolution is None:
            return None
        version = capability_resolution["profile_version"]
        summary = json.loads(version["state_summary_json"])
        _, derived = self._validate_and_derive_spec(json.loads(version["canonical_spec_json"]))
        diagnostics = derived["capability_diagnostics"]
        return {
            "provider_execution": "LOCAL_OR_MOCK_DIAGNOSTIC_ONLY",
            "real_provider_verified": False,
            "external_calls_made": False,
            "state_summary": summary,
            "capability_diagnostics": diagnostics,
            "fallback_policy": {
                reason: fallback_decision(reason, True, "available")
                for reason in (
                    *FALLBACK_ALLOWED_REASONS,
                    *FALLBACK_TERMINAL_REASONS,
                )
            },
            "disabled_zero_provider": all(
                item["selected_provider_id"] is None
                for item in diagnostics["capabilities"].values()
                if item["state"] == "disabled"
            ),
        }

    def _insert_profile_version(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        *,
        profile_id: str,
        profile_version_id: str,
        site_id: str,
        version_number: int,
        canonical_spec: str,
        derived: dict[str, Any],
        now: float,
    ) -> None:
        connection.execute(
            """
            INSERT INTO capability_profile_versions(
                profile_version_id, tenant_id, deployment_id, site_id,
                profile_id, version_number, schema_version,
                canonical_spec_json, content_hash,
                provider_registry_version, provider_registry_hash,
                state_summary_json, dependency_findings_json,
                activation_eligible, created_by_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_version_id,
                principal.tenant_id,
                principal.deployment_id,
                site_id,
                profile_id,
                version_number,
                PROFILE_SCHEMA_VERSION,
                canonical_spec,
                hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest(),
                PROVIDER_REGISTRY_VERSION,
                PROVIDER_REGISTRY_HASH,
                canonical_json(derived["state_summary"]),
                canonical_json(derived["dependency_findings"]),
                int(derived["activation_eligible"]),
                principal.user_id,
                now,
            ),
        )

    def _load_profile(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        profile_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = connection.execute(
            """
            SELECT * FROM capability_profiles
            WHERE profile_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (profile_id, principal.tenant_id, principal.deployment_id),
        ).fetchone()
        if row is None or not self.owner._can_access_site(
            principal,
            row["site_id"],
            permission,
        ):
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Capability profile was not found",
            )
        return row

    def _load_profile_version(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        profile_version_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = connection.execute(
            """
            SELECT v.* FROM capability_profile_versions v
            JOIN capability_profiles p ON p.profile_id = v.profile_id
            WHERE v.profile_version_id = ?
              AND v.tenant_id = ? AND v.deployment_id = ?
            """,
            (
                profile_version_id,
                principal.tenant_id,
                principal.deployment_id,
            ),
        ).fetchone()
        if row is None or not self.owner._can_access_site(
            principal,
            row["site_id"],
            permission,
        ):
            raise ControlPlaneError(
                404,
                "RESOURCE_NOT_FOUND",
                "Capability profile version was not found",
            )
        return row

    def _profile_response(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        include_versions: bool = False,
    ) -> dict[str, Any]:
        head = connection.execute(
            """
            SELECT * FROM capability_profile_versions
            WHERE profile_version_id = ? AND profile_id = ?
            """,
            (row["head_version_id"], row["profile_id"]),
        ).fetchone()
        if head is None:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Capability profile head is unavailable",
                retryable=False,
            )
        result = {
            "api_version": "v1",
            "profile_id": row["profile_id"],
            "site_id": row["site_id"],
            "name": row["name"],
            "description": row["description"],
            "source_preset_id": row["source_preset_id"],
            "head_version_id": row["head_version_id"],
            "head_version_number": row["head_version_number"],
            "resource_revision": row["revision"],
            "head_version": self._profile_version_response(head),
            "etag": self.owner._resource_etag(
                "capability-profile",
                row["profile_id"],
                row["revision"],
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_versions:
            versions = connection.execute(
                """
                SELECT * FROM capability_profile_versions
                WHERE profile_id = ? ORDER BY version_number DESC
                """,
                (row["profile_id"],),
            ).fetchall()
            result["versions"] = [self._profile_version_response(version) for version in versions]
        return result

    def _profile_version_response(self, row: sqlite3.Row) -> dict[str, Any]:
        spec, derived = self._verified_version_data(row)
        return {
            "profile_version_id": row["profile_version_id"],
            "profile_id": row["profile_id"],
            "version_number": row["version_number"],
            "schema_version": row["schema_version"],
            "spec": spec,
            "content_hash": row["content_hash"],
            "provider_registry_version": row["provider_registry_version"],
            "provider_registry_hash": row["provider_registry_hash"],
            "state_summary": derived["state_summary"],
            "capability_diagnostics": derived["capability_diagnostics"],
            "dependency_findings": derived["dependency_findings"],
            "activation_eligible": bool(row["activation_eligible"]),
            "created_by_user_id": row["created_by_user_id"],
            "created_at": row["created_at"],
            "immutable": True,
        }

    def _verified_version_data(
        self,
        row: sqlite3.Row,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            spec = json.loads(row["canonical_spec_json"])
            canonical_spec, derived = self._validate_and_derive_spec(spec)
        except (
            ControlPlaneError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Capability profile version integrity check failed",
                retryable=False,
            ) from exc
        if (
            row["schema_version"] != PROFILE_SCHEMA_VERSION
            or canonical_spec != row["canonical_spec_json"]
            or hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest() != row["content_hash"]
            or row["provider_registry_version"] != PROVIDER_REGISTRY_VERSION
            or row["provider_registry_hash"] != PROVIDER_REGISTRY_HASH
            or canonical_json(derived["state_summary"]) != row["state_summary_json"]
            or canonical_json(derived["dependency_findings"]) != row["dependency_findings_json"]
            or int(derived["activation_eligible"]) != row["activation_eligible"]
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Capability profile version integrity check failed",
                retryable=False,
            )
        return spec, derived

    @staticmethod
    def _draft_assignment_row(
        connection: sqlite3.Connection,
        draft_id: str,
        draft_revision: int,
    ) -> sqlite3.Row | None:
        if not P21ControlPlane._table_exists(
            connection,
            "config_draft_capability_assignments",
        ):
            return None
        return connection.execute(
            """
            SELECT * FROM config_draft_capability_assignments
            WHERE draft_id = ? AND draft_revision = ?
            """,
            (draft_id, draft_revision),
        ).fetchone()

    @staticmethod
    def _table_exists(
        connection: sqlite3.Connection,
        table: str,
    ) -> bool:
        return (
            connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _draft_site_id(
        connection: sqlite3.Connection,
        draft: sqlite3.Row,
    ) -> str:
        if draft["target_type"] == "SCREEN":
            row = connection.execute(
                """
                SELECT site_id FROM screen_instances
                WHERE tenant_id = ? AND deployment_id = ? AND screen_id = ?
                """,
                (
                    draft["tenant_id"],
                    draft["deployment_id"],
                    draft["screen_id"],
                ),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT site_id FROM screen_groups
                WHERE tenant_id = ? AND deployment_id = ?
                  AND screen_group_id = ?
                """,
                (
                    draft["tenant_id"],
                    draft["deployment_id"],
                    draft["screen_group_id"],
                ),
            ).fetchone()
        if row is None:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Draft target scope is unavailable",
                retryable=False,
            )
        return row["site_id"]

    @staticmethod
    def _insert_draft_assignment(
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        draft_revision: int,
        principal: Any,
        site_id: str,
        version: sqlite3.Row,
        assigned_by_user_id: str,
        assigned_at: float,
    ) -> None:
        connection.execute(
            """
            INSERT INTO config_draft_capability_assignments(
                draft_id, draft_revision, tenant_id, deployment_id, site_id,
                profile_id, profile_version_id, version_number,
                profile_content_hash, provider_registry_version,
                provider_registry_hash, state_summary_json,
                dependency_findings_json, activation_eligible,
                assigned_by_user_id, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                draft_revision,
                principal.tenant_id,
                principal.deployment_id,
                site_id,
                version["profile_id"],
                version["profile_version_id"],
                version["version_number"],
                version["content_hash"],
                version["provider_registry_version"],
                version["provider_registry_hash"],
                version["state_summary_json"],
                version["dependency_findings_json"],
                version["activation_eligible"],
                assigned_by_user_id,
                assigned_at,
            ),
        )

    @staticmethod
    def _assignment_matches_version(
        assignment: sqlite3.Row,
        version: sqlite3.Row,
    ) -> bool:
        return (
            assignment["tenant_id"] == version["tenant_id"]
            and assignment["deployment_id"] == version["deployment_id"]
            and assignment["site_id"] == version["site_id"]
            and assignment["profile_id"] == version["profile_id"]
            and assignment["profile_version_id"] == version["profile_version_id"]
            and assignment["version_number"] == version["version_number"]
            and assignment["profile_content_hash"] == version["content_hash"]
            and assignment["provider_registry_version"] == version["provider_registry_version"]
            and assignment["provider_registry_hash"] == version["provider_registry_hash"]
            and assignment["state_summary_json"] == version["state_summary_json"]
            and assignment["dependency_findings_json"] == version["dependency_findings_json"]
            and assignment["activation_eligible"] == version["activation_eligible"]
        )

    def _binding_target_response(
        self,
        connection: sqlite3.Connection,
        *,
        tenant_id: str,
        deployment_id: str,
        screen_id: str,
        release_target_id: str | None,
        binding_generation: int,
        digital_human_instance_id: str | None,
    ) -> dict[str, Any] | None:
        if release_target_id is None:
            return None
        target = connection.execute(
            """
            SELECT rt.*, r.release_sequence, r.creation_kind
            FROM release_targets rt
            JOIN config_releases r ON r.release_id = rt.release_id
            WHERE rt.release_target_id = ?
              AND rt.tenant_id = ? AND rt.deployment_id = ?
              AND rt.screen_id = ?
            """,
            (release_target_id, tenant_id, deployment_id, screen_id),
        ).fetchone()
        if target is None:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Applied release target is unavailable",
                retryable=False,
            )
        snapshot = self.release_snapshot_response(connection, release_target_id)
        if snapshot is not None and snapshot["digital_human_instance_id"] != digital_human_instance_id:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Applied capability snapshot scope changed",
                retryable=False,
            )
        return {
            "state": "CONFIGURED" if snapshot is not None else "NOT_CONFIGURED_P2_1",
            "release_id": target["release_id"],
            "release_target_id": target["release_target_id"],
            "release_sequence": target["release_sequence"],
            "creation_kind": target["creation_kind"],
            "binding_generation": binding_generation,
            "profile_snapshot": snapshot,
        }

    def _validate_and_derive_spec(
        self,
        spec: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if not isinstance(spec, dict) or set(spec) != set(CAPABILITY_KEYS):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Capability profile must contain exactly the seven closed capabilities",
            )
        normalized: dict[str, dict[str, Any]] = {}
        summaries: dict[str, dict[str, Any]] = {}
        findings: list[dict[str, Any]] = []
        for capability in CAPABILITY_KEYS:
            item = spec[capability]
            if not isinstance(item, dict) or set(item) != CAPABILITY_FIELDS:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability} must contain exactly the closed capability fields",
                )
            enabled = item["enabled"]
            primary_id = item["primary_provider_id"]
            fallback_ids = item["fallback_provider_ids"]
            timeout_ms = item["timeout_ms"]
            if not isinstance(enabled, bool):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability}.enabled must be a boolean",
                )
            if (
                not isinstance(timeout_ms, int)
                or isinstance(timeout_ms, bool)
                or not 100 <= timeout_ms <= 120000
            ):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability}.timeout_ms must be from 100 through 120000",
                )
            if not isinstance(fallback_ids, list) or any(
                not isinstance(provider_id, str) or not provider_id for provider_id in fallback_ids
            ):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability}.fallback_provider_ids must be an ordered string list",
                )
            if len(fallback_ids) != len(set(fallback_ids)):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability} fallback Providers must be unique",
                )
            if not enabled:
                if primary_id is not None or fallback_ids:
                    raise ControlPlaneError(
                        422,
                        "SCHEMA_VALIDATION_FAILED",
                        f"Disabled {capability} cannot select a Provider",
                    )
                normalized[capability] = {
                    "enabled": False,
                    "primary_provider_id": None,
                    "fallback_provider_ids": [],
                    "timeout_ms": timeout_ms,
                }
                summaries[capability] = {
                    "state": "disabled",
                    "selected_provider_id": None,
                    "fallback_provider_ids": [],
                    "timeout_ms": timeout_ms,
                    "provider_execution_allowed": False,
                    "fallback_contract": {},
                }
                continue
            if not isinstance(primary_id, str) or not primary_id:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"Enabled {capability} requires a primary Provider",
                )
            primary = self._provider_for_capability(primary_id, capability)
            if primary_id in fallback_ids:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability} primary Provider cannot also be a fallback",
                )
            fallback_providers = [
                self._provider_for_capability(provider_id, capability) for provider_id in fallback_ids
            ]
            if any(
                provider["permission_scope"] != primary["permission_scope"] for provider in fallback_providers
            ):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    f"{capability} fallback permission scope is not equivalent",
                )
            normalized[capability] = {
                "enabled": True,
                "primary_provider_id": primary_id,
                "fallback_provider_ids": list(fallback_ids),
                "timeout_ms": timeout_ms,
            }
            fallback_contract = {
                provider["provider_id"]: {
                    reason: fallback_decision(
                        reason,
                        provider["permission_scope"] == primary["permission_scope"],
                        provider["state"],
                    )
                    for reason in (
                        *FALLBACK_ALLOWED_REASONS,
                        *FALLBACK_TERMINAL_REASONS,
                    )
                }
                for provider in fallback_providers
            }
            summaries[capability] = {
                "state": primary["state"],
                "selected_provider_id": primary_id,
                "fallback_provider_ids": list(fallback_ids),
                "timeout_ms": timeout_ms,
                "provider_execution_allowed": primary["state"] in ACTIVATABLE_PROVIDER_STATES,
                "fallback_contract": fallback_contract,
            }
            for provider in (primary, *fallback_providers):
                if provider["state"] == "unverified":
                    findings.append(
                        {
                            "severity": "ERROR",
                            "code": "UNVERIFIED_PROVIDER_BLOCKS_ACTIVATION",
                            "capability": capability,
                            "provider_id": provider["provider_id"],
                            "message": (
                                f"{provider['provider_id']} lacks the required "
                                "external evidence; no external call will occur."
                            ),
                        }
                    )
                elif provider["state"] == "degraded":
                    findings.append(
                        {
                            "severity": "WARNING",
                            "code": "DEGRADED_PROVIDER_LIMITED_BEHAVIOR",
                            "capability": capability,
                            "provider_id": provider["provider_id"],
                            "message": provider["boundary"],
                        }
                    )
                elif provider["state"] == "mock":
                    findings.append(
                        {
                            "severity": "INFO",
                            "code": "MOCK_PROVIDER_PREVIEW_ONLY",
                            "capability": capability,
                            "provider_id": provider["provider_id"],
                            "message": "Mock evidence is never real-provider evidence.",
                        }
                    )
        canonical_spec = canonical_json(normalized)
        self._reject_secret_material(canonical_spec, "Capability profile")
        state_summary = {capability: summaries[capability]["state"] for capability in CAPABILITY_KEYS}
        ordered_states = [state_summary[key] for key in CAPABILITY_KEYS]
        overall_state = next(
            (state for state in ("unverified", "degraded", "mock", "available") if state in ordered_states),
            "disabled",
        )
        activation_eligible = not any(finding["severity"] == "ERROR" for finding in findings)
        return canonical_spec, {
            "state_summary": state_summary,
            "capability_diagnostics": {
                "overall_state": overall_state,
                "capabilities": summaries,
            },
            "dependency_findings": findings,
            "activation_eligible": activation_eligible,
        }

    @staticmethod
    def _provider_for_capability(
        provider_id: str,
        capability: str,
    ) -> dict[str, Any]:
        provider = PROVIDER_BY_ID.get(provider_id)
        if provider is None or provider["capability"] != capability:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{provider_id} is not registered for {capability}",
            )
        return provider

    @classmethod
    def _public_text(
        cls,
        value: str,
        label: str,
        *,
        minimum: int,
        maximum: int,
    ) -> str:
        if not isinstance(value, str):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} must be a string",
            )
        normalized = value.strip()
        if (
            len(normalized) < minimum
            or len(normalized) > maximum
            or (normalized and not normalized.isprintable())
        ):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} must contain {minimum} to {maximum} printable characters",
            )
        cls._reject_secret_material(normalized, label)
        return normalized

    @classmethod
    def _runtime_session_id(cls, value: str | None) -> str:
        if value is None:
            return DEFAULT_RUNTIME_SESSION_ID
        normalized = cls._public_text(
            value,
            "Runtime session ID",
            minimum=1,
            maximum=128,
        )
        if _OWNERSHIP_SELECTOR.search(normalized):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Runtime session ID cannot contain an ownership selector",
            )
        return normalized

    @staticmethod
    def _reject_secret_material(value: str, label: str) -> None:
        if (
            _SECRET_ASSIGNMENT.search(value)
            or _SECRET_VALUE.search(value)
            or _DSN_VALUE.search(value)
            or _ENDPOINT_VALUE.search(value)
            or _FREE_SQL_VALUE.search(value)
            or _EXECUTABLE_VALUE.search(value)
        ):
            raise ControlPlaneError(
                422,
                "SECRET_MATERIAL_FORBIDDEN",
                f"{label} cannot contain credentials, DSNs, or Secret material",
            )
