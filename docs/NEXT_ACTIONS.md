# Next Actions

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: exactly one active result batch
- Last reviewed: 2026-07-27
- Historical tasks: [archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md](archive/poc-v1/root-snapshots/NEXT_ACTIONS_FULL_HISTORY.md)

## Current Phase

`Productization P1.1 Identity And Device Trust`.

G0 and P1.0 were explicitly accepted on 2026-07-27. P1.0 is the accepted target-contract and rollback baseline. P1.1 candidate `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e` is frozen with required local automated, browser and rollback gates passing, but it remains unaccepted and the accepted runtime baseline is still the single-instance POC.

## Next Task

Obtain a separate read-only Codex review of the frozen P1.1 candidate, remediate any blocking finding, then present the reviewed local identity and screen-device trust result for explicit user acceptance.

### User-Visible Result

P1.1 must provide:

1. A built-in administrator can sign in through an opaque server-side browser session.
2. Administrators can inspect the exact role catalog and create implementation or audit user records through typed different-user approval.
3. An audit user can read sanitized immutable security events but cannot manage users, approve privileged changes, mutate device trust or reveal Secret values.
4. An authorized implementation engineer can request a one-time credential for a pre-existing screen trust target through typed approval.
5. A device can claim enrollment once, authenticate with a separate screen-bound credential, rotate to a pending successor and activate that successor on first use.
6. An administrator can hard-revoke the complete credential family through typed approval; old, successor and replayed credentials then fail closed.

### Result Package

- [acceptance/productization/P1.1/ACCEPTANCE_CARD.md](acceptance/productization/P1.1/ACCEPTANCE_CARD.md)
- [acceptance/productization/P1.1/AUTOMATED_SUMMARY.md](acceptance/productization/P1.1/AUTOMATED_SUMMARY.md)
- [acceptance/productization/P1.1/KNOWN_LIMITATIONS.md](acceptance/productization/P1.1/KNOWN_LIMITATIONS.md)
- [acceptance/productization/P1.1/manifest.json](acceptance/productization/P1.1/manifest.json)
- [acceptance/productization/P1.1/USER_DECISION.md](acceptance/productization/P1.1/USER_DECISION.md)
- [acceptance/productization/P1.1/IMPLEMENTED_API.md](acceptance/productization/P1.1/IMPLEMENTED_API.md)
- [acceptance/productization/P1.1/IMPLEMENTED_DATA.md](acceptance/productization/P1.1/IMPLEMENTED_DATA.md)
- [acceptance/productization/P1.1/RUNBOOK.md](acceptance/productization/P1.1/RUNBOOK.md)

The independent review and user decision remain Pending. P1.1 cannot be presented for acceptance until the independent review passes.

### User Result Scenarios

1. Sign in as administrator A and inspect current session, users and role definitions.
2. Request an implementation or audit user creation, sign in separately as administrator B to approve it, then have administrator A resubmit the identical command.
3. Sign in as the auditor, inspect security events, and confirm user management, approval, device mutation and Secret-bearing responses are denied.
4. Request enrollment for the trust-only screen fixture, approve with the other administrator, execute the exact request and claim it once.
5. Rotate the active device credential, activate the successor on first authenticated use and confirm the predecessor is revoked.
6. Hard-revoke the credential family with different-user approval and confirm every family credential is rejected.
7. Trigger failed logins, stale ETags, missing Origin / CSRF, self-approval, altered-command replay and cross-screen selectors and confirm fail-closed results.

### Automated Gates

- Python formatting / syntax and API application import pass.
- SQLite schema migration from an empty store and repeat initialization pass.
- Argon2id policy, password length / common-password rejection and progressive lockout pass.
- Secure host-only session cookie, exact-Origin, CSRF, idle / absolute expiry, rotation and revocation pass.
- API RBAC denial for auditor and implementation roles passes.
- Different-user approval, exact-command binding, self-approval denial and stale-precondition rejection pass.
- Enrollment single use, exact idempotency replay window, credential rotation activation and family-wide hard revocation pass.
- Device credential-derived screen scope passes and client-selected tenant, deployment, site or screen scope is rejected.
- Secret scans cover API responses, audit details, the frontend bundle and evidence.
- Web type-check / build and a browser workflow smoke pass where the environment supports them.
- `git diff --check`, P1 target-contract validation and repository lifecycle lint pass.

### Non-Scope

- No Site, ScreenGroup or production ScreenInstance inventory management; P1.1 may use one explicitly labeled trust-only screen fixture.
- No three-screen configuration isolation claim; that belongs to P1.2.
- No configuration draft, release, publication, rollback, runtime binding or recovery implementation; those belong to P1.3.
- No PostgreSQL certification, production custodian ceremony, external monotonic security anchor or production activation claim.
- No Secret or FineReport credential implementation and no change to the POC `/api/config/*`, `/api/ops/*` or `/api/screen/*` semantics.
- No FineReport plugin, database QuerySource, Dora, ASR, TTS, FVS or Renderer expansion.

### Stop Conditions

- A user, session, enrollment or device can select or cross another ownership scope.
- Auditor or implementation privileges exceed the accepted role catalog.
- Approval executes the effect, self-approval succeeds, or a changed command reuses approval.
- Password, cookie, CSRF, enrollment or device plaintext enters the database, logs, audit details, ordinary reads, bundle or Git.
- A revoked, expired or superseded credential authenticates.
- A runtime result is described as production-ready without its required external security anchors and production activation evidence.

## Queued After P1.1 Acceptance

`Productization P1.2 Three-Screen Inventory`.

P1.2 remains queued until P1.1 receives an explicit user result decision.
