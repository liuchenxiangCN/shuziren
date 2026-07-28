# P2.1 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Result: versioned per-screen capability profiles and credential-scoped runtime resolution
- Base accepted runtime: commit `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree `04bcbb940fbedb5fbb8957e538f46a4422e15db2`
- Base acceptance record: commit `c24f041a0414ea5361a6fcb7216d7be99ea0bb56`
- Candidate commit: `8f364b93b574c058cd8cd617f925107985318098`
- Candidate tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- Candidate fingerprint: `516995361810AF2D3F3FC609F4676D5A2D620216E6BB9DA305EDC57CD8622332` over 36 files
- Logical schema / migration: `p1_control_plane_001` / `004_capability_profiles`
- Capability schemas: `p2_capability_profile_v1` / `p2_provider_registry_001`
- Gate summary: automated candidate gates `PASS`
- Independent review: `PASS`; reviewer Huygens, zero blocking and zero non-blocking findings
- User decision: `通过` on 2026-07-28

This card froze the complete P2.1 result and non-scope before runtime
implementation. The candidate above implements the bounded local
development-preview result, passed its automated gates and final independent
review, and was explicitly accepted without conditions on 2026-07-28. It is
now the accepted runtime baseline for subsequent productization batches.

## Frozen Observable Outcome

P2.1 must deliver one independently usable development-preview slice:

1. The `/manage` console adds a capability-profile view. An implementation
   engineer can inspect the provider catalog, copy one of three product
   presets, configure the exact seven capability switches and create immutable
   profile versions.
2. Every profile visibly distinguishes `disabled`, `mock`, `unverified`,
   `available` and `degraded`. The console explains closed behavior,
   dependencies, technical-only fallback and terminal permission failures.
3. A profile version can be assigned to a P1.3 configuration draft without
   changing the accepted two-field `p1_screen_config_v1` base schema. The
   assignment advances the draft revision and invalidates stale validation,
   preview and approval evidence.
4. Existing validation, Mock preview, different-user approval, immutable
   ConfigRelease, single-screen/group publication, device acknowledgement and
   forward rollback include an exact immutable capability snapshot.
5. A control-plane reader can see each authorized screen's desired and applied
   capability profile. A device can resolve only the applied profile for the
   screen derived from its active credential.
6. Three screens can publish, acknowledge and resolve three different profile
   versions concurrently, including the same caller session label, without
   sharing screen, DigitalHumanInstance, ReleaseTarget, Provider selection,
   state or failure evidence.
7. A profile containing an enabled unverified Provider remains inspectable but
   cannot pass draft validation or become a new release. FineReport official
   plugin status remains `unverified`; no external call occurs.
8. Backup, verification, staged restore, retention and product-code rollback
   preserve the accepted P1.3 security and recovery boundaries plus all P2.1
   profile/version/snapshot data.

## Frozen Data And Immutability Model

Checksummed migration `004_capability_profiles` adds only additive structures:

| Structure | Frozen purpose |
| --- | --- |
| `capability_profiles` | Site-owned mutable envelope, display metadata, head version and strong revision |
| `capability_profile_versions` | Immutable canonical `p2_capability_profile_v1` versions and hashes |
| `config_draft_capability_assignments` | Immutable exact profile-version assignment per draft revision |
| `release_target_capability_snapshots` | Immutable per-screen resolution copied into a ReleaseTarget |

P1.3 tables and their frozen schema checks are not rebuilt or weakened.

Every ProfileVersion binds:

- Tenant, Deployment and Site ownership;
- profile ID, version ID and monotonic version number;
- closed seven-capability canonical spec and SHA-256;
- provider registry version/hash;
- server-derived state summary, dependency findings and activation eligibility;
- creator and creation time.

The mutable profile envelope never enters a release. An existing release
continues to resolve its exact immutable version after the profile head moves.
All four new structures reject Secret-like content and cross-scope references.

## Frozen Capability Schema

The exact capability keys are:

- `dora`
- `knowledge`
- `direct_llm`
- `asr`
- `tts`
- `querying`
- `fvs_control`

Every capability contains exactly:

- `enabled`
- `primary_provider_id`
- ordered `fallback_provider_ids`
- bounded `timeout_ms`

Disabled requires a null primary and no fallback. Enabled requires one
catalogued primary for the same capability. Fallbacks must be unique,
same-capability, same screen-bound permission scope and different from the
primary. Timeout is 100 through 120000 milliseconds.

The profile accepts no URL, endpoint, Secret reference, credential, DSN,
Provider payload, Prompt, SQL, executable code, health result, certification
claim, state override or fallback decision.

## Frozen Provider And State Boundary

The exact provider registry is
[p2-1-capability-profile-contract.json](../../../product/contracts/p2-1-capability-profile-contract.json).
The runtime implements only deterministic local/Mock selection and diagnostic
behavior. It performs no real external-provider call.

State semantics:

- `disabled`: explicit off; zero Provider execution.
- `mock`: development preview/failure drill only.
- `unverified`: external evidence absent; profile inspectable but activation
  blocked.
- `available`: bounded local behavior usable in the preview boundary.
- `degraded`: documented reduced behavior, never presented as full capability.

Fallback is allowed only for `timeout`, `unavailable` or `unsupported`, and only
to an equivalent screen-bound permission scope. `permission_denied`,
`invalid_request`, `unauthorized_template` and `cancelled` are terminal.

## Frozen Draft, Release And Runtime Integration

- `p1_screen_config_v1` remains exactly `welcome_text` plus
  `fvs_binding_ref`.
- A populated draft receives its capability assignment through a technical
  write with `If-Match`.
- Assignment creates a new draft revision, copies the base spec, records the
  exact version/hash and clears prior validation, preview and approval.
- A later base-spec replacement or legal draft revision copies the current
  assignment to the new draft revision.
- Validation binds the assignment, registry and canonical per-screen capability
  envelope into the existing ResolutionFingerprint.
- NORMAL release creation copies one immutable capability snapshot per target.
- Rollback copies the historical base target and capability snapshot
  byte-for-byte into a new release.
- Publication still changes only desired state. Device acknowledgement still
  changes applied state only after exact credential/screen/target/generation/
  content checks.
- Capability resolution reads only the applied ReleaseTarget. An old P1.3
  target without a capability snapshot returns `NOT_CONFIGURED_P2_1`; there is
  no global Provider or Mock fallback.

## Frozen API Slice

P2.1 adds:

| Operation | Method and path |
| --- | --- |
| List provider catalog | `GET /api/v1/control-plane/capability-providers` |
| List immutable presets | `GET /api/v1/control-plane/capability-profile-presets` |
| List/create profiles | `GET` / `POST /api/v1/control-plane/capability-profiles` |
| Read profile | `GET /api/v1/control-plane/capability-profiles/{profile_id}` |
| Create immutable version | `POST /api/v1/control-plane/capability-profiles/{profile_id}/versions` |
| Assign draft profile | `PUT /api/v1/control-plane/config-drafts/{draft_id}/capability-profile` |
| Read screen resolution | `GET /api/v1/control-plane/screen-instances/{screen_id}/effective-capabilities` |
| Resolve device profile | `GET /api/v1/device/capabilities/current` |

Profile reads require `config.read`. Create/version/assign require
`config.edit_technical`. All browser mutations keep exact Origin, bound CSRF,
server-side session, scope, strong ETag and request-bound idempotency controls.
The device route accepts no ownership or screen selector.

## User Result Scenarios

1. Open capability profiles, inspect all five state meanings and copy the
   `text_only` preset into a Site-owned custom profile.
2. Create a second immutable version by changing only allowlisted capability
   selectors, fallback order and timeout; confirm version 1 does not change.
3. Create text-only, Mock voice and Mock presenter profiles, assign one to each
   of three screens and preview three different effective snapshots.
4. Complete approval, publication and device acknowledgement for one screen;
   confirm only its desired/applied target, generation, acknowledgement and
   capability resolution change.
5. Resolve all three screens concurrently with the same session label and
   confirm screen, DigitalHumanInstance, profile, Provider state and failure
   context remain separate.
6. Configure `finereport_ai_plugin` or another unverified external Provider;
   confirm the UI explains the blocked dependency and release validation fails
   without any network call or fallback.
7. Publish profile version 2, view the exact difference, then forward-roll back
   to version 1; confirm a new release is created and all historical rows stay
   immutable.
8. Verify an auditor is read-only, create/verify/restore an encrypted backup,
   confirm three applied profiles return and prove code/data rollback to
   accepted P1.3.

## Required Gates

- Ruff format/check, API import and the complete P1.1-P1.3 plus P2.1 backend
  suite.
- Machine target-contract validation and negative fixtures.
- Empty initialization, accepted-P1.3 copied upgrade, repeat migration,
  migration-checksum tamper rejection and WAL-safe pre-`004` rollback copy.
- Profile schema closure, provider/capability mismatch, unknown/duplicate
  fallback, timeout bounds and arbitrary-payload rejection.
- Secret/DSN/token/credential rejection over profile names, descriptions,
  specs, requests, responses, audit, SQLite, backup, frontend and evidence.
- Strong ETag, exact idempotency replay, changed-command replay and immutable
  ProfileVersion/snapshot tests.
- UI/API RBAC, Tenant/Deployment/Site/profile/screen non-disclosure and
  cross-scope reference tests.
- Draft assignment revision, stale approval/fingerprint, unverified activation
  block and legacy-target `NOT_CONFIGURED_P2_1` tests.
- Single-screen and group release, publication, acknowledgement, rollback and
  historical immutability regression.
- Three-screen concurrent resolution using three different profiles plus
  per-screen session/Provider/error state isolation.
- Disabled-zero-execution, Mock labelling, degraded limited behavior and
  terminal permission-denial/no-fallback tests.
- Timeout, cancellation, backpressure and technical-only equivalent fallback
  contract tests for the local/Mock diagnostic boundary.
- Encrypted backup/verify/restore with new-table hash/reference validation,
  retained pre-restore store and protected retention counts.
- Frontend type/build and a 1280 by 720 browser workflow with no horizontal
  overflow or console warning/error.
- Pinned pnpm, Docker Compose exact-candidate smoke, P1 target regression,
  lifecycle lint, `git diff --check`, exact candidate-tree fingerprint and
  evidence hashes.
- Separate read-only Codex review of the immutable candidate with critical
  negative-test reruns and zero blocking findings.
- Product-code rollback to accepted P1.3 runtime plus a verified exact
  pre-`004` online backup. The P1.3 archive must pass its original 22 tests and
  expose no P2.1 route.

## Frozen Non-Scope

- No Excel, MySQL, Oracle or PostgreSQL QuerySource registration or execution;
  no real query, dataset, SQL or data-permission certification. Those belong to
  P2.2.
- No P2.3 integrated resilience/capacity certification, high-throughput claim,
  cluster behavior or SLA. P2.1 still proves its own three-screen correctness
  and local/Mock failure contract.
- No FineReport official-plugin adapter, undocumented/internal API,
  authentication, session, permission inheritance, template discovery, real
  request or compatibility certification. Those belong to gated P2.4.
- No real Dora, RAGFlow, direct LLM, ASR, TTS or FVS customer connection,
  credential or availability claim.
- No ConnectorInstance, SecretRecord/SecretVersion, QuerySource,
  ScreenActionPack CRUD or arbitrary provider extension.
- No real FVS action execution and no executable JavaScript, SQL, Python or
  shell.
- No Renderer, AvatarPackage, production activation, PostgreSQL control-plane
  store, full-loss recovery, external monotonic anchors or customer RPO/RTO.
- No change to accepted POC route meanings or P1.1 identity/device trust, P1.2
  inventory isolation, or P1.3 release/recovery/retention semantics.

## Immediate Failure Conditions

- Profile, assignment, release snapshot or resolution crosses Tenant,
  Deployment, Site, screen, DigitalHumanInstance or device scope.
- A single-screen operation changes any sibling binding, acknowledgement,
  profile, ETag, session or Provider state.
- A mutable head or new registry meaning changes a published historical
  snapshot.
- A stale draft/profile ETag, fingerprint, approval, target generation or
  changed idempotency command succeeds.
- A disabled capability selects or invokes a Provider.
- Mock or unverified evidence is presented as real, available, certified or
  production-ready.
- Permission denial, invalid input, unauthorized template or cancellation
  triggers fallback.
- FineReport plugin, QuerySource or any external Provider is contacted.
- Secret, DSN, token, credential, customer endpoint, free SQL or executable
  content enters profile/config/API/audit/log/backup/frontend/evidence.
- Migration/restore loses a profile/version/snapshot, revives older P1
  authority or leaves no usable accepted rollback point.

## Rollback Target

Product-code rollback target is accepted P1.3 runtime commit
`0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`, tree
`04bcbb940fbedb5fbb8957e538f46a4422e15db2`, plus a verified WAL-safe exact
pre-`004` database backup from the accepted P1.3 schema.

Rollback acceptance must prove the archived P1.3 runtime passes its original 22
tests, retains identity, device trust, three-screen inventory, release,
publication, acknowledgement, rollback, encrypted recovery and retention
behavior, and exposes no P2.1 route.
