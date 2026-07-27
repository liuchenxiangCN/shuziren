# P1.2 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`

## Frozen Limits

- P1.2 is a local development-preview inventory result, not production
  activation or a customer compatibility certification.
- FVS references are non-secret labels only. Connectivity remains
  `UNVERIFIED`; the candidate does not call FineReport, FVS or the licensed
  plugin.
- Runtime inventory reports `NOT_CONFIGURED_P1_3`. Drafts, releases,
  publication, acknowledgement, product rollback and recovery remain P1.3.
- Site is read-only. Screen/group retirement, deletion, cross-Site move and
  multi-Site delivery are outside this result.
- DigitalHumanInstance has no Renderer, AvatarPackage or provider configuration
  and only supports the first active inventory instance.
- SQLite is the only exercised P1.2 store. PostgreSQL, production custodian
  ceremonies, external monotonic anchors and backup/restore remain unverified.
- Snapshot cursors are opaque, principal-bound and five-minute local
  control-plane records; this is not a high-concurrency or distributed-cursor
  SLA.
- Docker/Compose and browser evidence prove one local packaging/runtime path,
  not production HTTPS, orchestrator, customer infrastructure or upgrade
  certification.
- The backend suite emits one Starlette `TestClient` dependency deprecation
  warning; the warning does not affect the passing cases.
- FineReport/FVS/plugin/browser version compatibility remains Blocked by the P2
  external gate.
- The user's acceptance does not waive these limits or turn unverified
  FineReport/FVS, publication, recovery or production behavior into supported
  capability.
