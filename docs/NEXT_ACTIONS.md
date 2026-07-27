# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.2 Three-Screen Inventory`.

G0, P1.0 and P1.1 were explicitly accepted on 2026-07-27. Accepted
P1.1 candidate `8c18e5d6b10081eaaf608436440046894d235d46`, tree
`9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`, is the runtime rollback
baseline. P1.2 inventory behavior is not implemented.

## Next Task

Freeze the P1.2 result card and non-scope against the accepted P1.1 baseline.
This task is documentation and acceptance-boundary work only. Runtime,
database, API and UI implementation must not start until the result card is
frozen and `NEXT_ACTIONS.md` is updated to name that implementation task.

### Result Card Must Resolve

1. The exact default Site, ScreenGroup and minimum three-screen fixture.
2. The inventory fields and lifecycle exposed for each ScreenInstance.
3. The per-screen DigitalHumanInstance and runtime-status boundary.
4. Create, update, list and read permissions plus idempotency and ETag behavior.
5. Migration from the accepted P1.1 trust-only screen fixture without losing its device-family history.
6. Observable three-screen isolation scenarios and understandable failure behavior.
7. Automated, browser, migration, rollback and independent-review gates.

### Intended User-Visible Result

- The management UI shows one Site, screen groups and at least three screens.
- Each screen has its own non-secret FVS reference, DigitalHumanInstance and runtime status.
- Authorized users can inspect and maintain inventory through the accepted P1.1 identity and audit boundary.
- Changing one screen or group does not change an unrelated screen.

### Required Gate Families

- Empty and accepted-P1.1 database migration, repeat initialization and rollback.
- API and UI RBAC denial for unauthorized roles and ownership scopes.
- Three-screen identity, inventory, device-family and runtime-status isolation.
- Idempotency, strong ETag and stale-write rejection.
- Database uniqueness, foreign-key and composite-ownership enforcement.
- Frontend build and browser workflow at the supported preview size.
- Secret and sensitive-data scan of APIs, bundles, database, logs and evidence.
- P1 target-contract validation, lifecycle lint and independent read-only review.

### Frozen Non-Scope Direction

- No ConfigDraft, ConfigRelease, publication, rollback or recovery implementation; those remain P1.3.
- No FineReport plugin call, FineReport credential value, Secret value, QuerySource, Dora, ASR, TTS, FVS control or Renderer expansion.
- No multi-customer shared database, multi-Site delivery promise or high-concurrency SLA.
- No production activation, custodian ceremony, external monotonic anchor or PostgreSQL certification claim.
- No change to accepted POC route meanings or accepted P1.1 identity/device-trust semantics.

### Stop Conditions

- A screen, group, device family, DigitalHumanInstance or runtime status can cross tenant, deployment, Site or screen scope.
- Changing one screen mutates another screen or its accepted P1.1 trust history.
- A migration loses or silently relabels accepted P1.1 device or audit history.
- Missing or stale ETag succeeds, an idempotency key accepts a changed command, or unauthorized inventory access succeeds.
- FVS or production readiness is described as verified without its external evidence.

## Queued After P1.2 Acceptance

`Productization P1.3 Publish, Rollback And Recovery`.

P1.3 remains queued until P1.2 receives an explicit user result decision.
