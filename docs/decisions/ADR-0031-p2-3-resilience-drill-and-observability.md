# ADR-0031: P2.3 Resilience Drill And Queue Observability Sidecar

## Status

Proposed

Proposed with the P2.3 candidate. It becomes `Accepted` only with the explicit
P2.3 user decision.

## Date

2026-07-29

## Context

Accepted P2.2 proves bounded execution, timeout, cancellation, backpressure
and per-screen failure isolation inside its own backend suite, but the runtime
exposes no way for an operator to observe per-screen queue state or to verify,
against a live published screen, that the frozen P2.1 fallback contract
(equivalent fallback for technical failures; terminal no-fallback for
permission, invalid and cancelled signals) actually holds. P2.3 is the
integrated resilience certification of accepted P2.1 and P2.2 and must make
these guarantees observable without widening any permission boundary.

## Decision

1. P2.3 adds no schema migration. The store stays at
   `p1_control_plane_001` with head `005_controlled_querying`; the rollback
   target is the accepted P2.2 candidate with no data reversal.
2. A `P23ControlPlane` sidecar adds browser-session-only surfaces:
   a screen-bound metadata-only execution list, a screen-bound queue-status
   view and a screen-bound resilience drill. No device-prefix routes are
   added.
3. Queue status exposes only the requesting screen's live inflight, static
   configured capacity and that screen's own persisted backpressure-rejection
   counter. Live global counters and sibling-screen identifiers are never
   exposed.
4. The resilience drill is a deterministic, synchronous, in-process
   simulation over the screen's applied capability snapshot. It makes no
   external provider call, starts no thread and evaluates fallback exclusively
   through the accepted `p2_1.fallback_decision` contract: technical signals
   (`timeout`, `unavailable`, `unsupported`) resolve through a
   permission-equivalent activatable fallback; `permission_denied`,
   `invalid_request`, `unauthorized_template` and `cancelled` are always
   terminal; `backpressure` models queue admission rejection without provider
   execution.
5. Drill runs are audited through the existing audit machinery
   (`runResilienceDrill`), require Idempotency-Key semantics identical to
   other mutations and are retained only in a bounded in-memory store (128
   drills); eviction yields a sanitized 404.
6. Capacity certification is a reproducible local measurement harness
   (`capacity_p2_3.py`) producing deployment-local reference numbers with
   recorded environment facts. It publishes no SLA, no throughput promise and
   no customer-environment certification.

## Consequences

- Operators can watch three screens execute concurrently and confirm that a
  slow query, cancellation, failed source or failed provider affects only the
  requesting screen.
- The equivalent-fallback contract is demonstrated live per screen instead of
  only in decision-function unit tests, while permission denial still never
  falls back.
- Capacity guidance is measured and reproducible but remains
  deployment-local; high-concurrency or linear-scaling claims stay out of
  scope.
- Concurrency limits remain the accepted P2.2 constants, imported rather than
  duplicated; tuning them is a future batch, not operator configuration.

## Follow-Up

- P2.4 remains blocked on official FineReport plugin evidence.
- Production activation, external control-plane stores, clusters and
  customer RPO/RTO certification remain later-phase gates.
