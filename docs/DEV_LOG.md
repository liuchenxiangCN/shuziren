# Productization Development Log

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: factual work completed after productization began
- Last reviewed: 2026-07-27
- Full POC and initial P0 history: [archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md)

## 2026-07-27

### P1.1 User Acceptance And P1.2 Activation

#### Completed Facts

- The user explicitly accepted P1.1 (`通过`) without conditions or scope reduction.
- P1.1 candidate commit `8c18e5d6b10081eaaf608436440046894d235d46`, tree `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`, became the accepted runtime rollback baseline.
- P1.2 Three-Screen Inventory became the sole active result batch.
- Froze the P1.2 result card and non-scope before implementation. It promotes the exact P1.1 fixture screen into a default Site/group three-screen inventory without changing its ID or trust history, keeps FVS `UNVERIFIED`, keeps runtime configuration `NOT_CONFIGURED_P1_3`, and requires ownership-aware isolation, migration and rollback evidence.
- No P1.2 runtime implementation is claimed or started by the result-card freeze.

### P1.0 User Acceptance And P1.1 Activation

#### Completed Facts

- The user explicitly accepted P1.0 (`通过`) without conditions and authorized P1.1 development.
- ADR-0028 changed from Proposed to Accepted; this freezes the target contract but does not claim runtime implementation.
- P1.0 became the accepted rollback baseline and P1.1 Identity And Device Trust became the sole active result batch.
- The P1.1 result card and non-scope were frozen before runtime implementation.

### P1.1 Identity And Device Trust

#### Completed Facts To Date

- Frozen final P1.1 candidate commit `8c18e5d6b10081eaaf608436440046894d235d46`, tree `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`.
- Added a separate P1.1 SQLite control-plane store at logical schema `p1_control_plane_001`; the POC `sessions.db` and existing POC route meanings are unchanged.
- Added Argon2id local-password verification, progressive lockout, opaque server-side browser sessions, exact-Origin / CSRF enforcement, idle / absolute expiry and session rotation on reauthentication.
- Added the exact accepted five-role permission catalog and API-side authorization; auditors can read sanitized audit events but cannot read user administration or device credential metadata.
- Added typed high-risk action request, different-user approval / rejection and original-initiator exact-command resubmission for user creation, device enrollment and device-family revocation. Approval records evidence but cannot execute the effect.
- Added one-time screen-bound enrollment, HMAC-only token / credential storage, AES-GCM five-minute exact response replay, device credential rotation with pending-successor activation and atomic whole-family revocation.
- Added issuance-time absent / terminal family preconditions and a partial active-family uniqueness constraint. A fresh post-terminal enrollment creates a distinct family, preserves old terminal history and rejects stale pre-issued or changed-generation enrollment.
- Added versioned domain-separated SHA-256-chained append-only security audit records with SQLite update/delete denial triggers and sanitized API-denial events.
- Added `/manage` as a separate management preview without changing the existing conversation, Ops or POC configuration views.
- Added an explicit development-only initializer. Production startup does not auto-create identities, passwords, roles, screen targets or cryptographic keys.
- Added a local PowerShell API launcher so Docker is optional for development preview; it imports only allowlisted preview settings, forces the local database path and never prints root-key material.
- Added the missing web workspace package declaration required for reproducible pinned pnpm 9.15.4 and Docker builds.
- Hardened generic authentication failures, password validation, bounded idempotency/precondition headers, operation/route-bound sensitive request evidence, terminal expiry persistence and expired one-time ciphertext destruction.
- The first independent Codex review rejected candidate `f4fadbf44a284ba0678eb82e37a1cebbcf6c3d1e` with four blocking and two medium findings. The repaired candidate checks revoked-session state/revision updates, preserves exact reauthentication and device-rotation idempotency, cleans unreachable one-time device material, prevents terminal-family reopening, uses only frozen key-purpose names, stores one-time response encryption-key/AAD evidence and implements checksum-backed migration `001_initial_identity_device_trust`.
- The second independent review rejected candidate `45dd8ff9455c1ab62a408d26c15f15a14256341b` only because the historical screen-uniqueness constraint permanently prevented a fresh family after hard revocation or `REENROLL_REQUIRED`. The final candidate replaces it with partial active-family uniqueness and generation-bound enrollment.
- Kept Site / ScreenGroup / production ScreenInstance inventory, publication, rollback, recovery, Secret and FineReport identity behavior outside P1.1.

#### Verification To Date

- Backend Ruff formatting/check and ten integration tests pass, covering named-migration checksum/repeatability/no-auto-bootstrap, frozen key purposes, password/session/CSRF/lockout, idempotent reauthentication, auditor denial, different-user command binding, terminal expiry, enrollment replay destruction, unreachable one-time-material cleanup, exact rotation replay, stale pre-issued enrollment denial, fresh-family re-enrollment after `REVOKED` and `REENROLL_REQUIRED`, activation, predecessor rejection, whole-family revocation, audit-chain verification and database/audit plaintext scans.
- The Vue TypeScript check and Vite production build pass.
- A real local browser workflow at 1280 by 720 passed administrator login, role inspection, different-user user creation, auditor denial/audit read, device enrollment/claim/rotation/activation/revocation, fresh-family re-enrollment and password reauthentication with no horizontal overflow or captured console warning/error.
- The final-candidate sanitized auditor screenshot SHA-256 is `80b11a1706e734fe7dcc9fc8083a841b7532760ebd31582d9472f4b91c20aacb`.
- P1 contract validation passed 2,722 checks and lifecycle lint passed 314 checks under both PowerShell hosts. Candidate-diff, bundle and evidence secret scanning returned zero findings.
- Detached-worktree rollback to P1.0 passed contract/lifecycle checks and POC API import, then the temporary worktree was removed.
- The pinned pnpm 9.15.4 frontend build and isolated Docker / Compose API/web build-runtime smoke pass; `/api/health` and `/manage` returned HTTP 200, and the Compose project shut down cleanly.
- The same independent reviewer completed a third read-only review of the final candidate: `PASS`, zero blocking findings and zero non-blocking findings. Evidence hashes, P1.0 rollback and all prior findings were independently rechecked.
- P1.1 became ready for explicit user acceptance; the user subsequently accepted it without conditions as recorded above.

### P1.0 Target Contract Result Pack

#### Completed Facts

- The user explicitly accepted G0 and authorized P1 work.
- Activated P1.0 as the sole result batch and froze its result card and non-scope before contract work.
- Added target domain, identity / RBAC, device trust, configuration-release, relational data, storage / recovery and control-plane API contracts under `docs/product/contracts/`.
- Added a machine-readable registry for 32 entities, five exact roles, 23 permissions, 16 exact state machines, 31 internal security-record schemas, IAM/scope parameters, storage decisions, 86 API operations and complete pre-publish/post-publish/post-ack three-screen isolation snapshots.
- Proposed ADR-0028 for the P1 control-plane foundation; it was subsequently accepted with the explicit P1.0 user decision.
- Added ResolutionFingerprint binding from validation through release creation, immutable ConfigLayer/FineReport/Secret versions, composite PublicationTarget ownership keys and exact control-plane ETag versus device CAS rules.
- Added bootstrap/reset/session API closure, explicit draft revise/abandon operations, exact-path default-deny field authorization, administrator-only FineReport identity management and typed different-user approval whose evidence step cannot execute the protected action.
- Added mutually exclusive `NORMAL` / `ROLLBACK` release provenance, exact historical rollback source maps and no-substitution constraints.
- Added DeviceCredentialFamily metadata/ETag and exact epoch/ledger concurrency for atomic whole-family revocation.
- Replaced the same-backup-domain recovery journal idea with an authenticated RecoverySecurityLedger and independently held monotonic anchor that authoritatively reconcile complete role/scope snapshots, devices, Secrets and FineReport binding versions.
- Added staged external-credential rotation, fail-closed recovery states, approval epoch invalidation and an authenticated continuity envelope that carries the current restore's own authorization/idempotency/audit evidence into the staged store.
- Closed production bootstrap, provisioning, password-reset, browser-session and human-identity bindings; production four-eyes now protects an exact 20-operation set and requires different users backed by different active custodian-attested people.
- Froze 18 independent key-purpose domains, an externally anchored OperationalFence, three typed local recovery authorities and three RecoveryPasswordSetupGrant authorization kinds. Every production restore remains `RECOVERY_REQUIRED` until a separate local readiness recovery records an authenticated `READY` successor.
- Expanded independent contract validation to 190 rejection executions: 166 semantic mutation fixtures plus 12 raw JSON fixtures under both PowerShell hosts, covering duplicate/non-finite/invalid-number/trailing-data rejection, exact state/role/API/error drift, field authorization, high-risk approval/atomicity, release provenance, security-ledger recovery, immutable deletion and complete three-screen state isolation.
- Kept implemented POC API, data and runtime code unchanged.

#### Verification To Date

- `scripts/validate-p1-target-contracts.ps1` passed 2,722 contract, state, RBAC, storage, API and Markdown consistency checks under both PowerShell 7 and Windows PowerShell 5.1.
- `scripts/test-p1-target-contracts.ps1` passed 191 cases: one baseline, 166 semantic reject fixtures under Windows PowerShell 5.1 and 12 raw JSON reject fixtures under both Windows PowerShell 5.1 and PowerShell 7.
- Final lifecycle, evidence, fingerprint, rollback and independent-review conclusions are recorded only after the candidate is complete.

### G0 Documentation Governance And Result-Driven Planning

#### Completed

- Preserved the long-form POC and initial productization context, task list, development log, plan, risks and changelog under `docs/archive/poc-v1/root-snapshots/`.
- Added a line-count, byte-count and SHA-256 archive manifest.
- Rebuilt `CODEX_CONTEXT.md` as a small current snapshot and `NEXT_ACTIONS.md` as exactly one active result batch.
- Added `DOCUMENT_GOVERNANCE.md` with lifecycle classes, truth precedence, active-document responsibilities, size budgets, archive rules and contract namespaces.
- Added `RESULT_ACCEPTANCE_STANDARD.md` for result cards, automated gates, independent Codex review, evidence packages, user decisions and rollback rules.
- Replaced the traditional P1-P5 phase plan with vertical user-result batches and explicit automated gates, user scenarios and stop conditions.
- Separated implemented POC contracts from future target product contracts using `docs/product/contracts/`.
- Reduced the current risk file to active product risks and external blockers.
- Added a productization acceptance-package structure for G0.
- Added a documentation lifecycle lint script and FineReport plugin ZIP Git-exclusion rule.
- Added ADR-0027 to record the result-driven development and document-lifecycle decision.
- Rebuilt root `AGENTS.md` as stable Codex routing / execution policy and root `README.md` as stable product boundary / navigation, removing duplicated phase, milestone, port and next-batch status.
- Kept runtime code and implemented API / data structures unchanged.

#### Verification

- `scripts/lint-doc-lifecycle.ps1` passed 268 dynamic lifecycle, root responsibility, task, link / path, customer, Secret, UTF-8, whitespace, contract, archive and vendor-binary checks.
- `scripts/test-doc-lifecycle-lint.ps1` passed all 21 isolated accept / reject fixtures, including dynamic root status, README budget, broken policy paths, scoped deep links, Secret patterns, tracked vendor packages and a real plugin copy renamed to `.dat`.
- Root `AGENTS.md` is 95 / 120 lines and root `README.md` is 70 / 80 lines; their reviewed SHA-256 values are recorded in the G0 machine manifest.
- All six archive hashes matched the archive manifest; removing the two-line archive banner restores 4,105 original lines.
- The local FineReport plugin hash matched its evidence document, Git tracked zero copies and the canonical local file was ignored.
- The rollback exporter produced a P0-preserving tree from base commit `8e293af1f56e5d7623b0af3dfd408e6086e736c2`, restored six root documents, preserved eleven P0 artifacts, excluded G0-only files and rejected unsafe workspace / `.git` targets.
- Independent architecture and documentation-gate reviewers passed the remediated candidate. Their task IDs and conclusions are recorded in the G0 manifest.
- Runtime and database-migration tests were `N/A` because the candidate changes documentation, governance scripts and repository metadata only; no runtime path changed.

#### User Decision

- Explicitly accepted (`通过`) on 2026-07-27 in the Codex task that started P1 development.

## 2026-07-26

### P0 Product Definition

- Product scope was narrowed to customers that already own FineReport and use FVS.
- Single-site, multi-screen private deployment, per-screen capability configuration, built-in RBAC, three-day runtime-log retention, controlled MySQL / Oracle / PostgreSQL querying and non-redistribution of the official plugin were frozen.
- `17_STANDARD_PRODUCT_DESIGN.md`, ADR-0026 and the FineReport plugin integration boundary were created.
- Official plugin API, authentication, session, permission and upgrade behavior remained a P2 external gate.
- No product runtime capability was implemented in P0.

Detailed evidence remains in the archived full history.
