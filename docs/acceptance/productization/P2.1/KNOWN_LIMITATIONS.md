# P2.1 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_PRESENT; FINAL_VERIFICATION_PENDING`
- Candidate commit / tree: `PENDING`
- User decision: `PENDING`

## Frozen Limits

- P2.1 is a local development-preview implementation. Candidate binding,
  automated gates, browser evidence, rollback proof, independent review and
  user acceptance are still `PENDING`.
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
- A legacy P1.3 applied ReleaseTarget intentionally resolves to
  `NOT_CONFIGURED_P2_1`; migration does not silently attach a default profile.
- SQLite is the only implemented control-plane store. There is no PostgreSQL,
  cluster, distributed-concurrency, high-throughput or SLA certification.
- Backup/restore remains the existing encrypted local preview path. P2.1 does
  not add external WORM evidence, full-loss authority, cryptographic-root
  recovery or customer RPO/RTO.
- P2.3 integrated resilience/capacity certification, Renderer/AvatarPackage
  release management and production activation remain outside this result.

User acceptance cannot turn local/Mock evidence, an unverified Provider or an
uncatalogued customer environment into supported production capability.
