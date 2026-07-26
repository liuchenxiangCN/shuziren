# G0 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Candidate: working tree documentation state on 2026-07-27
- Result: documentation governance and result-driven development plan
- Candidate commit: uncommitted P0 + G0 working-tree candidate based on `8e293af1f56e5d7623b0af3dfd408e6086e736c2`
- Candidate fingerprint: recorded in `manifest.json`; acceptance evidence files are excluded to avoid a circular hash
- Base committed version: `8e293af1f56e5d7623b0af3dfd408e6086e736c2`
- Database schema / migration: `N/A` — documentation-only batch
- Rollback target: a verified recovery tree built from the base runtime, six exact pre-G0 root documents and eleven preserved P0 product-definition artifacts, including the three productized entry documents
- Rollback procedure: run `scripts/export-g0-rollback-target.ps1 -Destination <empty-directory>`, verify its proof, then switch to the exported tree through a separately approved workspace operation
- Post-restore verification: recorded in `manifest.json`; runtime data is unchanged
- User decision: Pending

## Observable Outcome

G0 changes how Codex receives instructions and how future product work is accepted:

- One small current context.
- One active task.
- Separate target and as-built contract namespaces.
- Preserved but non-executable POC history.
- Explicit customer and POC fixture classification.
- Result-driven P1-P5 roadmap.
- Mandatory automated gates, independent review, evidence and rollback.
- FineReport plugin ZIP excluded from Git.
- Stable root entries: `AGENTS.md` owns Codex policy; `README.md` owns product navigation; neither owns dynamic task status.

G0 does not change runtime code or claim a new product feature.

## User Scenarios

### Scenario 1: Find The Current Task

1. Open `docs/00_INDEX.md`.
2. Follow the Start Here list.
3. Open `docs/NEXT_ACTIONS.md`.

Expected:

- Only G0 result acceptance is active.
- P1.0 is queued, not already implemented.
- No POC phase is presented as the next task.

### Scenario 2: Distinguish Target And Implemented Contracts

1. Open `docs/06_API_CONTRACT.md` and `docs/07_DATA_CONTRACT.md`.
2. Open `docs/product/contracts/README.md`.

Expected:

- Existing contracts are marked `AS_BUILT_POC`.
- Product contracts are marked `TARGET_NOT_IMPLEMENTED`.
- Neither can be confused with the other.

### Scenario 3: Review The Development Model

1. Open `docs/05_DEVELOPMENT_PLAN.md`.
2. Review P1 through P5.
3. Open `docs/RESULT_ACCEPTANCE_STANDARD.md`.

Expected:

- Stages are vertical user outcomes, not component departments.
- Every stage lists visible results, automated gates, user scenarios and stop conditions.
- The user is not expected to review source code.

### Scenario 4: Inspect Historical Evidence

1. Open `docs/archive/poc-v1/README.md`.
2. Open one root snapshot.

Expected:

- Historical material is preserved.
- The archive banner says old Current / Next language cannot direct new work.

### Scenario 5: Verify The Plugin Boundary

1. Review `.gitignore`.
2. Review the automated summary.

Expected:

- The local FineReport plugin ZIP remains available on disk if supplied by the user.
- Git does not track it.
- Product documentation keeps only non-secret metadata and the hash.

### Scenario 6: Verify Root Entry Responsibilities

1. Open root `AGENTS.md`.
2. Open root `README.md`.
3. Search both for a declared current phase, next task or post-acceptance phase.

Expected:

- `AGENTS.md` contains stable routing, execution, evidence and safety policy.
- `README.md` contains stable product boundaries, navigation and the minimum POC run entry.
- Both point the current snapshot to `docs/CODEX_CONTEXT.md` and the sole active batch / acceptance state to `docs/NEXT_ACTIONS.md`.
- Neither duplicates a concrete phase or next-task status.

## Immediate Failure Conditions

- More than one active Current Phase or Next Task.
- A root entry declares dynamic phase or task status.
- A current entry points to V0.x / V1.0 POC work.
- Target contracts appear implemented.
- Historical evidence was lost.
- The plugin ZIP is tracked.
- The lifecycle check fails.

## Decision

Record the decision in [USER_DECISION.md](USER_DECISION.md):

- `通过`
- `条件通过`
- `不通过`
