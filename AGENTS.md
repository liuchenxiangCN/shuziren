# AGENTS.md

## Purpose And Authority

This file contains stable repository instructions for Codex. It must not declare the current phase, next task, implementation status or customer-specific objective. Code comments and most product, POC and customer documents are Chinese; the agent-facing governance documents are English. Keep each file's existing language when editing.

`docs/CODEX_CONTEXT.md` provides the small current snapshot. The active result batch and its acceptance state come only from `docs/NEXT_ACTIONS.md`. Product truth, implemented POC truth and historical evidence remain separate according to `docs/DOCUMENT_GOVERNANCE.md`.

## Project Overview

The goal is a privately deployed, single-site, multi-screen conversational digital-human platform for customers that already own FineReport and build large screens with FVS. Each screen gets independent digital-human configuration, capability orchestration, controlled read-only data querying, whitelisted screen actions, versioned publishing, monitoring, audit, backup and recovery.

The repository holds a runnable single-customer, single-instance POC baseline plus a control plane being productized in accepted result batches. Target designs under `docs/product/contracts/` are `TARGET_NOT_IMPLEMENTED`; never describe them as built.

## Repository Layout

- `apps/api/` — FastAPI backend (Python 3.12, `uv`): `app/main.py` POC HTTP/SSE routes, `app/services/` provider adapters (Dora, ASR, TTS, RAGFlow knowledge, Excel ask-metrics, screen actions, wake words), `app/control_plane/` versioned control-plane sidecars, `tests/` pytest suite.
- `apps/web/` — Vue 3 + strict TypeScript + Vite frontend (`pnpm`, Nginx in Docker); `src/main.ts` mounts `App.vue` (digital-human UI) or `ControlPlaneApp.vue` under `/manage`.
- `config/` — YAML/JSON runtime config (screen-action whitelist, wake words, demo cases, ask-metrics) with `customers/<customer-id>/` overlays. `docs/` — governed documentation routed by `docs/00_INDEX.md`. `scripts/` — PowerShell gate, preview, smoke and doc-lint scripts. `data/`, `logs/`, `outputs/` — gitignored local state and evidence.

## Technology Stack

- Backend: FastAPI + Uvicorn, Pydantic Settings, SQLAlchemy + SQLite (control plane and session logs), `sqlglot` read-only SQL validation, drivers `psycopg` / `pymysql` / `oracledb`, `argon2-cffi` + `cryptography`; locked in `apps/api/uv.lock`.
- Frontend: Vue 3, Vite 6, `pnpm` 9.15.4 via Corepack, Canvas 2D + Web Audio; no JS unit-test framework — verification is `vue-tsc` plus PowerShell browser gates.
- Runtime: Windows 10/11 + Docker Desktop (WSL2); `docker-compose.yml` builds `api` (port 18080) and `web` (port 18000); external providers (Dora, RAGFlow, Aliyun ASR/TTS, FVS) sit behind `ENABLE_MOCK_*` switches.

## Build, Run And Test

- Backend, from `apps/api/`: `uv run ruff format --check app tests`, `uv run ruff check app tests`, `uv run pytest -q`, `uv run uvicorn app.main:app --host 127.0.0.1 --port 18080`.
- Frontend, from `apps/web/`: `corepack pnpm install --frozen-lockfile`, then `pnpm dev` (port 18000) or `pnpm build` (runs `vue-tsc --noEmit` first).
- POC loop from the repo root (requires Docker): `scripts\check-poc.ps1`, `scripts\start-poc.ps1 -Build`, `scripts\check-poc.ps1 -RequireServices -RunSmoke`, `scripts\stop-poc.ps1`.
- Control-plane previews use the `scripts\initialize-*-preview.ps1` and `scripts\start-*-local-api.ps1` pairs; browser gates use `scripts\start-*-browser-gate.ps1`; secret scans use `scripts\test-*-secret-surfaces.ps1`. Real-database adapter tests are opt-in via `P22_POSTGRES_*`, `P22_MYSQL_*` and `P22_ORACLE_*` environment variables and skip otherwise.

## Code Style

- Python: Ruff, `line-length = 110`, target `py312`; typed code with strict Pydantic request models; provider differences stay behind adapters in `app/services/`; secrets enter only through environment-backed settings.
- TypeScript: strict-mode Vue SFCs; the frontend never holds API keys — every provider call goes through the backend gateway.
- PowerShell: `$ErrorActionPreference = "Stop"`; scripts keep evidence inside the repository and never print secrets. Commit messages use conventional prefixes scoped to the result batch (`feat(p2.2): ...`, `docs(p2.2): ...`).
- Match the surrounding file's conventions; keep changes scoped to the active result batch.

## Required Routing

Before starting scoped work, read:

1. `docs/00_INDEX.md` — document router and lifecycle map
2. `docs/CODEX_CONTEXT.md` — small current product and execution snapshot
3. `docs/NEXT_ACTIONS.md` — the only active result batch
4. `docs/13_RISKS_AND_TODO.md` — active risks and blockers
5. `docs/RESULT_ACCEPTANCE_STANDARD.md` — evidence and decision rules

Use only the task declared by `docs/NEXT_ACTIONS.md`. A queued phase, archived prompt, roadmap item or target design does not authorize implementation.

## Scope-Based Reading

Read additional material only when the task needs it:

| Task Scope | Additional Source |
| --- | --- |
| Product behavior, domain model, scope or acceptance | `docs/17_STANDARD_PRODUCT_DESIGN.md` |
| Phase composition or roadmap change | `docs/05_DEVELOPMENT_PLAN.md` |
| Implemented API or shared data change | `docs/06_API_CONTRACT.md` and `docs/07_DATA_CONTRACT.md` |
| Target product contract design | the applicable file under `docs/product/contracts/` |
| External system | only the relevant file under `docs/integrations/` |
| Customer delivery | `docs/customers/README.md` and only the target `docs/customers/<customer-id>/` |
| Archived POC handoff | `docs/12_CUSTOMER_HANDOFF.md` and the specifically referenced archive |
| Recent factual history | the relevant entry in `docs/DEV_LOG.md` |

Do not load a whole integration, customer or archive directory when one routed document is sufficient.

## Result-Driven Execution

- Deliver one independently usable vertical result batch at a time.
- Freeze its result card and non-scope before implementation.
- The user reviews observable behavior and business outcomes, not source code.
- Codex owns implementation quality, automated gates, negative tests, independent review, evidence and rollback preparation.
- Automated success alone is insufficient; the result also needs independent review and an explicit user decision.
- User silence is never acceptance.
- Do not advance a queued batch until the active batch is explicitly accepted.
- Keep the latest accepted version recoverable.

## State And Evidence Rules

- Never describe `TARGET_NOT_IMPLEMENTED` content as implemented.
- `AS_BUILT_POC` documents describe only the existing POC baseline.
- `Mock Passed` proves only the product flow; missing real-provider evidence remains `Blocked`.
- Unverified FineReport, FVS, plugin, database, browser or renderer combinations remain `Unverified` or `Unsupported`.
- Every gate is recorded as `PASS`, `FAIL`, `Blocked` or `N/A`; `N/A` requires a reason.
- A blocking independent-review finding prevents user acceptance.

## Safety Boundaries

- Keep Mock switches for Dora, ASR, TTS and FVS.
- Never expose API keys, tokens, passwords, DSNs or Secrets in frontend code, logs, evidence or support packages.
- Screen control uses `action_id` plus backend whitelist and parameter-schema validation.
- Never execute model-generated JavaScript, SQL, Python, shell or other executable code.
- Database querying uses predefined parameterized read-only datasets; users and models cannot submit free SQL.
- Permission denial must never fall back to a more privileged source.
- Customer-specific content stays in customer configuration and customer documentation.
- Vendor plugins and licensed archives never enter Git, product packages, images or public source archives.
- Cross-screen leakage, authorization bypass, Secret exposure, data corruption or unrecoverable change immediately fails the batch.

## Testing And Completion Gate

- The pytest suite in `apps/api/tests/` covers POC routes and per-batch control-plane behavior: authorization negatives, error sanitization, upgrade integrity and controlled querying. Run it fully before finalizing work; add proportional gates per `docs/RESULT_ACCEPTANCE_STANDARD.md`.
- Before finalizing a batch: confirm the result card stayed within scope; run the proportional automated gates and required negative tests; obtain an independent Codex review; record the runnable result, known limitations, evidence hashes and rollback result.
- Confirm `docs/NEXT_ACTIONS.md` remains the sole active-task source; run `scripts/lint-doc-lifecycle.ps1`, plus `scripts/test-doc-lifecycle-lint.ps1` if the lint changed.

## Documentation Synchronization

Update only documents whose facts changed; `README.md` stays a stable product and navigation entry and never duplicates phase or task status:

- Always update the active acceptance package and record factual completion in `docs/DEV_LOG.md`.
- Update `docs/NEXT_ACTIONS.md` only when the active batch or its acceptance state changes.
- Update `docs/CHANGELOG.md` only for user-visible, operational or delivery-facing changes.
- Update `docs/13_RISKS_AND_TODO.md` only when a risk, limit or blocker changes.
- Add or update an ADR when architecture, security or process decisions change; archive historical detail instead of expanding current entry documents indefinitely.
- Update the applicable as-built or target contract when an API or shared structure changes; never merge the two states.
