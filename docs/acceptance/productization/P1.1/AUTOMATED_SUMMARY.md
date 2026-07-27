# P1.1 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_FROZEN_REVIEW_PENDING`
- Candidate: `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e`
- Candidate tree: `d7c6d0221ccb156a69858742b5cda45e3ef9554d`
- Gate summary: required local gates PASS; optional Docker preview Blocked; independent review Pending

Sanitized raw evidence is under ignored local path `logs/productization/P1.1-20260727-local/`. The tracked [manifest.json](manifest.json) is the machine-readable gate record.

## Candidate Gate Results

- Ruff format/check and API import: PASS.
- Pytest: PASS, nine tests. They cover empty and repeat schema initialization, production-like no-auto-bootstrap, password policy, generic authentication failure, progressive lockout, duplicate-cookie denial, CSRF/session expiry and rotation, exact RBAC, different-user approval, stale ETag, action/enrollment/successor terminal expiry, cross-screen denial, one-time replay destruction, device rotation/family revocation, audit-chain recomputation and plaintext scans.
- Vue TypeScript check and Vite production build: PASS; 19 modules transformed.
- Browser workflow at 1280 by 720: PASS for administrator login, exact role catalog, different-user user creation, auditor denial/audit read, enrollment/claim, successor activation, family hard revocation and reauthentication. No horizontal overflow or browser console warning/error was observed.
- Browser screenshot: PASS; `audit-role-preview.png` SHA-256 `741c6e9d1b8d1c96e36a2383b9e9839f33ad0854f512f19c950d3a23e4d2b21e`.
- Candidate-diff, frontend-bundle and text-evidence secret scan: PASS with zero findings; the screenshot was also visually checked for credential material.
- P1 target-contract validator: PASS under PowerShell 7 and Windows PowerShell 5.1, 2,722 checks each.
- Repository lifecycle lint: PASS under PowerShell 7 and Windows PowerShell 5.1, 314 checks each.
- `git diff --check` and tracked candidate worktree check: PASS.
- Rollback to P1.0 commit `6ec4cdbf03ddf64796c9f09d3a5950a7a2ee8758`: PASS in a detached temporary worktree.
- Docker / Compose preview: Blocked because the Docker CLI is unavailable on this host. Docker is optional for this local development preview, so no image digest or container smoke is claimed.

The only required completion step still Pending is the separate independent Codex review. The existing Starlette `TestClient` emitted one dependency deprecation warning; it did not affect the nine passing tests.
