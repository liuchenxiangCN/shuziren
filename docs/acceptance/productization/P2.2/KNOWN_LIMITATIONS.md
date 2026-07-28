# P2.2 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_PREPARATION`
- Candidate commit/tree: pending immutable candidate record
- User decision: `PENDING`

## Frozen Limits

- P2.2 is a local development-preview candidate, not accepted or production
  activated.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 passed isolated deployment-local
  tests. This is not a compatibility promise for other versions, operating
  systems, networks or customer configurations; product certification remains
  `UNVERIFIED`.
- The control-plane store remains SQLite. There is no cluster, distributed
  queue, external control-plane database, measured throughput or SLA.
- The worker pool and per-screen bound prove correctness/backpressure for this
  result, not P2.3 capacity certification.
- Successful rows are retained only in the current process, capped at 256
  terminal jobs. Eviction, process restart or restore keeps sanitized metadata
  but requires the caller to rerun the dataset.
- Secret rotation/retiring windows and external key custody are outside P2.2.
  Database credentials are immutable per source; replacement uses a new
  source.
- Excel supports only `.xlsx`, one approved worksheet, scalar cells and
  equality filters. Formulas, macros, ActiveX/OLE/binary parts, external
  relationships or hyperlinks, `.xls`, CSV and arbitrary paths are rejected.
- Database querying supports one administrator-approved parameterized
  read-only statement. There is no free SQL, stored procedure, writeback,
  federated/cross-source query or model-generated query/summarization.
- No FineReport official-plugin request is made. Plugin API, authentication,
  permission inheritance and exact compatibility remain the P2.4 external
  gate.
- The browser workflow proves local source/dataset administration and
  unpublished zero-execution behavior. Full published execution is covered by
  backend browser/device integration tests.
- The backend suite emits one Starlette TestClient dependency deprecation
  warning.

User acceptance cannot turn deployment-local evidence or an unlisted customer
environment into product certification.
