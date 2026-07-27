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
- An isolated Docker / Compose build and runtime smoke passed for the API and web preview. This is local packaging evidence only; production HTTPS, customer infrastructure, orchestrator, backup and upgrade behavior remain uncertified.
- FineReport plugin behavior remains Blocked by the P2 external gate.
- Two independent review rounds failed earlier candidates and their findings are remediated in the current candidate. Final re-review of the frozen commit is Pending; P1.1 must not be presented for user acceptance until it passes.
