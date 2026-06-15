# ADR-0022: 能力解耦路由与配置中心

## Status

Proposed

## Date

2026-06-15

## Context

当前系统已经具备三条核心能力:

- 问数: 已实现 Gateway 本地 Excel Adapter, 并通过 `ASK_METRICS_MODE=excel|dora|auto` 支持 Dora / 本地 / 自动回退。
- 知识库: 已实现 Dora 调用 RAGFlow MCP 的路径, 但 Gateway 本地直连知识库 Adapter 尚未实现。
- 控屏: 已实现 `action_id` 白名单校验和 FVS iframe `page_number` / postMessage 执行链路。

用户希望继续增强为通用可配置数字人 POC 模板:

- 三类能力都可以按配置选择 Dora 或本地实现。
- 知识库本地直连由 RAGFlow 只做检索, 最终答案由 Gateway 中受控 LLM summarizer 生成, 不依赖 RAGFlow chat / assistant。
- 问数数据源扩展为受控数据库结果表 / 汇总表 / 视图。
- 控屏白名单和映射关系、Prompt、项目名称、看板地址、客户相关信息都应可配置。
- 前端提供配置页, 用户可调整非敏感配置。
- 中天证券党建大屏不再作为项目本体, 而是通过 `zt-securities` 客户 profile 实现的一个实例。

2026-06-15 对当前实际代码和工作树审计后发现, 临时宣传录屏分支内容曾进入主线工作树, 包括录屏页面、专用数字人组件、专用资产、专用客户配置、财务录屏动作白名单和临时 ADR。这些内容不属于通用可配置数字人主链路, 也不能作为能力路由与配置中心的输入。

同时当前代码还存在两个实现约束:

- 尚未实现 `/api/config/*`; 配置中心必须从只读 effective config 和 schema 开始。
- `POST /api/screen/execute` 尚未返回完整授权 action 配置; 前端仍依赖已缓存的动作列表执行 FVS 动作。因此开放 action 可写配置前, 必须先把前端执行依据切到后端本次授权结果。
- `docker-compose.yml`、包名、根级配置和前端 Mock 默认态仍有客户实例残留; 默认启动路径必须先改回通用 profile。
- `AskMetricsService` 仍包含党建 Excel 问数硬编码。若阶段 0A 直接要求 `apps/` 零客户词, 会与阶段 2 才抽象 `AskMetricsProvider` 的路线冲突。
- 当前配置加载只返回合并后的 `Settings`, 不保留字段级来源。只读 effective config 若要展示 `source`, 必须新增来源追踪或显式来源构造逻辑。

## Decision

- 先恢复主线清洁基线: 删除本地临时宣传分支, 移除主线中的临时录屏页面、专用资产、专用客户配置、财务录屏白名单和临时 ADR。
- 将阶段 0 明确为阶段 0A: 先修正默认启动入口、包名、根级配置和前端 Mock 默认态; `apps/api/app/services/ask_metrics.py` 在 Provider 抽象前列为临时遗留 allowlist, 不把它作为阶段 0A 失败条件。
- 能力路由与配置中心只覆盖通用可配置数字人 POC 主链路, 不继承临时宣传录屏链路的 action、页面、Prompt 或资产。
- 项目本体使用通用默认 profile; 中天证券需求通过 `config/customers/zt-securities/` 覆盖项目名称、客户名称、助手名称、Dora Agent、知识库、问数数据源、FVS 地址、动作白名单、唤醒词、演示问题和话术。
- 新增能力路由概念 `CapabilityRouter`, 将问数、知识库、控屏解析分别路由到独立 Provider。
- 大屏真实执行继续固定为本地 `action_id` 白名单链路; Dora、本地规则和 LLM 均不得直接执行 FVS JavaScript。
- 问数 Provider 目标支持:
  - `excel`
  - `database`
  - `dora`
- 数据库问数只允许查询配置中的只读结果表 / 汇总表 / 视图和字段, 禁止 LLM 生成 SQL。
- 知识库 Provider 目标支持:
  - `dora`
  - `local_ragflow_llm`
- `local_ragflow_llm` 中 RAGFlow 只负责检索 chunks; Gateway 内 LLM summarizer 只基于 chunks 输出带来源的受控 `answer`。
- 控屏拆分为:
  - Resolver: 解析用户意图为候选 `action_id`。
  - Executor: 通过本地白名单执行已授权 action。
- 新增配置中心方案:
   - `GET /api/config/effective`
   - `GET /api/config/schema`
  - `POST /api/config/validate`
  - `PUT /api/config/overrides`
  - `POST /api/config/test`
  - `POST /api/config/reload`
  - `GET /api/config/audit`
- 配置页只能编辑非敏感配置; API Key、Token、数据库密码和 DSN 明文仍只允许通过 `.env` / 部署环境变量提供。
- 阶段 1 的 `effective` 必须由白名单 `ConfigSnapshot` 构造, 且字段来源必须来自 provenance 或显式来源构造; 无法精确判断来源时标注为 `derived` / `unknown`, 不得凭最终值误标。
- 项目名称、客户名称、场景名称、助手名称、看板地址、Prompt profile、白名单 action、演示问题和话术都进入配置, 不再写死为中天证券党建场景。
- 实施顺序调整为:
  1. 阶段 0A: 主线默认入口和根模板清洁, 并记录问数遗留 allowlist。
  2. 配置模型与只读配置页。
  3. 问数 Provider 抽象与数据库 Adapter, 移除问数遗留 allowlist。
  4. KnowledgeDirectAdapter + 受控 LLM summarizer。
  5. 控屏 resolver 与 `/api/screen/execute` 授权 action 返回增强。
  6. 可写配置页、dry-run、reload 和 audit。

## Consequences

优点:

- 主线重新聚焦客户交付 POC, 避免临时宣传链路污染后续架构判断。
- 三类能力可以独立切换 Dora / 本地 / auto, 不再被一个全局模式绑定。
- 高频固定路径可以本地加速, 复杂编排仍可交给 Dora。
- 知识库本地直连不要求配置 RAGFlow chat / assistant, 保持 RAGFlow 只检索的边界。
- 数据库问数沿用 Excel Adapter 的口径化思路, 适合客户提供结果表或视图。
- 控屏执行安全边界更清晰, 所有真实动作仍必须经过本地白名单。
- 多客户复用时可以移除代码和默认模板中的中天证券 / 党建大屏硬编码。

约束:

- 需要新增配置 schema、配置校验、配置审计和可写 override 存储。
- 阶段 1 必须先只读展示, 不能直接写默认 YAML; 当前 Compose 配置目录仍是只读挂载。
- 阶段 1 还需要新增字段来源追踪或来源构造, 否则只读配置页只能展示最终值, 不能可靠解释配置来源。
- action 配置开放写入前, 需要先修改 `/api/screen/execute` 响应和前端执行路径, 确保前端只执行后端本次授权 action。
- 数据库问数不覆盖任意自然语言 BI 分析, 只覆盖配置过的指标和字段。
- LLM summarizer 的输出必须强制 schema 校验和来源约束, 否则会引入编造风险。
- 配置页如果开放给客户现场使用, 后续需要访问控制; 当前 Ops 看板仍按本地 POC 内网前提运行。
- 历史 DEV_LOG、CHANGELOG、客户目录和已交付材料中的客户名称是历史事实或客户实例内容, 不应批量改写。
- 在阶段 2 完成前, `AskMetricsService` 中的党建问数硬编码是已知遗留, 不应继续扩展; 新数据库问数必须等 Provider 抽象后接入。
