# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-28
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P2.1 Accepted; P2.2 Awaiting Explicit Activation`.

G0 and P1.0 through P2.1 are explicitly accepted. P2.1 candidate
`8f364b93b574c058cd8cd617f925107985318098`, tree
`7c277e32b6419bd3720591c454e8282d94f081ec`, fingerprint
`516995361810AF2D3F3FC609F4676D5A2D620216E6BB9DA305EDC57CD8622332`
over 36 files, schema `p1_control_plane_001` with migration
`004_capability_profiles`, is the accepted runtime baseline. Its automated
gates and final independent review pass; reviewer Huygens reported zero
blocking and zero non-blocking findings.

Accepted P1.3 candidate `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`,
tree `04bcbb940fbedb5fbb8957e538f46a4422e15db2`, remains the verified
product-code and pre-`004` data rollback target. P2.2 is not active.

## Next Task

Await an explicit user instruction to begin P2.2. On that instruction, freeze
the complete P2.2 result card and non-scope against accepted P2.1 before
implementing any QuerySource, dataset or Excel/database execution behavior.

Acceptance and publication of P2.1 do not activate P2.2.

### Accepted P2.1 Baseline

- [acceptance/productization/P2.1/ACCEPTANCE_CARD.md](acceptance/productization/P2.1/ACCEPTANCE_CARD.md)
- [acceptance/productization/P2.1/AUTOMATED_SUMMARY.md](acceptance/productization/P2.1/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P2.1/KNOWN_LIMITATIONS.md](acceptance/productization/P2.1/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P2.1/RUNBOOK.md](acceptance/productization/P2.1/RUNBOOK.md)
- [acceptance/productization/P2.1/manifest.json](acceptance/productization/P2.1/manifest.json)
- [acceptance/productization/P2.1/USER_DECISION.md](acceptance/productization/P2.1/USER_DECISION.md)

### Accepted Boundary

- Migration `004_capability_profiles` is additive; accepted P1.3 tables and the
  exact two-field `p1_screen_config_v1` base schema remain unchanged.
- Browser evidence is an explicit semantic rebind from the earlier interactive
  candidate because the UI/API-client/fixture inputs are byte-identical; the
  final interactive workflow was not rerun.
- All real Providers and the FineReport official plugin remain `unverified`;
  Mock/local evidence does not establish compatibility or production support.
- No QuerySource, Excel/database execution, free SQL, real Provider call,
  executable action, production activation or customer certification is part
  of P2.1.

## Queued

`Productization P2.2 Controlled Excel And Database Querying`.

P2.2 has not started. Only a separate explicit start instruction can activate
it.
