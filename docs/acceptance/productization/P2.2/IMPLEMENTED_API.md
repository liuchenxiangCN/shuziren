# P2.2 Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `a75d3327fdc1ab4b83b0bba501d387af150353c4`
- Candidate tree: `aaa499de416b522e21c02f41119024296fc2c3a0`
- API version: `v1`
- User decision: `通过` without conditions or scope reduction on 2026-07-28

This file describes the accepted P2.2 development-preview result. Acceptance
does not claim production certification.

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
