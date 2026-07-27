# P1.1 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate: `8c18e5d6b10081eaaf608436440046894d235d46`
- Candidate tree: `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`
- Gate summary: required local gates PASS; Docker build/runtime smoke PASS; final-candidate independent review PASS
- User decision: `通过` on 2026-07-27

Sanitized raw evidence is under ignored local path `logs/productization/P1.1-20260727-reenroll/`. The tracked [manifest.json](manifest.json) is the machine-readable gate record.

## Candidate Gate Results

- Ruff format/check and API import: PASS.
- Pytest: PASS, ten tests. They cover empty and repeat schema initialization, named-migration checksum tamper rejection, frozen key-purpose membership, production-like no-auto-bootstrap, password policy, generic authentication failure, progressive lockout, duplicate-cookie denial, CSRF/session expiry and idempotent reauthentication, exact RBAC, different-user approval, stale ETag, action/enrollment/successor terminal expiry, cross-screen denial, AEAD one-time replay binding and destruction, unreachable one-time-material cleanup, exact device-rotation replay, stale pre-issued enrollment rejection, fresh-family re-enrollment after `REVOKED` and `REENROLL_REQUIRED`, partial active-family uniqueness, family revocation, SHA-256 audit-chain recomputation and plaintext scans.
- Vue TypeScript check and Vite production build: PASS; 19 modules transformed.
- Browser workflow at 1280 by 720: PASS for administrator login, exact role catalog, different-user user creation, auditor denial/audit read, enrollment/claim, successor activation, family hard revocation, fresh-family re-enrollment and reauthentication. Database evidence preserved the old `REVOKED` family and showed one distinct new `ACTIVE` family. No horizontal overflow or browser console warning/error was observed.
- Browser screenshot: PASS; `audit-role-preview.png` SHA-256 `80b11a1706e734fe7dcc9fc8083a841b7532760ebd31582d9472f4b91c20aacb`.
- Candidate-diff, frontend-bundle and text-evidence secret scan: PASS with zero findings; the screenshot was also visually checked for credential material.
- P1 target-contract validator: PASS under PowerShell 7 and Windows PowerShell 5.1, 2,722 checks each.
- Repository lifecycle lint: PASS under PowerShell 7 and Windows PowerShell 5.1, 314 checks each.
- `git diff --check` and tracked candidate worktree check: PASS.
- Rollback to P1.0 commit `6ec4cdbf03ddf64796c9f09d3a5950a7a2ee8758`: PASS in a detached temporary worktree.
- Docker / Compose preview: PASS after adding the missing workspace package declaration required by the pinned pnpm 9.15.4 build. Isolated alternate-port probes returned HTTP 200 for `/api/health` and `/manage`; image IDs and clean Compose shutdown are recorded in the manifest.

The first independent review correctly returned `FAIL` for candidate `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e`. The second review confirmed those repairs and returned `FAIL` for `45dd8ff9455c1ab62a408d26c15f15a14256341b` only because terminal-family history could not coexist with a fresh replacement family. Both dispositions are recorded in [manifest.json](manifest.json). The same reviewer completed a third read-only review of the final candidate with `PASS`, zero blocking findings and zero non-blocking findings. The existing Starlette `TestClient` emitted one dependency deprecation warning; it did not affect the ten passing tests. The user explicitly accepted the result on 2026-07-27.
