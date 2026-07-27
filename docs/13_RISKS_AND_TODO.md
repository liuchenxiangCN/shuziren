# Active Product Risks And Blockers

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: active standard-product risks and current external blockers
- Last reviewed: 2026-07-27
- Historical POC risks: [archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md](archive/poc-v1/root-snapshots/RISKS_AND_TODO_FULL_HISTORY.md)

Customer-specific and POC现场 issues are not tracked here. They remain in customer documents or the archive.

## Active Risks

| ID | Risk | Required Control | Status |
| --- | --- | --- | --- |
| R-041 | Multi-screen configuration, session, identity or permission leakage | P1 uses separate ScreenInstance / DigitalHumanInstance / DeviceEnrollment contexts and proves three-screen isolation | Open |
| R-043 | FineReport plugin external API, authentication, session, permission inheritance and upgrade stability are unknown | Keep the provider `Unverified` and unpublished until official documentation and isolated real-environment probes pass | Blocked |
| R-044 | Reusing the POC admin token or local-only boundary would make production roles insecure | The P1 target requires built-in users, secure sessions, lockout / reset, RBAC, separate device credentials and immutable audit; later P1 batches must implement and prove them | Open |
| R-045 | Embedded storage and global providers may not support product publishing, recovery and multi-screen correctness | P1 freezes storage / recovery; P2 introduces instance-bound providers, pools, timeouts, cancellation and backpressure | Open |
| R-046 | Plugin failure could fall back to a database or Excel source with broader permission | Permit fallback only for technical unavailability and equivalent ScreenInstance-bound permission scope; never for permission denial | Open |
| R-047 | “FineReport / FVS 11.0+ target” may be interpreted as automatic compatibility | Publish only exact certified FineReport + FVS + plugin + browser + product combinations | Open |
| R-048 | “No product hard cap” may be interpreted as unlimited throughput or SLA | Keep three-screen correctness as the first baseline and publish only measured capacity guidance | Mitigated |
| R-049 | Real 2D / 3D assets, suppliers, formats and licenses are unavailable | P3 accepts only the Renderer / AvatarPackage contract and test renderer; real adapters require separate certification | Mitigated |
| R-050 | A user who does not review code could receive superficially working but insecure or unrecoverable results | Enforce result cards, automated gates, independent Codex review, evidence packages and rollback proof | Open |
| R-051 | Historical POC instructions could redirect Codex away from the product phase | G0 created one current phase / task, archived long histories and added lifecycle lint | Mitigated |

## Current Product Blockers

### P1.1 Identity And Device Trust

P1.0 accepted the target decisions on 2026-07-27. P1.1 now implements only the local identity, session, RBAC, audit and screen-device trust slice.

- The development preview may initialize explicit test identities and one trust-only screen fixture, but production startup must never auto-create users, passwords, roles, device targets or keys.
- The accepted contract requires typed different-user production approval; approval records evidence only and cannot execute the effect.
- User sessions, CSRF, one-time enrollment and device credentials must persist only keyed verifiers, never plaintext.
- Device scope must come only from its credential record; requests cannot select tenant, deployment, Site or ScreenInstance.
- Production custodian attestation, monotonic anchors and production activation remain unverified and must not be inferred from development-preview evidence.
- P1.2 inventory and P1.3 publishing / recovery remain blocked until P1.1 is explicitly accepted.

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
