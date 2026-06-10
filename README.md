# 数字人本地 POC 工程

本仓库用于沉淀一套可复用给客户的“党建大屏对话数字人”本地 POC 工程。当前阶段先建立文档驱动开发体系, 后续再逐步实现前端、后端、Mock 闭环和真实外部系统集成。

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

- 当前阶段: V0.0 文档体系初始化
- 下一阶段: V0.1 Mock 闭环工程初始化
- 代码状态: 尚未创建前后端工程
- 目标: 先保证项目可跨对话、跨人员、跨客户继续开发
