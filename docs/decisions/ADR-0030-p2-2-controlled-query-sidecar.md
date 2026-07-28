# ADR-0030: P2.2 Controlled Querying Sidecar

## Status

Proposed

P2.2 implementation and verification may prove this candidate, but only an
explicit user decision can change this ADR to `Accepted`.

## Date

2026-07-28

## Context

Accepted P2.1 can select `controlled_query`, but intentionally has no
QuerySource, dataset or execution path. The accepted P1.3 base configuration
and P2.1 capability profile are immutable compatibility boundaries. P2.2 must
add Excel and database querying without adding SQL to business/device input,
placing Secrets in ordinary reads or mutating a historical release.

## Decision

1. Migration `005_controlled_querying` is additive and leaves
   `p1_screen_config_v1` and `p2_capability_profile_v1` unchanged.
2. QuerySource and QueryDataset are Site-owned envelopes with immutable
   versions. Published snapshots bind exact source and dataset versions.
3. Database credentials are accepted only on the source write route and are
   stored as authenticated ciphertext under `SECRET_ENVELOPE_ENCRYPTION`.
   Ordinary reads expose only bounded non-sensitive qualification metadata.
4. Excel content is accepted only as a bounded `.xlsx`, validated against
   active content and stored in the encrypted backup domain. Runtime reads the
   immutable database-held workbook bytes, not a caller-selected path.
5. Database templates are administrator-approved, server-parsed, single
   read-only statements with exact relation, bind and output allowlists.
   Runtime callers submit only a dataset ID and typed values.
6. Draft query assignment shares the existing draft revision axis. NORMAL
   releases snapshot the exact assignment; forward rollback copies the
   historical snapshot.
7. Execution is asynchronous, screen-bound and bounded by global/per-screen
   slots. Start and cancel are idempotent. Permission, validation and
   cancellation failures are terminal and have no fallback.
8. `AVAILABLE` records exact deployment-local evidence only. Product
   certification remains `UNVERIFIED`, including the FineReport plugin.
9. Online restore validates all P2.2 hashes and references while preserving
   current source/dataset authority. It refuses a live controlled-query worker,
   terminalizes nonterminal restored rows and clears pre-cutover in-memory
   results after quiescent cutover. The verified product/data rollback target
   remains accepted P2.1 plus a WAL-safe pre-`005` copy.

## Consequences

- Business users and devices cannot submit SQL, connection selectors or
  ownership selectors.
- Historical releases remain stable while disabling a live envelope stops
  execution immediately.
- Query results are held only in the bounded in-memory job result and are not
  written to SQLite or audit.
- The control plane remains SQLite; P2.3 capacity/SLA certification, Secret
  rotation and production activation are deferred.

## Follow-Up

- Explicit P2.2 acceptance may mark this ADR `Accepted`.
- P2.3 may measure integrated resilience and capacity without widening this
  permission boundary.
- P2.4 remains blocked on official FineReport plugin evidence.
