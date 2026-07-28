# P1.3 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `READY_FOR_USER_ACCEPTANCE`
- Candidate: `0f210cffa5a9b49fd93d36dbb42bd36bb2899f54`
- Scope: local P1.3 preview only
- Production use: forbidden

## Fresh Preview Initialization

Run once from the repository root:

```powershell
scripts\initialize-p1-3-preview.ps1
```

The initializer prompts without echo for two administrators, one implementation
engineer and one auditor. It creates:

```text
data/control-plane-p1-3.db
data/control-plane-p1-3-backups/
.env.p1-3-preview
```

It refuses overwrite, creates identities/inventory only in explicit preview
mode and never prints passwords or root-key material. Do not commit, attach or
upload the env file, databases or backup directory.

## Upgrade An Accepted P1.2 Preview Copy

Stop every API/Compose writer first. Keep the accepted source and its
environment file:

```text
data/control-plane-p1-2-final.db
.env.p1-2-final
```

Run:

```powershell
scripts\upgrade-p1-2-to-p1-3-preview.ps1
```

The script:

1. requires the exact accepted 001/002 registry and clean foreign keys;
2. uses SQLite's online backup API and never changes the source;
3. refuses any existing P1.3 database, env file or backup root;
4. applies checksummed `003_publish_rollback_recovery`;
5. verifies three screens and null-release generation-zero P1.2 bindings; and
6. writes only allowlisted preview settings without printing the key.

Keep a verified pre-003 SQLite backup with the accepted P1.2 runtime before
choosing the new preview as the active development copy.

## Start Locally

First terminal:

```powershell
scripts\start-p1-3-local-api.ps1
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

The Compose alternative uses the same generated environment:

```powershell
docker compose --env-file .env.p1-3-preview up --build
```

Stop it with:

```powershell
docker compose --env-file .env.p1-3-preview down
```

## Result Walkthrough

1. Sign in as `implementation`; open `发布与恢复`.
2. Select Screen 2, create a draft and replace the complete spec with a new
   welcome text and non-secret Mock FVS reference.
3. Validate and preview. Confirm the state is `MOCK_PASSED`, the resolved
   screen/DigitalHumanInstance and fingerprint are visible, and FVS remains
   `UNVERIFIED`.
4. Submit the exact draft. Sign out, sign in as `admin-a`, reauthenticate, load
   the draft ID, approve it and create the immutable NORMAL release.
5. As one administrator, submit a Screen 2 publication request. As the other
   administrator, approve it. Return to the initiator and execute the exact
   request. Confirm only Screen 2 desired target/generation changes.
6. With an active Screen 2 device credential, fetch
   `/api/v1/device/config-releases/current` and acknowledge its exact target,
   generation and hash. Confirm only Screen 2 applied state changes.
7. Publish another Screen 2 release, compare both versions and rollback to the
   first target. Confirm a third immutable ROLLBACK release is created and both
   sources stay unchanged.
8. Create one group release, submit/approve/execute a group publication with
   the displayed group and three RuntimeBinding preconditions. Confirm three
   independent target states.
9. Sign in as `auditor`. Read release/diff/audit evidence and confirm mutation
   attempts are denied.
10. Create and verify an encrypted backup. Change all three desired bindings,
    create a newer live user and active device credential, then create and
    execute an approved restore plan with `RESTORE_VERIFIED_BACKUP`. Confirm
    the backed-up bindings return, newer live security remains authoritative,
    old sessions/replay material do not revive and the pre-restore store is
    retained.

## Backup Handling

Treat the active database, every retained pre-restore database and encrypted
bundle as sensitive local operator material. A valid bundle directory has only
the four files documented in `IMPLEMENTED_DATA.md`. Never copy the root key into
the bundle directory or evidence.

Verification or restore must stop on:

- a changed file/checksum/authenticated header;
- a bundle whose authenticated identity or hashes do not match the requested
  immutable backup record;
- a missing or wrong recovery key;
- an invalid source snapshot during backup creation;
- a migration, foreign-key, audit-chain or release-content mismatch;
- incomplete RuntimeBindings; or
- stale restore-plan metadata/approval/ETag.

A failed pre-cutover attempt leaves the active database and all three live
bindings unchanged. Backup capture and restore cutover serialize supported
control-plane mutations. A command that waited across a restore must satisfy
its preconditions against the restored active store; an invalidated command
fails explicitly and must not be reported as a successful lost write.

## Product-Code Rollback

The accepted code target is:

```text
commit 2ddd2116aad19babc9acbfde1110802eb3187c2b
tree   565dbb3567e2a4ae5b872177d97449120477fe8c
```

Use a reviewed deployment procedure to select that exact code and the verified
pre-003 database copy together. Do not point accepted P1.2 code at a database
that already depends on migration 003. Post-rollback verification must show:

- migration `002_three_screen_inventory` and exactly three screens;
- accepted login, RBAC, audit and device trust tests pass;
- P1.2 inventory/device runtime routes remain; and
- P1.3 draft and backup routes are absent.
