# P2.3 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- State: `ACCEPTED`
- Scope: local P2.3 preview only
- Production use: forbidden

## Start A Fresh Preview

From the repository root:

```powershell
scripts\initialize-p2-3-preview.ps1
scripts\start-p2-3-local-api.ps1
```

In a second terminal:

```powershell
Set-Location apps\web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:18000/manage`. The initializer refuses overwrite and
creates `data/control-plane-p2-3.db`, its backup directory and
`.env.p2-3-preview`. Never commit or share those files.

The fixture contains one Site with three published and acknowledged screens
on distinct capability profiles (`text_only`, `mock_voice`, `mock_presenter`;
the last carries the permission-equivalent `tts` fallback
`mock_tts` → `browser_text_fallback`) and one generated non-customer Excel
QuerySource with a normal dataset and a long-timeout dataset.

## Resilience Walkthrough

1. Sign in and open `受控问数`. Select each screen in turn: the executions
   list and the queue-status strip （本屏在途 / 全局在途上限 / 执行线程 /
   背压拒绝） show only that screen's state.
2. Run the normal dataset on all three screens; each list shows only its own
   executions with request IDs, latency, rows and terminal state.
3. Cancel a non-terminal execution from the list; it ends `CANCELLED`, its
   slot recovers and sibling screens are unaffected.
4. On the `mock_presenter` screen run 弹性演练 with `tts` + `timeout`: the
   outcome is 等价回退成功 resolving to `browser_text_fallback`. Repeat with
   `permission_denied`: the outcome is 终态无回退. Every run is audited.
5. Saturate the queue (repeat starts beyond the per-screen/global bounds):
   rejections arrive as retryable backpressure, the 背压拒绝 counter grows,
   and the queue recovers after drain.

## Capacity Measurement

```powershell
Set-Location apps\api
uv run python -m app.control_plane.capacity_p2_3 --output-dir <evidence-dir>
```

The harness builds an isolated in-process fixture (it never touches `data/`),
measures the sequential baseline, three-screen concurrent rounds and
saturation/recovery, and writes `capacity-measurement.json` plus
`capacity-measurement.md`. Numbers are deployment-local reference values for
the recording machine only — never quote them as an SLA.

## Browser Gate

```powershell
scripts\start-p2-3-browser-gate.ps1 -BrowserPassword <local-only-password>
```

The gate builds a fresh fixture under `logs/productization/P2.3-<stamp>/`,
serves the API on 18380 and the web on 18300 and prints
`BROWSER_GATE_READY`. Stop the printed PIDs afterwards.

## Contract, Secret And Rollback Gates

```powershell
scripts\validate-p2-3-resilience-contract.ps1
scripts\test-p2-3-resilience-contract.ps1
scripts\test-p2-3-secret-surfaces.ps1 -EvidenceRoot <evidence-dir>
```

The validator and its self-test must pass under both `pwsh` and Windows
PowerShell 5.1. Product-code rollback restores accepted P2.2 commit
`a75d3327fdc1ab4b83b0bba501d387af150353c4`; because P2.3 adds no migration,
no data reversal is needed and the P2.3 routes disappear with the code.
