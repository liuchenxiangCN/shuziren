# P2.3 Automated Summary

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `a124f63b8f3b5e499b6c561e78199a26f860edc9`
- Candidate tree: `8a2f4e36ca0751b6106a174f7dae63be9299ad5b`
- Candidate fingerprint:
  `FE0F87AC1B3F1FD5373681E86BDFA0DE909D6A1E637BD22E2A97DEFD57F26097`
  over 36 files
- Automated gates: `PASS`
- Independent review: `PASS_WITH_NONBLOCKING`; zero blocking findings,
  seven non-blocking findings, N1–N3 closed before candidate binding
- User decision: `通过` without conditions or scope reduction on 2026-07-29

## Passed Results

- Candidate-scoped Ruff format/check passed over the P2.3 Python files; the
  API imports with 120 routes (accepted P2.2 exposed 116). Full-tree Ruff
  reports the same pre-existing POC-era findings at the accepted P2.2 base,
  so the gate is candidate-scoped exactly as in accepted P2.2.
- Complete backend regression passed 77 cases plus 3 environment-gated
  real-database skips, including the new P2.3 suite: four-screen global queue
  saturation with recovery, executor starvation with queued-cancel slot
  recovery, six rounds of timeout-versus-cancel races settling in exactly one
  terminal state, the full eight-signal drill decision matrix, drill
  isolation/audit/idempotency, metadata-only screen-scoped execution lists,
  queue-status shape and isolation, and three distinct-profile screens under
  mixed concurrent load with single-source failure isolation.
- Capacity measurement smoke suite passed; a real run on the reference
  machine (Windows 11, 16 CPUs, Python 3.12.13) measured medians near
  73–76 ms sequential per screen, 14.1 completed/s three-screen concurrent,
  12 saturation submissions with 6 retryable backpressure rejections and 3/3
  recovery. Recorded as deployment-local reference only, not an SLA.
- P2.3 machine contract passed 46 checks and 8 mutation fixtures under
  PowerShell 7 and Windows PowerShell 5.1.
- Pinned pnpm 9.15.4 TypeScript/Vite build passed with 19 modules.
- Fresh 1280 by 720 headless-Chrome workflow passed: login, per-screen
  executions list and queue status for all three screens, a UI-driven dataset
  query reaching SUCCEEDED (21 ms, 2 rows), drill `tts/timeout` resolving
  等价回退成功 to `browser_text_fallback` and drill `tts/permission_denied`
  ending 终态无回退. Document width was 1265 pixels with no horizontal
  overflow. Console raw count was 2 with both entries recorded verbatim and
  excluded for documented reasons (vite dev favicon 404; the app's own
  pre-login session-restore probe returning 401); effective warning/error
  count is 0. Edge was unavailable on this host; the Chrome fallback was
  used.
- Exact-candidate Compose smoke passed: images built and started, health
  OK, the P2.3 routes respond with 401 before authentication, the in-container
  store initializes to head `005_controlled_querying`, and teardown removed
  containers, network and smoke data.
- Secret scans of the candidate surfaces passed under both PowerShell hosts
  with zero exact and zero unapproved findings.
- Empty preview initialization passed; a copied accepted-P2.2-era database
  opened under the candidate with zero new migrations, head staying
  `005_controlled_querying`.
- Product-code rollback verification passed: the accepted P2.2 worktree ran
  its 67 original tests, exposed 116 routes with no P2.3 route or module, and
  required no data reversal.
- Documentation lifecycle lint passed 425 checks under both PowerShell hosts
  (the Windows PowerShell 5.1 run required an explicit 5.1 Utility-module
  import because the host PSModulePath shadows `Get-FileHash`; recorded in
  evidence). `git diff --check` is clean.

## Independent Review

Reviewer `Faraday` (read-only, did not implement the batch) returned
`PASS_WITH_NONBLOCKING`: zero blocking findings and seven non-blocking
findings. It reran the P2.3 isolation suite (8 passed), the capacity suite
(2 passed), the P2.2 three-screen/backpressure/timeout subset, the full
backend regression (77 passed, 3 skipped), the machine contract in both
hosts (46 checks, 9 mutation cases) and the frontend build, and it executed
21/21 passing negative probes of its own (anonymous/device 401, ghost and
cross-screen 404, idempotency replay/conflict, invalid signal 422,
queue-status non-disclosure, sanitized single audit per drill). Non-blocking
items N1–N3 (stale fingerprint, one contradictory CHANGELOG line, then-open
browser/Docker gates) were closed before candidate binding; N4–N7 are
recorded limitations.

Raw evidence is under `logs/productization/P2.3-20260729-234531`.
