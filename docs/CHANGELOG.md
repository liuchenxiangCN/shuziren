# Changelog

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard-product changes
- Last reviewed: 2026-07-27
- Historical POC changelog: [archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md)

## Unreleased

### Added

- A P1.2 candidate with one default Site, screen group and three isolated ScreenInstances, each with non-secret FVS inventory, one active DigitalHumanInstance, device-trust summary and a same-screen RuntimeBinding.
- Checksum-backed `002_three_screen_inventory` copied-database upgrade, opaque snapshot pagination, scope-aware inventory APIs, strong ETags, idempotent creates and the `/manage` multi-screen inventory workflow.
- P1.2 local initialization, accepted-P1.1 copied-upgrade, API launcher and isolated browser-gate scripts.
- P1.1 accepted local IAM, server-side browser sessions, fixed RBAC, typed different-user approval, append-only audit and screen-device trust APIs under separate `/api/v1/control-plane` and `/api/v1/device` namespaces.
- A `/manage` development-preview console and an explicit local initializer that never auto-creates production identities or keys.
- A PowerShell local API launcher and documented two-terminal preview path that do not require Docker.
- A reproducible pinned pnpm 9.15.4 web workspace and verified Docker / Compose API/web preview path.
- A separate `p1_control_plane_001` SQLite store using WAL, full synchronous durability, foreign keys, Argon2id password verifiers, purpose-separated HMAC / AEAD material and encrypted five-minute one-time response replay.
- P1.0 target domain, identity / RBAC, device trust, configuration-release, data, storage / recovery and control-plane API contracts.
- A machine-readable P1 contract registry plus validator and negative-fixture self-test.
- Accepted ADR-0028 for SQLite / PostgreSQL, local IAM, device credentials, backup / recovery and API foundation decisions.
- Documentation lifecycle and archive policy.
- Result acceptance standard for Codex-driven development.
- Target product contract namespace under `docs/product/contracts/`.
- G0 acceptance package structure.
- Documentation lifecycle lint script.
- Lifecycle-lint negative-fixture self-test and reproducible candidate fingerprint.
- Active product risk and blocker view.
- ADR-0027 for result-driven development and document lifecycle.
- SHA-256 manifest for archived root snapshots.
- P0-preserving G0 rollback-target exporter and recovery proof.

### Changed

- G0, P1.0 and P1.1 are explicitly accepted. P1.2 Three-Screen Inventory is implemented as a local candidate with passing automated and zero-finding independent-review evidence, but remains unaccepted pending an explicit user decision.
- P1.1 local implementation is accepted at candidate `8c18e5d6b10081eaaf608436440046894d235d46`; two earlier candidates failed independent review, both finding sets were remediated, and the third independent review passed with zero findings.
- The P1.0 target chooses SQLite for the embedded control plane, PostgreSQL 16 for the external target and an hourly separate-mount backup design with one-hour RPO / two-hour RTO targets; implementation evidence remains pending.
- P1.0 validation now binds target membership and inheritance through ResolutionFingerprint, creates immutable ReleaseTargets only with ConfigRelease and separates control-plane ETag checks from device acknowledgement CAS.
- P1.0 release provenance now separates `NORMAL` approved-draft creation from exact-map `ROLLBACK` creation, with no cross-screen or credential-version substitution.
- Production high-risk approval now records evidence only; the original initiator's exact protected-command resubmission atomically consumes approval with the domain effect or durable async enqueue.
- Production four-eyes now covers an exact 20-operation set and requires different active users backed by different active custodian-attested people; provisioning and reset cannot grant authority.
- Device hard revocation now uses a readable DeviceCredentialFamily ETag plus credential epoch and ledger-head checks for atomic whole-family revocation.
- Recovery anti-rollback now uses an authenticated RecoverySecurityLedger, separate monotonic anchor, authoritative role/scope and external-credential state, staged credential rotation and a restore-continuity envelope rather than a journal that could roll back with the backup.
- Production restore now always leaves or enters `RECOVERY_REQUIRED`; only a separate typed local readiness recovery may append an authenticated `READY` fence successor. Emergency authority reduction and cryptographic-root recovery cannot reopen serving or increase authority.
- Current context now contains only the product snapshot, current phase, as-built boundary and non-negotiable rules.
- Next Actions contains exactly one active result batch and queues its successor only after explicit user acceptance.
- P1-P5 now use vertical user-visible result batches, automated gates, independent review, evidence and rollback instead of traditional component phases.
- Current risk tracking no longer mixes POC现场 issues, customer tasks and product risks.
- POC API and data contracts are explicitly classified as implemented POC truth, not target product contracts.
- Root documentation index classifies product, as-built POC, customer and archive material.
- Root `AGENTS.md` is now stable Codex policy and root `README.md` is stable product navigation; dynamic phase and task status were removed from both.

### Archived

- Long-form context, next actions, development log, development plan, risk list and POC changelog snapshots.

### Security

- P1.2 inventory requests derive tenant/deployment/Site/screen lineage from the authenticated session and path; screen-scoped readers cannot enumerate sibling Site/group membership, and auditors cannot use any inventory mutation.
- P1.2 rejects Secret-like FVS references, cross-Site members, stale ETags, changed-command idempotency replay, duplicate slugs and second active digital-human instances without partial effects.
- P1.2 preserves the accepted P1.1 migration checksum, fixture screen ID, device/credential history and original immutable audit chain while appending only a sanitized migration event.
- P1.1 accepted device credentials derive screen scope server-side; rotation atomically activates a successor and revokes its predecessor, while hard revocation invalidates the complete family.
- P1.1 accepted browser mutations require exact Origin and bound CSRF; login and reauthentication rotate opaque host-only Secure / HttpOnly cookies, and validation errors do not echo submitted inputs.
- P1.1 accepted protected user/device mutations use different-user approval evidence that cannot execute the effect; altered-command replay and self-approval fail closed.
- P1.1 accepted authentication failures no longer disclose unknown, disabled or locked account state; expired actions, enrollments, successor credentials and one-time replay ciphertext become durable terminal evidence.
- P1.1 accepted reauthentication and device rotation use exact request-bound idempotency; revoked sessions cannot issue successors, expired one-time delivery clears unreachable device material, terminal device families never reopen, and a current post-terminal enrollment may create one distinct active replacement while stale enrollment generations fail closed.
- P1.1 accepted key purposes are a strict subset of the frozen eighteen domains; sensitive requests retain their HMAC key ID, one-time AES-GCM records retain the response key ID and canonical AAD evidence, and the named migration is checksum-verified.
- P1.0 separates user, device and FineReport data credentials; freezes local password/session/lockout/reset targets; prohibits Secret reveal; requires default-deny changed-field authorization, 18 non-reused cryptographic purpose domains and typed different-user/different-person production approval; and fails recovery closed against account/password/device generation rollback.
- FineReport official plugin archives are excluded from Git and remain outside product distribution.
- Result acceptance treats cross-screen leakage, authorization bypass, Secret exposure, data corruption and unrecoverable changes as immediate failures.

### Not Implemented

- P1.2 does not connect to FineReport/FVS, publish configuration, configure a renderer/avatar/provider, implement backup/restore or claim production readiness; FVS remains `UNVERIFIED` and runtime inventory remains `NOT_CONFIGURED_P1_3`.
- P1.1 is an accepted development-preview result, not a production-readiness claim. Production custodian/person binding, external monotonic anchors, production activation, complete user onboarding and recovery are not implemented.
- G0 changes documentation and development governance only.
- P1.0 is target contract design only. Its RBAC, device trust, multi-screen storage, API, migration, backup and restore behaviors are not implemented.
- P1.3 publication/recovery, the remaining target control-plane APIs beyond the P1.2 subset, database querying, FineReport plugin calling and real 2D / 3D rendering remain unimplemented product targets.
