# P3 Known Limitations

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: ACTIVE_CANDIDATE
- Candidate commit: TBD
- User decision: pending

## Frozen Limits

- P3 is a local development-preview extension-contract result. It is not
  production activation and does not certify a real 2D or 3D Renderer.
- test_card is product-owned, declarative and TEST_ONLY. It is not Live2D,
  Spine, glTF, GLB, VRM, transparent video, a supplier SDK or a compatibility
  claim for any browser/GPU/driver combination.
- Packages contain exactly one small JSON preview resource. No online
  Renderer installation, dynamic import, script, shader, WebAssembly, HTML,
  CSS, SVG, archive or executable content is supported.
- Assets remain inside SQLite for this bounded proof. P3 adds no object store,
  CDN, distributed cache, resumable upload, antivirus service or production
  cache-eviction policy.
- A switch is atomic in the control-plane database. P3 does not introduce a
  real renderer process, conversation-boundary handoff, frame-level health
  monitor or customer-display SLA.
- Migration 006 is forward-only. Accepted P2.3 code rejects a database whose
  migration registry already contains 006. Product rollback requires a
  verified pre-P3 database copy while retaining the P3 database for forward
  restoration; it never edits migration history in place.
- The browser workflow is local and Mock/test-only. No external provider,
  licensed asset, FineReport/FVS combination or customer environment is
  certified.
- P2.4 remains deferred and Blocked by its independent official-plugin
  evidence gate.

User acceptance cannot convert these test-only results into real Renderer,
asset-license, supplier, production-capacity or customer-compatibility
certification.
