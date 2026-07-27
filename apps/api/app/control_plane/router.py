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


IdempotencyKeyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=200),
]
IfMatchHeader = Annotated[str, Header(alias="If-Match", min_length=5, max_length=200)]


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
    authorization = request.headers.get("authorization", "")
    context = service_from_request(request).authenticate_device(authorization)
    request.state.control_plane_actor_type = "DEVICE"
    request.state.control_plane_actor_id = context.credential_id
    return context


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
    issue = service_from_request(request).reauthenticate(context, payload.password, if_match)
    _set_session_response(response, issue.cookie_value, issue.csrf_token)
    return issue.response


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
