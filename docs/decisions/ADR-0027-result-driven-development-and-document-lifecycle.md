# ADR-0027: Result-Driven Development And Document Lifecycle

## Status

Accepted

## Date

2026-07-27

## Context

The repository accumulated a complete POC history, changing next-task instructions, customer delivery material, long development logs and both target and implemented contracts in the same documentation entry path.

The user develops through Codex and reviews observable results rather than source code. A traditional component plan and informal self-review would place too much quality and recovery risk on a user who does not audit implementation details.

Before G0:

- mandatory first-read documents exceeded four thousand lines;
- current P1 instructions coexisted with old V0.x / V1.0 next steps and prompts;
- implemented POC contracts were not clearly separated from future product contracts;
- product, POC and customer risks shared one active file;
- evidence existed, but result cards, independent review and rollback proof were not mandatory.

## Decision

1. Documentation uses explicit lifecycle classes: current authority, stable policy, target not implemented, as-built POC, customer-specific, archived snapshot and acceptance evidence.
2. `CODEX_CONTEXT.md` remains a small current snapshot.
3. `NEXT_ACTIONS.md` contains exactly one active result batch.
4. Long POC and initial productization histories are preserved under `docs/archive/poc-v1/` and cannot direct current work.
5. Implemented POC API / data contracts remain separate from target product contracts under `docs/product/contracts/`.
6. P1-P5 are planned as vertical user-visible outcomes, not sequential database, backend, frontend and test phases.
7. Every result batch requires a result card, automated gates, independent Codex review, runnable evidence, known limitations and rollback proof.
8. The user records `通过`, `条件通过`, `不通过` or `Blocked` without needing to inspect source code.
9. Mock evidence proves only a flow. Real external support requires evidence from a certified real environment.
10. Cross-screen leakage, authorization bypass, Secret exposure, data corruption, permission-broadening fallback and unrecoverable change immediately fail a batch.
11. A lifecycle lint script enforces the current entry, link, contract, archive and vendor-binary boundaries.
12. The FineReport plugin ZIP stays local and cannot be tracked or redistributed.
13. Root `AGENTS.md` contains stable Codex policy only; root `README.md` contains stable product boundary and navigation only.
14. The two root files route the current snapshot to `docs/CODEX_CONTEXT.md` and the sole active batch / acceptance state to `docs/NEXT_ACTIONS.md`; they cannot duplicate either.

## Consequences

### Positive

- Codex receives one unambiguous current task.
- Historical facts remain available without becoming instructions.
- The user can approve product behavior through small scenario cards.
- Code-quality, security and recovery checks become Codex responsibilities with reproducible evidence.
- Target and implemented states are harder to confuse.
- Failure returns to a known accepted result rather than accumulating on an unstable candidate.
- Root entry files remain useful without becoming competing current-status documents.

### Trade-Offs

- Each batch carries evidence and independent-review overhead.
- A feature can appear complete but remain unaccepted until its result gate passes.
- External capabilities remain visibly blocked when a customer or vendor environment is unavailable.
- Current documentation must stay intentionally small; detailed history moves to the archive.

## Follow-Up

- G0 must pass its result card before P1.0 starts.
- P1.0 creates the target domain, data, identity, state, storage and control-plane contracts.
- Every later batch follows `docs/RESULT_ACCEPTANCE_STANDARD.md`.
- `scripts/lint-doc-lifecycle.ps1` remains part of the completion gate.
