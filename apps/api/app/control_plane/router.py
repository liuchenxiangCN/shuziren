from __future__ import annotations

import logging
import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.control_plane.errors import ControlPlaneError
from app.control_plane.service import ControlPlaneService, DeviceContext, SessionContext

CONTROL_PREFIX = "/api/v1/control-plane"
DEVICE_PREFIX = "/api/v1/device"
SESSION_COOKIE = "__Host-shuziren_session"

router = APIRouter()
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)


class ReauthenticateRequest(StrictModel):
    password: str = Field(min_length=1, max_length=128)


class UserCreateRequest(StrictModel):
    normalized_username: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


class ReasonRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class ApprovalRequest(StrictModel):
    expected_request_digest: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


class EnrollmentClaimRequest(StrictModel):
    enrollment_token: str = Field(min_length=20, max_length=512)


class DeviceRevokeRequest(StrictModel):
    expected_credential_epoch: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class ScreenGroupCreateRequest(StrictModel):
    slug: str = Field(min_length=1, max_length=63)
    display_name: str = Field(min_length=1, max_length=128)


class ScreenGroupUpdateRequest(StrictModel):
    slug: str | None = Field(default=None, min_length=1, max_length=63)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    member_screen_ids: list[str] | None = Field(default=None, max_length=200)


class ScreenInstanceCreateRequest(StrictModel):
    slug: str = Field(min_length=1, max_length=63)
    display_name: str = Field(min_length=1, max_length=128)
    fvs_binding_ref: str | None = Field(default=None, max_length=512)


class ScreenInstanceUpdateRequest(StrictModel):
    slug: str | None = Field(default=None, min_length=1, max_length=63)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    fvs_binding_ref: str | None = Field(default=None, max_length=512)


class DigitalHumanInstanceCreateRequest(StrictModel):
    pass


class ConfigDraftCreateRequest(StrictModel):
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str = Field(min_length=1, max_length=200)
    schema_version: str = Field(min_length=1, max_length=64)


class ConfigDraftSpecRequest(StrictModel):
    welcome_text: str = Field(min_length=1, max_length=500)
    fvs_binding_ref: str = Field(min_length=1, max_length=512)


class ConfigDraftDecisionRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class ConfigReleaseCreateRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class PublishScreenRequest(StrictModel):
    release_id: str = Field(min_length=1, max_length=200)
    release_target_id: str = Field(min_length=1, max_length=200)
    expected_binding_generation: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


class GroupPublicationTargetRequest(StrictModel):
    screen_id: str = Field(min_length=1, max_length=200)
    release_target_id: str = Field(min_length=1, max_length=200)
    runtime_if_match: str = Field(min_length=5, max_length=200)
    expected_binding_generation: int = Field(ge=0)


class PublishGroupRequest(StrictModel):
    release_id: str = Field(min_length=1, max_length=200)
    targets: list[GroupPublicationTargetRequest] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=500)


class RollbackScreenRequest(StrictModel):
    source_release_target_id: str = Field(min_length=1, max_length=200)
    expected_binding_generation: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


class GroupRollbackSourceRequest(StrictModel):
    screen_id: str = Field(min_length=1, max_length=200)
    source_release_target_id: str = Field(min_length=1, max_length=200)


class RollbackGroupRequest(StrictModel):
    source_targets: list[GroupRollbackSourceRequest] = Field(min_length=1, max_length=200)
    targets: list[GroupPublicationTargetRequest] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=500)


class DeviceReleaseAcknowledgementRequest(StrictModel):
    binding_generation: int = Field(ge=1)
    content_hash: str = Field(min_length=64, max_length=64)


class BackupCreateRequest(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class RestorePlanCreateRequest(StrictModel):
    backup_id: str = Field(min_length=1, max_length=200)


class RestorePlanExecuteRequest(StrictModel):
    confirmation: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


IdempotencyKeyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200),
]
IfMatchHeader = Annotated[str, Header(alias="If-Match", min_length=5, max_length=200)]
HighRiskActionHeader = Annotated[
    str | None,
    Header(alias="High-Risk-Action-ID", min_length=8, max_length=200),
]


def service_from_request(request: Request) -> ControlPlaneService:
    service = getattr(request.app.state, "control_plane_service", None)
    if service is None:
        raise ControlPlaneError(
            503,
            "CONTROL_PLANE_UNAVAILABLE",
            "Control plane is unavailable until its external key and store are configured",
            retryable=False,
        )
    return service


def require_origin(request: Request) -> None:
    service_from_request(request)
    allowed = set(getattr(request.app.state, "control_plane_allowed_origins", ()))
    origin = request.headers.get("origin")
    if origin is None or origin not in allowed:
        raise ControlPlaneError(403, "FORBIDDEN", "Origin is not allowed")


def session_from_request(request: Request) -> SessionContext:
    reject_ownership_selectors(request)
    service = service_from_request(request)
    cookie_header = request.headers.get("cookie", "")
    matches = [
        part.strip().split("=", 1)[1]
        for part in cookie_header.split(";")
        if part.strip().startswith(f"{SESSION_COOKIE}=") and "=" in part
    ]
    if len(matches) != 1 or not matches[0]:
        raise ControlPlaneError(401, "AUTHENTICATION_REQUIRED", "Authentication is required")
    context = service.authenticate_session(matches[0])
    request.state.control_plane_actor_type = "USER"
    request.state.control_plane_actor_id = context.principal.user_id
    return context


def mutating_session(request: Request) -> SessionContext:
    require_origin(request)
    context = session_from_request(request)
    csrf_token = request.headers.get("x-csrf-token")
    if not csrf_token:
        raise ControlPlaneError(403, "FORBIDDEN", "CSRF validation failed")
    service_from_request(request).verify_csrf(context.auth_session_id, csrf_token)
    return context


def device_from_request(request: Request) -> DeviceContext:
    reject_ownership_selectors(request)
    authorization = request.headers.get("authorization", "")
    context = service_from_request(request).authenticate_device(authorization)
    request.state.control_plane_actor_type = "DEVICE"
    request.state.control_plane_actor_id = context.credential_id
    return context


def reject_ownership_selectors(request: Request) -> None:
    forbidden_headers = ("x-tenant-id", "x-deployment-id", "x-site-id", "x-screen-id")
    forbidden_query = {"tenant_id", "deployment_id", "site_id", "screen_id"}
    if any(request.headers.get(name) is not None for name in forbidden_headers) or any(
        name in request.query_params for name in forbidden_query
    ):
        raise ControlPlaneError(
            400,
            "INVALID_REQUEST",
            "Ownership is derived from the authenticated credential",
        )


@router.post(f"{CONTROL_PREFIX}/auth/sessions")
def create_auth_session(payload: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    require_origin(request)
    issue = service_from_request(request).login(payload.username, payload.password)
    _set_session_response(response, issue.cookie_value, issue.csrf_token)
    return issue.response


@router.get(f"{CONTROL_PREFIX}/auth/session")
def get_current_auth_session(request: Request, response: Response) -> dict[str, Any]:
    context = session_from_request(request)
    response.headers["ETag"] = f'"session:{context.revision}"'
    response.headers["Cache-Control"] = "no-store"
    return service_from_request(request).current_session(context)


@router.post(f"{CONTROL_PREFIX}/auth/session:refresh-csrf")
def refresh_csrf_token(request: Request, response: Response) -> dict[str, Any]:
    require_origin(request)
    context = session_from_request(request)
    csrf_token, result = service_from_request(request).refresh_csrf(context)
    response.headers["X-CSRF-Token"] = csrf_token
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/auth/session:reauthenticate")
def reauthenticate_auth_session(
    payload: ReauthenticateRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).reauthenticate(
        context,
        payload.password,
        if_match,
        idempotency_key,
    )
    if not result.replayed:
        if result.cookie_value is None or result.csrf_token is None:
            raise RuntimeError("Reauthentication result omitted new session material")
        _set_session_response(response, result.cookie_value, result.csrf_token)
    else:
        response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = result.response["etag"]
    return result.response


@router.delete(f"{CONTROL_PREFIX}/auth/session")
def delete_current_auth_session(request: Request, response: Response) -> dict[str, Any]:
    context = mutating_session(request)
    service_from_request(request).logout(context)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"signed_out": True}


@router.get(f"{CONTROL_PREFIX}/users")
def list_users(request: Request) -> dict[str, Any]:
    context = session_from_request(request)
    return {"items": service_from_request(request).list_users(context.principal)}


@router.get(f"{CONTROL_PREFIX}/role-definitions")
def list_role_definitions(request: Request) -> dict[str, Any]:
    context = session_from_request(request)
    return {"items": service_from_request(request).role_definitions(context.principal)}


@router.get(f"{CONTROL_PREFIX}/sites")
def list_sites(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=20, max_length=200),
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).list_sites(
        context.principal,
        limit=limit,
        cursor=cursor,
    )


@router.get(f"{CONTROL_PREFIX}/sites/{{site_id}}")
def get_site(site_id: str, request: Request, response: Response) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_site(context.principal, site_id)
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/screen-groups")
def list_screen_groups(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=20, max_length=200),
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).list_screen_groups(
        context.principal,
        limit=limit,
        cursor=cursor,
    )


@router.get(f"{CONTROL_PREFIX}/screen-groups/{{screen_group_id}}")
def get_screen_group(
    screen_group_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_screen_group(
        context.principal,
        screen_group_id,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/sites/{{site_id}}/screen-groups", status_code=201)
def create_screen_group(
    site_id: str,
    payload: ScreenGroupCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).create_screen_group(
        context.principal,
        site_id=site_id,
        slug=payload.slug,
        display_name=payload.display_name,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.patch(f"{CONTROL_PREFIX}/screen-groups/{{screen_group_id}}")
def update_screen_group(
    screen_group_id: str,
    payload: ScreenGroupUpdateRequest,
    request: Request,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    if if_match is None:
        raise ControlPlaneError(428, "PRECONDITION_REQUIRED", "If-Match is required")
    if (
        ("slug" in payload.model_fields_set and payload.slug is None)
        or ("display_name" in payload.model_fields_set and payload.display_name is None)
        or ("member_screen_ids" in payload.model_fields_set and payload.member_screen_ids is None)
    ):
        raise ControlPlaneError(422, "VALIDATION_ERROR", "Explicit null is not allowed")
    result = service_from_request(request).update_screen_group(
        context.principal,
        screen_group_id,
        slug=payload.slug if "slug" in payload.model_fields_set else None,
        display_name=(payload.display_name if "display_name" in payload.model_fields_set else None),
        member_screen_ids=(
            payload.member_screen_ids if "member_screen_ids" in payload.model_fields_set else None
        ),
        if_match=if_match,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/screen-instances")
def list_screen_instances(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=20, max_length=200),
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).list_screen_instances(
        context.principal,
        limit=limit,
        cursor=cursor,
    )


@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}")
def get_screen_instance(
    screen_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_screen_instance(context.principal, screen_id)
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/sites/{{site_id}}/screen-instances", status_code=201)
def create_screen_instance(
    site_id: str,
    payload: ScreenInstanceCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).create_screen_instance(
        context.principal,
        site_id=site_id,
        slug=payload.slug,
        display_name=payload.display_name,
        fvs_binding_ref=payload.fvs_binding_ref,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.patch(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}")
def update_screen_instance(
    screen_id: str,
    payload: ScreenInstanceUpdateRequest,
    request: Request,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    if if_match is None:
        raise ControlPlaneError(428, "PRECONDITION_REQUIRED", "If-Match is required")
    if ("slug" in payload.model_fields_set and payload.slug is None) or (
        "display_name" in payload.model_fields_set and payload.display_name is None
    ):
        raise ControlPlaneError(422, "VALIDATION_ERROR", "Explicit null is not allowed")
    result = service_from_request(request).update_screen_instance(
        context.principal,
        screen_id,
        slug=payload.slug if "slug" in payload.model_fields_set else None,
        display_name=(payload.display_name if "display_name" in payload.model_fields_set else None),
        fvs_binding_ref_set="fvs_binding_ref" in payload.model_fields_set,
        fvs_binding_ref=payload.fvs_binding_ref,
        if_match=if_match,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(
    f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/digital-human-instances",
    status_code=201,
)
def create_digital_human_instance(
    screen_id: str,
    payload: DigitalHumanInstanceCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    del payload
    context = mutating_session(request)
    result = service_from_request(request).create_digital_human_instance(
        context.principal,
        screen_id,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/digital-human-instances/{{digital_human_instance_id}}")
def get_digital_human_instance(
    digital_human_instance_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_digital_human_instance(
        context.principal,
        digital_human_instance_id,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/runtime-binding")
def get_control_plane_runtime_binding(
    screen_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_runtime_binding(context.principal, screen_id)
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/users", status_code=202)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: Annotated[str | None, Header(alias="High-Risk-Action-ID")] = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).request_or_execute_user_creation(
        context,
        normalized_username=payload.normalized_username,
        display_name=payload.display_name,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "USER_CREATED":
        response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(f"{CONTROL_PREFIX}/high-risk-actions")
def list_pending_high_risk_actions(request: Request) -> dict[str, Any]:
    context = session_from_request(request)
    return {"items": service_from_request(request).list_pending_actions(context.principal)}


@router.get(f"{CONTROL_PREFIX}/high-risk-actions/{{action_id}}")
def get_high_risk_action(action_id: str, request: Request, response: Response) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_action(context.principal, action_id)
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/high-risk-actions/{{action_id}}:approve")
def approve_high_risk_action(
    action_id: str,
    payload: ApprovalRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).approve_action(
        context,
        action_id,
        expected_request_digest=payload.expected_request_digest,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/high-risk-actions/{{action_id}}:reject")
def reject_high_risk_action(
    action_id: str,
    payload: ApprovalRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).reject_action(
        context,
        action_id,
        expected_request_digest=payload.expected_request_digest,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/device-enrollments", status_code=202)
def issue_device_enrollment(
    screen_id: str,
    payload: ReasonRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: Annotated[str | None, Header(alias="High-Risk-Action-ID")] = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).request_or_execute_enrollment(
        context,
        screen_id=screen_id,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "DEVICE_ENROLLMENT_ISSUED":
        response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(f"{CONTROL_PREFIX}/device-enrollments/{{enrollment_id}}")
def get_device_enrollment(enrollment_id: str, request: Request, response: Response) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).get_enrollment(context.principal, enrollment_id)
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/device-credentials/{{credential_id}}")
def get_device_credential_metadata(
    screen_id: str,
    credential_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).credential_metadata(
        context.principal,
        screen_id,
        credential_id,
    )
    response.headers["ETag"] = result["family_etag"]
    return result


@router.post(
    f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/device-credentials/{{credential_id}}:revoke",
    status_code=202,
)
def revoke_device_credential(
    screen_id: str,
    credential_id: str,
    payload: DeviceRevokeRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: Annotated[str | None, Header(alias="High-Risk-Action-ID")] = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).request_or_execute_device_revoke(
        context,
        screen_id=screen_id,
        credential_id=credential_id,
        expected_credential_epoch=payload.expected_credential_epoch,
        if_match=if_match,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "DEVICE_CREDENTIAL_FAMILY_REVOKED":
        response.status_code = 200
    return result


@router.get(f"{CONTROL_PREFIX}/audit-events")
def list_audit_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    context = session_from_request(request)
    return {"items": service_from_request(request).list_audit_events(context.principal, limit)}


@router.post(f"{CONTROL_PREFIX}/config-drafts", status_code=201)
def create_config_draft(
    payload: ConfigDraftCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.create_config_draft(
        context.principal,
        target_type=payload.target_type,
        target_id=payload.target_id,
        schema_version=payload.schema_version,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}")
def get_config_draft(
    draft_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).p1_3.get_config_draft(
        context.principal,
        draft_id,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.put(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}/spec")
def replace_config_draft_spec(
    draft_id: str,
    payload: ConfigDraftSpecRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.replace_config_draft_spec(
        context.principal,
        draft_id,
        spec=payload.model_dump(),
        if_match=if_match,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:validate")
def validate_config_draft(
    draft_id: str,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.validate_config_draft(
        context.principal,
        draft_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:preview")
def preview_config_draft(
    draft_id: str,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.preview_config_draft(
        context.principal,
        draft_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:submit-for-approval")
def submit_config_draft_approval(
    draft_id: str,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.submit_config_draft(
        context.principal,
        draft_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:approve")
def approve_config_draft(
    draft_id: str,
    payload: ConfigDraftDecisionRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.decide_config_draft(
        context,
        draft_id,
        decision="APPROVED",
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:reject")
def reject_config_draft(
    draft_id: str,
    payload: ConfigDraftDecisionRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.decide_config_draft(
        context,
        draft_id,
        decision="REJECTED",
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:revise")
def revise_config_draft(
    draft_id: str,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.revise_config_draft(
        context.principal,
        draft_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:abandon")
def abandon_config_draft(
    draft_id: str,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.abandon_config_draft(
        context.principal,
        draft_id,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(f"{CONTROL_PREFIX}/config-drafts/{{draft_id}}:release", status_code=201)
def create_config_release(
    draft_id: str,
    payload: ConfigReleaseCreateRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.create_config_release(
        context.principal,
        draft_id,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/config-releases/{{release_id}}")
def get_config_release(
    release_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    context = session_from_request(request)
    result = service_from_request(request).p1_3.get_config_release(
        context.principal,
        release_id,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.get(f"{CONTROL_PREFIX}/config-release-diffs")
def diff_config_releases(
    request: Request,
    from_release_id: str = Query(alias="from", min_length=1, max_length=200),
    to_release_id: str = Query(alias="to", min_length=1, max_length=200),
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).p1_3.diff_config_releases(
        context.principal,
        from_release_id,
        to_release_id,
    )


@router.post(
    f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/publications",
    status_code=202,
)
def publish_config_to_screen(
    screen_id: str,
    payload: PublishScreenRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: HighRiskActionHeader = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.publish_to_screen(
        context,
        screen_id,
        release_id=payload.release_id,
        release_target_id=payload.release_target_id,
        expected_binding_generation=payload.expected_binding_generation,
        runtime_if_match=if_match,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "CONFIG_RELEASE_PUBLISHED":
        response.status_code = 201
    return result


@router.post(
    f"{CONTROL_PREFIX}/screen-groups/{{screen_group_id}}/publications",
    status_code=202,
)
def publish_config_to_group(
    screen_group_id: str,
    payload: PublishGroupRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: HighRiskActionHeader = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.publish_to_group(
        context,
        screen_group_id,
        release_id=payload.release_id,
        group_if_match=if_match,
        targets=[item.model_dump() for item in payload.targets],
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "CONFIG_RELEASE_PUBLISHED":
        response.status_code = 201
    return result


@router.get(f"{CONTROL_PREFIX}/publications/{{publication_id}}")
def get_publication(
    publication_id: str,
    request: Request,
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).p1_3.get_publication(
        context.principal,
        publication_id,
    )


@router.post(
    f"{CONTROL_PREFIX}/screen-instances/{{screen_id}}/rollbacks",
    status_code=202,
)
def rollback_config_on_screen(
    screen_id: str,
    payload: RollbackScreenRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: HighRiskActionHeader = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.rollback_screen(
        context,
        screen_id,
        source_release_target_id=payload.source_release_target_id,
        expected_binding_generation=payload.expected_binding_generation,
        runtime_if_match=if_match,
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "CONFIG_ROLLBACK_PUBLISHED":
        response.status_code = 201
    return result


@router.post(
    f"{CONTROL_PREFIX}/screen-groups/{{screen_group_id}}/rollbacks",
    status_code=202,
)
def rollback_config_on_group(
    screen_group_id: str,
    payload: RollbackGroupRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: HighRiskActionHeader = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.rollback_group(
        context,
        screen_group_id,
        source_targets=[item.model_dump() for item in payload.source_targets],
        group_if_match=if_match,
        targets=[item.model_dump() for item in payload.targets],
        reason=payload.reason,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "CONFIG_ROLLBACK_PUBLISHED":
        response.status_code = 201
    return result


@router.get(f"{CONTROL_PREFIX}/storage-profile")
def get_storage_profile(request: Request) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).p1_3.get_storage_profile(context.principal)


@router.post(f"{CONTROL_PREFIX}/backups", status_code=201)
def create_backup(
    payload: BackupCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    return service_from_request(request).p1_3.create_backup(
        context.principal,
        reason=payload.reason,
        idempotency_key=idempotency_key,
    )


@router.get(f"{CONTROL_PREFIX}/backups/{{backup_id}}")
def get_backup(
    backup_id: str,
    request: Request,
) -> dict[str, Any]:
    context = session_from_request(request)
    return service_from_request(request).p1_3.get_backup(
        context.principal,
        backup_id,
    )


@router.post(f"{CONTROL_PREFIX}/backups/{{backup_id}}:verify")
def verify_backup(
    backup_id: str,
    request: Request,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    return service_from_request(request).p1_3.verify_backup(
        context.principal,
        backup_id,
        idempotency_key=idempotency_key,
    )


@router.post(f"{CONTROL_PREFIX}/restore-plans", status_code=201)
def create_restore_plan(
    payload: RestorePlanCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.create_restore_plan(
        context,
        backup_id=payload.backup_id,
        idempotency_key=idempotency_key,
    )
    response.headers["ETag"] = result["etag"]
    return result


@router.post(
    f"{CONTROL_PREFIX}/restore-plans/{{restore_plan_id}}:execute",
    status_code=202,
)
def execute_restore_plan(
    restore_plan_id: str,
    payload: RestorePlanExecuteRequest,
    request: Request,
    response: Response,
    if_match: IfMatchHeader,
    idempotency_key: IdempotencyKeyHeader,
    high_risk_action_id: HighRiskActionHeader = None,
) -> dict[str, Any]:
    context = mutating_session(request)
    result = service_from_request(request).p1_3.execute_restore_plan(
        context,
        restore_plan_id,
        confirmation=payload.confirmation,
        reason=payload.reason,
        if_match=if_match,
        idempotency_key=idempotency_key,
        high_risk_action_id=high_risk_action_id,
    )
    if result.get("kind") == "RESTORE_COMPLETED":
        response.status_code = 200
    return result


@router.post(f"{DEVICE_PREFIX}/enrollments:claim")
def claim_device_enrollment(
    payload: EnrollmentClaimRequest,
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    result = service_from_request(request).claim_enrollment(payload.enrollment_token, idempotency_key)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(f"{DEVICE_PREFIX}/credentials:rotate")
def rotate_device_credential(
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = device_from_request(request)
    result = service_from_request(request).rotate_device(context, idempotency_key=idempotency_key)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(f"{DEVICE_PREFIX}/runtime-binding")
def get_device_runtime_binding(request: Request) -> dict[str, Any]:
    context = device_from_request(request)
    return service_from_request(request).device_trust_status(context)


@router.get(f"{DEVICE_PREFIX}/config-releases/current")
def get_device_current_release(request: Request) -> dict[str, Any]:
    context = device_from_request(request)
    return service_from_request(request).p1_3.get_device_current_release(context)


@router.post(f"{DEVICE_PREFIX}/config-releases/{{release_target_id}}:ack")
def acknowledge_device_release(
    release_target_id: str,
    payload: DeviceReleaseAcknowledgementRequest,
    request: Request,
    idempotency_key: IdempotencyKeyHeader,
) -> dict[str, Any]:
    context = device_from_request(request)
    return service_from_request(request).p1_3.acknowledge_device_release(
        context,
        release_target_id,
        binding_generation=payload.binding_generation,
        content_hash=payload.content_hash,
        idempotency_key=idempotency_key,
    )


async def control_plane_error_handler(request: Request, exc: ControlPlaneError) -> JSONResponse:
    service = getattr(request.app.state, "control_plane_service", None)
    actor_type = getattr(request.state, "control_plane_actor_type", None)
    if service is not None and actor_type is not None:
        try:
            service.record_denial(
                actor_type=actor_type,
                actor_id=getattr(request.state, "control_plane_actor_id", None),
                target_id=f"{request.method} {request.url.path}",
                code=exc.code,
            )
        except (sqlite3.Error, ValueError):
            logger.exception("Failed to append sanitized control-plane denial audit")
    request_id = getattr(request.state, "request_id", None)
    content: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
        "request_id": request_id,
    }
    if exc.details:
        content["error"]["details"] = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"Cache-Control": "no-store"},
    )


def sanitized_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in error.items() if key not in {"input", "ctx", "url"}}
        for error in exc.errors()
    ]


def _set_session_response(response: Response, cookie_value: str, csrf_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        cookie_value,
        max_age=8 * 60 * 60,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.headers["X-CSRF-Token"] = csrf_token
    response.headers["Cache-Control"] = "no-store"
