# 数字人本地 POC 工程

本仓库用于沉淀一套可复用给客户的“党建大屏对话数字人”本地 POC 工程。当前已输出 V1.0 验收交付包, 可通过 Docker Compose 和 PowerShell 脚本启动前后端、预检依赖、执行演示 smoke 并导出脱敏日志包。

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
- [docs/delivery/v1.0/README.md](docs/delivery/v1.0/README.md): V1.0 验收交付包

## 当前状态

- 当前阶段: V1.0 POC 验收交付包已输出, 下一步为客户现场验收复演和签收
- 已完成: V0.8 功能增强、V0.9 交付优化、V1.0 交付包
- 代码状态: Vue 3 前端、FastAPI 后端、Docker Compose、客户配置覆盖层和 V0.9 脚本均已落地
- 本地访问: `http://localhost:18000`、`http://localhost:18080/api/health`

## 常用脚本

```powershell
scripts\check-poc.ps1
scripts\start-poc.ps1 -Build
scripts\smoke-demo.ps1
scripts\export-logs.ps1 -Zip
scripts\stop-poc.ps1
```
