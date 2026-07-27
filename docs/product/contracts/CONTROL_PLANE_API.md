# P1 Target Control-Plane API

## Document Status

- Lifecycle: `TARGET_NOT_IMPLEMENTED`
- Scope: P1 control-plane and screen-device HTTP contracts
- Contract version: `p1.0-target-v1`
- Last reviewed: 2026-07-27

This target API is not implemented. The current POC routes in [../../06_API_CONTRACT.md](../../06_API_CONTRACT.md) retain their existing meaning.

## Namespaces

| Surface | Base path | Identity | Purpose |
| --- | --- | --- | --- |
| Control plane | `/api/v1/control-plane` | local user session + RBAC | users, screens, drafts, publication, storage and audit |
| Screen device | `/api/v1/device` | DeviceCredential | enrollment claim, binding fetch and acknowledgement |

The target API does not reuse or redefine POC `/api/config/*`, `/api/ops/*` or `/api/screen/*`. In particular, POC global override/reload operations are not aliases for ConfigDraft or ConfigRelease.

## Cross-Cutting Contract

### Authentication And Scope

- Control-plane browser sessions use a `Secure`, `HttpOnly`, `SameSite=Strict` cookie plus origin checks and a CSRF token on state-changing requests.
- Successful login returns the session identifier only through `Set-Cookie`, with `Cache-Control: no-store`; it never appears in the JSON body.
- Device calls use `Authorization: DeviceCredential <credential-id>.<secret>`.
- The server derives tenant and deployment from the user session, and tenant/deployment/screen from the DeviceCredential.
- `X-Tenant-ID`, `X-Screen-ID`, body `operator` and any device-supplied ownership selector are rejected.
- Authorization is deny-by-default and checked for every operation and resource.

### Media, Naming And Versioning

- JSON requests and responses use `application/json`; errors use `application/problem+json`.
- Field names use `snake_case`.
- IDs have semantic names such as `auth_session_id`, `screen_id`, `release_target_id` and `publication_id`; bare `session_id` and `version` are not used.
- The URL major version changes only for incompatible HTTP behavior.
- `schema_version`, `resource_revision`, `release_sequence`, `credential_version` and `binding_generation` evolve independently.
- Unknown write fields are rejected. Security-sensitive request schemas use `additionalProperties: false`.

### Request IDs

The client may send `X-Request-ID` if it is a valid opaque identifier. The service always returns its accepted or generated request ID. Audit and asynchronous Operation records include it.

### Optimistic Concurrency

- Mutable resources return a strong ETag and `resource_revision`.
- PUT, PATCH and control-plane commands that mutate an existing resource require `If-Match`; create-only commands use their stated creation precondition.
- Missing precondition returns `428 PRECONDITION_REQUIRED`.
- A stale ETag returns `412 RESOURCE_VERSION_CONFLICT`.
- Single-screen publication/rollback also compares the RuntimeBinding `binding_generation`; group commands compare the group ETag plus every target RuntimeBinding ETag and generation.
- Device acknowledgement is the explicit device-side exception: credential scope plus `binding_generation`, desired target ID and content hash form its dedicated CAS, so it does not use control-plane `If-Match`.

This use of `If-Match` prevents lost updates as defined by [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html).

### Idempotency

All high-risk or resource-creating POST operations require `Idempotency-Key`, including user creation, enrollment, credential rotation/revocation, approval, release, publication, rollback, Secret writes, backup and restore.

The key scope is:

```text
authenticated principal or enrollment-token digest
+ tenant/deployment
+ HTTP method
+ canonical route
```

The service stores the normalized request hash and result in the same transaction as the domain effect. Same key and same request returns the same resource or Operation; same key and different request returns `409 IDEMPOTENCY_KEY_REUSED`.

Ordinary command results are retained for at least 24 hours. One-time enrollment or credential responses may be replayed only for the same token/key during a five-minute encrypted response window and always return `Cache-Control: no-store`. In the machine registry, `response_secret` covers these dedicated authentication/credential response channels as well as one-time JSON bodies; every other operation is `none`.

### Asynchronous Operations

Publication, backup and restore may return:

```json
{
  "operation_id": "019c...",
  "kind": "RESTORE",
  "state": "QUEUED",
  "resource_ref": "/api/v1/control-plane/operations/019c..."
}
```

HTTP `202 Accepted` means queued, not completed. Callers poll the Operation and, for group publication, inspect every target result.

### Production High-Risk Approval

There is no generic endpoint that accepts a free-form `action_type` or payload. Calling an allowlisted protected business endpoint in production validates the caller's underlying permission/scope and creates a typed HighRiskAction from that endpoint's closed schema. It binds method, canonical path, tenant/deployment, requester, target IDs, canonical body, `If-Match`, target generations, reason, policy version and—when applicable—the RecoverySecurityLedger head.

A different user must approve with `risk.approve`, the same underlying operation permission/scope, recent reauthentication, reason and the expected request hash. Approval atomically queues only that exact command; execution rechecks requester and executor authorization and all preconditions. Expired, changed, self-approved or reused evidence fails. Development/test auto-approval requires an explicit audited policy; production cannot bypass four eyes.

## Control-Plane Operations

### Authentication And Users

| Operation ID | Method and path | Permission / rule | Concurrency |
| --- | --- | --- | --- |
| `completeBootstrap` | `POST /bootstrap:complete` | one-time bootstrap-secret scope only | atomic single use; no-store |
| `createAuthSession` | `POST /auth/sessions` | public login policy | rate-limited |
| `getCurrentAuthSession` | `GET /auth/session` | authenticated | N/A |
| `reauthenticateAuthSession` | `POST /auth/session:reauthenticate` | authenticated password confirmation | idempotency key + current session `If-Match`; no-store |
| `listOwnAuthSessions` | `GET /auth/sessions` | current user only | snapshot pagination |
| `revokeOwnAuthSession` | `DELETE /auth/sessions/{auth_session_id}` | current user owns target | `If-Match` |
| `deleteCurrentAuthSession` | `DELETE /auth/session` | authenticated | idempotent |
| `createUser` | `POST /users` | `user.manage` | idempotency key |
| `updateUser` | `PATCH /users/{user_id}` | `user.manage` | `If-Match` |
| `disableUser` | `POST /users/{user_id}:disable` | `user.manage`, recent reauth, reason | idempotency key + user `If-Match` + ledger head |
| `enableUser` | `POST /users/{user_id}:enable` | `user.manage`, recent reauth, reason | idempotency key + user `If-Match` + ledger head |
| `unlockUser` | `POST /users/{user_id}:unlock` | `user.manage`, recent reauth, reason | idempotency key + `If-Match` |
| `issuePasswordReset` | `POST /users/{user_id}:issue-password-reset` | `user.manage`, recent reauth, reason | idempotency key |
| `consumePasswordReset` | `POST /auth/password-resets:consume` | one-time reset-token scope only | atomic single use; no-store |
| `listUserAuthSessions` | `GET /users/{user_id}/auth-sessions` | `user.manage` | snapshot pagination |
| `revokeUserAuthSession` | `POST /users/{user_id}/auth-sessions/{auth_session_id}:revoke` | `user.manage`, recent reauth, reason | idempotency key + session `If-Match` |
| `replaceUserRoles` | `PUT /users/{user_id}/role-assignments` | `role.assign`, recent reauth, reason | `If-Match` |

Passwords appear only in login, bootstrap, reauthentication and reset-consumption request schemas. Bootstrap and reset consumption never create a normal browser session. Session lists return only non-secret AuthSession record ID, state, timestamps, client label and current marker—never cookie value, digest, CSRF material or reauthentication proof. `updateUser` cannot write enabled/security generations; `enableUser` and `disableUser` own those ledger-backed transitions.

### Sites, Groups And Screens

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `listSites` | `GET /sites` | `screen.read` | snapshot pagination |
| `getSite` | `GET /sites/{site_id}` | `screen.read` | ETag |
| `createScreenGroup` | `POST /sites/{site_id}/screen-groups` | `screen.manage` | idempotency key |
| `updateScreenGroup` | `PATCH /screen-groups/{screen_group_id}` | `screen.manage` | `If-Match` |
| `createScreenInstance` | `POST /sites/{site_id}/screen-instances` | `screen.manage` | idempotency key |
| `updateScreenInstance` | `PATCH /screen-instances/{screen_id}` | `screen.manage` | `If-Match` |
| `createDigitalHumanInstance` | `POST /screen-instances/{screen_id}/digital-human-instances` | `screen.manage` | idempotency key |
| `getRuntimeBinding` | `GET /screen-instances/{screen_id}/runtime-binding` | `screen.read` | ETag |
| `getFineReportIdentityBinding` | `GET /screen-instances/{screen_id}/fine-report-identity-binding` | all: `screen.read`, `secret.metadata.read` | sanitized ETag |
| `putFineReportIdentityBinding` | `PUT /screen-instances/{screen_id}/fine-report-identity-binding` | all: `screen.manage`, `secret.write`, `finereport.binding.manage`; production four eyes | create `If-None-Match: *`; replace `If-Match` |

There is no direct control-plane write that sets applied release. Desired release changes only through Publication; applied release changes only through a credential-bound device acknowledgement.

### Device Trust

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `issueDeviceEnrollment` | `POST /screen-instances/{screen_id}/device-enrollments` | `device.enroll`, reason | idempotency key |
| `getDeviceEnrollment` | `GET /device-enrollments/{enrollment_id}` | `screen.read` | ETag |
| `revokeDeviceEnrollment` | `POST /device-enrollments/{enrollment_id}:revoke` | `device.enroll`, recent reauth, reason | idempotency key + `If-Match` |
| `revokeDeviceCredential` | `POST /screen-instances/{screen_id}/device-credentials/{credential_id}:revoke` | `device.revoke`, recent reauth, reason | idempotency key |

Enrollment and credential values are returned only by dedicated one-time operations and never by GET.

### Secrets

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `createSecret` | `POST /secrets` | `secret.write`, recent reauth, reason | idempotency key |
| `rotateSecret` | `POST /secrets/{secret_ref}:rotate` | `secret.write`, recent reauth, reason | idempotency key + `If-Match` |
| `getSecretMetadata` | `GET /secrets/{secret_ref}` | `secret.metadata.read` | metadata ETag |

Create and rotate requests accept the value. Responses contain only `secret_ref`, type, ownership and rotation metadata. No endpoint reveals a stored value.

### High-Risk Approval Evidence

| Operation ID | Method and path | Permission / rule | Concurrency |
| --- | --- | --- | --- |
| `getHighRiskAction` | `GET /high-risk-actions/{high_risk_action_id}` | requester with `operation.read`, or approver with `risk.approve`; same resource scope | ETag |
| `listPendingHighRiskActions` | `GET /high-risk-actions` | `risk.approve` | snapshot pagination |
| `approveHighRiskAction` | `POST /high-risk-actions/{high_risk_action_id}:approve` | `risk.approve`, target-operation permission/scope, different user, recent reauth, reason | idempotency key + `If-Match` + expected request hash |
| `rejectHighRiskAction` | `POST /high-risk-actions/{high_risk_action_id}:reject` | same approver rules | idempotency key + `If-Match` + expected request hash |

Protected endpoints are production publication, rollback, device hard revocation, Secret rotation/replacement, FineReport identity replacement and restore execution. ConfigDraft ApprovalRecord approves content; HighRiskApproval authorizes an exact operational impact. They are not interchangeable.

### Drafts, Releases And Publication

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `createConfigDraft` | `POST /config-drafts` | `config.edit_business` or `config.edit_technical` | idempotency key |
| `getConfigDraft` | `GET /config-drafts/{draft_id}` | `config.read` | ETag |
| `replaceConfigDraftSpec` | `PUT /config-drafts/{draft_id}/spec` | field-level edit permission | `If-Match` |
| `validateConfigDraft` | `POST /config-drafts/{draft_id}:validate` | `config.validate` | idempotency key + `If-Match` |
| `previewConfigDraft` | `POST /config-drafts/{draft_id}:preview` | `config.preview` | idempotency key + `If-Match` |
| `submitConfigDraftApproval` | `POST /config-drafts/{draft_id}:submit-for-approval` | draft editor | idempotency key + `If-Match` |
| `approveConfigDraft` | `POST /config-drafts/{draft_id}:approve` | `config.approve`, reason | idempotency key + `If-Match` |
| `rejectConfigDraft` | `POST /config-drafts/{draft_id}:reject` | `config.approve`, reason | idempotency key + `If-Match` |
| `createConfigRelease` | `POST /config-drafts/{draft_id}:release` | `release.publish` | idempotency key + `If-Match` |
| `getConfigRelease` | `GET /config-releases/{release_id}` | `config.read` | immutable ETag |
| `diffConfigReleases` | `GET /config-release-diffs?from={id}&to={id}` | `config.read` | immutable |
| `publishToScreen` | `POST /screen-instances/{screen_id}/publications` | `release.publish`, recent reauth, reason, production four eyes | idempotency key + RuntimeBinding `If-Match` + expected generation |
| `publishToScreenGroup` | `POST /screen-groups/{screen_group_id}/publications` | `release.publish`, recent reauth, reason, production four eyes | idempotency key + group `If-Match` + per-target ETags/generations |
| `rollbackScreen` | `POST /screen-instances/{screen_id}/rollbacks` | `release.rollback`, recent reauth, reason, production four eyes | idempotency key + RuntimeBinding `If-Match` + expected generation |
| `rollbackScreenGroup` | `POST /screen-groups/{screen_group_id}/rollbacks` | `release.rollback`, recent reauth, reason, production four eyes | idempotency key + group `If-Match` + per-target ETags/generations |
| `getPublication` | `GET /publications/{publication_id}` | `config.read` | immutable plan + target status |
| `cancelPublicationTarget` | `POST /publications/{publication_id}/targets/{screen_id}:cancel` | `release.publish`, reason | idempotency key + target `If-Match`; only queued/waiting |

Validation that finds business/configuration errors returns HTTP 200 with `outcome: INVALID` and findings. Malformed JSON or a request that violates the request schema returns 422.

Validation creates the ResolutionFingerprint; preview and approval bind it. `createConfigRelease` revalidates it and atomically creates ConfigRelease plus all ReleaseTargets. `RESOLUTION_FINGERPRINT_STALE` requires a new draft revision and approval. Publication references existing targets and never creates or re-resolves them.

### Storage, Recovery, Operations And Audit

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `getStorageProfile` | `GET /storage-profile` | `screen.read` | sanitized metadata |
| `createBackup` | `POST /backups` | `backup.create`, reason | idempotency key; returns 202 |
| `getBackup` | `GET /backups/{backup_id}` | `operation.read` | immutable metadata |
| `verifyBackup` | `POST /backups/{backup_id}:verify` | `backup.create` | idempotency key; returns 202 |
| `createRestorePlan` | `POST /restore-plans` | `backup.restore`, recent reauth | idempotency key |
| `executeRestorePlan` | `POST /restore-plans/{restore_plan_id}:execute` | `backup.restore`, recent reauth, reason and confirmation | idempotency key + `If-Match`; returns 202 |
| `abortRestorePlan` | `POST /restore-plans/{restore_plan_id}:abort` | `backup.restore`, reason | idempotency key + `If-Match`; READY only |
| `getOperation` | `GET /operations/{operation_id}` | `operation.read` | ETag |
| `listAuditEvents` | `GET /audit-events` | `audit.read` | cursor pagination |

Storage profile and backup metadata never return database DSNs, credentials, recovery keys or Secret values.

## Device Operations

| Operation ID | Method and path | Identity | Concurrency |
| --- | --- | --- | --- |
| `claimDeviceEnrollment` | `POST /enrollments:claim` | one-time enrollment secret | idempotency key; one-time response |
| `rotateDeviceCredential` | `POST /credentials:rotate` | active DeviceCredential | idempotency key; one-time successor response |
| `getDeviceRuntimeBinding` | `GET /runtime-binding` | active DeviceCredential | credential-derived screen only |
| `getDeviceCurrentRelease` | `GET /config-releases/current` | active DeviceCredential | desired generation and hash |
| `acknowledgeDeviceRelease` | `POST /config-releases/{release_target_id}:ack` | active DeviceCredential | idempotency key + generation/hash |
| `recordDeviceHeartbeat` | `POST /heartbeats` | active DeviceCredential | idempotency key per sample window |

The device path contains no `screen_id` because the credential is the only trusted screen selector.

## Safe Error Contract

```json
{
  "type": "urn:shuziren:error:resource-version-conflict",
  "title": "Resource version conflict",
  "status": 412,
  "code": "RESOURCE_VERSION_CONFLICT",
  "detail": "The resource changed. Refresh it and retry the operation.",
  "request_id": "req-019c...",
  "retryable": false,
  "field_errors": []
}
```

| HTTP | Stable codes | Meaning |
| ---: | --- | --- |
| 400 | `INVALID_REQUEST`, `IDEMPOTENCY_KEY_REQUIRED` | malformed command or missing command key |
| 401 | `AUTHENTICATION_REQUIRED`, `SESSION_EXPIRED`, `DEVICE_CREDENTIAL_INVALID` | caller is not authenticated |
| 403 | `FORBIDDEN`, `RECENT_REAUTHENTICATION_REQUIRED` | authenticated but not allowed |
| 404 | `RESOURCE_NOT_FOUND` | absent or outside caller boundary |
| 409 | `INVALID_STATE_TRANSITION`, `DUPLICATE_RESOURCE`, `IDEMPOTENCY_KEY_REUSED`, `PUBLISH_TARGET_CHANGED`, `RESOLUTION_FINGERPRINT_STALE`, `HIGH_RISK_APPROVAL_REQUIRED`, `HIGH_RISK_ACTION_MISMATCH` | domain or approval conflict |
| 412 | `RESOURCE_VERSION_CONFLICT`, `ACTIVE_RELEASE_CHANGED`, `SECURITY_LEDGER_HEAD_CHANGED` | stale ETag, generation or ledger anchor |
| 422 | `SCHEMA_VALIDATION_FAILED` | request-schema or field validation failed |
| 428 | `PRECONDITION_REQUIRED` | missing `If-Match` |
| 429 | `RATE_LIMITED` | caller must honor `Retry-After` |
| 503 | `STORAGE_UNAVAILABLE`, `DEPENDENCY_UNAVAILABLE`, `SECURITY_LEDGER_UNAVAILABLE` | temporary dependency or required anti-rollback anchor failure |
| 500 | `INTERNAL_ERROR` | safe generic failure with request ID |

Errors never include stack traces, SQL, paths, provider raw bodies, passwords, tokens, DSNs, Secret values or complete sensitive inputs. Permission denial never triggers a more privileged fallback.

## Examples Tied To User Operations

### Issue And Claim A Screen Enrollment

Control-plane request:

```http
POST /api/v1/control-plane/screen-instances/019fa100-0000-7000-8000-000000000102/device-enrollments
Idempotency-Key: enroll-screen-2-001
X-CSRF-Token: <browser-csrf-value>
Content-Type: application/json

{"reason":"Install the approved screen device"}
```

The response returns the 15-minute enrollment value once and uses `Cache-Control: no-store`.

Device claim:

```http
POST /api/v1/device/enrollments:claim
Idempotency-Key: claim-install-001
Content-Type: application/json

{"enrollment_secret":"<one-time-value>"}
```

The response returns one DeviceCredential once. It does not accept a screen ID.

### Update And Validate A Draft

```http
PUT /api/v1/control-plane/config-drafts/019fa100-0000-7000-8000-000000000401/spec
If-Match: "draft-019fa100-0000-7000-8000-000000000401-r7"
Idempotency-Key: draft-1-spec-008
Content-Type: application/json

{
  "welcome_text":"Welcome to this screen",
  "fvs_binding_ref":"fvs-binding-02"
}
```

`schema_version` and target scope are draft-envelope fields set at creation, not editable spec fields. This mixed request requires both business and technical edit permissions because authorization is computed from the changed JSON Pointers. A later validate call binds revision 8, its content hash and ResolutionFingerprint. If another editor already created revision 8, this request returns 412 and does not overwrite it.

### Publish Only Screen 2

```http
POST /api/v1/control-plane/screen-instances/019fa100-0000-7000-8000-000000000102/publications
Idempotency-Key: publish-screen-2-release-d
If-Match: "runtime-binding-019fa100-0000-7000-8000-000000000102-r17"
Content-Type: application/json

{
  "release_id":"019fa100-0000-7000-8000-000000000501",
  "release_target_id":"019fa100-0000-7000-8000-000000000601",
  "expected_binding_generation":17,
  "reason":"Approved screen-2 update"
}
```

In production the first accepted result is the typed approval request:

```json
{
  "high_risk_action_id":"019fa100-0000-7000-8000-000000000701",
  "state":"PENDING",
  "request_hash":"sha256:..."
}
```

A different authorized user approves that exact hash; the service rechecks the RuntimeBinding ETag/generation and then queues the Publication. The operation cannot change screens 1 or 3. Screen 2 reports desired release D and applied release B until its authenticated acknowledgement.

### Roll Back Without Mutating History

```http
POST /api/v1/control-plane/screen-instances/019fa100-0000-7000-8000-000000000102/rollbacks
Idempotency-Key: rollback-screen-2-to-b
If-Match: "runtime-binding-019fa100-0000-7000-8000-000000000102-r18"
Content-Type: application/json

{
  "source_release_target_id":"019fa100-0000-7000-8000-000000000602",
  "expected_binding_generation":18,
  "reason":"Restore the last accepted behavior"
}
```

Success creates a new release and Publication. It never changes release B or release D.

### Validate Then Execute Restore

`POST /restore-plans` returns findings for the exact backup hash, current control-plane epoch and independently anchored RecoverySecurityLedger head. Execution requires the plan ETag, recent reauthentication, a reason, explicit `confirmation: "RESTORE"` and different-user HighRiskApproval bound to the same ledger head. A checksum, schema, Secret-key, ledger/anchor or three-screen binding failure leaves the current store active and returns a safe failed Operation.

## Pagination And Filtering

- Lists use opaque cursor pagination with a default limit of 50 and maximum 200.
- Filters are allowlisted fields; clients cannot submit SQL, arbitrary expressions or field names.
- Audit export is asynchronous and sanitized.
- Sort order always includes a unique ID tie-breaker.

## Compatibility And Deprecation

- Additive response fields may appear inside documented extensible read objects; write objects reject unknown fields.
- Removing or changing a field requires a new API major version or an announced compatibility window.
- Every response includes `api_version`; configuration and release objects also include their schema version.
- Target API examples remain non-executable design evidence until later batches implement and test them.
