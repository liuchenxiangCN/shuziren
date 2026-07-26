# Changelog

## Document Status

- Lifecycle: `AUTHORITATIVE_CURRENT`
- Scope: standard-product changes
- Last reviewed: 2026-07-27
- Historical POC changelog: [archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md](archive/poc-v1/root-snapshots/CHANGELOG_FULL_HISTORY.md)

## Unreleased

### Added

- Documentation lifecycle and archive policy.
- Result acceptance standard for Codex-driven development.
- Target product contract namespace under `docs/product/contracts/`.
- G0 acceptance package structure.
- Documentation lifecycle lint script.
- Lifecycle-lint negative-fixture self-test and reproducible candidate fingerprint.
- Active product risk and blocker view.
- ADR-0027 for result-driven development and document lifecycle.
- SHA-256 manifest for archived root snapshots.
- P0-preserving G0 rollback-target exporter and recovery proof.

### Changed

- Current context now contains only the product snapshot, current phase, as-built boundary and non-negotiable rules.
- Next Actions now contains exactly one active G0 acceptance batch and queues P1.0 after user acceptance.
- P1-P5 now use vertical user-visible result batches, automated gates, independent review, evidence and rollback instead of traditional component phases.
- Current risk tracking no longer mixes POC现场 issues, customer tasks and product risks.
- POC API and data contracts are explicitly classified as implemented POC truth, not target product contracts.
- Root documentation index classifies product, as-built POC, customer and archive material.
- Root `AGENTS.md` is now stable Codex policy and root `README.md` is stable product navigation; dynamic phase and task status were removed from both.

### Archived

- Long-form context, next actions, development log, development plan, risk list and POC changelog snapshots.

### Security

- FineReport official plugin archives are excluded from Git and remain outside product distribution.
- Result acceptance treats cross-screen leakage, authorization bypass, Secret exposure, data corruption and unrecoverable changes as immediate failures.

### Not Implemented

- G0 changes documentation and development governance only.
- Multi-screen runtime, target control-plane APIs, RBAC, database querying, FineReport plugin calling and real 2D / 3D rendering remain unimplemented product targets.
