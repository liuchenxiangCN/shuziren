# P2.1 Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate commit: `8f364b93b574c058cd8cd617f925107985318098`
- Candidate tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- Logical schema: `p1_control_plane_001`
- Latest migration: `004_capability_profiles`
- Migration checksum SHA-256: `c0522a5a5dc596355812333a5895a204acf16c5ad80b0b83be1a16da3f3116cd`
- Profile / registry schema: `p2_capability_profile_v1` /
  `p2_provider_registry_001`
- Acceptance: `PENDING`

This document describes the additive SQLite structures in the exact candidate
that passed automated gates and independent review. The candidate remains
unaccepted until the user records an explicit decision.

## Additive Structures

| Structure | Implemented purpose |
| --- | --- |
| `capability_profiles` | Site-owned mutable name, description, head pointer and strong revision |
| `capability_profile_versions` | Immutable canonical seven-capability specs and derived evidence |
| `config_draft_capability_assignments` | Exact immutable ProfileVersion assignment for one draft revision |
| `release_target_capability_snapshots` | Exact immutable per-screen capability envelope for one ReleaseTarget |

Migration `004_capability_profiles` follows the checksummed 001, 002 and 003
registry entries. It adds tables, indexes, foreign keys and triggers without
rebuilding the accepted P1.3 tables or widening `p1_screen_config_v1`.
Initialization validates the exact ordered migration registry and every
expected user table, index, trigger and view definition. It fails closed on a
missing, unknown, reordered, checksum-changed or structurally changed object.
The accepted-P1.3 copied-upgrade command proves the complete source schema
before copying or applying migration 004; registry rows alone are not accepted
as source-integrity evidence.

## Profile Identity And Versions

The profile envelope binds Tenant, Deployment and Site, the mutable head
version, creator, timestamps and monotonic resource revision. Its head foreign
key is deferred so the initial envelope and immutable version 1 can be inserted
in one transaction.

Every ProfileVersion binds:

- profile, Site and monotonic version number;
- canonical `p2_capability_profile_v1` JSON and SHA-256 content hash;
- exact provider-registry version and hash;
- server-derived state summary, dependency findings and activation eligibility;
- creator and creation time.

Database triggers reject ProfileVersion update or delete. Another trigger
allows the envelope head only to advance. Reading a historical version does
not depend on the current head, and moving the head cannot alter an existing
draft assignment or release snapshot.

## Draft And Release Sidecars

Assigning a ProfileVersion creates a new `config_draft_revisions` row with the
unchanged two-field base spec, inserts the exact immutable capability
assignment for that revision, advances the draft resource revision and clears
validation, preview and approval references. Later legal base-spec revisions
copy the current assignment forward. Same-version assignment is idempotent and
does not create a second revision.

The assignment copies the version number, content hash, registry binding,
state summary, dependency findings and activation eligibility. Composite
foreign keys and an insert trigger enforce Tenant, Deployment and Site
agreement with both the profile version and the screen/group draft target.
Update and delete are rejected.

NORMAL release creation copies one canonical per-screen capability envelope
into `release_target_capability_snapshots`. The envelope binds the screen,
DigitalHumanInstance, profile/version, registry, closed spec and derived
evidence; its canonical JSON has a separate SHA-256 envelope hash. Update and
delete are rejected. Forward rollback copies the historical snapshot and hash
byte-for-byte into the new ReleaseTarget instead of resolving the current
profile head.

## Applied Runtime Isolation

RuntimeBindings remain the P1.3 desired/applied authority. Capability reads do
not add a mutable global-provider table or a caller-selected screen. Browser
readers see authorized desired/applied snapshots; devices see only the applied
target derived from their active credential.

The returned runtime isolation hash binds Tenant, Deployment, screen,
DigitalHumanInstance, ReleaseTarget, ProfileVersion and the optional
non-authoritative session label. It is derived per request and is not a shared
provider-session store.

## Recovery And Historical-Evidence Integrity

Snapshot validation walks both surviving P2.1 rows and immutable P1.3 evidence
that requires P2.1 sidecars. It rejects complete or partial profile/version,
assignment or release-snapshot loss, including a profile-only store whose rows
would otherwise disappear self-consistently. It recomputes canonical profile,
registry, state, dependency, effective-envelope and ResolutionFingerprint
hashes and reverse-binds validation, preview, approval, normal release and
rollback evidence to their authoritative inputs.

Resolution fingerprints retain their validation-time control-plane epoch.
After restore and a later draft revision, snapshot validation derives that
historical epoch from immutable evidence instead of the draft's mutable
current epoch. Tamper, restore, re-login, revise, online snapshot validation,
subsequent backup, second restore and discarded-branch pruning are covered by
executable regression.

Restore reconciliation is phase-aware for idempotency and protected domain
actions. A successful response is not reusable when its referenced restored
object is absent, and consumed publication or rollback actions whose domain
effect is no longer present are retained as failed history rather than revived
authority.

## Backup And Restore Integration

The existing encrypted online SQLite backup path includes the four new tables
in its native snapshot and logical export. Snapshot validation now checks:

- the complete four-table set and exact migration registry;
- canonical spec, content, provider-registry, state and dependency hashes;
- profile-head and draft-assignment scope/reference integrity;
- per-screen release envelope shape, hash and version references;
- presence of snapshots for assigned NORMAL releases; and
- byte-identical capability snapshot/hash copying for rollback targets.

These checks run during backup creation, fresh verification and staged restore
validation. The existing live-security reconciliation, mutation barrier,
retained pre-restore store and protected retention semantics remain in place.
The final candidate backup/restore regressions and the accepted-P1.3
product-code plus exact pre-004 data rollback gate passed.

## Explicitly Absent

- No SecretRecord/SecretVersion, ConnectorInstance, QuerySource,
  ScreenActionPack, Provider credential, endpoint, DSN or customer data.
- No real FineReport/FVS/plugin identity, session, permission inheritance,
  template or compatibility evidence.
- No PostgreSQL control-plane migration, external monotonic anchor, full-loss
  recovery or customer RPO/RTO certification.
