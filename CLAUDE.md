# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

通用可配置数字人 (Configurable Digital Human) local POC — a reusable, configuration-driven conversational digital human for big-screen scenarios. The current customer instance is 中天证券 (zt-securities) for a party-building dashboard, but the project itself is generic and customer-agnostic.

Pipeline: `Voice Wake-up → ASR → Text → Dora Agent (or Mock) → Query Excel metrics / RAGFlow knowledge / Screen control → Reply text + TTS → Frontend playback + subtitles + FVS dashboard control`

## Development Workflow

**Before starting any task**, read in order:
1. `AGENTS.md`
2. `docs/CODEX_CONTEXT.md`
3. `docs/NEXT_ACTIONS.md` — current phase and next task
4. `docs/DEV_LOG.md`
5. `docs/05_DEVELOPMENT_PLAN.md`
6. `docs/13_RISKS_AND_TODO.md`

For API/data changes also read `docs/06_API_CONTRACT.md` and `docs/07_DATA_CONTRACT.md`.
For external integrations also read `docs/integrations/`.

**After each development round**, update: `docs/DEV_LOG.md`, `docs/NEXT_ACTIONS.md`, `docs/CHANGELOG.md`. If risks/architecture change, update `docs/13_RISKS_AND_TODO.md` and add an ADR in `docs/decisions/`.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite (port 18000) |
| Backend | Python 3.12 + FastAPI (port 18080) |
| Frontend pkg mgr | `pnpm` (via Corepack) |
| Backend pkg mgr | `uv` |
| Deployment | Docker Compose |
| Session storage | SQLite (`data/sessions.db`) |
| Charts | ECharts |
| Animations | Canvas 2D + Web Audio API + CSS |

## Building

```bash
# Frontend (from apps/web/)
pnpm install --frozen-lockfile
pnpm build                    # runs vue-tsc --noEmit && vite build
pnpm dev                      # dev server on :18000

# Backend syntax check
python -m compileall apps/api/app

# Docker Compose (full stack)
docker compose up -d --build api web
docker compose down
```

## Testing

No conventional test framework is configured. The project uses these verification methods:

```bash
# PowerShell scripts (Windows/Docker Desktop environment)
scripts/check-poc.ps1                     # Pre-flight checks (Docker, ports, config, API, Web, Ops)
scripts/start-poc.ps1 -Build              # Build and start API + Web
scripts/start-poc.ps1 -Build -DemoStable   # Start with demo stable mode
scripts/smoke-demo.ps1                    # API smoke test with fixed demo questions
scripts/smoke-demo.ps1 -ExecuteScreenActions  # Smoke test including screen actions
scripts/export-logs.ps1 -Zip              # Export sanitized log package
scripts/stop-poc.ps1                      # Stop containers
```

Manual verification checklist for each phase: `pnpm build` passes, `python -m compileall apps/api/app` passes, `git diff --check` clean, relevant smoke endpoints return expected results.

## Architecture

### Frontend (`apps/web/src/`)
- `App.vue` — Single-file component (~3400 lines): state machine (`idle→monitoring→wake_checking→recording→thinking→speaking→cooldown`), VAD audio capture, wake-word detection, conversation UI, FVS iframe host, ops dashboard (`/ops` route), TTS playback (streaming PCM + fallback segment)
- `api.ts` — HTTP/SSE client for all backend endpoints
- `fvsAdapter.ts` — postMessage bridge to embedded FVS iframe
- `types.ts` — TypeScript type definitions matching backend models
- Vite dev server proxies `/api` → `http://localhost:18080`

### Backend (`apps/api/app/`)
- `main.py` — All FastAPI routes, chat processing pipeline, SSE streaming, TTS streaming, ops endpoints, config governance APIs
- `config.py` — Pydantic Settings from `.env` + YAML, customer overlay loading
- `models.py` — Pydantic request/response models
- `services/`:
  - `dora_client.py` — Dora Agent HTTP/SSE client
  - `dora_normalizer.py` — Parses Dora JSON output into `ChatResponse`
  - `mock_dora.py` — Mock Dora for demo/fallback
  - `ask_metrics.py` — Orchestrates metrics providers (excel/dora/auto mode)
  - `excel_ask_metrics_provider.py` — Excel-based metrics adapter
  - `ask_metrics_provider.py` — Abstract provider interface
  - `knowledge.py` — Knowledge service factory (Dora vs KnowledgeDirect routing)
  - `knowledge_provider.py` — KnowledgeDirect: RAGFlow retrieval + source-bound summarizer
  - `asr_provider.py` — ASR adapter (Aliyun/Mock)
  - `tts_provider.py` — TTS adapter with streaming support (Aliyun/Mock)
  - `screen_actions.py` — Screen action whitelist validation and execution
  - `screen_resolver.py` — Fixed command → action_id resolver
  - `config_overrides.py` — Runtime config overrides with validation/audit
  - `config_snapshot.py` — Read-only effective config + schema builder
  - `session_log.py` — SQLite session/error/metrics logging
  - `wake_words.py` — Wake word config loader
  - `yaml_loader.py` — YAML file loader utility

### Request Routing Logic (`_chat_response` in main.py)
1. **Screen control check** — resolve fixed commands against allowlist
2. **Metrics mode routing**: `excel` → metrics first, then knowledge/Dora; `dora` → knowledge/Dora only; `auto` → knowledge/Dora, fallback to metrics
3. **Knowledge routing**: `KnowledgeDirect` (local RAGFlow + source-bound summarizer) before Dora
4. **Dora/Mock Dora** — real Dora SSE or Mock Dora demo response
5. **Demo stable mode** fallback chain on Dora failure

### Configuration System
- `config/` — Generic defaults (screen-actions, wake-words, demo-cases, ask-metrics template)
- `config/customers/<customer-id>/` — Customer overrides (zt-securities is the current instance)
- `data/config-overrides/` — Runtime overrides (non-sensitive fields only), governed via `/api/config/*` APIs
- `ASK_METRICS_MODE`: `excel` (local Excel priority), `dora` (Dora-only), `auto` (Dora with Excel fallback)
- `KNOWLEDGE_MODE`: `dora` (Dora→RAGFlow MCP), `local_ragflow_llm` (Gateway-direct RAGFlow + source-bound summarizer), `auto`

## Non-Negotiable Rules

- **Never expose API keys** in frontend code, config YAML, or ops dashboard
- **Never execute model-generated code** (SQL, Python, JavaScript, shell)
- **Screen control only via `action_id`** — backend whitelist validation is mandatory
- **Keep Mock switches** for Dora, ASR, TTS, FVS — `ENABLE_MOCK_*` env vars
- **External systems through Adapter/Provider layer** — never call vendors directly
- **Customer content in customer configs/docs only** — never hardcoded in core code
- **Only advance the current phase** in `docs/NEXT_ACTIONS.md` — do not jump ahead to unimplemented features
- **Config writes require `CONFIG_ADMIN_TOKEN`** (or localhost origin when token is unset)

## Key Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `POST /api/chat` | Synchronous chat |
| `POST /api/chat/stream` | SSE streaming chat with incremental TTS |
| `POST /api/asr/transcribe` | Audio → text |
| `POST /api/tts` | Text → speech (full file) |
| `POST /api/tts/stream` | Text → speech (SSE PCM chunks) |
| `GET /api/wake/config` | Wake word configuration |
| `GET /api/demo/config` | Demo mode status, project display fields, mock state |
| `GET /api/screen/actions` | Read-only action whitelist |
| `POST /api/screen/execute` | Execute screen action (whitelist-validated) |
| `GET /api/ops/*` | Sanitized ops: health, dependencies, sessions, errors, metrics, export |
| `GET /api/config/effective` | Read-only effective config snapshot |
| `GET /api/config/schema` | Config field schema |
| `GET/PUT /api/config/overrides` | Runtime override read/write |
| `POST /api/config/validate` | Validate override payload |
| `POST /api/config/test` | Dry-run override validation |
| `POST /api/config/reload` | Reload runtime services from current overrides |
| `GET /api/config/audit` | Config change audit trail |
