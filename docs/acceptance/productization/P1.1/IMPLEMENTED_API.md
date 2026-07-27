# P1.1 Candidate Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_IN_PROGRESS`
- Scope: factual P1.1 candidate API; not an accepted production-support claim
- Target source: [../../../product/contracts/CONTROL_PLANE_API.md](../../../product/contracts/CONTROL_PLANE_API.md)

The existing POC routes in [../../../06_API_CONTRACT.md](../../../06_API_CONTRACT.md) keep their meanings. P1.1 adds the separate namespaces below without changing `/api/config/*`, `/api/ops/*` or `/api/screen/*`.

## Implemented Control-Plane Routes

| Operation | Route | Implemented P1.1 behavior |
| --- | --- | --- |
| `createAuthSession` | `POST /api/v1/control-plane/auth/sessions` | Argon2id login, progressive lockout, exact Origin, opaque Secure / HttpOnly cookie and header-only CSRF delivery |
| `getCurrentAuthSession` | `GET /api/v1/control-plane/auth/session` | Sanitized current user, roles, permissions and session ETag; never rotates or returns CSRF |
| `refreshCsrfToken` | `POST /api/v1/control-plane/auth/session:refresh-csrf` | Exact-Origin, authenticated CSRF rotation; plaintext only in `X-CSRF-Token` |
| `reauthenticateAuthSession` | `POST /api/v1/control-plane/auth/session:reauthenticate` | Password confirmation plus session ETag; revokes predecessor and returns a rotated cookie / CSRF pair |
| `deleteCurrentAuthSession` | `DELETE /api/v1/control-plane/auth/session` | Revokes the server-side session and clears the cookie |
| `listUsers` | `GET /api/v1/control-plane/users` | `user.manage`; sanitized user and role-assignment metadata |
| `listRoleDefinitions` | `GET /api/v1/control-plane/role-definitions` | `role.assign`; exact `p1_roles_v1` catalog |
| `createUser` | `POST /api/v1/control-plane/users` | Different-user typed approval; execution creates only `PROVISIONING`, disabled, passwordless, empty-role user |
| `listPendingHighRiskActions` | `GET /api/v1/control-plane/high-risk-actions` | `risk.approve`; filters by the approver's underlying operation permission |
| `getHighRiskAction` | `GET /api/v1/control-plane/high-risk-actions/{id}` | Initiator or authorized approver; sanitized digest and state only |
| `approveHighRiskAction` | `POST /api/v1/control-plane/high-risk-actions/{id}:approve` | Different user, recent reauthentication, exact digest / ETag and idempotency; records evidence only |
| `rejectHighRiskAction` | `POST /api/v1/control-plane/high-risk-actions/{id}:reject` | Same separation as approval; no protected effect |
| `issueDeviceEnrollment` | `POST /api/v1/control-plane/screen-instances/{screen_id}/device-enrollments` | `device.enroll`, different-user approval and exact trust-fixture target |
| `getDeviceEnrollment` | `GET /api/v1/control-plane/device-enrollments/{id}` | Sanitized state and ETag; no enrollment material |
| `getDeviceCredentialMetadata` | `GET /api/v1/control-plane/screen-instances/{screen_id}/device-credentials/{credential_id}` | `device.revoke`; family ETag / epoch and non-secret credential state |
| `revokeDeviceCredential` | `POST /api/v1/control-plane/screen-instances/{screen_id}/device-credentials/{credential_id}:revoke` | Different-user approval, family ETag and epoch; atomically revokes active and pending credentials |
| `listAuditEvents` | `GET /api/v1/control-plane/audit-events` | `audit.read`; sanitized append-only HMAC-chained events |

## Implemented Device Routes

| Operation | Route | Implemented P1.1 behavior |
| --- | --- | --- |
| `claimDeviceEnrollment` | `POST /api/v1/device/enrollments:claim` | Atomic single use; returns one screen-bound credential; five-minute encrypted exact replay |
| `rotateDeviceCredential` | `POST /api/v1/device/credentials:rotate` | Active credential only; one pending successor; five-minute encrypted exact replay |
| trust probe within `getDeviceRuntimeBinding` | `GET /api/v1/device/runtime-binding` | Authenticates and activates a pending successor, then returns trust-only metadata plus `runtime_binding_status=NOT_IMPLEMENTED_P1_2` |

`GET /api/v1/device/runtime-binding` does not implement or claim a P1.2 RuntimeBinding. It provides the first successful authenticated-use point needed to prove successor activation while reporting the later inventory/runtime slice as not implemented.

## Browser Security

- Cookie name is `__Host-shuziren_session`; attributes are `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/` and no Domain.
- Duplicate or missing session cookies fail authentication.
- Every control-plane mutation requires an exact configured Origin.
- Every authenticated control-plane mutation except `refreshCsrfToken` requires the session-bound `X-CSRF-Token`.
- Login, reauthentication and one-time material responses use `Cache-Control: no-store`.
- Validation errors remove submitted input, context and URL values before returning details.

## Different-User Approval

The protected route itself creates a `PENDING` action on the first typed request. A different currently authorized user may append `APPROVED` evidence, but approval cannot execute the effect. Only the original initiator can resubmit the identical operation, target, fields and reason with `High-Risk-Action-ID`. A changed command, self-approval, expired action, stale ETag or changed identity epoch fails without an effect.

## Error Shape

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Permission denied",
    "retryable": false
  },
  "request_id": "opaque-request-id"
}
```

The API never returns password verifiers, session / CSRF verifiers, one-time-token verifiers, device verifiers, root keys or audit HMAC keys.
