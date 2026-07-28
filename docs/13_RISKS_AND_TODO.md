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
| R-041 | Multi-screen configuration, session, identity or permission leakage | Accepted P1.2 uses separate ScreenInstance / DigitalHumanInstance / DeviceEnrollment contexts and passes three-screen isolation plus independent-review gates; later batches must preserve these controls | Mitigated |
| R-043 | FineReport plugin external API, authentication, session, permission inheritance and upgrade stability are unknown | Keep the provider `Unverified` and unpublished until official documentation and isolated real-environment probes pass | Blocked |
| R-044 | Reusing the POC admin token or local-only boundary would make production roles insecure | P1.1 proves the development-preview IAM, session, RBAC, separate device credential and immutable-audit slice; later batches must preserve it while production activation and custodian controls remain unverified | Open |
| R-045 | Embedded storage and global providers may not support product publishing, recovery and multi-screen correctness | P1 freezes storage / recovery; P2 introduces instance-bound providers, pools, timeouts, cancellation and backpressure | Open |
| R-046 | Plugin failure could fall back to a database or Excel source with broader permission | Permit fallback only for technical unavailability and equivalent ScreenInstance-bound permission scope; never for permission denial | Open |
| R-047 | “FineReport / FVS 11.0+ target” may be interpreted as automatic compatibility | Publish only exact certified FineReport + FVS + plugin + browser + product combinations | Open |
| R-048 | “No product hard cap” may be interpreted as unlimited throughput or SLA | Keep three-screen correctness as the first baseline and publish only measured capacity guidance | Mitigated |
| R-049 | Real 2D / 3D assets, suppliers, formats and licenses are unavailable | P3 accepts only the Renderer / AvatarPackage contract and test renderer; real adapters require separate certification | Mitigated |
| R-050 | A user who does not review code could receive superficially working but insecure or unrecoverable results | Enforce result cards, automated gates, independent Codex review, evidence packages and rollback proof | Mitigated |
| R-051 | Historical POC instructions could redirect Codex away from the product phase | G0 created one current phase / task, archived long histories and added lifecycle lint | Mitigated |

## Current Product Blockers

### P1.3 Active

P1.2 was explicitly accepted on 2026-07-27. Candidate
`2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree
`565dbb3567e2a4ae5b872177d97449120477fe8c`, is the current runtime rollback
baseline. The user explicitly activated P1.3 on 2026-07-27, and the complete
result/non-scope is frozen before implementation in the P1.3 acceptance card.

- P1.2 proves the local default Site, group and independently addressable screen inventory without claiming publication or real FVS connectivity.
- P1.3 must preserve accepted ownership, sibling non-disclosure, Secret rejection, immutable audit and device-trust behavior.
- Final candidate `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54` implements the
  frozen local development-preview slice. Migration, publication,
  acknowledgement, rollback, backup/restore, retention, browser, Secret-scan,
  Docker and accepted-P1.2 rollback gates pass.
- The final isolated independent review returned PASS with zero blocking and
  zero non-blocking findings. The only remaining P1.3 acceptance condition is
  the user's explicit result decision.
- Real FVS/plugin behavior, production activation, external anti-rollback
  anchors, full-loss recovery, PostgreSQL and customer RPO/RTO certification
  remain blocked or outside the frozen P1.3 result.

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
