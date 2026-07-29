# P2.3 Known Limitations

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE`
- Candidate commit: `PENDING`
- Candidate fingerprint:
  `FE0F87AC1B3F1FD5373681E86BDFA0DE909D6A1E637BD22E2A97DEFD57F26097`
  over 36 files
- User decision: `PENDING`

## Frozen Limits

- P2.3 is a local development-preview resilience certification, not
  production activation or capacity/SLA certification.
- The capacity measurement is a deployment-local reference on the recording
  machine only. It is not an SLA, not a throughput promise for any other
  hardware, operating system or network and not a customer-environment
  certification.
- The resilience drill is a deterministic in-process simulation against the
  applied capability snapshot. It proves the fallback decision contract live;
  it does not call Dora, ASR, TTS, RAGFlow, FVS or any external provider, and
  Mock evidence closes no real-provider risk. The drill evaluates the first
  configured fallback provider only, matching the accepted decision contract.
- Concurrency limits remain the accepted P2.2 constants (global 6,
  per-screen 2, workers 3, retained 256). They are not tunable in this batch.
- Drill records live only in a bounded in-memory store (128 drills). Eviction
  or process restart removes drill detail reads; the sanitized audit event
  persists.
- The queue-status view shows the requesting screen's own live state plus
  static capacity. A live global occupancy view for operators does not exist.
- The preview fixture's "slow" dataset carries the maximum long timeout but
  the Excel engine executes near-instantly; genuine slow-execution isolation
  is proven by the backend suite and the capacity harness, not the static
  fixture.
- The FineReport official plugin remains `Unverified`; P2.4 stays blocked by
  its external gate. External Providers stay unverified and blocked.
- The control-plane store remains SQLite with no cluster, distributed queue
  or external scheduler. Secret rotation, full-loss recovery, external
  monotonic anchors and customer RPO/RTO certification remain out of scope.

User acceptance cannot turn deployment-local measurements or simulated
drills into product certification for real providers or customer
environments.
