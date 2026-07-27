# Codex Context

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard product target and current execution state
- Last reviewed: 2026-07-27
- Historical context: [archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CODEX_CONTEXT_FULL_HISTORY.md)

## Product

This repository is productizing the existing local POC into a privately deployed, single-site, multi-screen conversational digital-human management platform for customers that already own FineReport and use FVS to build large screens.

The product reuses customer FineReport / FVS assets. It adds per-screen digital-human configuration, capability orchestration, controlled querying and screen actions, versioned publishing, monitoring, audit, backup and recovery.

## Execution Snapshot

Current phase: `Productization P1.2 Three-Screen Inventory`. G0, P1.0 and P1.1 were explicitly accepted on 2026-07-27.

P1.0 froze the accepted target domain model, data model, identity and permission model, configuration-release state machines, storage / recovery decision and control-plane API contract. P1.1 implemented and proved the local identity, browser-session, RBAC, security-audit and screen-device trust slice. The P1.2 candidate now implements the frozen three-screen inventory slice and has passed its local automated, browser, migration, Docker, rollback and independent-review gates. It is ready for explicit user result acceptance but remains unaccepted. Release publication and backup / restore remain P1.3.

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

The accepted runtime baseline remains the original single-instance POC plus the
separate P1.1 development-preview control plane. P1.1 adds local IAM, server-side
browser sessions, RBAC, append-only security audit and screen-device trust
without changing the existing POC route meanings.

The unaccepted P1.2 candidate adds the checksum-backed
`002_three_screen_inventory` migration, default Site/group/three-screen
inventory, scoped inventory APIs and the `/manage` multi-screen view. FVS is
still `UNVERIFIED`; runtime configuration is still `NOT_CONFIGURED_P1_3`.
Nothing in the candidate claims publication, real FVS connectivity or
production readiness.

Implemented POC contracts remain authoritative for the original POC namespaces:

- [06_API_CONTRACT.md](06_API_CONTRACT.md)
- [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md)

Accepted P1.1 behavior is recorded separately in
[acceptance/productization/P1.1](acceptance/productization/P1.1). The current
P1.2 candidate and its pending acceptance state are recorded in
[acceptance/productization/P1.2](acceptance/productization/P1.2). P1.3 and later
target behavior under [product/contracts](product/contracts) remains
unimplemented.

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
