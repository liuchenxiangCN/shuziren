# P3 Implemented API

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: ACTIVE_CANDIDATE
- Candidate commit: `0b37f7c0917441543735c0b4a08d15e27a27f98c`
- API version: v1
- Production use: forbidden; test-only Renderer evidence

This file describes only the P3 candidate implementation. It does not claim
support for a real 2D or 3D Renderer or asset format.

## Control-Plane Routes

All control-plane routes require the existing browser session, CSRF policy,
RBAC and Tenant/Deployment/Site/screen ownership checks.

- GET /api/v1/control-plane/renderer-providers returns the immutable registry.
  P3 contains only test_card 1.0.0, marked test_only and not production
  eligible.
- GET /api/v1/control-plane/avatar-packages returns only packages in sites
  visible to the principal.
- POST /api/v1/control-plane/avatar-packages creates one immutable package
  version. It requires config.edit_technical and Idempotency-Key. The strict
  body is site_id, manifest and files; validation completes before the single
  storage transaction.
- GET /api/v1/control-plane/avatar-package-versions/{version_id}/preview
  returns the verified product-rendered preview model, Renderer compatibility,
  manifest/content hashes and each resource path, media type, byte count and
  SHA-256.
- POST /api/v1/control-plane/screen-instances/{screen_id}/
  avatar-package-versions/{version_id}:prefetch requires config.preview and
  Idempotency-Key. It records READY only when expected_content_hash exactly
  matches the recomputed immutable content hash; otherwise it records FAILED
  with CONTENT_HASH_MISMATCH and changes no binding.
- GET /api/v1/control-plane/screen-instances/{screen_id}/avatar-binding
  returns current, previous, generation, ETag and bounded switch history.
- POST /api/v1/control-plane/screen-instances/{screen_id}/
  avatar-publications requires release.publish, If-Match, expected binding
  generation and Idempotency-Key. The exact package must already have a READY
  prefetch for that screen.
- POST /api/v1/control-plane/screen-instances/{screen_id}/avatar-rollbacks
  requires release.rollback and the same concurrency/idempotency controls. It
  creates a new generation pointing to the previous verified version.

Cross-site or cross-screen targets are sanitized as not found. Changed
commands cannot reuse an idempotency key. Stale ETags or generations fail
without changing the binding.

## Device Route

- GET /api/v1/device/avatar/current requires an active device credential and
  returns only that credential's screen_id, state, generation, current
  verified package and ETag.

No device-prefix package creation, preview, prefetch, publication or rollback
route exists.

## Closed Package Contract

The only accepted resource is avatar.json with media type
application/vnd.shuziren.test-avatar+json. The manifest is schema
p3_avatar_package_v1, avatar_type test, Renderer test_card with range ^1.0.0,
all five states mapped to avatar.json, volume lip sync and a TEST_ONLY /
DEVELOPMENT_PREVIEW license. JavaScript, WebAssembly, HTML, CSS, SVG,
archives, executables, path traversal, encoded separators, malformed hashes,
unknown Renderers and incompatible versions are rejected.
