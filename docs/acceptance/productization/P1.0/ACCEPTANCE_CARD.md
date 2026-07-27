# P1.0 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Result: target control-plane contract result pack
- Base accepted version: commit `226e2d48d0731f989c3895e4abc5237cee2b2d10`, tree `f2846576b1184fcf522151057215fb41a9efc4d0` (G0)
- Candidate: commit `d78de0cfce64777678ec606b03470d6ffd5e970f`, tree `8538a8b89b789ebac7ff436ec17c51d1fa86bb47`
- Candidate fingerprint: `8B894F9EAF0A491A3F5DA3B367B4D03DBD56C63A0470B5840E354CA06160C633` over 26 non-evidence files
- Scope: 31 changed documentation and validation-script files; runtime unchanged
- Database schema / migration: `N/A` — target design only; no runtime database or migration changed
- Gate summary: `PASS`
- User decision: `通过` on 2026-07-27

The user explicitly accepted this result on 2026-07-27 and authorized P1.1 development.

## Observable Outcome

P1.0 lets a reviewer understand, without reading runtime source code:

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
- Evidence root: `logs/productization/P1.0-20260727T064034Z`
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
   - Safe failure: missing hashes, keys or ledger anchors, in-place overwrite, or old account/password/device credential resurrection fails closed and leaves the accepted store recoverable.
7. Match API examples to the same operations.
   - Expected: separate user/device namespaces, per-request authorization, idempotency, ETags, target generations and safe errors.
   - Safe failure: client-selected ownership, missing preconditions or one idempotency key with different content is rejected.

## Frozen Non-Scope

- No runtime code, database, migration, UI or HTTP endpoint implementation.
- No modification of the implemented POC contracts.
- No FineReport plugin or Provider implementation.
- No real backup, restore, authentication or three-screen execution claim.
- No P1.1, P1.2 or P1.3 implementation.
- At candidate freeze time, ADR-0028 remained `Proposed` and P1.1 remained queued. The explicit user decision subsequently accepted ADR-0028 and released P1.1.

## Gate Results

- Machine contract and Markdown consistency on PowerShell 7 and PowerShell 5.1: `PASS` — 2,722 checks, 86 operations, 32 entities and 5 roles on each host.
- Registry consistency: `PASS` — 23 permissions, 16 state machines, 31 internal security records, 40 errors, 18 key purposes and 20 four-eyes operations.
- Contract negative-fixture self-test: `PASS` — 191 cases: 1 baseline, 166 semantic mutations on PowerShell 5.1 and 12 raw-JSON mutations on each host (24 executions).
- Documentation lifecycle on both hosts: `PASS` — 298 checks, 135 links, 108 files and 1 plugin file.
- Candidate scope and Secret scan: `PASS` — 31 changed documentation/script files, no runtime changes and 0 Secret findings.
- Independent Codex review: `PASS` — zero blocking findings; the report is hash-bound in `manifest.json`.
- Rollback proof: `PASS` — exact G0 recovery tree, both-host lifecycle result of 267 checks / 122 links / 97 files / 0 plugin files, and all P1-only paths absent.
- Lifecycle-lint self-test: `N/A` — the lifecycle lint implementation did not change.
- Runtime, database, real IAM, real three-screen, RPO/RTO, PostgreSQL and FineReport execution gates: `N/A` with reasons recorded in `manifest.json`.

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

Decision recorded: `通过` on 2026-07-27. P1.0 is the accepted rollback baseline for P1.1.
