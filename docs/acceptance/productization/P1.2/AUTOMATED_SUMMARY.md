# P1.2 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `2ddd2116aad19babc9acbfde1110802eb3187c2b`
- Candidate tree: `565dbb3567e2a4ae5b872177d97449120477fe8c`
- Candidate fingerprint: `16D8840CBF876BB08A5A33F92A7C30AC1E3CFA1DA28F599AE374AE447DEB87E1` across 29 files
- Gate summary: PASS
- Independent review: PASS; zero blocking and zero non-blocking findings
- User decision: Pending

Sanitized raw evidence is under ignored local path
`logs/productization/P1.2-20260727-222737/`. The tracked
[manifest.json](manifest.json) will be the machine-readable final gate record.

## Candidate Gate Results

- Scoped Ruff format/check and API import: PASS.
- Pytest: PASS, 14 cases. They retain the complete accepted P1.1 suite and add
  empty/repeat/copied/failed/tampered/reordered/missing migration checks,
  three-screen fixture/UUIDv7/pagination, role/resource-scope and sibling
  nondisclosure, Secret/DSN rejection, idempotency mismatch, duplicate
  slug/instance, stale/concurrent ETags, cross-Site group denial, foreign keys,
  immutable audit and no-delete-cascade checks.
- Pinned pnpm 9.15.4 TypeScript/Vite build: PASS; 19 modules transformed.
- Browser workflow at 1280 by 720: PASS. Initial three-screen inventory,
  isolated Screen 2 update, Screen 4 plus first DigitalHumanInstance and auditor
  read-only behavior were observed with no horizontal overflow or captured
  console warning/error.
- Accepted-P1.1 copied upgrade: PASS. All original enrollment/family/credential
  rows and the original 55-event audit prefix remained exact; one sanitized
  migration event was appended; repeat initialization left the database file
  hash unchanged.
- Accepted-P1.1 runtime rollback: PASS. Its ten original tests pass, migration
  remains 001, P1.2 Site/Screen list routes return not found and the accepted
  device runtime route remains present.
- Secret scan: PASS across candidate files, the frontend bundle, SQLite copies
  and 343 final evidence files. Exact operational Secret findings and unapproved
  pattern findings are both zero; four classified matches are synthetic
  rejection fixtures.
- Docker/Compose: PASS for image build, generated-env database selection,
  alternate-port API/web runtime, migration 002 probe and clean shutdown.
- P1 target-contract validator: PASS under PowerShell 7 and Windows PowerShell
  5.1, 2,722 checks each. All 191 contract self-test cases pass.
- Repository lifecycle lint: PASS under both PowerShell hosts. `git diff
  --check`, PowerShell parsing and candidate fingerprint generation pass.

The first independent review of candidate
`2f0c4f3a4889b41910c4dc1397df4394762784dd` correctly found blocking
Secret/DSN, SCREEN-scoped audit and migration fail-closed gaps. That candidate
is superseded. The same reviewer independently recomputed the final candidate
fingerprint, reran the complete backend and critical negative tests, verified
all 24 manifest hashes, Docker/browser/rollback evidence and both lifecycle
lints, and returned PASS with zero findings.
