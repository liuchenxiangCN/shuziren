# P2.1 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate commit: `8f364b93b574c058cd8cd617f925107985318098`
- Candidate tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- Candidate fingerprint: `516995361810AF2D3F3FC609F4676D5A2D620216E6BB9DA305EDC57CD8622332` across 36 files
- Evidence manifest: `F89AEA6BED6B1AC91428E226C9C34DBA38F35D1764DCEA9AFA8716D8F74229F5`
  over 53 files; verification receipt:
  `B9581CA42760E22D89EB12B8238492ECA225E67A94547C8207DF5C808BDCD648`
- Gate summary: automated candidate gates `PASS`
- Independent review: `PASS`; reviewer Huygens, zero blocking and zero non-blocking findings
- User decision: `PENDING`

Sanitized raw evidence is under ignored local path
`logs/productization/P2.1-20260728-100208/`. The tracked `manifest.json` binds
the candidate, gates, independent-review history, rollback and final evidence
hashes. P2.1 remains unaccepted until the user records an explicit decision.

## Candidate Gate Results

- Candidate-scoped Ruff format/check: PASS over 13 Python files. API import
  exposed 98 routes, and the complete backend suite passed all 35 cases with
  one Starlette TestClient dependency deprecation warning.
- P2.1 target-contract validation: PASS under PowerShell 7 and Windows
  PowerShell 5.1, 206 checks each. The mutation self-test passed all 51 cases
  under each host.
- P1 target regression: PASS under both PowerShell hosts, 2,722 checks and 191
  mutation cases each.
- Profile schema, Provider/capability closure, public-metadata rejection,
  unverified activation blocking, disabled-zero-execution, terminal
  no-fallback, timeout, cancellation, backpressure, ETag, idempotency, RBAC,
  sibling non-disclosure and three-screen resolution cases: PASS.
- Empty initialization, exact accepted-P1.3 copied upgrade, repeat migration,
  migration-registry/schema-object tamper rejection and exact checksummed
  `004_capability_profiles`: PASS.
- Encrypted backup, fresh verification, staged restore, retained-store,
  reverse-integrity, restored-validation epoch and restore-then-revise
  regression cases: PASS.
- Pinned pnpm 9.15.4 TypeScript/Vite build: PASS; 19 modules transformed.
- Startup access-log inventory and runtime probe: PASS for all three P2.1
  entrypoints under both PowerShell hosts. Request targets are not written by
  those startup paths.
- Exact-candidate Docker/Compose smoke: PASS. The API and web images built,
  all 8 HTTP probes passed, migration 004 and the exact 36-table, 13-index,
  35-trigger schema were observed, no request target or Secret probe appeared
  in logs, and cleanup removed the project resources.
- Product-code rollback to accepted P1.3: PASS. The independent archive passed
  its original 22 API tests, ended at migration 003 and exposed no P2.1 route
  or schema object. The WAL-safe pre-004 copy passed all 12 verification
  checks.
- Secret-surface scan: PASS with zero exact local-root-key findings and zero
  unapproved pattern findings. Its final documentation/evidence hash is bound
  only after this acceptance package is stable.
- Candidate fingerprint, `git diff --check`, lifecycle lint and lifecycle
  self-test: PASS. The final acceptance package passed 379 lifecycle checks
  under both PowerShell hosts; the independent candidate review also passed
  its 378 checks and all 21 self-test fixtures.

## Browser Evidence Provenance

The 1280 by 720 interactive workflow was executed against source candidate
`3062b14863d1ed0a1f92f4f6a203a602cc4c6045`, not rerun against the final
candidate. It passed profile navigation, seven fixed capabilities, three
presets, 21 Provider rows, all five state meanings, `text_only` profile
creation, legacy `NOT_CONFIGURED_P2_1`, no horizontal overflow and zero
captured console warning/error.

The final candidate reuses that result through an explicit semantic rebind:
`ControlPlaneApp.vue`, `controlPlaneApi.ts` and the browser fixture are
byte-identical. The only browser-launcher delta adds `--no-access-log` to the
same Uvicorn invocation, and that launcher passed runtime probes under both
PowerShell hosts. This is not represented as an exact-candidate interactive
rerun.

## Independent Review History

Four earlier candidates were rejected and never entered user acceptance:

1. `3062b14863d1ed0a1f92f4f6a203a602cc4c6045`: `FAIL`, seven blocking
   findings covering response/public-metadata exposure, audit targets,
   migration/recovery integrity, restore replay and missing backpressure.
2. `c9cd471762eb202371c11361c69b814cecffea1c`: `FAIL`, six blocking finding
   families covering remaining metadata/log surfaces and reverse-integrity or
   replay gaps.
3. `6e43b17b4c9c75885c32b400112c985a0265b2ec`: `FAIL`, two blocking findings
   covering validation-field reflection and accepted-source schema proof.
4. `eba052678d3293448036d7426c61409063cb7c93`: `FAIL`, one blocking recovery
   finding covering mutable-epoch recomputation of historical fingerprints.

Every finding above is `REMEDIATED`. Reviewer Huygens extracted and tested an
independently hashed archive of final candidate
`8f364b93b574c058cd8cd617f925107985318098`, archive SHA-256
`C4C6A33FD7CE69EB4734ED9516942593B942E3B1E6925CDF92F07C602A3B0A74`,
12,759,040 bytes. The final result is `PASS` with zero blocking and zero
non-blocking findings.

`USER_DECISION.md` remains `PENDING`; automated completion and independent
review do not accept P2.1 or activate P2.2.
