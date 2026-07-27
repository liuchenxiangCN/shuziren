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
baseline. The P1.2 result card and non-scope are frozen. The complete local
candidate is implemented and its automated, browser, migration, Docker,
Secret-scan, P1.1 rollback and independent-review gates pass. It is ready for
explicit user result acceptance but is not accepted.

## Next Task

Present the final P1.2 result and evidence for the user's explicit result
decision against
[acceptance/productization/P1.2/ACCEPTANCE_CARD.md](acceptance/productization/P1.2/ACCEPTANCE_CARD.md).
The independent review passed with zero findings. Do not start P1.3 from that
PASS, automated success or user silence.

### User-Visible Result

1. `/manage` shows `多屏清单` with one default Site, one group and three distinct screens.
2. The accepted P1.1 fixture screen keeps its exact ID and device/audit history as Screen 1.
3. Every screen has separate non-secret FVS inventory, DigitalHumanInstance, device-trust status and RuntimeBinding.
4. Authorized administrators and implementation engineers can maintain inventory; auditors can read but cannot mutate it.
5. Updating one screen or group cannot change an unrelated screen.
6. Device runtime reads remain credential-bound and report `NOT_CONFIGURED_P1_3`.

### Result Package

- [acceptance/productization/P1.2/ACCEPTANCE_CARD.md](acceptance/productization/P1.2/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.2/USER_DECISION.md](acceptance/productization/P1.2/USER_DECISION.md)

The automated summary, implemented API/data record, limitations and
machine-readable manifest must contain only the factual final-candidate
evidence. `USER_DECISION.md` remains Pending until the user explicitly decides.

### Required Gate Families

- Empty and accepted-P1.1 migration, repeat initialization, tamper rejection and pre-migration-copy rollback.
- API/UI RBAC and resource-scope denial, including sibling non-disclosure.
- Three-screen ownership, device-family, DigitalHumanInstance, RuntimeBinding and ETag isolation.
- Idempotency mismatch, stale ETag, duplicate slug/instance and cross-Site membership negative tests.
- Database foreign-key, unique-index, immutable-audit and no-delete-cascade checks.
- Frontend build, 1280 by 720 browser workflow, Secret scan and Docker Compose smoke.
- P1 target-contract validation, lifecycle lint, evidence hashes and independent read-only review.

### Frozen Non-Scope

- No P1.3 draft, release, publication, acknowledgement, rollback or recovery implementation.
- No real FineReport/FVS connection, plugin call, compatibility certification, credential binding or Secret value.
- No QuerySource, provider, ASR/TTS, action, Renderer or AvatarPackage expansion.
- No Site mutation, screen retirement/deletion, group deletion, multi-Site promise or high-concurrency SLA.
- No production activation, external monotonic anchor, PostgreSQL certification or product backup/restore claim.
- No change to accepted POC route meanings or P1.1 identity/device-trust semantics.

### Stop Conditions

- Any ownership, identity, inventory, device or runtime state crosses screen scope.
- A one-screen mutation changes an unrelated screen or its ETag.
- Migration rewrites or loses accepted P1.1 IDs, trust state, audit history or checksum.
- Unauthorized sibling discovery/mutation, stale-write success or changed-command idempotency replay.
- A Secret enters inventory/evidence or unverified FVS/runtime state is described as connected or published.

## Queued After P1.2 Acceptance

`Productization P1.3 Publish, Rollback And Recovery`.

P1.3 remains queued until P1.2 receives an explicit user result decision.
