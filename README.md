# 数字人本地 POC 工程

本仓库用于沉淀一套可复用给客户的“党建大屏对话数字人”本地 POC 工程。当前已完成 V0.1 Mock 闭环, 可通过 Docker Compose 跑通文本输入、Mock Dora 回复、Mock FVS 动作展示和会话日志。

## 快速恢复上下文

新开 Codex 对话时, 优先让 Codex 阅读:

1. [AGENTS.md](AGENTS.md)
2. [docs/CODEX_CONTEXT.md](docs/CODEX_CONTEXT.md)
3. [docs/NEXT_ACTIONS.md](docs/NEXT_ACTIONS.md)
4. [docs/DEV_LOG.md](docs/DEV_LOG.md)
5. [docs/05_DEVELOPMENT_PLAN.md](docs/05_DEVELOPMENT_PLAN.md)
6. [docs/13_RISKS_AND_TODO.md](docs/13_RISKS_AND_TODO.md)

建议提示词:

```text
请先阅读 AGENTS.md 和 docs/CODEX_CONTEXT.md, 再按照 docs/NEXT_ACTIONS.md 继续推进。遵守 docs/05_DEVELOPMENT_PLAN.md 和 docs/decisions 下的 ADR。
```

## 文档入口

- [docs/00_INDEX.md](docs/00_INDEX.md): 文档总目录
- [docs/01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md): 项目背景、目标、边界
- [docs/02_PRODUCT_BLUEPRINT.md](docs/02_PRODUCT_BLUEPRINT.md): 产品蓝图与业务流程
- [docs/03_ARCHITECTURE.md](docs/03_ARCHITECTURE.md): 总体架构
- [docs/05_DEVELOPMENT_PLAN.md](docs/05_DEVELOPMENT_PLAN.md): 分阶段开发计划
- [docs/12_CUSTOMER_HANDOFF.md](docs/12_CUSTOMER_HANDOFF.md): 客户移交说明

## 当前状态

- 当前阶段: V0.1 Mock 闭环已完成
- 下一阶段: V0.2 Dora 接入准备
- 代码状态: 已创建 `apps/web`、`apps/api` 和 `docker-compose.yml`
- 本地访问: `http://localhost:18000`、`http://localhost:18080/api/health`
