# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.0 Target Contract Result Pack`.

G0 was explicitly accepted on 2026-07-27. Product runtime remains the existing single-instance POC baseline.

## Next Task

Complete and verify the P1.0 target contract result pack, then present it for explicit user acceptance.

### User-Visible Result

P1.0 must provide:

1. A business-readable domain diagram for Tenant, Deployment, Site, ScreenGroup, ScreenInstance, DeviceEnrollment, DigitalHumanInstance and RuntimeBinding.
2. Separate identity models for control-plane users, screen devices and FineReport display / service identities.
3. A role-action matrix and frozen local password, session, lockout and reset policy.
4. Screen-enrollment and configuration-release state walkthroughs.
5. An immutable release, targeted publication and rollback contract that preserves three-screen isolation.
6. A relational target data model with ownership, uniqueness, foreign-key and optimistic-concurrency rules.
7. A frozen embedded / external control-plane storage, migration, backup, restore, retention, RPO and RTO decision.
8. A versioned control-plane API contract with user-operation examples, authorization, idempotency and understandable failure semantics.

### Result Package

- [acceptance/productization/P1.0/ACCEPTANCE_CARD.md](acceptance/productization/P1.0/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.0/AUTOMATED_SUMMARY.md](acceptance/productization/P1.0/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P1.0/KNOWN_LIMITATIONS.md](acceptance/productization/P1.0/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P1.0/manifest.json](acceptance/productization/P1.0/manifest.json)
- [acceptance/productization/P1.0/USER_DECISION.md](acceptance/productization/P1.0/USER_DECISION.md)
- [product/contracts/README.md](product/contracts/README.md)

The user decision remains Pending until an explicit result decision is received.

### User Result Scenarios

1. Follow the domain diagram from one Site to three independently bound screens.
2. Walk a device from one-time enrollment through credential rotation and revocation.
3. Compare administrator, implementation, operations and audit permissions.
4. Walk a draft through validation, preview, approval, publication and rollback.
5. Trace a single-screen publish and prove the other two screen bindings do not change.
6. Review backup, restore, RPO and RTO behavior for embedded and external storage.
7. Match API examples to the same user operations and failure paths.

### Automated Gates

- Contract index, lifecycle markers, links and machine-readable artifacts validate.
- Domain, data, identity, RBAC, state-machine and API names are consistent.
- Forbidden state transitions, mutable published releases and cross-screen targeting are rejected by negative fixtures.
- API operations define authorization, idempotency or optimistic concurrency where applicable.
- Secret values cannot appear in ordinary API responses, audit details or backup manifests.
- Storage, migration, backup, restore, RPO and RTO decisions are explicit.
- `git diff --check` and the repository lifecycle lint pass.

### Non-Scope

- No runtime code, database, migration, management UI or HTTP endpoint implementation.
- No P1.1 identity or device-trust implementation.
- No P1.2 three-screen inventory implementation.
- No P1.3 publish, rollback or recovery implementation.
- No FineReport plugin, database-query Provider or Renderer implementation.
- No change to the implemented POC API or data contracts.

### Stop Conditions

- A target contract is described as implemented.
- A control-plane user, screen device and FineReport data identity can be confused or reused.
- A published release can be edited in place.
- A single-screen operation can implicitly target another screen.
- UI authorization can differ from API authorization.
- A Secret value can be returned, logged or placed in a plaintext backup manifest.
- Storage or recovery decisions remain ambiguous.
- Contract consistency, negative-fixture or lifecycle checks fail.

## Queued After P1.0 Acceptance

`Productization P1.1 Identity And Device Trust`.

P1.1 remains queued until P1.0 receives an explicit user result decision.
