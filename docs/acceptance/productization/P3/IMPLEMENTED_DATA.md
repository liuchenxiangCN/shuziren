# P3 Implemented Data

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: ACTIVE_CANDIDATE
- Logical schema: p1_control_plane_001
- Latest migration: 006_renderer_avatar_packages
- Candidate commit: `0b37f7c0917441543735c0b4a08d15e27a27f98c`

Migration 006 is additive. It preserves all accepted P1 and P2 tables and
adds six P3 sidecar tables.

## Tables

- avatar_packages: immutable package identity per tenant, deployment, site
  and avatar_id, with display name, creator and creation time.
- avatar_package_versions: immutable semantic version, exact schema and
  Renderer contract, canonical manifest, manifest/content hashes, canonical
  preview, byte count and creator. Package plus version is unique.
- avatar_package_resources: immutable bytes keyed by package version and
  normalized resource path, with exact media type, size and SHA-256.
- screen_avatar_bindings: mutable screen pointer containing current and
  previous package version, monotonically increasing generation, actor and
  update time. It is the only mutable P3 data row.
- avatar_prefetch_records: immutable per-screen verification evidence with
  expected hash, READY or FAILED outcome and sanitized failure code.
- avatar_switch_records: immutable per-screen PUBLISH or ROLLBACK history,
  from/to versions, outcome, binding generation, reason and actor.

Foreign keys bind packages to sites and users, versions/resources to their
parents, and bindings/evidence/history to screens and package versions.
Schema-integrity startup checks compare tables, indexes and triggers against
the migration registry. Update/delete triggers prevent mutation of package,
version, resource, prefetch and switch history.

## Integrity And Recovery

Every read before preview, switch, rollback or device delivery recomputes the
manifest hash, every resource SHA-256 and the domain-separated package content
hash. Backup creation and verification additionally revalidates migration
objects, the closed declarative package contract, ownership, binding,
prefetch and switch-history consistency. Restore stages beside the live
database, preserving atomic same-volume replacement on Windows.
