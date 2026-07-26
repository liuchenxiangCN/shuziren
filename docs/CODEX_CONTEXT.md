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

Current phase: `G0 Acceptance Gate`. Documentation governance and the result-driven roadmap are implemented; the user result decision is pending.

P0 product definition is complete. After G0 acceptance, the queued phase is `Productization P1.0`: target domain model, data model, identity model, storage decision and control-plane API contract result pack. P1.0 is contract design only.

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

The implemented code remains a single-runtime POC baseline with Vue 3, FastAPI, Docker Compose, customer configuration overlays, Mock switches, provider abstractions, controlled `action_id` screen actions, Excel querying, knowledge retrieval, ASR / TTS and sanitized Ops capabilities.

Implemented POC contracts remain authoritative only for the current code:

- [06_API_CONTRACT.md](06_API_CONTRACT.md)
- [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md)

They are not the target multi-screen product contracts. Target contracts will be created under [product/contracts](product/contracts).

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
