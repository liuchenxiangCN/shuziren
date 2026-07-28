# P2.2 Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `a75d3327fdc1ab4b83b0bba501d387af150353c4`
- Candidate tree: `aaa499de416b522e21c02f41119024296fc2c3a0`
- Logical schema: `p1_control_plane_001`
- Latest migration: `005_controlled_querying`
- Migration checksum SHA-256:
  `d6661b95fcf08e478c29ea20314f3dc158be88433a7fa3c3c86d119b33cfbcf4`

## Additive Structures

| Structure | Purpose |
| --- | --- |
| `query_secret_records` | Mutable authority envelope for one write-only database credential |
| `query_secret_versions` | Immutable authenticated Secret ciphertext and exact AAD |
| `query_sources` | Site-owned source state, qualification and strong revision |
| `query_source_versions` | Immutable source config and exact workbook/Secret reference |
| `query_datasets` | Site-owned dataset state, head and strong revision |
| `query_dataset_versions` | Immutable typed definition, allowlists and bounds |
| `config_draft_query_assignments` | Exact dataset versions for one draft revision |
| `query_validation_records` | Query sidecar evidence bound to P1/P2.1 validation |
| `release_target_query_snapshots` | Immutable per-screen applied-query contract |
| `query_executions` | Sanitized asynchronous execution metadata only |

Immutable versions, assignments and release snapshots have update/delete
triggers. Source/dataset envelopes may only be disabled; historical versions
never change. Execution rows store parameter names plus a keyed digest, never
parameter values or result rows.

## Secret And Workbook Storage

Database credentials are encrypted using AES-256-GCM material derived for
`SECRET_ENVELOPE_ENCRYPTION`. The stored record binds key ID, unique nonce,
ciphertext, canonical AAD and its SHA-256. There is no ordinary decryption/read
API.

Validated `.xlsx` bytes are retained in the immutable source version BLOB so
the existing encrypted online backup captures the exact workbook. A
server-owned working copy is not runtime authority and arbitrary paths are
rejected.

## Recovery

Snapshot validation checks all ten tables, source config/workbook hashes,
Secret AAD/ciphertext references, dataset definition hashes, assignment
closure, validation binding, release snapshots and execution metadata.
Backup creation, fresh verification and staged restore use this validation.
Online restore reconciles current matching source/dataset/Secret authority
instead of resurrecting older enabled state. Restore refuses cutover while a
controlled-query worker is live, terminalizes nonterminal rows from the
restored snapshot as `QUERY_RESTORE_INTERRUPTED`, and clears pre-cutover
in-memory results only after a quiescent cutover. Startup similarly marks
orphaned `QUEUED`/`RUNNING` rows as `QUERY_PROCESS_RESTARTED`.

The exact accepted-P2.1 copied upgrade, repeat migration and WAL-safe pre-005
copy are executable regression cases. Product rollback uses accepted P2.1 code
and that pre-005 copy; it must expose no P2.2 route or table.
