# FineReport / FVS 多大屏数字人平台

本仓库正在把现有通用可配置数字人 POC 产品化为一套面向已采购 FineReport、并使用 FVS 建设大屏客户的本地化多大屏数字人管理平台。

当前代码仍是单客户配置 / 单运行实例 POC 基线。多大屏、Renderer / AvatarPackage 扩展接口、FineReport 官方插件问数、RBAC 和完整后台管理属于目标态，尚未实现。首批只预留 2D / 3D 接口，不承诺具体格式。

## P0 结果

- FineReport / FVS 目标为 11.0 大版本及以后，实际支持按精确版本组合认证。
- 标准部署为单站点、多大屏，不设置产品硬编码数量上限；首版验证三路并发正确性。
- 使用内置本地用户和 RBAC。
- Excel、MySQL、Oracle、PostgreSQL 采用受控只读数据集。
- 官方插件由客户合法安装，本产品只调用且不分发。
- 官方插件外部 API、认证、会话、权限和升级行为仍是 P2 外部门禁。

## 当前阶段

P0 产品定义已完成。下一阶段是 P1 目标领域模型、数据模型、身份模型、存储与控制面 API 契约设计；尚未进入目标产品运行时代码实现。

## 主要入口

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/17_STANDARD_PRODUCT_DESIGN.md`
- `docs/integrations/FINEREPORT_AI_PLUGIN_INTEGRATION.md`
