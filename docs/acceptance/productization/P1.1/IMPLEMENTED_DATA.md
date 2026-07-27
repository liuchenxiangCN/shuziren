# P1.1 Candidate Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Logical schema: `p1_control_plane_001`
- Scope: factual SQLite P1.1 candidate subset; not the complete P1 target model
- Target source: [../../../product/contracts/DATA_MODEL.md](../../../product/contracts/DATA_MODEL.md)

P1.1 uses a new control-plane database, separate from the POC `sessions.db`. SQLite initialization enables WAL, `synchronous=FULL`, foreign keys and a 30-second busy timeout.

## Tables

| Table | P1.1 purpose |
| --- | --- |
| `schema_migrations` | Applied named migration version, source checksum and application time |
| `control_plane_metadata` | Explicit `DEVELOPMENT_PREVIEW` profile, tenant, deployment and one trust-only screen fixture |
| `users` | Local account state, Argon2id verifier, authentication / authorization epochs, lockout state and ETag revision |
| `role_assignments` | Exact role and scope rows; unique per user / role / scope |
| `auth_sessions` | HMAC session and CSRF verifiers, expiry, recent reauthentication, state and ETag revision |
| `high_risk_actions` | Typed command digest, initiator / approver epochs, immutable command JSON and approval state |
| `device_enrollments` | HMAC one-time enrollment verifier, preselected screen, issuance-time absent / terminal family precondition, state, expiry and ETag revision |
| `device_credential_families` | Screen-bound historical family state, active / pending pointers, credential epoch and ETag revision; a partial unique index permits at most one `ACTIVE` family per screen |
| `device_credentials` | HMAC verifier, version, activation deadline, last authenticated time and state |
| `idempotency_records` | Phase, operation, canonical route, principal, domain-separated idempotency-key digest, sensitive request HMAC / key ID and either sanitized result or AES-GCM one-time response with encryption key ID and canonical AAD evidence |
| `security_audit_events` | Append-only sequence, sanitized detail JSON and versioned domain-separated SHA-256 hash-chain evidence |

## Implemented Invariants

- Usernames are unique inside tenant and deployment.
- A created network user starts `PROVISIONING`, with a null password verifier and empty role set.
- Active or disabled preview users require an Argon2id verifier.
- Role assignments reference an existing user and use only `DEPLOYMENT`, `SITE` or `SCREEN`.
- The store contains only HMAC verifiers for session, CSRF, enrollment and device material.
- Device scope is read from the credential family; no device request field selects tenant, deployment, Site or screen.
- A screen has at most one `ACTIVE` credential family. Any number of terminal historical families may remain preserved, and each family has at most one active credential pointer and one pending successor pointer.
- A terminal `REVOKED` or `REENROLL_REQUIRED` credential family is never reopened in place; a fresh enrollment bound to that exact terminal generation creates a distinct family.
- Enrollment issuance and claim bind the absent or terminal family precondition. Activation of another family or any generation change makes a pre-issued enrollment stale and rejects it before a credential family is created.
- Rotation creates only `PENDING_ACTIVATION`; first authenticated successor use revokes the predecessor and activates the successor in one transaction.
- Hard revocation advances the family credential epoch exactly once and revokes both active and pending credential rows.
- One idempotency key with a changed request digest is rejected.
- Reauthentication, approval, rejection, protected request/execution, enrollment claim and device rotation persist operation and canonical-route-bound idempotency evidence.
- One-time enrollment and device-credential responses are AES-256-GCM encrypted with `ONE_TIME_RESPONSE_ENCRYPTION`, its key ID and canonical AAD that binds the operation, route, principal, object IDs, idempotency digest, sensitive request HMAC / key ID and expiry.
- Expired one-time replay nonce, ciphertext and AAD are overwritten with null before the terminal replay error is returned. Unreachable issued enrollment material is revoked; an unproven claimed credential closes its family; an unproven pending rotation successor is revoked and its pointer is cleared while the predecessor remains active.
- Expired approval, enrollment and pending-successor states are committed separately from their fail-closed response so later reads cannot observe a rolled-back live state.
- Audit-event UPDATE and DELETE are rejected by SQLite triggers.

## Key Material Boundary

The live database stores key IDs, digests, nonces and ciphertext only. `CONTROL_PLANE_ROOT_KEY_B64` is supplied outside the database and derives distinct keys using HKDF-SHA-256 with a purpose-specific domain separator. The seven P1.1 purposes are a strict subset of the frozen eighteen-purpose registry, including separate `HIGH_RISK_REQUEST_HMAC`, `SENSITIVE_REQUEST_DIGEST_HMAC` and `ONE_TIME_RESPONSE_ENCRYPTION`; no candidate-only purpose is introduced. P1.1 does not claim the complete external monotonic key registry or production recovery anchors accepted in P1.0.

## Explicitly Absent

- No Site, ScreenGroup or production ScreenInstance inventory tables.
- No DigitalHumanInstance, RuntimeBinding, ConfigDraft, ConfigRelease, Publication or backup / restore tables.
- No SecretRecord, SecretVersion or FineReport identity binding implementation.
- No PostgreSQL migration or certification.
- No production custodian-person registry, external monotonic ledger anchor or production OperationalFence implementation.
