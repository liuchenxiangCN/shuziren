# Codex Context

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard product target and current execution state
- Last reviewed: 2026-07-28
- Historical context: [archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md)

## Product

This repository is productizing the existing local POC into a privately deployed, single-site, multi-screen conversational digital-human management platform for customers that already own FineReport and use FVS to build large screens.

The product reuses customer FineReport / FVS assets. It adds per-screen digital-human configuration, capability orchestration, controlled querying and screen actions, versioned publishing, monitoring, audit, backup and recovery.

## Execution Snapshot

Current phase: `Productization P2.2 Accepted; P2.3 Awaiting Explicit
Activation`. G0 and P1.0 through P2.2 are explicitly accepted. P1.1 proves
local identity/device trust, P1.2 three-screen inventory, P1.3
draft/release/recovery and P2.1 per-screen capability profiles. P2.2 candidate
`a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
`aaa499de416b522e21c02f41119024296fc2c3a0`, implements the frozen local
controlled-querying result. Its automated, browser, exact real-database,
rollback and independent-review gates passed, and the user accepted it without
conditions on 2026-07-28. P2.3 is queued and not active.

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

The accepted runtime baseline is P2.2 commit
`a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
`aaa499de416b522e21c02f41119024296fc2c3a0`. It retains the original POC route
meanings and accepted P1/P2.1 controls, then adds Site-owned immutable
QuerySources and datasets, exact release query snapshots, write-only encrypted
database credentials and bounded screen/device execution. Accepted P2.1
commit `8f364b93b574c058cd8cd617f925107985318098`, tree
`7c277e32b6419bd3720591c454e8282d94f081ec`, plus the verified WAL-safe
pre-`005` copy remains the P2.2 product/data rollback target. External
Providers and FVS remain `UNVERIFIED`, and production readiness is not
claimed.

Implemented POC contracts remain authoritative for the original POC namespaces:

- [06_API_CONTRACT.md](06_API_CONTRACT.md)
- [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md)

Accepted behavior is recorded under [acceptance/productization](acceptance/productization).
P2.1/P2.2 target boundaries remain under [product/contracts](product/contracts);
the accepted P2.2 facts and limitations are under
[acceptance/productization/P2.2](acceptance/productization/P2.2). P2.3 remains
queued and requires a separate explicit activation instruction.

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

For every task:

1. [NEXT_ACTIONS.md](NEXT_ACTIONS.md)
2. [13_RISKS_AND_TODO.md](13_RISKS_AND_TODO.md)
3. [RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md)

Read [17_STANDARD_PRODUCT_DESIGN.md](17_STANDARD_PRODUCT_DESIGN.md) when changing product behavior, scope, domain models, contracts or acceptance. Read [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) when changing phase scope. Read current POC contracts only when touching implemented APIs or shared structures. Historical documents are evidence, not executable instructions.

## Resume Protocol

1. Confirm the single current phase and single next task in `NEXT_ACTIONS.md`.
2. Freeze the result card before implementation.
3. Implement one vertical result batch only.
4. Run automated gates and an independent Codex review.
5. Deliver a preview and evidence pack for user result acceptance.
6. Update current docs only after the result and verification are factual.
