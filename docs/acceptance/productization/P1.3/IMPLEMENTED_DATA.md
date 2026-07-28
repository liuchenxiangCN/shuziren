# P1.3 Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Logical schema: `p1_control_plane_001`
- Latest migration: `003_publish_rollback_recovery`
- Migration checksum SHA-256: `4dd3fbb74e71d669e7ee0a7c22ecb2edfbca278609eba1724dc01163dc1bfe31`
- Scope: factual local SQLite subset; not the complete P1 production target
- Target source: [../../../product/contracts/DATA_MODEL.md](../../../product/contracts/DATA_MODEL.md)

P1.3 preserves the accepted `001_initial_identity_device_trust` and
`002_three_screen_inventory` rows and checksums. Startup accepts only the exact
ordered registry. Missing, reordered, unknown or checksum-tampered migration
state fails closed.

## Added Or Rebuilt Structures

| Table | Candidate purpose |
| --- | --- |
| `config_drafts` | Target envelope, state, mutable head revision and resource revision |
| `config_draft_revisions` | Immutable canonical spec revisions and content hashes |
| `resolution_fingerprints` | Immutable resolved target/DigitalHumanInstance set and hashes |
| `validation_records` | Immutable `VALID` or sanitized `INVALID` schema/ownership validation evidence |
| `preview_records` | Immutable `MOCK_PASSED` preview evidence |
| `config_approval_records` | Exact different-user approve/reject evidence |
| `config_releases` | Immutable NORMAL or ROLLBACK provenance and release sequence |
| `release_targets` | Immutable per-screen canonical effective content and content hash |
| `runtime_bindings` | Rebuilt P1.2 binding with desired/applied targets, generation and acknowledgement |
| `publications` / `publication_targets` | Frozen plan plus independently observable target state |
| `runtime_binding_history` | Append-only before/after generation and desired/applied evidence |
| `backup_records` | Bundle identity, hashes, encryption key ID and verification result |
| `restore_plans` / `restore_executions` | Staging/cutover preconditions and retained-store result |
| `retention_runs` | Three-day cleanup count plus protected control-plane count hash |

Migration 003 copies all accepted RuntimeBindings into the rebuilt table with
null desired/applied targets and generation zero, then re-establishes
same-screen composite ownership. An exact accepted-P1.2 copy reaches 003 with
three screens and three unchanged null-release bindings. Repeat initialization
does not change the file hash.

A `VALID` validation row must bind a non-null resolution fingerprint ID and
hash. An `INVALID` row must bind neither; it preserves sanitized failure
findings and draft revision evidence while the draft remains `DRAFT`. The
database check constraint rejects either branch in the other shape.

## Immutability And Provenance

- ConfigDraft revisions, fingerprints, validation/preview/approval records,
  ConfigRelease, ReleaseTarget and RuntimeBinding history reject update and
  delete through database triggers.
- NORMAL release provenance binds one approved draft revision, fingerprint and
  approval. ROLLBACK provenance binds one consumed HighRiskAction and a
  canonical per-screen historical source map. The branches are mutually
  exclusive.
- Each ReleaseTarget recomputes SHA-256 over its canonical effective content.
  Source and destination screen must match for rollback. A rollback copies
  source content/hash byte-for-byte into a new target and never repoints
  history.
- Publications cannot change their frozen plan fields or be deleted. Group
  target rows are inserted only after the complete membership, release target,
  ETag and generation set passes.

## Runtime Binding Semantics

- Publication writes `desired_release_target_id`, increments
  `binding_generation` and leaves applied/acknowledgement fields unchanged.
- Device acknowledgement compares the credential-owned screen, exact desired
  target, generation and content hash, then writes
  `applied_release_target_id` and acknowledgement evidence.
- Single-screen and group paths retain same-screen composite foreign keys.
  No supported write can bind one screen to another screen's ReleaseTarget or
  DigitalHumanInstance.

## Backup Bundle And Restore

Every bundle directory has exactly four files:

```text
manifest.json
payload.aes256gcm
checksums.sha256
verification.json
```

`payload.aes256gcm` contains an AES-256-GCM encrypted archive with an online
SQLite snapshot and logical NDJSON export. The authenticated header binds
schema/migration checksums, source database hash, logical export hash, audit
head, complete RuntimeBinding count and purpose-separated recovery key ID.
The root/recovery key is not stored in the bundle.

Backup creation applies the same complete snapshot checks as later verification
before it can publish the four-file directory or insert a `VERIFIED`
`backup_records` row. The verified snapshot and logical-export row counts must
match. A source snapshot with foreign-key or migration corruption therefore
fails without a final bundle, staging bundle or backup record.

Verification decrypts only into a temporary staging directory and checks:

1. exact file set, checksums and authenticated header;
2. exact ordered migration registry;
3. SQLite foreign keys and complete three-screen RuntimeBindings;
4. immutable ReleaseTarget content hashes;
5. logical export hash/counts and SecurityAuditEvent chain head.

Fresh verification additionally compares the authenticated bundle identity,
manifest and ciphertext hashes, ownership, migration set, recovery-key ID, row
counts, audit head, size and timestamp to the immutable requested
`backup_records` row. A different internally valid bundle cannot impersonate
the requested backup.

Restore reconciles the active live security tables into the staged snapshot
before cutover. Live users, role assignments, credential generations and
active device families/credentials remain authoritative. Pending one-time
enrollment/credential material is revoked, sessions and replay ciphertext are
invalidated, unfinished HighRiskActions fail, and the previous online database
is retained. Staged evidence is validated before the atomic path replacement.
All supported control-plane mutations use one re-entrant mutation barrier;
backup capture and restore hold it across their consistency boundary so an
acknowledged mutation cannot be silently lost at cutover.

## Runtime-Detail Retention

The separate POC session-log database defaults to three days and records every
cleanup run. The control-plane retention record stores only the deleted detail
count and a hash of protected row counts. Cleanup never targets users, device
history, releases, publications, restore evidence or SecurityAuditEvent rows.

## Explicitly Absent

- No SecretRecord/SecretVersion, FineReport identity/session binding,
  QuerySource, provider, Renderer or AvatarPackage release data.
- No external RecoverySecurityLedger/WORM/OperationalFence, offline/full-loss
  authority or cryptographic-root recovery.
- No PostgreSQL migration/restore, automatic hourly scheduler, separate-mount
  production certification or customer RPO/RTO.
