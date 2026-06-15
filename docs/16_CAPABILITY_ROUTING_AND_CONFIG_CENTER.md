# 能力解耦路由与配置中心方案

本文记录后续主线增强方案: 将问数、知识库、控屏解析、控屏执行白名单、Prompt、项目名称、客户信息和看板地址从写死逻辑中拆出来, 形成通用可配置数字人项目, 再通过客户配置和前端配置页适配具体客户。

本文只覆盖通用可配置数字人 POC 主链路。中天证券党建大屏是当前客户配置实例, 通过 `config/customers/zt-securities/` 和客户文档实现。2026-06-15 已按主线清洁原则删除本地临时宣传分支, 并从主线移除录屏页面、专用资产、临时客户配置、财务录屏动作白名单和对应临时 ADR。

## 本轮审计修正与解决方案

基于当前实际代码, 后续优化不能直接从“可写配置中心”开始, 需要先建立主线清洁基线和只读配置观测层。后续实现若与本文冲突, 以本文的阶段边界和前置条件为准。

### 已确认的真实代码约束

- 尚未实现 `/api/config/*`; 现有配置可观测入口主要是 `/api/demo/config`、`/api/ops/*` 和各业务 API。
- `POST /api/screen/execute` 当前只返回 `success`、`action_id`、`speak_text`、`request_id` 和 `error`, 尚未返回完整授权 action 配置。
- 前端当前仍依赖 `GET /api/screen/actions` 的缓存动作配置执行 FVS `page_number` / `postMessage`。
- Docker Compose 当前把 `./config:/app/config:ro` 只读挂载; 可写配置页必须先引入独立覆盖目录, 不能直接改默认 YAML。
- 当前 FVS 配置存在前后端来源分裂: 后端会从客户 `fvs.yaml` / 环境变量得到 `settings.fvs_*`, 但浏览器实际执行由 `VITE_FVS_*` 构建参数和 URL 参数 `?fvs_url=` / `?fvs_mode=` 决定。
- 阶段 2 已完成问数 Provider 抽象: `AskMetricsService` 仅做 provider 编排, Excel 问数由配置驱动 `ExcelAskMetricsProvider` 承接; 客户实例 metric 规则位于客户 profile。
- 当前配置加载器只返回合并后的 `Settings`, `_overlay_value()` / `_overlay_path()` 没有记录字段级来源; 阶段 1 若要展示 `source`, 必须新增来源追踪或显式按规则重算来源。
- 当前根级默认模板尚未完全通用化: `docker-compose.yml` 默认仍指向 `zt-securities` 和 `zt-digital-human-*`; `apps/api/pyproject.toml`、`apps/web/package.json` 仍使用 `zt-digital-human-*` 包名; 根级 `config/ask-metrics.yaml`、`apps/api/app/services/ask_metrics.py`、根级 `config/wake-words.yaml`、前端 Mock 大屏仍有党建 / 客户实例残留。

### 需要解决的问题

| 编号 | 问题 | 影响 | 解决方向 |
| --- | --- | --- | --- |
| P0-1 | 临时宣传 / 录屏内容可能污染主线 | 后续架构误把临时页面、资产或 action 当主线能力 | 阶段 0A 固化临时污染搜索门禁, 只允许主线文档和客户 profile 进入方案输入 |
| P0-2 | 客户实例内容仍散落在默认启动入口和根模板 | “通用可配置数字人”默认运行路径无法成立 | 阶段 0A 先修正 Docker Compose、包名、根级配置和前端 Mock 默认态, 默认启动不得进入 `zt-securities` |
| P0-3 | 工作树存在未分类输出和未提交变更 | 清洁基线不可复现 | 阶段 0A 记录或清理临时输出目录, 明确哪些文件属于本轮主线变更 |
| P0-4 | `AskMetricsService` 曾是客户 Excel 硬编码 | 如果不抽象 Provider, `apps/` 零客户词会与保留 Excel 问数冲突 | 阶段 2 已抽象 `AskMetricsProvider` 并移除该 allowlist; 运行代码不再依赖客户实例词 |
| P1-1 | effective config 若直接 dump `Settings` 会泄露密钥 | Dora / ASR / TTS / RAGFlow Key 可能进入前端 | 阶段 1 使用白名单构造 `ConfigSnapshot`, 不使用 `Settings.model_dump()` 作为输出源 |
| P1-2 | FVS 显示配置和浏览器实际执行配置可能不一致 | 配置页展示的看板地址不一定驱动当前页面 | 阶段 1 同时展示后端 effective FVS 配置和前端 runtime FVS 配置来源 |
| P1-3 | 当前 `Settings` 不保留字段来源 | `effective.source` 可能被误标, 影响配置解释和排障 | 阶段 1 新增字段来源构造器或配置加载 provenance, 不允许凭最终值猜测为精确来源 |
| P2-1 | 数据库问数若直接塞进现有 Excel Provider | 破坏只读、配置驱动和多客户边界 | 阶段 2 只完成 Provider 抽象和 Excel 迁移, Database Provider 保持 `not_implemented`; 后续必须另开只读表 / 字段白名单阶段 |
| P4-1 | action 可写早于授权 action 响应增强 | 前端可能执行缓存旧 action, 不能保证本次后端授权是唯一依据 | 阶段 4 先让 `/api/screen/execute` 返回完整授权 action, 前端只执行该响应 |

### 总体解决顺序

1. 阶段 0A: 主线默认入口和根模板清洁。先清掉临时宣传污染, 修正 Docker Compose 默认 profile、包名、根级配置和前端 Mock 默认态, 并记录不可立即抽象的遗留 allowlist。
2. 阶段 1: 只读脱敏 effective config。只新增观测能力和字段来源构造, 不改现有问答、问数、语音、TTS、控屏行为。
3. 阶段 2: 问数 Provider 抽象优先。已先把 `AskMetricsProvider` 和配置驱动 Excel Provider 立住, 并移除 `AskMetricsService` 客户实例 allowlist; Database Provider 仅保留未实现状态。
4. 阶段 3 / 4: 分别推进知识库直连和控屏授权 action 增强。
5. 阶段 5: 可写配置、dry-run、reload、audit。未完成阶段 4 前, 不开放 action 映射写入。

## 目标

- 根级默认模板、Docker Compose 默认值、前端 Mock 默认态和核心代码不再绑定中天证券 / 党建大屏; 客户实例只能通过客户 profile、客户文档和历史交付材料出现。
- 问数、知识库、控屏解析三类能力分别可配置为 Dora 或本地直连实现。
- 大屏真实执行永远留在本地 `action_id` 白名单链路内, Dora、本地规则或 LLM 只能产出候选 `action_id`。
- 知识库本地直连不依赖 RAGFlow chat / assistant; RAGFlow 只检索 chunks, Gateway 通过受控 LLM summarizer 汇总。
- 问数数据源从 Excel 扩展到受限数据库结果表 / 汇总表 / 视图。
- 项目名称、客户名称、看板地址、欢迎语、演示文案、Prompt profile 等客户差异都进入配置。
- 前端先提供只读配置管理路由, 展示脱敏后的 effective config、配置来源和当前 provider 状态; 可写配置、校验、dry-run 和热加载放到阶段 5。

## 非目标

- 阶段 1 不实现可写配置, 不实现 `PUT /api/config/overrides`, 不改默认 YAML, 不改变现有问答、问数、语音、TTS 或控屏行为。
- 不允许模型生成 SQL、Python、JavaScript 或 shell 后由系统执行。
- 不允许 Dora、LLM summarizer 或前端直接执行 FVS JavaScript。
- 不把 API Key、Token、数据库密码或供应商密钥写入 YAML 或返回前端。
- 不把当前 POC 直接扩展成通用 BI 自助分析系统; 问数数据库直连只面向受控结果表和受控字段。

## 当前实现基线

### 问数

当前已实现 `ASK_METRICS_MODE=excel|dora|auto`:

- `excel`: Gateway 本地 Excel Adapter 先匹配问数, 命中后直接返回 `answer`; 未命中继续 Dora / Mock Dora。
- `dora`: Excel Adapter 不抢答, 由 Dora / Mock Dora 承接问数。
- `auto`: 优先 Dora / Mock Dora, Dora 返回 `fallback` 或请求失败时回退 Excel。

现有本地问数路径为 `AskMetricsService -> AskMetricsProvider -> ExcelAskMetricsProvider`, 数据来自 `docs/demo_data/ask_metrics/*.xlsx`, workbook / sheet / metric 定义来自根级 `config/ask-metrics.yaml` 或客户覆盖层 `config/customers/<customer-id>/ask-metrics.yaml`。

当前状态:

- 阶段 2 已新增 `AskMetricsProvider` 接口和配置驱动 `ExcelAskMetricsProvider`。
- `AskMetricsService` 只负责 provider 编排和 `ChatResponse` 包装, 不再包含客户实例关键词、字段或模板。
- 根级 `config/ask-metrics.yaml` 是通用空 metric 模板, 不引用客户 Excel 文件。
- 当前客户实例的 Excel 文件、sheet、关键词、字段、回答模板和来源说明保留在 `config/customers/zt-securities/ask-metrics.yaml`。
- Database Provider 仅在状态和 schema 中保留 `not_implemented`, 阶段 2 未连接数据库、未执行 SQL。

### 通用默认模板

当前已有项目 / 客户展示字段: `project_id`、`project_name`、`product_name`、`customer_id`、`customer_name`、`scenario_name`、`assistant_name`, 并已通过 `/api/demo/config` 返回给前端。

当前缺口:

- `docker-compose.yml` 默认值仍使用 `CUSTOMER_ID=zt-securities`、`CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities` 和 `zt-digital-human-*` 镜像 / 容器名。
- `apps/api/pyproject.toml` 和 `apps/web/package.json` 的包名仍使用 `zt-digital-human-*`。
- 根级 `config/wake-words.yaml` 仍包含 `中天小天`、`小天` 等客户实例唤醒词。
- 前端 Mock 大屏仍显示 `党员总数`、`学习完成率` 等党建指标。
- 根级 `config/demo-cases.yaml` 仍有 `党员学习`、`党建活动` 等客户场景关键词。

解决方向:

- 根级默认值改为 `default` / `configurable-digital-human-*` / 通用唤醒词和通用指标样例。
- 包名和容器名也改为 `configurable-digital-human-*`, 让默认构建产物与项目定位一致。
- 中天证券和党建话术保留在 `config/customers/zt-securities/`、`docs/customers/zt-securities/`、历史交付包和历史日志中。
- `.env.example` 可保留中天证券 profile 的注释示例, 但不能让默认启动路径自动进入客户实例。

### 知识库

当前已实现 Dora 中心路径:

```text
Gateway /api/chat
-> Dora OpenClaw SSE
-> Dora Agent 调用 RAGFlow MCP ragflow_retrieval(keyword=false)
-> RAGFlow Dataset 返回 chunks
-> Dora 生成最终 answer
-> Gateway 归一化为 ChatResponse
```

当前尚未实现 `KnowledgeDirectAdapter`。`RAGFLOW_BASE_URL` 和 `RAGFLOW_MCP_URL` 已作为 Gateway 侧配置和 Ops 探测预留。

### 控屏

当前控屏安全链路已经可配置:

```text
Dora / Mock Dora / 本地规则
-> 只输出 screen_control.action.id
-> Gateway 通过 ScreenActionService 校验 action_id 白名单
-> 前端收到 screen_control 后再次调用 /api/screen/execute
-> Gateway 再次校验 action_id
-> 前端 FVS Adapter 按后端确认结果执行 iframe page_number 或 postMessage
```

白名单配置位置:

- 默认: `config/screen-actions.yaml`
- 客户覆盖: `config/customers/<customer-id>/screen-actions.yaml`

动作示例:

```yaml
actions:
  SWITCH_TAB_ORG:
    label: 成品库存
    type: page
    description: 切换到成品库存页
    fvs_function: gotoPage
    params:
      pageNumber: 2
    speak_text: 已为您切换到成品库存页面。
```

## 目标架构

新增能力路由层:

```text
ChatRequest
-> CapabilityRouter
   -> AskMetricsProvider
   -> KnowledgeProvider
   -> ScreenControlResolver
   -> DoraProvider / MockDoraProvider
-> ChatResponse(answer / screen_control / fallback)
```

执行层保持独立:

```text
screen_control.action.id
-> /api/screen/execute
-> ScreenActionService whitelist
-> AuthorizedScreenAction
-> Frontend FVS Adapter
```

核心原则:

- Provider 只负责理解、检索、汇总或解析。
- Executor 只执行本地白名单动作。
- Provider 和 Executor 之间唯一可执行桥梁是 `action_id`。

## 能力路由配置

建议新增客户级 `capabilities.yaml`:

```yaml
version: 1

project:
  project_id: configurable-digital-human
  project_name: 通用可配置数字人 POC
  product_name: 可配置大屏对话数字人
  customer_id: default
  customer_name: 默认客户
  scenario_name: 通用大屏交互
  assistant_name: 小智
  wake_greeting: 您好。
  acknowledgement_text: 收到, 正在为您查找信息。
  fallback_text: 这个问题我还需要更多信息，请您换一种方式描述。

dashboard:
  provider: fvs
  integration_mode: iframe
  url: /webroot/decision/view/duchamp?viewlet=your-dashboard.fvs&page_number=1
  target_origin: ""
  page_param: page_number
  same_origin_proxy:
    enabled: true
    public_prefix: /webroot/
    upstream: http://host.docker.internal:8075/webroot/

capabilities:
  ask_metrics:
    mode: auto
    order: [database, excel, dora]
    fallback_text: 问数数据暂不可用，请稍后重试。

  knowledge:
    mode: auto
    order: [local_ragflow_llm, dora]
    fallback_text: 知识库未找到可靠依据，请补充资料后再试。

  screen_control:
    resolver: hybrid
    resolver_order: [local_rules, dora]
    executor: fvs_whitelist
    require_execute_api: true
    allow_dynamic_js: false

prompts:
  knowledge_summarizer:
    profile: generic_knowledge_qa
    file: config/prompts/knowledge-summarizer.md
    output_schema: answer_with_sources

  screen_resolver:
    profile: screen_action_resolver
    file: config/prompts/screen-resolver.md
    output_schema: screen_action_candidate

  dora_direct_mode:
    profile: dora_capability_router
    file: config/prompts/dora-direct-mode.md
```

`mode=auto` 表示按 `order` 依次尝试。Provider 返回明确 `fallback`、超时或异常时, 才进入下一个 Provider。命中答案但置信度低时, 应按能力配置决定是否 fallback。

## 问数扩展方案

### 数据源类型

问数 Provider 分三类:

- `excel`: 现有本地 Excel Adapter。
- `database`: 新增只读数据库 Adapter, 查询受控结果表 / 汇总表 / 视图。
- `dora`: Dora 侧通用问数工具或 Agent。

以下配置是客户 profile 级数据库问数示例, 不能直接作为根级默认模板:

```yaml
ask_metrics:
  provider: database
  fallback: excel

  database:
    connection_name: party_metrics_readonly
    dialect: postgres
    timeout_seconds: 5
    max_rows: 50

  tables:
    study_dashboard:
      table: party_study_dashboard_result
      label: 党员学习结果表
      allowed_fields:
        period: 统计周期
        total_members: 党员总数
        completed_members: 已完成学习人数
        completion_rate: 学习完成率

  metrics:
    study_completion_rate:
      source_table: study_dashboard
      match_keywords: ["学习完成率", "党员学习完成率"]
      select_fields:
        - total_members
        - completed_members
        - completion_rate
      filters:
        period: latest
      title: 党员学习完成率
      speak_template: "当前党员学习完成率为{completion_rate}，党员总数{total_members}人，已完成学习{completed_members}人。"
      source_template: "数据库视图 party_study_dashboard_result / 最新统计周期"
```

数据库 DSN 不进 YAML, 只通过环境变量或部署密钥提供:

```env
METRICS_DB_DSN=postgresql://readonly_user:***@host:5432/db
```

### 数据库问数安全规则

- 使用只读数据库账号。
- 只允许查询配置中的表 / 视图。
- 只允许查询配置中的字段。
- SQL 只能由系统根据配置模板生成, 不允许 LLM 生成 SQL。
- where 条件只能来自受控枚举、固定参数或参数化值。
- 必须设置超时、默认 limit 和最大返回行数。
- 日志只记录数据源别名、表别名、字段别名、命中指标, 不记录 DSN 和密码。

### 适用范围

适合:

- 客户侧可提供结果表、汇总表、宽表或视图。
- 表结构与 Excel Dashboard / 汇总 sheet 接近。
- 指标口径、字段和统计周期可配置。

不适合:

- 让系统理解复杂业务库并任意 join。
- 自然语言生成任意 SQL。
- 跨库自由分析或临时 BI 探索。

## 知识库直连方案

新增 `KnowledgeDirectAdapter`:

```text
用户问题
-> KnowledgeDirectAdapter 判断知识库问题
-> RAGFlowRetriever 调用 RAGFlow MCP 或 Retrieval API
-> 返回 chunks + metadata
-> LlmSummarizer 受控汇总
-> ChatResponse(answer) + sources
```

以下配置是客户 profile 级知识库直连示例, 不能直接作为根级默认模板:

```yaml
knowledge:
  provider: local_ragflow_llm

  retrieval:
    provider: ragflow
    transport: mcp
    mcp_url: http://host.docker.internal:9382/mcp
    dataset_name: zt_party_building_demo
    keyword: false
    page_size: 3
    top_k: 16
    similarity_threshold: 0.35
    max_chunk_chars: 1200

  summarizer:
    provider: qwen
    model: qwen-plus
    prompt_profile: customer_knowledge_qa
    require_sources: true
    max_answer_chars: 800
    no_evidence_policy: fallback
```

Summarizer 约束:

- 只能基于检索 chunks 回答。
- 必须输出来源列表。
- 检索为空或依据不足时返回无依据 fallback。
- 不生成控屏动作。
- 不生成或要求执行 SQL、Python、JavaScript、shell。
- 输出必须满足 `answer_with_sources` schema。

建议 schema:

```json
{
  "type": "answer",
  "title": "入党流程",
  "speak_text": "根据知识库资料，入党流程主要包括...",
  "display": {
    "mode": "text",
    "summary": "入党流程摘要",
    "bullets": ["递交申请", "谈话", "积极分子培养"],
    "sources": [
      {
        "document_name": "join_party_process.md",
        "chunk_id": "chunk-001",
        "similarity": 0.82
      }
    ]
  },
  "audit": {
    "capability": "knowledge",
    "provider": "local_ragflow_llm",
    "prompt_profile": "customer_knowledge_qa"
  }
}
```

## 控屏解析与白名单方案

控屏拆为两段:

1. Resolver: 把用户意图解析为候选 `action_id`。
2. Executor: 通过本地白名单执行已授权动作。

Resolver 可配置:

```yaml
screen_control:
  resolver: hybrid
  resolver_order: [local_rules, dora]
  local_rules:
    - action_id: SWITCH_HOME
      match_keywords: ["返回总览", "回到首页", "打开总览"]
    - action_id: SWITCH_TAB_ORG
      match_keywords: ["成品库存", "库存页面"]
  dora:
    require_json: true
    output_schema: screen_action_candidate
```

Executor 配置仍使用 `screen-actions.yaml`:

```yaml
actions:
  SWITCH_HOME:
    label: 总览
    type: page
    description: 切换到总览页
    fvs_function: gotoPage
    params:
      pageNumber: 1
    speak_text: 已为您切换到总览页面。
```

建议增强:

- `/api/screen/execute` 返回本次已授权的完整 action 配置。
- 前端只执行 `/api/screen/execute` 返回的授权 action, 不依赖前端缓存。
- 对 `params` 做 schema 校验, 例如 `pageNumber` 必须是正整数。
- Ops 日志记录 resolver provider、候选 action、最终执行 action 和拦截原因。

该增强是后续开放 action 配置写入的前置条件。否则配置页新增或修改 action 后, 前端仍可能执行旧缓存, 无法把“后端本次授权结果”作为唯一执行依据。

## Prompt 配置

Prompt 不再散落在代码或文档中, 统一进入 `config/prompts/`:

```text
config/prompts/
  knowledge-summarizer.md
  screen-resolver.md
  dora-direct-mode.md
  ask-metrics-dora.md
```

Prompt 配置原则:

- Prompt 文件可由配置页选择和编辑, 但需保存版本号、更新时间和操作者。
- Prompt 输出必须配套 schema。
- Prompt 中禁止要求模型生成可执行代码。
- Prompt 中应包含客户名称、项目名称、数据来源说明等变量占位, 由 Gateway 渲染。

示例变量:

```text
{{project.customer_name}}
{{project.project_name}}
{{project.assistant_name}}
{{knowledge.require_sources}}
{{screen.allowed_action_ids}}
```

## 前端配置页

建议新增 `/ops/config` 或 `/admin/config` 路由。短期可挂在 `/ops` 下, 长期如果要交付客户, 应加访问控制。

### API

阶段 1 只实现:

```text
GET  /api/config/effective
GET  /api/config/schema
```

阶段 5 才允许继续实现:

```text
POST /api/config/validate
PUT  /api/config/overrides
POST /api/config/test
POST /api/config/reload
GET  /api/config/audit
```

说明:

- `effective`: 返回脱敏后的当前生效配置。
- `schema`: 阶段 1 返回只读字段、枚举、说明、来源和风险等级; 阶段 5 才标注可编辑字段。
- `validate`: 保存前校验 YAML / JSON / Prompt / action_id。
- `overrides`: 写入运行时覆盖文件, 不直接改根目录默认配置。
- `test`: 用临时配置做 dry-run, 例如问数查询、知识库检索、控屏动作解析。
- `reload`: 热加载配置; 不可热加载项提示需要重启。
- `audit`: 查看配置修改记录。

`effective` 的实现规则:

- 必须由显式白名单构造 `ConfigSnapshot`, 不允许直接返回 `Settings.model_dump()` 后再过滤。
- 每个字段建议包含 `value`、`source`、`sensitive`、`editable_stage` 和 `notes`。
- `source` 可取 `code_default`、`root_config`、`customer_config`、`env`、`frontend_build`、`frontend_runtime`、`derived`。
- 当前 `Settings` 对象不保留字段来源。阶段 1 必须新增 `ConfigSourceTracker` / `ConfigSnapshotBuilder` 之类的显式来源构造逻辑, 或在配置加载时保留 provenance; 不能只凭最终值猜测精确来源。
- 若某字段在阶段 1 只能可靠判断为“合并后值”, 必须把 `source` 标为 `derived` 或 `unknown` 并在 `notes` 中说明限制, 不能误标为 `env` / `customer_config`。
- `sensitive=true` 的字段只返回是否已配置、来源和脱敏摘要, 不返回原值。
- 不返回 Dora / ASR / TTS / RAGFlow API Key、Token、数据库 DSN、密码、Bearer、`sk-*`、`ak-*` 或供应商完整原始响应。
- 问数、知识库、控屏 provider 先展示“当前实现状态”, 不能把尚未实现的 Database Provider、KnowledgeDirectAdapter 或本地 ScreenControlResolver 标成已启用。

阶段 1 推荐 `effective` 结构:

```json
{
  "project": {
    "project_id": {"value": "configurable-digital-human", "source": "code_default"},
    "project_name": {"value": "通用可配置数字人 POC", "source": "code_default"},
    "customer_id": {"value": "default", "source": "env"},
    "customer_name": {"value": "默认客户", "source": "code_default"},
    "scenario_name": {"value": "通用大屏交互", "source": "code_default"},
    "assistant_name": {"value": "小智", "source": "code_default"}
  },
  "capabilities": {
    "ask_metrics": {
      "mode": {"value": "excel", "source": "env"},
      "current_provider": "excel",
      "implemented_providers": ["excel", "dora", "auto"],
      "planned_providers": ["database"]
    },
    "knowledge": {
      "current_provider": "dora_ragflow_mcp",
      "implemented_providers": ["dora_ragflow_mcp"],
      "planned_providers": ["local_ragflow_llm"]
    },
    "screen_control": {
      "resolver": "dora_or_mock",
      "executor": "fvs_whitelist",
      "execute_returns_authorized_action": false
    }
  },
  "dashboard": {
    "backend_effective": {
      "integration_mode": {"value": "iframe", "source": "customer_config"},
      "url": {"value": "/webroot/decision/view/duchamp?...page_number=1", "source": "customer_config"}
    },
    "frontend_runtime": {
      "integration_mode": {"value": "iframe", "source": "frontend_build_or_url"},
      "url_source": "VITE_FVS_URL or URL query"
    }
  },
  "secrets": {
    "dora_api_key": {"configured": true, "source": "env", "sensitive": true},
    "asr_api_key": {"configured": true, "source": "env", "sensitive": true},
    "tts_api_key": {"configured": true, "source": "env", "sensitive": true}
  }
}
```

FVS 配置展示规则:

- 后端 API 只能准确展示后端 effective FVS 配置。
- 前端配置页必须同时读取浏览器当前 `getFvsConfig()` 结果, 展示 `frontend_runtime`。
- 当后端配置和前端 runtime 不一致时, 页面应明确提示“当前浏览器实际执行以后端以外的前端运行时配置为准”。

当前 Docker Compose 将 `./config:/app/config:ro` 只读挂载, 因此前端配置页不应直接改默认 YAML。建议新增可写目录:

```text
data/config-overrides/
  active.yaml
  history/
```

优先级:

1. 代码默认值和根目录配置。
2. 客户目录配置。
3. `data/config-overrides/active.yaml`。
4. `.env` / 环境变量显式覆盖。

### 可编辑项

以下仅为阶段 5 可写配置范围。阶段 1 配置页只能只读展示, 不能保存、reload 或 dry-run。

阶段 5 允许前端配置:

- 项目名称、产品名称、客户名称、场景名称、助手名称。
- 看板地址、FVS 集成模式、同源代理提示信息。
- 问数 Provider、fallback 顺序、Excel 文件 / sheet 映射、数据库表别名和字段别名。
- 知识库 Provider、RAGFlow dataset、检索参数、summarizer prompt profile。
- 控屏 resolver 顺序、本地关键词规则、白名单 action 的 label / pageNumber / speak_text。
- 演示问题集、欢迎语、等待提示语、fallback 文案。
- Prompt profile 和非敏感 Prompt 文件内容。

所有阶段都禁止前端配置:

- Dora API Key。
- ASR / TTS API Key。
- 数据库密码 / DSN 明文。
- RAGFlow MCP host API Key。
- 任意可执行脚本。
- 未经白名单声明的 FVS 函数执行入口。

## 项目和客户信息可配置化

现有代码和文档中存在固定客户和场景名称, 后续应统一通过 `project` 配置注入:

```yaml
project:
  project_id: configurable-digital-human
  project_name: 通用可配置数字人 POC
  product_name: 可配置大屏对话数字人
  customer_id: default
  customer_name: 默认客户
  customer_short_name: 默认客户
  scenario_name: 通用大屏交互
  assistant_name: 小智
  wake_words_profile: default
```

中天证券实例可在 `config/customers/zt-securities/runtime.yaml` 中覆盖为:

```yaml
project:
  project_id: zt-digital-human
  project_name: 中天证券党建大屏数字人 POC
  product_name: 党建大屏对话数字人
  customer_name: 中天证券
  scenario_name: 党建大屏
  assistant_name: 小天
```

替换范围:

- Docker Compose 默认 `APP_NAME`、`CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR`、镜像名和容器名。
- 根级 `config/wake-words.yaml`、`config/demo-cases.yaml`、`config/ask-metrics.yaml`。
- 前端 Mock 大屏中的指标标签、默认输入文本和 fallback demo questions。
- 前端页面标题、Ops 看板标题、演示稳态标识。
- Demo questions 和 smoke 脚本展示文案。
- Dora Prompt 和 summarizer Prompt 变量。
- 交付文档模板中的客户名称和项目名称。
- 看板地址、页面映射和 action 文案。

不建议替换:

- 历史 DEV_LOG / CHANGELOG 中已经发生的事实记录。
- 已交付 V1.0 包中的历史验收材料, 除非重新生成新客户交付包。

阶段 0A 通用化规则:

- 根级默认模板可以保留“示例”能力, 但示例必须是通用业务场景, 不能直接使用中天证券、党建大屏、张书记、党员学习、主题党日等客户实例词。
- 中天证券 / 党建内容只允许出现在:
  - `config/customers/zt-securities/`
  - `docs/customers/zt-securities/`
  - `docs/delivery/` 中已经交付的历史材料
  - `docs/DEV_LOG.md`、`docs/CHANGELOG.md`、历史风险记录等事实日志
  - `logs/`、`outputs/` 中明确标注为历史或客户交付输出的文件
  - `config/customers/<customer-id>/ask-metrics.yaml` 等明确客户 profile
- `.env.example` 允许保留中天证券 profile 的注释示例, 但默认值必须保持通用 profile。
- 后续新增客户时, 只能新增 `config/customers/<customer-id>/` 和 `docs/customers/<customer-id>/`, 不应修改核心代码或根级默认模板。

## 审计与可解释性

每次回答和控屏建议记录能力审计信息:

```json
{
  "capability": "knowledge",
  "provider": "local_ragflow_llm",
  "fallback_from": null,
  "prompt_profile": "customer_knowledge_qa",
  "sources": ["join_party_process.md"],
  "action_id": null,
  "data_source": "ragflow:zt_party_building_demo"
}
```

问数记录:

```json
{
  "capability": "ask_metrics",
  "provider": "database",
  "metric_id": "study_completion_rate",
  "data_source": "party_metrics_readonly.study_dashboard",
  "fields": ["total_members", "completed_members", "completion_rate"]
}
```

控屏记录:

```json
{
  "capability": "screen_control",
  "resolver": "local_rules",
  "candidate_action_id": "SWITCH_HOME",
  "executor": "fvs_whitelist",
  "executed": true
}
```

Ops 看板应展示脱敏后的 provider、fallback、来源和执行状态, 便于现场解释“这条回答到底来自 Dora、本地 Excel、数据库还是知识库直连”。

## 实施路线

### 阶段 0A: 主线默认入口和根模板清洁

目标: 让主线默认启动和根级模板具备可复用的通用默认形态, 不继承临时宣传链路, 也不把中天证券客户实例当成默认 profile。

工作项:

- 保持临时宣传分支删除状态。
- 确认 `apps/`、根级 `config/` 无录屏页面、专用数字人组件、临时客户配置和临时白名单动作。
- 修正 Docker Compose 默认值: 默认 `CUSTOMER_ID` / `CUSTOMER_CONFIG_DIR` 使用通用 profile, 镜像名和容器名不再使用 `zt-digital-human-*`。
- 修正包名: `apps/api/pyproject.toml` 和 `apps/web/package.json` 不再使用 `zt-digital-human-*`。
- 修正根级默认模板: `config/wake-words.yaml`、`config/demo-cases.yaml`、`config/ask-metrics.yaml` 和前端 Mock 大屏不再使用中天证券 / 党建大屏 / 张书记 / 党员 / 主题党日等客户实例词。
- 保留 `config/customers/zt-securities/` 作为客户实例配置, 不删除客户 profile。
- 阶段 2 已移除临时遗留 allowlist: `apps/api/app/services/ask_metrics.py` 不再包含客户实例词; 客户问数定义只应位于客户 profile。
- 标记或清理非主线输出目录, 例如手工图稿、录屏草稿或临时报告输出; 如需保留, 必须在文档中说明“不作为主线方案输入”。
- 文档索引只保留主线架构、配置中心方案和 ADR-0022 / ADR-0023。
- `NEXT_ACTIONS` 明确下一轮只推进主线配置能力, 不引入录屏、宣传、财务驾驶舱临时动作或专用素材。

验收:

- `git branch --list` 不再出现临时宣传分支。
- `rg` 搜索运行目录时, `apps/`、根级 `config/` 不再命中已清理的临时录屏入口、临时客户目录或临时动作白名单。
- `rg` 搜索 `apps/`、根级 `config/` 和 `docker-compose.yml` 时, 不再命中中天证券 / 党建大屏 / 张书记 / 财务录屏 / demo-video / Avatar2D / FINANCE 等客户实例或临时演示词; 客户实例词只能位于客户 profile、客户文档或历史记录。
- `config/ask-metrics.yaml` 不再引用 `zt_party_*.xlsx`; 中天证券 Excel 问数映射只保留在客户 profile 或客户交付资料中。
- `rg` 搜索 `apps/`、根级 `config/` 和 `docker-compose.yml` 时, 允许出现通用产品标识 `configurable-digital-human`, 不允许默认启动自动进入 `zt-securities`。
- `git status --short` 中未跟踪输出目录要么清理, 要么记录为明确的历史 / 手工输出, 不作为阶段 1 输入。
- `corepack.cmd pnpm --dir apps/web build`、`python -m compileall apps/api/app` 和 `git diff --check` 通过。

### 阶段 1: 配置模型与只读配置页

状态: 2026-06-15 已完成。已新增只读脱敏 `GET /api/config/effective`、`GET /api/config/schema` 和 `/ops/config` 页面; 页面不含保存、reload、action 编辑或写入入口。

目标: 建立脱敏、只读、可解释的配置观测能力, 不改变当前业务行为。

工作项:

- 新增通用 `project.yaml` / `capabilities.yaml` 样例, 客户实例示例放在 `config/customers/<customer-id>/`。
- 新增 `GET /api/config/effective`, 使用白名单构造 `ConfigSnapshot`, 不直接 dump `Settings`。
- 新增字段来源构造逻辑: 要么在配置加载时记录 provenance, 要么由 `ConfigSnapshotBuilder` 按代码默认值、根配置、客户配置、环境变量、前端运行时显式计算; 对无法精确判断的字段标 `source=derived|unknown`。
- 新增 `GET /api/config/schema`, 阶段 1 只描述字段含义、来源、风险等级和后续可编辑阶段, 不返回保存接口。
- 前端新增只读配置页入口, 可挂在 `/ops/config`。
- 页面展示项目、客户、场景、助手、看板、问数、知识库、控屏 provider、Mock 开关、Prompt profile 和配置来源。
- 页面同时展示后端 effective FVS 配置和当前浏览器前端 runtime FVS 配置。
- Ops 中展示当前问数、知识库、控屏 provider 和“planned / not implemented” 状态。
- 不实现 `PUT /api/config/overrides`、`POST /api/config/validate`、`POST /api/config/test`、`POST /api/config/reload` 或 `GET /api/config/audit`。

验收:

- 页面能看到项目名称、客户名称、场景名称、助手名称、看板地址、三类能力 provider 和配置来源。
- `effective` 的字段来源不得凭最终值硬猜; 无法精确判定来源时必须标注为 `derived` / `unknown` 并附说明。
- API 不返回 API Key、Token、密码、DSN、Bearer、`sk-*`、`ak-*` 或供应商完整原始响应。
- `effective` 中明确标注当前知识库仍是 `dora_ragflow_mcp`, `KnowledgeDirectAdapter` 未实现。
- `effective` 中明确标注当前问数 `excel|dora|auto` 来自 `ASK_METRICS_MODE`, Database Provider 未实现。
- `effective` 中明确标注 `/api/screen/execute` 尚未返回完整授权 action, action 写入不可用。
- 前端配置页无保存按钮、无 reload 按钮、无 action 编辑入口。
- 不改变 `/api/chat`、`/api/chat/stream`、`/api/tts/stream`、`/api/screen/execute` 的既有行为。

### 阶段 2: 问数 Provider 抽象与 Excel 迁移

状态: 2026-06-15 已完成。阶段 2 只完成 Provider 抽象和 Excel 问数迁移, 未实现真实数据库问数。

- 已抽象 `AskMetricsProvider`, 将当前 Excel 问数从 `AskMetricsService` 的客户实例硬编码中拆出。
- 已新增配置驱动 `ExcelAskMetricsProvider`, 按客户 `ask-metrics.yaml` 中的 metric 定义读取 workbook、sheet、字段、模板和来源。
- 已保留 `ASK_METRICS_MODE=excel|dora|auto`: `excel` 本地优先, `dora` 不让 Excel 抢答, `auto` 只在 Dora / Mock Dora fallback 时回退 Excel。
- 根级 `config/ask-metrics.yaml` 保持通用空 metric 模板; 客户 Excel 问数规则位于客户 profile。
- 已移除阶段 0A 为 `apps/api/app/services/ask_metrics.py` 设置的客户实例词 allowlist; 运行代码不再把客户指标作为通用默认逻辑。
- Database Provider 仅保留 `not_implemented` 状态和后续边界说明; 未连接数据库、未执行 SQL、未让 LLM 生成 SQL。

验收:

- 阶段 2 开始前已建立 11 个固定问数 smoke 基线。
- 迁移后 11 个固定问数 smoke 继续通过, 回答仍包含 Excel 来源和口径说明。
- `dora` 模式不返回 Excel 来源, `auto` 模式在 Dora / Mock Dora fallback 时回退 Excel。
- `/api/config/effective` 和 `/api/config/schema` 明确 Provider 接口 / Excel Provider 已实现, Database Provider 未实现。

### 阶段 3: KnowledgeDirectAdapter + LLM Summarizer

- 新增 RAGFlow Retriever。
- 新增受控 LLM Summarizer。
- 支持 `knowledge.mode=local_ragflow_llm|dora|auto`。
- 输出 `answer_with_sources`。

验收:

- 知识库问题可绕过 Dora, 由 Gateway 检索 + summarizer 回答。
- 回答包含来源。
- 无检索依据时返回 fallback, 不编造。

### 阶段 4: 控屏 resolver 与授权 action 增强

- 新增本地关键词 / 规则 resolver。
- Dora resolver 继续保留。
- `/api/screen/execute` 返回完整授权 action。
- 前端只执行本次授权 action。
- `ScreenExecuteResponse` 增加 `authorized_action`, 包含 `id`、`label`、`type`、`fvs_function`、`params`、`speak_text` 和 schema 校验结果。
- 前端 `applyFvsAction` 不再从 `GET /api/screen/actions` 缓存中取执行参数, 只使用 `authorized_action`。
- `GET /api/screen/actions` 可继续用于只读展示按钮, 但不能作为真实执行依据。
- action 可写配置、action dry-run 和 action reload 必须等本阶段完成后才能进入阶段 5。

验收:

- “返回总览”等固定控屏命令可不经 Dora 解析。
- 非白名单 action 仍被拦截。
- 修改或新增 action 后, 前端执行依据来自本次 `/api/screen/execute` 响应, 不会执行旧缓存 action。
- 本阶段完成后, 阶段 5 才允许配置页新增 action 并通过 dry-run 检查。

### 阶段 5: 可写配置页与审计

- 新增 `data/config-overrides/active.yaml`。
- 新增配置 validate / test / reload / audit API。
- 配置页支持修改非敏感配置。
- 加入配置修改审计。

验收:

- 用户可在前端修改项目名称、客户名称、看板地址、能力 provider、Prompt profile 和 action 映射。
- 保存前可校验, 保存后可 reload 或提示重启。
- 修改记录可追溯。

## 风险与控制

| 风险 | 控制 |
| --- | --- |
| 配置页泄露密钥 | 只允许非敏感配置; effective config 脱敏; 密钥只走环境变量 |
| `Settings` 全量返回导致泄密 | `effective` 必须白名单构造 `ConfigSnapshot`, 禁止直接 dump settings 后过滤 |
| 字段来源误标 | 阶段 1 必须新增 provenance 或显式来源构造; 无法精确判断时标 `derived` / `unknown` |
| 根模板继续被客户实例污染 | 阶段 0A 同时查临时宣传词和客户实例词; 默认模板必须保持通用 profile; 阶段 2 已移除 `AskMetricsService` 遗留词 |
| FVS 展示配置与浏览器实际执行不一致 | 配置页同时展示后端 effective 配置和前端 runtime 配置来源 |
| 在 Excel Provider 中继续堆数据库问数 | 阶段 2 只做 Provider 抽象和 Excel 迁移; Database Provider 真实查询必须另开阶段, 且只读表 / 字段白名单先行 |
| 数据库问数越权 | 只读账号; 表 / 字段白名单; 参数化查询; 超时和 limit |
| LLM summarizer 编造 | require_sources; no_evidence_policy=fallback; 输出 schema 校验 |
| 控屏误执行 | Resolver 只产 action_id; Executor 永远本地白名单; 二次 `/api/screen/execute` |
| action 可写早于授权 action 响应增强 | 阶段 4 前配置页不得写 action; 前端必须先切到执行本次授权 action |
| 配置改坏现场环境 | validate + dry-run + audit + 可回滚 history |
| 客户信息仍散落在历史文档 | 新功能和模板走 project 配置; 历史日志保留事实不改写 |

## 推荐下一步

阶段 0A 已完成: Docker Compose 默认 profile、包名、根级唤醒词 / demo cases / ask-metrics / 前端 Mock 大屏、README 和脚本默认 smoke 均已切为通用示例。

阶段 1 已完成: 已建立只读 effective config / schema 和 `/ops/config` 观测入口, 使用白名单构造和来源构造展示项目名称、客户信息、看板地址、三类能力 provider、Prompt profile、FVS 前后端配置来源和白名单现状, 并明确 Database Provider、KnowledgeDirectAdapter、可写 action 配置、LLM summarizer 和可写 Prompt 尚未实现。

阶段 2 已完成: 已抽象 `AskMetricsProvider`, 将当前 Excel 问数迁移到配置驱动 `ExcelAskMetricsProvider`, 并移除旧 `AskMetricsService` 客户实例 allowlist; Database Provider 仍未实现。

下一轮优先执行阶段 3: 若用户确认进入 KnowledgeDirectAdapter, 先做 RAGFlow 检索来源约束和 summarizer 输出 schema, 不得混入数据库问数、可写配置、Prompt 编辑或控屏授权响应增强。
