# P2.2 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Batch: `P2.2 Controlled Excel And Database Querying`
- State: `CANDIDATE_PREPARATION`
- Activated by: explicit user instruction `完成P2.2`
- Activated at: 2026-07-28
- Base accepted commit: `8f364b93b574c058cd8cd617f925107985318098`
- Base accepted tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- Candidate commit/tree: pending immutable candidate record
- Logical schema: `p1_control_plane_001`
- Planned migration: `005_controlled_querying`
- Target contract:
  [CONTROLLED_QUERYING.md](../../../product/contracts/CONTROLLED_QUERYING.md)
- User decision: pending; silence is not acceptance

## User-Visible Outcome

P2.2 will let an administrator register bounded Excel, MySQL, Oracle and
PostgreSQL QuerySources and immutable approved datasets. A business operator
or enrolled screen selects only a published dataset and supplies typed
parameters; neither can submit SQL.

Results will show source, metric definition, requested time scope, permission
subject, deployment-local qualification, latency, request ID, fields and
bounded rows. Connection tests and query failures will return stable,
understandable, sanitized errors.

## Entry Point And Test Data

- Management entry: P2 control-plane preview at `/control-plane`.
- Runtime API entry: the P2.2 control-plane and device dataset routes frozen in
  the target contract.
- Test data: generated non-customer `.xlsx` workbook plus isolated reference
  database fixtures. No customer endpoint, credential or row enters Git or
  evidence.

## Result Scenarios

1. Register and test one generated `.xlsx` source; create an approved dataset
   and query it using only typed parameters.
2. Register MySQL, Oracle and PostgreSQL sources; confirm a successful exact
   reference connection is labelled deployment-local, while unavailable or
   untested combinations remain `UNVERIFIED` with a sanitized reason.
3. Create one immutable database dataset with named parameters, relation and
   output-field allowlists; verify runtime exposes no SQL or connection data.
4. Assign different dataset sets to three screen drafts, publish and
   acknowledge them, then confirm each screen sees only its applied snapshot.
5. Run three screen-bound queries concurrently and confirm results, request
   IDs, queue state, cancellation and failures remain isolated.
6. Submit SQL-shaped runtime fields, injection-shaped parameter values,
   unauthorized fields/datasets and a cross-screen execution ID; confirm safe
   denial with no write and no disclosure.
7. Timeout, cancel and saturate one source; confirm bounded backpressure,
   terminal cancellation/permission failures and no fallback.
8. Create, verify and restore an encrypted backup; confirm QuerySource
   authority does not roll back, then prove product/data rollback to accepted
   P2.1 with no P2.2 route.

## Required Gates

- Ruff format/check, API import, complete accepted P1.1-P2.1 regression and the
  P2.2 backend suite.
- Machine-readable P2.2 target-contract validation and negative fixtures.
- Empty initialization, accepted-P2.1 copied upgrade, repeat migration,
  migration-checksum tamper rejection and WAL-safe pre-`005` rollback copy.
- Closed source/dataset schemas, engine/dialect match, typed parameters,
  relation/field allowlists, row limit and timeout bounds.
- SQL parser negatives for free SQL, statement chaining, comments, writes,
  DDL, procedures, dynamic execution and undeclared binds/relations.
- Injection values proving parameter binding and no data/schema mutation.
- Dedicated Secret write, authenticated encryption, no-readback, wrong-key/AAD
  failure, API/audit/SQLite/backup/frontend/evidence Secret scans.
- Excel ZIP/workbook size, worksheet, formula, macro, external-link, traversal
  and arbitrary-path negatives.
- UI/API RBAC, Tenant/Deployment/Site/screen non-disclosure and
  DeviceCredential-derived scope.
- Strong ETag, exact idempotency replay, changed-command replay and immutable
  QuerySource/Dataset/snapshot tests.
- Draft assignment invalidation, release snapshot, publication,
  acknowledgement, historical immutability and forward rollback.
- Disabled/untested/unbound zero execution and terminal
  permission/invalid/cancelled no-fallback behavior.
- Three-screen concurrency, timeout, cancellation, bounded backpressure and
  single-source failure isolation.
- Encrypted backup/verify/restore with P2.2 hash/reference validation and
  current source/dataset/Secret authority reconciliation.
- Frontend type/build and 1280 by 720 browser workflow without horizontal
  overflow or console warning/error.
- Pinned package managers, Docker Compose exact-candidate smoke, dependency and
  Secret scans, lifecycle lint, `git diff --check`, candidate-tree fingerprint
  and evidence hashes.
- Separate read-only Codex review with critical negative-test reruns and zero
  blocking findings.
- Product-code rollback to accepted P2.1 plus a verified exact pre-`005`
  online backup; accepted P2.1 tests pass and no P2.2 route exists.

## Frozen Non-Scope

- No FineReport official-plugin adapter or compatibility claim; P2.4 remains
  blocked by its external gate.
- No model-generated SQL, user SQL, query summarization by Dora/LLM, executable
  action or model-generated code.
- No `.xls`, CSV, macro, formula, external Excel link, arbitrary path, writeback,
  stored procedure, federated query or cross-source join.
- No Secret rotation/retiring window, P2.3 capacity/SLA certification,
  production activation, PostgreSQL control-plane store, full-loss recovery,
  external monotonic anchor or customer RPO/RTO certification.
- No change to accepted POC route meanings or P1/P2.1 identity, device trust,
  inventory, release, recovery and capability-profile semantics.

## Immediate Failure Conditions

The immediate failure conditions in the frozen target contract are binding. A
failure preserves evidence, restores accepted P2.1 and blocks presentation for
user acceptance.

## Rollback Target

Product-code rollback target is accepted P2.1 commit
`8f364b93b574c058cd8cd617f925107985318098`, tree
`7c277e32b6419bd3720591c454e8282d94f081ec`, plus a verified WAL-safe exact
pre-`005` database backup at migration `004_capability_profiles`.

Rollback must pass accepted P2.1 gates, retain all accepted P1/P2.1 behavior
and expose no P2.2 QuerySource, dataset or query-execution route.
