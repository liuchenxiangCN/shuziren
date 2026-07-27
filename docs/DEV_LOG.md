# Productization Development Log

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: factual work completed after productization began
- Last reviewed: 2026-07-27
- Full POC and initial P0 history: [archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md)

## 2026-07-27

### P1.0 Target Contract Result Pack

#### Completed Facts

- The user explicitly accepted G0 and authorized P1 work.
- Activated P1.0 as the sole result batch and froze its result card and non-scope before contract work.
- Added target domain, identity / RBAC, device trust, configuration-release, relational data, storage / recovery and control-plane API contracts under `docs/product/contracts/`.
- Added a machine-readable registry for 31 entities, five exact roles, 22 permissions, nine exact state machines, IAM parameters, storage decisions, 70 API operations and the three-screen isolation fixture.
- Proposed ADR-0028 for the P1 control-plane foundation; it remains Proposed until explicit P1.0 acceptance.
- Added ResolutionFingerprint binding from validation through release creation, immutable ConfigLayer/FineReport/Secret versions, composite PublicationTarget ownership keys and exact control-plane ETag versus device CAS rules.
- Added bootstrap/reset/session API closure, default-deny draft-field authorization, administrator-only FineReport identity management and typed different-user approval for production high-risk actions.
- Replaced the same-backup-domain recovery journal idea with an authenticated RecoverySecurityLedger and an independently held monotonic anchor that fail closed against user/password/device credential rollback.
- Expanded independent contract validation to 69 reject fixtures covering exact state/role/API drift, field authorization, high-risk approval, security-ledger recovery, immutable deletion and three-screen isolation.
- Kept implemented POC API, data and runtime code unchanged.

#### Verification To Date

- `scripts/validate-p1-target-contracts.ps1` passed 1439 contract, state, RBAC, storage, API and Markdown consistency checks.
- `scripts/test-p1-target-contracts.ps1` passed the baseline plus 69 reject fixtures.
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
