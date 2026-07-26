# G0 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Candidate: working tree documentation state on 2026-07-27

## Limitations

- G0 changes documentation governance only; runtime behavior is unchanged.
- P1 target domain, data and API contracts are not yet designed.
- Long-form archive snapshots intentionally retain outdated commands and environment facts as historical evidence. They are excluded from active lifecycle lint and carry archive warnings.
- Stable-path POC documents remain in `docs/` to avoid breaking runtime references and historical links; lifecycle banners and the index prevent them from being treated as product target truth.
- Customer fixture files under `docs/demo_data` and `docs/demo_knowledge` remain at their existing runtime-compatible paths and are explicitly classified as POC fixtures.
- The local FineReport plugin ZIP is not moved or deleted; it is ignored by Git and remains non-distributable vendor evidence.
- The candidate remains an uncommitted working tree until the user requests a Git operation; its reproducible file fingerprint, file count and evidence hashes identify the reviewed state.
- Raw rollback and fingerprint evidence is local under ignored `logs/productization/`; the tracked manifest contains sanitized hashes and conclusions.
- G0 is not accepted until the user records a result decision.
