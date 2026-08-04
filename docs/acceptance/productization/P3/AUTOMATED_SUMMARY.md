# P3 Automated Summary

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: IN_PROGRESS
- Candidate commit: TBD
- Candidate tree: TBD
- Automated gates: IN_PROGRESS
- Independent review: pending
- User decision: pending

## Verified Results So Far

- The backend implements a fixed test_card Renderer registry, immutable
  declarative AvatarPackage versions, strict resource validation, preview,
  exact-hash prefetch, per-screen atomic publication, rollback and a
  device-scoped current binding.
- Dedicated backend tests cover the full two-version, multi-screen lifecycle,
  unsafe resources, ownership, optimistic concurrency, failed-hash retention,
  device isolation, migration and encrypted backup/restore.
- The frontend TypeScript/Vite build passes and the management UI exposes a
  clearly marked TEST_ONLY workflow.
- A fresh 1280 by 720 browser run passed corrupted-hash retention, correct
  prefetch, atomic switch and rollback. Document width equaled client width
  and the captured browser warning/error list was empty.
- The P3 machine contract passes 85 checks and its mutation self-test rejects
  eight unsafe or incomplete fixtures.

Final candidate hashes, complete regression, Compose, secret scan, rollback
worktree and independent-review results will be bound here before the user is
asked for an acceptance decision.
