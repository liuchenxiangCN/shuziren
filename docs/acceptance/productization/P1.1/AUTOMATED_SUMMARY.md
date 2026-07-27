# P1.1 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_FROZEN_REVIEW_PENDING`
- Candidate: `45dd8ff9455c1ab62a408d26c15f15a14256341b`
- Candidate tree: `8b730d5e1122515ee242887a6a5b9a8ab86d633b`
- Gate summary: required local gates PASS; optional Docker preview Blocked; repaired-candidate independent review Pending

Sanitized raw evidence is under ignored local path `logs/productization/P1.1-20260727-repair/`. The tracked [manifest.json](manifest.json) is the machine-readable gate record.

## Candidate Gate Results

- Ruff format/check and API import: PASS.
- Pytest: PASS, ten tests. They cover empty and repeat schema initialization, named-migration checksum tamper rejection, frozen key-purpose membership, production-like no-auto-bootstrap, password policy, generic authentication failure, progressive lockout, duplicate-cookie denial, CSRF/session expiry and idempotent reauthentication, exact RBAC, different-user approval, stale ETag, action/enrollment/successor terminal expiry, cross-screen denial, AEAD one-time replay binding and destruction, unreachable one-time-material cleanup, exact device-rotation replay, terminal-family denial, family revocation, SHA-256 audit-chain recomputation and plaintext scans.
- Vue TypeScript check and Vite production build: PASS; 19 modules transformed.
- Browser workflow at 1280 by 720: PASS for administrator login, exact role catalog, different-user user creation, auditor denial/audit read, enrollment/claim, successor activation, family hard revocation and reauthentication. No horizontal overflow or browser console warning/error was observed.
- Browser screenshot: PASS; `audit-role-preview.png` SHA-256 `3da0034de5b63773ca9656846c05eefdb8a0fb2cfe843bd334fa996f706a6151`.
- Candidate-diff, frontend-bundle and text-evidence secret scan: PASS with zero findings; the screenshot was also visually checked for credential material.
- P1 target-contract validator: PASS under PowerShell 7 and Windows PowerShell 5.1, 2,722 checks each.
- Repository lifecycle lint: PASS under PowerShell 7 and Windows PowerShell 5.1, 314 checks each.
- `git diff --check` and tracked candidate worktree check: PASS.
- Rollback to P1.0 commit `6ec4cdbf03ddf64796c9f09d3a5950a7a2ee8758`: PASS in a detached temporary worktree.
- Docker / Compose preview: Blocked because the Docker CLI is unavailable on this host. Docker is optional for this local development preview, so no image digest or container smoke is claimed.

The first independent review correctly returned `FAIL` for candidate `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e`. Its four blocking and two medium findings were repaired before this candidate was frozen; the exact first-review record and disposition are in [manifest.json](manifest.json). The only required completion step still Pending is the separate read-only re-review of the repaired candidate. The existing Starlette `TestClient` emitted one dependency deprecation warning; it did not affect the ten passing tests.
