# Document Governance

## Document Status

- Lifecycle: `AUTHORITATIVE_POLICY`
- Scope: documentation lifecycle, truth precedence and archive rules
- Last reviewed: 2026-07-27

## Purpose

The documentation system must help Codex identify the current product, implemented baseline, single active task and acceptance boundary without reading historical instructions as current work.

Historical evidence is retained. Obsolete instructions are archived or explicitly marked, not silently rewritten into current truth.

## Lifecycle Classes

| Lifecycle | Meaning | May Direct Current Work |
| --- | --- | --- |
| `AUTHORITATIVE_CURRENT` | Current phase, current task or current product truth | Yes |
| `AUTHORITATIVE_POLICY` | Stable execution, security or governance rule | Yes |
| `TARGET_NOT_IMPLEMENTED` | Reviewed target design that is not yet implemented | Only within its active phase |
| `AS_BUILT_POC` | Contract or architecture describing the existing POC | Only when changing existing POC behavior |
| `CUSTOMER_SPECIFIC` | Customer configuration, fixtures, delivery or acceptance material | Only for that customer |
| `ARCHIVED_POC_SNAPSHOT` | Immutable historical evidence | No |
| `ACCEPTANCE_EVIDENCE` | Result card, verification summary and user decision | No new scope |

## Truth Precedence

When documents conflict, use this order:

1. Accepted current ADRs and non-negotiable repository rules.
2. `17_STANDARD_PRODUCT_DESIGN.md` for target product boundaries.
3. Reviewed target contracts under `docs/product/contracts/`.
4. `06_API_CONTRACT.md` and `07_DATA_CONTRACT.md` for implemented POC behavior only.
5. `NEXT_ACTIONS.md` for the single active result batch.
6. Historical snapshots only as evidence of what happened at that time.

Historical text such as “current”, “next”, “recommended prompt” or “acceptance draft” never overrides an authoritative current document.

## Active-Document Responsibilities

| Document | Single Responsibility |
| --- | --- |
| root `AGENTS.md` | Stable Codex routing, execution and safety policy; never phase or task status |
| root `README.md` | Stable product boundary, document navigation and POC run entry; never phase or task status |
| `CODEX_CONTEXT.md` | Small current snapshot and immutable boundaries |
| `NEXT_ACTIONS.md` | One active result batch |
| `17_STANDARD_PRODUCT_DESIGN.md` | Target product design |
| `05_DEVELOPMENT_PLAN.md` | Result-driven P1-P5 roadmap |
| `13_RISKS_AND_TODO.md` | Active product risks and current blockers |
| `DEV_LOG.md` | Factual productization work completed after G0 |
| `CHANGELOG.md` | Productization release-facing changes |
| `RESULT_ACCEPTANCE_STANDARD.md` | Result-card and evidence rules |

## Size Budgets

- Root `AGENTS.md`: no more than 120 lines.
- Root `README.md`: no more than 80 lines.
- `CODEX_CONTEXT.md`: no more than 100 lines.
- `NEXT_ACTIONS.md`: no more than 120 lines.
- Current risk file: active product risks only.
- Historical task transcripts, old prompts and completed acceptance drafts belong in the archive.
- `DEV_LOG.md` is rolled into a dated archive before it becomes a mandatory long-form history.

## Root Entry Rules

- `AGENTS.md` contains stable repository policy and scope-based reading routes.
- `README.md` introduces the product, distinguishes target from as-built behavior, routes readers and provides the minimum POC run entry.
- Neither root file declares or paraphrases the current phase, next task, post-acceptance phase or historical completion timeline.
- Both route the current snapshot to `docs/CODEX_CONTEXT.md` and the sole active batch / acceptance state to `docs/NEXT_ACTIONS.md`; README routes scoped customer and integration material through indexes.
- Root paths, links, target / as-built markers, high-confidence secret patterns and vendor-binary references are automated gates.

## Archive Rules

- Archive before deleting material that contains a decision, test result, environment fact or customer acceptance record.
- Preserve ADR paths whenever practical; use ADR status to supersede decisions.
- Archived snapshots are immutable except for a lifecycle banner or broken-link repair.
- Archived “next task” text is historical and must never be copied into the current task.
- Customer-specific material remains under `docs/customers/<customer-id>/` or is explicitly classified as a POC fixture.

## Contract Namespace

- Existing `06_API_CONTRACT.md` and `07_DATA_CONTRACT.md` are `AS_BUILT_POC`.
- P1 target product contracts live under `docs/product/contracts/`.
- Target contracts do not replace as-built contracts until implementation and migration are accepted.
- A document must never claim an API or data structure is implemented merely because it appears in a target contract.

## Binary And Secret Rules

- Vendor plugins, licensed archives, keys and customer secrets do not belong in tracked documentation.
- The FineReport plugin ZIP is local vendor evidence only. Git, images, installers and public source archives must exclude it.
- Documentation may keep a verified hash and non-secret metadata.

## Automated Governance

Run:

```powershell
scripts/lint-doc-lifecycle.ps1
```

The check enforces root and current-document budgets, stable root-entry responsibilities, dynamically discovered lifecycle and archive markers, unique current-task declarations, Markdown and root-policy path validity, absence of stale POC directives, customer isolation, target / as-built separation, high-confidence root secret checks, strict UTF-8 / whitespace checks, staged and unstaged diff checks, and vendor-binary plus FineReport plugin path, hash, tracking and ignore boundaries.

When the lint implementation changes, also run:

```powershell
scripts/test-doc-lifecycle-lint.ps1
```

The self-test injects isolated temporary violations and proves that the lint rejects them.

## Change Protocol

1. Update the authoritative source, not every historical copy.
2. Update `NEXT_ACTIONS.md` only when the active result batch changes.
3. Record factual completion in `DEV_LOG.md`.
4. Update `CHANGELOG.md` for user-visible or delivery-facing change.
5. Update risks only when probability, impact, mitigation or status changes.
6. Archive the previous current snapshot when a document becomes too large or changes responsibility.
