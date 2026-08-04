# Codex Context

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard product target and current execution state
- Last reviewed: 2026-08-04
- Historical context: [archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md)

## Product

This repository is productizing the existing local POC into a privately deployed, single-site, multi-screen conversational digital-human management platform for customers that already own FineReport and use FVS to build large screens.

The product reuses customer FineReport / FVS assets. It adds per-screen digital-human configuration, capability orchestration, controlled querying and screen actions, versioned publishing, monitoring, audit, backup and recovery.

## Execution Snapshot

Current phase: `Productization P3 Active — Candidate Ready For User Decision; P2.4 Deferred And Blocked By External Gate`.
G0 and P1.0 through P2.3 are explicitly accepted. P1.1 proves local
identity/device trust, P1.2 three-screen inventory, P1.3 draft/release/recovery,
P2.1 per-screen capability profiles and P2.2 controlled querying. Accepted
P2.3 candidate `a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
`8a2f4e36ca0751b6106a174f7dae63be9299ad5b`, certifies three-screen concurrent
correctness, failure isolation, equivalent fallback versus terminal
no-fallback, bounded backpressure and deployment-local capacity without a
schema migration. Its gates passed and the user accepted it without
conditions on 2026-07-29. The user activated P3 on 2026-08-04. Candidate
`0b37f7c0917441543735c0b4a08d15e27a27f98c`, tree
`48498864ea4c87e11e035b5439478d6c9b610046`, verifies the test-only Renderer /
AvatarPackage safe-switching result; all automated and independent-review
gates pass with zero blocking findings. It requires explicit user acceptance.
P2.4 remains blocked and in product scope.

## Frozen Product Boundaries

- Target FineReport / FVS range: major version 11.0 and later; actual support is limited to certified exact version combinations.
- Standard deployment: one customer, one Site, multiple screens; Site remains in the model for future expansion.
- No license-coded screen or session cap; the first correctness baseline is three concurrent screens, without a high-concurrency SLA.
- 2D / 3D V1 scope: Renderer / AvatarPackage interfaces and a test renderer only.
- Identity: built-in local users and RBAC; no AD / LDAP / OIDC in V1.
- Runtime logs and session details: three days by default and configurable; an external database has no product-enforced retention ceiling.
- Database querying: MySQL, Oracle and PostgreSQL through controlled read-only datasets; Excel remains supported.
- FineReport official plugin: installed and licensed by the customer; this product never redistributes it.
- Plugin API, authentication, session, permission inheritance and upgrade stability remain a P2 external gate.

## Current As-Built Baseline

The accepted runtime baseline is P2.3 commit
`a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
`8a2f4e36ca0751b6106a174f7dae63be9299ad5b`. It retains the original POC route
meanings and accepted P1/P2.1/P2.2 controls, then adds screen-bound
metadata-only execution listing, queue-status observability, an audited
in-process resilience drill over the accepted fallback contract and a
reproducible deployment-local capacity harness. Accepted P2.2 commit
`a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
`aaa499de416b522e21c02f41119024296fc2c3a0`, remains the P2.3 product rollback
target with no data reversal required. External Providers and FVS remain
`UNVERIFIED`, and production readiness is not claimed.

The unaccepted P3 candidate adds forward-only migration
`006_renderer_avatar_packages`; its product-code rollback target is accepted
P2.3 serving a verified pre-P3 database while P3 data is retained for forward
restoration.

Implemented POC contracts remain authoritative for the original POC namespaces:

- [06_API_CONTRACT.md](06_API_CONTRACT.md)
- [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md)

Accepted behavior is recorded under [acceptance/productization](acceptance/productization).
P2.1/P2.2 target boundaries remain under [product/contracts](product/contracts);
the accepted P2.2 facts and limitations are under
[acceptance/productization/P2.2](acceptance/productization/P2.2). P3 is active with its result card frozen at [acceptance/productization/P3/ACCEPTANCE_CARD.md](acceptance/productization/P3/ACCEPTANCE_CARD.md).

## Non-Negotiable Rules

- Do not describe target product capabilities as implemented.
- Keep Mock switches for Dora, ASR, TTS and FVS.
- Never expose API keys, tokens, passwords or DSNs in frontend code or ordinary configuration output.
- Screen control always uses `action_id` plus backend whitelist and parameter-schema validation.
- Never execute model-generated JavaScript, SQL, Python or shell.
- Database querying uses predefined parameterized read-only datasets; users and models cannot submit free SQL.
- A permission denial must never fall back to a more privileged provider.
- Customer-specific content stays under customer configuration and customer documentation.
- The FineReport plugin archive must not enter Git, product packages, images or public source archives.

## Required Reading

For every task, read [NEXT_ACTIONS.md](NEXT_ACTIONS.md),
[13_RISKS_AND_TODO.md](13_RISKS_AND_TODO.md) and
[RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md).

Read [17_STANDARD_PRODUCT_DESIGN.md](17_STANDARD_PRODUCT_DESIGN.md) when changing product behavior, scope, domain models, contracts or acceptance. Read [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) when changing phase scope. Read current POC contracts only when touching implemented APIs or shared structures. Historical documents are evidence, not executable instructions.

## Resume Protocol

1. Confirm the single current phase/task and freeze its result card.
2. Implement one vertical result batch and run automated gates plus review.
3. Deliver a preview and evidence pack for explicit user acceptance.
4. Update current documents only after results and verification are factual.
