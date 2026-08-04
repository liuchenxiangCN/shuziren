# P3 Development Preview And Recovery Runbook

## Status

- Lifecycle: ACCEPTANCE_EVIDENCE
- State: ACTIVE_CANDIDATE
- Scope: local P3 test-only preview
- Production use: forbidden
- Candidate: `0b37f7c0917441543735c0b4a08d15e27a27f98c`

## Start A Fresh Preview

From the repository root run:

    scripts\initialize-p3-preview.ps1
    scripts\start-p3-local-api.ps1

In a second terminal run:

    Set-Location apps\web
    corepack pnpm install --frozen-lockfile
    corepack pnpm dev

Open http://localhost:18000/manage and select 测试形象. The initializer
refuses overwrite and creates data/control-plane-p3.db, the matching backup
directory and .env.p3-preview. Never commit or share those local files.

The generated fixture has three screens, two immutable test-guide versions
and initial bindings that demonstrate reuse and screen isolation.

## Acceptance Walkthrough

1. Confirm the Renderer registry shows only test_card 1.0.0 with 测试专用=是
   and 生产可用=否.
2. Preview both versions. The appearance is drawn by product code from the
   declarative model; no package content is inserted as HTML or executed.
3. Select a screen currently on version 1 while version 2 is the target.
4. Choose 模拟损坏哈希. Confirm FAILED is visible, the current version and
   binding generation are unchanged, and publication remains unavailable.
5. Choose 预取并校验 and confirm READY, then 原子切换到目标屏. Confirm only
   the selected screen moves to version 2 and its generation increments.
6. Choose 回退上一版本. Confirm the current version returns to version 1 as
   a new generation and history contains both PUBLISH and ROLLBACK.

## Browser And Machine Gates

    scripts\start-p3-browser-gate.ps1 -BrowserPassword <local-only-password>
    scripts\validate-p3-renderer-contract.ps1
    scripts\test-p3-renderer-contract.ps1
    scripts\test-p3-secret-surfaces.ps1 -EvidenceRoot <evidence-directory>

The browser gate prints the exact evidence directory and process IDs. Stop
only those printed processes after recording the workflow. The password and
root key must never enter evidence.

## Backup And Restore

Create a verified encrypted backup through the existing control-plane backup
route after the intended P3 bindings are active. Backup verification must list
migration 006 and nonzero P3 row counts when packages exist. Restore uses the
existing four-eyes high-risk workflow and replaces the whole control-plane
store only after P3 schema, content hashes, ownership and history pass.

The automated P3 test proves: backup with version 1 active, switch to version
2 after backup, restore, then observe version 1 active again with its original
generation.

## Product-Code Rollback

Rollback target:

- accepted P2.3 runtime commit:
  a124f63b8f3b5e499b6c561e78199a26f860edc9
- accepted P2.3 runtime tree:
  8a2f4e36ca0751b6106a174f7dae63be9299ad5b

Exact procedure:

1. Stop the candidate and copy the P3 database plus WAL/SHM sidecars, or retain
   a verified P3 encrypted backup. Do not delete migration 006 or rewrite
   schema_migrations.
2. Switch product code to the accepted P2.3 commit in a separate worktree.
3. Configure that code with a verified database copy captured before P3
   migration. Start it and run its accepted regression/smoke checks.
4. To return to P3, stop P2.3, restore the retained P3 database (or its
   verified encrypted backup) and start the P3 candidate. It revalidates head
   006 and every P3 package/binding before serving.

P3 data created after migration 006 is unavailable while P2.3 serves but is
not destroyed. There is no down-migration.
