# ADR-0029: P2.1 Versioned Capability Profiles And Release Sidecars

## Status

Proposed

This decision becomes Accepted only after explicit P2.1 user acceptance.
Implementation and automated evidence alone do not accept it.

## Date

2026-07-28

## Context

The accepted P1.3 runtime freezes `p1_screen_config_v1` as exactly
`welcome_text` plus `fvs_binding_ref`. Its draft, fingerprint, approval,
ConfigRelease, ReleaseTarget, publication, device acknowledgement, rollback and
recovery graph is already proven and accepted.

P2.1 must add per-screen Dora, knowledge, direct LLM, ASR, TTS, querying and
FVS-control selection. It must also preserve five distinct states, block
unverified activation and prevent global Provider/session state from leaking
between screens.

Adding a third field silently to `p1_screen_config_v1` would falsify accepted
evidence. Rebuilding the complete P1.3 relational graph only to change a schema
CHECK would introduce unnecessary migration and rollback risk. Reusing the
POC's module-global Provider objects would not provide a trusted per-screen
runtime context.

## Decision

1. `p1_screen_config_v1` remains unchanged and continues to own only its
   accepted two base fields.
2. P2.1 introduces `p2_capability_profile_v1` with a closed seven-capability
   schema and server-owned provider registry `p2_provider_registry_001`.
3. `CapabilityProfile` is a Site-owned mutable envelope. Every content change
   creates an immutable `CapabilityProfileVersion`; published releases
   reference only an exact version and hash.
4. Migration `004_capability_profiles` is additive. It adds profile/version
   tables, immutable draft-revision assignments and immutable ReleaseTarget
   capability snapshots. It does not rebuild an accepted P1.3 table.
5. Profile assignment shares the existing draft revision axis. Assignment,
   base-spec edit or legal draft revision creates a new revision and carries
   the exact assignment forward while invalidating stale validation, preview
   and approval evidence.
6. ResolutionFingerprint binds the exact profile version, content hash,
   provider registry version/hash and per-screen capability envelope hash.
7. NORMAL release creation copies the resolved capability snapshot atomically.
   ROLLBACK copies the historical snapshot byte-for-byte into a new immutable
   ReleaseTarget.
8. Publication and device acknowledgement retain the accepted desired/applied
   split. Device capability resolution reads only the applied target and derives
   screen scope from the active DeviceCredential.
9. A legacy P1.3 target without a capability sidecar returns
   `NOT_CONFIGURED_P2_1`; it never inherits module-global Settings or Mock
   switches.
10. P2.1 implements only deterministic local/Mock diagnostic behavior.
    Unverified real Providers may be described but cannot pass release
    validation or make an external request.
11. Fallback is a closed server decision: only timeout, unavailable or
    unsupported may use an equivalent screen-bound fallback. Permission denial,
    invalid request, unauthorized template and cancellation are terminal.

## Consequences

### Positive

- Accepted P1.3 base-schema and release semantics remain byte-for-byte
  distinguishable from the new capability layer.
- Existing releases remain readable and fail closed instead of receiving new
  implicit behavior.
- Profile versions and provider registry meaning are immutable inputs to a
  release, so moving a profile head cannot mutate a deployed screen.
- The additive migration has a direct WAL-safe pre-`004` rollback point.
- Device-scoped resolution can prove three-screen isolation without claiming
  the legacy POC chat/ASR/TTS/FVS routes are multi-screen product runtime.

### Trade-Offs

- A complete ReleaseTarget spans a base row and one immutable capability
  sidecar, so backup verification and evidence must validate both hashes and
  their reference.
- Draft base-spec edits must explicitly copy the current sidecar assignment to
  the next revision.
- Legacy releases require an explicit not-configured state until a P2.1 release
  is published and acknowledged.
- Real Provider execution, health transitions and integrated resilience remain
  later gated results.

## Follow-Up

- P2.2 adds controlled QuerySources without weakening the P2.1 fallback and
  permission-equivalence rules.
- P2.3 performs integrated capability/query resilience and measured-capacity
  certification.
- P2.4 implements the FineReport official-plugin adapter only after its
  external entry gate passes.
