# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-08-04
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P3 Active — Candidate Ready For User Decision; P2.4 Deferred And Blocked By External Gate`.

G0 and P1.0 through P2.3 are explicitly accepted. The user accepted P2.3
without conditions or scope reduction through `通过` on 2026-07-29. Candidate
`a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
`8a2f4e36ca0751b6106a174f7dae63be9299ad5b`, fingerprint
`FE0F87AC1B3F1FD5373681E86BDFA0DE909D6A1E637BD22E2A97DEFD57F26097` over 36
files, schema `p1_control_plane_001` with migration
`005_controlled_querying`, is the accepted runtime baseline. Its automated
gates, fresh 1280 by 720 browser workflow, capacity measurement, Compose
smoke, accepted-P2.2 rollback and independent review pass; reviewer Faraday
reported zero blocking findings and seven non-blocking findings with N1–N3
closed before candidate binding.

On 2026-08-04 the user explicitly instructed `开始P3`. This defers P2.4
without removing it from product scope and activates exactly one result batch:
`P3 Renderer Extension Mechanism`. The accepted P2.3 candidate remains the
base and rollback target while P3 is active.

P3 candidate `0b37f7c0917441543735c0b4a08d15e27a27f98c`, tree
`48498864ea4c87e11e035b5439478d6c9b610046`, fingerprint
`6FFC13F6905122BBDC5B07B238821494F4A6C874C6216E7121CE1E4FBD54C058`
over 29 files is now bound. Its backend, frontend, contract, browser, Secret,
recovery, rollback, Compose smoke and independent-review gates pass with zero
blocking review findings. It remains unaccepted until the user explicitly
reviews and decides.

## Next Task

Review the runnable result and bound evidence in the frozen
[P3 acceptance card](acceptance/productization/P3/ACCEPTANCE_CARD.md), then
record an explicit user decision: accept, request changes or reject. Do not
advance another batch on silence. P3 proves only the test-only Renderer /
AvatarPackage extension and safe screen switching contract; it does not claim
any real 2D/3D format, supplier SDK or licensed asset.

P2.4 `FineReport Official Plugin` remains queued and blocked by its external
gate. Starting P3 neither passes nor removes P2.4.

### Accepted P2.3 Baseline

- [acceptance/productization/P2.3/ACCEPTANCE_CARD.md](acceptance/productization/P2.3/ACCEPTANCE_CARD.md)
- [acceptance/productization/P2.3/AUTOMATED_SUMMARY.md](acceptance/productization/P2.3/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P2.3/IMPLEMENTED_API.md](acceptance/productization/P2.3/IMPLEMENTED_API.md)
- [acceptance/productization/P2.3/KNOWN_LIMITATIONS.md](acceptance/productization/P2.3/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P2.3/RUNBOOK.md](acceptance/productization/P2.3/RUNBOOK.md)
- [acceptance/productization/P2.3/manifest.json](acceptance/productization/P2.3/manifest.json)
- [acceptance/productization/P2.3/USER_DECISION.md](acceptance/productization/P2.3/USER_DECISION.md)

### Accepted P2.2 Baseline

- [acceptance/productization/P2.2/ACCEPTANCE_CARD.md](acceptance/productization/P2.2/ACCEPTANCE_CARD.md)
- [acceptance/productization/P2.2/AUTOMATED_SUMMARY.md](acceptance/productization/P2.2/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P2.2/IMPLEMENTED_API.md](acceptance/productization/P2.2/IMPLEMENTED_API.md)
- [acceptance/productization/P2.2/IMPLEMENTED_DATA.md](acceptance/productization/P2.2/IMPLEMENTED_DATA.md)
- [acceptance/productization/P2.2/KNOWN_LIMITATIONS.md](acceptance/productization/P2.2/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P2.2/RUNBOOK.md](acceptance/productization/P2.2/RUNBOOK.md)
- [acceptance/productization/P2.2/manifest.json](acceptance/productization/P2.2/manifest.json)
- [acceptance/productization/P2.2/USER_DECISION.md](acceptance/productization/P2.2/USER_DECISION.md)

### Accepted Boundary

- Migration `005_controlled_querying` is additive; accepted P1.3/P2.1 base
  schemas and immutable release/profile structures remain unchanged.
- Runtime callers can select only a published immutable dataset and submit
  typed parameter values; free SQL, connection selectors and ownership
  selectors remain prohibited.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 evidence is deployment-local.
  Other versions, customer environments and the FineReport official plugin
  remain `UNVERIFIED`.
- P2.2 is an accepted local development-preview result, not production
  activation, capacity/SLA certification or customer compatibility
  certification.

## Queued

`Productization P2.4 FineReport Official Plugin` remains queued and blocked by
its external FineReport plugin gate.
