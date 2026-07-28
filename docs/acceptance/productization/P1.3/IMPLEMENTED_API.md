# P1.3 Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Scope: factual local development-preview API; not a production-support claim
- Target source: [../../../product/contracts/CONTROL_PLANE_API.md](../../../product/contracts/CONTROL_PLANE_API.md)

Accepted P1.1 identity/device-trust and P1.2 inventory routes keep their
meanings. P1.3 adds the operations below under `/api/v1/control-plane` and
`/api/v1/device`.

## Draft And Release Routes

| Operation | Method and path | Candidate behavior |
| --- | --- | --- |
| `createConfigDraft` | `POST /config-drafts` | Creates a SCREEN or SCREEN_GROUP envelope for `p1_screen_config_v1` |
| `getConfigDraft` | `GET /config-drafts/{draft_id}` | Scoped draft, revision history, validation, preview and approval evidence |
| `replaceConfigDraftSpec` | `PUT /config-drafts/{draft_id}/spec` | Exact `welcome_text` plus `fvs_binding_ref`; authorizes only the changed leaves and requires `If-Match` |
| `validateConfigDraft` | `POST /config-drafts/{draft_id}:validate` | Persists `VALID` or sanitized `INVALID` evidence; valid input resolves the exact screen/DigitalHumanInstance set and immutable fingerprint |
| `previewConfigDraft` | `POST /config-drafts/{draft_id}:preview` | Built-in Mock only; returns `MOCK_PASSED` |
| `submitConfigDraftApproval` | `POST /config-drafts/{draft_id}:submit-for-approval` | Freezes exact content, fingerprint and control-plane epoch |
| `approveConfigDraft` / `rejectConfigDraft` | `POST /config-drafts/{draft_id}:approve` or `:reject` | Recent reauthentication; approver must differ from editor |
| `reviseConfigDraft` / `abandonConfigDraft` | `POST /config-drafts/{draft_id}:revise` or `:abandon` | Legal state transition with immutable prior revisions |
| `createConfigRelease` | `POST /config-drafts/{draft_id}:release` | Creates one immutable NORMAL release and all exact targets atomically |
| `getConfigRelease` | `GET /config-releases/{release_id}` | Scoped immutable provenance and per-screen target content/hash |
| `diffConfigReleases` | `GET /config-release-diffs?from=...&to=...` | Per-screen field differences without Secret material |

Draft mutations use exact strong ETags and request-bound idempotency. A changed
command cannot replay a result. Stale membership, DigitalHumanInstance,
fingerprint or epoch requires a new revision and new validation/preview/
approval.

The first complete spec requires both business and technical edit permissions.
Afterward, an unchanged leaf requires no permission recheck: changing only
`welcome_text` requires `config.edit_business`, while changing only
`fvs_binding_ref` requires `config.edit_technical`. An unauthorized changed
leaf fails atomically without advancing the draft revision or content. Expected
validation failures return HTTP 200 with `outcome=INVALID`, keep the draft in
`DRAFT` and persist immutable sanitized evidence without fabricating a
resolution fingerprint.

## Publication, Device And Rollback Routes

| Operation | Method and path | Candidate behavior |
| --- | --- | --- |
| `publishToScreen` | `POST /screen-instances/{screen_id}/publications` | Typed two-user approval; exact RuntimeBinding ETag/generation; desired state only |
| `publishToScreenGroup` | `POST /screen-groups/{screen_group_id}/publications` | Exact group ETag and complete per-screen target/ETag/generation set; atomic plan |
| `getPublication` | `GET /publications/{publication_id}` | Scoped target states and failure evidence |
| `getCurrentDeviceRelease` | `GET /api/v1/device/config-releases/current` | Credential-derived screen only; returns exact desired target |
| `acknowledgeDeviceRelease` | `POST /api/v1/device/config-releases/{release_target_id}:ack` | Exact credential screen, generation and content hash; then applied state advances |
| `rollbackScreen` | `POST /screen-instances/{screen_id}/rollbacks` | Creates/publishes a new same-screen immutable ROLLBACK release |
| `rollbackScreenGroup` | `POST /screen-groups/{screen_group_id}/rollbacks` | Exact complete source map; mixed historical releases are explicit per screen |

Publish and rollback use the accepted HighRiskAction flow: the initiator
submits one canonical command, another authorized user approves it, and only
the original initiator can resubmit and atomically consume that exact approval.
Approval cannot execute the effect. Single-screen operations do not change a
sibling. Group preconditions are all checked before any target write.

Device authentication accepts no screen selector. Wrong-screen, revoked or
predecessor credentials fail through the shared credential boundary. Wrong
target, generation or hash and changed acknowledgement replay fail without
advancing applied state.

## Backup And Restore Routes

| Operation | Method and path | Candidate behavior |
| --- | --- | --- |
| `getStorageProfile` | `GET /storage-profile` | Local SQLite/online-source boundary, paths classified without key values |
| `createBackup` | `POST /backups` | Fully validates the SQLite online snapshot before producing logical NDJSON, encryption or a verified record |
| `getBackup` | `GET /backups/{backup_id}` | Plaintext-safe manifest/evidence only |
| `verifyBackup` | `POST /backups/{backup_id}:verify` | Checks AEAD, file hashes, registry, foreign keys, release hashes and bindings |
| `createRestorePlan` | `POST /restore-plans` | Binds one verified backup and current metadata revision |
| `executeRestorePlan` | `POST /restore-plans/{restore_plan_id}:execute` | Typed two-user approval plus `RESTORE_VERIFIED_BACKUP`; stages before atomic replacement |

The development-preview restore mode is `ONLINE_ACTIVE_STORE` only. It retains
the pre-restore database, restores the backed-up runtime bindings, preserves
newer live users/roles/active device security state, revokes unfinished
one-time device material, invalidates browser sessions and replay ciphertext,
and fails unfinished actions. A tampered or wrong-key bundle cannot reach
cutover. Verification, restore planning and restore execution also bind the
authenticated bundle identity, ciphertext hash, manifest hash and recovery
metadata back to the exact immutable `backup_records` row, so another valid
bundle cannot be substituted under a requested backup ID.

Backup capture and restore cutover share the control-plane mutation barrier.
Once restore captures the live security state, later mutations wait until the
cutover decision is complete; a command that was valid before the cutover is
re-evaluated afterward and fails explicitly if its precondition was consumed or
invalidated. The API therefore cannot report success for a concurrent write
that disappears during restore.

## Authorization And Boundary

- Permissions are evaluated from the authenticated principal and server-owned
  tenant/deployment/Site/screen lineage.
- Auditors can read authorized release/audit evidence but every draft,
  publication, rollback, backup and restore mutation is denied.
- `p1_screen_config_v1` contains only `welcome_text` and non-secret
  `fvs_binding_ref`; executable content and Secret-like/DSN material are
  rejected.
- FVS remains `UNVERIFIED`, preview remains `MOCK_PASSED`, and no route calls
  FineReport, FVS or a licensed plugin.
- This API is not production activation, full-loss recovery, PostgreSQL
  recovery or customer RPO/RTO certification.
