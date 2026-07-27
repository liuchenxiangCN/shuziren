# P1.2 Acceptance Card

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Result: three-screen inventory and isolation
- Base accepted runtime: commit `8c18e5d6b10081eaaf608436440046894d235d46`, tree `9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`
- Base acceptance record: commit `6c3d06c9ca916b5c08c1a1a71c80b06dc80f36b7`
- Candidate: commit `2ddd2116aad19babc9acbfde1110802eb3187c2b`, tree `565dbb3567e2a4ae5b872177d97449120477fe8c`
- Target logical schema / migration: `p1_control_plane_001` / `002_three_screen_inventory`
- Gate summary: PASS
- Independent review: PASS; zero blocking and zero non-blocking findings on the final candidate
- User decision: Pending

This card froze the complete P1.2 result and non-scope before implementation.
The final candidate now implements that frozen result and is ready for explicit
user review. It is not accepted until the user records a decision.

## Frozen Observable Outcome

P1.2 must deliver one independently usable management slice:

1. The `/manage` console adds a `多屏清单` view showing one default Site, at least one ScreenGroup and at least three ScreenInstances.
2. The accepted P1.1 trust-only `fixture_screen_id` becomes the first inventory screen without changing its `screen_id`, device-enrollment history, credential-family history or audit evidence.
3. Every screen shows its own display metadata, group membership, non-secret FVS reference, DigitalHumanInstance, device-trust status and runtime-inventory status.
4. A platform administrator or implementation engineer can create and update groups and screens through `screen.manage`.
5. Every accepted role with `screen.read`, including the auditor, can inspect only inventory inside its authorized deployment, Site or Screen scope.
6. Updating one screen or replacing one group's membership leaves unrelated screen metadata, device trust, DigitalHumanInstance and runtime binding unchanged.
7. A newly created screen can receive one active DigitalHumanInstance and one same-screen RuntimeBinding; a second active instance is rejected.
8. The credential-bound device runtime read resolves the same inventory screen and reports configuration as `NOT_CONFIGURED_P1_3`; it does not claim publication or real FVS connectivity.

## Frozen Preview Fixture

An explicit P1.2 development-preview initialization or P1.1 upgrade produces:

| Object | Frozen preview value |
| --- | --- |
| Site | slug `site-default`, display name `默认站点`, timezone `Asia/Shanghai`, status `ACTIVE` |
| ScreenGroup | slug `group-main`, display name `默认大屏组`, all three initial screens |
| Screen 1 | exact accepted P1.1 `fixture_screen_id`, slug `screen-1`, display name `大屏 1` |
| Screen 2 | server-generated UUIDv7 ID, slug `screen-2`, display name `大屏 2` |
| Screen 3 | server-generated UUIDv7 ID, slug `screen-3`, display name `大屏 3` |
| FVS references | distinct non-secret reference labels; connectivity status always `UNVERIFIED` in P1.2 |
| Digital human | one server-generated `ACTIVE` DigitalHumanInstance per initial screen |
| Runtime binding | one row per screen; release pointers null, generation `0`, acknowledgement fields null, status `NOT_CONFIGURED_P1_3` |
| Device trust | Upgrade: Screen 1 preserves its exact P1.1 history; fresh initialization: all screens start `UNENROLLED`; Screens 2 and 3 never inherit Screen 1 history |

Fixture creation is allowed only in the explicit development-preview initializer.
Production startup must not auto-create Site, group, screen, digital-human or FVS
inventory.

## Frozen Inventory Fields

### Site

P1.2 exposes the default Site read-only:

- `site_id`, `tenant_id`, `deployment_id`
- `slug`, `display_name`, `timezone`, `status`
- `screen_group_count`, `screen_count`
- `resource_revision` and strong ETag

There is no Site create, update or delete operation in P1.2.

### ScreenGroup

P1.2 stores and returns:

- `screen_group_id`, ownership IDs and `site_id`
- `slug`, `display_name`
- exact sorted member `screen_id` values
- `resource_revision`, created/updated timestamps and strong ETag

Group membership is convenience metadata, never an authorization boundary.
One screen belongs to at most one active group. `updateScreenGroup` replaces the
complete sorted membership set atomically. Every member must belong to the same
Site. The successful transaction increments the group revision and every screen
whose membership changed; a stale group ETag changes nothing.

### ScreenInstance

P1.2 stores and returns:

- `screen_id`, ownership IDs and `site_id`
- nullable `screen_group_id`
- `slug`, `display_name`
- nullable non-secret `fvs_binding_ref`
- fixed P1.2 `lifecycle_state=ACTIVE`
- derived `fvs_status=UNVERIFIED`
- derived device-trust and runtime-inventory summaries
- `resource_revision`, created/updated timestamps and strong ETag

`fvs_binding_ref` is an inventory label only. Requests reject URLs containing
userinfo, DSNs, passwords, tokens, cookies, authorization headers and Secret
values. P1.2 never connects to FineReport or FVS.

`updateScreenInstance` may change only `slug`, `display_name` and
`fvs_binding_ref`. Group membership is owned by `updateScreenGroup`.
Retirement, deletion and cross-Site moves are not exposed.

### DigitalHumanInstance And RuntimeBinding

P1.2 DigitalHumanInstance contains only its server-generated ID, ownership IDs,
screen ID, `status=ACTIVE`, resource revision and timestamps. It contains no
Renderer, AvatarPackage, provider or configuration profile.

Every screen has one RuntimeBinding row with its own `resource_revision` and
strong ETag. Before its first DigitalHumanInstance, the binding may have a null
`digital_human_instance_id` and reports
`INVENTORY_INCOMPLETE`. `createDigitalHumanInstance` atomically creates the
single active instance, binds it to the same screen and changes the inventory
status to `NOT_CONFIGURED_P1_3`. A second active instance returns
`DUPLICATE_RESOURCE` with no state change.

Desired/applied release targets, acknowledgement markers and acknowledgement
time remain null, and `binding_generation` remains `0` throughout P1.2.

## Frozen API Slice

All paths remain under `/api/v1/control-plane` unless marked device:

| Operation | Method and path | Permission / behavior |
| --- | --- | --- |
| `listSites` | `GET /sites` | `screen.read`; snapshot pagination |
| `getSite` | `GET /sites/{site_id}` | `screen.read`; strong ETag |
| `listScreenGroups` | `GET /screen-groups` | `screen.read`; snapshot pagination |
| `getScreenGroup` | `GET /screen-groups/{screen_group_id}` | `screen.read`; strong ETag |
| `createScreenGroup` | `POST /sites/{site_id}/screen-groups` | `screen.manage`; required idempotency key |
| `updateScreenGroup` | `PATCH /screen-groups/{screen_group_id}` | `screen.manage`; required `If-Match` |
| `listScreenInstances` | `GET /screen-instances` | `screen.read`; snapshot pagination |
| `getScreenInstance` | `GET /screen-instances/{screen_id}` | `screen.read`; strong ETag |
| `createScreenInstance` | `POST /sites/{site_id}/screen-instances` | `screen.manage`; required idempotency key |
| `updateScreenInstance` | `PATCH /screen-instances/{screen_id}` | `screen.manage`; required `If-Match` |
| `createDigitalHumanInstance` | `POST /screen-instances/{screen_id}/digital-human-instances` | `screen.manage`; required idempotency key |
| `getDigitalHumanInstance` | `GET /digital-human-instances/{digital_human_instance_id}` | `screen.read`; strong ETag |
| `getRuntimeBinding` | `GET /screen-instances/{screen_id}/runtime-binding` | `screen.read`; strong ETag |
| `getDeviceRuntimeBinding` | `GET /api/v1/device/runtime-binding` | credential-derived screen only; inventory plus `NOT_CONFIGURED_P1_3` |

No P1.2 request accepts `tenant_id` or `deployment_id`. A nested request takes
its Site or screen from the path and verifies every referenced object inside the
authenticated ownership lineage.

List operations return only rows visible to the current resource scope and use
opaque, expiring, server-side snapshot cursors. Direct ownership/scope mismatch
returns not found without disclosing the object. Missing operation permission
returns forbidden. Screen-scoped users cannot read Site or ScreenGroup
membership, because that would reveal sibling screens.

Inventory mutations are direct `screen.manage` operations and do not use the
production four-eyes workflow. Exact idempotency replay returns the original
result; reuse with changed input fails. PATCH accepts only the frozen allowlist,
requires a strong ETag and rejects stale preconditions without partial effects.

## Frozen Database And Migration Boundary

- Preserve `001_initial_identity_device_trust` and its accepted checksum byte for byte.
- Add named migration `002_three_screen_inventory`; startup accepts only the exact ordered migration registry and rejects missing, unknown, reordered or checksum-tampered entries.
- Empty initialization applies `001` then `002`; accepted-P1.1 upgrade applies only `002`; repeat initialization is a no-op.
- Add ownership-aware Site, ScreenGroup, ScreenInstance, DigitalHumanInstance, RuntimeBinding and server-side list-snapshot tables.
- Enforce composite tenant/deployment/Site/screen foreign keys, unique slugs inside their parent, at most one group per screen, one RuntimeBinding per screen and at most one active DigitalHumanInstance per screen.
- Backfill the accepted fixture screen with the exact existing ID before adding the other two fixture screens.
- Existing DeviceEnrollment and DeviceCredentialFamily rows must resolve to the backfilled ScreenInstance without rewriting their IDs, family state, credential state, epochs, revisions or timestamps.
- Existing SecurityAuditEvent rows are immutable. The same successful migration transaction appends one sanitized inventory-migration event only after all backfill checks pass; failure rolls back all P1.2 rows and leaves P1.1 data usable.
- Acceptance migration runs only against a copied database and retains a verified pre-migration copy. P1.2 does not claim a product backup/restore feature.

## User Result Scenarios

1. Sign in as an implementation engineer, open `多屏清单` and see the exact default Site, group and three distinct screens.
2. Using the upgraded accepted-P1.1 preview database, confirm Screen 1 retains its device family while Screens 2 and 3 are `UNENROLLED`.
3. Inspect all three screens and confirm distinct IDs, FVS references, DigitalHumanInstances and RuntimeBindings, with FVS `UNVERIFIED` and configuration `NOT_CONFIGURED_P1_3`.
4. Create another screen and its DigitalHumanInstance, then retry both operations with the same and changed idempotency keys.
5. Update only Screen 2's display name and FVS reference; confirm Screen 1 and Screen 3 metadata, device families, instances, bindings and ETags are unchanged.
6. Replace a group's membership with a current ETag, then retry with the stale ETag and a cross-Site screen ID; confirm each failed request has no partial effect.
7. Sign in as an auditor and read authorized inventory, then confirm every create/update route is denied by the API.
8. Use a credential bound to Screen 1 to read device runtime inventory and confirm the request cannot select Screen 2 or Screen 3.

## Required Gates

- Ruff formatting/check, API import and complete backend integration tests.
- Empty initialization, accepted-P1.1 upgrade, repeat migration, migration checksum tamper rejection and pre-migration-copy rollback.
- Three-screen ownership, identity, group, device-family, DigitalHumanInstance, RuntimeBinding and ETag isolation snapshots before and after every mutation.
- Concurrent group membership, duplicate slug, duplicate active DigitalHumanInstance, idempotency mismatch and stale-write negative tests.
- Role and resource-scope API denial tests, including screen-scoped sibling non-disclosure and forbidden tenant/deployment selectors.
- Database foreign-key, unique-index, trigger, immutable-audit and no-delete-cascade tests.
- Frontend type/build plus browser workflow at 1280 by 720 with no horizontal overflow or console errors.
- Secret scans over requests, responses, audit details, SQLite files, frontend bundle, logs, screenshot and evidence.
- Pinned pnpm and Docker Compose API/web build-runtime smoke.
- P1 target-contract validation, repository lifecycle lint, `git diff --check`, evidence hashes and clean candidate state.
- Separate read-only Codex review with critical negative-test reruns and zero blocking findings.
- Rollback proof to accepted P1.1 runtime and its verified pre-migration database copy.

## Frozen Non-Scope

- No ConfigDraft, ConfigRelease, Publication, publication acknowledgement, rollback or recovery implementation; those remain P1.3.
- No real FineReport/FVS connection, template discovery, plugin call, compatibility certification, credential/session binding or permission-inheritance claim.
- No Secret value, FineReport identity binding, QuerySource, database query, Excel expansion, Dora, knowledge, LLM, ASR, TTS, screen action or Renderer/AvatarPackage configuration.
- No DigitalHumanInstance candidate/activation/retirement workflow beyond the first active inventory instance.
- No Site mutation, ScreenInstance retirement/deletion, group deletion, cross-Site move or multi-Site delivery promise.
- No production bootstrap/activation, custodian ceremony, external monotonic anchor, PostgreSQL certification, product backup/restore or high-concurrency SLA.
- No change to accepted POC route meanings or accepted P1.1 identity, approval, audit and device-trust semantics.

## Immediate Failure Conditions

- A screen, group, device family, DigitalHumanInstance or RuntimeBinding crosses tenant, deployment, Site or screen ownership.
- A mutation to one screen changes an unrelated screen, including its ETag or derived status.
- P1.1 screen ID, device/audit history, credential state or migration checksum is rewritten, lost or silently relabeled.
- An auditor or screen-scoped user discovers or mutates an unauthorized sibling.
- A stale ETag, changed-command idempotency replay, duplicate active instance or cross-Site group member succeeds.
- A Secret, DSN, credential, cookie, token or authorization header enters inventory, audit, bundle, database, log or evidence.
- `UNVERIFIED` FVS or `NOT_CONFIGURED_P1_3` runtime state is presented as connected, published or production-ready.

## Rollback Target

Rollback target is accepted P1.1 runtime commit
`8c18e5d6b10081eaaf608436440046894d235d46`, tree
`9bf17c8ac4b2fbf221cbaf1a27c0a3fb098aafbd`, plus the verified exact
pre-`002` database copy. Rollback acceptance must prove P1.1 login, audit,
enrollment, credential rotation/revocation and fresh-family re-enrollment still
work and that no P1.2 route is exposed.
