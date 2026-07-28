# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-28
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P2.2 Candidate Preparation`.

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
pre-`004` data rollback target.

The user explicitly activated P2.2 with `完成P2.2` on 2026-07-28. Its result
card and non-scope are frozen against accepted P2.1 in
[acceptance/productization/P2.2/ACCEPTANCE_CARD.md](acceptance/productization/P2.2/ACCEPTANCE_CARD.md).
Implementation, proportional automated gates, three exact ephemeral database
adapters and a fresh 1280 by 720 browser workflow pass. The first immutable
candidate was rejected by independent review and is not presentable; its SQL,
OOXML, queued-cancel, authority-race, timeout, three-screen, recovery, audit
and negative-coverage findings were repaired and re-tested. Replacement
candidate `78b5af301a1c57915a4535d3decc11c59b79eba7` was then rejected for
Oracle sequence expressions, PostgreSQL custom operators and user-defined
casts that escaped the closed SQL grammar. Those final SQL expression families
are now rejected with cross-dialect regression coverage. A new immutable
candidate binding and exact independent re-review remain before presentation;
P2.2 is not accepted.

## Next Task

Freeze the exact P2.2 candidate, obtain the required independent review,
complete its evidence hashes/rollback record and present it for an explicit
user decision.

Do not start P2.3 or P2.4 and do not interpret implementation completion,
automated success or user silence as acceptance.

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

## Active Acceptance Package

- [acceptance/productization/P2.2/ACCEPTANCE_CARD.md](acceptance/productization/P2.2/ACCEPTANCE_CARD.md)
- [acceptance/productization/P2.2/AUTOMATED_SUMMARY.md](acceptance/productization/P2.2/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P2.2/KNOWN_LIMITATIONS.md](acceptance/productization/P2.2/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P2.2/RUNBOOK.md](acceptance/productization/P2.2/RUNBOOK.md)
- [acceptance/productization/P2.2/USER_DECISION.md](acceptance/productization/P2.2/USER_DECISION.md)
- [product/contracts/CONTROLLED_QUERYING.md](product/contracts/CONTROLLED_QUERYING.md)

P2.3 and P2.4 remain queued/inactive.
