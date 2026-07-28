# P1.3 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Result: publish, forward rollback and verified development-preview recovery
- Base accepted runtime: commit `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree `565dbb3567e2a4ae5b872177d97449120477fe8c`
- Base acceptance record: commit `7e7bf28a8393878185d55ea532b4212eee818586`
- Candidate commit: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Candidate tree: `04bcbb940fbedb5fbb8957e538f46a4422e15db2`
- Candidate fingerprint: `8cf8cdb380f849b947a76abeef2ff895fb79f7696effbb1abbdf9bdc0bb04e55` over 29 files
- Target logical schema / migration: `p1_control_plane_001` / `003_publish_rollback_recovery`
- Gate summary: automated candidate gates `PASS`
- Independent review: `PASS`; zero blocking and zero non-blocking findings
- User decision: `通过` on 2026-07-28

This card froze the complete P1.3 result and non-scope before implementation.
The candidate above implements the bounded local development-preview result,
passed its automated gates and final independent review, and was explicitly
accepted without conditions on 2026-07-28. It is now the runtime rollback
baseline for subsequent productization batches.

## Frozen Observable Outcome

P1.3 must deliver one independently usable development-preview slice:

1. The `/manage` console adds a release center where an implementation engineer
   can create a screen- or group-targeted draft, replace its complete spec,
   validate it and produce a clearly labelled Mock preview.
2. A different authorized administrator can approve the exact previewed draft.
   The approved draft creates one immutable `NORMAL` ConfigRelease and one
   immutable ReleaseTarget for every frozen target screen.
3. An authorized publisher can publish an existing ReleaseTarget to one screen
   or publish the complete frozen release to its ScreenGroup. The publication
   changes only each target's desired release and binding generation.
4. An active credential bound to the same screen can fetch and acknowledge the
   exact desired target. Applied state changes only after that acknowledgement.
5. Releases, target content hashes, desired/applied differences, publication
   target states and append-only audit history are visible without exposing a
   Secret.
6. Rollback creates a new immutable `ROLLBACK` ConfigRelease and publishes its
   newly copied ReleaseTarget. It never edits, deletes or repoints history.
7. An authorized operator can create and verify an encrypted local logical
   backup. An authorized administrator can validate and restore that exact
   bundle into a new SQLite store, recover all three screen bindings and retain
   a verified pre-restore store.
8. Restore invalidates browser sessions, one-time replay material and unfinished
   approvals/actions. It preserves the newer live user/role/device security
   state instead of reviving older credentials from the backup.
9. Runtime conversation detail defaults to three-day retention, while users,
   device security history, releases, publications, restore evidence and
   SecurityAuditEvent rows are not deleted by that cleanup.

## Frozen Development-Preview Boundary

The accepted P1.2 runtime is a local `DEVELOPMENT_PREVIEW`, not an activated
production deployment. P1.3 preserves that boundary:

- Preview uses the built-in Mock FVS flow and is labelled `MOCK_PASSED`.
- FVS references remain non-secret inventory/configuration labels with status
  `UNVERIFIED`; no FineReport/FVS/plugin request is made.
- Publication and rollback still require the existing typed two-user
  HighRiskAction workflow. There is no production auto-approval.
- Backup encryption uses purpose-separated key material derived from the
  externally supplied preview root key. The key and root material are never
  stored in the bundle, database, API response, log or evidence.
- The local backup root must differ from the live database path. A same-device
  development path displays a visible warning and cannot be presented as a
  production recovery topology.
- Restore is online-source-only. It requires the active preview store, stages a
  new database, verifies it before pointer replacement and keeps the previous
  store. Full-loss disaster quorum, production OperationalFence, external WORM
  anchor and PostgreSQL restore remain outside this batch.
- Measured preview backup/restore duration is evidence for the local reference
  workflow only. It does not certify a customer RPO/RTO or production support.

## Frozen Configuration Spec

P1.3 implements schema `p1_screen_config_v1` with exactly these writable fields:

| Field | Class | Rule |
| --- | --- | --- |
| `welcome_text` | business | required printable string, 1 to 500 Unicode code points |
| `fvs_binding_ref` | technical | required non-secret reference label, 1 to 512 characters, subject to the accepted P1.2 Secret/DSN rejection policy |

Every effective ReleaseTarget additionally binds the server-resolved
`digital_human_instance_id`, target `screen_id`, schema version and immutable
canonical content hash. Clients cannot set ownership IDs, content hashes,
release IDs, DigitalHumanInstance IDs, Secret references or executable content.

The draft target envelope is exactly one of:

- `SCREEN` with one authorized `screen_id`; or
- `SCREEN_GROUP` with one authorized `screen_group_id`.

Group validation freezes the exact sorted member set and current group revision.
Validation also freezes every target screen revision, RuntimeBinding revision
and generation, active DigitalHumanInstance ID, target set hash and per-screen
effective-content hash. A later target, membership, instance, source or
control-plane epoch change returns `RESOLUTION_FINGERPRINT_STALE` and requires
a new draft revision, validation, preview and approval.

## Frozen Draft And Release Lifecycle

The implemented lifecycle is:

```text
DRAFT
-> VALIDATED
-> PREVIEWED
-> APPROVAL_PENDING
-> APPROVED
-> RELEASED
```

- `createConfigDraft` accepts only the target envelope and schema version. An
  initial `spec` is rejected.
- `replaceConfigDraftSpec` replaces the complete spec only while `DRAFT`,
  requires a current strong ETag and applies field-level permissions atomically.
- Validation failure returns `outcome=INVALID` with sanitized findings and
  leaves the draft in `DRAFT`.
- Preview requires the exact passed validation and returns only Mock evidence.
- Submission freezes the last editor, revision, content hash, fingerprint and
  control-plane epoch.
- Approval requires `config.approve`, recent reauthentication and a user
  different from the last content editor. Rejection preserves history.
- An approved draft is never edited. `reviseConfigDraft` copies legal
  non-terminal source content into a new `DRAFT` revision and invalidates older
  validation/preview/approval evidence.
- `RELEASED` and `ABANDONED` are terminal.
- A `NORMAL` release requires the exact approved evidence. A `ROLLBACK` release
  has no normal-draft provenance and instead stores the exact historical
  source-target map plus consumed HighRiskAction evidence.
- ConfigRelease and ReleaseTarget have no update or delete route.

## Frozen API Slice

All control-plane paths are under `/api/v1/control-plane`; device paths are
under `/api/v1/device`.

### Draft, Release And Diff

| Operation | Method and path | Required behavior |
| --- | --- | --- |
| `createConfigDraft` | `POST /config-drafts` | field-edit permission; idempotency; target envelope only |
| `getConfigDraft` | `GET /config-drafts/{draft_id}` | `config.read`; strong ETag |
| `replaceConfigDraftSpec` | `PUT /config-drafts/{draft_id}/spec` | field permissions; current `If-Match` |
| `reviseConfigDraft` | `POST /config-drafts/{draft_id}:revise` | legal source state; idempotency plus `If-Match` |
| `abandonConfigDraft` | `POST /config-drafts/{draft_id}:abandon` | legal source state; idempotency plus `If-Match` |
| `validateConfigDraft` | `POST /config-drafts/{draft_id}:validate` | `config.validate`; idempotency plus `If-Match` |
| `previewConfigDraft` | `POST /config-drafts/{draft_id}:preview` | `config.preview`; idempotency plus `If-Match` |
| `submitConfigDraftApproval` | `POST /config-drafts/{draft_id}:submit-for-approval` | last editor; idempotency plus `If-Match` |
| `approveConfigDraft` | `POST /config-drafts/{draft_id}:approve` | different `config.approve` user, recent reauthentication |
| `rejectConfigDraft` | `POST /config-drafts/{draft_id}:reject` | `config.approve`; preserves history |
| `createConfigRelease` | `POST /config-drafts/{draft_id}:release` | `release.publish`; approved exact evidence |
| `getConfigRelease` | `GET /config-releases/{release_id}` | `config.read`; immutable ETag |
| `diffConfigReleases` | `GET /config-release-diffs?from=...&to=...` | `config.read`; canonical per-screen JSON-pointer diff |

### Publication, Device Apply And Rollback

| Operation | Method and path | Required behavior |
| --- | --- | --- |
| `publishToScreen` | `POST /screen-instances/{screen_id}/publications` | `release.publish`; typed two-user approval; binding ETag/generation |
| `publishToScreenGroup` | `POST /screen-groups/{screen_group_id}/publications` | typed two-user approval; group ETag and every binding ETag/generation |
| `getPublication` | `GET /publications/{publication_id}` | `config.read`; immutable plan plus target states |
| `rollbackScreen` | `POST /screen-instances/{screen_id}/rollbacks` | `release.rollback`; typed two-user approval; same-screen historical source |
| `rollbackScreenGroup` | `POST /screen-groups/{screen_group_id}/rollbacks` | typed two-user approval; exact source map and frozen target set |
| `getDeviceCurrentRelease` | `GET /config-releases/current` | active DeviceCredential; credential-derived screen only |
| `acknowledgeDeviceRelease` | `POST /config-releases/{release_target_id}:ack` | credential-derived screen; idempotency plus exact generation/hash |

Publication references ReleaseTargets already owned by the release and never
creates or re-resolves them. A single-screen publication must contain exactly
that screen's target. Group publication must match the frozen group release
target set. Each target independently enters `WAITING_FOR_DEVICE` or
`APPLYING`; a matching acknowledgement moves only that target to `ACTIVE`.
Older acknowledgements are retained as stale evidence and cannot change the
current binding.

### Backup, Restore And Storage

| Operation | Method and path | Required behavior |
| --- | --- | --- |
| `getStorageProfile` | `GET /storage-profile` | sanitized development topology, retention and target metadata |
| `createBackup` | `POST /backups` | `backup.create`; reason and idempotency; encrypted verified bundle |
| `getBackup` | `GET /backups/{backup_id}` | `operation.read`; immutable safe metadata |
| `verifyBackup` | `POST /backups/{backup_id}:verify` | `backup.create`; fresh decrypt/hash/database validation |
| `createRestorePlan` | `POST /restore-plans` | `backup.restore`; recent reauthentication; exact verified backup |
| `executeRestorePlan` | `POST /restore-plans/{restore_plan_id}:execute` | typed two-user approval, confirmation, idempotency and `If-Match` |

The preview implementation may complete these bounded local operations
synchronously, but the response must distinguish requested, verified and
completed states. It must never return `202` while already reporting a terminal
result.

## Frozen Database And Migration Boundary

- Preserve accepted migrations `001_initial_identity_device_trust` and
  `002_three_screen_inventory` byte for byte.
- Add the checksummed forward-only migration
  `003_publish_rollback_recovery`.
- Rebuild RuntimeBinding only as needed to permit desired/applied release
  targets and generations greater than zero. Existing ownership, screen,
  DigitalHumanInstance and null-release P1.2 values must remain exact.
- Add immutable draft revision/evidence, release/target, publication/target,
  binding-history, backup and restore-plan records with ownership-aware foreign
  keys and unique constraints.
- Add no update/delete path for releases, release targets, publication plans,
  binding history or SecurityAuditEvent rows.
- Empty initialization, accepted-P1.2 copy upgrade and repeat initialization
  must converge on the exact migration registry. Unknown, reordered, missing or
  checksum-tampered migrations fail closed.
- Acceptance upgrade and restore always operate on copies and retain a verified
  pre-change store.

## Frozen Backup Bundle

Each completed preview backup is an atomically finalized directory:

```text
backup-<backup_id>/
├─ manifest.json
├─ payload.aes256gcm
├─ checksums.sha256
└─ verification.json
```

The authenticated encrypted payload contains an engine-neutral logical export
and a SQLite online snapshot. The plaintext-safe manifest contains only safe
ownership IDs, schema/product/migration versions, row counts, audit head,
ciphertext size/hash, AEAD nonce, purpose key ID, canonical AAD hash and
timestamps. It contains no key material, password verifier, session/cookie,
CSRF, token, device credential, authorization header, DSN or Secret value.

Verification decrypts to a temporary staging location, checks every hash,
migration/checksum, foreign key, immutable release content hash and all three
complete RuntimeBindings, then destroys plaintext staging material.

## User Result Scenarios

1. Sign in as `implementation`, create a Screen 2 draft with a new welcome text
   and Mock FVS reference, validate it and inspect the Mock preview and frozen
   per-screen fingerprint.
2. Submit that exact draft. Sign in as `admin-a`, reauthenticate and approve it,
   then create the immutable normal release.
3. Publish the release only to Screen 2 through the typed two-user workflow.
   Confirm Screen 2 desired release/generation changes while every RuntimeBinding
   field and ETag for Screens 1 and 3 remains unchanged.
4. Claim or use an active Screen 2 device credential, fetch the credential-bound
   current release and acknowledge the exact generation/hash. Confirm only
   Screen 2 applied state and acknowledgement marker change.
5. Create and publish a later Screen 2 release, compare both versions, then
   rollback to the first target. Confirm rollback creates a third immutable
   release and leaves both sources unchanged.
6. Create one group-targeted release and publish it with exact group and
   per-screen preconditions. Confirm every target reports its own state and no
   non-member or cross-Site screen can enter the plan.
7. Sign in as `auditor`, inspect releases, differences and audit evidence, and
   confirm every draft, approval, publication, rollback, backup and restore
   mutation is denied by the API.
8. Create and verify an encrypted backup, change all three desired/applied
   bindings, validate and execute an authorized restore, then confirm the
   backup's three bindings return, the newer live user/role/device security
   state remains authoritative, old sessions/credentials do not revive and the
   pre-restore store is retained.

## Required Gates

- Ruff format/check, API import and the complete backend test suite.
- Empty initialization, accepted-P1.2 upgrade, repeat migration, checksum
  tamper rejection and verified pre-`003` rollback copy.
- Draft illegal transitions, field-level RBAC, stale ETag/fingerprint/epoch,
  wrong-editor approval, self-approval and changed-command idempotency tests.
- ConfigRelease/ReleaseTarget immutability, provenance XOR, content-hash,
  target-set and cross-screen ownership tests.
- Single-screen and group publication tests with complete before/after snapshots
  of all three RuntimeBindings, DigitalHumanInstances, device families and ETags.
- Credential-bound fetch/acknowledgement, stale generation/hash, wrong-screen,
  revoked/predecessor credential and acknowledgement replay tests.
- Rollback forward-copy equality, historical immutability and mixed/cross-screen
  source rejection tests.
- Encrypted bundle structure, separate-key/no-key-in-bundle, tamper, wrong-key,
  SQLite WAL snapshot, logical-export, foreign-key and release-hash tests.
- Restore-to-stage, pre-cutover failure retention, session/action/replay
  invalidation, live security-state reconciliation, three-screen binding
  recovery and retained pre-restore-store tests.
- Runtime-detail cleanup at three days plus explicit proof that user, release,
  publication, device-security and audit records remain.
- Frontend type/build plus browser workflow at 1280 by 720 with no horizontal
  overflow or console errors.
- Secret scans over requests, responses, audit details, SQLite files, encrypted
  and plaintext-safe bundle surfaces, frontend bundle, logs, screenshots and
  evidence.
- Pinned pnpm and Docker Compose API/web build-runtime smoke.
- P1 target-contract validation, repository lifecycle lint, `git diff --check`,
  evidence hashes and clean candidate state.
- Separate read-only Codex review with critical negative-test reruns and zero
  blocking findings.
- Product-code rollback proof to accepted P1.2 runtime commit and its verified
  pre-`003` database copy.

## Frozen Non-Scope

- No real FineReport/FVS connection, template discovery, official plugin call,
  compatibility certification, FineReport credential/session binding or
  permission-inheritance claim.
- No SecretRecord/SecretVersion, QuerySource, database/Excel expansion, Dora,
  knowledge, LLM, ASR, TTS, screen action, Renderer or AvatarPackage release
  field.
- No production bootstrap/activation, HumanOperatorIdentity ceremony, external
  RecoverySecurityLedger/WORM anchor, OperationalFence, offline disaster quorum,
  full-loss restore, custodian/password-setup grant or cryptographic-root
  recovery.
- No PostgreSQL control-plane implementation or certification, automatic hourly
  scheduler, production backup mount certification or customer RPO/RTO claim.
- No Site mutation, screen retirement/deletion, group deletion, cross-Site move,
  multi-Site delivery promise or high-concurrency SLA.
- No silent fallback from FVS permission denial and no executable script, SQL,
  Python, JavaScript or shell configuration.
- No change to accepted POC route meanings or accepted P1.1/P1.2 identity,
  device-trust, inventory, ownership or audit semantics.

## Immediate Failure Conditions

- A draft, release, publication, rollback, acknowledgement or restore crosses
  tenant, deployment, Site, group, screen, DigitalHumanInstance or device scope.
- A single-screen operation changes any RuntimeBinding, instance, device state,
  ETag or acknowledgement field of a sibling.
- A published release or historical target can be edited, deleted or repointed.
- Applied state changes before the exact credential-bound acknowledgement.
- A stale ETag, generation, fingerprint, approval, content hash, group member
  set or changed idempotency command succeeds.
- Rollback mutates history or silently substitutes an asset, FVS/Secret version
  or configuration value.
- Backup verification can be bypassed, a restore overwrites the active store
  before staging checks pass, or failed restore leaves no usable prior store.
- Restore revives an older browser session, device credential, role assignment
  or pending/approved high-risk action.
- Three-day cleanup deletes a user, release, publication, security generation
  or SecurityAuditEvent.
- A key, password verifier, credential, cookie, CSRF value, token, DSN, Secret
  or authorization header enters an API read, manifest, log, frontend bundle,
  screenshot or tracked evidence.
- Mock/unverified capability is presented as real, certified, production-ready
  or a passed customer RPO/RTO.

## Rollback Target

Product-code rollback target is accepted P1.2 runtime commit
`2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree
`565dbb3567e2a4ae5b872177d97449120477fe8c`, plus a verified exact pre-`003`
database copy. Rollback acceptance must prove the accepted P1.2 login, RBAC,
audit, enrollment, credential rotation/revocation, three-screen inventory,
screen/group isolation and credential-bound runtime inventory behavior still
work and that no P1.3 route is exposed.
