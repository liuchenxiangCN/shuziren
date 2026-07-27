# P1 Target Storage And Recovery Decision

## Document Status

- Lifecycle: `TARGET_NOT_IMPLEMENTED`
- Scope: control-plane stores, migration, backup, restore, retention, RPO and RTO
- Contract version: `p1.0-target-v1`
- Last reviewed: 2026-07-27

These are proposed P1.0 design decisions, not proof that backup or restore is implemented.

## Frozen Target Decisions

| Topic | P1.0 target |
| --- | --- |
| Default embedded control-plane engine | bundled and release-pinned SQLite 3, minimum implementation baseline 3.45 |
| Embedded topology | one active control-plane instance, database on local persistent block storage |
| External control-plane store | PostgreSQL 16 on the current supported minor release |
| MySQL / Oracle role | QuerySource engines only; not control-plane stores in V1 |
| Default backup backend | encrypted, hashed filesystem bundle on a mounted path separate from the live data root |
| Default schedule | hourly; plus mandatory verified checkpoints before upgrade, migration and restore |
| Default retention | 24 hourly, 7 daily and 4 weekly verified backups |
| Embedded-store RPO target | at most 1 hour for standard production configuration |
| Reference single-site RTO target | at most 2 hours from restore authorization to verified service |
| Runtime detail retention | 3 days by default and configurable |
| Security / release retention | not subject to the three-day cleanup |

RPO and RTO remain unverified targets until P1.3 measures a reference restore. P1.0 can validate only that the design is complete and internally consistent.

## Embedded SQLite Profile

The embedded profile is for a private, single-site control plane with low-to-moderate write volume:

- exact SQLite library version is pinned in the product SBOM;
- `journal_mode=WAL`;
- `synchronous=FULL`;
- `foreign_keys=ON` on every connection;
- a bounded busy timeout and short transactions;
- one service-owned write coordinator; background jobs do not hold long read transactions;
- explicit WAL checkpoints and growth monitoring;
- database and WAL files on the same local persistent filesystem;
- no active SQLite database on SMB, NFS or another network filesystem.

SQLite documents that WAL allows readers and a writer to proceed concurrently but requires the same host and shared-memory support; the [SQLite WAL documentation](https://www.sqlite.org/wal.html) is the governing engine constraint. `synchronous=FULL` is selected for power-loss durability rather than the lower-durability NORMAL mode described in the [SQLite pragma documentation](https://sqlite.org/pragma.html).

SQLite serializes writes. The profile is a correctness baseline, not a high-concurrency claim. Capacity evidence or multiple active control-plane instances require the external store.

## External PostgreSQL Profile

V1 supports one external control-plane family:

- PostgreSQL major version 16, always on its latest supported minor release;
- TLS where traffic leaves the application host;
- separate owner/migration and least-privilege runtime database roles;
- connection pool, transaction timeout and statement timeout owned by the control plane;
- exact driver and minor-version combinations certified in P5;
- customer DBA native backup and HA policy remain operational responsibilities;
- product logical export, manifest and restore preflight remain mandatory.

The PostgreSQL project supports a major release for five years and recommends the current minor release; see its [versioning policy](https://www.postgresql.org/support/versioning/). PostgreSQL support here is a target contract and remains unverified until migration and restore evidence exists.

## Storage Layout

Logical categories are separated even if the embedded profile uses one host:

| Category | Content | Rule |
| --- | --- | --- |
| Control-plane database | relational state and encrypted Secret records | never on the backup output path |
| Asset store | immutable content-addressed assets and hashes | P1 records indexes; later asset batches own formats |
| Backup root | verified recovery bundles | production path must be a distinct mounted filesystem or managed NAS |
| Recovery key | key-encryption / recovery material | held outside database and backup bundle |
| RecoverySecurityLedger | authenticated append-only anti-rollback events | separate from live data, backup root and active pointer; restore never overwrites or replays it |
| Ledger anchor | latest monotonic sequence and chain head | independent administrator-controlled WORM or keystore; separate from ledger, live data and backups |
| Raw runtime logs | short-lived operational detail | excluded or sanitized according to retention policy |

The production installer requires an explicit writable `backup_root` and rejects the live data root, application package tree and database directory. A same-disk development path may be used only with a visible non-production warning and cannot pass production recovery acceptance.

## Backup Bundle

Each backup is written to a temporary directory, verified and atomically renamed only after completion:

```text
backup-<id>/
├─ manifest.json
├─ control-plane.logical.ndjson.zst
├─ embedded-native.snapshot            # embedded profile only
├─ assets/
├─ secrets.enc
├─ checksums.sha256
└─ verification.json
```

The complete payload is protected by AEAD AES-256-GCM before finalization. Its encryption/recovery key is held outside the bundle; envelope metadata stores a nonce unique for that key, authentication tag, `recovery_encryption_key_id` and canonical AAD schema binding deployment, manifest hash, schema/product versions and bundle generation. The encrypted payload contains:

- schema and product versions;
- tenant/deployment identity and control-plane epoch;
- engine-neutral logical records in dependency order;
- embedded online snapshot when applicable;
- immutable release content, asset index and referenced content hashes;
- encrypted Secret ciphertext, password verifiers and key-version metadata inside the whole-bundle AEAD boundary;
- user, role, credential state, revocation history and immutable audit;
- RuntimeBinding desired/applied targets for all screens;
- per-file sizes and SHA-256 values.

The plaintext-safe manifest records only the RecoverySecurityLedger sequence/anchored head plus separate `recovery_encryption_key_id`, `ledger_chain_hmac_key_id` and `ledger_record_aead_key_id` needed for recovery and anti-rollback validation. The manifest and verification output never contain plaintext Secret values, password verifiers, reset/enrollment tokens, session IDs, device credentials, DSNs or the recovery key.

SQLite backups use its online backup mechanism or an equivalent verified snapshot, never a raw copy that separates the database from an uncheckpointed WAL. The [SQLite Online Backup API](https://www.sqlite.org/backup.html) supports an incremental consistent snapshot while normal access continues.

## Key Management Policy

The eighteen fixed, mutually isolated domains are `HIGH_RISK_REQUEST_HMAC`, `SENSITIVE_REQUEST_DIGEST_HMAC`, `RESTORE_CONTINUITY_ENVELOPE_HMAC`, `RECOVERY_LEDGER_CHAIN_HMAC`, `RECOVERY_LEDGER_RECORD_AEAD`, `AUTH_SESSION_VERIFIER_PEPPER`, `CSRF_TOKEN_VERIFIER_PEPPER`, `ONE_TIME_TOKEN_VERIFIER_PEPPER`, `ONE_TIME_RESPONSE_ENCRYPTION`, `DEVICE_CREDENTIAL_VERIFIER_PEPPER`, `SECRET_ENVELOPE_ENCRYPTION`, `BACKUP_RECOVERY_ENCRYPTION`, `OFFLINE_RECOVERY_AUTHENTICATION`, `HUMAN_OPERATOR_ATTESTATION_SIGNATURE`, `DISASTER_ENVELOPE_NONCE_HMAC`, `OPERATIONAL_FENCE_HMAC`, `PRODUCTION_READINESS_NONCE_HMAC` and `EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC`. Cross-purpose reuse is forbidden; backup recovery, offline authorization and human attestation are always distinct.

Key metadata stores `key_id`, purpose domain, version, `ACTIVE | VERIFY_ONLY | RETIRED | REVOKED`, lifecycle times and monotonic registry generation; material is outside live storage, logs, backups and evidence. The authoritative registry is the external keystore/monotonic anchor, rotation/revocation are ledger-backed, and restore uses current external state without widening it from a backup copy. Symmetric service domains have at most one active key. Each custodian has at most one active key for each signature purpose; production readiness requires at least three active offline-recovery custodians and three separately keyed active human-attestation custodians.

Every keyed verifier is HMAC-SHA-256 with a purpose-bound key of at least 256 bits and stores `key_id`. Every AEAD record uses AES-256-GCM with nonce uniqueness per key and stores nonce, authentication tag, key ID and canonical AAD schema. Immutable protected records are never rewritten merely for rotation: request/envelope HMACs and verifiers retain their bound verification key; ledger-chain rotation appends a rotation record; ledger-record AEAD appends wrapped-DEK metadata or retains the decrypt key; one-time response encryption lives no longer than five minutes; Secret envelopes create successors or rewrap a DEK without changing business-content hash; backup keys are per bundle; offline keys rotate per custodian.

Temporary KMS/keystore unavailability returns `503 KEY_SERVICE_UNAVAILABLE` or a purpose-specific 503 and leaves credential/action/key state unchanged. Only confirmed revocation or permanent loss triggers irreversible invalidation. Loss of verifier keys invalidates affected artifacts; durable ledger-key loss blocks mutation/restore; request-HMAC compromise fails pending actions; Secret compromise requires rotation; backup-key loss leaves its bundle unrecoverable until authorized recovery; and an offline-key compromise disables that custodian and requires a fresh quorum.

## Production Activation Readiness

Bootstrap completes in deployment mode `SETUP` and may temporarily leave one credential-usable platform administrator. `activateDeploymentProduction` requires `deployment.manage`, `production_four_eyes_v1` and the complete frozen machine-readiness checklist: two credential-usable deployment administrators backed by two distinct active attested persons; all required active keys across the eighteen purpose domains; a writable separate production backup mount and backup-recovery key; current cryptographically verified ledger, key and person-registry generations; healthy RecoverySecurityLedger and anchor; at least three active offline-recovery custodians and three separately keyed human-attestation custodians with successful Ed25519 preflights; read/write compare-and-swap preflights for the disaster, production-readiness and emergency-reduction nonce registries and OperationalFence anchor; trusted monotonic time and anchor-native cryptographic-root recovery preflights; and the RestoreContinuityEnvelope key. The ledger-backed one-way transition `SETUP -> PRODUCTION_ACTIVE` commits the readiness snapshot and initial authenticated `READY` fence generation. Ordinary network/product mutations may not reduce either the two-user or two-distinct-attested-person administrator floor; only the local fenced emergency reduction below may cross it without restoring service.

## Operational Fence And Local Recovery

ExternalOperationalFenceRecord is the authoritative production-serving posture. It is an append-only, monotonically generated compare-and-swap chain in the external anchor and is authenticated with HMAC-SHA-256 under `OPERATIONAL_FENCE_HMAC`. Its three evidence branches are `RECOVERY_REQUIRED`, `READY_INITIAL_ACTIVATION` and `READY_RECOVERY_SUCCESSOR`. HMAC possession alone never authorizes `READY`: the external anchor also verifies the branch's activation or offline-recovery authorization, ledger, terminal nonce, readiness, external-audit and finalized-result evidence. Startup uses the highest verified generation. Clearing a fence never edits or deletes an earlier record; it appends a new authenticated `READY_RECOVERY_SUCCESSOR` only after local offline authorization, complete readiness and the matching committed ledger/anchor evidence.

Temporary unavailability of a required registry, anchor, key or dependency creates only an ephemeral fail-closed gate, returns retryable `503`, preserves the persisted posture and domain state, and clears automatically when the dependency recovers. Confirmed loss, revocation, invalid evidence or a persistent readiness breach appends a `RECOVERY_REQUIRED` successor. The database and ledger reconcile that evidence when available, but neither can override the external fence.

The following operations are `LOCAL_MAINTENANCE_ONLY_NO_NETWORK_API`:

- `recoverProductionReadiness` verifies a fresh ProductionReadinessRecoveryAuthorization and production-readiness nonce. `READINESS_ONLY` performs the exact signed remediation and changes no user, person, role or credential. `ADMIN_REPLACEMENT` is allowed only with exactly one usable active attested administrator; it may create, bind, enable, credential and grant the exact one new replacement administrator, using two distinct offline-recovery signatures, two distinct separately keyed human-attestation signatures, and one target-only RecoveryPasswordSetupGrant. Zero current active attested administrators requires explicit new-deployment reinitialization. The operation commits `deployment_production_readiness_recovery`, appends an ordered SHA-256 ExternalProductionReadinessRecoveryAudit record to external WORM storage and then a SecurityAuditEvent, rechecks complete readiness, and finally appends the authenticated `READY` successor bound to that audit hash and finalized result.
- `emergencyReduceAuthority` verifies an EmergencyAuthorityReductionAuthorization and may only revoke a key, person attestation/user binding, device family or Secret/FineReport credential version, or disable a user. It appends and anchors the ExternalAuthorityRevocationTombstone before the target revocation, then commits `emergency_authority_reduction_reconciliation` and a SecurityAuditEvent. It may cross the ordinary two-administrator floor for safety, but never increases authority and always leaves the deployment `RECOVERY_REQUIRED`.
- `recoverCryptographicReadinessRoot` verifies a CryptographicRootRecoveryAuthorization and may install exactly one replacement root for `PRODUCTION_READINESS_NONCE_HMAC`, `EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC`, `DISASTER_ENVELOPE_NONCE_HMAC` or `OPERATIONAL_FENCE_HMAC`. Its root nonce is SHA-256-protected, anchor-native WORM compare-and-swap with no service-HMAC dependency. The replacement key-registry generation, ordered SHA-256 ExternalCryptographicRootRecoveryAudit and new `RECOVERY_REQUIRED` checkpoint commit in the same WORM generation, followed by `cryptographic_readiness_root_recovery_reconciliation` when the ledger is available. It cannot write `READY` or change users, roles, credentials or business state; a separate fresh `recoverProductionReadiness` remains mandatory.

Each local SecurityAuditEvent is appended only after the matching typed authorization, terminal nonce, external audit/tombstone and ledger anchor are authenticated. Its local extension records authorization kind/ID/hash, terminal nonce ID/hash, external evidence kind/ID/hash, sanitized custodian evidence and committed ledger sequence/head; DirectOperationAuthorization, HighRiskAction and disaster-envelope IDs remain null. Readiness, emergency reduction and cryptographic-root recovery use distinct authorization/nonce/external-evidence mappings and cannot substitute one another.

## Schedule And Recovery Objectives

### Schedule

- Hourly logical backup and integrity verification.
- Retain 24 hourly, 7 daily and 4 weekly verified generations.
- Create an additional verified checkpoint before upgrade, schema migration or restore execution.
- A platform administrator or operations engineer may request an on-demand backup.
- Failed verification does not replace the latest verified generation and raises an operational alert.

High-risk configuration changes remain recoverable through immutable ConfigRelease and audit history; backup is not a substitute for application rollback.

### RPO

The embedded standard-production target is `RPO <= 1 hour` for control-plane state when the required separate backup mount is healthy. Losing both live storage and a co-located development backup is outside that target.

### RTO

The reference single-site target is `RTO <= 2 hours`, measured from authorized restore execution through:

- bundle and recovery-key availability;
- integrity and compatibility validation;
- restore into a new location;
- migration when required;
- Secret decrypt probe without exposing values;
- three-screen binding and release verification;
- recoverable cutover and service health;
- post-restore session / credential safety actions.

Customer hardware, remote media and external DBA processes may require a separately published RTO. No RTO is marked passed before P1.3 evidence.

## Restore Plan

Restore is never an in-place overwrite:

1. Select one verified backup and record its manifest hash.
2. Create a read-only RestorePlan that checks schema/product compatibility, checksums, ownership references, release hashes, asset availability, Secret key availability, the current independently anchored RecoverySecurityLedger head and expected impact; freeze exactly one recovery-source mode and completion mode.
3. Choose exactly one `authorization_mode` and bind its exact evidence. `NORMAL_API_FOUR_EYES` requires `ONLINE_ACTIVE_STORE`, HighRiskAction and HighRiskApproval. `LOCAL_DISASTER_QUORUM` requires DisasterRecoveryAuthorizationEnvelope and may use either source; its online-source branch is legal only when the authoritative active store proves no credential-usable deployment administrator can authenticate, while active-store unavailability requires full loss. RestorePlan, RestoreContinuityEnvelope and RestoreCutoverRecord apply identical branch nullability: normal requires action+approval and null disaster fields; local requires envelope+entry-condition evidence and null action+approval fields. Replacement attestation/binding fields are present only for `LOCAL_DISASTER_REPLACE_ONE`.
4. In online mode, acquire the maintenance lock, drain writes and stop externally serving control-plane/device traffic. In full loss there is no active store or retained pointer to lock; local maintenance keeps the staged store unserved. Safe pre-pointer abort may restore the prior online service. A completed `SETUP` restore remains non-serving, while a completed `PRODUCTION_ACTIVE` restore remains fenced `RECOVERY_REQUIRED` until the separate local `recoverProductionReadiness` protocol succeeds.
5. Restore into a new database and asset staging root.
6. Apply only documented forward migrations.
7. Run foreign-key, uniqueness, hash-chain, release-hash and three-screen binding checks.
8. Probe Secret decryption without returning plaintext.
9. Re-read the external anchor before security reconciliation; any head change invalidates the plan and approval.
10. Move the plan to `RECONCILING_SECURITY` while the restored store remains staged. Reconcile identity, role/scope, device, Secret and FineReport state from the current external ledger/registry; replace roles rather than merge, advance epochs, invalidate all restored AuthSessions, bootstrap/reset/enrollment tokens, pending successors and device sessions, and delete every one-time response replay ciphertext.
11. Prove deployment-mode admin readiness against staged state: `SETUP` requires one selected existing attested administrator; `PRODUCTION_ACTIVE` requires two selected administrators backed by distinct current attested persons. Normal online restore uses existing selected administrators and issues one or two provisional grants only for the exact stale or missing selected credentials. Local disaster issues one grant in `SETUP` and two in production; if exactly one current production administrator survives, `LOCAL_DISASTER_REPLACE_ONE` selects that person plus one exact dual-purpose-signed replacement. Zero surviving current active attested administrators requires reinitialization.
12. Build both evidence dimensions independently. `ONLINE_ACTIVE_STORE` flushes the old live chain, captures `barrier_live_audit_head_hash`, activates the barrier and carries the complete canonical sanitized SecurityAuditSuffix from backup head exclusive through barrier head inclusive plus the retained previous pointer. `FULL_LOSS_ACTIVE_STORE_UNAVAILABLE` has no live barrier or retained pointer and carries the exact empty backup-head-to-backup-head SecurityAuditSuffix. Separately, every `LOCAL_DISASTER_QUORUM` restore, whether online-source or full-loss, carries its signed ExternalRecoveryAudit; `NORMAL_API_FOUR_EYES` carries its HighRiskAction/HighRiskApproval and any optional provisional-grant evidence.
13. Compute the continuity payload/hash; append/fsync the cutover `PREPARED` record; authenticate RestoreContinuityEnvelope using HMAC-SHA-256 under `RESTORE_CONTINUITY_ENVELOPE_HMAC`; then insert and verify carried rows in one staged transaction. The envelope and RestoreCutoverRecord bind `recovery_source_mode`, `authorization_mode` and branch evidence, admin-readiness branch, prepared sequence/head, ledger-chain/envelope key IDs, payload hash, nullable previous store, staged store, nonce and expiry. Cutover ID+nonce is single use.
14. Re-read the unchanged anchor and all applicable source evidence, then verify the three complete RuntimeBindings, all cutover preconditions and every mode-required staged administrator proof. Online mode also proves the barrier-live head remains unchanged; full loss does not fabricate that check. Any mismatch aborts before pointer replacement.
15. Commit staged state with the ledger sequence and `CUTOVER_PREPARED`, then replace the active-pointer artifact. Online mode retains the previous pointer until committed anchor; full loss starts with null previous pointer. Reconciliation infers `POINTER_SWITCHED_PENDING_ANCHOR` from actual pointer plus authenticated evidence, appends ledger `COMMITTED`, advances the external anchor and enters `ANCHOR_COMMITTED_PENDING_FINALIZATION`. Standard provisional grants commit with the restore ledger anchor; disaster grants require both that anchor and the terminally committed disaster-nonce anchor.
16. From the committed anchor, one idempotent transaction finalizes RestorePlan, AsyncOperation, OutboxRecord, IdempotencyRecord, RestoreCutoverRecord and SecurityAuditEvent. Replay returns the stored result without redispatch. Every `PRODUCTION_ACTIVE` restore finalization sets or keeps the authoritative OperationalFence at `RECOVERY_REQUIRED` bound to that finalized result; restore never writes its `READY` successor. External serving resumes only after a separate fresh `recoverProductionReadiness` authorization, nonce, complete-readiness proof, external audit and matching authenticated `READY_RECOVERY_SUCCESSOR`. A `SETUP` restore remains `SETUP` and externally unserved until later production activation.

If an online pre-pointer check fails, the staged restore is discarded and the previous store remains active. If a full-loss pre-pointer check fails, preparation is aborted and the staged store remains `UNSERVED`; no previous-store claim is made. After pointer replacement, recovery follows the fenced protocol; after anchor commitment it finalizes forward.

### Restore Authorization And Password Setup Grants

DisasterRecoveryAuthorizationEnvelope and standard HighRiskAction are XOR. Disaster authorization binds exact entry condition plus externally verifiable evidence. `ACTIVE_STORE_UNAVAILABLE` requires full-loss/local mode; `NO_CREDENTIAL_USABLE_ENABLED_DEPLOYMENT_PLATFORM_ADMIN` permits local authorization against an online source. It is local-maintenance-only, exposes no network API and replaces only the standard different-user approval for exact `executeRestorePlan`. It requires two distinct signatures among at least three active registered custodians, expires after 30 minutes and binds one nonce. Public keys/revocation and registry generation are in the external anchor; private keys stay offline.

The envelope binds entry condition/evidence, deployment mode and operational posture, recovery-source mode, deployment ID, backup-manifest hash, ledger head, staged-store ID, exact completion mode, exact missing-credential subject set, admin-readiness branch, selected admin user/person tuples and generations, person/custodian registries, nonce and expiry. Its commands are limited to exact-backup validation, exact-restore authorization and issuance of the mode-required grants. `SETUP` selects one existing attested administrator. Production normally selects exactly two existing administrators with distinct active attested persons; when exactly one current active attested administrator survives, `LOCAL_DISASTER_REPLACE_ONE` may select that person and one exact new replacement only with two offline-recovery plus two separate human-attestation signatures. Zero survivors requires explicit reinitialization.

RecoveryPasswordSetupGrant has exactly three authorization kinds with exactly one matching reference: `STANDARD_HIGH_RISK`, `DISASTER_CUSTODIAN` and `PRODUCTION_READINESS_CUSTODIAN`. Normal restore issues exactly the number needed for stale or missing selected-admin credentials, minimum one and maximum two. Disaster restore issues one in `SETUP` and two in any production posture. Production-readiness `ADMIN_REPLACEMENT` issues exactly one. Each grant contains at least 256 random bits and persists only a keyed digest/key ID plus its authorization, target person/user and generation, credential stage, prepared sequence, nonce and expiry bindings. Plaintext is target-local once with `no-store` and never enters continuity, ledger, audit, backup or logs.

The state machine is `ISSUED -> PROVISIONALLY_CONSUMED -> COMMITTED_CONSUMED`; terminal alternatives are `EXPIRED` and `ABORTED_REVOKED`. Provisional consumption creates the staged verifier and target-person authentication proof against the same authority `PREPARED` sequence. `STANDARD_HIGH_RISK` commits with the restore-cutover ledger anchor; `DISASTER_CUSTODIAN` requires the restore ledger and disaster-nonce anchors; `PRODUCTION_READINESS_CUSTODIAN` requires the production-readiness ledger, nonce and authenticated `READY` fence-successor anchors. Any required grant expiry, revocation or authentication failure atomically aborts the complete set, destroys every provisional verifier and terminally consumes the applicable nonce. Ordinary grants never create, enable or widen authority; only the exact signed `LOCAL_DISASTER_REPLACE_ONE` and readiness `ADMIN_REPLACEMENT` branches may create, bind, enable, credential and grant their single named replacement while all other authority increase remains forbidden.

## RecoverySecurityLedger And Anti-Rollback Anchor

A backup can predate a user disable, password reset, device rotation or revocation. A journal stored beside that backup can itself be rolled back, so production uses a third trust domain:

- RecoverySecurityLedger is an authenticated append-only HMAC-SHA-256 chain with AEAD-protected records. Its integrity/encryption key is outside the live database, backup root and ledger.
- An independent administrator-controlled monotonic WORM or keystore anchor stores the latest committed sequence and chain head. Restore cannot overwrite, replay or prune either the ledger or anchor.
- Records carry deployment, sequence, event/subject IDs, subject owner/scope, subject generation, `PREPARED | COMMITTED | ABORTED`, domain commit ID, previous/current hashes, distinct `chain_hmac_key_id` and `record_aead_key_id`, AEAD nonce/tag/AAD schema and timestamps; they contain no password, verifier, token or credential value.
- User facts include enabled state, account-state generation, password generation/state, authentication/authorization epochs, an encrypted canonical role/resource-scope assignment snapshot plus generation and hash, and a separate `user_identity_snapshot`. The identity snapshot schema is exactly `user_id`, `tenant_id`, `deployment_id`, `normalized_username`, `display_name`, `enabled`, `account_state_generation`, `authentication_epoch`, `authorization_epoch` and `credential_material_excluded`; the last field is true, and the snapshot never contains a password verifier or any credential material. The role/scope snapshot includes user ID, role-catalog version and a sorted set of `(role_id, scope_type, scope_id)`.
- Device facts include family state, family generation, active credential version, revocation epoch and screen ownership.
- SecretRecord facts include owner scope, state, security generation, authoritative current version, revocation epoch/tombstone and each version's `ACTIVE | RETIRING | REVOKED` authorization state. FineReportIdentityBinding facts include the analogous screen-owned binding state. A retiring entry stores both the canonical lexicographically sorted exact pre-rotation applied-target ID set and its hash inside the AEAD-protected ledger record, plus a deadline no later than 24 hours. These are identifiers and state only, never credential values.
- Bootstrap completion, deployment mode/readiness and the monotonic key-registry generation/state hash are anchored so an old backup cannot recreate bootstrap authority, undo production activation or widen key state.

Security mutation ordering is fail closed for bootstrap completion, deployment production activation, user create/identity/enabled/password/role changes, DeviceCredentialFamily creation/rotation/revocation, Secret create/rotation, FineReport binding create/replacement and key-registry rotation/revocation: `append/fsync PREPARED`, commit the domain row referencing that sequence, then append `COMMITTED` and advance the external anchor. The closed ledger mutation catalog also includes exact entries `deployment_production_readiness_recovery`, `emergency_authority_reduction_reconciliation`, `cryptographic_readiness_root_recovery_reconciliation` and `human_operator_identity_or_user_binding_or_eligibility_change`; no untyped local recovery mutation may bypass their authorization and external evidence. On startup or restore, an unresolved `PREPARED` record keeps the affected subject denied until safely reconciled.

Restore reconciliation rules are exact:

- a newer ledger `DISABLED` state overrides an older backup `ENABLED`;
- a ledger user absent from the backup is reconstructed in staged state only from the exact `user_identity_snapshot`, without credential material, and is set to `RESET_REQUIRED`; an identity conflict fails restore, leaving the online previous store active or full-loss staged state unserved;
- a ledger password generation newer than the backup makes the restored verifier unusable and sets `RESET_REQUIRED`; reset never changes enabled state;
- the latest role/scope snapshot replaces the restored `user_role` set rather than merging with it; any restored assignment absent from the snapshot is removed. Unknown roles/scopes/catalog versions or a missing/mismatched snapshot set `ROLE_RECONCILIATION_REQUIRED` and grant zero permissions;
- a ledger-revoked device family remains revoked;
- a different ledger active credential version makes the restored family `REENROLL_REQUIRED`; a predecessor never becomes active again;
- a SecretRecord generation/current-version mismatch never promotes restored ciphertext or widens its allowed target set. A ledger `REVOKED` version remains unusable; `RETIRING` remains limited to its AEAD-protected canonical sorted exact-target set and matching hash until the deadline. A missing set, noncanonical/duplicate member, or hash mismatch makes the predecessor deny all and sets `SECRET_ROTATION_REQUIRED`. If the authoritative active version is missing, the same state blocks new release creation, publication, rollback, new runtime delivery and decryption outside valid frozen retiring targets;
- a FineReport binding generation/current-version mismatch follows the same no-widening rule. A missing/invalid canonical retiring target set or hash denies all and sets `FINEREPORT_REBIND_REQUIRED`; the same state applies when authoritative active material is missing;
- all AuthSessions, one-time tokens, pending device successors and device sessions are invalidated unconditionally;
- every restored one-time Secret response replay ciphertext is deleted unconditionally;
- all restored `PENDING` or `APPROVED` HighRiskActions become `FAILED_RESTORE_EPOCH_CHANGED`, and all restored config approvals require validation, preview and approval in the new control-plane epoch; historical evidence remains readable;
- a user, device family, SecretRecord or FineReport binding in the backup but missing required ledger coverage fails closed; a ledger tombstone absent from the backup remains authoritative.

Missing, stale, unverifiable or unavailable ledger/anchor state blocks the related security mutation and restore with a safe failure. It never falls back to the backup copy. This design is a target only; P1.3 must prove the real recovery workflow.

Authoritative current Secret or FineReport material missing from staged state refuses pointer replacement by default. `DEGRADED_CREDENTIAL_RECOVERY` is the only exception and binds the exact missing-subject set plus `RESTORE_DEGRADED_CREDENTIALS` in the selected XOR authorization branch: normal/online uses HighRiskAction plus different-user HighRiskApproval; local disaster uses the signed envelope and its entry-condition evidence, never a fabricated approval. Affected subjects remain fail closed and the result is `COMPLETED_DEGRADED`.

The RestorePlan and XOR authorization evidence are created after backup selection. RestoreContinuityEnvelope binds recovery-source mode, `authorization_mode`, the exact branch evidence/hash and nullability, admin-readiness branch, ledger preparation, key IDs, payload, nullable previous pointer, staged pointer, nonce and expiry, and authenticates the exact payload with `RESTORE_CONTINUITY_ENVELOPE_HMAC`. Common carried rows bind the same tuple. `NORMAL_API_FOUR_EYES` carries HighRiskAction, HighRiskApproval and optional RecoveryPasswordSetupGrant provisional evidence. `LOCAL_DISASTER_QUORUM` always carries DisasterRecoveryAuthorizationEnvelope, provisionally consumed grant evidence and ExternalRecoveryAudit, independently of whether its source is online or full loss.

ExternalRecoveryAudit is an ordered SHA-256 hash chain. Its canonical record contains `sequence`, `previous_record_hash`, `authorization_envelope_hash`, `disaster_entry_condition`, custodian registry generation, sorted distinct custodian IDs and signature-key IDs, signature tuples sorted by custodian ID, sorted distinct selected admin user/person tuples, command, result and creation time. The first `previous_record_hash` is the backup-manifest audit head. Every record carries and verifies the same valid two-of-three distinct-custodian Ed25519 evidence under exact `OFFLINE_RECOVERY_AUTHENTICATION`; signatures are excluded only from the signed payload, not the carried record. The first staged SecurityAuditEvent binds both the backup head and terminal external-audit hash.

SecurityAuditSuffix is source-specific. Online source carries the complete live suffix and retained previous pointer. Full loss carries a null previous pointer and a canonical empty suffix whose backup and barrier heads both equal the backup-manifest audit head, `event_count` is zero, ordered events are empty, `first_event_previous_hash` is null, `last_event_hash` is that backup head, and no live barrier exists. Missing or mismatched authorization, audit or source evidence keeps the online previous store active or full-loss staged state unserved.

RestoreCutoverRecord binds recovery-source mode and makes each boundary explicit: `CUTOVER_PREPARED -> POINTER_SWITCHED_PENDING_ANCHOR -> ANCHOR_COMMITTED_PENDING_FINALIZATION -> FINALIZED`, with pre-anchor `REVERTED`. Online retains the previous pointer until committed anchor and may restore it on a provably abortable pre-anchor failure. Full loss has null previous pointer; if a post-pointer/pre-anchor reconciliation cannot prove the exact ledger commit, it restores the null pointer and keeps staged state unserved rather than claiming rollback to a missing store. Once the anchor is committed, startup finalizes forward from authenticated evidence. `FINALIZED` is only the restore transaction's terminal state: `SETUP` remains non-serving, and every production restore writes or retains a finalized-result-bound `RECOVERY_REQUIRED` fence until a separate fresh `recoverProductionReadiness` completes its external audit and appends the matching authenticated `READY` fence successor.

## Migration

- Logical schema version starts at `p1_control_plane_001`.
- Migrations are ordered, forward-only and checksummed.
- Production startup reports a pending migration and remains read-only until the explicit upgrade workflow runs.
- Preflight checks free space, current schema, product compatibility, backup health and recovery key.
- Migration runs on a copy or in an engine transaction where fully supported.
- Post-migration validation covers foreign keys, uniqueness, audit chain, release hashes and three-screen bindings.
- Failed validation preserves the last accepted product and store.
- Moving SQLite to PostgreSQL uses the engine-neutral logical bundle and the same validation; it is not a file copy.

## Retention

- Conversation detail and verbose runtime logs default to three days and are configurable by type.
- One-time Secret response replay ciphertext expires and is destroyed within five minutes and is deleted unconditionally during restore.
- Users, password history required for security, role/scope snapshots and changes, device/Secret/FineReport security generations and tombstones, ConfigRelease, Publication, RuntimeBinding history, restore history and SecurityAuditEvent are not removed by that job.
- Backup pruning deletes only a verified generation outside retention after confirming at least one newer verified generation and one weekly recovery point remain.
- Every cleanup and prune produces an audit event with counts and hashes, never raw sensitive content.

## Failure Conditions

P1 implementation cannot pass if:

- SQLite live data is placed on network storage;
- an unverified backup replaces the latest verified recovery point;
- the recovery key is stored in the same bundle;
- a restore overwrites the active database before verification;
- the anti-rollback ledger or its latest external anchor shares the live/backup failure domain, is missing, stale or unverifiable;
- an old password verifier or predecessor device credential authenticates after restore;
- production activates without two distinct attested-person administrators and the complete machine-readiness gate, an ordinary network/product mutation crosses either two-administrator floor, or emergency reduction increases authority or claims `READY`;
- AEAD nonce reuse occurs under one key, a protected record lacks its purpose-bound key ID/AAD, or restore trusts a backup key registry over the external monotonic registry;
- OperationalFence is cleared by mutation/deletion, HMAC alone, stale generation, missing branch evidence, or any path other than an authenticated append-only successor at the external monotonic anchor;
- pointer switch violates its deployment/admin-readiness branch: `SETUP` requires one selected attested administrator, production requires two distinct attested persons, and the exact signed replace-one branch is the only permitted replacement;
- any RecoveryPasswordSetupGrant set reaches `COMMITTED_CONSUMED` before its authorization-kind-specific anchors, or abort/expiry/authentication failure omits atomic whole-set verifier destruction and terminal consumption of the applicable nonce;
- full loss is required to fabricate a live barrier/retained pointer, or failure serves staged state instead of keeping it `UNSERVED`;
- a local disaster restore omits its ordered ExternalRecoveryAudit, a full-loss SecurityAuditSuffix is non-empty or does not bind backup head to itself, or the first staged audit event omits the terminal external-audit hash;
- a local production-readiness, emergency-reduction or cryptographic-root recovery operation is network exposed, bypasses its external authorization/audit/ledger evidence, or root recovery writes `READY`;
- restored one-time response replay ciphertext survives reconciliation;
- a restored backup reactivates revoked users, removed role/scope assignments, sessions, device credentials, predecessor Secret versions or predecessor FineReport identities;
- a restore silently switches with missing authoritative Secret/FineReport material, reconstructs a verifier, tolerates a user identity conflict, or labels explicit degraded recovery as `COMPLETED`;
- a retiring target set/hash is missing or invalid but predecessor use is not denied, any `SETUP` restore serves traffic, or any production restore serves before a separate matching complete-readiness `READY` fence successor;
- three-day cleanup removes security, release or audit evidence;
- PostgreSQL or an RPO/RTO is described as supported without real evidence.
