# ADR-0032: P3 Test Renderer And Screen-Bound Avatar Switching

## Status

Accepted

The user explicitly accepted P3 on 2026-08-04 after the bound candidate,
automated evidence, limitations and independent review were presented.

## Date

2026-08-04

## Context

The product design reserves an AvatarRendererProvider and AvatarPackage
extension boundary, but no licensed 2D/3D asset, supplier SDK or certified
browser/GPU combination is available. P3 must prove that packages can be
validated, reused, prefetched, switched per screen and rolled back without
presenting generated evidence as real 2D/3D support or creating a dynamic-code
loading mechanism.

## Decision

1. P3 registers one built-in `test_card` Renderer at exact contract version
   `1.0.0`. It is always `TEST_ONLY`, `production_eligible=false` and supports
   only `avatar_type=test` with schema `p3_avatar_package_v1`.
2. A package version is an immutable manifest plus one product-owned
   declarative `avatar.json` resource. The backend validates the closed
   schema, semantic version, exact media type, normalized path, file count,
   byte size, duplicate paths and SHA-256 before one transaction persists any
   package row. JavaScript, WebAssembly, HTML, CSS, SVG, archives, executables,
   absolute/traversal/encoded paths and unregistered or incompatible
   Renderers are rejected.
3. Package, version and resource history is immutable. A version may be
   referenced by multiple screens; no per-screen package copy or mutation is
   created.
4. A screen switch requires a prior `READY` prefetch record for that exact
   screen, package version and content hash. Binding updates use ETags,
   expected generations, idempotency and one database transaction. Failed
   verification or switching never changes the current binding.
5. Rollback is a new audited binding generation pointing to the previous
   verified version. Switch history remains immutable; the device surface can
   read only its own screen's current binding.
6. Migration `006_renderer_avatar_packages` is additive. Encrypted backup
   verification revalidates the P3 schema, package hashes, declarative content,
   ownership, prefetch evidence and switch history. Restore staging is created
   on the live database volume so the final replacement remains atomic on
   Windows.

## Consequences

- Operators can demonstrate two safe test versions, reuse one version across
  screens, simulate a corrupt hash, switch only the selected screen and roll
  back without restarting the backend or rebuilding the frontend.
- This result does not add a real renderer format, supplier compatibility,
  asset licensing, shader/plugin execution, CDN or production cache.
- Accepted P2.3 code cannot open a database already migrated to 006. Product
  rollback therefore retains the P3 database and serves accepted P2.3 against
  a verified pre-P3 database copy; returning to P3 restores the retained P3
  database or a verified P3 backup.

## Follow-Up

- A real 2D/3D adapter requires a separate result card, licensed assets,
  supplier contract, browser/GPU compatibility evidence and production
  security review.
- P2.4 remains deferred and blocked by the independent FineReport official
  plugin evidence gate.
