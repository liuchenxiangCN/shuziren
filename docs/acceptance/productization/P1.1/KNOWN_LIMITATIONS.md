# P1.1 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_FROZEN_REVIEW_PENDING`

## Frozen Limits

- P1.1 proves local identity, browser-session, RBAC, audit and device-trust behavior only.
- The screen used for device trust is an explicit fixture, not P1.2 inventory evidence.
- Development preview identity initialization is never a production bootstrap or custodian-attestation claim.
- Network `createUser` correctly creates only a disabled, passwordless, empty-role `PROVISIONING` record. Complete target-person credential setup, custodian binding, role replacement and enablement are not yet implemented; the preview's usable auditor and implementation identities come only from explicit local initialization.
- Production activation, external monotonic anchors, full security-ledger recovery, PostgreSQL and backup / restore remain unverified.
- Local API/web startup and the complete browser workflow passed. The retained screenshot shows the sanitized auditor view and contains no observed credential material.
- Docker / Compose execution is Blocked on the current host because the Docker CLI is unavailable; no image digest or container smoke is claimed.
- FineReport plugin behavior remains Blocked by the P2 external gate.
- The first independent Codex review failed the earlier candidate and its findings are remediated in the current candidate. Independent re-review of the repaired commit is Pending; P1.1 must not be presented for user acceptance until it passes.
