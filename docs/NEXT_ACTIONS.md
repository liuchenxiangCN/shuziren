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
the accepted runtime and rollback baseline.

P2.1 final candidate
`8f364b93b574c058cd8cd617f925107985318098`, tree
`7c277e32b6419bd3720591c454e8282d94f081ec`, fingerprint
`516995361810AF2D3F3FC609F4676D5A2D620216E6BB9DA305EDC57CD8622332`
over 36 files, implements only the frozen local development-preview result.
Its automated gates and final independent review pass. Reviewer Huygens
reported zero blocking and zero non-blocking findings. The candidate is ready
for explicit user acceptance but is not yet accepted.

## Next Task

Review the complete P2.1 result package and record one explicit user decision:
`通过`, `条件通过`, `不通过` or `Blocked`.

No additional P2.1 implementation scope is authorized while this decision is
pending. Automated success, reviewer success and user silence do not accept
P2.1 or activate P2.2.

### User-Visible Result

1. `/manage` exposes seven fixed per-screen capabilities, three immutable
   presets, 21 closed Provider descriptors and all five state meanings.
2. An implementation engineer can create a Site-owned profile and append
   immutable versions without changing an older version.
3. An exact ProfileVersion can be assigned through a new P1.3 draft revision;
   stale validation, preview and approval evidence is invalidated.
4. NORMAL release, publication, acknowledgement and forward rollback preserve
   an exact immutable per-screen capability snapshot.
5. Three screens can publish, acknowledge and resolve different profiles with
   the same correlation label without sharing screen or Provider state.
6. Unverified Providers remain inspectable but cannot validate or release, and
   no external request occurs.
7. Permission denial and cancellation are terminal; only bounded technical
   failures may use an equivalent screen-bound fallback.
8. Encrypted backup/restore preserves P2.1 rows and historical evidence, while
   accepted-P1.3 product/data rollback remains usable.

### Result Package

- [acceptance/productization/P2.1/ACCEPTANCE_CARD.md](acceptance/productization/P2.1/ACCEPTANCE_CARD.md)
- [acceptance/productization/P2.1/AUTOMATED_SUMMARY.md](acceptance/productization/P2.1/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P2.1/IMPLEMENTED_API.md](acceptance/productization/P2.1/IMPLEMENTED_API.md)
- [acceptance/productization/P2.1/IMPLEMENTED_DATA.md](acceptance/productization/P2.1/IMPLEMENTED_DATA.md)
- [acceptance/productization/P2.1/KNOWN_LIMITATIONS.md](acceptance/productization/P2.1/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P2.1/RUNBOOK.md](acceptance/productization/P2.1/RUNBOOK.md)
- [acceptance/productization/P2.1/manifest.json](acceptance/productization/P2.1/manifest.json)
- [acceptance/productization/P2.1/USER_DECISION.md](acceptance/productization/P2.1/USER_DECISION.md)

### Verified Boundary

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

P2.2 has not started. Only explicit P2.1 user acceptance followed by a
separate start instruction can activate it.
