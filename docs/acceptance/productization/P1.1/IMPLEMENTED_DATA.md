# P1.1 Candidate Implemented Data

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_IN_PROGRESS`
- Logical schema: `p1_control_plane_001`
- Scope: factual SQLite P1.1 candidate subset; not the complete P1 target model
- Target source: [../../../product/contracts/DATA_MODEL.md](../../../product/contracts/DATA_MODEL.md)

P1.1 uses a new control-plane database, separate from the POC `sessions.db`. SQLite initialization enables WAL, `synchronous=FULL`, foreign keys and a 30-second busy timeout.

## Tables

| Table | P1.1 purpose |
| --- | --- |
| `schema_migrations` | Applied logical schema version |
| `control_plane_metadata` | Explicit `DEVELOPMENT_PREVIEW` profile, tenant, deployment and one trust-only screen fixture |
| `users` | Local account state, Argon2id verifier, authentication / authorization epochs, lockout state and ETag revision |
| `role_assignments` | Exact role and scope rows; unique per user / role / scope |
| `auth_sessions` | HMAC session and CSRF verifiers, expiry, recent reauthentication, state and ETag revision |
| `high_risk_actions` | Typed command digest, initiator / approver epochs, immutable command JSON and approval state |
| `device_enrollments` | HMAC one-time enrollment verifier, preselected screen, state, expiry and ETag revision |
| `device_credential_families` | Screen-bound family state, active / pending pointers, credential epoch and ETag revision |
| `device_credentials` | HMAC verifier, version, activation deadline and state |
| `idempotency_records` | Phase/principal/key digest, request digest and either sanitized result or AES-GCM one-time response |
| `security_audit_events` | Append-only sequence, sanitized detail JSON and HMAC hash-chain evidence |

## Implemented Invariants

- Usernames are unique inside tenant and deployment.
- A created network user starts `PROVISIONING`, with a null password verifier and empty role set.
- Active or disabled preview users require an Argon2id verifier.
- Role assignments reference an existing user and use only `DEPLOYMENT`, `SITE` or `SCREEN`.
- The store contains only HMAC verifiers for session, CSRF, enrollment and device material.
- Device scope is read from the credential family; no device request field selects tenant, deployment, Site or screen.
- A screen has at most one credential family, one active credential pointer and one pending successor pointer.
- Rotation creates only `PENDING_ACTIVATION`; first authenticated successor use revokes the predecessor and activates the successor in one transaction.
- Hard revocation advances the family credential epoch exactly once and revokes both active and pending credential rows.
- One idempotency key with a changed request digest is rejected.
- One-time enrollment and device-credential responses are AES-256-GCM encrypted with purpose-derived material and expire after five minutes.
- Audit-event UPDATE and DELETE are rejected by SQLite triggers.

## Key Material Boundary

The live database stores key IDs, digests, nonces and ciphertext only. `CONTROL_PLANE_ROOT_KEY_B64` is supplied outside the database and derives distinct keys using HKDF-SHA-256 with a purpose-specific domain separator. P1.1 implements the purposes it uses; it does not claim the complete external monotonic key registry or production recovery anchors accepted in P1.0.

## Explicitly Absent

- No Site, ScreenGroup or production ScreenInstance inventory tables.
- No DigitalHumanInstance, RuntimeBinding, ConfigDraft, ConfigRelease, Publication or backup / restore tables.
- No SecretRecord, SecretVersion or FineReport identity binding implementation.
- No PostgreSQL migration or certification.
- No production custodian-person registry, external monotonic ledger anchor or production OperationalFence implementation.
