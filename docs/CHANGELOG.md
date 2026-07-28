# Changelog

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard-product changes
- Last reviewed: 2026-07-28
- Historical POC changelog: [archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md)

## Unreleased

### Added

- P2.2 candidate QuerySources for bounded `.xlsx`, PostgreSQL, MySQL and
  Oracle; write-only encrypted database credentials; immutable approved
  datasets; exact draft/release query sidecars; and screen/device-bound
  asynchronous execution with timeout, cancellation and backpressure.
- Additive `005_controlled_querying`, P2.2 preview/browser launchers,
  machine-readable query contract, management/runtime workflow and
  backup/restore validation that preserves current source/dataset authority,
  refuses live-query restore and terminalizes restored orphan executions.
- Accepted P2.1 Site-owned capability profiles, immutable profile
  versions, exact draft assignments, immutable ReleaseTarget capability
  snapshots and credential-scoped applied-profile resolution across three
  screens.
- Closed seven-capability/21-Provider registry, three product presets, five
  distinct state meanings, technical-only equivalent fallback and bounded
  local/Mock timeout, cancellation and backpressure diagnostics.
- Checksum-backed additive `004_capability_profiles`, exact accepted-P1.3
  copied upgrade, `/manage` capability-profile workflow, local launchers and
  candidate-bound API, browser, Docker, recovery, rollback and review evidence.
- Accepted P1.3 configuration drafts, Mock validation/preview,
  different-user approval, immutable normal/rollback releases, per-screen and
  group publication, credential-bound acknowledgement, diffs and audit
  evidence.
- Checksum-backed `003_publish_rollback_recovery`, encrypted verified local
  backup, staged online-source restore with retained pre-restore store and
  three-day runtime-detail retention.
- P1.3 release center, local initialization/upgrade launchers, accepted-P1.2
  rollback package and candidate-bound browser, recovery, Docker and acceptance
  evidence.
- Accepted P1.2 inventory with one default Site, screen group and three isolated ScreenInstances, each with non-secret FVS inventory, one active DigitalHumanInstance, device-trust summary and a same-screen RuntimeBinding.
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

- G0 and P1.0 through P2.1 are explicitly accepted. P2.1 candidate
  `8f364b93b574c058cd8cd617f925107985318098`, tree
  `7c277e32b6419bd3720591c454e8282d94f081ec`, is the accepted runtime baseline.
  P1.3 remains the verified product-code and pre-`004` data rollback target;
  P2.2 is a completed implementation candidate pending immutable review and
  explicit user acceptance.
- ADR-0029 is accepted with P2.1; its additive immutable capability-profile
  sidecar decision does not activate P2.2 or certify a real Provider.
- P1.2 local implementation is accepted at candidate `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree `565dbb3567e2a4ae5b872177d97449120477fe8c`; its automated and independent-review evidence passes with zero final findings.
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

- P2.1 rejects Secret-, endpoint-, credential-, DSN-, query-language-,
  executable- and Prompt-like material across profile metadata and specs;
  unknown Provider and validation failures return generic bounded errors, and
  denial audit targets use canonical route families.
- P2.1 validates complete migration/schema objects and recovery reverse
  references, preserves validation-time fingerprint epochs across restore and
  later draft revision, and prevents restored idempotency or consumed
  publication/rollback evidence from returning phantom success.
- All P2.1 API startup paths disable request-target access logging. Permission
  denial, invalid input, unauthorized template and cancellation are terminal
  and cannot trigger fallback.
- P1.3 binds verified bundle identity and hashes to immutable backup records,
  validates source snapshots before recording backup success and serializes
  restore cutover with supported control-plane mutations so no acknowledged
  write silently disappears.
- P1.3 persists sanitized HTTP 200 `INVALID` validation evidence without a
  fabricated fingerprint and applies business/technical permissions only to
  changed configuration leaves.
- Publication, rollback and restore consume exact typed different-user
  approvals; device apply derives screen scope from the active credential and
  requires the exact desired target, generation and content hash.
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

- Accepted P1.3 remains a local development-preview result. It does not
  implement real FineReport/FVS/plugin connectivity, production activation,
  offline/full-loss recovery, external anti-rollback authority, PostgreSQL
  recovery or customer RPO/RTO certification.
- Accepted P2.1 performs no real Provider call. QuerySource,
  Excel/database execution and P2.2 remain unimplemented; its browser evidence
  is an explicit byte-identical semantic rebind rather than a final-candidate
  interactive rerun.
- P1.2 does not connect to FineReport/FVS, publish configuration, configure a renderer/avatar/provider, implement backup/restore or claim production readiness; FVS remains `UNVERIFIED` and runtime inventory remains `NOT_CONFIGURED_P1_3`.
- P1.1 is an accepted development-preview result, not a production-readiness claim. Production custodian/person binding, external monotonic anchors, production activation, complete user onboarding and recovery are not implemented.
- G0 changes documentation and development governance only.
- P1.0 is target contract design only. Its RBAC, device trust, multi-screen storage, API, migration, backup and restore behaviors are not implemented.
- Remaining target control-plane behavior beyond accepted P2.1, database
  querying, FineReport plugin calling and real 2D / 3D rendering remain
  unimplemented product targets.
