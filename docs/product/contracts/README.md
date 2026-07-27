# Target Product Contracts

## Document Status

- Lifecycle: `TARGET_NOT_IMPLEMENTED`
- Scope: Productization P1 target domain, data, identity, state, storage and API contracts
- Contract version: `p1.0-target-v1`
- Last reviewed: 2026-07-27

These contracts define the reviewed target for later P1 implementation. They do not describe implemented runtime behavior.

## Contract Pack

1. [DOMAIN_MODEL.md](DOMAIN_MODEL.md) — aggregate ownership, identifiers and three-screen isolation.
2. [IDENTITY_AND_RBAC.md](IDENTITY_AND_RBAC.md) — local IAM, device trust, FineReport identity and role-action rules.
3. [CONFIGURATION_RELEASE.md](CONFIGURATION_RELEASE.md) — enrollment, draft, release, publication and rollback state machines.
4. [DATA_MODEL.md](DATA_MODEL.md) — relational entities, constraints, concurrency and retention.
5. [STORAGE_AND_RECOVERY.md](STORAGE_AND_RECOVERY.md) — embedded / external stores, migration, backup, restore, RPO and RTO.
6. [CONTROL_PLANE_API.md](CONTROL_PLANE_API.md) — versioned control-plane and device API operations and examples.
7. [p1-target-contract.json](p1-target-contract.json) — machine-readable invariants, states, permissions and operation registry.

The proposed architectural and security choices are recorded in [ADR-0028](../../decisions/ADR-0028-p1-control-plane-foundation.md). They remain proposed until P1.0 receives an explicit user decision.

## Namespace Boundary

The implemented single-instance POC contracts remain authoritative only for existing code:

- [../../06_API_CONTRACT.md](../../06_API_CONTRACT.md)
- [../../07_DATA_CONTRACT.md](../../07_DATA_CONTRACT.md)

P1.0 does not change those files, their routes or their data structures. Future implementation must explicitly migrate from the POC baseline to these target contracts; a target document alone is never implementation evidence.

## Contract Rules

- Terms and identifiers defined in [DOMAIN_MODEL.md](DOMAIN_MODEL.md) are canonical across this pack.
- Authorization is enforced by the API for every request; UI visibility never grants permission.
- Control-plane users, screen devices and FineReport data identities never share credentials.
- Preview and approval bind one ResolutionFingerprint; a `NORMAL` ConfigRelease revalidates it, while a mutually exclusive `ROLLBACK` release binds exact historical provenance and a HighRiskAction. Either release and all ReleaseTargets are created atomically.
- `ConfigRelease` content is immutable; Publication never creates release content, and rollback creates a new release and publication.
- A device credential determines its screen scope server-side; a request cannot choose another screen.
- Secret values are accepted only by dedicated write operations and are never returned by ordinary reads, audit events or backup manifests.
- Control-plane mutations use explicit optimistic concurrency; device acknowledgement uses its credential-scoped generation/hash CAS.
- Browser state changes require exact allowed Origin. Cookie mutations require a session-bound CSRF header except exact-Origin/no-store `refreshCsrfToken`, the single narrow bootstrap exception; `getCurrentAuthSession` is read-only. Pending high-risk items are filtered per target permission/scope.
- Draft creation accepts only a target envelope and `schema_version`, creates an empty spec and rejects initial content; first population uses the field-authorized spec replacement operation.
- Standard production high-risk approval records evidence only. Asynchronous network execution binds `authorization_kind` and exactly one of DirectOperationAuthorization, HighRiskAction or disaster-envelope ID; the direct branch is restricted to `createBackup` and `verifyBackup`, while the latter two branches retain their protected-operation and restore rules. Local readiness, emergency-reduction and root-recovery operations instead bind their own authorization, terminal nonce and external evidence. Idempotency scope is phase + kind + evidence + exact command. The closed operation-to-ledger map includes bootstrap; activation/readiness/emergency/root recovery; human-person identity/binding; user/password/role; device; Secret; FineReport; and key-registry security changes.
- Eighteen isolated purpose domains are frozen: `HIGH_RISK_REQUEST_HMAC`, `SENSITIVE_REQUEST_DIGEST_HMAC`, `RESTORE_CONTINUITY_ENVELOPE_HMAC`, `RECOVERY_LEDGER_CHAIN_HMAC`, `RECOVERY_LEDGER_RECORD_AEAD`, `AUTH_SESSION_VERIFIER_PEPPER`, `CSRF_TOKEN_VERIFIER_PEPPER`, `ONE_TIME_TOKEN_VERIFIER_PEPPER`, `ONE_TIME_RESPONSE_ENCRYPTION`, `DEVICE_CREDENTIAL_VERIFIER_PEPPER`, `SECRET_ENVELOPE_ENCRYPTION`, `BACKUP_RECOVERY_ENCRYPTION`, `OFFLINE_RECOVERY_AUTHENTICATION`, `HUMAN_OPERATOR_ATTESTATION_SIGNATURE`, `DISASTER_ENVELOPE_NONCE_HMAC`, `OPERATIONAL_FENCE_HMAC`, `PRODUCTION_READINESS_NONCE_HMAC` and `EMERGENCY_AUTHORITY_REDUCTION_NONCE_HMAC`. Cross-purpose reuse is forbidden. Keyed verifiers use HMAC-SHA-256 with at least 256-bit keys; AES-256-GCM records store unique-per-key nonce, tag, key ID and exact AAD schema.
- The first BootstrapGrant is issued only by a local setup ceremony and already binds a server-reserved user ID, two-custodian person attestation/user binding, target channel/possession proof and registry generations. Client completion cannot substitute person, user, role or channel. Later `createUser` produces only a disabled empty-role `PROVISIONING` account; target-only credential setup cannot enable or grant.
- Bootstrap remains `SETUP` and may have one administrator. Platform-admin-only `deployment.manage` plus `production_four_eyes_v1`, two usable administrators bound to two distinct attested persons and full disaster readiness are required for the ledger-backed one-way transition to `PRODUCTION_ACTIVE`.
- The external monotonic operational fence is authoritative in production. Temporary required-dependency outage creates an ephemeral retryable fail-closed gate without persisted mutation; confirmed loss or persistent breach appends `RECOVERY_REQUIRED`. Readiness, emergency authority-reduction and recoverable HMAC-root repair are local-only, use distinct nonce/authorization/audit records, and only the readiness branch may append a READY successor after complete evidence. Production never returns to SETUP.
- Normal restore implies online source. Full loss requires local 2-of-3 disaster quorum; local+online is legal only with no authenticatable administrator. Online carries the full maintenance-barrier SecurityAuditSuffix and retained pointer; full loss uses null previous pointer, an empty backup-head suffix and signed ExternalRecoveryAudit.
- RecoveryPasswordSetupGrant is shared by standard restore, disaster restore and readiness replacement. Exact count is normal stale/missing credentials 1..2, disaster SETUP=1/production=2, readiness replacement=1; state is `ISSUED -> PROVISIONALLY_CONSUMED -> COMMITTED_CONSUMED` with terminal `EXPIRED | ABORTED_REVOKED`. The complete set commits only with its branch-specific anchors or aborts atomically. Every restore deletes one-time response replay ciphertext.
- RestoreCutoverRecord exposes every pointer/anchor/finalization state. Pointer and database marks are reconciled rather than treated as cross-domain atomic; all cutover checks precede pointer replacement and finalization updates the whole execution atomically without redispatch. `SETUP` stays unserved; every finalized production restore stays `RECOVERY_REQUIRED` until a separate local readiness recovery commits its nonce/ledger/external-audit evidence and READY fence successor.
- Machine validation is necessary but does not make the target implemented or accepted.
