# P2.1 Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_PRESENT; FINAL_VERIFICATION_PENDING`
- Candidate commit / tree: `PENDING`
- Logical schema: `p1_control_plane_001`
- Latest migration: `004_capability_profiles`
- Profile / registry schema: `p2_capability_profile_v1` /
  `p2_provider_registry_001`
- Acceptance: `PENDING`

This document describes the additive SQLite structures currently present in
the candidate worktree. Final migration hashes, evidence hashes and gate
results remain `PENDING`.

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
Initialization validates the exact ordered migration registry and fails closed
on unknown, reordered or checksum-changed state.

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
Final backup/restore and rollback evidence is still `PENDING`.

## Explicitly Absent

- No SecretRecord/SecretVersion, ConnectorInstance, QuerySource,
  ScreenActionPack, Provider credential, endpoint, DSN or customer data.
- No real FineReport/FVS/plugin identity, session, permission inheritance,
  template or compatibility evidence.
- No PostgreSQL control-plane migration, external monotonic anchor, full-loss
  recovery or customer RPO/RTO certification.
