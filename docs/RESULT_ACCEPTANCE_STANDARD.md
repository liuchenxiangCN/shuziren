# Result Acceptance Standard

## Document Status

- Lifecycle: `AUTHORITATIVE_POLICY`
- Scope: Codex-driven development for a user who reviews results rather than source code
- Last reviewed: 2026-07-27

## Core Principle

Development is organized around independently usable vertical results, not sequential frontend, backend, database and test departments.

The user reviews observable behavior and business outcomes. Codex owns implementation, automated verification, independent review, evidence collection and rollback preparation.

## Fixed Batch Loop

Every result batch follows the same loop:

1. Freeze a result card before implementation.
2. Implement one vertical result only.
3. Run functional, security, isolation, migration and rollback gates.
4. Ask an independent Codex reviewer that did not implement the batch to perform negative testing and evidence review.
5. Prepare a runnable preview plus screenshots or recordings.
6. Give the user three to eight result scenarios.
7. Record `通过`, `条件通过`, `不通过` or `Blocked`.
8. Keep or restore the most recent accepted version.

## Result Card

Each result card contains:

- Candidate commit and, when applicable, image or package digest.
- Base accepted version to restore.
- Database schema and migration version when data changes.
- User-visible outcome.
- Entry point and test data.
- Three to eight user actions.
- Expected outcome and understandable failure behavior for every action.
- Explicit non-scope.
- Every automated gate marked `Pass`, `Fail`, `Blocked` or `N/A`; `N/A` requires a reason.
- Independent-review task ID, reviewer identity and conclusion.
- Known limitations.
- Rollback target, command or procedure, and post-restore verification result.
- User decision.

The user is not required to inspect a diff, source file, database migration or test implementation.

## Required Automated Gates

Apply gates in proportion to the batch:

- Build, type, syntax and contract validation.
- Unit, integration and browser end-to-end tests.
- UI and API authorization negative tests.
- Cross-screen configuration, session, identity and data isolation.
- Secret and sensitive-data scans of APIs, frontend bundles, logs and support packages.
- Database migration, backup and restore verification.
- Read-only dataset, parameter binding, SQL injection and permission-equivalent fallback tests.
- Provider timeout, cancellation, backpressure and single-provider failure isolation.
- Three-screen concurrent correctness.
- Package hash, dependency, license and vulnerability checks before delivery.

An automated pass is necessary but not sufficient; user-visible scenarios and independent review are also required.

## External And Mock Semantics

- `Mock Passed` proves only the product flow.
- A real provider is `Passed` only with evidence from a supported real environment.
- Missing customer or vendor conditions are `Blocked`, never silently converted to `Passed`.
- Uncertified version combinations display `Unverified` or `Unsupported`.
- The FineReport official plugin remains disabled until its P2 entry gate passes.

## Independent Review

The implementing Codex task cannot be the only reviewer. A separate read-only review must check:

- Result-card scope was not expanded.
- Target behavior is not described as already implemented.
- Security and permission failure paths.
- Cross-screen and cross-role isolation.
- Evidence matches the candidate version.
- Known limitations and blocked external dependencies are visible.

The independent reviewer must rerun the critical negative tests from the candidate where possible, not merely read the implementer's summary. A blocking independent-review finding prevents the result from being presented for user acceptance.

## Evidence Package

Use:

```text
docs/acceptance/productization/<batch>/
├─ ACCEPTANCE_CARD.md
├─ AUTOMATED_SUMMARY.md
├─ KNOWN_LIMITATIONS.md
├─ manifest.json
└─ USER_DECISION.md

logs/productization/<batch>-<timestamp>/
├─ manifest.json
├─ test-results/
├─ screenshots/
├─ recordings/
├─ security/
├─ migration/
└─ rollback/
```

Raw evidence must be sanitized and hashed. Documentation conclusions must identify the candidate version and trace back to raw evidence.

Automated gates must also emit the tracked machine-readable `manifest.json` that records candidate identifiers, gate statuses, evidence hashes, schema / migration version and rollback verification. Markdown is a readable summary, not the only record. Large or sensitive raw evidence remains outside Git under `logs/` and is referenced only by sanitized hashes.

## Decision Rules

| Decision | Meaning |
| --- | --- |
| `通过` | Core outcomes and security gates pass; rollback is proven |
| `条件通过` | Only non-core issues remain, with a documented workaround and follow-up |
| `不通过` | A core scenario or required gate fails |
| `Blocked` | A customer, vendor or environment dependency prevents real verification |

User silence, inactivity or lack of objection is never acceptance. `USER_DECISION.md` records only an explicit user decision, its date and the task or conversation reference in which it was given.

`条件通过` cannot waive security, authorization, cross-screen isolation, data integrity, migration / restore, rollback or required external gates. Removing a promised result batch from a phase requires explicit user approval; Codex cannot silently reduce the accepted scope.

## Immediate Failure Conditions

- Cross-screen data, configuration or identity leakage.
- Authorization bypass at either UI or API.
- Secret exposure.
- Data corruption or an unrecoverable migration.
- Published configuration mutated in place.
- Permission denial falling back to a more privileged source.
- Free SQL or model-generated executable code.
- Unverified external capability presented as supported.

When any immediate failure occurs, preserve the evidence, restore the latest accepted version and open a separate repair batch.
