# Productization Development Log

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: factual work completed after productization began
- Last reviewed: 2026-07-29
- Full POC and initial P0 history: [archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/DEV_LOG_FULL_HISTORY.md)

## 2026-07-29

### P2.3 User Acceptance

#### Completed Facts

- The user explicitly accepted P2.3 through `通过` without conditions or
  scope reduction, in the same structured prompt that authorized the
  candidate commit.
- P2.3 runtime candidate `a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
  `8a2f4e36ca0751b6106a174f7dae63be9299ad5b`, schema `p1_control_plane_001`
  and migration `005_controlled_querying` became the accepted runtime
  baseline; accepted P2.2 `a75d3327fdc1ab4b83b0bba501d387af150353c4` remains
  the rollback target with no data reversal required.
- ADR-0031 is accepted; NEXT_ACTIONS, CODEX_CONTEXT, 13_RISKS_AND_TODO
  (R-045 mitigated), CHANGELOG, 00_INDEX and the P2.3 acceptance package were
  synchronized to the accepted state.

### P2.3 Candidate Complete And Presented For Acceptance

#### Completed Facts

- Implemented the frozen P2.3 result: screen-bound metadata-only execution
  list, queue-status view and resilience drill (`apps/api/app/control_plane/p2_3.py`,
  four browser-session routes, no device routes), `/manage` queries-view
  observability and drill UI, a deployment-local capacity harness
  (`capacity_p2_3.py`), preview/browser/contract/Secret scripts and the P2.3
  test suites. No schema migration; head stays `005_controlled_querying`.
- Gates passed: 77 backend cases (3 environment-gated skips), 46 contract
  checks plus 8 mutation fixtures under both PowerShell hosts, frontend
  build, fresh 1280×720 headless-Chrome workflow (document width 1265,
  effective console count 0 with 2 documented raw exclusions), Compose smoke
  with in-container head `005_controlled_querying`, dual-host Secret scans,
  copied-P2.2-database zero-migration upgrade, accepted-P2.2 rollback
  (67 original tests, 116 routes, no P2.3 surface) and 425-check lifecycle
  lint under both hosts.
- Capacity measurement (deployment-local reference, not an SLA): sequential
  medians 73–76 ms per screen, 14.1 completed/s three-screen concurrent, 12
  saturation submissions with 6 retryable backpressure rejections and 3/3
  recovery on the reference machine.
- Independent reviewer `Faraday` returned `PASS_WITH_NONBLOCKING` (0 blocking,
  7 non-blocking; N1–N3 closed before binding) after rerunning the suites and
  21 own negative probes.
- Candidate fingerprint
  `39712F425BD478FFF88465C72C3D6EBC56A915C6303A7150380DF1363D674C47` over 36
  files; raw evidence under `logs/productization/P2.3-20260729-234531` (39
  hashed files, zero missing/unexpected/mismatched). The candidate commit is
  pending user acceptance; user decision is pending.

### P2.3 Activation And Result-Card Freeze

#### Completed Facts

- The user activated `Productization P2.3 Concurrent And Failure Isolation`
  with the explicit instruction `完成P2.3开发`.
- The P2.3 result card and non-scope were frozen against accepted P2.2 at
  `docs/acceptance/productization/P2.3/ACCEPTANCE_CARD.md`: an integrated
  resilience certification of accepted P2.1/P2.2 covering three-screen
  concurrent correctness with distinct capability profiles, single-source and
  single-provider failure isolation, a live screen-bound resilience drill for
  equivalent fallback versus terminal no-fallback, bounded backpressure
  evidence and a deployment-local capacity measurement. P2.3 adds no schema
  migration; the rollback target is accepted P2.2 commit
  `a75d3327fdc1ab4b83b0bba501d387af150353c4`.
- `docs/NEXT_ACTIONS.md`, `docs/CODEX_CONTEXT.md` and
  `docs/13_RISKS_AND_TODO.md` were synchronized to the active P2.3 state.

### FineReport AI Plugin Local Probe (Deployment-Local Evidence)

#### Completed Facts

- Installed plugin `com.fr.plugin.decision.ai.v11` 1.2.5 from the local sample
  ZIP into the local FineReport 11.0 designer (jar 11.5.11) through the
  platform plugin manager; manual file copy into `WEB-INF/plugins` was proven
  insufficient for runtime registration.
- Established deployment-local evidence for the plugin contract: platform
  login and Bearer transport, OpenAPI token extraction order
  (`fine_auth_token` query, Bearer header, cookie), 302-to-login behavior on
  invalid tokens, the full `/ai/api/*` OpenAPI surface (health, auth/refresh,
  search/templates, templates/list+meta, params/range+validate,
  sessions+data, chart/validate, summary/template, embed) and the in-platform
  SSE chat chain (`/ai/assets/chat*`) with frame types
  `chatId/reasoning/msg/tool_call/complete` and `tokenUsage`.
- Main-JAR classes are vendor-encrypted; route-level facts were recovered from
  bundled plaintext frontend JS and runtime Arthas `jad` dumps of the loaded
  classes.
- Configured user-supplied DeepSeek (`deepseek-v4-flash`) and SiliconFlow
  embedding endpoints in the local plugin; plugin connectivity tests passed
  for streaming and tool-calling capabilities. Indexed two of four local FVS
  templates; the two failures trace to missing template files in
  `reportlets/`, not to the plugin.
- Permission inheritance measured with a zero-permission test user:
  list/search/meta/params/summary and chat retrieval enforce FineReport
  directory permission; recorded finding F-01 — the OpenAPI sessions chain
  (`POST /ai/api/sessions`, `GET /ai/api/sessions/{id}/data`) does not enforce
  template permission. Per user decision F-01 is record-only and does not
  block this project.
- Distilled results were synchronized into
  `docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md` §2 and R-043 /
  P2-external-gate status in `docs/13_RISKS_AND_TODO.md`. Raw probe evidence
  stays in gitignored `data/plugin-probe/`; no keys, tokens or vendor binaries
  were committed. The plugin remains `Unverified`; upgrade stability and
  official documentation remain open gate items.

## 2026-07-28

### P2.2 User Acceptance

#### Completed Facts

- The user explicitly accepted P2.2 through `确认验收` without conditions or
  scope reduction.
- P2.2 runtime candidate
  `a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
  `aaa499de416b522e21c02f41119024296fc2c3a0`, schema
  `p1_control_plane_001` and migration `005_controlled_querying` became the
  accepted runtime baseline.
- Acceptance retains the candidate fingerprint, 67-file raw-evidence manifest,
  exact real-database, browser, Docker, Secret-scan, recovery, accepted-P2.1
  rollback and zero-finding independent-review evidence recorded by commit
  `bacc172ed5b8811f46a8de89ba254306243f735b`.
- ADR-0030 became `Accepted` through this explicit P2.2 decision.
- Accepted P2.1 plus the verified WAL-safe pre-`005` copy remains the P2.2
  product/data rollback target. P2.3 remains queued and has not started.

### P2.2 Controlled Querying Candidate Preparation

#### Completed Facts

- Added checksum-backed additive migration `005_controlled_querying` with
  Site-owned source/dataset envelopes, immutable versions, exact draft/release
  sidecars, sanitized execution metadata and authenticated Secret envelopes.
- Added closed `.xlsx`, PostgreSQL, MySQL and Oracle adapters. Runtime accepts
  only a published dataset ID and typed parameters; database templates are
  administrator-approved, parsed single read-only statements with exact bind,
  relation and output allowlists.
- Added screen/session and credential-derived device catalogs, asynchronous
  start/poll/cancel, exact idempotency, global/per-screen bounds, terminal
  no-fallback behavior and 256-job bounded in-memory result retention.
- Integrated query assignment with validation, preview, NORMAL release,
  publication/acknowledgement and historical forward rollback without changing
  accepted P1.3/P2.1 schemas.
- Extended encrypted backup, fresh verification and staged restore validation
  across the P2.2 graph while preserving current matching source/dataset
  authority. Restore rejects live workers and terminalizes restored/startup
  orphan executions. Added fresh preview/browser launchers and a proposed
  ADR-0030.

#### Verification To Date

- Candidate-scoped Ruff passed; 116 API routes import; complete backend
  regression passed 67 cases with three real-database cases gated separately.
- PostgreSQL 17, MySQL 8.4 and Oracle Free 23 ephemeral read-only tests passed
  DB-side INSERT denial plus exact published device query execution.
- P2.2 target validation passed 47 checks and six mutation fixtures under both
  PowerShell hosts. Pinned pnpm 9.15.4 frontend build passed.
- A fresh 1280 by 720 browser run passed Excel registration, list refresh,
  source qualification, immutable dataset creation, unpublished zero execution
  and draft assignment display with no horizontal overflow or console
  warning/error.
- The first browser run found a missing QuerySource list projection field.
  The blocker was fixed, covered by regression and rerun from a fresh fixture
  before candidate creation.
- Independent review rejected the first immutable candidate for closed-SQL and
  OOXML bypasses, queued-cancel capacity leakage, stale queued authority,
  incomplete timeout/three-screen/recovery/audit behavior and negative-test
  gaps. The candidate was discarded.
- The repaired implementation now closes function/session-variable SQL,
  external/active OOXML, uses exact-once slot release, rechecks current
  authority before adapter entry, applies an end-to-end execution watchdog,
  audits backpressure and quiesces restore. Expanded tests prove three distinct
  concurrent screens, failure isolation, timeout, disabled/unverified/unbound
  zero execution, stale ETag/idempotency, immutable sidecars, database Secret
  recovery/AAD failure and restored-orphan termination.
- Independent review rejected replacement candidate
  `78b5af301a1c57915a4535d3decc11c59b79eba7` for one remaining SQL-expression
  family: Oracle `NEXTVAL`/`CURRVAL`, PostgreSQL custom operators and
  user-defined casts could invoke stateful or unapproved database logic.
  Validation now rejects those AST forms, and 21 cross-dialect closed-SQL
  negative cases plus all three real adapters pass.
- Froze final runtime candidate
  `a75d3327fdc1ab4b83b0bba501d387af150353c4`, tree
  `aaa499de416b522e21c02f41119024296fc2c3a0`, fingerprint
  `8A1A369FA328F6A516D9A36AD5F36C314629D2E683BBF38304510521817D357D`
  over 47 files.
- Exact Compose startup/migration/route probes, the fresh Excel browser flow,
  three ephemeral real-database adapters, Secret scan and accepted-P2.1
  rollback proof pass. Accepted P2.1 passed its 35 original tests and exposes
  only migration 004 with no P2.2 route/table.
- Independent reviewer Einstein returned `PASS` for the exact final candidate
  with zero blocking and zero non-blocking findings. At candidate publication,
  P2.2 was waiting for an explicit user decision and P2.3 had not started.

### P2.1 User Acceptance

#### Completed Facts

- The user explicitly accepted P2.1 (`通过P2.1`) without conditions or scope
  reduction.
- P2.1 runtime candidate
  `8f364b93b574c058cd8cd617f925107985318098`, tree
  `7c277e32b6419bd3720591c454e8282d94f081ec`, schema
  `p1_control_plane_001` and migration `004_capability_profiles` became the
  accepted runtime baseline.
- The acceptance package retains the complete gate, review, evidence-hash,
  recovery and accepted-P1.3 rollback record.
- ADR-0029 became `Accepted` through this explicit P2.1 decision.
- Accepted P1.3 remains the verified product-code and pre-`004` data rollback
  target. P2.2 was not activated by this acceptance decision.

### P2.1 Capability Profiles Candidate

#### Completed Facts

- Froze final runtime candidate
  `8f364b93b574c058cd8cd617f925107985318098`, tree
  `7c277e32b6419bd3720591c454e8282d94f081ec`, fingerprint
  `516995361810AF2D3F3FC609F4676D5A2D620216E6BB9DA305EDC57CD8622332`
  over 36 files.
- Added checksummed additive migration `004_capability_profiles` without
  changing accepted `p1_screen_config_v1` or rebuilding accepted P1.3 tables.
  The four structures hold Site-owned profile envelopes, immutable versions,
  exact draft-revision assignments and immutable ReleaseTarget capability
  snapshots.
- Added the closed seven-capability/21-Provider catalog, three immutable
  presets, five state meanings, Site/profile version management, exact draft
  assignment, release/rollback snapshot integration, authorized screen reads
  and credential-derived device resolution.
- Added the `/manage` capability-profile and three-screen effective-state
  workflow. External Providers remain unverified and disabled; the candidate
  performs only bounded local/Mock diagnostics and no real external request.
- Closed public-metadata, response-reflection and denial-audit surfaces;
  disabled request-target access logs in every P2.1 startup path; implemented
  terminal no-fallback plus bounded timeout, cancellation and backpressure.
- Made initialization and accepted-P1.3 copied upgrade validate the complete
  table/index/trigger/view structure. Recovery now validates reverse
  profile/assignment/snapshot/effective/fingerprint/approval/release
  references, rejects complete P2.1 row loss, uses immutable historical
  validation epochs and fails restored phantom idempotency/action results.

#### Verification

- Candidate-scoped Ruff passed over 13 Python files; API import exposed 98
  routes; all 35 backend cases passed with one dependency deprecation warning.
- P2.1 validation passed 206 checks and all 51 mutation cases under both
  PowerShell hosts. P1 regression passed 2,722 checks and 191 mutation cases
  under both hosts.
- Pinned pnpm 9.15.4 TypeScript/Vite build passed with 19 transformed modules.
- The 1280 by 720 interactive workflow was executed on candidate
  `3062b14863d1ed0a1f92f4f6a203a602cc4c6045`. The final candidate uses an
  explicit semantic rebind because the Vue UI, API client and browser fixture
  are byte-identical; the only launcher delta adds `--no-access-log` and passed
  runtime probes under both PowerShell hosts. The final interactive workflow
  was not rerun.
- Exact-candidate Docker/Compose build/runtime smoke passed all eight HTTP
  probes, migration/schema, log-sanitization, restart and cleanup checks.
- Accepted-P1.3 product rollback passed its original 22 tests, retained
  migration 003 and exposed no P2.1 route or schema object. The WAL-safe exact
  pre-004 online copy passed 12 verification checks.
- Candidate Secret scans, Git diff, fingerprint and lifecycle gates passed.
  Final evidence hashes remain bound in the P2.1 machine manifest after the
  stable acceptance package scan.

#### Independent Review And Decision State

- The first candidate `3062b14863d1ed0a1f92f4f6a203a602cc4c6045`
  failed with seven blockers. The second candidate
  `c9cd471762eb202371c11361c69b814cecffea1c` failed with six blocking
  finding families. The third candidate
  `6e43b17b4c9c75885c32b400112c985a0265b2ec` failed with two blockers. The
  fourth candidate `eba052678d3293448036d7426c61409063cb7c93` failed with one
  recovery blocker. Every finding is remediated in the final candidate.
- Reviewer Huygens independently archived and tested the final candidate.
  Archive SHA-256
  `C4C6A33FD7CE69EB4734ED9516942593B942E3B1E6925CDF92F07C602A3B0A74`,
  size 12,759,040 bytes. The final review returned PASS with zero blocking and
  zero non-blocking findings.
- The user subsequently accepted P2.1 without conditions as recorded above.
  P1.3 remains the verified rollback target, and P2.2 has not started.

### P2.1 Activation And Result Freeze

#### Completed Facts

- The user explicitly instructed Codex to complete P2.1, activating it as the
  sole current result batch.
- Froze the complete P2.1 result card, incremental target contract, machine
  provider registry and non-scope before runtime implementation.
- The result covers Site-owned versioned CapabilityProfiles, immutable
  ProfileVersions, additive draft/release capability sidecars, five distinct
  states, dependency/fallback validation, `/manage` configuration and
  credential-scoped three-screen resolution.
- Preserved accepted P1.3 runtime commit
  `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
  `04bcbb940fbedb5fbb8957e538f46a4422e15db2`, plus a required WAL-safe
  pre-`004` database backup as the rollback target.
- Kept P2.2 QuerySources, P2.3 integrated resilience certification, P2.4
  FineReport official-plugin adaptation, all real Provider connections,
  production activation, PostgreSQL, full-loss recovery and customer RPO/RTO
  outside the frozen batch.
- No P2.1 runtime implementation, automated result, external Provider result or
  user acceptance is claimed by this activation and freeze.

### P1.3 User Acceptance

#### Completed Facts

- The user explicitly accepted P1.3 (`通过`) without conditions or scope
  reduction.
- P1.3 runtime candidate
  `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
  `04bcbb940fbedb5fbb8957e538f46a4422e15db2`, schema
  `p1_control_plane_001` and migration `003_publish_rollback_recovery` became
  the accepted runtime rollback baseline.
- The acceptance package retains the final automated, browser, migration,
  Docker, Secret-scan, recovery, retention, P1.2 rollback, hash-binding and
  zero-finding independent-review evidence.
- That P1.3 acceptance decision did not activate P2.1; the user activated P2.1
  separately in the later instruction recorded above.

### P1.3 Publish, Rollback And Recovery Candidate

#### Completed Facts

- Final runtime candidate
  `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
  `04bcbb940fbedb5fbb8957e538f46a4422e15db2`, implements the frozen local
  development-preview result without changing accepted POC route meanings.
- Added checksummed migration `003_publish_rollback_recovery`, complete
  draft/validation/Mock preview/different-user approval, immutable normal
  releases, per-screen/group publication, credential-bound exact
  acknowledgement and immutable forward rollback.
- Added an encrypted four-file local bundle, source-snapshot validation,
  backup-record identity binding, fresh verification, staged online-source
  restore, live security-state reconciliation, retained pre-restore store and a
  global control-plane mutation barrier across backup/restore consistency
  boundaries.
- Added three-day runtime-detail cleanup while protecting users, device history,
  releases, publications, restore evidence and SecurityAuditEvent rows.
- Added the `/manage` release center and explicit P1.3 initialize, accepted-P1.2
  copied-upgrade, local launcher, browser-gate and Secret-scan scripts.
- Kept FVS `UNVERIFIED`, preview `MOCK_PASSED` and real FineReport/FVS/plugin,
  production activation, full-loss recovery, PostgreSQL and customer RPO/RTO
  certification outside the candidate.

#### Verification To Date

- Ruff format/check, API import and all 22 backend integration cases pass.
  Pinned pnpm 9.15.4 builds the 19-module web bundle.
- The 1280 by 720 release-center workflow completes draft, validation/preview,
  different-user release approval and typed publication with no horizontal
  overflow or captured console warning/error.
- An exact accepted-P1.2 database copy reaches migration 003 with its source
  unchanged, three bindings and clean foreign keys; repeat initialization
  leaves the upgraded file unchanged. The accepted P1.2 runtime still passes
  its original 14 tests and exposes no P1.3 route.
- Invalid-source backup creation returns 503 and leaves no record or bundle.
  Verified backup/restore recovers three bindings, retains the old store and
  cannot report a successful mutation that disappears across cutover.
- Three-day cleanup deletes expired runtime detail without deleting the
  protected control-plane rows. Exact-candidate Docker/Compose, P1 target
  validation and Secret scanning pass.
- The first independent review rejected candidate
  `93bae87f028f50d0f1abd09c5d6c458490d52273` with four blocking findings; the
  second rejected `20a2be319fd74f689c8a581734b1cb3b21e6b0a3` with one additional
  backup-source validation finding. All five paths are repaired in the final
  candidate and pass independent focused regression; the complete final
  independent review passed with zero blocking and zero non-blocking findings.
- The user subsequently accepted the candidate without conditions as recorded
  above; P2.1 remains queued.

## 2026-07-27

### P1.3 Activation And Result Freeze

#### Completed Facts

- The user explicitly instructed Codex to complete P1.3, activating it as the
  sole current result batch.
- Froze the complete P1.3 result card and non-scope before implementation.
  The result covers development-preview draft validation/Mock preview,
  different-user approval, immutable normal releases, single-screen/group
  publication, credential-bound acknowledgement, forward rollback, encrypted
  online-source logical backup/restore and three-day runtime-detail retention.
- Preserved accepted P1.2 runtime commit
  `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree
  `565dbb3567e2a4ae5b872177d97449120477fe8c`, plus a verified pre-`003`
  database copy as the rollback target.
- Kept real FineReport/FVS/plugin behavior, production activation, external
  RecoverySecurityLedger/WORM/OperationalFence, full-loss recovery, PostgreSQL
  and customer RPO/RTO certification outside the frozen batch.
- No P1.3 runtime implementation or verification result is claimed by this
  activation and result-card freeze.

### P1.2 User Acceptance

#### Completed Facts

- The user explicitly accepted P1.2 (`通过`) without conditions or scope reduction.
- P1.2 candidate commit `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree `565dbb3567e2a4ae5b872177d97449120477fe8c`, schema `p1_control_plane_001` and migration `002_three_screen_inventory` became the accepted runtime rollback baseline.
- The acceptance package retains the final automated, browser, migration, Docker, Secret-scan, P1.1 rollback and zero-finding independent-review evidence.
- P1.3 remains queued and is not activated by this acceptance record.

### P1.2 Three-Screen Inventory Candidate

#### Completed Facts To Date

- Added checksum-backed migration `002_three_screen_inventory` while preserving the accepted `001_initial_identity_device_trust` source and checksum.
- Added ownership-aware Site, ScreenGroup, ScreenInstance, DigitalHumanInstance, RuntimeBinding and server-side list-snapshot tables. Production startup still creates no preview inventory.
- Explicit preview initialization and accepted-P1.1 copied-database upgrade produce the frozen default Site, group and three screens. Screen 1 keeps `screen-trust-fixture`; Screens 2 and 3 use UUIDv7 IDs.
- Added scoped inventory read/create/update APIs with strong resource ETags, direct `screen.manage` mutations, opaque snapshot cursors, exact idempotent replay, duplicate rejection and cross-Site fail-closed behavior.
- Added one active DigitalHumanInstance and one RuntimeBinding per screen. FVS remains `UNVERIFIED`; inventory runtime remains `INVENTORY_INCOMPLETE` before the first instance and `NOT_CONFIGURED_P1_3` afterward.
- Added the `/manage` multi-screen view. Implementation engineers can maintain screen/group inventory; auditors receive a read-only view; screen-scoped readers cannot enumerate Site/group or sibling-screen data.
- Added explicit P1.2 initializer, local API launcher, accepted-P1.1 copy-upgrade and isolated browser-gate scripts. The upgrade uses SQLite's backup API, refuses overwrite, propagates native failure before writing the target env, restores the caller's root-key environment and never prints root-key material.
- Kept publication, release/rollback/recovery, real FVS connectivity, Secret values, providers and production activation outside P1.2.

#### Verification To Date

- Scoped Ruff formatting/check and 14 backend integration cases pass. They cover P1.1 behavior plus empty/repeat/failed/tampered/reordered/missing migration, accepted-P1.1 copy and active-WAL preservation, UUIDv7 inventory, pagination and scope narrowing, role/resource scope, sibling non-disclosure, replay isolation, Secret/DSN rejection, duplicate slugs/instances, stale/concurrent ETags, cross-Site membership, foreign keys, immutable audit and no-delete-cascade behavior.
- Pinned pnpm 9.15.4 TypeScript/Vite build passes; the Docker API/web images build and an isolated Compose runtime returns HTTP 200 for `/api/health` and `/manage`, reports migration `002_three_screen_inventory`, and shuts down cleanly.
- A real 1280 by 720 browser workflow passed initial three-screen display, isolated Screen 2 update, Screen 4 creation, first DigitalHumanInstance binding and auditor read-only controls with no horizontal overflow or captured console warning/error.
- An exact copy of the accepted P1.1 preview database upgraded to three screens while preserving all original device enrollment, credential-family and credential rows and the original 55-event audit prefix. Repeat initialization left the database file hash unchanged.
- The accepted P1.1 runtime commit still passes all ten original integration tests; rollback exposes migration `001_initial_identity_device_trust`, omits P1.2 Site/Screen list routes and retains the accepted P1.1 device runtime route.
- P1 target validation passes 2,722 checks and all 191 self-test cases. Candidate, bundle, SQLite, logs, screenshot and evidence Secret scans report zero operational-secret findings.
- The first independent review rejected candidate `2f0c4f3a4889b41910c4dc1397df4394762784dd`; all environment, Secret/DSN, scope/replay, migration-registry/ownership and WAL-copy findings were remediated.
- The final independent review of commit `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree `565dbb3567e2a4ae5b872177d97449120477fe8c`, passed with zero blocking and zero non-blocking findings. The user subsequently accepted the result without conditions as recorded above.

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
