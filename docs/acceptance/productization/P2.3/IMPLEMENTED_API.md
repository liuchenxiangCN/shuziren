# P2.3 Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `a124f63b8f3b5e499b6c561e78199a26f860edc9`
- Candidate fingerprint:
  `FE0F87AC1B3F1FD5373681E86BDFA0DE909D6A1E637BD22E2A97DEFD57F26097`
  over 36 files
- API version: `v1`
- User decision: `通过` without conditions or scope reduction on 2026-07-29

This file describes the P2.3 candidate development-preview result. It adds no
schema migration; the store remains `p1_control_plane_001` at
`005_controlled_querying`.

## Added Routes

Four browser-session routes under `/api/v1/control-plane`. No device-prefix
route is added; every route enforces the accepted P2.2 RBAC and
Tenant/Deployment/Site/screen ownership checks, and cross-screen access is a
sanitized 404 with no privileged fallback.

- `GET /screen-instances/{screen_id}/query-executions?limit=` — metadata-only
  list of the screen's own query executions, newest first, `limit` 1–100
  (default 50). Items carry `execution_id`, `dataset_id`, `dataset_label`,
  `state`, `request_id`, `latency_ms`, `row_count`, `result_retained`,
  sanitized `error` and timestamps. Result rows and parameter values are
  never included.
- `GET /screen-instances/{screen_id}/queue-status` — the requesting screen's
  live `inflight` against the per-screen limit, the static configured
  capacity (global 6, per-screen 2, workers 3, retained terminal jobs 256,
  imported from the accepted P2.2 constants) and the screen's own persisted
  `rejected_backpressure` counter. No live global counters and no
  sibling-screen identifiers are exposed.
- `POST /screen-instances/{screen_id}/resilience-drills` (201) — runs a
  screen-bound resilience drill. Requires `Idempotency-Key` with the accepted
  exact-replay/changed-command semantics. The strict body accepts only
  `capability` (one of the seven P2.1 capabilities) and `signal` (one of
  `timeout`, `unavailable`, `unsupported`, `permission_denied`,
  `invalid_request`, `unauthorized_template`, `cancelled`, `backpressure`).
- `GET /screen-instances/{screen_id}/resilience-drills/{drill_id}` — reads a
  drill by opaque ID; cross-screen or evicted drills are a sanitized 404.

## Drill Semantics

The drill resolves the screen's applied capability snapshot and simulates the
injected signal deterministically in-process: no threads, no external
provider calls, bounded latency. An unpublished screen or disabled capability
yields outcome `CAPABILITY_DISABLED`. Technical signals evaluate the first
configured fallback through the accepted `p2_1.fallback_decision` contract:
`FALLBACK_ALLOWED` yields outcome `FALLBACK_RESOLVED` with the resolved
provider; any other decision yields `TERMINAL_NO_FALLBACK`. Profiles without
fallbacks yield `NO_FALLBACK_CONFIGURED`. Terminal signals
(`permission_denied`, `invalid_request`, `unauthorized_template`,
`cancelled`) never fall back. The `backpressure` signal models queue
admission rejection (`queue_admission: REJECTED`) without provider execution.

Every drill writes one sanitized `runResilienceDrill` audit event. Drill
records are retained only in a bounded in-memory store (128 drills); audit
history persists.

## Closed Inputs And Outputs

- The drill body is a strict two-field model; unknown fields fail validation.
- Drill, list and queue responses contain no secrets, DSNs, SQL, parameter
  values, result rows or workbook content.
- Concurrency limits are the accepted P2.2 constants, imported rather than
  duplicated; they are not operator-configurable.

## Frontend Surfaces

The `/manage` queries view gains, for the selected screen only: an executions
list with per-row cancel for non-terminal items, a queue-status strip and a
resilience-drill launcher rendering the outcome, decision, resolved provider
and flags. Screen switches clear all per-screen runtime state.
