# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`G0 Acceptance Gate`: documentation governance and result-driven P1-P5 planning are implemented and awaiting the user's result decision.

P0 product definition is complete. Product runtime remains the existing single-instance POC baseline.

## Next Task

Review the G0 result package and record `通过`, `条件通过` or `不通过`.

### User-Visible Result

G0 must demonstrate:

1. Codex has one small current context and one active task.
2. Historical POC instructions remain available but cannot direct current work.
3. Implemented POC contracts and target product contracts have separate namespaces.
4. Customer-specific fixtures and POC delivery material are visibly classified.
5. The FineReport plugin ZIP cannot enter Git.
6. P1-P5 are organized as user-visible vertical results, not sequential technical departments.
7. Every future batch requires automated gates, independent Codex review, evidence and rollback.
8. Root `AGENTS.md` and `README.md` have stable, non-overlapping responsibilities and cannot duplicate dynamic task status.

### Result Package

- [acceptance/productization/G0/ACCEPTANCE_CARD.md](acceptance/productization/G0/ACCEPTANCE_CARD.md)
- [acceptance/productization/G0/AUTOMATED_SUMMARY.md](acceptance/productization/G0/AUTOMATED_SUMMARY.md)
- [acceptance/productization/G0/KNOWN_LIMITATIONS.md](acceptance/productization/G0/KNOWN_LIMITATIONS.md)
- [acceptance/productization/G0/manifest.json](acceptance/productization/G0/manifest.json)
- [acceptance/productization/G0/USER_DECISION.md](acceptance/productization/G0/USER_DECISION.md)

### User Result Scenarios

1. Open [00_INDEX.md](00_INDEX.md) and confirm current, target, as-built, customer and archive material are separated.
2. Open this file and confirm it contains only the G0 acceptance task.
3. Open [CODEX_CONTEXT.md](CODEX_CONTEXT.md) and confirm it describes the current product without old POC next-step instructions.
4. Open [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) and confirm P1-P5 are expressed as observable results, automated gates, user scenarios and stop conditions.
5. Open [RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md) and confirm the user is not required to inspect source code.
6. Review the automated summary and known limitations.
7. Open root `AGENTS.md` and `README.md`; confirm both route the current task to this file and neither declares a phase or next batch.

### Automated Gates

- One `Current Phase` and one `Next Task` in current entry documents.
- Current context and task stay within line budgets.
- Root `AGENTS.md` and `README.md` stay within line budgets and contain no dynamic phase / task declaration.
- Root routing paths, target / as-built markers, scoped links, secret patterns and vendor-binary boundaries pass.
- Required lifecycle markers exist.
- Active Markdown links resolve.
- No stale POC next-step directive appears in current entry documents.
- Customer-specific terms do not enter current product documents.
- Implemented POC contracts carry `AS_BUILT_POC`.
- Archive snapshots carry `ARCHIVED_POC_SNAPSHOT`.
- FineReport plugin ZIP is not tracked.
- `git diff --check` passes.

### Non-Scope

- No runtime code changes.
- No target domain or API contract design.
- No management UI implementation.
- No database, FineReport plugin or Renderer implementation.
- No deletion of historical POC evidence.

### Stop Conditions

- A current entry still sends Codex to a POC phase.
- A root entry duplicates a current phase, next task or post-acceptance phase.
- Current and target contracts can be confused.
- A customer-specific document is presented as a product default.
- The plugin archive is tracked or distributed.
- The lifecycle check fails.

## Queued After G0 Acceptance

`Productization P1.0`: target domain, data, identity, configuration-release, storage / recovery and control-plane API contract result pack.

P1.0 remains contract design only. Its detailed scope and stop conditions are in [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md).
