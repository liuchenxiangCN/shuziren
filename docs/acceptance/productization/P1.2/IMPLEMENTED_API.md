# P1.2 Candidate Implemented API

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Scope: factual P1.2 development-preview API; not a production-support claim
- Target source: [../../../product/contracts/CONTROL_PLANE_API.md](../../../product/contracts/CONTROL_PLANE_API.md)

The accepted P1.1 routes keep their meanings. P1.2 adds the inventory operations
below under `/api/v1/control-plane` and enriches the accepted credential-bound
device runtime read.

## Inventory Routes

| Operation | Method and path | Candidate behavior |
| --- | --- | --- |
| `listSites` | `GET /sites` | `screen.read`; opaque five-minute server-side snapshot pagination |
| `getSite` | `GET /sites/{site_id}` | Authorized Site only; strong resource ETag |
| `listScreenGroups` | `GET /screen-groups` | `screen.read`; Site/deployment scope; no result for SCREEN-scoped readers |
| `getScreenGroup` | `GET /screen-groups/{screen_group_id}` | Authorized Site only; complete sorted member set |
| `createScreenGroup` | `POST /sites/{site_id}/screen-groups` | `screen.manage`; required exact idempotency key; creates an empty group |
| `updateScreenGroup` | `PATCH /screen-groups/{screen_group_id}` | Strong `If-Match`; allowlisted metadata and atomic complete membership replacement |
| `listScreenInstances` | `GET /screen-instances` | Only screens visible to the principal's deployment, Site or SCREEN assignment |
| `getScreenInstance` | `GET /screen-instances/{screen_id}` | Strong ETag plus same-screen FVS, device, digital-human and runtime summaries |
| `createScreenInstance` | `POST /sites/{site_id}/screen-instances` | `screen.manage`; UUIDv7 ID; idempotent create; starts `INVENTORY_INCOMPLETE` |
| `updateScreenInstance` | `PATCH /screen-instances/{screen_id}` | Strong `If-Match`; only slug, display name and non-secret FVS reference |
| `createDigitalHumanInstance` | `POST /screen-instances/{screen_id}/digital-human-instances` | One active instance; idempotent first create; duplicate rejection |
| `getDigitalHumanInstance` | `GET /digital-human-instances/{id}` | Same-screen scope and strong ETag |
| `getRuntimeBinding` | `GET /screen-instances/{screen_id}/runtime-binding` | Same-screen scope; generation `0`; no release or acknowledgement fields populated |

Every nested route derives tenant/deployment/Site/screen lineage from the
authenticated session and path. Headers and query parameters cannot select
tenant or deployment. Ownership mismatch returns not found; missing operation
permission returns forbidden.

## Device Runtime Route

`GET /api/v1/device/runtime-binding` still derives the screen exclusively from
the credential family. P1.2 returns that same inventory screen, device-family
metadata, FVS `UNVERIFIED` and runtime `NOT_CONFIGURED_P1_3`. It accepts no
screen selector and does not claim publication or real FVS connectivity.

## Mutation And Concurrency Rules

- Create routes require an 8-to-200-character `Idempotency-Key`.
- Exact replay returns the original result; reuse with a changed canonical
  command returns `IDEMPOTENCY_KEY_REUSED`.
- PATCH routes require one exact strong ETag and reject stale state before any
  effect.
- Group membership replacement validates every member inside one Site before
  changing the group or any screen revision.
- Duplicate screen/group slugs, a second active digital-human instance and a
  screen already owned by another group fail without partial effects.
- Concurrent requests using one group ETag yield one success and one
  `RESOURCE_VERSION_CONFLICT`.

## Scope And Secret Boundaries

- Deployment- and Site-scoped assignments see only their lineage.
- SCREEN-scoped readers can read only their exact ScreenInstance,
  DigitalHumanInstance and RuntimeBinding. They cannot enumerate Site,
  ScreenGroup, sibling inventory or deployment-wide audit/identity/action data.
- Auditors can read authorized inventory but every P1.2 mutation returns
  forbidden.
- FVS inventory values reject URL userinfo, database schemes, JDBC/ODBC/common
  DSN structures, bearer/basic material, passwords, API/access/private keys,
  tokens, cookies, authorization, client secrets and encoded equivalents.
- FVS responses remain `UNVERIFIED`; no candidate route connects to
  FineReport/FVS or reads a Secret.
