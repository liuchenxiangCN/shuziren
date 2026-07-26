# AGENTS.md

## Purpose And Authority

This file contains stable repository instructions for Codex. It must not declare the current phase, next task, implementation status or customer-specific objective.

`docs/CODEX_CONTEXT.md` provides the small current snapshot. The active result batch and its acceptance state come only from `docs/NEXT_ACTIONS.md`. Product truth, implemented POC truth and historical evidence remain separate according to `docs/DOCUMENT_GOVERNANCE.md`.

## Required Routing

Before starting scoped work, read:

1. `docs/00_INDEX.md` — document router and lifecycle map
2. `docs/CODEX_CONTEXT.md` — small current product and execution snapshot
3. `docs/NEXT_ACTIONS.md` — the only active result batch
4. `docs/13_RISKS_AND_TODO.md` — active risks and blockers
5. `docs/RESULT_ACCEPTANCE_STANDARD.md` — evidence and decision rules

Use only the task declared by `docs/NEXT_ACTIONS.md`. A queued phase, archived prompt, roadmap item or target design does not authorize implementation.

## Scope-Based Reading

Read additional material only when the task needs it:

| Task Scope | Additional Source |
| --- | --- |
| Product behavior, domain model, scope or acceptance | `docs/17_STANDARD_PRODUCT_DESIGN.md` |
| Phase composition or roadmap change | `docs/05_DEVELOPMENT_PLAN.md` |
| Implemented API or shared data change | `docs/06_API_CONTRACT.md` and `docs/07_DATA_CONTRACT.md` |
| Target product contract design | the applicable file under `docs/product/contracts/` |
| External system | only the relevant file under `docs/integrations/` |
| Customer delivery | `docs/customers/README.md` and only the target `docs/customers/<customer-id>/` |
| Archived POC handoff | `docs/12_CUSTOMER_HANDOFF.md` and the specifically referenced archive |
| Recent factual history | the relevant entry in `docs/DEV_LOG.md` |

Do not load a whole integration, customer or archive directory when one routed document is sufficient.

## Result-Driven Execution

- Deliver one independently usable vertical result batch at a time.
- Freeze its result card and non-scope before implementation.
- The user reviews observable behavior and business outcomes, not source code.
- Codex owns implementation quality, automated gates, negative tests, independent review, evidence and rollback preparation.
- Automated success alone is insufficient; the result also needs independent review and an explicit user decision.
- User silence is never acceptance.
- Do not advance a queued batch until the active batch is explicitly accepted.
- Keep the latest accepted version recoverable.

## State And Evidence Rules

- Never describe `TARGET_NOT_IMPLEMENTED` content as implemented.
- `AS_BUILT_POC` documents describe only the existing POC baseline.
- `Mock Passed` proves only the product flow; missing real-provider evidence remains `Blocked`.
- Unverified FineReport, FVS, plugin, database, browser or renderer combinations remain `Unverified` or `Unsupported`.
- Every gate is recorded as `PASS`, `FAIL`, `Blocked` or `N/A`; `N/A` requires a reason.
- A blocking independent-review finding prevents user acceptance.

## Safety Boundaries

- Keep Mock switches for Dora, ASR, TTS and FVS.
- Never expose API keys, tokens, passwords, DSNs or Secrets in frontend code, logs, evidence or support packages.
- Screen control uses `action_id` plus backend whitelist and parameter-schema validation.
- Never execute model-generated JavaScript, SQL, Python, shell or other executable code.
- Database querying uses predefined parameterized read-only datasets; users and models cannot submit free SQL.
- Permission denial must never fall back to a more privileged source.
- Customer-specific content stays in customer configuration and customer documentation.
- Vendor plugins and licensed archives never enter Git, product packages, images or public source archives.
- Cross-screen leakage, authorization bypass, Secret exposure, data corruption or unrecoverable change immediately fails the batch.

## Documentation Synchronization

Update only documents whose facts changed:

- Always update the active acceptance package and record factual completion in `docs/DEV_LOG.md`.
- Update `docs/NEXT_ACTIONS.md` only when the active batch or its acceptance state changes.
- Update `docs/CHANGELOG.md` only for user-visible, operational or delivery-facing changes.
- Update `docs/13_RISKS_AND_TODO.md` only when a risk, limit or blocker changes.
- Add or update an ADR when architecture, security or process decisions change.
- Update the applicable as-built or target contract when an API or shared structure changes; never merge the two states.
- Archive historical detail instead of expanding current entry documents indefinitely.

`README.md` is a stable product and navigation entry. It must not duplicate the current phase or next task.

## Completion Gate

Before finalizing a batch:

- Confirm the result card stayed within scope.
- Run the proportional automated gates and required negative tests.
- Obtain an independent Codex review.
- Record the runnable result, known limitations, evidence hashes and rollback result.
- Synchronize only affected authoritative documents.
- Confirm `docs/NEXT_ACTIONS.md` remains the sole active-task source.
- Run `scripts/lint-doc-lifecycle.ps1`.
- If the lifecycle lint changed, also run `scripts/test-doc-lifecycle-lint.ps1`.
