# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-28
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P2.2 Accepted; P2.3 Awaiting Explicit Activation`.

G0 and P1.0 through P2.2 are explicitly accepted. The user accepted P2.2
without conditions or scope reduction through `确认验收` on 2026-07-28.
Candidate `a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
`aaa499de416b522e21c02f41119024296fc2c3a0`, fingerprint
`8A1A369FA328F6A516D9A36AD5F36C314629D2E683BBF38304510521817D357D`
over 47 files, schema `p1_control_plane_001` with migration
`005_controlled_querying`, is the accepted runtime baseline. Its automated
gates, three exact ephemeral database adapters, fresh 1280 by 720 browser
workflow, accepted-P2.1 rollback and final independent review pass; reviewer
Einstein reported zero blocking and zero non-blocking findings.

Accepted P2.1 candidate `8f364b93b574c058cd8cd617f925107985318098`,
tree `7c277e32b6419bd3720591c454e8282d94f081ec`, plus the verified
WAL-safe pre-`005` copy remains the product/data rollback target for P2.2.
P2.3 is not active.

## Next Task

Await an explicit user instruction to begin P2.3. On that instruction, freeze
the complete P2.3 result card and non-scope against accepted P2.2 before
implementing any integrated resilience or capacity-certification behavior.

Acceptance of P2.2 does not activate P2.3 or P2.4.

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

`Productization P2.3 Concurrent And Failure Isolation`.

P2.3 has not started. Only a separate explicit start instruction can activate
it. P2.4 remains queued and blocked by its external FineReport plugin gate.
