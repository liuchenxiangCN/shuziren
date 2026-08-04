# Decision Index

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: ADR navigation and lifecycle
- Last reviewed: 2026-08-04

## Current Product Decisions

- [ADR-0026](ADR-0026-finereport-fvs-productization.md): FineReport / FVS multi-screen productization boundary.
- [ADR-0027](ADR-0027-result-driven-development-and-document-lifecycle.md): result-driven development and document lifecycle.
- [ADR-0028](ADR-0028-p1-control-plane-foundation.md): accepted P1 target domain, IAM, device trust, storage, recovery and API foundation.
- [ADR-0029](ADR-0029-p2-1-capability-profile-sidecars.md): accepted additive immutable capability-profile sidecars that preserve the accepted P1.3 base schema.
- [ADR-0030](ADR-0030-p2-2-controlled-query-sidecar.md): accepted additive
  controlled-query sidecars, write-only connection material and screen-bound
  bounded execution that preserve the accepted P1/P2.1 boundaries.
- [ADR-0031](ADR-0031-p2-3-resilience-drill-and-observability.md): accepted
  screen-bound resilience drill, queue observability and deployment-local
  capacity measurement with no schema migration.
- [ADR-0032](ADR-0032-p3-test-renderer-and-avatar-switching.md): proposed P3
  built-in test Renderer, immutable declarative AvatarPackage and screen-bound
  prefetch, switch and rollback contract; it remains proposed until P3 is
  explicitly accepted.

## Implemented POC Decisions

ADR-0002 through ADR-0025 remain stable historical paths for implemented POC behavior. Read them only when current work touches the corresponding as-built capability.

ADR-0001 and ADR-0023 are superseded for product positioning by ADR-0026, while their historical POC context remains preserved.

## Rule

An older ADR does not override current product boundaries, accepted later ADRs or the single task in `NEXT_ACTIONS.md`.
