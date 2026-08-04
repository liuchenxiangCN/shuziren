# P3 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Batch: `P3 Renderer Extension Mechanism`
- State: `ACTIVE_RESULT_CARD_FROZEN`
- Activated by: explicit user instruction `开始P3`
- Activated at: 2026-08-04
- Base accepted runtime commit: `a124f63b8f3b5e499b6c561e78199a26f860edc9`
- Base accepted tree: `8a2f4e36ca0751b6106a174f7dae63be9299ad5b`
- Base acceptance record: `6488044ae731a5f4928874896452254897de5b5e`
- Candidate commit: `0b37f7c0917441543735c0b4a08d15e27a27f98c`
- Candidate tree: `48498864ea4c87e11e035b5439478d6c9b610046`
- Logical schema: `p1_control_plane_001`
- Latest migration: `006_renderer_avatar_packages`; additive and recoverable
- Target behavior: `P3 Renderer Extension Mechanism` in
  [05_DEVELOPMENT_PLAN.md](../../../05_DEVELOPMENT_PLAN.md) and section 10 of
  [17_STANDARD_PRODUCT_DESIGN.md](../../../17_STANDARD_PRODUCT_DESIGN.md)
- User decision: pending runnable-result review

## User-Visible Outcome

P3 proves the product extension and safe-switch contract with a deliberately
test-only Renderer. It does not certify or emulate a real 2D/3D supplier.

- The management UI lists the built-in test Renderer, its exact version,
  compatibility state and explicit `TEST_ONLY` boundary.
- An administrator or implementation engineer can add two immutable versions
  of one test AvatarPackage and preview their safe declarative appearance.
- One validated package version can be reused by multiple screens without
  copying or mutating it.
- A target screen must successfully prefetch and verify an exact package hash
  before switching. A switch is screen-bound and atomic.
- Failed verification or switching leaves the prior version active and gives
  an understandable, sanitized reason.
- Rollback restores the previous verified version as a new audited switch;
  package history remains immutable.

## Entry Point And Test Data

- Management entry: `/manage`, new `avatars` view.
- Runtime/control-plane entry: P3 Renderer catalog, AvatarPackage, preview,
  prefetch, per-screen binding, publication and rollback routes under
  `/api/v1/control-plane` plus a device-scoped current-avatar read.
- Test data: generated declarative `test-card` packages containing only a
  strict JSON preview resource. No executable resource, customer asset,
  supplier SDK or licensed archive enters the repository or evidence.

## Result Scenarios

1. List the Renderer catalog and confirm the only P3 Renderer is clearly
   marked test-only with an exact supported contract version.
2. Add version 1 and version 2 of one test AvatarPackage, preview both and
   confirm their manifest/resource hashes and compatibility are visible.
3. Prefetch version 1 to two screens and publish it to both; confirm both
   bindings reference the same immutable version.
4. Prefetch and publish version 2 only to the second screen; confirm the first
   screen remains on version 1 and no sibling binding or history changes.
5. Submit a wrong hash/corrupted resource and confirm prefetch or package
   validation fails while the currently active version remains visible.
6. Submit path traversal, an executable/script resource, an oversized package,
   an unknown Renderer or an incompatible Renderer version and confirm safe
   rejection with no stored partial package.
7. Roll the second screen back and confirm a new audited binding generation
   points to version 1 while immutable package and switch history remains.

## Required Gates

- Ruff format/check, API import, complete accepted P1.1-P2.3 regression and a
  dedicated P3 backend suite.
- Strict manifest/schema, semantic version, file count, byte limit, exact
  media type, normalized path, SHA-256 and duplicate-resource validation.
- Path traversal, absolute path, encoded separator, script/executable,
  archive, unknown Renderer, incompatible version and malformed declarative
  preview negative tests.
- Immutable package/version/resource history and optimistic concurrency on
  every screen binding mutation.
- Prefetch exact-hash verification, atomic switch, injected/verification
  failure retention, idempotency, rollback and restart persistence.
- Tenant/Deployment/Site/screen ownership, sibling non-disclosure, device
  credential scope, UI/API RBAC and audit sanitization tests.
- One immutable package version reused on multiple screens and three-screen
  isolation for switch, failure and rollback.
- Empty initialization, accepted-P2.3 copied upgrade, migration integrity,
  backup/restore and product-code rollback to the accepted P2.3 baseline.
- Frontend type/build and a fresh 1280 by 720 browser workflow with no
  horizontal overflow or unexpected console warning/error.
- Secret/sensitive-data scan, package fingerprint, lifecycle lint,
  `git diff --check`, Docker Compose smoke and independent read-only review
  with zero blocking findings.

## Frozen Non-Scope

- No real 2D or 3D Renderer, Live2D, Spine, glTF, GLB, VRM, transparent video,
  sequence-frame format, supplier SDK, production asset or licensing claim.
- No uploaded JavaScript, WebAssembly, shader, HTML, CSS, SVG, archive or
  model-generated executable content; preview data is declarative and rendered
  only by product-owned code.
- No online Renderer installation, plugin loading, dynamic import, eval,
  subprocess or backend/frontend restart as part of an asset switch.
- No FineReport official-plugin work; P2.4 remains deferred, blocked and in
  product scope.
- No production activation, CDN/object store, distributed asset cache,
  customer compatibility certification or high-concurrency/SLA claim.
- No change to accepted POC route meanings or accepted P1/P2 identity,
  device, release, recovery, capability, querying or resilience semantics.

## Immediate Failure Conditions

In addition to the global failure conditions, P3 immediately fails if a
package can execute code, a failed switch blanks or replaces the current
avatar, a package/version/resource mutates in place, a screen can observe or
change a sibling binding, an unknown Renderer becomes publishable, or
test-only evidence is presented as real 2D/3D support.

## Rollback Target

Product-code rollback target is accepted P2.3 runtime commit
`a124f63b8f3b5e499b6c561e78199a26f860edc9`, tree
`8a2f4e36ca0751b6106a174f7dae63be9299ad5b`. The final candidate must document
whether P3 adds an additive migration, prove accepted-P2.3 code against a
pre-P3 database and provide the exact forward-restoration procedure for any
P3 data created after that baseline.
