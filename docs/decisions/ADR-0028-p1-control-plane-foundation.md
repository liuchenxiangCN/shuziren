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
4. User sessions are opaque server-side sessions with 30-minute idle and 8-hour absolute expiry, delivered only in the host-only `__Host-shuziren_session` cookie. Browser state changes require exact allowed Origin. Cookie mutations require a session-bound CSRF header except exact-Origin/no-store `refreshCsrfToken`, the sole narrow bootstrap exception; `getCurrentAuthSession` is read-only. Authentication, reauthentication and privilege change rotate the session identifier and revoke the predecessor before the successor is usable. High-risk actions require reauthentication no more than 10 minutes old, a reason and immutable audit.
5. Five failed logins inside 15 minutes cause a 15-minute lock; repeated locks inside 24 hours increase to 30 and 60 minutes. Reset tokens are random, digest-stored, single-use and expire after 15 minutes. `NORMAL_PASSWORD_RESET` binds the current person/privilege generations and target channel; `PROVISIONING_CREDENTIAL_SETUP` applies only to a disabled empty-role provisioning user, has null person fields at issuance and can set only credential plus target-possession evidence. Only reset issuance, enrollment issuance/claim and device rotation may retain a five-minute encrypted one-time response replay; login is excluded and restore deletes every replay ciphertext.
6. Device enrollment secrets are 256-bit, digest-stored, single-use and valid for 15 minutes. Production issuance is four-eyes and binds current DeviceCredentialFamily generation plus ledger head. Device credentials are screen-bound and versioned under a family with at most one `ACTIVE` credential and one pending successor. Rotation activates a successor and revokes its predecessor atomically; hard revocation binds the family ETag, credential epoch and ledger head, revokes the family atomically and advances the epoch exactly once.
7. Configuration uses ConfigDraft and immutable ConfigDraftRevision evidence. Draft creation accepts only target envelope plus `schema_version`, produces an empty spec and rejects initial content. Validation creates a ResolutionFingerprint binding target membership, inheritance revisions and per-screen hashes; preview and approval bind that fingerprint plus the control-plane epoch. A `NORMAL` release revalidates the approval/fingerprint; a mutually exclusive `ROLLBACK` release binds an exact same-screen historical target map and HighRiskAction. Either creates ConfigRelease and all ReleaseTargets atomically.
8. Publication only references existing ReleaseTargets, freezes its request plan and compares target binding preconditions. RuntimeBinding keeps desired and applied ReleaseTarget pointers separate. Rollback creates a new release and publication without substituting content or credential versions.
9. The embedded control-plane store is a release-pinned SQLite 3 library, minimum baseline 3.45, using WAL, `synchronous=FULL`, foreign keys and local persistent storage with one active control-plane instance.
10. The only V1 external control-plane store is PostgreSQL 16 on its current supported minor release. MySQL and Oracle remain QuerySource engines, not control-plane stores.
11. The default production backup backend is an encrypted and hashed filesystem bundle on a mounted path separate from the live data root. The default schedule is hourly, retaining 24 hourly, 7 daily and 4 weekly verified generations.
12. The embedded standard-production targets are RPO at most one hour and reference single-site RTO at most two hours. These remain unverified until P1.3 produces restore evidence.
13. Restore validates/reconciles staged state and uses an externally anchored RecoverySecurityLedger for bootstrap; deployment activation/readiness/emergency/root recovery; human-operator identity/bindings; users/passwords/roles; devices; Secrets; FineReport; and key-registry state. Normal authorization implies online source; full loss requires local disaster quorum; local+online is allowed only when no administrator can authenticate. Online retains the previous pointer and carries a full barrier suffix. Full loss uses null previous pointer, a strictly empty backup-head suffix and an ordered Ed25519 2-of-3 ExternalRecoveryAudit chain rooted at the backup-manifest audit head, and keeps failed staged state unserved. Degraded recovery binds the exact missing-subject set in the selected XOR authorization branch.
14. Target user APIs use `/api/v1/control-plane/*`; device APIs use `/api/v1/device/*`. Existing POC `/api/config/*`, `/api/ops/*` and `/api/screen/*` keep their current meanings.
15. Control-plane mutations use strong ETags; device acknowledgement uses credential-scoped generation/hash CAS. HighRiskAction stores `request_hmac_key_id`; general sensitive idempotency stores its separate `sensitive_digest_key_id`. Asynchronous network execution binds authorization kind plus exactly one DirectOperationAuthorization, action or disaster-envelope ID; the direct branch is restricted to backup creation/verification and cannot authorize a high-risk, restore or local-maintenance operation. Local readiness/emergency/root operations use their own authorization, terminal nonce and external evidence. Execution idempotency is phase + kind + evidence + exact command. Stale initiator reauth returns HTTP 403 `RECENT_REAUTHENTICATION_REQUIRED` while the action remains approved through TTL.
16. UI visibility is not authorization. The API denies by default, checks operation plus resource scope on every request, authorizes all changed draft fields atomically and has no permission that reveals stored Secret values.
17. Deployment activation; privileged user create/update/disable/enable/unlock/reset/session-revoke/role-replace; publication; rollback; device enrollment/revocation; Secret/FineReport replacement; and restore use `production_four_eyes_v1`. Production initiator and approver differ by both active UserAccount ID and externally custodian-attested person ID. Approval records evidence only; execution atomically freezes command/plan/operation/outbox/idempotency/audit under one authorization tuple, and the worker never rereads mutable request state.
18. RestoreContinuityEnvelope uses nonce-protected HMAC-SHA-256 under its own purpose and binds recovery-source mode, authorization evidence, prepared sequence/head, ledger/envelope key IDs, payload and pointers. RestoreCutoverRecord binds the same source mode. Online alone requires a live barrier/full suffix/retained pointer; full loss does not fabricate them. Cutover/finalization remains fenced and idempotent.
19. Eighteen key-purpose domains never reuse keys and use an external monotonic registry. The original twelve are joined by separate `CSRF_TOKEN_VERIFIER_PEPPER`, `HUMAN_OPERATOR_ATTESTATION_SIGNATURE`, `DISASTER_ENVELOPE_NONCE_HMAC`, `OPERATIONAL_FENCE_HMAC`, `PRODUCTION_READINESS_NONCE_HMAC` and `EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC` boundaries. Keyed verifiers are HMAC-SHA-256 with at least 256-bit keys and stored key IDs. AES-256-GCM records store unique-per-key nonce, tag, key ID and exact AAD. Immutable evidence rotates by purpose; temporary key outage returns 503 without state change, while confirmed revocation/loss alone causes irreversible invalidation.
20. A local setup ceremony issues the first BootstrapGrant already bound to a server-reserved first-user ID, two-custodian person attestation/user binding, target channel/possession proof and external registry generations; completion cannot substitute them. Bootstrap leaves deployment `SETUP` and may temporarily have one administrator. Only platform-admin `deployment.manage`, `production_four_eyes_v1`, two usable administrators bound to different attested persons and complete disaster readiness can anchor irreversible `SETUP -> PRODUCTION_ACTIVE`.
21. Production operational posture is governed by the highest verified external monotonic fence. Temporary registry/anchor/key outage is an ephemeral retryable fail-closed gate with no persisted mutation; confirmed loss or persistent breach appends `RECOVERY_REQUIRED`. Readiness recovery, emergency authority reduction and recoverable HMAC-root repair are local-only 2-of-3 flows with distinct terminal nonce and external audit records. Only readiness recovery can append a READY successor; emergency reduction cannot increase authority, root repair cannot write READY, and production never returns to SETUP.
22. RecoveryPasswordSetupGrant is shared by `STANDARD_HIGH_RISK`, `DISASTER_CUSTODIAN` and `PRODUCTION_READINESS_CUSTODIAN`. Counts are normal stale/missing credentials 1..2, disaster SETUP=1/production=2 and readiness replacement=1. State is `ISSUED -> PROVISIONALLY_CONSUMED -> COMMITTED_CONSUMED`, with terminal `EXPIRED | ABORTED_REVOKED`; the entire required set commits with its branch-specific restore/readiness anchors or aborts atomically and terminally consumes the applicable nonce.
23. The full normative detail is the proposed contract pack under `docs/product/contracts/` and its machine-readable `p1-target-contract.json`.

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
- Anti-rollback restore protection adds an independent authenticated ledger, administrator-controlled monotonic anchor and authenticated continuity envelope; recovery may require password reset, role reconciliation, device re-enrollment, Secret rotation or FineReport rebinding.
- Explicit degraded credential recovery can restore unaffected subjects but deliberately leaves listed Secret/FineReport subjects unavailable and produces a distinct terminal result.
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
