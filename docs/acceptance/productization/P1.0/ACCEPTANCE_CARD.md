# P1.0 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_VERIFYING`
- Result: target control-plane contract result pack
- Base accepted version: `226e2d48d0731f989c3895e4abc5237cee2b2d10` (G0)
- Candidate: working-tree target-contract candidate based on `226e2d48d0731f989c3895e4abc5237cee2b2d10`; fingerprint recorded in `manifest.json`
- Database schema / migration: `N/A` — target design only; no runtime database changes
- User decision: Pending

## Observable Outcome

P1.0 will let a reviewer understand, without reading runtime source code:

- how one Site owns three isolated screens and digital-human instances;
- how control-plane users, screen devices and FineReport data identities stay separate;
- who may configure, publish, revoke, recover or audit;
- how enrollment, draft validation, preview, approval, publication and rollback change state;
- how immutable releases and targeted publications prevent cross-screen changes;
- how the target relational model enforces ownership and concurrency;
- which embedded and external stores are supported by the target design;
- what backup, restore, retention, RPO and RTO mean;
- how versioned control-plane API operations expose the same rules and safe failures.

Nothing in this result card claims those target capabilities are implemented.

## Entry Point And Test Data

- Entry point: [../../../product/contracts/README.md](../../../product/contracts/README.md)
- Machine contract: [../../../product/contracts/p1-target-contract.json](../../../product/contracts/p1-target-contract.json)
- Test data: `three_screen_fixture` in the machine contract: one reference Site, three screens, three DigitalHumanInstances and three distinct RuntimeBindings.
- Base accepted version: G0 commit `226e2d48d0731f989c3895e4abc5237cee2b2d10`.

## Frozen User Scenarios

1. Trace one Site to three independently bound screens.
   - Expected: each screen owns its device, digital-human, FineReport identity and RuntimeBinding references.
   - Safe failure: a cross-tenant, cross-site or cross-screen reference is rejected as not found.
2. Walk one device through enrollment, rotation and revocation.
   - Expected: enrollment is single-use; rotation activates a successor and revokes its predecessor; scope comes from the credential.
   - Safe failure: replay, expiry, revocation or a device-supplied screen selector cannot authenticate or commit.
3. Compare role permissions.
   - Expected: the auditor is read-only, draft field authorization requires every changed-path permission, FineReport binding requires three joint permissions and no role can reveal a stored Secret.
   - Safe failure: the API denies by default even if a UI control is visible.
4. Walk a configuration draft through validation, preview, approval and release.
   - Expected: validation, preview and approval bind one ResolutionFingerprint; release creation revalidates it and atomically creates immutable per-screen targets.
   - Safe failure: stale ETags, skipped states, changed membership/inheritance and changes after approval are rejected.
5. Publish only screen 2 and then roll it back.
   - Expected: different-user production approval binds the exact command; only screen 2's desired target changes; applied changes only after its device acknowledgement; rollback creates a new release.
   - Safe failure: screens 1 and 3 remain unchanged, and no historical release can be edited.
6. Review backup and restore.
   - Expected: hourly separate-mount encrypted bundles target one-hour RPO / two-hour RTO; restore stages, verifies, checks an independently anchored RecoverySecurityLedger and reconciles security before completion.
   - Safe failure: missing hashes/keys/ledger anchor, in-place overwrite or old account/password/device credential resurrection fails closed and leaves the accepted store recoverable.
7. Match API examples to the same operations.
   - Expected: separate user/device namespaces, per-request authorization, idempotency, ETags, target generations and safe errors.
   - Safe failure: client-selected ownership, missing preconditions or one idempotency key with different content is rejected.

## Frozen Non-Scope

- No runtime code, database, migration, UI or HTTP endpoint implementation.
- No modification of the implemented POC contracts.
- No FineReport plugin or Provider implementation.
- No real backup, restore, authentication or three-screen execution claim.
- No P1.1, P1.2 or P1.3 implementation.

## Required Gates

Current candidate gates:

- Contract and machine-artifact validation: `PASS`.
- Domain / data / identity consistency: `PASS`.
- RBAC and Secret negative fixtures: `PASS`.
- Enrollment and release state-machine negative fixtures: `PASS`.
- Three-screen targeting and immutable-release fixtures: `PASS`.
- Storage / recovery decision completeness: `PASS` for design; real recovery is `N/A` in this design-only batch.
- Documentation lifecycle and diff checks: `PASS`.
- Independent Codex review: in progress; final result is recorded in `manifest.json`.
- Rollback proof to the accepted G0 version: in progress; final result is recorded in `manifest.json`.

## Immediate Failure Conditions

- Target design is presented as implemented behavior.
- Identities or screen ownership can cross boundaries.
- Published releases are mutable.
- Authorization is only a UI concern.
- Plaintext Secret values enter responses, audit details or backup manifests.
- Backup or restore cannot identify an integrity failure.
- Production high-risk execution can self-approve, use a free-form action or reuse approval across a changed request.
- Restore can roll account state, password generation or device credential generation backward.
- A required P1 storage or IAM decision remains unresolved.

## Decision

After verification, record `通过`, `条件通过`, `不通过` or `Blocked` in `USER_DECISION.md`.
