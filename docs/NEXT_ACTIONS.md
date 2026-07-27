# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.3 Publish, Rollback And Recovery`.

G0, P1.0, P1.1 and P1.2 were explicitly accepted on 2026-07-27. Accepted P1.2
runtime candidate `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree
`565dbb3567e2a4ae5b872177d97449120477fe8c`, schema
`p1_control_plane_001` with migration `002_three_screen_inventory`, is the
rollback baseline. The user explicitly activated P1.3 on 2026-07-27. Its result
card and non-scope are frozen; implementation has not started.

## Next Task

Implement the complete vertical P1.3 result exactly as frozen in
[acceptance/productization/P1.3/ACCEPTANCE_CARD.md](acceptance/productization/P1.3/ACCEPTANCE_CARD.md).

Start with the checksummed `003_publish_rollback_recovery` migration and
accepted-P1.2 copied-database upgrade gates. Then implement the draft/release,
publication/device acknowledgement, forward rollback, encrypted online-source
backup/restore, three-day runtime-detail retention, management preview,
evidence, rollback proof and independent review. Do not split the batch into
separately accepted backend/frontend/recovery tasks.

### User-Visible Result

1. `/manage` can create, validate and Mock-preview a screen- or group-targeted
   configuration draft.
2. A different authorized administrator approves the exact preview and an
   immutable normal ConfigRelease is created.
3. Publishing one screen changes only that screen's desired release; a
   credential-bound exact acknowledgement changes only its applied release.
4. Group publication freezes and reports every target independently.
5. Differences and append-only audit history are visible.
6. Rollback creates and publishes a new immutable release without changing
   either historical source.
7. An encrypted logical backup can be verified and restored into a staged store;
   all three bindings recover while newer live user/role/device security state
   remains authoritative and the pre-restore store is retained.
8. Runtime conversation detail defaults to three-day retention without deleting
   users, device history, releases, publications or security audit.

### Result Package

- [acceptance/productization/P1.3/ACCEPTANCE_CARD.md](acceptance/productization/P1.3/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.3/USER_DECISION.md](acceptance/productization/P1.3/USER_DECISION.md)

The automated summary, implemented API/data record, limitations and
machine-readable manifest are created only when factual candidate evidence
exists.

### Required Gate Families

- Empty and accepted-P1.2 migration, repeat initialization, tamper rejection and
  verified pre-`003` rollback copy.
- Draft state-machine, field-level RBAC, approval separation, ETag/fingerprint
  and changed-command replay negatives.
- Immutable release/provenance/content-hash and exact target-set constraints.
- Three-screen single/group publication, device fetch/acknowledgement and
  rollback isolation snapshots.
- Wrong-screen/revoked/stale device, group membership, generation, hash and
  historical-source negatives.
- Encrypted bundle, wrong-key/tamper, online SQLite snapshot, logical export,
  staged restore, session/action/replay invalidation and live security-state
  reconciliation.
- Three-day runtime-detail cleanup with explicit non-deletion proof for users,
  releases, publications, device history and SecurityAuditEvent rows.
- Frontend build, 1280 by 720 browser workflow, Secret scan and Docker Compose
  smoke.
- P1 target-contract validation, lifecycle lint, evidence hashes and separate
  read-only independent review.
- Product-code rollback to accepted P1.2 plus its verified pre-`003` database
  copy.

### Frozen Non-Scope

- No real FineReport/FVS/plugin call, certification, credential/session binding
  or permission-inheritance claim.
- No Secret, QuerySource, provider, ASR/TTS, action, Renderer or AvatarPackage
  expansion.
- No production bootstrap/activation, HumanOperatorIdentity/custodian ceremony,
  external RecoverySecurityLedger/WORM/OperationalFence, offline/full-loss
  recovery or cryptographic-root recovery.
- No PostgreSQL control-plane certification, automatic hourly scheduler,
  production backup mount certification or customer RPO/RTO claim.
- No Site mutation, screen/group deletion, cross-Site move, multi-Site promise
  or high-concurrency SLA.
- No change to accepted POC route meanings or P1.1/P1.2 identity, device-trust,
  inventory, ownership and audit semantics.

### Stop Conditions

- Any draft/release/publication/rollback/acknowledgement/restore crosses an
  ownership or screen boundary.
- A single-screen operation changes a sibling or applied state changes before
  exact credential-bound acknowledgement.
- Immutable history changes, or stale ETag/generation/fingerprint/approval/hash,
  changed replay or wrong-screen rollback succeeds.
- Backup verification can be bypassed, failed restore loses the active store,
  or restore revives an older session, device credential, role or approval.
- Three-day cleanup removes protected identity/release/security evidence.
- A Secret or key enters a read surface or Mock/unverified capability is
  presented as real, production-ready or customer-certified.

## Queued After P1.3 Acceptance

`Productization P2.1 Capability Profiles`.

P2.1 remains queued until P1.3 receives an explicit user result decision.
