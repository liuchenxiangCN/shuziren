# P1.1 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Result: local identity and screen-device trust
- Base accepted version: commit `6ec4cdbf03ddf64796c9f09d3a5950a7a2ee8758`, tree `33752e13a385b4980cd3ecca309ad0f27d9307ae`
- Candidate: commit `8c18e5d6b10081eaaf608436440046894d235d46`, tree `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`
- Database schema / migration: `p1_control_plane_001` / `001_initial_identity_device_trust`, checksum `fd7094d87568fddc42c339a4861a6004a136dfb26ed6d1a11549cdb7a5db95ce`; empty-store, repeat initialization and checksum-tamper rejection PASS
- Gate summary: required local automated, browser, Docker and rollback gates PASS; final-candidate independent review PASS
- User decision: `通过` on 2026-07-27

The user explicitly accepted this result without conditions on 2026-07-27.
P1.1 candidate commit `8c18e5d6b10081eaaf608436440046894d235d46`
is now the accepted runtime rollback baseline for subsequent P1 batches.

## Frozen Observable Outcome

P1.1 delivers one independently usable management slice:

1. A built-in administrator signs in through an opaque, server-side browser session.
2. Administrators inspect the exact role catalog and create implementation or audit user records through typed, different-user approval.
3. An audit user reads sanitized immutable security events but cannot manage users, approve privileged changes, mutate device trust or reveal Secret values.
4. An authorized implementation engineer requests a one-time credential for a pre-existing screen trust target through typed approval.
5. A device claims the enrollment once, authenticates with its own screen-bound credential, rotates to a pending successor and activates that successor on first use.
6. An administrator hard-revokes the complete device credential family through typed approval; old, successor and replayed credentials then fail closed.
7. A fresh enrollment issued after hard revocation or `REENROLL_REQUIRED` creates a distinct new family while the terminal family remains immutable history.

The management UI and API must explain safe failures without exposing password, session, CSRF, enrollment or device credential material.

## Frozen Entry Point And Test Data

- Management UI: `/manage`
- Control-plane API: `/api/v1/control-plane`
- Device API: `/api/v1/device`
- Candidate API truth: [IMPLEMENTED_API.md](IMPLEMENTED_API.md)
- Candidate data truth: [IMPLEMENTED_DATA.md](IMPLEMENTED_DATA.md)
- Local preview procedure: [RUNBOOK.md](RUNBOOK.md)
- Local preview setup: an explicit development-only initializer creates two separate administrator identities, one auditor and one implementation engineer plus one trust-only screen fixture.
- Production startup must not auto-create users, passwords, roles, device targets or cryptographic keys.
- Exact preview credentials are generated outside Git and never enter logs or evidence.

## Frozen User Scenarios

1. Sign in as administrator A and inspect current session, users and role definitions.
2. Request an implementation or audit user creation, sign in separately as administrator B to approve it, then have administrator A resubmit the identical command.
3. Sign in as the auditor, inspect security events, and confirm user management, approval, device mutation and Secret-bearing responses are denied.
4. Request enrollment for the trust-only screen fixture, approve with the other administrator, execute the exact request and claim it once.
5. Rotate the active device credential, activate the successor on first authenticated use and confirm the predecessor is revoked.
6. Hard-revoke the credential family with different-user approval and confirm every family credential is rejected.
7. Issue and claim a fresh enrollment after hard revocation and confirm the old family stays terminal while exactly one distinct new family is active.
8. Trigger failed logins, stale ETags, stale enrollment generations, missing Origin / CSRF, self-approval, altered-command replay and cross-screen selectors and confirm fail-closed results.

## Frozen Automated Gates

- Python formatting / syntax and API application import.
- SQLite schema migration from an empty store and repeat initialization.
- Argon2id policy, password length / common-password rejection and progressive lockout.
- Secure host-only session cookie, exact-Origin, CSRF, idle / absolute expiry, rotation and revocation.
- API RBAC denial for auditor and implementation roles.
- Different-user approval, exact-command binding, self-approval denial and stale-precondition rejection.
- Enrollment single use, exact idempotency replay window, credential rotation activation, family-wide hard revocation and fresh-family re-enrollment with stale-generation rejection.
- Device credential-derived screen scope and rejection of client-selected tenant, deployment, site or screen scope.
- Secret scan of API responses, audit details, frontend bundle and evidence.
- Web type-check / build and browser workflow smoke where the environment supports it.
- Reproducible pnpm 9.15.4 web build and isolated Docker Compose API/web smoke.
- `git diff --check`, P1 target-contract validation and repository lifecycle lint.

## Frozen Non-Scope

- No Site, ScreenGroup or production ScreenInstance inventory management; P1.1 may use one explicitly labeled trust-only screen fixture.
- No three-screen configuration isolation claim; that belongs to P1.2.
- No configuration draft, release, publication, rollback, runtime binding or recovery implementation; those belong to P1.3.
- No PostgreSQL certification, production custodian ceremony, external monotonic security anchor or production activation claim.
- No Secret or FineReport credential implementation and no change to the POC `/api/config/*`, `/api/ops/*` or `/api/screen/*` semantics.
- No FineReport plugin, database QuerySource, Dora, ASR, TTS, FVS or Renderer expansion.

## Immediate Failure Conditions

- A user, session, enrollment or device can select or cross another ownership scope.
- Auditor or implementation privileges exceed the accepted role catalog.
- Approval executes the effect, self-approval succeeds, or a changed command reuses approval.
- Password, cookie, CSRF, enrollment or device plaintext enters the database, logs, audit details, ordinary reads, bundle or Git.
- A revoked, expired or superseded credential authenticates.
- A runtime result is described as production-ready without its required external security anchors and production activation evidence.

## Rollback

Target: P1.0 acceptance-transition commit `6ec4cdbf03ddf64796c9f09d3a5950a7a2ee8758`, tree `33752e13a385b4980cd3ecca309ad0f27d9307ae`.

Rollback proof PASS in a detached temporary worktree: both P1 target-contract validation and repository lifecycle lint passed, the P1.1 control-plane module was absent, and the original POC API imported with `/api/config/*` present and no `/api/v1/control-plane/*` routes. The temporary worktree was removed after verification.

The P1.1 store is a new, separate `data/control-plane.db`. Rollback preserves it outside the active P1.0 runtime path rather than attempting an unsupported downgrade into the POC `sessions.db`.

## Review Boundary

Independent review task `/root/p1_1_independent_review` rejected candidate `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e` with four blocking and two medium findings. The findings covered revoked-session reauthentication, rotation replay and lost-successor cleanup, terminal-family reopening, key-purpose and one-time-response evidence drift, ignored reauthentication idempotency and an unimplemented named migration.

The same reviewer then rejected candidate `45dd8ff9455c1ab62a408d26c15f15a14256341b` because a full historical screen uniqueness constraint permanently prevented the fresh family required after hard revocation or failed credential delivery.

Both failed review rounds are remediated in the candidate above with regression coverage and rebuilt evidence. The same separate read-only Codex task completed its third review against commit `8c18e5d6b10081eaaf608436440046894d235d46` and tree `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`: `PASS`, with zero blocking and zero non-blocking findings. P1.1 is ready for an explicit user result decision; it is not accepted until that decision is recorded.
