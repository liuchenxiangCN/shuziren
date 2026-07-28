# P2.1 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `8f364b93b574c058cd8cd617f925107985318098`
- Candidate tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- User decision: `通过` on 2026-07-28

## Frozen Limits

- P2.1 is an accepted local development-preview result. Automated gates,
  rollback and independent review pass; acceptance does not broaden the
  verified local/Mock boundary.
- Every Provider descriptor has `external_calls_enabled=false`. The runtime
  performs only closed local/Mock diagnostic selection; it does not establish,
  authenticate or call a real Provider.
- `available` means only a bounded local descriptor is eligible inside this
  preview contract. `mock` is development evidence, `degraded` is reduced
  behavior, and `unverified` blocks activation. None is a production or vendor
  certification claim.
- The FineReport official-plugin entries remain `unverified`. No plugin
  archive, adapter, internal API, template discovery, authentication,
  permission inheritance, request or compatibility result is implemented.
  That external gate belongs to P2.4.
- Querying stores only a Provider selector. There is no QuerySource registry,
  Excel/MySQL/Oracle/PostgreSQL connection, dataset, SQL execution, data
  permission or result transport. Those belong to P2.2, which has not started.
- There is no real Dora, RAGFlow, direct LLM, ASR audio, TTS audio or FVS
  action execution. The profile contains no endpoint, Prompt, Secret,
  credential, arbitrary payload or executable content.
- The fallback function is a deterministic diagnostic contract, not an
  external call scheduler. It does not certify vendor timeout, cancellation,
  streaming, backpressure or session behavior.
- The 1280 by 720 interactive browser workflow ran against candidate
  `3062b14863d1ed0a1f92f4f6a203a602cc4c6045`. The final candidate rebinds it
  through byte-identical frontend/API-client/fixture inputs plus a
  dual-PowerShell-host-tested `--no-access-log` launcher change; the
  interactive workflow was not rerun against the final commit.
- A legacy P1.3 applied ReleaseTarget intentionally resolves to
  `NOT_CONFIGURED_P2_1`; migration does not silently attach a default profile.
- SQLite is the only implemented control-plane store. There is no PostgreSQL,
  cluster, distributed-concurrency, high-throughput or SLA certification.
- Backup/restore remains the existing encrypted local preview path. P2.1 does
  not add external WORM evidence, full-loss authority, cryptographic-root
  recovery or customer RPO/RTO.
- P2.3 integrated resilience/capacity certification, Renderer/AvatarPackage
  release management and production activation remain outside this result.
- The backend suite emits one Starlette TestClient dependency deprecation
  warning; it does not affect the 35 passing cases.

User acceptance cannot turn local/Mock evidence, an unverified Provider or an
uncatalogued customer environment into supported production capability.
