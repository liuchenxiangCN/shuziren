# P1.3 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`

## Frozen Limits

- P1.3 is a local development-preview result, not production activation,
  disaster-recovery certification or a customer compatibility claim.
- Preview is built-in Mock only and is visibly `MOCK_PASSED`. FineReport, FVS
  and the official plugin are not called and remain `UNVERIFIED`.
- The configuration schema contains only `welcome_text` and a non-secret
  `fvs_binding_ref`; it does not configure providers, data sources, actions,
  renderers, avatars or Secrets.
- SQLite is the only exercised control-plane store. PostgreSQL is not
  implemented or certified.
- Backup and restore are online-source local preview operations. There is no
  external WORM/monotonic anchor, OperationalFence, custodian quorum,
  full-loss restore or cryptographic-root recovery.
- The verified Compose path uses repository-mounted local data and does not
  prove a separate failure-domain production backup mount, HTTPS ingress,
  orchestrator behavior or customer RPO/RTO.
- Three-day cleanup runs when the API starts; P1.3 does not add an automatic
  hourly backup or retention scheduler.
- Group publication/rollback is atomic at the local SQLite transaction boundary
  but does not claim a high-concurrency or distributed-control-plane SLA.
- Publication moves desired state. A device must present its same-screen active
  credential and acknowledge the exact generation/hash before applied state
  moves.
- A retained pre-restore store is local recovery evidence; operators must keep
  it protected with the same sensitivity as the active control-plane database.
- The backend suite emits one Starlette `TestClient` dependency deprecation
  warning; it does not affect the passing cases.
- FineReport/FVS/plugin/browser combinations remain Blocked by the P2 external
  gate.

User acceptance cannot waive these limits or turn Mock/unverified behavior,
local recovery evidence or an uncatalogued customer environment into supported
production capability.
