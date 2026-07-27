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
- Preview and approval bind one ResolutionFingerprint; ConfigRelease and all ReleaseTargets are created atomically only after that fingerprint is revalidated.
- `ConfigRelease` content is immutable; Publication never creates release content, and rollback creates a new release and publication.
- A device credential determines its screen scope server-side; a request cannot choose another screen.
- Secret values are accepted only by dedicated write operations and are never returned by ordinary reads, audit events or backup manifests.
- Control-plane mutations use explicit optimistic concurrency; device acknowledgement uses its credential-scoped generation/hash CAS.
- Standard production high-risk commands use typed, different-user approval. Restore also reconciles an independently anchored RecoverySecurityLedger.
- Machine validation is necessary but does not make the target implemented or accepted.
