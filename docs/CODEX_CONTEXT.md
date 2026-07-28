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

Current phase: `Productization P1.3 Publish, Rollback And Recovery`. G0, P1.0,
P1.1 and P1.2 were explicitly accepted on 2026-07-27. The user explicitly
activated P1.3 on 2026-07-27; its result card and non-scope were frozen before
implementation.

P1.0 froze the target control-plane contract. P1.1 proved local identity,
RBAC, audit and screen-device trust. P1.2 proved three-screen inventory and
remains the accepted runtime rollback baseline. P1.3 final candidate
`0f210cffa5a9b49fd93d36dbb42bd36bb2899f54` implements only the frozen
development-preview draft/release, publication/acknowledgement, forward
rollback, encrypted online-source backup/restore and three-day runtime-detail
retention result. Its automated gates and final isolated independent review
pass with zero findings. P1.2 remains the accepted runtime until the user
records an explicit P1.3 decision.

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

The accepted runtime baseline includes the original POC plus P1.1 local IAM,
session/RBAC/audit/device trust without changing existing POC route meanings.

The accepted P1.2 runtime adds the checksum-backed
`002_three_screen_inventory` migration, default Site/group/three-screen
inventory, scoped inventory APIs and the `/manage` multi-screen view. FVS is
still `UNVERIFIED`. The P1.3 candidate adds bounded local publication and
recovery behavior with `MOCK_PASSED` preview evidence; neither accepted P1.2 nor
the P1.3 candidate claims real FVS connectivity or production readiness.

Implemented POC contracts remain authoritative for the original POC namespaces:

- [06_API_CONTRACT.md](06_API_CONTRACT.md)
- [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md)

Accepted P1.1 and P1.2 behavior is recorded separately in
[acceptance/productization/P1.1](acceptance/productization/P1.1) and
[acceptance/productization/P1.2](acceptance/productization/P1.2). The active
P1.3 result boundary and factual candidate record are in
[acceptance/productization/P1.3/ACCEPTANCE_CARD.md](acceptance/productization/P1.3/ACCEPTANCE_CARD.md).
P1.3 behavior outside that acceptance package and all later target behavior
under [product/contracts](product/contracts) remains unimplemented.

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
