# P3 Known Limitations

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: `ACCEPTED`
- Candidate commit: `0b37f7c0917441543735c0b4a08d15e27a27f98c`
- User decision: `通过` without conditions or scope reduction on 2026-08-04

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
- Docker Compose and the Mock demo smoke pass. External RAGFlow was
  deliberately unconfigured, so the dependency aggregate remains a warning;
  this is not real-provider evidence.
- The full repository Ruff command still reports 12 format files and 27 lint
  findings in untouched POC-era files. All P3 candidate Python files pass
  format/check; the historical baseline is not silently reformatted in this
  batch.
- The historical P2.3 validator intentionally requires migration head 005 and
  therefore is not a forward-compatible P3 validator. P3 uses its own
  head-006 contract and complete backend regression instead of weakening the
  accepted P2.3 invariant.
- P2.4 remains deferred and Blocked by its independent official-plugin
  evidence gate.

User acceptance cannot convert these test-only results into real Renderer,
asset-license, supplier, production-capacity or customer-compatibility
certification.
