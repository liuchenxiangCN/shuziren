# P2.1 Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Candidate commit: `8f364b93b574c058cd8cd617f925107985318098`
- Candidate tree: `7c277e32b6419bd3720591c454e8282d94f081ec`
- API version: `v1`
- Profile schema: `p2_capability_profile_v1`
- Provider registry: `p2_provider_registry_001`
- Acceptance: `通过` on 2026-07-28

This document describes the exact accepted P2.1 API result that passed
automated gates and independent review. The frozen result card and user
decision remain [ACCEPTANCE_CARD.md](ACCEPTANCE_CARD.md) and
[USER_DECISION.md](USER_DECISION.md).

## Added Routes

| Operation | Method and path | Required authority | Implemented behavior |
| --- | --- | --- | --- |
| Provider catalog | `GET /api/v1/control-plane/capability-providers` | browser session plus `config.read` | Returns the fixed non-secret registry, five state definitions and fallback policy |
| Product presets | `GET /api/v1/control-plane/capability-profile-presets` | browser session plus `config.read` | Returns immutable `text_only`, `mock_voice` and `mock_presenter` specs |
| List profiles | `GET /api/v1/control-plane/capability-profiles` | browser session plus `config.read` | Lists only profiles in authorized Tenant, Deployment and Site scope |
| Create profile | `POST /api/v1/control-plane/capability-profiles` | `config.edit_technical` | Copies one preset into a Site-owned profile and immutable version 1 |
| Read profile | `GET /api/v1/control-plane/capability-profiles/{profile_id}` | `config.read` | Returns the envelope, strong ETag, head and immutable version history |
| Create version | `POST /api/v1/control-plane/capability-profiles/{profile_id}/versions` | `config.edit_technical` | Validates the closed spec, appends an immutable version and advances the head |
| Assign draft | `PUT /api/v1/control-plane/config-drafts/{draft_id}/capability-profile` | `config.edit_technical` | Assigns an exact version through a new draft revision and clears stale evidence |
| Screen resolution | `GET /api/v1/control-plane/screen-instances/{screen_id}/effective-capabilities` | `config.read` | Returns authorized desired, applied and effective capability snapshots |
| Device resolution | `GET /api/v1/device/capabilities/current` | active device credential | Resolves only the credential-owned screen's applied snapshot |

Profile creation requires `Idempotency-Key`. Version creation and draft
assignment additionally require the current strong `If-Match`. Browser
mutations retain the existing exact-Origin, server-side session and bound-CSRF
controls. Replaying the same idempotency key with a changed command is rejected.
Unauthorized scope is returned as non-disclosing not-found behavior.

## Closed Profile Input

Every profile version accepts exactly:

- `dora`, `knowledge`, `direct_llm`, `asr`, `tts`, `querying` and
  `fvs_control`;
- `enabled`, `primary_provider_id`, ordered `fallback_provider_ids` and
  `timeout_ms` for each capability; and
- a timeout from 100 through 120000 milliseconds.

Disabled capability input must have a null primary and no fallback. Enabled
input must select a same-capability catalog entry. Primary/fallback duplication,
duplicate fallback entries, cross-capability Provider IDs, permission-scope
mismatch and unknown fields fail closed. Profile names, descriptions, specs
and runtime session labels reject Secret-, credential- and DSN-like material.

The server derives the content hash, registry binding, five-state summary,
diagnostics, dependency findings and `activation_eligible`; clients cannot
submit those results. An enabled `unverified` primary or fallback remains
inspectable but makes the version ineligible for release validation.

Unknown Provider identifiers and rejected model fields are returned only
through generic, bounded error categories. The API does not reflect the
submitted identifier, attacker-selected validation locator, raw input, parser
context or request target. Denial audit records use canonical route families
instead of untrusted path text. Profile names and descriptions are revalidated
when a backup snapshot is created or verified.

## Existing Flow Integration

The accepted P1.3 endpoints keep their route meanings and two-field
`p1_screen_config_v1` base spec. P2.1 adds sidecar fields to their responses:

- draft reads include the exact immutable `capability_profile` assignment;
- validation binds the assignment and per-screen envelope hashes into the
  ResolutionFingerprint;
- preview evidence reports local/Mock diagnostics, disabled-zero-provider
  behavior, fixed fallback decisions and `external_calls_made=false`;
- NORMAL ReleaseTargets include an immutable `capability_snapshot`;
- forward rollback copies the historical snapshot and envelope hash exactly;
- desired state changes at publication, while effective capability resolution
  changes only after same-screen device acknowledgement updates applied state.

An applied P1.3 ReleaseTarget without a P2.1 snapshot returns
`NOT_CONFIGURED_P2_1`. It never inherits a global profile or Mock Provider.

Restore remains phase-aware for request-bound idempotency. A result can be
reused only when its referenced domain state remains valid in the restored
phase. Consumed publish or rollback HighRiskActions whose effects are absent
after restore become failed historical evidence instead of replaying a phantom
success.

The optional `X-Runtime-Session-ID` header is a non-authoritative correlation
label. The device response returns a SHA-256 isolation key bound to Tenant,
Deployment, credential-derived screen, DigitalHumanInstance, ReleaseTarget,
ProfileVersion and that label. The label cannot choose ownership and no
cross-request provider state is stored under it.

## Provider And Fallback Boundary

All 21 catalog entries expose `external_calls_enabled=false`. P2.1 implements
only deterministic local/Mock selection and diagnostic evidence. Fallback is
eligible only for `timeout`, `unavailable` or `unsupported`, with equivalent
screen-bound permission scope and an activatable fallback state.
`permission_denied`, `invalid_request`, `unauthorized_template` and
`cancelled` are terminal.

The local diagnostic executor has bounded timeout, cancellation and
backpressure behavior. Queue saturation is an explicit isolated result; it
does not wait without a bound or spill work into another screen. Cancellation
does not trigger fallback. These checks prove only the executable local/Mock
contract, not a real-provider scheduler or vendor behavior.

No route executes FineReport, FVS, an official plugin, QuerySource, SQL, Dora,
RAGFlow, LLM, ASR, TTS or another external Provider. Real-provider support and
compatibility remain unverified and outside this implemented slice.
