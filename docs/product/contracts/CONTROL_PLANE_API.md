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

## Deployment Mode And Operational-Posture Gates

Route registration does not imply that an operation is callable in every mode. The service checks deployment mode and the external monotonic operational fence before RBAC or domain effects.

`SETUP` denies all device-surface requests and permits only this exact control-plane allowlist:

```text
completeBootstrap, getDeploymentStatus, activateDeploymentProduction,
createAuthSession, getCurrentAuthSession, refreshCsrfToken, reauthenticateAuthSession,
listOwnAuthSessions, revokeOwnAuthSession, deleteCurrentAuthSession, changeOwnPassword,
listUsers, getUser, getUserRoleAssignments, listRoleDefinitions, createUser, updateUser,
disableUser, enableUser, unlockUser, issuePasswordReset, consumePasswordReset,
listUserAuthSessions, revokeUserAuthSession, replaceUserRoles,
listSites, getSite, listScreenGroups, getScreenGroup, createScreenGroup, updateScreenGroup,
listScreenInstances, getScreenInstance, createScreenInstance, updateScreenInstance,
getDigitalHumanInstance, createDigitalHumanInstance, getRuntimeBinding,
getFineReportIdentityBinding, getHighRiskAction, listPendingHighRiskActions,
approveHighRiskAction, rejectHighRiskAction, createConfigDraft, getConfigDraft,
replaceConfigDraftSpec, reviseConfigDraft, abandonConfigDraft, validateConfigDraft,
previewConfigDraft, getConfigRelease, diffConfigReleases, getStorageProfile,
createBackup, getBackup, verifyBackup, getOperation, listAuditEvents
```

Even inside that list, SETUP forbids device credential issue/claim/rotation/runtime authentication, publication or rollback, runtime release delivery/acknowledgement, Secret or FineReport credential activation, restore cutover and all external device/runtime traffic. Configuration work stops at validation/preview; it cannot submit/approve a production draft or create a production release. Setup user administration is limited to establishing the second distinct custodian-attested platform administrator through the target-person provisioning flow. `SETUP -> PRODUCTION_ACTIVE` is irreversible.

When production posture is `RECOVERY_REQUIRED`, network mutation is denied by default. Only this exact network allowlist remains:

```text
getDeploymentStatus, createAuthSession, getCurrentAuthSession, refreshCsrfToken,
reauthenticateAuthSession, listOwnAuthSessions, revokeOwnAuthSession,
deleteCurrentAuthSession, changeOwnPassword, listUsers, getUser,
getUserRoleAssignments, listRoleDefinitions, listUserAuthSessions, listSites, getSite,
listScreenGroups, getScreenGroup, listScreenInstances, getScreenInstance,
getDigitalHumanInstance, getRuntimeBinding, getFineReportIdentityBinding,
getDeviceEnrollment, getDeviceCredentialMetadata, getSecretMetadata,
getHighRiskAction, listPendingHighRiskActions, getConfigDraft, getConfigRelease,
diffConfigReleases, getPublication, getStorageProfile, getBackup, verifyBackup,
getOperation, listAuditEvents, getDeviceRuntimeBinding, getDeviceCurrentRelease
```

The final two device reads are clamped to the last acknowledged applied target; claim, rotate, acknowledge and heartbeat writes remain denied. `recoverProductionReadiness`, `emergencyReduceAuthority` and `recoverCryptographicReadinessRoot` are local-maintenance-only and never appear as network routes. Their SecurityAuditEvent uses a separate local extension that binds the exact typed authorization/hash, terminal nonce/hash, external audit or tombstone hash, sanitized custodian evidence and committed ledger anchors; DirectOperationAuthorization, HighRiskAction and disaster-envelope IDs are all null. A temporary registry/anchor/key dependency outage creates only an ephemeral fail-closed 503 gate and leaves persisted posture/domain state unchanged; confirmed loss, revocation, invalid evidence or persistent readiness breach appends a `RECOVERY_REQUIRED` fence. Returning to `READY` requires fresh offline authorization, terminal nonce, complete readiness recheck, ledger/external-audit anchors and a new authenticated READY successor; production never returns to SETUP.

## Cross-Cutting Contract

### Authentication And Scope

- Control-plane browser sessions use the host-only `__Host-shuziren_session` cookie with `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/` and no `Domain` attribute. Duplicate or ambiguous session cookies fail authentication. A per-session CSRF token has at least 256 bits of entropy, rotates after authentication, reauthentication and privilege changes, and is never stored in URLs, local storage or logs.
- Every browser state-changing request, including unauthenticated login, requires an exact `Origin` from the server-configured allowlist. Cookie-authenticated mutations also require the bound CSRF token except the single `refreshCsrfToken` bootstrap operation, which still requires exact Origin and only rotates/delivers CSRF material. `GET`, `HEAD` and `OPTIONS` are safe-method exemptions. Missing/mismatched CSRF or origin returns `403 FORBIDDEN`.
- The server stores only an HMAC-SHA-256 CSRF verifier with its `verifier_key_id` under the separate `CSRF_TOKEN_VERIFIER_PEPPER` purpose. `getCurrentAuthSession` is read-only and never rotates CSRF. Exact-origin `refreshCsrfToken` rotates and delivers plaintext only in `X-CSRF-Token` with `Cache-Control: no-store`.
- Successful login returns the session identifier only through `Set-Cookie`, with `Cache-Control: no-store`; it never appears in the JSON body.
- Authentication, reauthentication and every privilege change rotate the session identifier; the old verifier is revoked atomically before the replacement cookie becomes usable. A privilege change also advances the authorization epoch and invalidates prior-epoch sessions.
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

The service stores the normalized request digest, `sensitive_digest_key_id` and result in the same transaction as the domain effect. Same key and same request returns the same resource or Operation; same key and different request returns `409 IDEMPOTENCY_KEY_REUSED`. Secret-bearing requests use HMAC-SHA-256 under `SENSITIVE_REQUEST_DIGEST_HMAC`, separate from the HighRiskAction request HMAC, rather than an unkeyed body hash. Canonicalization is strict typed RFC 8785 JCS with length-safe object encoding. The key is outside the live store, logs and backups, the plaintext body is never persisted as evidence, and key unavailability returns `503 SENSITIVE_REQUEST_DIGEST_KEY_UNAVAILABLE`.

Ordinary command results are retained for at least 24 hours. Exactly four operations—`issuePasswordReset`, `issueDeviceEnrollment`, `claimDeviceEnrollment` and `rotateDeviceCredential`—may replay an exact one-time Secret only for the same idempotency key and request during a five-minute AEAD response window under `ONE_TIME_RESPONSE_ENCRYPTION`; login/session creation is excluded. AES-256-GCM ciphertext persists with nonce, tag, `key_id` and canonical AAD schema, and nonce is unique for that key. AAD binds principal/credential ID, canonical route, idempotency-key digest, request HMAC, operation ID and expiry. Plaintext is never logged and ciphertext is destroyed at expiry or on restore. Expired replay returns `409 ONE_TIME_RESPONSE_REPLAY_EXPIRED`; temporary key unavailability returns `503 ONE_TIME_RESPONSE_KEY_UNAVAILABLE`. Every response uses `Cache-Control: no-store`.

All keyed bootstrap, AuthSession, CSRF, reset, enrollment, setup-grant and device verifiers use HMAC-SHA-256 with a distinct purpose-bound key of at least 256 bits and store the bound verifier `key_id`.

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

The enqueue transaction freezes ImmutableTypedCommand, FrozenPlan and domain intent together with the Operation, durable OutboxRecord, IdempotencyRecord and SecurityAuditEvent. Every asynchronous network record binds `authorization_kind` plus exactly one of `direct_operation_authorization_id`, `high_risk_action_id` or `disaster_recovery_authorization_envelope_id`. `DIRECT_PERMISSION` is legal only for `createBackup` and `verifyBackup`: the API rechecks the active user's person/session/role/scope/credential/eligibility generations and the exact storage-epoch or backup-hash precondition, then atomically creates an immutable DirectOperationAuthorization with the frozen enqueue. Its approver fields are null, its request HMAC uses `SENSITIVE_REQUEST_DIGEST_HMAC`, and it can never authorize a protected, restore or local-maintenance operation. A worker consumes only committed frozen records; it never reconstructs work or reauthorizes by rereading mutable request, identity, draft, plan or Secret-bearing state.

### Production High-Risk Approval

There is no generic endpoint that accepts a free-form `action_type` or payload. Calling an allowlisted protected business endpoint in production validates the caller's underlying permission/scope and creates a typed HighRiskAction from that endpoint's closed schema. It binds method, canonical path, tenant/deployment, requester, target IDs, canonical HMAC-SHA-256 request digest, `request_hmac_key_id`, `If-Match`, target generations, reason, policy version, control-plane epoch and—when applicable—the RecoverySecurityLedger head. The `HIGH_RISK_REQUEST_HMAC` key is held outside the live store, logs and backups, and execution verifies with the exact key ID bound to the action. Rotation retains an old key until the final referencing action is terminal and its evidence-retention interval ends. Temporary request-HMAC key unavailability returns `503 KEY_SERVICE_UNAVAILABLE` and leaves the action unchanged; confirmed revocation/permanent loss returns `409 REQUEST_DIGEST_KEY_EPOCH_CHANGED` and fails it. A Secret-bearing request body is never persisted in HighRiskAction, audit or idempotency evidence.

A different user must approve with `risk.approve`, the same underlying operation permission/scope, recent reauthentication, reason and the expected request digest. Approval appends HighRiskApproval evidence and changes only `PENDING -> APPROVED`; it never queues or executes the command. The original initiator then resubmits the identical typed command to the same protected endpoint with `High-Risk-Action-ID` and initiator reauthentication no more than 10 minutes old. Stale initiator reauthentication returns HTTP 403 with code `RECENT_REAUTHENTICATION_REQUIRED`, leaves the action `APPROVED` until its original TTL and creates no effect. Otherwise the service recomputes the digest, rechecks both users' authorization and all preconditions, and atomically consumes the action with the synchronous domain effect or with ImmutableTypedCommand, FrozenPlan, domain intent, AsyncOperation and durable OutboxRecord enqueue. Request and execution are distinct idempotency phases; execution is scoped by phase + `authorization_kind` + the exactly-one authorization evidence ID + exact command. A pre-commit crash leaves no effect and an approved action. A non-ledger post-commit retry returns the stored consumed result; a ledger-backed retry that finds `PREPARED` must reconcile the domain commit, append `COMMITTED` and advance the anchor before returning success, or fail closed with `503 SECURITY_LEDGER_RECONCILIATION_REQUIRED`. Expired, changed, self-approved or reused evidence fails. Development/test auto-approval requires an explicit audited policy; production cannot bypass four eyes.

## Control-Plane Operations

### Authentication And Users

| Operation ID | Method and path | Permission / rule | Concurrency |
| --- | --- | --- | --- |
| `completeBootstrap` | `POST /bootstrap:complete` | one-time grant-bound bootstrap scope only; client cannot substitute person, user, role or target channel | atomic single use; no-store |
| `getDeploymentStatus` | `GET /deployment` | `operation.read` | deployment/mode/fence/readiness snapshot |
| `activateDeploymentProduction` | `POST /deployment:activate-production` | `deployment.manage`, recent reauth, reason, `production_four_eyes_v1` | idempotency key + deployment `If-Match` + frozen production-readiness snapshot + ledger head |
| `createAuthSession` | `POST /auth/sessions` | public login policy + exact allowed Origin | rate-limited; no one-time response replay |
| `getCurrentAuthSession` | `GET /auth/session` | authenticated | read-only; never rotates or returns plaintext CSRF |
| `refreshCsrfToken` | `POST /auth/session:refresh-csrf` | authenticated + exact Origin; sole cookie mutation exempt from an existing CSRF header | atomically rotate the session-bound CSRF generation; `X-CSRF-Token`; no-store |
| `reauthenticateAuthSession` | `POST /auth/session:reauthenticate` | authenticated password confirmation | idempotency key + current session `If-Match`; no-store |
| `listOwnAuthSessions` | `GET /auth/sessions` | current user only | snapshot pagination |
| `revokeOwnAuthSession` | `DELETE /auth/sessions/{auth_session_id}` | current user owns target | `If-Match` |
| `deleteCurrentAuthSession` | `DELETE /auth/session` | authenticated | idempotent |
| `changeOwnPassword` | `POST /auth/session:change-password` | self-service current password + recent reauthentication | idempotency key + current password/authentication epoch + RecoverySecurityLedger head; no-store |
| `listUsers` | `GET /users` | `user.manage` | snapshot pagination |
| `getUser` | `GET /users/{user_id}` | `user.manage` | ETag |
| `createUser` | `POST /users` | `user.manage`; production four eyes; creates only a disabled, empty-role `PROVISIONING` user | idempotency key + expected RecoverySecurityLedger head |
| `updateUser` | `PATCH /users/{user_id}` | `user.manage`; production four eyes; exact allowlist is `normalized_username`, `display_name` | `If-Match` + ledger head; security/person/role fields forbidden |
| `disableUser` | `POST /users/{user_id}:disable` | `user.manage`, recent reauth, reason | idempotency key + user `If-Match` + ledger head |
| `enableUser` | `POST /users/{user_id}:enable` | `user.manage`, recent reauth, reason | idempotency key + user `If-Match` + ledger head |
| `unlockUser` | `POST /users/{user_id}:unlock` | `user.manage`, recent reauth, reason | idempotency key + `If-Match` |
| `issuePasswordReset` | `POST /users/{user_id}:issue-password-reset` | `user.manage`, recent reauth, reason; production four eyes | idempotency key; target-person/local target-channel delivery only; five-minute encrypted replay |
| `consumePasswordReset` | `POST /auth/password-resets:consume` | one-time reset-token scope only | atomic single use; no-store |
| `getUserRoleAssignments` | `GET /users/{user_id}/role-assignments` | `role.assign` | assignment generation + ETag |
| `listRoleDefinitions` | `GET /role-definitions` | `role.assign` | immutable role-catalog version |
| `listUserAuthSessions` | `GET /users/{user_id}/auth-sessions` | `user.manage` | snapshot pagination |
| `revokeUserAuthSession` | `POST /users/{user_id}/auth-sessions/{auth_session_id}:revoke` | `user.manage`, recent reauth, reason | idempotency key + session `If-Match` |
| `replaceUserRoles` | `PUT /users/{user_id}/role-assignments` | `role.assign`, recent reauth, reason | user `If-Match` + expected assignment generation + RecoverySecurityLedger head |

Passwords appear only in login, bootstrap, reauthentication, own-password change and reset-consumption request schemas. Bootstrap and reset consumption never create a normal browser session. Login has no one-time response replay. Session lists return only non-secret AuthSession record ID, state, timestamps, client label and current marker—never cookie value, digest, CSRF material or reauthentication proof. `createUser` creates a disabled, empty-role `PROVISIONING` account and accepts no password, enabled, role or person-binding field. Its target-only `PROVISIONING_CREDENTIAL_SETUP` reset token can establish only a credential and target possession evidence; it cannot enable or grant a role. A two-custodian person attestation and user binding must precede later enable/role grant. `createUser` and every allowed `updateUser` change use ledger `PREPARED -> database row with sequence -> COMMITTED anchor`; `updateUser` accepts only `normalized_username` and `display_name`, while dedicated operations own enabled, credential, role, session and person-binding transitions.

Role replacement submits the complete canonical assignment set, never a delta. Each assignment uses role catalog `p1_roles_v1` and one exact `DEPLOYMENT`, `SITE` or `SCREEN` scope ID inside the authenticated tenant/deployment. Scope grants only that named resource and descendants, never siblings or ancestors. The server rejects unknown roles/scopes/catalog versions, validates every scope against the role's allowed registry, increments assignment generation and authorization epoch, and commits the full sorted snapshot/hash through the RecoverySecurityLedger protocol. A fresh bootstrap remains `SETUP` and may temporarily have one administrator. `activateDeploymentProduction` performs the one-way `SETUP -> PRODUCTION_ACTIVE` ledger mutation only after two credential-usable deployment administrators and all disaster-readiness checks pass; after activation, `disableUser` and `replaceUserRoles` reject any command that would leave fewer than two.

In production, `createUser`, `updateUser`, `disableUser`, `enableUser`, `unlockUser`, `issuePasswordReset`, `revokeUserAuthSession` and `replaceUserRoles` all use the same typed four-eyes path. Initiator and approver must be different active user IDs and different current custodian-attested person IDs. Network product mutations cannot reduce either the credential-usable administrator count or distinct attested-admin-person count below two; emergency safety revocation is a separate local-only operation that may reduce authority while keeping the deployment fenced in `RECOVERY_REQUIRED`.

### Sites, Groups And Screens

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `listSites` | `GET /sites` | `screen.read` | snapshot pagination |
| `getSite` | `GET /sites/{site_id}` | `screen.read` | ETag |
| `listScreenGroups` | `GET /screen-groups` | `screen.read` | snapshot pagination |
| `getScreenGroup` | `GET /screen-groups/{screen_group_id}` | `screen.read` | ETag |
| `createScreenGroup` | `POST /sites/{site_id}/screen-groups` | `screen.manage` | idempotency key |
| `updateScreenGroup` | `PATCH /screen-groups/{screen_group_id}` | `screen.manage` | `If-Match` |
| `listScreenInstances` | `GET /screen-instances` | `screen.read` | snapshot pagination |
| `getScreenInstance` | `GET /screen-instances/{screen_id}` | `screen.read` | ETag |
| `createScreenInstance` | `POST /sites/{site_id}/screen-instances` | `screen.manage` | idempotency key |
| `updateScreenInstance` | `PATCH /screen-instances/{screen_id}` | `screen.manage` | `If-Match` |
| `createDigitalHumanInstance` | `POST /screen-instances/{screen_id}/digital-human-instances` | `screen.manage` | idempotency key |
| `getDigitalHumanInstance` | `GET /digital-human-instances/{digital_human_instance_id}` | `screen.read` | ETag |
| `getRuntimeBinding` | `GET /screen-instances/{screen_id}/runtime-binding` | `screen.read` | ETag |
| `getFineReportIdentityBinding` | `GET /screen-instances/{screen_id}/fine-report-identity-binding` | all: `screen.read`, `secret.metadata.read` | sanitized ETag |
| `putFineReportIdentityBinding` | `PUT /screen-instances/{screen_id}/fine-report-identity-binding` | all: `screen.manage`, `secret.write`, `finereport.binding.manage`; production four eyes | create `If-None-Match: *`; replace `If-Match` + security generation + ledger head + retiring-target set hash/generations |

There is no direct control-plane write that sets applied release. Desired release changes only through Publication; applied release changes only through a credential-bound device acknowledgement.

### Device Trust

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `issueDeviceEnrollment` | `POST /screen-instances/{screen_id}/device-enrollments` | `device.enroll`, recent reauth, reason, production four eyes | idempotency key + current family generation + RecoverySecurityLedger head; five-minute encrypted one-time response replay |
| `getDeviceEnrollment` | `GET /device-enrollments/{enrollment_id}` | `screen.read` | ETag |
| `revokeDeviceEnrollment` | `POST /device-enrollments/{enrollment_id}:revoke` | `device.enroll`, recent reauth, reason | idempotency key + `If-Match` |
| `getDeviceCredentialMetadata` | `GET /screen-instances/{screen_id}/device-credentials/{credential_id}` | `device.revoke` | sanitized DeviceCredentialFamily ETag, state, family generation and credential epoch |
| `revokeDeviceCredential` | `POST /screen-instances/{screen_id}/device-credentials/{credential_id}:revoke` | `device.revoke`, recent reauth, reason, production four eyes | idempotency key + DeviceCredentialFamily `If-Match` + expected credential epoch + RecoverySecurityLedger head |

Enrollment and credential values are returned only by dedicated one-time operations and never by GET.

`getDeviceCredentialMetadata` resolves the URL credential to its same-screen DeviceCredentialFamily and returns no verifier. Hard revocation locks that family, rechecks its strong ETag, expected credential epoch and ledger head, revokes the complete family and increments the epoch exactly once. Requests authenticated before revocation recheck epoch at commit; stale state returns `RESOURCE_VERSION_CONFLICT`. An idempotent replay cannot increment again.

Enrollment claim atomically rejects a second active family for the screen. Device rotation locks the active family, compares expected epoch and family generation, and permits at most one `ACTIVE` credential and one pending successor per family; successor activation revokes the predecessor in the same transaction, so concurrent different-key requests cannot leave two active credentials or create two successors.

### Secrets

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `createSecret` | `POST /secrets` | `secret.write`, recent reauth, reason | idempotency key |
| `rotateSecret` | `POST /secrets/{secret_ref}:rotate` | `secret.write`, recent reauth, reason, production four eyes | idempotency key + `If-Match` + security generation + ledger head + retiring-target set hash/generations |
| `getSecretMetadata` | `GET /secrets/{secret_ref}` | `secret.metadata.read` | metadata ETag |

Create and rotate requests accept the value. Responses contain only `secret_ref`, type, ownership and rotation metadata. No endpoint reveals a stored value.

Secret rotation and FineReport binding replacement accept only `STAGED` or `EMERGENCY_REVOKE`. `STAGED` makes the new version active and limits the predecessor to the exact already-applied ReleaseTarget set for at most 24 hours; no new release, publication, rollback or delivery may select it. The HighRiskAction binds the canonical exact retiring-target set hash and all affected RuntimeBinding generations. Execution recomputes both; any change returns `HIGH_RISK_ACTION_MISMATCH`. Emergency mode revokes the predecessor immediately and affected runtime fails closed until a new approved release uses the active version.

### High-Risk Approval Evidence

| Operation ID | Method and path | Permission / rule | Concurrency |
| --- | --- | --- | --- |
| `getHighRiskAction` | `GET /high-risk-actions/{high_risk_action_id}` | requester with `operation.read`, or approver with `risk.approve`; same resource scope | ETag |
| `listPendingHighRiskActions` | `GET /high-risk-actions` | per item: `risk.approve` plus the target operation permission and resource scope | snapshot pagination; unauthorized items are omitted |
| `approveHighRiskAction` | `POST /high-risk-actions/{high_risk_action_id}:approve` | `risk.approve`, target-operation permission/scope, different user, recent reauth, reason | idempotency key + `If-Match` + expected request HMAC/`request_hmac_key_id` |
| `rejectHighRiskAction` | `POST /high-risk-actions/{high_risk_action_id}:reject` | same approver rules | idempotency key + `If-Match` + expected request HMAC/`request_hmac_key_id` |

The exact `production_four_eyes_v1` protected set is `activateDeploymentProduction`, `createUser`, `updateUser`, `disableUser`, `enableUser`, `unlockUser`, `issuePasswordReset`, `revokeUserAuthSession`, `replaceUserRoles`, `publishToScreen`, `publishToScreenGroup`, `rollbackScreen`, `rollbackScreenGroup`, `issueDeviceEnrollment`, `revokeDeviceEnrollment`, `revokeDeviceCredential`, `createSecret`, `rotateSecret`, `putFineReportIdentityBinding` and `executeRestorePlan`. Permissions and concurrency shown in the endpoint tables are necessary but do not replace that four-eyes requirement. ConfigDraft ApprovalRecord approves content; HighRiskApproval authorizes an exact operational impact. They are not interchangeable.

### Drafts, Releases And Publication

| Operation ID | Method and path | Permission | Concurrency |
| --- | --- | --- | --- |
| `createConfigDraft` | `POST /config-drafts` | `config.edit_business` or `config.edit_technical` | idempotency key; target envelope + `schema_version` only |
| `getConfigDraft` | `GET /config-drafts/{draft_id}` | `config.read` | ETag |
| `replaceConfigDraftSpec` | `PUT /config-drafts/{draft_id}/spec` | field-level edit permission | `If-Match` |
| `reviseConfigDraft` | `POST /config-drafts/{draft_id}:revise` | `config.edit_business` or `config.edit_technical` | idempotency key + `If-Match`; copy-only legal source-state transition |
| `abandonConfigDraft` | `POST /config-drafts/{draft_id}:abandon` | `config.edit_business` or `config.edit_technical` | idempotency key + `If-Match`; legal source states only |
| `validateConfigDraft` | `POST /config-drafts/{draft_id}:validate` | `config.validate` | idempotency key + `If-Match` |
| `previewConfigDraft` | `POST /config-drafts/{draft_id}:preview` | `config.preview` | idempotency key + `If-Match` |
| `submitConfigDraftApproval` | `POST /config-drafts/{draft_id}:submit-for-approval` | draft editor | idempotency key + `If-Match` |
| `approveConfigDraft` | `POST /config-drafts/{draft_id}:approve` | `config.approve`, reason | idempotency key + `If-Match` |
| `rejectConfigDraft` | `POST /config-drafts/{draft_id}:reject` | `config.approve`, reason | idempotency key + `If-Match` |
| `createConfigRelease` | `POST /config-drafts/{draft_id}:release` | `release.publish` | idempotency key + `If-Match` |
| `getConfigRelease` | `GET /config-releases/{release_id}` | `config.read` | immutable ETag |
| `diffConfigReleases` | `GET /config-release-diffs` | `config.read` | immutable; required `from` and `to` query IDs |
| `publishToScreen` | `POST /screen-instances/{screen_id}/publications` | `release.publish`, recent reauth, reason, production four eyes | idempotency key + RuntimeBinding `If-Match` + expected generation |
| `publishToScreenGroup` | `POST /screen-groups/{screen_group_id}/publications` | `release.publish`, recent reauth, reason, production four eyes | idempotency key + group `If-Match` + per-target ETags/generations |
| `rollbackScreen` | `POST /screen-instances/{screen_id}/rollbacks` | `release.rollback`, recent reauth, reason, production four eyes | idempotency key + RuntimeBinding `If-Match` + expected generation |
| `rollbackScreenGroup` | `POST /screen-groups/{screen_group_id}/rollbacks` | `release.rollback`, recent reauth, reason, production four eyes | idempotency key + group `If-Match` + per-target ETags/generations |
| `getPublication` | `GET /publications/{publication_id}` | `config.read` | immutable plan + target status |
| `cancelPublicationTarget` | `POST /publications/{publication_id}/targets/{screen_id}:cancel` | `release.publish`, reason | idempotency key + target `If-Match`; only queued/waiting |

Validation that finds business/configuration errors returns HTTP 200 with `outcome: INVALID` and findings. Malformed JSON or a request that violates the request schema returns 422.

`createConfigDraft` rejects `spec` or any initial content field. It creates only the requested target envelope, `schema_version` and an empty working spec; the first content must go through `replaceConfigDraftSpec`, including its complete field-level authorization.

Validation creates the ResolutionFingerprint; preview and approval bind it plus the current control-plane epoch. `createConfigRelease` creates only a `NORMAL` release: it revalidates the fingerprint/epoch and atomically creates ConfigRelease plus all ReleaseTargets. `RESOLUTION_FINGERPRINT_STALE` or a changed control-plane epoch requires `reviseConfigDraft`, which copies the current spec into a new `DRAFT` revision even when only membership/inheritance/epoch changed, invalidates old evidence, and then requires validation, preview and approval again. Revising from `APPROVAL_PENDING` atomically withdraws the pending approval; revising from `APPROVED` is legal only when the server recomputes and confirms a stale fingerprint or stale epoch in the same transaction. `reviseConfigDraft` and `abandonConfigDraft` require permissions for every field class currently present, including both technical and `finereport.binding.manage` for a FineReport reference; a business-only editor cannot process a mixed draft. `abandonConfigDraft` preserves all history. Rollback endpoints create only the mutually exclusive `ROLLBACK` provenance branch. Publication references existing targets and never creates or re-resolves them.

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
| `claimDeviceEnrollment` | `POST /enrollments:claim` | one-time enrollment secret | idempotency key; five-minute encrypted one-time response replay |
| `rotateDeviceCredential` | `POST /credentials:rotate` | active DeviceCredential | idempotency key + expected credential epoch/family generation; one pending successor max; five-minute encrypted one-time response replay |
| `getDeviceRuntimeBinding` | `GET /runtime-binding` | active DeviceCredential | credential-derived screen only |
| `getDeviceCurrentRelease` | `GET /config-releases/current` | active DeviceCredential | desired generation and hash |
| `acknowledgeDeviceRelease` | `POST /config-releases/{release_target_id}:ack` | active DeviceCredential | idempotency key + generation/hash |
| `recordDeviceHeartbeat` | `POST /heartbeats` | active DeviceCredential | idempotency key per sample window |

The device path contains no `screen_id` because the credential is the only trusted screen selector.

## API To RecoverySecurityLedger Mapping

The frozen 86-operation registry marks every security-authoritative network mutation explicitly:

| API operation | Ledger mutation |
| --- | --- |
| `completeBootstrap` | `bootstrap_completion` |
| `activateDeploymentProduction` | `deployment_production_activation` |
| `changeOwnPassword`, `consumePasswordReset` | `user_password_change` |
| `createUser` | `user_identity_create` |
| `updateUser` for normalized username/display name | `user_identity_fields_update` |
| `disableUser`, `enableUser` | `user_enabled_state_change` |
| `replaceUserRoles` | `user_role_scope_assignment_replace` |
| `claimDeviceEnrollment` | `device_credential_family_create_from_enrollment_claim` |
| `rotateDeviceCredential`, `revokeDeviceCredential` | `device_credential_family_rotation_expiry_or_revoke` |
| `createSecret`, `rotateSecret` | `secret_record_create_or_rotate` |
| `putFineReportIdentityBinding` | `finereport_identity_binding_create_or_replace` |

Key-registry rotation/revocation and the three local-only operations `recoverProductionReadiness`, `emergencyReduceAuthority` and `recoverCryptographicReadinessRoot` are also ledger-backed and anchored, but are intentionally absent from the 86-operation network registry.

## Safe Error Contract

```json
{
  "type": "urn:shuziren:error:resource-version-conflict",
  "title": "Resource version conflict",
  "status": 412,
  "code": "RESOURCE_VERSION_CONFLICT",
  "detail": "The resource changed. Refresh it and retry the operation.",
  "state_effect": "DOMAIN_STATE_UNCHANGED",
  "request_id": "req-019c...",
  "retryable": false,
  "field_errors": []
}
```

| HTTP | Stable codes | Meaning |
| ---: | --- | --- |
| 400 | `INVALID_REQUEST`, `IDEMPOTENCY_KEY_REQUIRED` | malformed command or missing command key |
| 401 | `AUTHENTICATION_REQUIRED`, `SESSION_EXPIRED`, `DEVICE_CREDENTIAL_INVALID` | caller is not authenticated |
| 403 | `FORBIDDEN`, `RECENT_REAUTHENTICATION_REQUIRED` | authenticated but not allowed; stale execution reauth leaves the action approved until TTL |
| 404 | `RESOURCE_NOT_FOUND` | absent or outside caller boundary |
| 409 | `INVALID_STATE_TRANSITION`, `DUPLICATE_RESOURCE`, `IDEMPOTENCY_KEY_REUSED`, `PUBLISH_TARGET_CHANGED`, `RESOLUTION_FINGERPRINT_STALE`, `HIGH_RISK_APPROVAL_REQUIRED`, `HIGH_RISK_ACTION_MISMATCH`, `ACTIVE_DEVICE_FAMILY_EXISTS`, `SUCCESSOR_ALREADY_PENDING`, `AUTHORITATIVE_CREDENTIAL_MATERIAL_MISSING`, `AUTHENTICATABLE_PLATFORM_ADMIN_REQUIRED`, `IDENTITY_RECONCILIATION_CONFLICT`, `ONE_TIME_RESPONSE_REPLAY_EXPIRED`, `REQUEST_DIGEST_KEY_EPOCH_CHANGED`, `PRODUCTION_READINESS_REQUIRED` | domain, replay, readiness or approval conflict |
| 412 | `RESOURCE_VERSION_CONFLICT`, `ACTIVE_RELEASE_CHANGED`, `SECURITY_LEDGER_HEAD_CHANGED` | stale ETag, generation or ledger anchor |
| 422 | `SCHEMA_VALIDATION_FAILED` | request-schema or field validation failed |
| 428 | `PRECONDITION_REQUIRED` | missing `If-Match` |
| 429 | `RATE_LIMITED` | caller must honor `Retry-After` |
| 503 | `STORAGE_UNAVAILABLE`, `DEPENDENCY_UNAVAILABLE`, `KEY_SERVICE_UNAVAILABLE`, `SECURITY_LEDGER_UNAVAILABLE`, `SECURITY_LEDGER_RECONCILIATION_REQUIRED`, `SENSITIVE_REQUEST_DIGEST_KEY_UNAVAILABLE`, `ONE_TIME_RESPONSE_KEY_UNAVAILABLE`, `RESTORE_CONTINUITY_AUTHENTICATION_FAILED`, `RESTORE_CUTOVER_RECONCILIATION_REQUIRED`, `CRYPTOGRAPHIC_INTEGRITY_FAILURE` | temporary dependency or required reconciliation is retryable only where the registry says so; integrity/authentication failure is fail-closed and non-retryable |
| 500 | `INTERNAL_ERROR` | safe generic failure with request ID |

Every failure contains the exact stable `code`, registry-derived HTTP/body `status`, explicit `state_effect` and registry-derived `retryable` value. Errors never include stack traces, SQL, paths, provider raw bodies, passwords, tokens, DSNs, Secret values or complete sensitive inputs. Permission denial never triggers a more privileged fallback.

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

The response returns the 15-minute enrollment value and uses `Cache-Control: no-store`; the same idempotency key/request may recover that exact value only from its five-minute encrypted replay record.

Device claim:

```http
POST /api/v1/device/enrollments:claim
Idempotency-Key: claim-install-001
Content-Type: application/json

{"enrollment_secret":"<one-time-value>"}
```

The response returns one DeviceCredential. It does not accept a screen ID; exact replay is limited to the same request/key and five-minute encrypted window.

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
  "release_id":"019fa100-0000-7000-8000-000000000404",
  "release_target_id":"019fa100-0000-7000-8000-000000000504",
  "expected_binding_generation":17,
  "reason":"Approved screen-2 update"
}
```

In production the first accepted result is the typed approval request:

```json
{
  "high_risk_action_id":"019fa100-0000-7000-8000-000000000701",
  "state":"PENDING",
  "request_hash":"hmac-sha256:..."
}
```

A different authorized user approves that exact hash. Approval alone leaves the action `APPROVED` and queues nothing. The original initiator resubmits the identical request above with `High-Risk-Action-ID: 019c...701`; the service rechecks the RuntimeBinding ETag/generation and atomically consumes the action with creation of the Publication, AsyncOperation and durable outbox item. The operation cannot change screens 1 or 3. Screen 2 reports desired release D and applied release B until its authenticated acknowledgement.

### Roll Back Without Mutating History

```http
POST /api/v1/control-plane/screen-instances/019fa100-0000-7000-8000-000000000102/rollbacks
Idempotency-Key: rollback-screen-2-to-b
If-Match: "runtime-binding-019fa100-0000-7000-8000-000000000102-r18"
Content-Type: application/json

{
  "source_release_target_id":"019fa100-0000-7000-8000-000000000502",
  "expected_binding_generation":18,
  "reason":"Restore the last accepted behavior"
}
```

Success creates a new release and Publication. It never changes release B or release D.

### Validate Then Execute Restore

`POST /restore-plans` returns findings for the exact backup hash, current control-plane epoch and independently anchored RecoverySecurityLedger head. It freezes exactly one recovery-source mode—`ONLINE_ACTIVE_STORE` or `FULL_LOSS_ACTIVE_STORE_UNAVAILABLE`—and exactly one authorization mode. `NORMAL_API_FOUR_EYES` implies online source. Full loss requires `LOCAL_DISASTER_QUORUM`; local+online is legal only for `NO_CREDENTIAL_USABLE_ENABLED_DEPLOYMENT_PLATFORM_ADMIN`. Local disaster execution does not fabricate an action, approval or user actor. Every execution record binds `authorization_kind`, the entry-condition evidence and exactly one corresponding authorization ID.

Missing authoritative current Secret or FineReport material refuses cutover by default. `DEGRADED_CREDENTIAL_RECOVERY` binds the exact missing-subject set and `confirmation: "RESTORE_DEGRADED_CREDENTIALS"` in whichever authorization evidence is selected: standard mode requires the different-user HighRiskApproval, while disaster mode requires the custodian envelope to sign the same exact set. The two modes remain XOR. Affected subjects stay fail closed for decryption, new release creation, publication, rollback and new runtime delivery; the result is `COMPLETED_DEGRADED`.

Restore authorization is XOR. When the active store and credential-usable administrator path are available, only the standard HighRiskAction path is legal. Only `ACTIVE_STORE_UNAVAILABLE` or `NO_CREDENTIAL_USABLE_ENABLED_DEPLOYMENT_PLATFORM_ADMIN` permits a DisasterRecoveryAuthorizationEnvelope, and only through local maintenance. It requires two of at least three registered active custodian signatures, a 30-minute expiry and single-use nonce; binds deployment, backup hash, ledger head, staged-store ID, exact restore/completion mode and missing-subject set, two sorted existing enabled ledger-authoritative deployment-admin IDs, custodian-registry version, sorted signature key IDs, nonce and expiry; and substitutes only for exact `executeRestorePlan` authorization.

RecoveryPasswordSetupGrant is one shared authority-transition primitive with authorization kind `STANDARD_HIGH_RISK`, `DISASTER_CUSTODIAN` or `PRODUCTION_READINESS_CUSTODIAN`. Normal restore issues exactly the number of selected administrators whose backup credentials are stale or missing (minimum one, maximum two); local disaster issues one grant in `SETUP` and two in any `PRODUCTION_ACTIVE` posture; readiness administrator replacement issues one. Only keyed digest plus verifier key ID and the exact person/generation/authority/nonce/stage bindings persist. Plaintext appears locally once with `no-store` and never enters continuity, ledger, audit, backup or logs. State is `ISSUED -> PROVISIONALLY_CONSUMED -> COMMITTED_CONSUMED`, with terminal `EXPIRED` or `ABORTED_REVOKED`. Any required grant expiry, revocation or staged-authentication failure aborts the complete set atomically. Provisional verifiers become authoritative only after the branch-specific restore or readiness ledger/nonce/fence anchors commit; abort destroys the entire provisional set and terminally consumes the applicable nonce.

`ONLINE_ACTIVE_STORE` first flushes and captures the old live audit head, then its maintenance barrier blocks every producer. SecurityAuditSuffix contains every complete canonical sanitized SecurityAuditEvent from the backup-manifest head exclusive through that barrier-live head inclusive. The previous store pointer is non-null and retained through committed anchor; mismatch or a pre-pointer crash keeps it active.

`FULL_LOSS_ACTIVE_STORE_UNAVAILABLE` has `previous_store_pointer: null`, no live barrier and an empty SecurityAuditSuffix whose backup and barrier heads are both the backup-manifest head. Recovery-period actions are signed `ExternalRecoveryAudit` evidence, followed by a new staged audit chain. A mismatch or pre-pointer crash aborts the preparation and leaves the staged store `UNSERVED`; it never claims to retain or reactivate a missing previous store.

Both source modes delete every restored one-time response replay ciphertext, compute the continuity payload/hash, append/fsync the cutover `PREPARED` record, then authenticate RestoreContinuityEnvelope with HMAC-SHA-256 under `RESTORE_CONTINUITY_ENVELOPE_HMAC`. Its schema binds cutover/deployment/plan IDs, `recovery_source_mode`, authorization mode and evidence hash, prepared sequence/head, ledger-chain and envelope HMAC key IDs, payload hash, previous/staged store IDs, nonce and expiry. Cutover ID plus nonce is single use; startup recomputes the payload and verifies every bound key. One staged transaction inserts and verifies the applicable authorization records, ImmutableTypedCommand, AsyncOperation, OutboxRecord, IdempotencyRecord, RestoreCutoverRecord and full SecurityAuditSuffix. RestoreCutoverRecord also binds `recovery_source_mode`. Before pointer replacement, all three complete RuntimeBindings, every applicable source-mode precondition and every required staged administrator proof for the selected grant-count branch must match.

The staged commit contains RestoreCutoverRecord `CUTOVER_PREPARED`. Atomic pointer replacement is local to the pointer artifact and is not atomic with a database mark; worker/startup infers `POINTER_SWITCHED_PENDING_ANCHOR` from actual pointer plus authenticated evidence. It then appends ledger `COMMITTED`, advances the anchor—making any provisional disaster-password generation authoritative—and records `ANCHOR_COMMITTED_PENDING_FINALIZATION`. A pre-anchor abort restores the retained pointer online or the null pointer in full loss and keeps staged state unserved; after anchor commitment, the system never promises transparent rollback.

Finalization is one database transaction: RestorePlan terminal state, AsyncOperation terminal result, OutboxRecord `DELIVERED` or `SUPPRESSED`, IdempotencyRecord exact result, RestoreCutoverRecord `FINALIZED`, and the next SecurityAuditEvent. Startup with a committed anchor but missing database terminal facts idempotently replays that complete transaction; an already-finalized replay returns the exact stored result and never redispatches the outbox. `SETUP` remains externally unserved. Every finalized production restore appends or confirms `RECOVERY_REQUIRED`; external service resumes only after a separate local `recoverProductionReadiness` uses fresh offline authorization/nonce, rechecks complete readiness, commits ledger and external audit, and appends a READY successor bound to the restore final result. Restored unfinished HighRiskActions fail, and restored config approvals must be redone in the new epoch.

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
