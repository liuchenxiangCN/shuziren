# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.2 Accepted; P1.3 Awaiting Explicit Activation`.

G0, P1.0, P1.1 and P1.2 were explicitly accepted on 2026-07-27. Accepted P1.2
candidate `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree
`565dbb3567e2a4ae5b872177d97449120477fe8c`, schema
`p1_control_plane_001` with migration `002_three_screen_inventory`, is the
current runtime rollback baseline. P1.3 is not active.

## Next Task

Await an explicit user instruction to begin P1.3. On that instruction, freeze
the P1.3 result card and non-scope against the accepted P1.2 runtime before any
draft, release, publication, rollback or recovery implementation starts.

### Accepted P1.2 Baseline

- [acceptance/productization/P1.2/ACCEPTANCE_CARD.md](acceptance/productization/P1.2/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.2/USER_DECISION.md](acceptance/productization/P1.2/USER_DECISION.md)
- [acceptance/productization/P1.2/manifest.json](acceptance/productization/P1.2/manifest.json)

The accepted baseline remains a local development-preview result. FVS is
`UNVERIFIED`, runtime configuration is `NOT_CONFIGURED_P1_3`, and production
publication/recovery is not implemented.

### P1.3 Start Boundary

- Require an explicit user instruction before activating the batch.
- Freeze the complete user-visible result, non-scope and rollback target first.
- Preserve P1.2 screen ownership, device trust, audit and Secret boundaries.
- Keep real FineReport/FVS/plugin compatibility Blocked until its external gate passes.
- Do not treat the accepted P1.2 inventory as publication or recovery evidence.

## Queued

`Productization P1.3 Publish, Rollback And Recovery`.

P1.3 remains queued until the user explicitly starts it.
