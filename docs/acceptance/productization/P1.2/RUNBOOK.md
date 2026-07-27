# P1.2 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Scope: local P1.2 preview only
- Production use: forbidden

## Fresh Preview Initialization

Run once from the repository root:

```powershell
scripts\initialize-p1-2-preview.ps1
```

The initializer prompts without echo for two administrators, one implementation
engineer and one auditor. It creates:

```text
data/control-plane-p1-2.db
.env.p1-2-preview
```

It refuses overwrite, creates inventory only in explicit preview mode and never
prints passwords or the root key. Do not commit, attach or upload the env file.

## Upgrade An Accepted P1.1 Preview Copy

Stop the P1.1 API and any Compose process before choosing the upgrade snapshot.
The script uses SQLite's online backup API so committed WAL state is copied
consistently, but stopping writers freezes the intended rollback point.

The source must contain accepted migration
`001_initial_identity_device_trust` with checksum
`fd7094d87568fddc42c339a4861a6004a136dfb26ed6d1a11549cdb7a5db95ce`.

Defaults:

```powershell
scripts\upgrade-p1-1-to-p1-2-preview.ps1
```

Explicit paths are also supported:

```powershell
scripts\upgrade-p1-1-to-p1-2-preview.ps1 `
  -SourceDatabase data/control-plane.db `
  -TargetDatabase data/control-plane-p1-2.db `
  -SourceEnvironment .env.p1-1-preview `
  -TargetEnvironment .env.p1-2-preview
```

The script never changes the source, refuses an existing target, uses SQLite's
backup API before applying 002 and writes only allowlisted settings to the
target env file. A pre-candidate P1.1 checksum, missing/empty registry,
ownership mismatch or failed backfill is rejected.

## Start Locally

First terminal:

```powershell
scripts\start-p1-2-local-api.ps1
```

Second terminal:

```powershell
Set-Location apps/web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open:

```text
http://localhost:18000/manage
```

The generated env file includes the container database path, so the Docker
alternative selects the same P1.2 preview database:

```powershell
docker compose --env-file .env.p1-2-preview up --build
```

Stop the Docker alternative with:

```powershell
docker compose --env-file .env.p1-2-preview down
```

## Result Walkthrough

1. Sign in as `implementation` and open `多屏清单`.
2. Confirm default Site `site-default`, group `group-main` and three screens.
3. Confirm Screen 1 ID is the accepted P1.1 fixture, while Screens 2 and 3 have
   distinct UUIDv7 IDs.
4. Confirm each screen has a distinct FVS label and DigitalHumanInstance, FVS
   `UNVERIFIED`, independent device trust and runtime `NOT_CONFIGURED_P1_3`.
5. Update only Screen 2's display name and FVS label. Refresh and confirm
   Screens 1 and 3 are unchanged.
6. Create Screen 4. Confirm `INVENTORY_INCOMPLETE`, then create its first
   DigitalHumanInstance and confirm `NOT_CONFIGURED_P1_3`.
7. Replace the group's full membership with the current ETag. A stale retry,
   duplicate/cross-Site member or changed idempotency replay must fail.
8. Sign in as `auditor`. Confirm the inventory is visible and no create/update
   control is present; API mutation attempts return forbidden.
9. Use a Screen 1 device credential to read runtime inventory. Confirm it
   cannot select a sibling and reports `NOT_CONFIGURED_P1_3`.

## Reset A Local Preview

Stop API/web/Compose first. Move the exact database and env file to a separately
named local archive outside the active paths. Never delete or overwrite an
unknown database or environment file. Run the chosen initializer/upgrade again.
