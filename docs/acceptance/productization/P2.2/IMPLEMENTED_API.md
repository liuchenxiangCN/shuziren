# P2.2 Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_PREPARATION`
- Candidate commit/tree: pending immutable candidate record
- API version: `v1`
- User decision: `PENDING`

This file describes the observable P2.2 candidate. It does not claim user
acceptance or production certification.

## QuerySource And Dataset Routes

The candidate adds 18 control-plane/device routes:

- browser list, create, read, test and disable for QuerySources;
- browser list, create, read and disable for immutable QueryDatasets;
- exact dataset-version assignment to a draft revision;
- screen-bound browser catalog, start, poll and cancel;
- credential-derived device catalog, start, poll and cancel.

Technical writes require existing session, Origin, CSRF and
`config.edit_technical` controls. Database sources additionally require
`secret.write`. Envelope disable and source test use strong `If-Match`.
Create, assignment, start and cancel require `Idempotency-Key`; changed-command
reuse is rejected.

## Closed Inputs And Outputs

Source creation accepts one of `EXCEL`, `MYSQL`, `ORACLE` or `POSTGRESQL`.
Database connection material is write-only and never returned. Excel accepts
only bounded base64 `.xlsx` content and no server path.

Dataset creation accepts immutable metadata, typed parameter schema, ordered
output fields, row/timeout bounds and an engine-specific approved definition.
Database definitions contain the only SQL accepted by P2.2 and require a
single parsed read-only template plus exact relation allowlists. Unknown
functions, custom operators, user-defined casts and sequence
`NEXTVAL`/`CURRVAL` expressions are rejected. Runtime start accepts only
`parameters`; unknown fields such as SQL/template/relation/source or ownership
selectors fail schema validation.

Successful runtime output contains the dataset/source labels and opaque IDs,
metric/time-scope/permission evidence, request ID, latency, ordered fields and
bounded rows. It never contains a connection, Secret or SQL template.

## Release And Recovery Integration

Draft assignment advances the existing immutable revision axis and invalidates
stale validation/preview/approval evidence. Validation binds exact query
versions. NORMAL ReleaseTargets receive immutable query snapshots; forward
rollback copies the historical snapshot. Applied state changes only after the
existing device acknowledgement.

The existing backup, verify, restore-plan and restore-execute APIs retain their
route meaning. Their candidate implementation now validates and restores the
P2.2 data graph while preserving current source/dataset authority.
