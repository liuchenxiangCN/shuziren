# Active Product Risks And Blockers

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: active standard-product risks and current external blockers
- Last reviewed: 2026-07-28
- Historical POC risks: [archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md](archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md)

Customer-specific and POC现场 issues are not tracked here. They remain in customer documents or the archive.

## Active Risks

| ID | Risk | Required Control | Status |
| --- | --- | --- | --- |
| R-041 | Multi-screen configuration, session, identity or permission leakage | Accepted P2.1 preserves separate ScreenInstance / DigitalHumanInstance / DeviceEnrollment contexts and adds isolated capability snapshots and credential-scoped resolution; later batches must preserve these controls | Mitigated |
| R-043 | FineReport plugin external API, authentication, session, permission inheritance and upgrade stability are unknown | Keep the provider `Unverified` and unpublished until official documentation and isolated real-environment probes pass | Blocked |
| R-044 | Reusing the POC admin token or local-only boundary would make production roles insecure | P1.1 proves the development-preview IAM, session, RBAC, separate device credential and immutable-audit slice; later batches must preserve it while production activation and custodian controls remain unverified | Open |
| R-045 | Embedded storage and global providers may not support product publishing, recovery and multi-screen correctness | Accepted P2.1 proves bounded SQLite plus screen-bound local/Mock timeout, cancellation and backpressure contracts, while real-provider pools and measured capacity remain later gates | Open |
| R-046 | Plugin failure could fall back to a database or Excel source with broader permission | Accepted P2.1 permits only technical, equivalent screen-bound fallback and makes permission denial terminal; real plugin/query integration must preserve this rule | Open |
| R-047 | “FineReport / FVS 11.0+ target” may be interpreted as automatic compatibility | Publish only exact certified FineReport + FVS + plugin + browser + product combinations | Open |
| R-048 | “No product hard cap” may be interpreted as unlimited throughput or SLA | Keep three-screen correctness as the first baseline and publish only measured capacity guidance | Mitigated |
| R-049 | Real 2D / 3D assets, suppliers, formats and licenses are unavailable | P3 accepts only the Renderer / AvatarPackage contract and test renderer; real adapters require separate certification | Mitigated |
| R-050 | A user who does not review code could receive superficially working but insecure or unrecoverable results | Enforce result cards, automated gates, independent Codex review, evidence packages and rollback proof | Mitigated |
| R-051 | Historical POC instructions could redirect Codex away from the product phase | G0 created one current phase / task, archived long histories and added lifecycle lint | Mitigated |

## Current Product State And Blockers

### P2.1 Accepted; P2.2 User Decision Pending

The user explicitly accepted P2.1 without conditions on 2026-07-28. Candidate
`8f364b93b574c058cd8cd617f925107985318098`, tree
`7c277e32b6419bd3720591c454e8282d94f081ec`, is the accepted runtime baseline.
Accepted P1.3 remains the verified product-code and pre-`004` data rollback
target. P2.2 implementation and expanded automated/browser/ephemeral-database
gates pass. Its first immutable candidate failed independent review; the
reported gaps were repaired. Replacement candidate
`78b5af301a1c57915a4535d3decc11c59b79eba7` exposed one remaining closed-SQL
expression family and was also rejected; sequence expressions, custom
operators and user-defined casts are now fail-closed. Final candidate
`a75d3327fdc1ab4b83b0bba501d387af150353c4` passed exact independent review
with zero findings; explicit user acceptance remains.

- P2.1 accepted capability-profile, three-screen resolution, migration,
  recovery, Docker, Secret-scan and accepted-P1.3 rollback evidence; final
  independent review returned PASS with zero findings.
- Later batches must preserve P2.1 ownership, sibling non-disclosure, Secret
  rejection, immutable history, device trust, release snapshots and recovery
  controls.
- Real FVS/plugin behavior, production activation, external anti-rollback
  anchors, full-loss recovery, PostgreSQL and customer RPO/RTO certification
  remain blocked or outside the accepted P2.1 result.
- Accepted P2.1 keeps external Providers `unverified`, blocks their activation
  and resolves legacy P1.3 releases as `NOT_CONFIGURED_P2_1` rather than using
  a global Mock fallback.
- P2.2 must preserve the accepted P2.1 capability, ownership, release,
  recovery and isolation boundaries. No free-SQL path is authorized.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 passed isolated exact read-only
  adapter tests. This closes only the candidate's deployment-local reference
  evidence; customer/version product certification remains unverified.

### P2 External Gate

- Obtain official FineReport plugin OpenAPI or equivalent interface documentation.
- Confirm authentication and session behavior.
- Confirm whether and how FineReport template / data permission is inherited.
- Confirm upgrade and compatibility guarantees.
- Validate in an isolated legal customer FineReport 11.0 environment before expanding the certification matrix.

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
