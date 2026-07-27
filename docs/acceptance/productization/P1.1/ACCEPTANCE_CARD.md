# P1.1 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_IN_PROGRESS`
- Result: local identity and screen-device trust
- Base accepted version: P1.0 acceptance-transition commit to be recorded before runtime implementation
- Candidate: Pending
- Database schema / migration: `p1_control_plane_001`; implementation and rollback evidence pending
- Gate summary: Pending
- User decision: Pending

## Frozen Observable Outcome

P1.1 delivers one independently usable management slice:

1. A built-in administrator signs in through an opaque, server-side browser session.
2. Administrators inspect the exact role catalog and create implementation or audit user records through typed, different-user approval.
3. An audit user reads sanitized immutable security events but cannot manage users, approve privileged changes, mutate device trust or reveal Secret values.
4. An authorized implementation engineer requests a one-time credential for a pre-existing screen trust target through typed approval.
5. A device claims the enrollment once, authenticates with its own screen-bound credential, rotates to a pending successor and activates that successor on first use.
6. An administrator hard-revokes the complete device credential family through typed approval; old, successor and replayed credentials then fail closed.

The management UI and API must explain safe failures without exposing password, session, CSRF, enrollment or device credential material.

## Frozen Entry Point And Test Data

- Management UI: `/manage`
- Control-plane API: `/api/v1/control-plane`
- Device API: `/api/v1/device`
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
7. Trigger failed logins, stale ETags, missing Origin / CSRF, self-approval, altered-command replay and cross-screen selectors and confirm fail-closed results.

## Frozen Automated Gates

- Python formatting / syntax and API application import.
- SQLite schema migration from an empty store and repeat initialization.
- Argon2id policy, password length / common-password rejection and progressive lockout.
- Secure host-only session cookie, exact-Origin, CSRF, idle / absolute expiry, rotation and revocation.
- API RBAC denial for auditor and implementation roles.
- Different-user approval, exact-command binding, self-approval denial and stale-precondition rejection.
- Enrollment single use, exact idempotency replay window, credential rotation activation and family-wide hard revocation.
- Device credential-derived screen scope and rejection of client-selected tenant, deployment, site or screen scope.
- Secret scan of API responses, audit details, frontend bundle and evidence.
- Web type-check / build and browser workflow smoke where the environment supports it.
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

Target: the P1.0 acceptance-transition commit recorded before runtime implementation. Rollback procedure and post-restore verification remain Pending until the P1.1 candidate is frozen.
