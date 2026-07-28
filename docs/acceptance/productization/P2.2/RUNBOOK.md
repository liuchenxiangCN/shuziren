# P2.2 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `CANDIDATE_PREPARATION`
- Candidate commit/tree: pending immutable candidate record
- Scope: local P2.2 preview only
- Production use: forbidden

## Start A Fresh Preview

From the repository root:

```powershell
scripts\initialize-p2-2-preview.ps1
scripts\start-p2-2-local-api.ps1
```

In a second terminal:

```powershell
Set-Location apps\web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:18000/manage`. The initializer prompts without echo,
refuses overwrite and creates `data/control-plane-p2-2.db`, its backup
directory and `.env.p2-2-preview`. Never commit or share those files.

## Controlled Query Walkthrough

1. Sign in as `implementation` and open `受控问数`.
2. Register a formula-free `.xlsx` or one dedicated read-only database
   account. Confirm ordinary reads show only configured/fingerprint state.
3. Run the source test. Treat `AVAILABLE` as exact deployment-local evidence;
   keep product certification `UNVERIFIED`.
4. Freeze an immutable dataset with typed parameters, ordered output fields,
   row/timeout bounds and an exact engine definition.
5. In `发布中心`, create a draft, assign an eligible P2.1 profile whose
   querying primary is only `controlled_query`, and assign exact dataset
   versions.
6. Validate, preview, obtain different-user approval, release, publish and
   acknowledge using the accepted P1.3 workflow.
7. Return to `受控问数`, load the applied screen catalog and run only a
   published dataset with typed parameter JSON. Poll or cancel by its opaque
   execution ID.

Never paste customer credentials into evidence, send SQL from a runtime
caller, or interpret desired/unacknowledged state as applied.

## Verification

```powershell
Set-Location apps\api
uv run ruff format --check app tests
uv run ruff check app tests
uv run pytest -q
Set-Location ..\..
scripts\validate-p2-2-controlled-query-contract.ps1
scripts\test-p2-2-controlled-query-contract.ps1
scripts\lint-doc-lifecycle.ps1
```

The real-database tests are opt-in through `P22_POSTGRES_*`, `P22_MYSQL_*` and
`P22_ORACLE_*` environment variables and must use isolated read-only accounts.

## Rollback

Product rollback target:

```text
commit 8f364b93b574c058cd8cd617f925107985318098
tree   7c277e32b6419bd3720591c454e8282d94f081ec
```

Use it only with a verified WAL-safe pre-`005` database copy at migration
`004_capability_profiles`. Never point accepted P2.1 code at a store that
depends on migration 005. Post-rollback checks must pass accepted P2.1 tests
and show no P2.2 route/table.
