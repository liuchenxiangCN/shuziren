# P2.2 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `USER_DECISION_PENDING`
- Candidate commit: `a75d3327fdc1ab4b83b0bba501d387af150353c4`
- Candidate tree: `aaa499de416b522e21c02f41119024296fc2c3a0`
- Candidate fingerprint:
  `8A1A369FA328F6A516D9A36AD5F36C314629D2E683BBF38304510521817D357D`
  over 47 files
- Automated gates: `PASS`
- Independent review: `PASS`; zero blocking and zero non-blocking findings
- User decision: `PENDING`

## Passed Results

- Candidate-scoped Ruff format/check passed over 15 Python files; the API
  imports with 116 routes.
- Complete backend regression passed 67 cases; three environment-gated
  database cases are separate.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 exact ephemeral read-only
  adapters each rejected DB-side INSERT, qualified the exact source, executed
  a published screen/device-bound dataset, returned two bounded rows and
  preserved the source table row/schema invariants after an injection probe.
- P2.2 machine contract passed 47 checks and six mutation fixtures under
  PowerShell 7 and Windows PowerShell 5.1.
- Pinned pnpm 9.15.4 TypeScript/Vite build passed with 19 modules.
- Fresh 1280 by 720 browser rerun passed Excel registration, list refresh,
  qualification, immutable dataset creation, unpublished zero execution and
  draft dataset-assignment display. Document width was 1265 pixels and the
  console contained zero warning/error entries.
- The browser rerun found and remediated one blocking list-projection defect
  before candidate creation; the repaired flow passed from a fresh fixture.
- Migration/repeat/pre-005 copy, closed SQL/OOXML/Secret negative tests, three
  distinct screen releases with concurrent execution and one-source failure
  isolation, 100 ms Excel/database-path timeout, queued-cancel slot recovery,
  current-authority recheck, terminal audited backpressure and
  backup/verify/restore authority reconciliation pass in the backend suite.
- Restore rejects live controlled-query workers; restored nonterminal
  execution rows are sanitized to terminal failure, and startup reconciles
  orphaned nonterminal metadata.
- Independent review rejected candidate
  `78b5af301a1c57915a4535d3decc11c59b79eba7` after finding Oracle sequence
  expressions, PostgreSQL custom operators and user-defined casts outside the
  function-only SQL allowlist. The replacement validator rejects those AST
  forms; 21 cross-dialect SQL-negative cases and the full/real-adapter suites
  pass after the repair.

Exact-candidate Compose, Secret scan and accepted-P2.1 rollback passed.
Accepted P2.1 ran its 35 original tests, retained migration
`004_capability_profiles` and exposed no P2.2 route/table. Raw evidence is
under `logs/productization/P2.2-20260728-170650`; its verified manifest hashes
67 files with zero missing, unexpected or mismatched entries.
