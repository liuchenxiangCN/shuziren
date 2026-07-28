# P1.3 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Candidate tree: `04bcbb940fbedb5fbb8957e538f46a4422e15db2`
- Candidate fingerprint: `8cf8cdb380f849b947a76abeef2ff895fb79f7696effbb1abbdf9bdc0bb04e55` across 29 files
- Gate summary: automated candidate gates `PASS`
- Independent review: `PASS`; zero blocking and zero non-blocking findings
- User decision: Pending

Sanitized raw evidence is under ignored local path
`logs/productization/P1.3-20260728-final-0f210cf/`. The tracked
`manifest.json` binds the final gate and raw-evidence hashes.

## Candidate Gate Results

- Ruff format/check and API import: PASS.
- Complete backend integration suite: PASS, 22 cases. The suite includes all
  accepted P1.1/P1.2 behavior and P1.3 state-machine, RBAC, ETag,
  idempotency, immutable release, three-screen publication, device
  acknowledgement, rollback, backup/restore, retention and negative cases.
- Pinned pnpm 9.15.4 TypeScript/Vite build: PASS; 19 modules transformed.
- Browser workflow at 1280 by 720: PASS. The release center completed draft,
  `MOCK_PASSED` validation/preview, different-user approval and typed
  publication through `WAITING_FOR_DEVICE` with no horizontal overflow or
  captured console warning/error. The final repairs changed only backend/test
  files; the browser fixture, frontend and successful UI path remained
  byte-identical.
- Exact accepted-P1.2 copied upgrade: PASS. The source hash remained unchanged,
  the copy reached the exact checksummed
  `003_publish_rollback_recovery` registry, retained three bindings with clean
  foreign keys, accepted nullable fingerprint fields only for `INVALID`
  validation rows and remained byte-identical on repeat initialization.
- Backup source-integrity probe: PASS. A foreign-key-orphan source returned
  `503 STORAGE_UNAVAILABLE` and produced zero backup records, final bundles or
  staging bundles.
- Recovery-duration and cutover probe: PASS. The local preview created a
  verified 39,117-byte ciphertext bundle in 49 ms and restored three bindings
  in 26 ms with clean foreign keys and a retained previous store. A mutation
  racing cutover failed explicitly; no successful write disappeared. These
  measurements do not certify production recovery or a customer RPO/RTO.
- Three-day retention probe: PASS. One expired detail row was deleted while
  four users, one device-credential family, one release, one publication and
  all 21 SecurityAuditEvent rows remained.
- Exact-candidate Docker/Compose: PASS. API health and `/manage` returned 200;
  migration 003, three screens, three bindings and zero foreign-key errors were
  observed; Compose shut down cleanly.
- Accepted-P1.2 runtime rollback: PASS. Its 14 original integration tests pass,
  migration remains 002, P1.2 inventory remains present and P1.3 draft/backup
  routes are absent. The runtime archive and verified pre-003 database copy are
  retained with SHA-256 evidence.
- P1 target-contract validation: PASS under PowerShell 7 and Windows
  PowerShell 5.1, 2,722 checks each. The unchanged 191-case contract self-test
  evidence passes and is transparently marked as reused for the exact final
  backend-only delta.
- Candidate fingerprint generation and PowerShell parsing under both hosts:
  PASS.
- Final Secret-surface scan: PASS with zero exact local-root-key findings and
  zero unapproved pattern findings.

## Independent Review History

The same independent reviewer rejected candidate
`93bae87f028f50d0f1abd09c5d6c458490d52273` with four blocking findings:
whole-bundle substitution was not bound to the requested backup record,
restore could lose a mutation racing cutover, expected invalid validation did
not persist HTTP 200 evidence, and full-spec replacement required permissions
for unchanged leaves.

Candidate `20a2be319fd74f689c8a581734b1cb3b21e6b0a3` closed all four. The second review
found one new blocking path: backup creation could publish `VERIFIED` before
applying the complete snapshot checks later used by fresh verification.

The final candidate validates the source snapshot before logical export,
encryption, atomic publication or `backup_records` insertion. The same reviewer
independently reran all five repaired paths, the complete 22-case backend suite,
Ruff, API import, Git diff, lifecycle lint and the 191-case target-contract
self-test. The review returned PASS with zero blocking and zero non-blocking
findings, so the candidate may enter explicit user acceptance.
