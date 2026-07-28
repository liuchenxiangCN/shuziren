# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-28
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.3 Accepted; P2.1 Awaiting Explicit Activation`.

G0 and P1.0 through P1.3 are explicitly accepted. P1.3 candidate
`0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
`04bcbb940fbedb5fbb8957e538f46a4422e15db2`, schema
`p1_control_plane_001` with migration `003_publish_rollback_recovery`, is the
accepted runtime rollback baseline. The user accepted it without conditions on
2026-07-28. P2.1 is not active.

## Next Task

Await an explicit user instruction to begin P2.1. On that instruction, freeze
the complete P2.1 result card and non-scope against the accepted P1.3 runtime
before implementing any capability-profile behavior.

### Accepted P1.3 Baseline

- [acceptance/productization/P1.3/ACCEPTANCE_CARD.md](acceptance/productization/P1.3/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.3/AUTOMATED_SUMMARY.md](acceptance/productization/P1.3/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P1.3/KNOWN_LIMITATIONS.md](acceptance/productization/P1.3/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P1.3/RUNBOOK.md](acceptance/productization/P1.3/RUNBOOK.md)
- [acceptance/productization/P1.3/manifest.json](acceptance/productization/P1.3/manifest.json)
- [acceptance/productization/P1.3/USER_DECISION.md](acceptance/productization/P1.3/USER_DECISION.md)

The accepted baseline remains a local development-preview result. Preview is
`MOCK_PASSED`, FVS is `UNVERIFIED`, and no production activation, real
FineReport/FVS/plugin compatibility, full-loss recovery, PostgreSQL recovery or
customer RPO/RTO is claimed.

### P2.1 Start Boundary

- Require an explicit user instruction before activating the batch.
- Freeze one independently usable capability-profile result and rollback target.
- Preserve P1.3 ownership, publication, device acknowledgement, recovery,
  Secret, audit and three-screen isolation controls.
- Keep provider states distinct: `disabled`, `mock`, `unverified`, `available`
  and `degraded`.
- Do not present Mock evidence as real-provider or external-plugin evidence.

## Queued

`Productization P2.1 Capability Profiles`.

P2.1 remains queued until the user explicitly starts it.
