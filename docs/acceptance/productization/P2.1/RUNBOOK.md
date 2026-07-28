# P2.1 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `IMPLEMENTATION_PRESENT; FINAL_VERIFICATION_PENDING`
- Candidate commit / tree: `PENDING`
- Scope: local P2.1 preview only
- Production use: forbidden

## Fresh Preview Initialization

Run from the repository root:

```powershell
scripts\initialize-p2-1-preview.ps1
```

The initializer prompts without echo for two administrators, one implementation
engineer and one auditor. It refuses overwrite and creates:

```text
data/control-plane-p2-1.db
data/control-plane-p2-1-backups/
.env.p2-1-preview
```

Do not commit, upload or attach the environment file, database or backup
directory. The initializer never prints passwords or root-key material.

## Upgrade An Accepted P1.3 Preview Copy

Stop every API, Compose and other SQLite writer. Keep the accepted P1.3 source
database and environment file, then run:

```powershell
scripts\upgrade-p1-3-to-p2-1-preview.ps1
```

The script requires the exact accepted 001/002/003 registry and three-screen
binding baseline, copies SQLite through the online backup API and migrates only
the copy to `004_capability_profiles`. It refuses an existing P2.1 database,
environment file or backup root. The P1.3 source remains unchanged; keep it as
the verified pre-004 rollback copy.

## Start Locally

First terminal:

```powershell
scripts\start-p2-1-local-api.ps1
```

Second terminal:

```powershell
Set-Location apps\web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open:

```text
http://localhost:18000/manage
```

The local API listens on `127.0.0.1:18080`; Vite proxies `/api` to it.

## Capability Profile Walkthrough

1. Sign in as `implementation` and open `能力套餐`.
2. Confirm the page shows seven fixed capabilities, three immutable presets,
   five state meanings and the fixed non-secret Provider catalog. Every
   Provider must say that P2.1 external calls are disabled.
3. Select `text_only`, enter a non-secret name/description and copy it to a
   Site-owned profile. Record version 1 and its content/registry hashes.
4. Edit only allowlisted switches, primary/fallback order and timeout, then
   create version 2. Reload the profile and confirm version 1 remains
   immutable and the envelope head points to version 2.
5. Create separate `mock_voice` and `mock_presenter` profiles. Keep Mock
   labelling visible; do not describe either as a real-provider result.
6. Select an unverified Provider such as `finereport_ai_plugin` in a separate
   version. Confirm dependency findings explain the block and
   `activation_eligible=false`. Do not enter any endpoint, token, DSN, SQL or
   credential.

## Draft, Release And Per-Screen Walkthrough

1. Open `发布与恢复`, choose one screen, create and populate a
   `p1_screen_config_v1` draft, then assign an exact profile version.
2. Confirm assignment advances the draft revision while the base spec remains
   exactly `welcome_text` plus `fvs_binding_ref`; prior validation, preview and
   approval evidence must be cleared.
3. Validate and preview an eligible local/Mock profile. Confirm the preview is
   visibly `MOCK_PASSED`, reports `external_calls_made=false`, shows the exact
   per-screen capability hash and selects no Provider for disabled entries.
4. Submit, approve with a different user and create a NORMAL release. Publish
   it through the existing two-person HighRiskAction flow. Desired state moves
   first; applied state must not move before the credential-owned device
   acknowledges the exact generation, target and hash.
5. Repeat with a different profile version for each of the three screens.
   Under `三屏生效能力`, confirm desired/applied profile IDs, seven states,
   DigitalHumanInstance and ReleaseTarget remain distinct.
6. Resolve `GET /api/v1/device/capabilities/current` with each screen's active
   credential and the same non-secret `X-Runtime-Session-ID`. Confirm the
   screen, applied snapshot and returned isolation hash differ per screen. The
   request contains no screen or ownership selector.
7. Publish a later profile version, then forward-roll back to the earlier
   target. Confirm the rollback creates a new release and copies the historical
   capability snapshot/hash without changing either source.
8. Assign the unverified FineReport profile to a fresh draft. Validation must
   remain invalid and release creation must be unavailable; no external call
   or fallback is permitted.

An auditor may read authorized catalog, profile, screen and release evidence
but every mutation must remain denied.

## Fallback And Legacy Checks

- `timeout`, `unavailable` and `unsupported` may select only an activatable,
  equivalent screen-bound fallback.
- `permission_denied`, `invalid_request`, `unauthorized_template` and
  `cancelled` are terminal and must not fall back.
- A disabled capability has a null primary, empty fallback list and zero
  Provider execution.
- An applied legacy P1.3 target returns `NOT_CONFIGURED_P2_1`; it never receives
  a default or global Mock profile.

## Backup And Restore

Use the existing P1.3 two-person backup/restore workflow only with the P2.1
environment and backup root. Create and freshly verify an encrypted bundle
after profiles, assignments and release snapshots exist. Before cutover,
verification must reject any changed spec/hash, head reference, assignment
scope, release envelope or incomplete four-table set.

After staged restore, confirm all historical ProfileVersions, three applied
snapshots and rollback copies return, while live users and active device
security remain authoritative. Protect the retained pre-restore store with the
same sensitivity as the active database.

## Product-Code Rollback

The accepted product-code target is:

```text
commit 0f210cffa5a9b49fd93d36dbb42bd36bb2899f54
tree   04bcbb940fbedb5fbb8957e538f46a4422e15db2
```

Select that exact accepted P1.3 runtime together with the verified WAL-safe
pre-004 SQLite copy. Never point P1.3 code at a database that depends on
migration 004. Post-rollback verification must run the original 22 P1.3 tests,
show migration 003 and three bindings, and prove every P2.1 route is absent.
Final rollback evidence remains `PENDING`.
