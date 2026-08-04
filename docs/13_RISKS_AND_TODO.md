# Active Product Risks And Blockers

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: active standard-product risks and current external blockers
- Last reviewed: 2026-08-04
- Historical POC risks: [archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md](archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md)

Customer-specific and POC现场 issues are not tracked here. They remain in customer documents or the archive.

## Active Risks

| ID | Risk | Required Control | Status |
| --- | --- | --- | --- |
| R-041 | Multi-screen configuration, session, identity or permission leakage | Accepted P2.2 preserves separate ScreenInstance / DigitalHumanInstance / DeviceEnrollment contexts, immutable capability/query snapshots and credential-scoped resolution/execution; later batches must preserve these controls | Mitigated |
| R-043 | FineReport plugin external API, authentication, session, permission inheritance and upgrade stability are unknown | 2026-07-29 local probe of plugin 1.2.5 on FineReport 11.0 (jar 11.5.11) produced deployment-local evidence for API surface, authentication, session and permission behavior (see `docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md` §2), including recorded finding F-01 (OpenAPI sessions chain skips template-permission checks; record-only per user decision). Keep the provider `Unverified` and unpublished until official documentation and upgrade-stability confirmation arrive | Blocked |
| R-044 | Reusing the POC admin token or local-only boundary would make production roles insecure | P1.1 proves the development-preview IAM, session, RBAC, separate device credential and immutable-audit slice; later batches must preserve it while production activation and custodian controls remain unverified | Open |
| R-045 | Embedded storage and global providers may not support product publishing, recovery and multi-screen correctness | Accepted P2.3 certifies three-screen concurrent correctness, single-source/provider failure isolation, bounded backpressure and recovery on bounded SQLite, with a deployment-local capacity measurement; customer-environment capacity remains uncertified | Mitigated |
| R-046 | Plugin failure could fall back to a database or Excel source with broader permission | Accepted P2.2 preserves only technical, equivalent screen-bound fallback and makes permission/validation/cancellation failures terminal; real plugin integration must preserve this rule | Open |
| R-047 | “FineReport / FVS 11.0+ target” may be interpreted as automatic compatibility | Publish only exact certified FineReport + FVS + plugin + browser + product combinations | Open |
| R-048 | “No product hard cap” may be interpreted as unlimited throughput or SLA | Keep three-screen correctness as the first baseline and publish only measured capacity guidance | Mitigated |
| R-049 | Real 2D / 3D assets, suppliers, formats and licenses are unavailable | P3 accepts only the Renderer / AvatarPackage contract and test renderer; real adapters require separate certification | Mitigated |
| R-050 | A user who does not review code could receive superficially working but insecure or unrecoverable results | Enforce result cards, automated gates, independent Codex review, evidence packages and rollback proof | Mitigated |
| R-051 | Historical POC instructions could redirect Codex away from the product phase | G0 created one current phase / task, archived long histories and added lifecycle lint | Mitigated |

## Current Product State And Blockers

### P3 Active; P2.4 Deferred And Blocked By External Gate

The user explicitly accepted P2.3 without conditions on 2026-07-29. Candidate
`a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
`8a2f4e36ca0751b6106a174f7dae63be9299ad5b`, is the accepted runtime baseline.
Accepted P2.2 candidate `a75d3327fdc1ab4b83b0bba501d387af150353c4` remains
the P2.3 product rollback target; P2.3 added no migration, so no data
reversal is required.

The user activated P3 on 2026-08-04 while explicitly leaving P2.4 deferred.
P3 must keep R-049 visible: only the test Renderer and test AvatarPackage
contract may be accepted. No real 2D/3D file format, SDK, asset, browser/GPU
combination or supplier compatibility may be inferred from P3 evidence.

- P2.2 automated, browser, real-database, migration/recovery, Docker,
  Secret-scan and accepted-P2.1 rollback evidence passes; final independent
  review returned PASS with zero findings.
- Later batches must preserve P2.2 ownership, sibling non-disclosure, Secret
  rejection, immutable history, closed SQL, device trust, release snapshots,
  terminal no-fallback behavior and recovery controls.
- Real FVS/plugin behavior, production activation, external anti-rollback
  anchors, full-loss recovery, PostgreSQL and customer RPO/RTO certification
  remain blocked or outside the accepted P2.2 result.
- Accepted P2.2 keeps external Providers `unverified`, blocks their activation
  and resolves legacy P1.3 releases as `NOT_CONFIGURED_P2_1` rather than using
  a global Mock fallback.
- P2.3 preserved the accepted P2.2 capability, query, ownership, release,
  recovery and isolation boundaries. Later batches must preserve them and the
  P2.3 drill/observability contract. No free-SQL path is authorized.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 passed isolated exact read-only
  adapter tests. This closes only the accepted result's deployment-local
  reference evidence; customer/version product certification remains
  unverified.

### P2 External Gate

- Obtain official FineReport plugin OpenAPI or equivalent interface documentation. (Still open.)
- Confirm authentication and session behavior. (Deployment-local evidence obtained 2026-07-29 for plugin 1.2.5 on FineReport 11.0 jar 11.5.11; vendor confirmation still open.)
- Confirm whether and how FineReport template / data permission is inherited. (Deployment-local evidence obtained 2026-07-29, including recorded finding F-01: the OpenAPI sessions chain does not enforce template permission; record-only per user decision.)
- Confirm upgrade and compatibility guarantees. (Still open; single-version local probing cannot prove this.)
- Validate in an isolated legal customer FineReport 11.0 environment before expanding the certification matrix. (Local 11.0 designer environment validated 2026-07-29; customer environment remains uncovered.)

### Compatibility Work

- Choose the first exact FineReport / FVS / plugin / browser combinations.
- Choose the first exact MySQL, Oracle and PostgreSQL versions and driver combinations.
- Record reference hardware and measured capacity after three-screen correctness is stable.

## Closed Or Historical Topics

- P0 product-positioning decisions are frozen in [17_STANDARD_PRODUCT_DESIGN.md](17_STANDARD_PRODUCT_DESIGN.md) and ADR-0026.
- G0 documentation governance is defined in [DOCUMENT_GOVERNANCE.md](DOCUMENT_GOVERNANCE.md).
- POC customer-network, microphone, demo, RAGFlow, FVS iframe and customer sign-off issues are historical or customer-specific and are retained in the archive.

## Risk Rules

- Any cross-screen leak, authorization bypass, Secret exposure, data corruption, permission-broadening fallback or unrecoverable migration blocks acceptance.
- A missing external environment is `Blocked`, not `Passed`.
- Mock evidence cannot close a real-provider risk.
- Risk status changes require factual evidence and synchronization with the active acceptance package.
