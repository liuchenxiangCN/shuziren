# FineReport / FVS 多大屏数字人平台

面向已经采购 FineReport、并使用 FVS 建设业务大屏的客户，提供本地化部署的多大屏数字人配置、发布、问数与运营管理能力。

> 当前产品与执行摘要见 [docs/CODEX_CONTEXT.md](docs/CODEX_CONTEXT.md)；当前结果批次及其验收状态唯一以 [docs/NEXT_ACTIONS.md](docs/NEXT_ACTIONS.md) 为准。README 只负责稳定的产品介绍和导航，不复制动态状态。

## 产品与实现边界

| 范围 | 说明 |
| --- | --- |
| 目标产品 | 单站点、多大屏；每块屏独立配置数字人、能力组合、数据源、发布版本、监控和审计 |
| 当前实现 | 可运行的单客户配置、单运行实例 POC 基线 |
| 2D / 3D | V1 先提供 Renderer / AvatarPackage 扩展接口和测试 Renderer，不承诺尚未认证的真实格式 |
| 问数 | 保留 Excel；目标支持受控 MySQL、Oracle、PostgreSQL 以及通过外部门禁后的 FineReport 官方插件 |
| 身份 | 目标使用产品内置本地用户和 RBAC，不依赖 AD、LDAP 或 OIDC |
| 官方插件 | 由客户合法安装在 FineReport 工程中，本产品只调用且绝不分发 |

目标设计不代表已经实现。精确边界见 [标准产品设计](docs/17_STANDARD_PRODUCT_DESIGN.md)，当前代码事实见 [POC 已实现架构](docs/03_ARCHITECTURE.md)及 [已实现 API 契约](docs/06_API_CONTRACT.md)。

## 从这里开始

### 查看产品与计划

- [文档总入口](docs/00_INDEX.md)：生命周期、事实源和按范围阅读路线
- [标准产品设计](docs/17_STANDARD_PRODUCT_DESIGN.md)：目标客户、领域模型、能力边界和交付形态
- [结果驱动 P1–P5 路线](docs/05_DEVELOPMENT_PLAN.md)：按用户结果组织的产品化路线
- [当前唯一任务](docs/NEXT_ACTIONS.md)：当前结果批次及验收入口
- [结果验收规范](docs/RESULT_ACCEPTANCE_STANDARD.md)：自动门禁、独立复核、证据和回滚

### 使用 Codex 开发

先阅读 [AGENTS.md](AGENTS.md)，再按其中的 Required Routing 执行。不要从 README、历史归档或路线图推断当前任务。

### 区分目标与现状

- [当前上下文](docs/CODEX_CONTEXT.md)：小型当前快照
- [POC API 契约](docs/06_API_CONTRACT.md)与 [POC 数据契约](docs/07_DATA_CONTRACT.md)：`AS_BUILT_POC`
- [目标产品契约目录](docs/product/contracts/README.md)：`TARGET_NOT_IMPLEMENTED`
- [POC 历史归档](docs/archive/poc-v1/README.md)：只作历史证据
- [客户资料索引](docs/customers/README.md)：仅在明确客户任务时读取

## 运行当前 POC

以下命令只运行当前 POC 基线，不代表目标多大屏产品已经实现：

```powershell
.\scripts\check-poc.ps1
.\scripts\start-poc.ps1 -Build
.\scripts\check-poc.ps1 -RequireServices -RunSmoke
.\scripts\export-logs.ps1 -Zip
.\scripts\stop-poc.ps1
```

环境、端口和部署细节以 [POC 本地部署文档](docs/09_LOCAL_DEPLOY.md)为准。

## 文档与验收门禁

```powershell
.\scripts\lint-doc-lifecycle.ps1
.\scripts\test-doc-lifecycle-lint.ps1
```

每个产品化批次都必须提供可读验收卡和机器清单。用户只需验证结果场景；Codex 负责代码检查、安全负测、独立复核、证据哈希和恢复证明。

## 不进入仓库的内容

- API Key、Token、密码、DSN 和客户 Secrets
- 客户敏感数据、未脱敏日志和支持包
- FineReport 官方插件 ZIP 或其改名副本
- 未经授权的 2D / 3D 资产和供应商资源
