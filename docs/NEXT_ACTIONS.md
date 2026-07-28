# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-28
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P2.1 Capability Profiles Active`.

G0 and P1.0 through P1.3 are explicitly accepted. P1.3 runtime candidate
`0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
`04bcbb940fbedb5fbb8957e538f46a4422e15db2`, schema
`p1_control_plane_001` with migration `003_publish_rollback_recovery`, remains
the accepted runtime rollback baseline.

The user explicitly instructed Codex to complete P2.1 on 2026-07-28. P2.1 is
the sole active result batch. Its complete result card and non-scope are frozen
before runtime implementation:

- [acceptance/productization/P2.1/ACCEPTANCE_CARD.md](acceptance/productization/P2.1/ACCEPTANCE_CARD.md)
- [product/contracts/CAPABILITY_PROFILES.md](product/contracts/CAPABILITY_PROFILES.md)
- [product/contracts/p2-1-capability-profile-contract.json](product/contracts/p2-1-capability-profile-contract.json)

## Next Task

Complete the frozen P2.1 vertical result against accepted P1.3:

1. Implement checksummed additive migration `004_capability_profiles`.
2. Implement closed provider catalog, presets, Site-owned profiles and
   immutable versions.
3. Integrate exact profile assignment and immutable capability snapshots with
   the accepted P1.3 draft, fingerprint, release, publication,
   acknowledgement, rollback, backup and restore path.
4. Add the `/manage` capability-profile workflow and per-screen effective
   status.
5. Prove RBAC, Secret rejection, unverified activation blocking, technical-only
   safe fallback, legacy fail-closed behavior and three-screen concurrent
   resolution.
6. Produce exact-candidate evidence, a P1.3 rollback proof and a separate
   read-only Codex review.
7. Present the result scenarios for an explicit user decision.

### Active Boundary

- Preserve `p1_screen_config_v1` as the accepted exact two-field base schema;
  P2.1 uses additive immutable sidecars.
- Preserve P1.3 ownership, publication, device acknowledgement, recovery,
  Secret, audit and three-screen isolation controls.
- Keep `disabled`, `mock`, `unverified`, `available` and `degraded` distinct.
- A legacy P1.3 release without a capability snapshot resolves explicitly as
  `NOT_CONFIGURED_P2_1`; it never uses a global Provider or Mock fallback.
- FineReport official plugin and all unsupported real Providers remain
  `unverified`; no external request or compatibility claim is allowed.
- Mock/local evidence proves only the bounded P2.1 product flow.

### Rollback Baseline

- Runtime commit: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Runtime tree: `04bcbb940fbedb5fbb8957e538f46a4422e15db2`
- Acceptance record: `c24f041a0414ea5361a6fcb7216d7be99ea0bb56`
- Data rollback: verified WAL-safe exact pre-`004` backup

## Queued

`Productization P2.2 Controlled Excel And Database Querying`.

P2.2 remains queued. P2.1 implementation, automated success, independent
review or user silence does not activate it. Only an explicit P2.1 user
acceptance followed by a separate start instruction can do so.
