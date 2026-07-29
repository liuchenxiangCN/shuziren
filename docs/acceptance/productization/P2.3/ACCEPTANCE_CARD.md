# P2.3 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Batch: `P2.3 Concurrent And Failure Isolation`
- State: `ACCEPTED`
- Activated by: explicit user instruction `完成P2.3开发`
- Activated at: 2026-07-29
- Base accepted commit: `a75d3327fdc1ab4b83b0bba501d387af150353c4`
- Base accepted tree: `aaa499de416b522e21c02f41119024296fc2c3a0`
- Candidate commit: `a124f63b8f3b5e499b6c561e78199a26f860edc9`
- Candidate tree: `8a2f4e36ca0751b6106a174f7dae63be9299ad5b`
- Logical schema: `p1_control_plane_001`
- Latest migration: `005_controlled_querying` (unchanged; P2.3 adds no schema
  migration)
- Target behavior: `P2.3 Concurrent And Failure Isolation` in
  [05_DEVELOPMENT_PLAN.md](../../../05_DEVELOPMENT_PLAN.md) and the frozen
  fallback/isolation contracts in
  [CAPABILITY_PROFILES.md](../../../product/contracts/CAPABILITY_PROFILES.md)
  and
  [CONTROLLED_QUERYING.md](../../../product/contracts/CONTROLLED_QUERYING.md)
- User decision: `通过` without conditions or scope reduction on 2026-07-29

## User-Visible Outcome

P2.3 is the integrated resilience certification of accepted P2.1 and P2.2. It
does not introduce concurrency controls for the first time; it proves, end to
end and observably, that three screens with different capability profiles run
concurrently and that a slow query, a cancellation, a failed source or a
failed provider affects only the requesting screen.

- Three screens use different capability combinations concurrently; each
  screen sees only its own executions, results, request IDs, latency and queue
  occupancy.
- Bounded backpressure stays bounded: a saturated queue rejects with a
  retryable, understandable status and recovers after drain; nothing grows
  without limit.
- Equivalent fallback works through the real profile-resolution path: a
  technical failure (`timeout`, `unavailable`, `unsupported`) on a profile
  with a permission-equivalent fallback resolves to that fallback, while
  `permission_denied`, `invalid_request`, `unauthorized_template` and
  `cancelled` stay terminal with no fallback. A screen-bound resilience drill
  drives these injected failures live and records an auditable, sanitized
  outcome.
- A local capacity measurement on the reference machine records the
  three-screen baseline and the saturation point as deployment-local guidance.
  It is not an SLA, not a cluster claim and not customer-environment
  certification.

## Entry Point And Test Data

- Management entry: P2 control-plane preview at `/manage`, `queries` view,
  extended with per-screen execution list, queue occupancy and the resilience
  drill.
- Runtime API entry: the accepted P2.2 execution routes plus the P2.3
  screen-bound queue-status and resilience-drill routes.
- Test data: generated non-customer `.xlsx` workbook, Mock/local capability
  providers and isolated reference fixtures. No customer endpoint, credential
  or row enters Git or evidence.

## Result Scenarios

1. Start the P2.3 preview with three screens published on distinct capability
   profiles; run dataset queries on all three concurrently and confirm each
   screen observes only its own executions, results, request IDs, latency and
   queue occupancy.
2. Run a slow long-timeout dataset on one screen under load; confirm the other
   two screens keep their latency, results and queue state unaffected.
3. Cancel one screen's running execution; confirm it ends `CANCELLED` and
   terminal, its slot is recovered, no fallback occurs and the other screens
   are unaffected.
4. Force one screen's source to fail; confirm only that screen's executions
   fail with a sanitized error while the other screens succeed, and no
   execution falls back to another source.
5. Run the resilience drill on a profile with a permission-equivalent
   fallback: injected `timeout`/`unavailable` resolves through the fallback
   decision path; injected `permission_denied` and `cancelled` are terminal
   with no fallback; every drill is audited without secrets.
6. Saturate the global queue across the three screens; confirm bounded
   `REJECTED_BACKPRESSURE` with `retryable=True`, no unbounded queue growth
   and full recovery after drain.
7. Run the capacity measurement on the reference machine; confirm the report
   records the three-screen baseline and saturation behavior as
   deployment-local guidance with no SLA language.
8. Roll back product code to accepted P2.2; confirm the P2.3 surfaces
   disappear, accepted P2.2 gates pass and the accepted P2.2 runtime is
   unchanged.

## Required Gates

- Ruff format/check, API import, complete accepted P1.1-P2.2 regression and
  the new P2.3 backend suite.
- Three-screen concurrent correctness with distinct capability profiles,
  including global-queue saturation across more than three screens, executor
  worker starvation, timeout-versus-cancel races and slot recovery.
- Single-source and single-provider failure isolation: failures, queue state,
  results and errors remain invisible to sibling screens.
- Live resilience-drill decision matrix: every injected signal against
  fallback/non-fallback and permission-equivalent/non-equivalent profiles;
  terminal no-fallback for permission, invalid and cancelled signals; audit
  evidence for every drill.
- Bounded backpressure: rejection counters, no unbounded growth, recovery
  after drain and terminal-cancellation behavior preserved from P2.2.
- Capacity measurement harness producing reproducible deployment-local
  numbers with recorded hardware and environment facts.
- UI/API RBAC, Tenant/Deployment/Site/screen non-disclosure and
  DeviceCredential-derived scope on every new P2.3 surface.
- Secret and sensitive-data scans of APIs, frontend bundle, logs, evidence
  and drill output.
- Machine-readable P2.3 contract validation in both PowerShell hosts,
  including mutated negative fixtures.
- Empty initialization and accepted-P2.2 copied upgrade with no migration;
  schema remains `p1_control_plane_001` at `005_controlled_querying`.
- Frontend type/build and a fresh 1280 by 720 browser workflow covering the
  three-screen concurrent view, drill and queue occupancy without horizontal
  overflow or console warning/error.
- Pinned package managers, Docker Compose exact-candidate smoke, lifecycle
  lint, `git diff --check`, candidate-tree fingerprint and evidence hashes.
- Separate read-only Codex review with critical negative-test reruns and zero
  blocking findings.
- Product-code rollback to accepted P2.2 commit
  `a75d3327fdc1ab4b83b0bba501d387af150353c4`; accepted P2.2 gates pass and no
  P2.3 route remains.

## Frozen Non-Scope

- No real external provider calls; Dora, ASR, TTS, RAGFlow and FVS stay
  Mock/local or unverified and blocked, and Mock evidence closes no
  real-provider risk.
- No FineReport official-plugin adapter or compatibility claim; P2.4 remains
  blocked by its external gate.
- No SLA, high-concurrency or linear-scaling promise; capacity numbers are
  deployment-local guidance measured on the reference machine only.
- No schema or migration change; no PostgreSQL control-plane store, cluster,
  distributed queue or external scheduler.
- No new provider types, no free SQL, no model-generated executable code, no
  change to accepted POC route meanings or accepted P1/P2.1/P2.2 identity,
  device-trust, inventory, release, recovery, capability-profile or
  controlled-query semantics.
- No Secret rotation/retiring window, production activation, full-loss
  recovery, external monotonic anchor or customer RPO/RTO certification.

## Immediate Failure Conditions

The immediate failure conditions in RESULT_ACCEPTANCE_STANDARD.md and the
accepted P2.2 target contract remain binding, including cross-screen
observation or influence of another screen's request, result, queue state or
error, and permission denial falling back to a more privileged source. A
failure preserves evidence, restores accepted P2.2 and blocks presentation
for user acceptance.

## Rollback Target

Product-code rollback target is accepted P2.2 commit
`a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
`aaa499de416b522e21c02f41119024296fc2c3a0`, at schema
`p1_control_plane_001` with migration `005_controlled_querying`. P2.3 adds no
migration, so no data reversal is required.

Rollback must pass accepted P2.2 gates, retain all accepted P1/P2.1/P2.2
behavior and expose no P2.3 queue-status or resilience-drill route.
