# Codex Context

本文件是 Codex 跨对话恢复上下文的第一入口。新对话开始时, 先阅读本文件, 再阅读 `NEXT_ACTIONS.md` 和 `DEV_LOG.md`。

## Project

中天证券党建大屏对话数字人本地 POC 工程。

## Goal

构建一套可复用给客户的本地 POC 模板, 完整跑通:

```text
语音唤醒 -> ASR -> 文本问题 -> Dora Agent
-> Dora 问数 / RAGFlow 知识库 / 大屏控制动作
-> 回复文本 / 图文结果 / screen_action
-> TTS -> 前端播报 + 字幕 + 动效 + FVS 控制
```

## Current Phase

V0.0 文档体系初始化。

下一阶段是 V0.1 Mock 闭环, 只实现可运行工程骨架和文本 Mock 流程, 暂不接真实 Dora、ASR、TTS、RAGFlow、FVS。

## Must Read First

1. `AGENTS.md`
2. `docs/00_INDEX.md`
3. `docs/NEXT_ACTIONS.md`
4. `docs/DEV_LOG.md`
5. `docs/05_DEVELOPMENT_PLAN.md`
6. `docs/13_RISKS_AND_TODO.md`
7. `docs/decisions/`

## Core Architecture

- Frontend: Vue 3 + TypeScript + Vite
- Backend: Python FastAPI
- Deployment: Docker Compose
- Frontend package manager: pnpm
- Backend package manager: uv
- Backend Python runtime: Python 3.12 in Docker, Python 3.11/3.12 acceptable for non-Docker local development
- Config: `.env` + YAML
- Storage: SQLite
- Animation: Canvas 2D + Web Audio API + CSS
- Chart: ECharts
- Agent: Dora
- Knowledge Base: RAGFlow
- Screen: FVS
- ASR / TTS: 国产供应商优先, 默认阿里云百炼, 其他供应商通过 Adapter 扩展

## Non-Negotiable Rules

- 不在前端暴露 API Key。
- 不让大模型直接生成并执行 JavaScript。
- 大屏控制只能使用 `action_id`。
- 后端必须通过动作白名单校验 `action_id`。
- Dora / ASR / TTS / FVS 必须保留 Mock 开关。
- 外部系统接入必须通过 Adapter / Provider 层隔离。
- 每完成一轮开发必须更新 `DEV_LOG.md`、`NEXT_ACTIONS.md`、必要时更新 `13_RISKS_AND_TODO.md`。
- 客户差异放在客户配置和客户文档中, 不写死到核心代码。

## Resume Protocol

开始开发前:

1. 阅读 `NEXT_ACTIONS.md`, 确认当前任务。
2. 阅读相关设计文档和 ADR。
3. 如任务涉及接口或数据结构, 先检查 `06_API_CONTRACT.md` 和 `07_DATA_CONTRACT.md`。
4. 执行任务时保持变更聚焦, 不跨阶段实现真实外部服务。
5. 完成后更新开发记录、下一步、风险和变更日志。

推荐对 Codex 的启动提示:

```text
请先阅读 AGENTS.md 和 docs/CODEX_CONTEXT.md, 按 docs/NEXT_ACTIONS.md 继续。只推进当前阶段任务, 完成后更新 DEV_LOG、NEXT_ACTIONS、CHANGELOG 和必要的风险记录。
```
