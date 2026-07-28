# P2.2 Controlled Querying Target Contract

## Document Status

- Lifecycle: `TARGET_NOT_IMPLEMENTED`
- Scope: incremental P2.2 Excel, MySQL, Oracle and PostgreSQL QuerySource contract
- Contract version: `p2.2-controlled-querying-v1`
- Last reviewed: 2026-07-28
- Machine-readable contract:
  [p2-2-controlled-query-contract.json](p2-2-controlled-query-contract.json)

This contract freezes P2.2 before runtime implementation. It does not claim
that a QuerySource, dataset, connector or execution path is implemented or
accepted. Implemented evidence belongs only in the P2.2 acceptance package.

## Result Boundary

P2.2 adds a controlled-query sidecar to the accepted P2.1 runtime:

- Site-owned Excel, MySQL, Oracle and PostgreSQL QuerySources;
- encrypted database connection material that is write-only after submission;
- immutable approved dataset definitions with typed parameters, output-field
  allowlists, row limits and timeouts;
- draft-revision assignments and immutable per-ReleaseTarget query snapshots;
- screen-bound browser and DeviceCredential execution;
- normalized source, metric, time-scope, permission, latency and request
  evidence;
- bounded concurrency, cancellation, timeout, backpressure and per-screen
  failure isolation from the first connector batch.

P2.2 does not add free SQL, model-generated SQL, write-capable datasets, the
FineReport official-plugin adapter, an external control-plane store or
production activation.

## QuerySource Contract

Every QuerySource belongs to exactly one Tenant, Deployment and Site and has
one immutable V1 source version. Editing connection or workbook content creates
a replacement QuerySource; it never changes a published historical snapshot.
The envelope may be disabled with a strong ETag. Disabled sources execute
nothing, including from an older applied release.

The closed engine set is:

| Engine | Adapter | P2.2 meaning |
| --- | --- | --- |
| `EXCEL` | bounded `.xlsx` reader | real local workbook execution after validation |
| `MYSQL` | PyMySQL | live execution only after a successful deployment-local connection test |
| `ORACLE` | python-oracledb thin mode | live execution only after a successful deployment-local connection test |
| `POSTGRESQL` | psycopg | live execution only after a successful deployment-local connection test |

Database connection input is accepted only by the dedicated QuerySource write
route, encrypted immediately with the `SECRET_ENVELOPE_ENCRYPTION` purpose key
and stored as authenticated ciphertext. Ordinary reads, lists, audit, support
output, frontend state and evidence expose only `configured`, engine,
non-sensitive labels, a fingerprint suffix and qualification state. They never
return a host, port, database, username, password, DSN, ciphertext or key.

Excel registration accepts one `.xlsx` workbook as bounded base64 transport.
The service validates ZIP structure, workbook limits, worksheet names and
formula absence before placing the file under a server-owned source root. It
does not accept an arbitrary server path, macro-enabled workbook, external
link, formula or embedded executable content.

`AVAILABLE` means the exact source version passed the current
deployment-local test. It is not a claim that an unlisted database/server,
driver, operating system or customer combination is product-certified.
`UNVERIFIED` and `DISABLED` are distinct and visible.

## Approved Dataset Contract

Every dataset is immutable and belongs to the same Site as its QuerySource.
It contains only:

- display name, metric definition, time-scope description and freshness label;
- typed parameter schema using `string`, `integer`, `number`, `boolean` or
  `date`;
- an ordered output-field allowlist;
- row limit from 1 through 500 and timeout from 100 through 120000 ms;
- for Excel, one worksheet plus equality filters over allowlisted columns;
- for a database, one administrator-approved, parameterized read-only
  `SELECT`/`WITH ... SELECT` template plus an exact relation allowlist.

Database templates are parsed server-side for the selected dialect. They must
be one statement, may contain only named bind parameters declared in the
parameter schema, and may reference only declared relations. Comments,
semicolon chaining, DDL, DML, transaction/control commands, dynamic execution,
file/network functions and unknown constructs are rejected. Runtime callers
send only a dataset ID and parameter values; a SQL/template field is rejected
by the closed request schema.

Result columns outside the output allowlist fail closed. Values are normalized
to JSON-safe scalar types, bounded by the row limit and never sent to a model
by this batch.

## Release And Permission Binding

P2.2 does not mutate the accepted `p1_screen_config_v1` or
`p2_capability_profile_v1` schemas. It adds:

- an immutable draft-revision query assignment;
- a query validation record bound to the accepted P1/P2.1 validation record;
- one immutable query snapshot per ReleaseTarget;
- forward-rollback copying of the exact historical snapshot.

The P2.1 `controlled_query` descriptor remains unverified by itself. A P2.2
query sidecar makes it executable only when all of the following are true:

1. the applied capability snapshot enables `querying` with
   `controlled_query` as the primary Provider and no fallback;
2. the applied query snapshot contains the requested exact dataset and source
   versions;
3. the source and dataset envelopes are active;
4. the source version passed its deployment-local test;
5. the caller is bound to the same Tenant, Deployment, Site and screen.

Browser execution requires the existing authenticated session plus
screen-scoped `config.read`. Device execution derives screen scope only from
the active DeviceCredential and accepts no ownership selector. Permission
denial, invalid parameters, unauthorized datasets and cancellation are
terminal and never fall back.

## Execution And Evidence

Execution is asynchronous and bounded. Starting a request returns an opaque
execution ID. The caller polls its own screen-bound result or cancels it.
The closed states are `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`,
`CANCELLED` and `REJECTED_BACKPRESSURE`.

The runtime enforces a bounded global queue, bounded per-screen work and at
least three independent worker slots. Cancellation is propagated to the
adapter where supported; timed-out or cancelled results are discarded and
never trigger fallback.

A successful response contains:

- source and dataset labels and opaque IDs;
- metric definition, time-scope description and normalized requested scope;
- permission subject type and opaque screen ID;
- provider/engine, deployment-local qualification label and cache status;
- latency, request ID, row count, ordered fields and bounded result rows.

Audit records contain request/dataset/source IDs, screen and actor metadata,
parameter names plus a keyed/canonical digest, outcome, latency and row count.
They contain no parameter values, result rows, connection material or SQL.

## Recovery Boundary

Migration `005_controlled_querying` is additive to accepted schema
`p1_control_plane_001`. QuerySource ciphertext, immutable definitions,
assignments, snapshots and non-sensitive audit metadata are included in the
existing encrypted online backup.

Online restore preserves the current QuerySource/Dataset enabled state and
current Secret ciphertext instead of resurrecting an older authority state.
P2.2 proves an exact pre-`005` WAL-safe rollback copy against accepted P2.1.
External anti-rollback anchors, Secret rotation/retiring windows, full-loss
recovery and production custodian ceremonies remain later production gates.

## Immediate Failure Conditions

- Runtime accepts SQL, a template, relation, field or ownership selector from a
  business/device execution request.
- A database template can write, chain statements, escape parameter binding or
  reference a non-allowlisted relation.
- A disabled, untested, cross-Site or unbound source/dataset executes.
- A result contains a non-allowlisted field or exceeds its row limit.
- A Secret, DSN, endpoint, SQL template, workbook content, parameter value or
  result row enters an ordinary read, audit, log, frontend bundle or evidence.
- Permission denial, invalid input, unauthorized dataset or cancellation
  triggers fallback.
- One screen can observe, cancel or influence another screen's request,
  result, queue state or error.
- A source/dataset definition or published query snapshot mutates in place.
- Migration, backup/restore or product-code rollback loses the latest accepted
  P2.1 recovery point.

## Frozen Non-Scope

- No FineReport official-plugin call, undocumented API, authentication,
  permission inheritance or version certification; P2.4 remains gated.
- No Dora, LLM or model-generated query/summarization path.
- No arbitrary Excel/CSV upload, `.xls`, macro, formula, external link or
  arbitrary local/network path.
- No joins across QuerySources, federated query, writeback, stored procedure,
  dynamic SQL, user SQL or dataset designer that bypasses the closed contract.
- No P2.3 integrated capacity certification, high-throughput SLA or cluster.
- No Secret rotation, predecessor retiring window, external key service,
  production activation, PostgreSQL control-plane store, full-loss recovery or
  customer RPO/RTO certification.
