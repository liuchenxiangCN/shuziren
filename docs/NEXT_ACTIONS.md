# Next Actions

## Current Phase

V0.0 文档体系初始化。

## Next Phase

V0.1 Mock 闭环。

## Next Task

初始化前后端工程骨架和 Docker Compose。

## Context

当前仓库已有文档体系、Git 仓库、`.env.example` 和第一版 `config/` 配置文件, 尚未创建前端、后端和 Docker Compose。下一步应严格按 V0.1 范围推进, 只实现 Mock 闭环, 不接真实 Dora、ASR、TTS、RAGFlow、FVS。

## Recommended Prompt

```text
请先阅读 AGENTS.md、docs/CODEX_CONTEXT.md、docs/05_DEVELOPMENT_PLAN.md、docs/06_API_CONTRACT.md、docs/07_DATA_CONTRACT.md、docs/NEXT_ACTIONS.md, 然后开始 V0.1 Mock 闭环工程初始化。前端使用 pnpm, 后端使用 uv + Python 3.12 Docker 运行时。不要接真实 Dora、ASR、TTS、RAGFlow、FVS。完成后更新 DEV_LOG、NEXT_ACTIONS、CHANGELOG 和必要的风险记录。
```

## Already Done

- 已初始化 Git 仓库。
- 已创建 `.gitignore`。
- 已创建 `.env.example`。
- 已创建 `config/screen-actions.yaml`。
- 已创建 `config/wake-words.yaml`。
- 已创建 `config/demo-cases.yaml`。
- 已创建 `config/dora-output-schema.json`。
- 已创建 `data/.gitkeep` 和 `logs/.gitkeep`。

## V0.1 Acceptance

- 创建 `apps/web` Vue 3 + TypeScript + Vite 工程。
- 创建 `apps/api` FastAPI 工程。
- 创建 `docker-compose.yml`。
- `GET /api/health` 返回 ok。
- `POST /api/chat` 可通过 Mock Dora 返回 `answer` / `screen_control` / `fallback`。
- `GET /api/screen/actions` 返回动作白名单。
- `POST /api/screen/execute` 合法 action 成功, 非法 action 被拒绝。
- 前端可输入文本、调用 `/api/chat`、展示回复、执行 Mock FVS 动作。
- 基础会话日志可写入 `data/` 或 SQLite。

## Files Likely To Create Next

```text
apps/web/
apps/api/
infra/caddy/
docker-compose.yml
```

## Do Not Do Yet

- 不接真实 Dora。
- 不接真实 ASR。
- 不接真实 TTS。
- 不部署真实 RAGFlow。
- 不真实调用 FVS JS。
- 不做 2D / 3D 数字人形象。
