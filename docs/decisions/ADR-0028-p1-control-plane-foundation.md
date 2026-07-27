# ADR-0028: P1 Control-Plane Foundation Contracts

## Status

Proposed

This decision becomes Accepted only if the user explicitly accepts the P1.0 result package. Nothing in this ADR is implemented by its publication.

## Date

2026-07-27

## Context

ADR-0026 fixed the single-customer, single-site, multi-screen product boundary but intentionally deferred:

- the embedded and external control-plane stores;
- backup medium, schedule, RPO and RTO;
- built-in local password, session, lockout and reset policy;
- device credential lifecycle;
- the target control-plane namespace and concurrency contract;
- the precise separation between mutable drafts, immutable releases and per-screen applied state.

The existing POC still uses global Settings, global Provider instances, an administrator token and unversioned routes. Reusing those semantics would allow cross-screen configuration, identity or release leakage.

P1.0 must freeze a design that later P1.1-P1.3 can implement without describing target behavior as already available.

## Decision

1. The target hierarchy is Tenant -> Deployment -> Site -> optional ScreenGroup -> ScreenInstance. Every tenant-owned reference carries the ownership boundary, and each screen has one RuntimeBinding and no more than one active DigitalHumanInstance.
2. Control-plane users, ScreenInstance devices and FineReport display / service identities are three different identity planes with different credential stores. A device credential determines its screen scope server-side.
3. V1 local passwords use a 15-to-128 Unicode-code-point policy, block common/compromised choices, impose no composition or periodic-change rule and use Argon2id with at least 19 MiB, two iterations and parallelism one.
4. User sessions are opaque server-side sessions with 30-minute idle and 8-hour absolute expiry. High-risk actions require reauthentication no more than 10 minutes old, a reason and immutable audit.
5. Five failed logins inside 15 minutes cause a 15-minute lock; repeated locks inside 24 hours increase to 30 and 60 minutes. Reset tokens are random, digest-stored, single-use and expire after 15 minutes.
6. Device enrollment secrets are 256-bit, digest-stored, single-use and valid for 15 minutes. Device credentials are screen-bound and versioned. Rotation activates a successor and revokes its predecessor atomically; hard revocation advances a credential epoch.
7. Configuration uses ConfigDraft and immutable ConfigDraftRevision evidence. Validation creates a ResolutionFingerprint binding target membership, inheritance revisions and per-screen hashes; preview and approval bind that fingerprint. Release creation revalidates it and atomically creates an immutable ConfigRelease plus all ReleaseTargets.
8. Publication only references existing ReleaseTargets, freezes its request plan and compares target binding preconditions. RuntimeBinding keeps desired and applied ReleaseTarget pointers separate. Rollback creates a new release and publication.
9. The embedded control-plane store is a release-pinned SQLite 3 library, minimum baseline 3.45, using WAL, `synchronous=FULL`, foreign keys and local persistent storage with one active control-plane instance.
10. The only V1 external control-plane store is PostgreSQL 16 on its current supported minor release. MySQL and Oracle remain QuerySource engines, not control-plane stores.
11. The default production backup backend is an encrypted and hashed filesystem bundle on a mounted path separate from the live data root. The default schedule is hourly, retaining 24 hourly, 7 daily and 4 weekly verified generations.
12. The embedded standard-production targets are RPO at most one hour and reference single-site RTO at most two hours. These remain unverified until P1.3 produces restore evidence.
13. Restore validates into a new location before atomic cutover, never overwrites the active store, and reconciles an authenticated RecoverySecurityLedger whose monotonic anchor is outside the live store, backup root and ledger. Old password generations, disabled-user state and superseded/revoked device credentials cannot be revived.
14. Target user APIs use `/api/v1/control-plane/*`; device APIs use `/api/v1/device/*`. Existing POC `/api/config/*`, `/api/ops/*` and `/api/screen/*` keep their current meanings.
15. Control-plane mutations of existing resources require strong ETags and `If-Match`; publication also checks binding generations. Device acknowledgement uses credential-scoped generation/hash CAS as its explicit exception. High-risk POST commands require scoped idempotency keys.
16. UI visibility is not authorization. The API denies by default, checks operation plus resource scope on every request, authorizes all changed draft fields atomically and has no permission that reveals stored Secret values.
17. Standard production publication, rollback, device hard revocation, Secret replacement, FineReport identity replacement and restore require a typed HighRiskAction approved by a different user. Generic free-form high-risk action creation is forbidden.
18. The full normative detail is the proposed contract pack under `docs/product/contracts/` and its machine-readable `p1-target-contract.json`.

## Consequences

### Positive

- Identity and data scope cannot be selected by a device request body or reused from an administrator token.
- A screen can remain on its last verified applied release while the control plane has a newer desired release.
- Group membership changes cannot silently alter an in-flight publication.
- SQLite keeps the default private deployment small, while PostgreSQL provides one explicit scale-up and external-operations path.
- Password and session behavior is testable rather than left to framework defaults.
- Backup and restore have concrete media, cadence and safety targets.
- Target APIs are isolated from the implemented POC and can use explicit version, authorization, idempotency and concurrency semantics.

### Trade-Offs

- SQLite permits one active control-plane writer topology and cannot place its WAL database on shared network storage.
- PostgreSQL 16 adds a second migration and recovery path that must be certified before support is claimed.
- Hourly verified backups require a separate production mount and capacity monitoring.
- Anti-rollback restore protection adds an independent authenticated ledger plus administrator-controlled monotonic anchor and may require password reset or device re-enrollment after recovery.
- A fully resolved ReleaseTarget per screen stores more metadata than a shared mutable configuration, but removes runtime inheritance ambiguity.
- The standard production approval preset may require a second privileged user for four-eyes operations.
- P1.0 remains documentation and machine-contract validation only; real authentication, migration, concurrency and restore behavior still require P1.1-P1.3 evidence.

## Follow-Up

- Validate `p1-target-contract.json` and negative fixtures before presenting P1.0 for acceptance.
- Keep ADR-0028 Proposed and P1.1 queued until the user decides on P1.0.
- P1.1 implements local IAM and device trust against this accepted contract.
- P1.2 implements three-screen inventory and ownership constraints.
- P1.3 implements immutable publication, backup and restore and measures the RPO/RTO target.
- P5 certifies exact SQLite library, PostgreSQL minor, driver and operating-system combinations.
