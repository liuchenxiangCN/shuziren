# P2.1 Capability Profile Target Contract

## Document Status

- Lifecycle: `TARGET_NOT_IMPLEMENTED`
- Scope: incremental P2.1 capability-profile, provider-catalog and per-screen resolution contract
- Contract version: `p2.1-capability-profile-v1`
- Last reviewed: 2026-07-28

This contract freezes the P2.1 target before runtime implementation. It does
not claim that any provider, profile, API or migration described here is
implemented or accepted. Implemented evidence belongs only in the P2.1
acceptance package.

## Result Boundary

P2.1 adds a versioned capability-selection layer to the accepted P1.3
development-preview runtime:

- a Site-scoped reusable `CapabilityProfile` envelope;
- immutable `CapabilityProfileVersion` content;
- an immutable draft-revision assignment and ReleaseTarget capability
  snapshot;
- a server-owned provider catalog with explicit qualification states;
- per-screen resolution derived from a DeviceCredential and the applied
  ReleaseTarget;
- dependency and fallback validation visible in the management console.

P2.1 does not add real customer Provider connections, Secret writes,
QuerySource execution, an official FineReport plugin adapter or production
compatibility certification.

## Closed Capability Set

Every `p2_capability_profile_v1` spec contains exactly these seven keys:

1. `dora`
2. `knowledge`
3. `direct_llm`
4. `asr`
5. `tts`
6. `querying`
7. `fvs_control`

Every capability contains exactly:

```json
{
  "enabled": true,
  "primary_provider_id": "mock_tts",
  "fallback_provider_ids": ["browser_text_fallback"],
  "timeout_ms": 5000
}
```

Rules:

- `enabled=false` requires a null primary, an empty fallback list and a bounded
  timeout retained only for schema uniformity.
- `enabled=true` requires one catalogued primary Provider for the same
  capability.
- Fallback IDs are ordered, unique, different from the primary and registered
  for the same capability.
- `timeout_ms` is an integer from 100 through 120000.
- The spec accepts no arbitrary Provider payload, URL, connection string,
  Secret reference, Prompt, SQL, executable code or vendor response.
- Capability and Provider states are server-derived. Clients cannot submit an
  effective state, health result, certification result or fallback decision.

## Provider Catalog

The provider catalog is immutable for one registry version and contains only
non-secret descriptors. Contract registry version
`p2_provider_registry_001` contains:

| Capability | Provider ID | Declared state | Boundary |
| --- | --- | --- | --- |
| Dora | `local_rules` | `available` | deterministic local fixed capability |
| Dora | `mock_dora` | `mock` | development preview and failure drill only |
| Dora | `dora_gateway` | `unverified` | no real connection or certification in P2.1 |
| Knowledge | `local_extractive` | `available` | source-bound extractive response only |
| Knowledge | `mock_knowledge` | `mock` | development preview only |
| Knowledge | `dora_ragflow` | `unverified` | no real connection or certification in P2.1 |
| Knowledge | `ragflow_gateway` | `unverified` | no real connection or certification in P2.1 |
| Direct LLM | `fixed_template` | `available` | no model execution |
| Direct LLM | `mock_llm` | `mock` | development preview only |
| Direct LLM | `direct_llm_gateway` | `unverified` | no real connection or certification in P2.1 |
| ASR | `mock_asr` | `mock` | development preview only |
| ASR | `vendor_asr` | `unverified` | no real connection or certification in P2.1 |
| TTS | `mock_tts` | `mock` | development preview only |
| TTS | `browser_text_fallback` | `degraded` | text and subtitle fallback; not full TTS |
| TTS | `vendor_tts` | `unverified` | no real connection or certification in P2.1 |
| Querying | `mock_query` | `mock` | development preview only; no data query |
| Querying | `finereport_ai_plugin` | `unverified` | P2.4 gate; publication blocked |
| Querying | `controlled_query` | `unverified` | P2.2 gate; no QuerySource execution |
| FVS control | `mock_fvs` | `mock` | development preview only |
| FVS control | `fvs_page_number` | `unverified` | no real FVS call or certification in P2.1 |
| FVS control | `fvs_post_message` | `unverified` | no real FVS call or certification in P2.1 |

The catalog exposes adapter/certification metadata, cancellation support,
streaming/session declarations and a fixed permission-scope class. It never
contains a key, token, password, cookie, DSN, Authorization header, customer
endpoint or licensed artifact.

## State Semantics

The five user-visible states are distinct:

| State | Meaning |
| --- | --- |
| `disabled` | Capability is explicitly off; no Provider is selected or invoked |
| `mock` | Only a built-in Mock flow is selected; evidence is never real-provider evidence |
| `unverified` | Provider lacks the required external evidence; the profile version is inspectable but cannot be assigned to a releasable draft |
| `available` | A bounded local Provider contract is usable inside the P2.1 preview boundary |
| `degraded` | Only a documented reduced behavior remains, such as text/subtitle output instead of TTS |

`inherit` is not a P2.1 profile value. Profile assignment is exact. A legacy
P1.3 ReleaseTarget without a capability snapshot resolves to
`NOT_CONFIGURED_P2_1`; it never falls back to a global Mock switch or Settings
singleton.

## Dependency And Fallback Rules

- ASR disabled preserves text input. ASR use never bypasses explicit browser
  microphone permission.
- TTS disabled or degraded preserves text and subtitles.
- Knowledge disabled does not route a knowledge request.
- Querying disabled returns an explicit not-enabled outcome and executes no
  query.
- FVS control disabled permits answers but no screen action.
- An enabled unverified primary or fallback blocks draft validation and release
  creation.
- Fallback is permitted only for `timeout`, `unavailable` or `unsupported`,
  and only when the fallback has the same server-declared screen-bound
  permission scope.
- `permission_denied`, `invalid_request`, `unauthorized_template` and
  `cancelled` are terminal and never fall back.
- FineReport plugin permission denial never falls back to a database, Excel,
  Dora or Mock source.

The P2.1 runtime does not execute real Providers. Mock/local diagnostics may
exercise these decisions, timeouts, cancellation and backpressure without
network access or customer data.

## Ownership And Versioning

`CapabilityProfile` is owned by exactly one Tenant, Deployment and Site. Its
mutable envelope contains only name, description, source preset, head version
and a strong resource revision.

`CapabilityProfileVersion` is immutable and contains:

- opaque profile and version IDs;
- monotonically increasing version number;
- `p2_capability_profile_v1`;
- canonical spec and SHA-256;
- provider registry version and SHA-256;
- server-derived state summary, dependency findings and activation eligibility;
- creator and timestamp.

Updating a profile creates a new immutable version and moves only the mutable
head pointer with a strong `If-Match`. Published releases continue to reference
their exact historical version.

## P1.3 Release Integration

P2.1 preserves `p1_screen_config_v1` and its exact two base fields. It does not
silently add a third field to the accepted schema.

Instead, migration `004_capability_profiles` adds:

- `capability_profiles`;
- `capability_profile_versions`;
- immutable `config_draft_capability_assignments` keyed by draft and draft
  revision;
- immutable `release_target_capability_snapshots` keyed by ReleaseTarget.

A P2.1 draft must first contain a valid P1.3 base spec. Assigning or changing a
profile creates the next draft revision, copies the unchanged base spec,
records the exact profile version/hash and invalidates prior validation,
preview and approval evidence. Later base-spec edits or draft revision copy
the exact assignment forward.

ResolutionFingerprint includes the profile/version IDs, profile hash, registry
version/hash and per-screen capability envelope hash. A NORMAL ConfigRelease
copies the resolved snapshot atomically. A ROLLBACK ConfigRelease copies the
historical base ReleaseTarget and its capability snapshot byte-for-byte into a
new immutable target.

Publication still changes only desired state. The device applies the exact
target only after credential-bound acknowledgement. Runtime capability
resolution uses only the applied ReleaseTarget.

## API Slice

All control-plane routes use the accepted browser session, Origin, CSRF, RBAC,
scope, ETag and idempotency boundaries:

- `GET /api/v1/control-plane/capability-providers`
- `GET /api/v1/control-plane/capability-profile-presets`
- `GET /api/v1/control-plane/capability-profiles`
- `POST /api/v1/control-plane/capability-profiles`
- `GET /api/v1/control-plane/capability-profiles/{profile_id}`
- `POST /api/v1/control-plane/capability-profiles/{profile_id}/versions`
- `PUT /api/v1/control-plane/config-drafts/{draft_id}/capability-profile`
- `GET /api/v1/control-plane/screen-instances/{screen_id}/effective-capabilities`

The device route is:

- `GET /api/v1/device/capabilities/current`

The device route accepts no tenant, deployment, Site or screen selector. Scope
comes only from the active DeviceCredential. A same-named runtime session on
two screens remains separated by server-owned screen, DigitalHumanInstance,
ReleaseTarget and profile-version context.

Profile reads require `config.read`. Profile creation/versioning and draft
assignment require `config.edit_technical`. Business operators and auditors
cannot mutate technical capability selection.

## Presets

The server exposes immutable presets:

- `text_only`: local rules; all other capabilities disabled.
- `mock_voice`: Mock Dora, ASR and TTS; querying, knowledge, direct LLM and FVS
  control disabled.
- `mock_presenter`: Mock Dora, ASR, TTS and FVS control; the remaining
  capabilities disabled.

Copying a preset creates a Site-owned custom profile and immutable version.
Presets are templates, not mutable shared runtime records.

## Immediate Failure Conditions

- A profile, assignment, release snapshot or resolution crosses Tenant,
  Deployment, Site, screen or DigitalHumanInstance scope.
- A legacy target silently receives global Provider or Mock configuration.
- A mutable profile head, unverified Provider or changed registry meaning
  alters an already published snapshot.
- Disabled capability invokes a Provider.
- Mock or unverified state is presented as available or real.
- Permission denial, invalid input, unauthorized template or cancellation
  triggers fallback.
- A Secret, DSN, token, endpoint credential, arbitrary Provider payload,
  executable code or free SQL enters profile content or a read response.
- One screen's resolution, session marker, Provider state, error or fallback
  changes a sibling screen.

## Deferred Batches

- P2.2 owns Excel/MySQL/Oracle/PostgreSQL QuerySources and controlled datasets.
- P2.3 owns integrated capability/query resilience certification and measured
  capacity guidance.
- P2.4 owns the gated FineReport official-plugin adapter and exact compatibility
  certification.
- P3 owns Renderer and AvatarPackage contracts.
- Production activation, PostgreSQL control-plane storage, full-loss recovery
  and customer RPO/RTO remain outside P2.1.
