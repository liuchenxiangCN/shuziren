# Result-Driven Productization Plan

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: Productization P1-P5 outcome roadmap
- Last reviewed: 2026-07-28
- Historical plan: [archive/poc-v1/root-snapshots/DEVELOPMENT_PLAN_FULL_HISTORY.md](archive/poc-v1/root-snapshots/DEVELOPMENT_PLAN_FULL_HISTORY.md)

## Planning Model

This plan is designed for Codex-driven development where the user reviews results rather than source code.

Work is not organized as sequential database, backend, frontend and testing phases. Every batch is a vertical result that includes the minimum data, API, UI, security, observability and recovery behavior needed for the user to exercise it.

Every batch must follow [RESULT_ACCEPTANCE_STANDARD.md](RESULT_ACCEPTANCE_STANDARD.md):

```text
result card
-> Codex implementation
-> automated gates
-> independent Codex review
-> runnable preview and evidence
-> user result decision
-> keep or restore last accepted version
```

## Global Gates

The following rules apply to every phase:

- Only one active result batch exists in `NEXT_ACTIONS.md`.
- Target behavior is never described as implemented before acceptance.
- A Mock result cannot replace real external-system evidence.
- A blocked vendor or customer dependency remains `Blocked`.
- Cross-screen leakage, authorization bypass, Secret exposure, data corruption and unrecoverable change are immediate failures.
- Every accepted batch has a rollback or restore path.
- Customer-specific behavior does not enter product core code.
- Screen control continues to use `action_id` plus backend whitelist validation.
- Free SQL and model-generated executable code remain prohibited.

## Route Overview

| Stage | Result Theme | User Acceptance Outcome | Status |
| --- | --- | --- | --- |
| P0 | Product boundary | Product scope, target customer and constraints are frozen | Done |
| G0 | Documentation and result governance | Codex reads one current task and every batch has an evidence gate | Accepted |
| P1 | Multi-screen control closed loop | Three screens can be registered, configured, published and rolled back independently | P1.0 through P1.3 accepted; complete |
| P2 | Per-screen capabilities and querying | Different provider combinations and controlled data sources work without cross-screen impact | P2.1 and P2.2 accepted; P2.3 planned and awaiting explicit activation; P2.4 blocked by external gate |
| P3 | Renderer extension mechanism | Test renderers and asset versions can switch safely without claiming real 2D / 3D support | Planned |
| P4 | Management and operations closed loops | Each product role completes its daily task without editing code or YAML | Planned |
| P5 | Standard delivery candidate | Installation, upgrade, backup, restore and acceptance are reproducible | Planned |

## P1 Multi-Screen Control Closed Loop

### Result Batches

#### P1.0 Target Contract Result Pack

User-visible result:

- Business-readable domain and identity diagrams.
- Screen enrollment and configuration-release state walkthroughs.
- Role-action matrix.
- Storage, migration, backup, restore, RPO and RTO decision.
- Control-plane API examples tied to user operations.

This batch does not change runtime code.

#### P1.1 Identity And Device Trust

User-visible result:

- An administrator can sign in and create implementation and audit users.
- A device can enroll once, obtain a separate credential, rotate it and be revoked.
- Audit users can inspect but cannot edit or reveal Secrets.

#### P1.2 Three-Screen Inventory

User-visible result:

- The management UI shows one Site, screen groups and at least three screens.
- Each screen has its own FVS binding, DigitalHumanInstance and runtime status.
- Changing one screen does not change another screen.

#### P1.3 Publish, Rollback And Recovery

User-visible result:

- A draft can be validated and previewed.
- A ConfigRelease can be published to one screen or a group.
- Version differences and audit history are visible.
- Rollback creates a new immutable release.
- A logical backup can be restored and the three screens recover their bindings.
- Runtime log retention defaults to three days without deleting users, releases or security audit records.

### Automated Gates

- Contract, schema and state-machine consistency.
- Password, session, lockout, reset and RBAC negative tests.
- Device credential replay, rotation and revocation tests.
- Database uniqueness, foreign-key and optimistic-concurrency tests.
- Three-screen identity, configuration, session and release isolation.
- Immutable release and illegal state-transition tests.
- Migration and backup-restore verification.
- Secret and sensitive-data scans.

### User Result Scenarios

1. Create an implementation user and a read-only auditor.
2. Enroll three test screens.
3. Give the screens different welcome text and Mock FVS bindings.
4. Publish only the second screen and confirm the first and third do not change.
5. Roll the second screen back.
6. Confirm the auditor cannot edit or reveal a Secret.
7. Restore a logical backup and confirm all three bindings return.

### P1 Stop Conditions

- Any cross-screen identity, configuration, data or release leakage.
- A published release can be edited in place.
- UI permission differs from API permission.
- Device credentials can be replayed after revocation.
- Backup cannot be restored.
- A core screen flow still requires direct YAML editing.

## P2 Per-Screen Capabilities And Querying

### Result Batches

#### P2.1 Capability Profiles

User-visible result:

- Each screen independently enables or disables Dora, knowledge, direct LLM, ASR, TTS, querying and FVS control.
- `disabled`, `mock`, `unverified`, `available` and `degraded` states are distinct.
- The management UI explains dependencies and safe fallback behavior.
- Three screens can resolve different profiles concurrently without sharing session or provider state.

#### P2.2 Controlled Excel And Database Querying

User-visible result:

- Administrators register Excel, MySQL, Oracle and PostgreSQL QuerySources.
- Business users select approved datasets; they never submit SQL.
- Answers show source, metric definition, time scope, permission subject, latency and request ID.
- Connection tests show understandable failures.
- Query-source acceptance includes concurrent requests, cancellation, timeout and failure isolation from the first real connector batch.

#### P2.3 Concurrent And Failure Isolation

User-visible result:

- This batch is an integrated resilience certification of P2.1 and P2.2, not the first introduction of concurrency controls.
- Three screens use different capability combinations concurrently.
- A slow query, cancellation or failed provider affects only the requesting screen.
- Equivalent fallback works; permission denial does not fall back.

#### P2.4 FineReport Official Plugin

This is a gated batch.

- Without official API, authentication, session, permission and upgrade evidence, the UI shows `Unverified` and publishing is disabled.
- After the external gate passes, the product can probe and call only documented external interfaces.
- The plugin is installed and licensed by the customer and is never included in this product.
- P2.4 passes only with official interface material, a certified exact version combination, a legal customer installation, confirmed authentication and session behavior, a least-privilege FineReport display / service identity, an authorized test FVS template, a successful minimum query and an upgrade re-test.
- Until all gate evidence exists, P2.4 remains `Blocked`; Mock evidence cannot pass it and the batch cannot be silently removed to declare P2 complete.

### Automated Gates

- The concurrency, cancellation, timeout, backpressure and fault-isolation gates apply to every accepted P2 batch, not only P2.3.
- Shared Provider contract suite for every implementation.
- Real-engine evidence before a database combination is marked supported.
- Read-only account, parameter binding, row limit, timeout and field / dataset whitelist tests.
- SQL injection, free SQL, write operation and unauthorized-field negative tests.
- Permission-equivalent fallback tests.
- Three-screen concurrent correctness, cancellation, timeout, backpressure and single-provider failure isolation.
- Mock and disabled regression tests.

### User Result Scenarios

1. Assign three different capability packages to three screens.
2. Query Excel and each certified database source.
3. Disconnect one provider and confirm only the bound screen degrades.
4. Query with an unauthorized identity and confirm safe denial without fallback.
5. Disable ASR, TTS or knowledge and confirm documented degraded behavior.
6. Inspect plugin status; it must remain unavailable until certified.

### P2 Stop Conditions

- Permission denial causes a more privileged fallback.
- Free SQL, writes or model-generated code can execute.
- One slow provider blocks other screens.
- A result lacks source or permission scope.
- Internal plugin paths are implemented without an official contract.

## P3 Renderer Extension Mechanism

V1 validates the extension mechanism and test renderer only. It does not certify a real 2D or 3D format.

### User-Visible Result

- The management UI lists Renderer providers, test AvatarPackages and compatibility state.
- One test asset version can be reused by multiple screens.
- Two test asset versions can be uploaded, previewed, prefetched and switched.
- A failed switch keeps the previous version visible.
- Packages containing scripts or using an unknown renderer are rejected with a clear reason.

### Automated Gates

- Manifest and schema validation.
- Hash, file-type, path-traversal, oversized-package and script-injection tests.
- Uncertified renderer, incompatible version and missing-resource tests.
- Prefetch, atomic switch, failure retention and rollback tests.
- Multi-screen asset isolation and duplicate-resource handling.
- No backend restart or frontend rebuild for a test asset version switch.

### User Result Scenarios

1. Upload two test AvatarPackage versions.
2. Preview both versions.
3. Publish the new version only to the second screen.
4. Simulate corrupted resources and confirm the previous version remains.
5. Upload a scripted package and confirm rejection.

### P3 Stop Conditions

- An asset package can execute arbitrary code.
- A failed switch causes a blank screen or loses the previous version.
- An uncertified renderer can enter production publishing.
- Test-renderer evidence is presented as real 2D / 3D support.

## P4 Management And Operations Closed Loops

P4 is organized by user jobs, not technical modules.

### Result Batches

- P4.1 Implementation loop: create screen, bind resources, test, preview and publish.
- P4.2 Business-operation loop: manage persona, voice, capability, knowledge, querying and interaction policy.
- P4.3 Operations loop: monitor, receive alert, diagnose by screen / provider / release and export a sanitized support package.
- P4.4 Security-audit loop: manage users, review high-risk operations and reconstruct a configuration change.

### User-Visible Result

- Platform administrator, implementation engineer, business operator, operations engineer and auditor see only their tasks.
- A new screen can be delivered without code or YAML editing.
- An alert is traceable to Site, screen, instance, provider and release.
- Support packages omit Secrets and complete sensitive business data.
- High-risk publish, rollback, device revocation and batch operations are confirmed and audited.

### Automated Gates

- Browser end-to-end flows for every role.
- UI and API authorization negative tests.
- Batch-operation partial failure, idempotency and retry tests.
- Alert trigger, recovery and attribution tests.
- Secret scans of support packages and frontend bundles.
- Accessibility, empty-state, error-state and target-resolution checks.
- Retention cleanup, audit integrity and configuration-drift tests.

### User Result Scenarios

1. A platform administrator creates an implementation user and an auditor, then verifies their different navigation and actions.
2. An implementation engineer registers, binds, tests, previews and publishes a new screen without editing YAML.
3. A business operator changes persona or capability settings and submits a preview without gaining system-administration access.
4. An operations engineer follows an alert to the affected screen, provider and release, then exports a sanitized support package.
5. An auditor reconstructs a configuration change, its approver, published release and rollback from immutable records.

### P4 Stop Conditions

- The UI hides an action but the API still permits it.
- A support package, log or frontend bundle exposes a Secret.
- A core role still needs a command line or direct configuration edit.
- A batch operation lacks per-item results or recovery behavior.
- Errors do not tell the operator what to do next.

## P5 Standard Delivery Candidate

### User-Visible Result

- A clean reference environment can install the product using the delivery guide.
- Three screens run concurrently.
- An accepted previous version upgrades without losing configuration or data.
- Backup, failure simulation, restore and product rollback are demonstrated.
- The support matrix clearly separates certified and unverified combinations.
- Product package, connector package, customer solution package and evidence package have explicit boundaries.
- The FineReport official plugin is absent from every product package.

### Automated Gates

- Installer / image hash, signature, SBOM, license and vulnerability checks.
- Clean-environment installation smoke.
- Upgrade data checks, database migration and rollback verification.
- Backup, restore and abnormal-process recovery drill.
- Full P1-P4 regression.
- FineReport, FVS, plugin, browser and database compatibility probes.
- Three-screen correctness and stability observation without claiming unlimited capacity.

### User Result Scenarios

1. A person who did not implement the product follows the guide to install it.
2. Register three screens and load a customer solution package.
3. Upgrade from the previous accepted version.
4. Damage disposable test data and recover from backup.
5. Restore the previous accepted product version.
6. Run the business matrix for query, knowledge, voice, screen control, degradation and operations.

### P5 Release Stop Conditions

- Clean installation is not reproducible.
- Upgrade loses data or lacks a verified recovery route.
- Backup cannot restore.
- A high-risk vulnerability, Secret leak or license issue remains open.
- An uncertified combination is presented as supported.
- Any P1-P4 security or isolation gate regresses.

## Evidence And Decision

Every result batch stores its acceptance card, automated summary, known limitations and user decision under:

```text
docs/acceptance/productization/<batch>/
```

Sanitized raw evidence belongs under:

```text
logs/productization/<batch>-<timestamp>/
```

A phase is complete only when all constituent result batches are accepted or explicitly removed from scope. Near-complete work, Mock-only external verification and undocumented workarounds do not count as completion.

Removing a batch from phase scope requires the user's explicit decision. User silence never counts as acceptance or scope approval.
