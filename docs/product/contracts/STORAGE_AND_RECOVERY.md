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

The complete payload is protected by AEAD AES-256-GCM before finalization. Its encryption/recovery key is held outside the bundle. The encrypted payload contains:

- schema and product versions;
- tenant/deployment identity and control-plane epoch;
- engine-neutral logical records in dependency order;
- embedded online snapshot when applicable;
- immutable release content, asset index and referenced content hashes;
- encrypted Secret ciphertext, password verifiers and key-version metadata inside the whole-bundle AEAD boundary;
- user, role, credential state, revocation history and immutable audit;
- RuntimeBinding desired/applied targets for all screens;
- per-file sizes and SHA-256 values.

The plaintext-safe manifest records only the RecoverySecurityLedger sequence, anchored head hash and key ID needed for anti-rollback validation. The manifest and verification output never contain plaintext Secret values, password verifiers, reset/enrollment tokens, session IDs, device credentials, DSNs or the recovery key.

SQLite backups use its online backup mechanism or an equivalent verified snapshot, never a raw copy that separates the database from an uncheckpointed WAL. The [SQLite Online Backup API](https://www.sqlite.org/backup.html) supports an incremental consistent snapshot while normal access continues.

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
- atomic cutover and service health;
- post-restore session / credential safety actions.

Customer hardware, remote media and external DBA processes may require a separately published RTO. No RTO is marked passed before P1.3 evidence.

## Restore Plan

Restore is never an in-place overwrite:

1. Select one verified backup and record its manifest hash.
2. Create a read-only RestorePlan that checks schema/product compatibility, checksums, ownership references, release hashes, asset availability, Secret key availability, the current independently anchored RecoverySecurityLedger head and expected impact.
3. Require `backup.restore`, recent reauthentication, a reason, explicit confirmation, an idempotency key and a production HighRiskApproval from a different user. The approval binds the backup hash, control-plane epoch and ledger head.
4. Acquire the maintenance lock and advance a pending control-plane epoch.
5. Restore into a new database and asset staging root.
6. Apply only documented forward migrations.
7. Run foreign-key, uniqueness, hash-chain, release-hash and three-screen binding checks.
8. Probe Secret decryption without returning plaintext.
9. Re-read the external anchor immediately before cutover; any head change invalidates the plan and approval.
10. Atomically switch the active storage pointer into `RECONCILING_SECURITY`, not `COMPLETED`.
11. Reconcile user and device security state from the independently anchored ledger, increment control-plane/authentication/device epochs and invalidate every restored AuthSession, bootstrap/reset/enrollment token, pending successor and device session.
12. Commit a post-restore ledger checkpoint and anchor it. Only then may RestorePlan become `COMPLETED`.
13. Verify the three reference screens recover their own desired/applied bindings.

If any check fails, the staged restore is discarded, the previous active store remains unchanged and the safe failure identifies the failing category without leaking data.

## RecoverySecurityLedger And Anti-Rollback Anchor

A backup can predate a user disable, password reset, device rotation or revocation. A journal stored beside that backup can itself be rolled back, so production uses a third trust domain:

- RecoverySecurityLedger is an authenticated append-only HMAC-SHA-256 chain with AEAD-protected records. Its integrity/encryption key is outside the live database, backup root and ledger.
- An independent administrator-controlled monotonic WORM or keystore anchor stores the latest committed sequence and chain head. Restore cannot overwrite, replay or prune either the ledger or anchor.
- Records carry deployment, sequence, event/subject IDs, subject generation, `PREPARED | COMMITTED | ABORTED`, domain commit ID, previous/current hashes, key ID and timestamps; they contain no password, verifier, token or credential value.
- User facts include enabled state, account-state generation, password generation/state, authentication epoch and authorization epoch.
- Device facts include family state, family generation, active credential version, revocation epoch and screen ownership.
- Bootstrap completion is anchored so an old pre-initialization backup cannot recreate bootstrap authority.

Security mutation ordering is fail closed: append and fsync `PREPARED`, commit the database row referencing that sequence, then append `COMMITTED`. On startup or restore, an unresolved `PREPARED` record keeps the affected user denied/`RESET_REQUIRED` or device `REENROLL_REQUIRED` until it is safely committed or aborted.

Restore reconciliation rules are exact:

- a newer ledger `DISABLED` state overrides an older backup `ENABLED`;
- a ledger password generation newer than the backup makes the restored verifier unusable and sets `RESET_REQUIRED`; reset never changes enabled state;
- a ledger-revoked device family remains revoked;
- a different ledger active credential version makes the restored family `REENROLL_REQUIRED`; a predecessor never becomes active again;
- all AuthSessions, one-time tokens, pending device successors and device sessions are invalidated unconditionally;
- a user/device in the backup but missing required ledger coverage fails closed; a ledger tombstone absent from the backup remains authoritative.

Missing, stale, unverifiable or unavailable ledger/anchor state blocks the related security mutation and restore with a safe failure. It never falls back to the backup copy. This design is a target only; P1.3 must prove the real recovery workflow.

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
- Users, password history required for security, role changes, credential revocations, ConfigRelease, Publication, RuntimeBinding history, restore history and SecurityAuditEvent are not removed by that job.
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
- a restored backup reactivates revoked users, sessions or device credentials;
- three-day cleanup removes security, release or audit evidence;
- PostgreSQL or an RPO/RTO is described as supported without real evidence.
