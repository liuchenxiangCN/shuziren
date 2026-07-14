# 开发日志

本文件记录每轮开发的事实结果。不要写愿望, 只写已经发生的变更、验证和遗留问题。

## 2026-07-06

### 汽车营销录屏 Mock 方案

#### Completed

- 将 `finance-dashboard` 当前录屏配置从财务驾驶舱 Mock 调整为汽车营销决策分析 Mock。
- FVS iframe 地址切换为汽车营销解决方案 / 公司经营总览页面; 当前录屏只使用 `page_number=1` 公司经营总览和 `page_number=2` 线索总览。
- 控屏白名单收敛为两个动作: `SWITCH_HOME` 和 `SWITCH_LEADS_OVERVIEW`; 前端执行仍必须走 `/api/screen/execute` 本次 `authorized_action`。
- Mock Dora 演示问题收敛为约 2 分钟脚本: 唤醒、领导欢迎、整体经营问答、切换线索总览、线索情况、销售线索制度知识库问答和销售行动建议。
- 新增首页批售指标 Mock 问答: 批售指标值 18,628、同比 1467.2%、环比 1.52%、当日 1,060、昨日 916、目标完成率 46.56%、年累计 162,633、累计完成率 134.48%。
- 基于 FVS 线索总览 page 2 截图新增门店线索对比 Mock 问答: A 店线索量排名第一, B 店大定承接突出, E/G 店转化率更优。
- 新增知识库类 Mock 回答《销售线索分级与跟进管理办法》, 回答包含 `display.sources`, 用于录屏展示“企业规章制度知识库问答”能力。
- 当前本地 `.env` 录屏环境切换为 `ASK_METRICS_MODE=dora`, 避免旧财务 Excel 问数抢答汽车营销问题; `DEMO_STABLE_MODE` 保持开启。
- 本轮未接入真实 Dora / RAGFlow / Database Provider, 未执行自由 SQL, 未新增模型生成代码或任意 FVS 函数写入能力。

#### Changed Files

- `config/customers/finance-dashboard/demo-cases.yaml`
- `config/customers/finance-dashboard/screen-actions.yaml`
- `config/customers/finance-dashboard/runtime.yaml`
- `config/customers/finance-dashboard/fvs.yaml`
- `config/customers/finance-dashboard/dora.yaml`
- `config/customers/finance-dashboard/README.md`

#### Verification

- `docker compose --project-directory /home/liufeng/code/shuziren up -d --build api web` 通过。
- `GET /api/demo/config` 返回 `project_name=汽车营销决策分析数字人 POC`, `ask_metrics_mode=dora`, 并返回 9 条汽车营销录屏演示题。
- 新 FVS 同源代理 URL 经 `http://localhost:18000/webroot/...` 返回 HTTP 200。
- `/api/chat` 验证通过: `我是李总`、`当前整体经营情况怎么样？`、`批售指标怎么样？`、`切换到线索总览`、`今天线索情况怎么样？`、`线索页面门店对比怎么样？`、`公司对高意向线索跟进有什么要求？`、`今天销售团队优先做什么？` 均命中新 Mock。
- `线索页面门店对比怎么样？` 返回 answer, 未再被切页关键词误匹配为 screen_control; `切换到线索总览` 仍返回 `SWITCH_LEADS_OVERVIEW`。
- `/api/chat` 的制度问题返回 `title=销售线索分级与跟进管理办法` 且包含 `display.sources`。
- `/api/screen/execute` 执行 `SWITCH_LEADS_OVERVIEW` 成功, 本次授权 `fvs_routing.page_number=2`。
- `/api/ops/dependencies` 显示 SQLite、动作白名单、Mock Dora、真实 ASR/TTS 配置和 Mock FVS 正常; RAGFlow 仍不可达, 但当前录屏 Mock 方案不依赖 RAGFlow。

## 2026-06-16

### 上线前风险处理、完整 smoke、安全负测与核心回归

#### Completed

- 本地 `.env` 已配置 `CONFIG_ADMIN_TOKEN`（未输出明文）, 写配置接口在当前运行态要求 `X-Config-Admin-Token`; 无 token、错误 token、非本机 Host / Origin 写入均返回 403。
- Docker Compose 默认端口已收敛到 `127.0.0.1`, 避免 `/ops`、`/ops/config`、API 和 Web 默认裸露到外网接口; 正式跨机器访问仍需反向代理鉴权或网关 ACL。
- Docker Compose 已透出后端 RAGFlow / Knowledge / FVS 运行参数, 并将 AskMetrics / Knowledge / DemoStable 等可写运行态字段的空默认交由后端默认值 / 客户配置 / runtime override 处理; `Settings` 已启用 `env_ignore_empty=True`。
- 修复阶段 5 runtime override 被 compose 默认 `ASK_METRICS_MODE=excel` 遮蔽的问题; 复测 `ASK_METRICS_MODE=dora` 不再返回 Excel source。
- 配置安全校验补充拒绝 `python -c` / `python3 -c` / `python.exe` 可执行文本。
- 完成无害 runtime override 的 validate / dry-run / save / reload / effective / audit / rollback 验证; 最终 `data/config-overrides/active.yaml` 已回滚为空覆盖, `ask_metrics.mode` 来源恢复为 `customer_config`。
- 完成 17 项配置安全负测: API Key、Token、password、Bearer、DSN、RAGFlow MCP Key、URL secret query、自由 SQL、`mode=database`、`query` / `sql` 字段、数据库配置、脚本、shell、Python、JavaScript、任意 FVS function 均被拒绝。
- 完成控屏安全负测: 非白名单 action、未知 target、URL / script 参数、嵌套 params、`pageNumber` 参数值覆盖均被 `/api/screen/execute` 拒绝; 合法 action 返回本次 `authorized_action`。
- 完成 11 个固定 Excel 问数 smoke; 完成 `ASK_METRICS_MODE=excel|dora|auto` 路由回归; `dora` / `auto` 均未返回 Excel source。
- 默认 `KNOWLEDGE_MODE=dora` 下, 固定知识问题“入党流程是什么?”通过 Dora 路径返回 `answer`; 本轮未启用 `local_ragflow_llm` / `auto`, 因客户 RAGFlow 资料的检索命中、来源质量、fallback 和延迟仍未现场复验。
- 归档 Ops 导出、config audit、effective/schema、浏览器截图 / CDP 控制台结果、日志包和最终风险摘要到 `logs/prelaunch-20260616-161620/`; 另生成 `logs/exports/zt-poc-logs-20260616-205839.zip`。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/services/config_overrides.py`
- `docker-compose.yml`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack.cmd pnpm --dir apps/web build` 通过。
- `git diff --check` 通过。
- `scripts/start-poc.ps1 -Build -SkipCheck` 通过; API / Web 容器启动成功。
- `scripts/check-poc.ps1 -RequireServices -Json` 已归档, exit code 为 1: Docker、端口、API、Web、配置、SQLite、screen actions、ASR / TTS 配置和 Mock FVS 正常; Ops aggregate 为 error, Dora 探测超时, RAGFlow 探测失败, 外部 RAGFlow healthz 无法连接。
- 归档脚本 `regression-security.json` 共 54 项断言, failures=0。
- 浏览器 / CDP 验证: `/ops` 无应用 console error; `/ops/config` 可渲染配置页, 仅有 Chrome 对 token/password 输入框的建议级提示; `/` 首页 iframe 当前返回 `/webroot/...` 502 Bad Gateway, 说明正式 FVS / 本机 FVS 代理未就绪。
- `/api/config/effective`、`/api/config/schema`、`/api/ops/export` 和 `apps/web/dist` 未发现本地实际 secret 值; `.env` 仍为 ignored 且 untracked。

#### Remaining Risks

- 无法在本机替用户完成供应商控制台 API Key 轮换; 本轮仅验证 `.env` 不入 Git, 前端 bundle / Ops 导出 / config API 不返回本地明文 secret。上线前仍需在百炼 / RAGFlow / 其他供应商控制台轮换曾出现在对话上下文中的 Key。
- 客户网络下 Dora、RAGFlow MCP、ASR、TTS、正式 FVS、麦克风权限和浏览器自动播放仍需现场复测; 本机 `check-poc -RequireServices` 已明确记录 Dora 超时和 RAGFlow 不可达。
- 当前正式 FVS iframe 策略未通过本机 smoke: `/webroot/...` 返回 502; 需恢复本机 FVS、接入客户 FVS 同源代理, 或由 FVS 侧放开嵌入策略后复测。
- ASR 本轮只验证当前真实模式在无音频时返回结构化错误; 未进行真实浏览器麦克风、连续追问、播报中长唤醒词打断、等待提示音和 AI 结果打断等待提示音人工复测。

### 上线前风险处理与全链路 E2E 验证任务包文档化

#### Completed

- 将下一轮新对话目标固定为“上线前风险处理 + 完整启动 smoke + 安全负测 + 核心业务回归 + 全链路 E2E 验证”。
- `docs/NEXT_ACTIONS.md` 已补充执行顺序、完成标准、硬边界和可复制的新对话提示词。
- `docs/13_RISKS_AND_TODO.md` 已新增 R-039, 并补充上线前风险处理与 E2E 验证任务包。
- `docs/CODEX_CONTEXT.md` 已更新当前阶段和 Latest Update, 方便新对话恢复。
- 本轮仅更新文档, 未实现 Database Provider、外部 LLM summarizer、Prompt 内容编辑、自由 SQL 或模型生成代码执行。

#### Changed Files

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/DEV_LOG.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`

#### Verification

- `git diff --check` 通过。

### 通用可配置数字人阶段 5 可写配置页与审计

#### Completed

- 新增 `data/config-overrides/` 运行时覆盖层; Git 只跟踪 `.gitkeep` 和 README, `active.yaml`、`history/`、`audit.jsonl` 作为本地运行数据忽略。
- 新增 `ConfigOverrideService`, 支持读取 / 保存 `active.yaml`、保存历史版本、追加 JSONL 审计和计算覆盖摘要。
- `Settings` 已接入覆盖层, 优先级为默认 / 根配置 -> 客户 profile -> `data/config-overrides/active.yaml` -> `.env` / 环境变量; 环境变量仍最高优先级。
- 新增阶段 5 配置 API: `GET /api/config/overrides`、`POST /api/config/validate`、`POST /api/config/test`、`PUT /api/config/overrides`、`POST /api/config/reload`、`GET /api/config/audit`。
- 写接口加入最小访问边界: 配置 `CONFIG_ADMIN_TOKEN` 时要求 `X-Config-Admin-Token`; 未配置 token 时仅允许 localhost / testserver origin 的本地 POC 写入。
- 配置保存只允许非敏感字段: 项目 / 客户展示字段、后端 FVS effective 非敏感字段、`ASK_METRICS_MODE=excel|dora|auto`、知识库 mode 与受控检索数值参数、source-bound summarizer profile 标签、`demo_stable_mode`、`gotoPage/pageNumber` action 映射。
- action 覆盖保存前复用 `ScreenActionService` 和阶段 4 params allowlist 做 dry-run; 前端真实执行仍只使用 `/api/screen/execute` 本次返回的 `authorized_action` / `resolved_action`。
- 前端 `/ops/config` 新增受控编辑面板、validate、dry-run、保存覆盖、reload、审计列表和 operator / reason / admin token 输入; admin token 只在本次浏览器内存中使用。
- `/api/config/effective` / `/api/config/schema` 已同步 `runtime_override` 来源、阶段 5 enabled endpoints、写入范围和仍然 blocked 的密钥 / SQL / 脚本 / 外部 LLM / Database Provider 边界。
- 新增 ADR-0025 记录 runtime config overrides、访问边界和审计决策。
- 本轮未实现 Database Provider 真实查询、自由 SQL、模型生成 SQL/Python/JavaScript/shell、外部 LLM summarizer、Prompt 内容编辑或任意 FVS 函数写入。

#### Changed Files

- `.gitignore`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/config_overrides.py`
- `apps/api/app/services/config_snapshot.py`
- `apps/api/app/services/screen_actions.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `data/config-overrides/.gitkeep`
- `data/config-overrides/README.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`
- `docs/decisions/ADR-0025-runtime-config-overrides-and-audit.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack.cmd pnpm --dir apps/web build` 通过。
- uv + FastAPI TestClient 阶段 5 smoke 通过: `/api/config/schema` 返回阶段 5 enabled endpoints; `/api/config/effective` 标注 writable config implemented 且 Database Provider 仍 `not_implemented`; validate / dry-run 对合法覆盖返回 ok; save 写入隔离测试覆盖目录; reload 后新增 action 可由 `/api/screen/actions` 读取并由 `/api/screen/execute` 返回授权 action; API Key 样式字段被 `SENSITIVE_FIELD_BLOCKED` 拒绝; database/free SQL payload 被拒绝; `/api/config/audit` 返回审计事件。
- TestClient 使用 `CONFIG_OVERRIDES_DIR=data/config-overrides-test` 隔离运行, 验证后已清理该测试目录。
- `git diff --check` 通过。

#### Notes

- `CONFIG_ADMIN_TOKEN` 不返回前端明文, `/api/config/effective` 只显示 configured/source/masked。
- 正式跨机器部署仍应配置 `CONFIG_ADMIN_TOKEN` 或在反向代理层加访问控制; 默认 local-origin 写入仅面向本地 POC。

### 通用可配置数字人阶段 4 控屏 resolver 与授权 action 响应增强

#### Completed

- 新增 `ScreenControlResolver`, 本地规则只根据当前白名单 action 的 label / description 解析候选 `action_id`, 固定控屏命令可不经 Dora 先命中本地 resolver。
- Dora / Mock Dora resolver 继续保留; 未命中本地规则时仍走既有归一化路径。
- `/api/screen/execute` 在保留 `success`、`action_id`、`speak_text`、`request_id`、`error` 兼容字段的同时, 返回本次 `authorized_action` / `resolved_action`。
- `authorized_action` 包含 `action_id`、`target`、`provider`、`fvs_function`、`fvs_routing`、净化后的 `params`、`speak_text` 和 validation 结果。
- `ScreenActionService.execute()` 已成为 action_id、target 和 params 的唯一授权出口; 非白名单 action、未知 target、未声明 params、参数值覆盖、URL / 脚本 / 命令类参数和嵌套参数均安全拒绝。
- 前端 `applyFvsAction()` 已改为只使用 `/api/screen/execute` 本次响应中的 `authorized_action` / `resolved_action`; `GET /api/screen/actions` 仅继续用于只读按钮展示。
- 前端 FVS Adapter 优先使用授权动作中的 `fvs_routing` 执行 iframe `page_number` 路由, 再兼容净化后的 `params.pageNumber`。
- `/api/config/effective` 和 `/api/config/schema` 同步标注 ScreenControlResolver、授权 action 响应和 params allowlist 已实现; 可写 action 配置仍为未实现。
- 本轮未实现可写配置、Prompt 编辑、可写 Prompt、可写 action 配置、配置 validate/test/reload/audit、Database Provider 真实查询、SQL 执行、外部 LLM summarizer 或 KnowledgeDirect 扩展。

#### Changed Files

- `apps/api/app/models.py`
- `apps/api/app/main.py`
- `apps/api/app/services/screen_actions.py`
- `apps/api/app/services/screen_resolver.py`
- `apps/api/app/services/config_snapshot.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/fvsAdapter.ts`
- `apps/web/src/types.ts`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`

#### Verification

- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- uv + FastAPI TestClient 阶段 4 smoke 通过 85 项: `/api/screen/execute` 合法 action 返回 `authorized_action`; 非法 action_id、非法 params、参数值覆盖和未知 target 均拒绝且不返回授权 action; `/api/config/effective`、`/api/config/schema` 返回阶段 4 状态; `/api/chat` 本地 resolver 命中 `SWITCH_HOME`; 11 个固定问数 smoke 11/11 通过并保留来源; `/api/chat/stream` 返回 `answer` / `end`; KnowledgeDirect source-bound summarizer 命中和无来源 fallback 行为通过。
- 静态搜索通过: 后端没有新增配置写入路由; 前端没有新增配置写入调用; 未发现 `Settings.model_dump()` 直接作为配置响应输出; 未发现新增明文 secret 输出、动态代码执行、子进程调用或 SQL 执行路径。
- `git diff --check` 通过。

#### Notes

- 阶段 5 可以另开, 但必须先设计 `data/config-overrides/`、validate / dry-run / audit 和访问控制边界; 不得把密钥、任意脚本、自由 SQL 或模型生成代码执行能力放入配置页。

### 通用可配置数字人阶段 3 KnowledgeDirectAdapter + 来源约束回答

#### Completed

- 新增 `KnowledgeDirectProvider`、`RagflowKnowledgeRetriever`、`SourceBoundSummarizer` 和 `KnowledgeService`。
- 默认 `KNOWLEDGE_MODE=dora`, 保持既有 Dora -> RAGFlow MCP -> Dora 最终回答路径不退化。
- 支持 `KNOWLEDGE_MODE=local_ragflow_llm|auto`: 本地直连只调用 RAGFlow 检索 chunks/metadata, 固定 `keyword=false`, 不使用 RAGFlow chat / assistant 生成最终回答。
- 当前 summarizer 为后端受控 `source_bound_extractive`, 不调用外部 LLM; 只从检索 chunk 中抽取来源句子组织回答。
- KnowledgeDirect 命中时返回标准 `answer`, `display.sources`、`display.source_summary` 和 `display.audit` 包含来源与审计信息。
- 检索无结果或依据不足时返回 `fallback`, `error.code=KNOWLEDGE_NO_SOURCES|KNOWLEDGE_NO_EVIDENCE`, 不转交模型编造。
- `auto` 模式下, 本地直连配置缺失或检索异常会回到 Dora; 但本地检索无依据仍 fallback。
- `/api/chat` 和 `/api/chat/stream` 保持既有响应类型和事件结构; 问数 `ASK_METRICS_MODE=excel|dora|auto` 路由语义保持不变。
- `/api/config/effective` 和 `/api/config/schema` 已同步 KnowledgeDirectAdapter / source-bound summarizer 状态, Database Provider、外部 LLM summarizer、可写 Prompt、可写配置和授权 action 响应增强仍为未实现。
- `config/customers/zt-securities/ragflow.yaml` 显式保持 `knowledge.mode=dora`, 避免客户 profile 默认绕过 Dora 知识库路径。
- 新增 ADR-0024 记录 KnowledgeDirect 来源约束回答边界。
- 本轮未实现 Database Provider 真实查询, 未执行 SQL, 未让 LLM 生成 SQL/Python/JavaScript/shell, 未实现 Prompt 编辑、可写 Prompt、可写 action 配置或可写配置中心, 未新增 `PUT /api/config/overrides`、`POST /api/config/validate`、`POST /api/config/test`、`POST /api/config/reload`、`GET /api/config/audit`, 未改变 `/api/screen/execute` 响应结构。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/config_snapshot.py`
- `apps/api/app/services/knowledge.py`
- `apps/api/app/services/knowledge_provider.py`
- `config/README.md`
- `config/customers/zt-securities/ragflow.yaml`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`
- `docs/decisions/ADR-0024-knowledge-direct-source-bound-summarizer.md`

#### Verification

- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- uv + FastAPI TestClient smoke 通过: `/api/config/effective`、`/api/config/schema`; 写配置接口仍 404; 11 个固定问数 smoke 11/11 通过; KnowledgeDirect 命中返回 `answer` 且包含 sources / source summary; KnowledgeDirect 无依据返回 fallback; `/api/chat/stream` 本地知识库路径返回 `metadata` 和最终 `answer`; `ASK_METRICS_MODE=dora` 不返回 Excel 来源且不走 KnowledgeDirect 本地 sources。
- 静态搜索通过: 后端仅存在 `GET /api/config/effective` 和 `GET /api/config/schema`; 前端只调用这两个只读接口; 未发现 `Settings.model_dump()` 直接输出; KnowledgeDirect 代码未发现 SQL / `eval` / `exec` / `subprocess` / 外部 LLM Provider 关键词; secret 命中仅为 `.env.example` 占位值、后端 provider 使用和配置快照脱敏逻辑。
- `git diff --check` 通过。

#### Notes

- 当前 source-bound summarizer 是 POC 阶段来源边界实现, 表达能力弱于外部 LLM 总结; 如后续接入 LLM summarizer, 必须继续走后端受控 Provider、schema 校验、require_sources 和 no_evidence_policy=fallback。
- 阶段 4 可以开始, 但只能推进控屏 resolver 与 `/api/screen/execute` 授权 action 响应增强; 阶段 5 可写配置、Prompt 编辑、配置 validate/test/reload/audit 仍不可开始。

## 2026-06-15

### 通用可配置数字人阶段 2 AskMetricsProvider 抽象与 Excel 问数迁移

#### Completed

- 按阶段 2 边界先建立当前客户 profile 下 11 个固定 Excel 问数 smoke 基线, 结果为 11/11 通过。
- 新增 `AskMetricsProvider` 抽象和 `MetricResult` / provider status 数据结构。
- 新增配置驱动 `ExcelAskMetricsProvider`, 只读读取配置声明的 workbook、sheet、metric 匹配规则、字段、模板、来源和 transform。
- 将 `apps/api/app/services/ask_metrics.py` 改为 provider 编排与 `ChatResponse` 包装, 不再包含客户实例关键词、字段名或 metric 模板。
- 将当前 Excel 问数能力迁移到 `config/customers/zt-securities/ask-metrics.yaml`, 客户关键词、字段、回答模板、来源说明和口径说明只保留在客户 profile 中。
- 根级 `config/ask-metrics.yaml` 保持通用空 metric 模板, 默认 profile 不再依赖客户 Excel 文件或客户词硬编码。
- `/api/config/effective` 和 `/api/config/schema` 同步标注 `AskMetricsProvider` / `ExcelAskMetricsProvider` 已实现, Database Provider 仍为 `not_implemented`。
- 保持 `ASK_METRICS_MODE=excel|dora|auto`: `excel` 本地优先, `dora` 不返回 Excel 来源, `auto` 在 Dora / Mock Dora fallback 时回退 Excel。
- Database Provider 本轮只保留 `not_implemented` 状态, 未连接数据库、未执行 SQL、未让 LLM 生成 SQL。
- 补齐 `SessionLogStore` 和 API 时间戳在 uv 精简 Python 缺少 `Asia/Shanghai` tzdata 时的 UTC+8 fallback, 避免 TestClient 日志写入失败。
- 本轮未实现 KnowledgeDirectAdapter、LLM summarizer、Prompt 编辑、可写 Prompt、可写 action 配置、可写配置中心、配置 validate/test/reload/audit, 未改变 `/api/screen/execute` 响应结构。

#### Changed Files

- `apps/api/app/main.py`
- `apps/api/app/services/ask_metrics.py`
- `apps/api/app/services/ask_metrics_provider.py`
- `apps/api/app/services/excel_ask_metrics_provider.py`
- `apps/api/app/services/config_snapshot.py`
- `apps/api/app/services/session_log.py`
- `config/ask-metrics.yaml`
- `config/customers/zt-securities/ask-metrics.yaml`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`

#### Verification

- 阶段 2 前基线: uv + FastAPI TestClient, `CUSTOMER_ID=zt-securities`、`ASK_METRICS_MODE=excel`, 11 个固定问数 smoke 11/11 通过。
- 迁移后: uv + FastAPI TestClient, 同一 11 个固定问数 smoke 11/11 通过。
- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- uv + FastAPI TestClient 阶段 2 关键路径通过: `/api/config/effective` 和 `/api/config/schema` 返回 200; 配置写接口仍为 404; `/api/chat/stream` Excel 问数返回 `metadata` 和 `answer`; `dora` 模式不返回 Excel 来源; `auto` 模式在 Mock Dora fallback 时回退 Excel; 默认通用 profile 不依赖客户硬编码。
- 验收搜索通过: `apps/`、根级 `config/`、`docker-compose.yml`、`README.md`、`scripts/` 不再命中客户实例或临时宣传词; `apps/api/app/services/ask_metrics.py` 无客户实例词。
- 静态搜索通过: 新增 Provider / 配置 API 代码未发现 `Settings.model_dump()` 直接输出、配置写接口路由、前端配置写 API 调用或明文 secret 输出。
- `git diff --check` 通过。

#### Notes

- 阶段 3 可以开始, 但仅限 KnowledgeDirectAdapter / 来源约束方向; 不得在同一 goal 混入数据库问数、可写配置、Prompt 编辑或控屏授权响应增强。
- 新增风险 R-036: 配置驱动问数定义目前依赖 smoke 覆盖, 未来新增客户 metric 前应在阶段 5 validate/test API 中补 ask-metrics dry-run。

### 通用可配置数字人阶段 1 只读 effective config 与 schema

#### Completed

- 新增脱敏只读 `GET /api/config/effective`, 通过 `ConfigSnapshot` 白名单构造项目、客户、场景、助手、看板、问数、知识库、控屏、Mock 开关、Prompt profile、敏感字段摘要和当前实现状态。
- 新增只读 `GET /api/config/schema`, 返回阶段 1 只读 schema、来源类型、分区说明和阶段 5 前禁用的写入 / validate / test / reload / audit 接口列表。
- 新增 `apps/api/app/services/config_snapshot.py`, 按环境变量、客户配置、根配置、代码默认和前端 runtime 契约显式构造字段来源; 对无法精确表示的聚合字段标 `derived` / `unknown`, 不直接返回 `Settings.model_dump()`。
- sensitive 字段只返回 `configured`、`source`、`masked` 和 `sensitive=true`; Dora / RAGFlow / ASR / TTS API Key 及数据库 DSN 不返回明文。
- `effective` 明确当前 `KnowledgeDirectAdapter`、Database Provider、可写 action 配置、配置写入、validate、test、reload、audit、LLM summarizer 和可写 Prompt 均未实现。
- 前端新增 `/ops/config` 只读配置页入口, 展示后端 effective config、schema 禁用接口、当前浏览器 FVS runtime 配置、Mock 开关、Prompt profile 和实现状态; 页面不包含保存、reload、action 编辑或写入入口。
- 本轮未修改 `/api/chat`、`/api/chat/stream`、`/api/tts/stream`、`/api/screen/execute` 的既有行为。

#### Changed Files

- `apps/api/app/models.py`
- `apps/api/app/main.py`
- `apps/api/app/services/config_snapshot.py`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`

#### Verification

- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `git diff --check` 通过。
- 使用 `C:\Users\nifen\.local\bin\uv.exe run python -` 完成 FastAPI TestClient 请求级 smoke: `/api/config/effective` 和 `/api/config/schema` 均返回 200; `PUT /api/config/overrides`、`POST /api/config/validate`、`POST /api/config/test`、`POST /api/config/reload`、`GET /api/config/audit` 均返回 404。
- 新增 API / 前端配置页代码静态搜索未发现 `Settings.model_dump()` 作为配置响应输出, 未发现写入配置 API 调用。
- `apps/`、根级 `config/`、`docker-compose.yml`、`README.md`、`scripts/` 的客户实例和临时宣传词搜索未发现本轮新增污染; 既有 `apps/api/app/services/ask_metrics.py` 仍作为阶段 2 前临时 allowlist。

#### Notes

- 本机已安装 `uv` 到 `C:\Users\nifen\.local\bin\uv.exe`, 当前 PowerShell PATH 尚未刷新; 本轮使用绝对路径完成请求级 smoke。第一次 smoke 发现 `ZoneInfo("Asia/Shanghai")` 在 uv 精简 Python 下缺少 `tzdata` 会失败, 已补充 UTC+8 fallback。
- 阶段 2 可以开始, 但边界是先抽象 `AskMetricsProvider` 并移除旧 `AskMetricsService` 客户实例 allowlist, 不得在旧服务内继续新增客户规则或直接接自由 SQL。

### 通用可配置数字人阶段 0A 默认入口和根模板清洁

#### Completed

- 将 `docker-compose.yml` 默认 `CUSTOMER_ID` 改为 `default`, `CUSTOMER_CONFIG_DIR` 改为空默认值, API / Web 镜像名和容器名改为 `configurable-digital-human-*`, 默认启动不再自动进入 `zt-securities` 客户 profile。
- 将 `apps/api/pyproject.toml`、`apps/api/uv.lock` 和 `apps/web/package.json` 的包名改为 `configurable-digital-human-*`。
- 将根级 `config/wake-words.yaml` 默认唤醒词从客户实例唤醒词切为通用“小智”示例; 前端 `DEFAULT_WAKE_CONFIG` 和 ASR 唤醒按钮同步为通用示例。
- 将根级 `config/demo-cases.yaml` 中的客户实例关键词替换为通用业务大屏示例, 保留成品库存、生产管理、设备分析和总览的通用 Mock 控屏路径。
- 将根级 `config/ask-metrics.yaml` 从客户 Excel 文件映射改为通用占位模板; 中天证券 Excel 问数映射仅保留在 `config/customers/zt-securities/ask-metrics.yaml`。
- 将前端 Mock 大屏默认指标从客户实例指标改为通用示例指标。
- 将 `README.md`、`scripts/poc-common.ps1`、`scripts/check-poc.ps1` 和 `scripts/smoke-demo.ps1` 的默认说明、默认 CustomerId 和默认 smoke 用例改为通用主线。
- 保留 `config/customers/zt-securities/` 作为客户实例配置目录, 未删除客户 profile。
- 明确 `apps/api/app/services/ask_metrics.py` 仍是阶段 2 前的临时遗留 allowlist, 本轮未在该文件继续新增客户规则。
- 清点未跟踪目录 `outputs/manual-20260614-212600/`: 当前内容为 `presentations/` 下的历史 / 手工输出, 保留但不作为阶段 1 配置模型、schema 或页面输入。

#### Changed Files

- `docker-compose.yml`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/web/package.json`
- `apps/web/src/App.vue`
- `config/wake-words.yaml`
- `config/demo-cases.yaml`
- `config/ask-metrics.yaml`
- `config/README.md`
- `README.md`
- `scripts/poc-common.ps1`
- `scripts/check-poc.ps1`
- `scripts/smoke-demo.ps1`
- `docs/13_RISKS_AND_TODO.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`

#### Verification

- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `git diff --check` 通过。
- `git branch --list` 仅显示 `main`, 未发现临时宣传分支。
- 对 `apps/`、`docker-compose.yml`、`README.md`、`scripts/` 执行客户实例和临时宣传词搜索, 仅 `apps/api/app/services/ask_metrics.py` 命中阶段 2 前临时遗留 allowlist。
- 对根级 `config/` 执行同类搜索并排除 `config/customers/**`, 无命中。
- `config/ask-metrics.yaml` 不再引用 `zt_party_*.xlsx`; 相关映射只保留在 `config/customers/zt-securities/ask-metrics.yaml`。
- `git status --short` 仍显示已有未提交变更和未跟踪 `outputs/manual-20260614-212600/`; 该输出目录已在文档中标注为历史 / 手工输出, 不作为阶段 1 输入。

#### Notes

- 本轮未新增 `/api/config/*`, 未做只读配置页, 未做可写配置, 未抽象 `AskMetricsProvider`, 未新增数据库问数、`KnowledgeDirectAdapter`、LLM summarizer 或 Prompt 编辑。
- 下一步可以进入阶段 1, 但阶段 1 必须先实现字段来源构造 / provenance 和脱敏白名单输出, 不能直接 dump `Settings` 或加入保存 / reload 能力。

### 配置中心方案二次审计修正

#### Completed

- 基于实际代码二次审计 `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`, 修正阶段 0A / 阶段 1 的不可达验收口径。
- 明确当前 `docker-compose.yml` 默认仍进入 `zt-securities`, 镜像 / 容器 / 包名仍有 `zt-digital-human-*`, 根级配置和前端 Mock 默认态仍有客户实例残留, 因此下一步应先执行阶段 0A 默认入口和根模板清洁。
- 明确 `apps/api/app/services/ask_metrics.py` 仍包含党建 Excel 问数硬编码; 在阶段 2 抽象 `AskMetricsProvider` 前, 该文件只能作为临时遗留 allowlist, 不能把 `apps/` 零客户词作为阶段 0A 的硬验收。
- 明确阶段 1 的 `effective.source` 不能从合并后的 `Settings` 直接可靠推出; 必须新增字段来源构造或 provenance 追踪, 无法精确判断时标 `derived` / `unknown`。
- 同步更新 ADR-0022 和 `NEXT_ACTIONS.md`, 将下一推荐 goal 调整为阶段 0A / 阶段 1, 并保留“不得新增可写配置、不改变现有业务行为”的边界。

#### Changed Files

- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- 已用 `rg` 对实际路由、`ScreenExecuteResponse`、前端 FVS 执行路径、Docker Compose 默认值、根级配置、`AskMetricsService` 和配置加载来源能力进行静态核对。
- 本轮仅修正文档, 未改前后端代码, 未运行构建。

#### Notes

- 下一轮如果实现阶段 0A, 应先改默认启动入口、根模板和前端 Mock 默认态; 不应在旧 `AskMetricsService` 里继续堆新客户规则。
- 下一轮如果实现阶段 1, 应先设计 `ConfigSnapshot` 和字段来源构造, 再开放只读 API / 页面。

### 通用可配置数字人项目定位调整

#### Completed

- 按用户要求将项目本体从“中天证券党建大屏数字人”调整为“通用可配置数字人”。
- 明确中天证券党建大屏只是客户实例, 通过 `config/customers/zt-securities/` 和客户文档 / 交付包实现。
- 后端 `Settings` 新增 `project_id`、`project_name`、`product_name`、`customer_name`、`scenario_name`、`assistant_name`, 并支持从客户 `runtime.yaml` 的 `project` 段覆盖。
- `/api/demo/config` 新增项目 / 客户展示字段, 供前端只读展示使用。
- 前端首页 eyebrow / H1 和 Ops 客户显示改为读取配置字段; 未加载配置时使用通用默认文案。
- 运维日志导出标题改为当前生效 `project_name`, 客户行改为 `customer_name (customer_id)`。
- 根目录默认配置和 `.env.example` 改为通用默认; 中天证券实例配置补充 `project` 元数据。
- 新增 ADR-0023 记录通用可配置数字人项目定位。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/web/src/App.vue`
- `apps/web/src/types.ts`
- `config/README.md`
- `config/demo-cases.yaml`
- `config/screen-actions.yaml`
- `config/customers/zt-securities/README.md`
- `config/customers/zt-securities/runtime.yaml`
- `docs/00_INDEX.md`
- `docs/01_PROJECT_BRIEF.md`
- `docs/02_PRODUCT_BLUEPRINT.md`
- `docs/03_ARCHITECTURE.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/14_ENHANCEMENT_ROADMAP.md`
- `docs/15_MAINLINE_ARCHITECTURE_DIAGRAM.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/integrations/FVS_INTEGRATION.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`
- `docs/decisions/ADR-0023-generic-configurable-digital-human-positioning.md`

#### Verification

- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `git diff --check` 通过。
- 对核心默认配置、运行代码和接口 / FVS 契约执行客户实例关键词搜索, 中天证券 / 党建大屏 / 张书记相关内容无命中; `.env.example` 仅保留中天证券客户 profile 的注释示例。

#### Notes

- 历史交付包、历史 DEV_LOG / CHANGELOG 和 `docs/customers/zt-securities/` 中的中天证券内容保留为历史事实或客户实例内容, 不批量改写。
- 下一轮阶段 0A 应先把默认启动入口和根模板不得写死客户实例固化为可重复检查; `AskMetricsService` 遗留硬编码等阶段 2 Provider 抽象后再移除。

### 主线清洁基线与配置中心方案修正

#### Completed

- 删除本地临时宣传分支, 当前本地分支只保留 `main`。
- 清理主线工作树中的临时录屏页面、专用数字人组件、专用资产、临时客户配置、财务录屏动作白名单和临时 ADR。
- 回退 `apps/web`、`config/screen-actions.yaml`、`config/customers/zt-securities/screen-actions.yaml` 和集成说明中属于临时录屏链路的改动。
- 保留并更新主线架构图、能力路由与配置中心方案和 ADR-0022。
- 将配置中心优化路线修正为: 阶段 0A 默认入口 / 根模板清洁门禁, 阶段 1 只读脱敏 effective config 和 schema, 后续再做数据库问数、知识库直连、控屏 resolver、可写配置和审计。
- 明确当前实际代码约束: 尚未实现 `/api/config/*`; `/api/screen/execute` 尚未返回完整授权 action; 前端仍依赖缓存动作列表执行 FVS; Compose 当前把 `config/` 只读挂载。

#### Changed Files

- `docs/00_INDEX.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/15_MAINLINE_ARCHITECTURE_DIAGRAM.md`
- `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0022-capability-routing-and-config-center.md`

#### Verification

- 临时宣传分支检查无输出。
- 对 `apps`、`config` 和 `docs` 执行临时录屏污染关键词搜索, 结果无命中。
- `corepack.cmd pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `git diff --check` 通过。

#### Notes

- 本轮未实现配置中心 API 或前端页面; 仅完成主线清洁、方案修正和文档同步。
- 下一轮如开始实现, 应先落地阶段 0A / 阶段 1, 不直接做可写配置或数据库 / 知识库直连。

## 2026-06-11

### 本地问数确认播报顺序修复

#### Completed

- 用户反馈询问党员学习完成率相关问题时, 语音没有播报“收到”, Dora Agent 后台也没有收到该条记录; 翻页和领导相关知识库查询无此问题。
- 确认默认 `ASK_METRICS_MODE=excel` 下, 党员学习完成率属于 Gateway 本地 Excel 问数 Adapter 命中项, 会在调用 Dora 前直接返回本地指标答案, 因此 Dora Agent 后台没有该记录属于当前设计行为。
- 修复前端语音命令自动播报顺序: `runMonitorCommand` 现在把确认播报 Promise 传给 `submitQuestion`, 自动播放最终回答前会先等待确认播报完成或最多等待 1800ms。
- 快速返回的本地 Excel 问数答案不再立即启动真流式 TTS 抢占“收到, 正在为您查找信息。”提示。
- 提示音播放队列新增失败容错, 单次提示播放失败不会让后续提示队列卡在 rejected Promise。
- 未改变问数路由策略; 如需 Dora Agent 后台也记录指标类问题, 需切换 `ASK_METRICS_MODE=dora` 或 `auto` 并接受指标固定回答策略变化。

#### Changed Files

- `apps/web/src/App.vue`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose up -d --build web` 成功, Compose 依赖同时重启 API / Web。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过。
- `GET /api/wake/config` 返回普通唤醒 `vad_threshold=0.018`, 播报中打断 `barge_in_enabled=true`。
- `POST /api/chat` 测试“当前党员学习完成率是多少?”返回本地指标答案, 来源为 `zt_party_study_metrics_2026.xlsx / Dashboard`。
- `GET /api/health` 返回 `status=ok`。
- `git diff --check` 通过。
- Codex Browser 刷新 `http://localhost:18000/`, 确认加载新 bundle `index-CQTUuisV.js`, DOM 渲染正常且控制台无 error。

#### Notes

- 该修复需要用户在真实麦克风环境刷新页面、重新开启后台监听后复测“当前党员学习完成率是多少?”。
- 若验收要求所有指标问题必须进入 Dora Agent 后台留痕, 下一步应先确认是否将问数模式切到 `dora` 或 `auto`, 并重新做 11 个固定问数 smoke。

### 普通唤醒不可用热修

#### Completed

- 用户反馈播报中打断能力上线后普通语音唤醒完全无法触发。
- 检查 API 日志发现仍有 `/api/asr/transcribe` 请求, 且多次返回 `ASR_EMPTY_RESULT`, 判断更像是普通唤醒 VAD 阈值过低导致环境 / 外放噪声先触发短片段, 真实唤醒词被 ASR / cooldown 窗口吃掉。
- 前端 VAD 新增连续两帧超过阈值才正式开始收音的启动确认, 避免单帧噪声尖峰触发唤醒片段。
- 普通唤醒 `vad_threshold` 从 0.014 回调到 0.018; 播报中 `barge_in_vad_threshold` 保持 0.018。
- 播报中长唤醒词确认打断能力保留。

#### Changed Files

- `apps/web/src/App.vue`
- `config/wake-words.yaml`
- `config/customers/zt-securities/wake-words.yaml`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose up -d --build api web` 成功。
- `GET /api/wake/config` 返回普通唤醒 `vad_threshold=0.018`, 播报中打断 `barge_in_vad_threshold=0.018`。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过。
- `git diff --check` 通过。
- Codex Browser 验证页面加载新前端 bundle `index-f8g4rF8T.js`, FVS iframe 和 compact 语音入口存在。

#### Notes

- 当前仍需用户真实麦克风复测普通唤醒是否恢复。若仍失败, 下一步需要记录 ASR 返回文本或临时开启可见唤醒调试提示, 判断是空识别、误识别还是命中词匹配问题。

### 客户汇报项目计划与甘特图

#### Completed

- 按用户确认的客户汇报口径生成项目管理计划和实施甘特图 Excel 工作簿。
- 工作簿路径: `outputs/customer-report-20260617/zt_project_plan_gantt_20260610_0630.xlsx`。
- 工作簿包含 `客户汇报摘要`、`实施计划`、`甘特图`、`里程碑与风险`、`工作日历` 和 `数据源` 6 个 sheet。
- 汇报口径使用 `2026-06-17` 作为阶段进展日期, 明确写为“截至 2026-06-17, 项目按计划完成 Mock 链路联调与端到端流程验证, 真实外部系统接入进入专项实施阶段”。
- 计划周期覆盖 `2026-06-10` 到 `2026-06-30`, 目标写为“完成测试验收并上线”。
- 已按用户指定将 `2026-06-13`、`2026-06-14`、`2026-06-19`、`2026-06-20`、`2026-06-21`、`2026-06-27`、`2026-06-28` 标为非工作日, 仅保留风险响应 / 问题跟进。
- 后续待完成专项在计划中明确列出: 自定义新闻爬虫及导入知识库、RAGFlow 知识库调用、性能优化、安全优化。
- 新增需求在计划中表述为: 前端根据用户指定人员发起请求, 后端按客户确认的新闻源白名单采集公开新闻, 清洗整理后保存到本地 RAGFlow 知识库, 并衔接后续 RAGFlow MCP 问答能力。

#### Changed Files

- `outputs/customer-report-20260617/zt_project_plan_gantt_20260610_0630.xlsx`
- `outputs/customer-report-20260617/build_customer_plan_gantt.mjs`
- `outputs/customer-report-20260617/preview_summary.png`
- `outputs/customer-report-20260617/preview_gantt.png`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- 已生成最终 Excel 工作簿。
- 已渲染并人工检查 `客户汇报摘要` 和 `甘特图` 预览图, 确认摘要、进度指标、每日投入图、任务甘特条、节假日置灰和进度百分比显示正常。
- 公式 / 错误标记扫描未命中 `#REF!`、`#DIV/0!`、`#VALUE!`、`#NAME?` 或 `#N/A`。

#### Notes

- 本轮为客户汇报计划材料输出, 未实现自定义新闻爬虫、RAGFlow 导入 API、RAGFlow 调用专项、性能优化或安全优化代码。
- 指定新闻网站暂未确认, 工作簿中采用“客户确认的新闻源白名单 / 可配置新闻源”口径。

### 播报中长唤醒词确认打断

#### Completed

- 新增播报中 `barge_in` 打断能力: 前端在 `speaking` 状态下继续通过 VAD 截取短音频片段, 但只用于长唤醒词确认, 不因任意人声直接打断。
- `GET /api/wake/config` 的 `settings` 新增 `barge_in_enabled`、`barge_in_wake_words`、`barge_in_vad_threshold`、`barge_in_min_audio_ms`、`barge_in_silence_ms`、`barge_in_max_audio_ms` 和 `barge_in_ignore_after_tts_start_ms`。
- 默认配置和中天证券客户配置启用 `barge_in_enabled=true`, 播报中打断词仅包含 `小天小天` 和 `你好小天`, 不包含短唤醒词 `小天`。
- 播报中 ASR 命中 `barge_in_wake_words` 后, 前端调用 `cleanupAudio()` 停止当前 TTS, 播放“您好。”并进入正式指令录音; 若同句包含指令, 剥离唤醒词后直接进入 `/api/chat`。
- 播报中 ASR 未命中、空识别或请求失败时静默忽略, 当前 TTS 继续播放, 不进入 cooldown, 不进入 `/api/chat`。
- 新增 ADR-0017, 记录只做长唤醒词确认打断、避免任意人声打断的决策。

#### Changed Files

- `apps/api/app/models.py`
- `apps/web/src/App.vue`
- `apps/web/src/types.ts`
- `config/wake-words.yaml`
- `config/customers/zt-securities/wake-words.yaml`
- `config/README.md`
- `docs/00_INDEX.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/decisions/ADR-0017-speaking-barge-in-with-long-wake-words.md`
- `docs/delivery/v1.0/03_USER_MANUAL.md`
- `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md`
- `docs/delivery/v1.0/06_TEST_REPORT.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `docker compose up -d --build api web` 成功重建并启动 API / Web。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过。
- `GET /api/wake/config` 返回 `barge_in_enabled=true`, `barge_in_wake_words` 为 2 条, `barge_in_vad_threshold=0.018`, `barge_in_min_audio_ms=900`, `barge_in_silence_ms=700`, `barge_in_max_audio_ms=3500`, `barge_in_ignore_after_tts_start_ms=700`。
- `GET http://localhost:18000` 返回 HTTP 200。
- Codex Browser 验证本地页面加载新前端 bundle `index-Mcwb3gfL.js`, FVS iframe 和 compact 语音入口存在。

#### Notes

- 当前打断仍依赖云 ASR 确认, 不是本地 KWS, 因此预计会有约 1-2 秒确认延迟。
- 尚未完成真实麦克风人工复测。建议现场测试播报中说“小天小天”“你好小天”“小天小天, 返回总览”是否能打断, 并测试普通闲聊和短词“小天”不会打断。

### 语音唤醒失败率现场调优

#### Completed

- 针对本地复测中语音唤醒失败率较高的问题, 检查 API 日志发现多次 `/api/asr/transcribe` 返回 `ASR_EMPTY_RESULT`, 说明前端送到 ASR 的唤醒片段存在过短、过弱或未完整包含唤醒词的情况。
- 前端 VAD 增加约 360ms 预录缓冲: 检测到人声后, 会把触发阈值前的一小段音频一起送入 ASR, 降低“小天小天”开头被截掉导致识别为空或只识别后半段的概率。
- 前端唤醒词匹配增加常见 ASR 同音偏差归一化: `晓` / `肖` 归一为 `小`, `田` / `甜` / `添` / `填` 归一为 `天`, 提升“小田小田”“小甜小甜”等识别结果的命中率; 匹配时按唤醒词长度优先, 剥离唤醒词时同样支持这些同音偏差, 避免短唤醒词抢占长唤醒词。
- 默认和中天证券客户唤醒配置同步调宽: 新增短唤醒词 `小天`, `min_audio_ms` 从 800 调整为 1000, `silence_ms` 从 700 调整为 1000, `max_audio_ms` 从 5000 调整为 6500, `cooldown_ms` 从 1500 调整为 800, `vad_threshold` 从 0.018 调整为 0.014。

#### Changed Files

- `apps/web/src/App.vue`
- `config/wake-words.yaml`
- `config/customers/zt-securities/wake-words.yaml`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- 本轮已确认 API 日志中存在多次 `ASR_EMPTY_RESULT`, 调优方向聚焦于改善前端 VAD 截段和唤醒词容错。

#### Notes

- 本轮尚未完成真实麦克风复测。调优后需重建 / 重启 API 和 Web, 再由用户在现场连续测试 10 次以上唤醒成功率。
- 新增短唤醒词 `小天` 会提高召回率, 也可能略微提高误唤醒概率; 若现场误唤醒明显增加, 可把 `vad_threshold` 回调到 0.016 或移除短唤醒词。

### V1.0 POC 验收交付包

#### Completed

- 新增 `docs/delivery/v1.0/` 正式交付包目录。
- 新增交付包索引 `docs/delivery/v1.0/README.md`, 说明交付范围、阅读顺序和关键安全边界。
- 新增验收报告 `docs/delivery/v1.0/01_ACCEPTANCE_REPORT.md`, 覆盖验收范围、结果、脚本复演记录、日志包、耗时、截图附件位、客户确认项和验收结论。
- 新增部署方案 `docs/delivery/v1.0/02_DEPLOYMENT_PLAN.md`, 覆盖 Windows + Docker Desktop + 本项目 API / Web + 独立 RAGFlow + Dora + ASR / TTS + FVS 的部署步骤和端口规划。
- 新增用户手册 `docs/delivery/v1.0/03_USER_MANUAL.md`, 覆盖唤醒、同句指令、连续追问、知识问答、问数、大屏切换、播报和兜底提示。
- 新增运维手册 `docs/delivery/v1.0/04_OPERATIONS_MANUAL.md`, 覆盖 `check-poc.ps1`、`start-poc.ps1`、`stop-poc.ps1`、`smoke-demo.ps1`、`export-logs.ps1`、Ops 看板和故障排查。
- 新增配置手册 `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md`, 覆盖 `.env`、客户私有配置目录、Mock 开关、`ASK_METRICS_MODE`、`DEMO_STABLE_MODE`、FVS URL、密钥边界和配置变更流程。
- 新增测试报告 `docs/delivery/v1.0/06_TEST_REPORT.md`, 汇总 V0.7 / V0.8 / V0.9 已验证项、最新 smoke / 日志包证据和客户现场待确认项。
- 新增客户移交清单 `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md`, 覆盖交付物、环境、密钥、操作、验收场景、风险和签收。
- `docs/00_INDEX.md` 增加 V1.0 验收交付包入口。
- `docs/NEXT_ACTIONS.md` 当前阶段改为 V1.0 已输出, 下一推荐 goal 改为客户现场验收复演、补齐截图、确认真实依赖并完成签字。

#### Changed Files

- `docs/delivery/v1.0/README.md`
- `docs/delivery/v1.0/01_ACCEPTANCE_REPORT.md`
- `docs/delivery/v1.0/02_DEPLOYMENT_PLAN.md`
- `docs/delivery/v1.0/03_USER_MANUAL.md`
- `docs/delivery/v1.0/04_OPERATIONS_MANUAL.md`
- `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md`
- `docs/delivery/v1.0/06_TEST_REPORT.md`
- `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md`
- `docs/00_INDEX.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- 交付包引用现有脚本复演证据: `logs/smoke/smoke-demo-20260611-011803.md`, 5 条固定演示题均为 `True`。
- 交付包引用现有日志包证据: `logs/exports/zt-poc-logs-20260611-011813.zip`。
- 交付包文件完整性检查通过: `docs/delivery/v1.0/` 下 8 个 Markdown 文件均存在。
- `git diff --check` 通过。
- `scripts/check-poc.ps1 -SkipExternal -Json` 通过: Docker CLI / daemon / Compose、`.env`、客户配置、问数数据、Dora / ASR / TTS 配置和 FVS Mock 配置为 ok; 因本轮未启动 API / Web, 端口空闲与 API / Web 未连接为 warning; 外部依赖探测按参数跳过。
- 本轮为文档交付, 未修改前后端代码, 未重新执行真实 Dora / RAGFlow / ASR / TTS / FVS 联调。

#### Notes

- 验收报告中明确标注现场截图、真实客户网络、麦克风 / 播放权限、Dora / RAGFlow 连通性和客户签字仍需现场补齐。
- 演示稳态模式继续作为固定演示保底, 不能替代真实外部依赖验收。

### FVS 大屏交互精简与唤醒语音反馈

#### Completed

- FVS iframe host 默认态语音入口由大号红色圆形按钮改为小型低透明麦克风 icon, 并移除 FVS 主画布右上角“运维”悬浮入口。
- FVS host 悬浮层展开条件收紧为正式录音、连续追问、思考、TTS 加载或播报; `monitoring`、`wake_checking`、`cooldown` 和未命中唤醒词不再展开对话浮层。
- FVS host 展开态改为半透明评论流, 仅显示最近用户识别文本和数字人回复文本; 不再显示监听调试、来源、`action_id`、reason、TTS 按钮或 audio 控件。
- 新增前端 `/ops` 独立路径进入运维看板, 复用现有 Ops API 和 Nginx history fallback, 不新增端口或后端接口。
- 命中唤醒词后立即播报固定提示 `您好。`; 若唤醒句中包含指令, 指令处理不等待该提示播完, 等待提示 `收到, 正在为您查找信息。` 会排在 `您好。` 之后播放。
- 新增 ADR-0016, 记录 FVS 极简悬浮层、独立运维路径和唤醒成功语音反馈决策。

#### Changed Files

- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `docs/integrations/FVS_INTEGRATION.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/00_INDEX.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0016-fvs-minimal-overlay-and-ops-route.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- `git diff --check` 通过。
- 本地 Vite preview 验证 `GET http://127.0.0.1:18001/` 返回 HTTP 200。
- 本地 Vite preview 验证 `GET http://127.0.0.1:18001/ops` 返回 HTTP 200。
- 源码断言通过: FVS 主画布无 `ops-float-button`; 存在 `WAKE_GREETING_TEXT = '您好。'`; `/ops` 路径识别存在; FVS 评论流模板 / 样式存在; compact icon 样式为 48px; FVS 展开状态不包含 `wake_checking`。

#### Notes

- 本轮未改后端接口, 未新增端口。
- 当前工具环境未暴露 Codex Browser 控制工具, 且未安装 Playwright / Puppeteer; 未做截图级浏览器验证和真实麦克风唤醒音频顺序人工验证。

### V0.9 交付优化

#### Completed

- 新增交付脚本目录 `scripts/`:
  - `check-poc.ps1`: 预检 Docker CLI / Docker daemon / Compose、端口、配置、API、Web、Ops 依赖和 RAGFlow。
  - `start-poc.ps1`: 一键启动 API / Web, 支持 `-Build`、`-DemoStable`、`-WithRagflow`。
  - `stop-poc.ps1`: 一键停止 API / Web, 支持可选停止本机 RAGFlow。
  - `export-logs.ps1`: 基于 V0.8 脱敏 Ops API 导出现场日志包。
  - `smoke-demo.ps1`: 使用固定演示问题集做 API smoke, 可选执行已白名单校验的大屏动作。
  - `poc-common.ps1`: 复用 `.env` 解析、HTTP 检查、UTF-8 响应解码和报告输出等 helper。
- 新增 `DEMO_STABLE_MODE` 后端开关和 `VITE_DEMO_STABLE_MODE` 前端构建开关; `.env.example`、Docker Compose、Web Dockerfile 和客户 `runtime.yaml` 已同步。
- 新增 `GET /api/demo/config`, 返回演示稳态、客户 ID、问数模式、Mock 开关和固定演示问题。
- `DEMO_STABLE_MODE=true` 时, Dora 请求失败会优先尝试本地 Excel 问数和 Mock Dora 演示兜底; 未命中时仍返回安全 fallback。
- Excel 问数数据缺失、Dora 流式异常和 TTS 分段异常会返回面向演示的安全提示, 不向前端暴露系统堆栈或供应商异常原文。
- 前端新增“演示稳态”状态标识, 演示按钮改为读取 `/api/demo/config` 的固定问题集, 并保留本地默认题集。
- FVS iframe 新增加载超时 / 加载失败兜底提示; 控屏仍只在 `/api/screen/execute` 白名单校验成功后执行。
- 新增 ADR-0015, 记录 V0.9 交付脚本、日志包和演示稳态模式决策。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/mock_dora.py`
- `apps/web/Dockerfile`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `config/customers/zt-securities/runtime.yaml`
- `docker-compose.yml`
- `scripts/`
- `docs/decisions/ADR-0015-v09-delivery-scripts-and-demo-stable-mode.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `scripts/check-poc.ps1 -SkipExternal -Json` 可输出预检 JSON, 当前 Docker daemon、Compose、API / Web 端口、`.env`、客户配置和问数数据检查通过。
- `scripts/start-poc.ps1 -Build -DemoStable` 成功重建并启动 API / Web, `GET /api/demo/config` 返回 `stable_mode=true`。
- `scripts/smoke-demo.ps1 -ExecuteScreenActions` 通过, 固定 5 条演示题返回预期 `answer` / `screen_control`, 控屏动作经 `/api/screen/execute` 执行成功。
- `scripts/export-logs.ps1 -Zip` 成功生成日志包 `logs/exports/zt-poc-logs-20260611-011813.zip`。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过, 当前 API / Web 服务已启动。
- Codex Browser 验证 `http://127.0.0.1:18000?fvs_mode=mock` 可见“演示稳态”和动态演示题; `fvs_mode=iframe` 配无效 FVS URL 时可见“FVS 看板暂不可用”超时兜底。

#### Notes

- `scripts/export-logs.ps1` 默认不打包 Docker 原生日志; 如现场确需原生日志, 需显式加 `-IncludeDockerLogs`。
- 演示稳态模式只用于降低外部服务临时不可用对固定演示的影响, 不能替代真实 Dora / RAGFlow / ASR / TTS / FVS 验收。

### V0.8 第三阶段运维监控和日志看板

#### Completed

- 新增后端只读 Ops API:
  - `GET /api/ops/health`
  - `GET /api/ops/dependencies`
  - `GET /api/ops/sessions`
  - `GET /api/ops/session/{session_id}`
  - `GET /api/ops/errors`
  - `GET /api/ops/metrics`
  - `GET /api/ops/export`
- 扩展 `SessionLogStore`, 基于现有 SQLite `session_logs` 表提供最近会话、单会话明细、错误列表、聚合耗时和最近耗时样本查询。
- 日志摘要、错误消息和 Markdown 导出会做长度截断, 并对常见 `api_key` / `token` / `password` / `Bearer` / `sk-*` / `ak-*` 模式做脱敏。
- Ops 依赖状态覆盖 SQLite 会话日志、Screen Actions 白名单、Dora、RAGFlow、ASR、TTS 和 FVS。
- Dora / RAGFlow 依赖状态只做轻量只读 HTTP 探测; ASR / TTS 不主动上传音频或触发合成, 仅报告 Mock 或真实配置就绪状态。
- 后端读取客户 `fvs.yaml` 中的非敏感 FVS 模式和 URL 样例, 并兼容 `VITE_FVS_*` 环境变量别名用于 Ops 状态展示。
- 前端新增“演示 / 运维”视图切换。运维看板展示系统状态、依赖状态、最近会话、错误列表、耗时指标, 并支持导出 Markdown 日志摘要。
- 新增 ADR-0014, 记录只读脱敏 Ops API 和同页运维看板决策。
- 同步更新 API 契约、数据契约、开发计划、下一步、风险、测试计划、客户移交、客户验收清单、路线图、变更记录和跨对话上下文。

#### Changed Files

- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/session_log.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/14_ENHANCEMENT_ROADMAP.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/decisions/ADR-0014-readonly-sanitized-ops-dashboard.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `docker compose up -d --build api web` 成功, API / Web 容器均已重建并启动。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET /api/ops/health` 返回 HTTP 200, `customer_id=zt-securities`。
- `GET /api/ops/dependencies` 返回 HTTP 200, 当前聚合 `status=error`: SQLite、动作白名单、ASR、TTS、FVS Mock 为 ok; Dora 探测超时, RAGFlow 探测失败。
- `GET /api/ops/sessions`、`GET /api/ops/errors`、`GET /api/ops/metrics` 均返回 HTTP 200。
- `GET /api/ops/export` 返回 HTTP 200 `text/markdown; charset=utf-8`, 并带 Markdown 运维日志摘要。
- 对 `/api/ops/export` 内容做密钥模式扫描, 未命中 `api_key` 明文、`Bearer ...`、`sk-*` 或 `ak-*` 模式。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- Codex Browser 验证 FVS iframe host 模式下右上角“运维”悬浮入口可见; 点击后进入运维看板, 依赖状态、最近会话、错误列表和耗时指标均可见。
- Codex Browser 验证 `?fvs_mode=mock` 非 FVS 主画布模式下顶部“演示 / 运维”切换可进入运维看板。

#### Notes

- 当前耗时指标来自 `session_logs.latency_total_ms`, 覆盖已写入日志的 chat / stream chat / screen execute 总耗时; ASR / Dora / RAGFlow / TTS 更细分的链路耗时留给 V0.9 交付优化继续细化。
- 当前运维看板未加入登录鉴权, 仍按本地 POC 内网使用前提控制访问范围。
- 本轮未执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell。

## 2026-06-10

### V0.8 第二阶段 TTS 字节级真流式播放

#### Completed

- 新增后端 TTS 真流式 Provider 接口 `stream_synthesize`。
- Mock TTS 支持输出 PCM 音频 chunk, 用于无外部 TTS Key 时验证真流式播放器。
- 阿里云 CosyVoice TTS Provider 支持逐块转发 WebSocket 二进制音频帧, 不再必须等全部音频合成后写文件。
- 新增 `POST /api/tts/stream`, 通过 `text/event-stream` 返回 `metadata`、`audio_chunk`、`tts_error` 和 `end`。
- 新增 `TTS_STREAMING_ENABLED`、`TTS_STREAMING_FALLBACK`、`TTS_STREAMING_AUDIO_FORMAT` 后端配置, Docker Compose 和 `.env.example` 已透出。
- 客户 `voice.yaml` 新增 TTS streaming 配置样例: `enabled=true`、`fallback=segment`、`audio_format=pcm`。
- 前端新增 `/api/tts/stream` SSE 客户端。
- 前端新增 PCM Web Audio 真流式播放器: 将后端返回的 PCM chunk 解码为 `AudioBuffer`, 按时间轴排队播放并驱动语音能量动画。
- 前端自动播报和播报按钮优先尝试真流式; 真流式失败时回退 `/api/chat/stream` 的 `tts_ready` 分段音频, 最后回退完整 `/api/tts` 文件。
- AI 真流式音频开始播放时继续复用 `cleanupAudio()`, 可打断等待提示音或浏览器本地 `speechSynthesis` 等待提示。
- 新增 ADR-0013, 记录 TTS 字节级真流式采用 SSE + PCM chunk + Web Audio 的决策。
- 同步更新 API 契约、数据契约、配置说明、测试计划、ASR/TTS 集成说明、风险和下一步文档。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/tts_provider.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `config/README.md`
- `config/customers/zt-securities/customer.env.example`
- `config/customers/zt-securities/voice.yaml`
- `docker-compose.yml`
- `docs/00_INDEX.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/decisions/ADR-0013-tts-byte-streaming-with-pcm-web-audio.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `docker compose up -d --build api web` 成功, API / Web 容器均已重建并启动。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- 默认配置恢复后容器内确认:
  - `tts_streaming_enabled=True`
  - `tts_streaming_fallback=segment`
  - `tts_streaming_audio_format=pcm`
  - `enable_mock_tts=False`
- 真实 TTS 配置下 `POST /api/tts/stream` 请求 `format=pcm` 返回 `metadata -> audio_chunk* -> end`; 本轮抽样首个 `audio_chunk` 约 567ms 到达, `end.duration_ms=3387`, 共 33 个 chunk。
- 临时以 `TTS_STREAMING_ENABLED=false` 重建 API 后, `POST /api/tts/stream` 返回 `tts_error` code=`TTS_STREAMING_DISABLED`, 随后 `end.ok=false`, `fallback=segment`; 验证后已恢复默认真流式开启。
- `/api/chat/stream` 输入 `当前党员学习完成率是多少?` 返回 `metadata`、多个 `dora_delta`、`answer`、4 个 `tts_ready` 和 `end`, 说明分段 TTS fallback 仍保留。
- `GET http://127.0.0.1:18000` 返回前端 HTML, JS / CSS 构建产物均返回 HTTP 200。

#### Notes

- 当前前端真流式播放默认请求 PCM, 以规避浏览器对 MP3 / Opus MediaSource 支持不一致的问题。
- `/api/chat/stream` 的分段 `tts_ready` 事件仍保留, 作为 `TTS_STREAMING_FALLBACK=segment` 的稳定 fallback。
- 本轮 Codex Browser 控制工具未暴露, 未做截图级浏览器交互验证; 已完成前端生产构建和 HTTP 资源可访问检查。

### V0.8 第一阶段客户配置覆盖层与问数模式

#### Completed

- 新增 `CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR` 和 `ASK_METRICS_MODE` 后端配置项。
- 新增后端客户配置覆盖层解析: 默认读取根配置, 若存在 `config/customers/<customer-id>/` 则优先使用客户级 `screen-actions.yaml`、`demo-cases.yaml`、`wake-words.yaml`、`ask-metrics.yaml`。
- 客户级 `runtime.yaml` / `ask-metrics.yaml` 可配置 `ask_metrics_mode` / `mode` 和 `data_dir`; `.env` 或容器环境变量中的 `ASK_METRICS_MODE` 可覆盖 YAML。
- 客户级 `dora.yaml`、`ragflow.yaml`、`voice.yaml` 可覆盖非敏感 Dora Agent、RAGFlow 地址、ASR/TTS 模型和超时参数; API Key 仍只允许来自 `.env` / 部署环境变量。
- 兼容旧 `.env`: 如果旧路径变量仍等于根目录默认配置路径, 不阻止客户目录覆盖; 真正自定义路径仍优先。
- 新增 `config/customers/zt-securities/` 客户私有配置目录, 包含:
  - `README.md`
  - `customer.env.example`
  - `runtime.yaml`
  - `screen-actions.yaml`
  - `ask-metrics.yaml`
  - `demo-cases.yaml`
  - `wake-words.yaml`
  - `dora.yaml`
  - `ragflow.yaml`
  - `voice.yaml`
  - `fvs.yaml`
- Docker Compose 新增 `CUSTOMER_ID` / `CUSTOMER_CONFIG_DIR`, 不再硬编码根目录 YAML 路径, 由后端配置解析器选择默认配置或客户配置。
- `/api/chat` 新增 `ASK_METRICS_MODE` 路由:
  - `excel`: 保持 V0.7 行为, 先匹配 Excel 问数, 未命中再走 Dora / Mock Dora。
  - `dora`: Excel Adapter 不抢占, 直接走 Dora / Mock Dora。
  - `auto`: 优先 Dora / Mock Dora, 返回 `fallback` 或 Dora 请求失败时再回退 Excel。
- `/api/chat/stream` 同步 `ASK_METRICS_MODE` 路由, 保持问数 SSE 事件兼容。
- 新增 ADR-0012, 记录客户配置覆盖层与问数模式路由决策。
- 同步更新 API 契约、数据契约、配置说明、部署说明、测试计划、路线图、风险、客户移交、客户验收清单和客户演示用例。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `docker-compose.yml`
- `config/README.md`
- `config/customers/zt-securities/`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/14_ENHANCEMENT_ROADMAP.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/customers/zt-securities/DEMO_CASES.md`
- `docs/customers/zt-securities/SCREEN_ACTIONS.md`
- `docs/decisions/ADR-0012-customer-config-overlay-and-ask-metrics-mode.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api` 成功。
- API 容器内 `get_settings()` 确认:
  - `customer_id=zt-securities`
  - `customer_config_dir=/app/config/customers/zt-securities`
  - `action_whitelist_path=/app/config/customers/zt-securities/screen-actions.yaml`
  - `demo_cases_path=/app/config/customers/zt-securities/demo-cases.yaml`
  - `wake_words_path=/app/config/customers/zt-securities/wake-words.yaml`
  - `ask_metrics_config_path=/app/config/customers/zt-securities/ask-metrics.yaml`
  - `ask_metrics_data_dir=/app/docs/demo_data/ask_metrics`
  - `ask_metrics_mode=excel`
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `ASK_METRICS_MODE=excel` 下 `/api/chat` 11 个问数 smoke 均返回 `type=answer`, 且回答包含 Excel 来源:
  - 当前党员学习完成率 87.5%, 党员总数 128 人, 已完成学习 112 人。
  - 本月完成学习 112 人。
  - 最低学习完成率支部为信息技术支部, 83.3%。
  - 主题党日 34 次。
  - 组织生活平均参会率 83.9%。
  - 整改闭环率 46.7%。
  - 入党积极分子 12 人。
  - 发展对象 7 人及支部分布。
  - 本年转正党员 3 人。
  - 党员发展材料待补充 3 人。
  - 党建整体总结包含学习完成率 87.5%、组织生活活动完成率 92.6%、平均参会率 83.9%、入党积极分子 12 人、发展对象 7 人。
- `ASK_METRICS_MODE=excel` 下 `入党流程是什么?` 未被问数 Adapter 拦截, `display.source=None`。
- `/api/chat/stream` 输入 `当前党员学习完成率是多少?` 返回事件顺序 `metadata -> dora_delta -> answer -> tts_ready -> end`。
- 容器内函数级验证 `ASK_METRICS_MODE=dora` 输入 `学习完成率是多少?` 返回 Mock Dora `answer`, `display.source=None`, 说明 Excel Adapter 未抢答。
- 容器内函数级验证 `ASK_METRICS_MODE=auto` 输入 `本月主题党日开展了几次?` 在 Mock Dora 兜底后回退 Excel, 返回 34 次和 `zt_party_org_life_metrics_2026.xlsx / Dashboard` 来源。
- 验证后 API 容器已恢复为默认 `ASK_METRICS_MODE=excel`; 当前 `docker compose ps` 显示 API / Web 均为 running。

#### Notes

- 本轮未实现 TTS 字节级真流式和运维监控 / 日志看板。
- `dora` 模式会把问数交给 Dora / Mock Dora 链路; 真实 Dora 通用问数质量仍取决于 Dora 侧数据源、工具和 Prompt。
- 本轮未执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell。

### V0.8 / V0.9 / V1.0 路线文档调整

#### Completed

- 根据用户要求调整后续路线: 先做功能增强, 再做交付前优化, 最后输出验收报告、部署方案和用户手册等交付材料。
- 新增 `docs/14_ENHANCEMENT_ROADMAP.md`, 记录 V0.8 / V0.9 / V1.0 的目标、范围、验收和推荐 goal 顺序。
- 新增 ADR-0011, 记录“先功能增强再交付优化”的阶段决策。
- `docs/05_DEVELOPMENT_PLAN.md` 增加 V0.8 功能增强版、V0.9 交付优化版、V1.0 POC 验收交付版。
- `docs/NEXT_ACTIONS.md` 当前阶段改为 V0.8 功能增强版准备, 并写入第一推荐 goal: 客户私有配置目录 + `ASK_METRICS_MODE=dora|excel|auto`。
- `docs/CODEX_CONTEXT.md` 更新跨对话恢复上下文和推荐启动提示。
- `docs/06_API_CONTRACT.md` 增加 V0.8 Draft: `ASK_METRICS_MODE`、`POST /api/tts/stream`、Ops APIs。
- `docs/07_DATA_CONTRACT.md` 增加 V0.8 Draft: Ask Metrics Mode、Streamed Audio Chunk、Ops Status、Customer Config Overlay。
- `docs/08_CONFIG_GUIDE.md` 增加 V0.8 Draft: 客户私有配置目录、`CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR`、`ASK_METRICS_MODE`、TTS 真流式配置。
- `docs/10_TEST_PLAN.md` 增加 V0.8 / V0.9 / V1.0 测试草案。
- `docs/13_RISKS_AND_TODO.md` 增加 Dora 通用问数、TTS 真流式、运维看板敏感信息、客户配置覆盖层风险。
- `docs/12_CUSTOMER_HANDOFF.md` 的后续建议同步为 V0.8 -> V0.9 -> V1.0。

#### Changed Files

- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/14_ENHANCEMENT_ROADMAP.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/decisions/ADR-0011-enhancement-before-handoff.md`

#### Verification

- 本轮仅更新文档, 未修改运行时代码。
- `git diff --check` 通过。

#### Notes

- 下一轮推荐用 goal 方式执行 V0.8 第一阶段。
- 正式验收报告、部署方案和用户手册延后到 V1.0, 以 V0.8 / V0.9 的真实实现和验证结果为准。

### V0.7 POC 稳定版问数 Adapter 与演示包准备

#### Completed

- 新增 `apps/api/app/services/ask_metrics.py`, 实现 Gateway 本地只读 Excel 问数 Adapter。
- 新增 `config/ask-metrics.yaml`, 管理 V0.7 本地问数工作簿文件名和 sheet 映射。
- Adapter 使用 Python 标准库解析 `.xlsx`, 不新增后端依赖, 读取 `docs/demo_data/ask_metrics/` 下三份脱敏样例:
  - `zt_party_study_metrics_2026.xlsx`
  - `zt_party_org_life_metrics_2026.xlsx`
  - `zt_party_development_metrics_2026.xlsx`
- `/api/chat` 在调用 Mock Dora / 真实 Dora 前优先匹配问数意图, 命中后直接返回标准 `answer`, 并在 `display.source` 和 bullets 中标明数据来源。
- `/api/chat/stream` 问数命中后直接返回 `metadata`、`dora_delta`、`answer`, 并继续复用现有分段 TTS 逻辑。
- Docker API 镜像已复制 `docs/demo_data`, Compose 已新增只读挂载 `./docs/demo_data:/app/docs/demo_data:ro`、`ASK_METRICS_DATA_DIR=/app/docs/demo_data/ask_metrics` 和 `ASK_METRICS_CONFIG_PATH=/app/config/ask-metrics.yaml`。
- 新增 ADR-0010, 记录 V0.7 采用本地 Excel Adapter 承接问数的决策。
- 同步更新 API 契约、数据契约、配置说明、部署说明、测试计划、POC 演示脚本、客户移交、客户验收清单、客户演示用例、风险清单、下一步和跨对话上下文。

#### Changed Files

- `.env.example`
- `apps/api/Dockerfile`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/ask_metrics.py`
- `config/ask-metrics.yaml`
- `docker-compose.yml`
- `config/README.md`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/10_TEST_PLAN.md`
- `docs/11_POC_DEMO_SCRIPT.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/customers/zt-securities/DEMO_CASES.md`
- `docs/decisions/ADR-0010-local-excel-ask-metrics-adapter.md`
- `docs/demo_data/ask_metrics/README.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api` 成功。
- API 容器内 `uv run python -m compileall app` 通过。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `/api/chat` 问数 smoke 通过 11 题:
  - `当前党员学习完成率是多少?` -> `answer`, 87.5%, 128 人, 112 人。
  - `本月有多少人完成学习?` -> `answer`, 112 人。
  - `哪个支部学习完成率最低?` -> `answer`, 信息技术支部, 83.3%。
  - `本月主题党日开展了几次?` -> `answer`, 34 次。
  - `组织生活平均参会率是多少?` -> `answer`, 83.9%。
  - `整改事项闭环率是多少?` -> `answer`, 46.7%。
  - `当前入党积极分子有多少人?` -> `answer`, 12 人。
  - `发展对象有多少人? 分别在哪些支部?` -> `answer`, 7 人及支部分布。
  - `本年转正党员有多少人?` -> `answer`, 3 人。
  - `哪些党员发展材料还待补充?` -> `answer`, 3 人及支部 / 人员 ID。
  - `总结一下当前党建工作整体情况` -> `answer`, 综合学习、组织生活和党员发展指标。
- 服务级检查确认 `入党流程是什么?` 不被问数 Adapter 拦截。
- `/api/chat/stream` 输入 `当前党员学习完成率是多少?` 返回事件顺序 `metadata`、`dora_delta`、`answer`。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose up -d --build web` 成功, API 和 Web 容器均启动。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。

#### Notes

- 当前问数能力是本地 POC 稳定演示方案, 不是通用 BI 问数引擎。
- 正式客户问数仍需确认真实数据源、指标口径、刷新频率和授权范围。
- Adapter 不执行模型生成 SQL、Python 或 JavaScript; 未命中问数意图时继续走 Dora / Mock Dora 原链路。

### V0.6 FVS 网页框真实集成准备

#### Completed

- 用户确认 V0.6 先尝试把数字人前端作为 FVS 网页框嵌入大屏, 并提供帆软 FVS 网页框通信文档。
- 已核对帆软文档中的关键通信路径:
  - FVS 主模板使用 `duchamp.onlyCommunicateWithOrigins([...])` 指定允许通信的网页框来源。
  - 数字人网页框可通过 `window.parent.postMessage(message, targetOrigin)` 向 FVS 主模板发送消息。
  - FVS 主模板使用 `duchamp.addPostMessageListener(callback)` 接收网页框消息。
- 新增 `apps/web/src/fvsAdapter.ts`, 支持 `mock`、`iframe`、`parent` 三类模式; `web-frame` / `fvs-web-frame` 作为 `parent` 别名。
- 前端在 `VITE_FVS_INTEGRATION_MODE=parent` 时按 FVS 网页框模式运行, 使用单列嵌入友好布局, 不再优先展示内部 Mock 大屏。
- 前端只在 `/api/screen/execute` 返回 `success=true` 后发送 `FVS_ACTION` 消息给父 FVS 页面。
- `FVS_ACTION` 消息包含 `type=FVS_ACTION`、`source=zt-digital-human`、`action_id`、`actionId`、`functionName` 和 `params`; FVS 侧应以 `action_id` 做固定映射。
- 增强前端麦克风失败提示, 可区分非安全上下文、网页框未授予 microphone 权限、浏览器拒绝、设备不存在或设备占用等常见原因。
- 根据用户现场反馈, V0.6 推荐方向从“FVS 网页框嵌入数字人”切换为“数字人前端主页面 iframe 嵌入 FVS 看板”。
- `apps/web/src/fvsAdapter.ts` 新增运行时 URL 参数支持: `?fvs_url=...`、`?fvs_origin=...` 和 `?fvs_mode=...`, 便于不重建前端直接测试 FVS URL。
- 本地 `.env` 已将 `VITE_FVS_INTEGRATION_MODE` 从 `parent` 切换为 `iframe`。
- 新增 ADR-0007, 并将 ADR-0006 标记为 Superseded。
- `docker-compose.yml` 和 `apps/web/Dockerfile` 已透出 `VITE_FVS_URL`、`VITE_FVS_INTEGRATION_MODE`、`VITE_FVS_TARGET_ORIGIN` 构建参数。
- 本地 `.env` 已将 FVS 配置从占位 `iframe` 切到 `parent` 网页框通信模式。
- 新增 ADR-0006, 记录 FVS 网页框通信集成方向。
- 同步更新 FVS 集成说明、配置说明、API / 数据契约、测试计划、客户动作清单、客户移交、风险、下一步和变更记录。

#### Changed Files

- `.env`
- `.env.example`
- `apps/web/Dockerfile`
- `apps/web/src/App.vue`
- `apps/web/src/fvsAdapter.ts`
- `apps/web/src/style.css`
- `docker-compose.yml`
- `config/README.md`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/customers/zt-securities/SCREEN_ACTIONS.md`
- `docs/decisions/ADR-0006-fvs-web-frame-communication.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- 增强麦克风失败提示后, `corepack pnpm --dir apps/web build` 再次通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build web` 成功, API 和 Web 容器均已重建并启动。
- 增强麦克风失败提示后, `docker compose up -d --build web` 再次成功。
- iframe host 方向调整后, `corepack pnpm --dir apps/web build` 通过。
- iframe host 方向调整后, `docker compose up -d --build web` 成功。
- Codex 内置浏览器使用 `http://127.0.0.1:18000/?fvs_url=http%3A%2F%2F127.0.0.1%3A18080%2Fapi%2Fhealth` 验证运行时 FVS URL 参数生效: 页面显示 `FVS iframe`, iframe `src` 正确, 内部 Mock 屏未出现, 控制台无 error。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- Codex 内置浏览器验证 `http://127.0.0.1:18000`: 当前构建为 `workspace fvs-web-frame` 单列布局, 页面显示 `FVS 通信已就绪`, 内部 Mock 大屏未出现, 文本输入可见, 控制台无 error。
- `POST /api/screen/execute` 执行 `SWITCH_TAB_ORG` 返回 `success=true`。
- `POST /api/screen/execute` 执行 `UNKNOWN_ACTION` 返回 `success=false` 和 `ACTION_NOT_ALLOWED`。

#### Notes

- 本轮尚未接到真实 FVS 页面 / Tab 控制 API。
- 下一步需要在真实 FVS 主模板中添加网页框组件, 加载数字人前端 URL, 配置 `duchamp.onlyCommunicateWithOrigins` 和 `duchamp.addPostMessageListener`, 再映射 3 个以上动作。
- FVS 侧也不得根据 `functionName` 动态执行脚本, 只能按 `action_id` 固定映射。

### Completed

- 根据《中天证券党建大屏对话数字人本地开发技术方案》建立文档驱动开发体系。
- 创建项目文档总入口、Codex 跨对话上下文、项目蓝图、架构、开发计划、接口契约、数据契约、配置说明、部署说明、测试计划、演示脚本、客户移交文档、风险清单。
- 创建 ADR 决策记录目录。
- 创建 Dora、RAGFlow、FVS、ASR/TTS 集成说明。
- 创建中天证券客户资料目录。
- 创建根目录 `AGENTS.md`, 作为 Agent 阅读顺序、开发规则和文档维护规则入口。
- 初始化当前目录为 Git 仓库, 默认分支为 `main`。
- 检查本机工具链: Git、Docker、Node.js、npm、Corepack 可用; pnpm 和 uv 未安装; PATH 上 Python 为 3.14.5。
- 固定项目包管理决策: 前端使用 pnpm, 后端使用 uv, Docker 内后端运行时使用 Python 3.12。
- 创建 `.gitignore`、`.env.example` 和第一版 `config/` 配置文件。

### Changed Files

- `README.md`
- `AGENTS.md`
- `.gitignore`
- `.env.example`
- `config/`
- `data/.gitkeep`
- `logs/.gitkeep`
- `docs/`

### Verification

- 文档文件已创建。
- Git 仓库已初始化。
- Docker 服务可用, Server 版本为 `29.5.2`。
- 本地 Markdown 链接检查通过。
- 尚未创建代码工程, 无需运行前后端测试。

### Notes

- 当前阶段为 V0.0 文档体系初始化。
- 下一阶段建议进入 V0.1 Mock 闭环工程初始化。

### V0.1 Mock 闭环初始化

#### Completed

- 创建 `apps/api` FastAPI 后端工程, 使用 uv 管理依赖, Docker 内运行 Python 3.12。
- 创建 `apps/web` Vue 3 + TypeScript + Vite 前端工程, 使用 pnpm 管理依赖。
- 创建根目录 `docker-compose.yml`, 暴露前端 `18000` 和后端 `18080`。
- 后端读取现有 `config/screen-actions.yaml`、`config/demo-cases.yaml`、`config/wake-words.yaml`。
- 实现 `GET /api/health`、`POST /api/chat`、`GET /api/screen/actions`、`POST /api/screen/execute`。
- `/api/chat` 已支持 Mock Dora 的 `answer`、`screen_control`、`fallback` 返回。
- `/api/screen/execute` 已通过后端白名单校验 `action_id`, 合法动作成功, 非法动作返回 `ACTION_NOT_ALLOWED`。
- 前端已实现文本输入、Mock 回复展示、Mock FVS 当前页面/最近动作展示。
- 增加 SQLite 会话日志写入, 数据库路径为 `data/sessions.db`。
- 生成并提交 `apps/web/pnpm-lock.yaml` 和 `apps/api/uv.lock`, Docker 构建使用 frozen install。
- 更新 `.env.example` 和配置说明中的 `DEMO_CASES_PATH`、`WAKE_WORDS_PATH`。

#### Changed Files

- `.env.example`
- `README.md`
- `apps/api/`
- `apps/web/`
- `docker-compose.yml`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均保持运行。
- `GET http://localhost:18080/api/health` 返回 `status=ok`。
- `GET http://localhost:18080/api/screen/actions` 返回 4 个白名单动作。
- `POST /api/chat` 输入“请切换到组织建设页面”返回 `type=screen_control` 和 `SWITCH_TAB_ORG`。
- `POST /api/chat` 输入“张书记”和“入党流程是什么”返回 `type=answer`。
- `POST /api/chat` 输入未命中内容返回 `type=fallback`。
- `POST /api/screen/execute` 执行 `SWITCH_TAB_ORG` 返回 `success=true`。
- `POST /api/screen/execute` 执行 `UNKNOWN_ACTION` 返回 `success=false` 和 `ACTION_NOT_ALLOWED`。
- `GET http://localhost:18000` 返回 HTTP 200。
- Codex 内置浏览器验证前端可输入“请切换到组织建设页面”, 展示数字人回复和 `SWITCH_TAB_ORG`, Mock FVS 切换到“组织建设”, 控制台无 error。

#### Notes

- V0.1 未接入真实 Dora、ASR、TTS、RAGFlow、FVS。
- PowerShell 直接发送中文 JSON 时本地终端可能出现编码显示干扰; 使用浏览器和 Unicode escape JSON 验证链路正常。

### V0.2 Dora 配置准备

#### Completed

- 创建本地 `.env`, 写入 Dora 环境地址、Dora Key、Agent 名称和 `DORA_CHANNEL_TYPE=feishu`; `.env` 已被 `.gitignore` 排除。
- 更新 `.env.example`, 增加 `DORA_AGENT_NAME` 和 `DORA_CHANNEL_TYPE`, 并允许 `DORA_AGENT_ID` 为空。
- 更新 `docker-compose.yml`, 将 Dora 配置变量传入后端容器。
- 更新后端 Settings, 增加 Dora Base URL、Key、Agent ID、Agent Name、Channel Type、Chat Mode 和 Timeout 配置字段。
- 更新 Dora 集成说明, 明确 V0.2 使用 Dora OpenClaw API, 支持按 Agent 名称自动发现已发布 Agent。

#### Verification

- 尚未调用真实 Dora; 当前仅完成 V0.2 配置文件准备。
- 真实接入时先通过 `GET /external/api/openclaw/agents` 查找 `DORA_AGENT_NAME` 对应的已发布 Agent。

#### Notes

- 当前 `DORA_CHANNEL_TYPE` 暂用 `feishu`, 如客户环境要求其他渠道值, 只需修改 `.env`。
- Dora Key 只应保存在本地 `.env`, 不应写入前端、文档或 Git。

### V0.2 Dora Adapter 实现

#### Completed

- 增加 `apps/api/app/services/dora_client.py`, 实现 Dora OpenClaw `list_agents`、`resolve_agent_id` 和 `sse_chat`。
- 增加 `apps/api/app/services/dora_normalizer.py`, 支持 Dora 标准 JSON、Markdown JSON、自然语言输出归一化。
- `/api/chat` 已根据 `ENABLE_MOCK_DORA` 分流: `true` 继续走 V0.1 Mock, `false` 调用 Dora OpenClaw SSE。
- `DORA_BASE_URL`、`DORA_API_KEY`、`DORA_AGENT_ID`、`DORA_AGENT_NAME`、`DORA_CHANNEL_TYPE`、`DORA_TIMEOUT_SECONDS` 均从 `.env` / 环境变量读取。
- 当 `DORA_AGENT_ID` 为空时, 已按 `DORA_AGENT_NAME=战区业绩分析Agent-刘峰` 自动发现已发布 Agent。
- Dora SSE 解析已适配当前 OpenClaw event 形态: 忽略 `metadata` / `values`, 从 `messages` chunk 中收敛回答文本。
- Dora 输出统一返回 `answer` / `screen_control` / `fallback`; Dora `clarify` 在 V0.2 中先转为 `answer` 展示。
- `screen_control` 仍只透出白名单中的 `action.id`, 非法 action 返回 `fallback` 和 `ACTION_NOT_ALLOWED`。
- 增加后端依赖 `httpx`, 并刷新 `apps/api/uv.lock`。
- `.env.example` 中 `DORA_AGENT_NAME` 示例更新为 `战区业绩分析Agent-刘峰`。

#### Verification

- `docker compose build api` 通过, `uv sync --frozen --no-dev` 安装 `httpx` 成功。
- `python -m compileall app` 通过。
- 容器内归一化 smoke tests 通过: Markdown JSON、自然语言、合法 `screen_control`、非法 `screen_control` 均符合预期。
- V0.1 回归通过: `GET /api/health`、Mock `answer` / `screen_control` / `fallback`、动作白名单、合法动作执行、非法动作拒绝、前端 HTTP 200。
- Dora 连通性验证通过: `list_agents` 返回可用列表, `resolve_agent_id` 成功匹配本地 `.env` 中的已发布 Agent, `sse_chat` 返回内容并归一为 `answer`。
- 临时设置 `ENABLE_MOCK_DORA=false` 后, `POST /api/chat` 真实调用 Dora 并返回归一化 `answer`; 验证后已将运行态恢复为 `ENABLE_MOCK_DORA=true`。

#### Notes

- 未接入真实 ASR、TTS、RAGFlow、FVS。
- 真实 Dora 当前连接的是“战区业绩分析Agent-刘峰”, 已验证问答连通性; 真实 `screen_control` 还需在 Dora Agent Prompt 对齐项目动作白名单后验证。
- PowerShell 管道直接传中文到容器时仍可能出现编码替换; HTTP JSON 使用 Unicode escape 验证正常。

### V0.2 Dora Prompt 对齐与控屏探测

#### Completed

- 更新 `docs/integrations/DORA_AGENT_PROMPT.md`, 将 Dora Agent Prompt 收紧为 V0.2 可复制到 Dora 后台的专用版本。
- Prompt 已写入 4 个白名单动作: `SWITCH_HOME`、`SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_TAB_ACTIVITY`。
- Prompt 已明确禁止 Dora 输出 JavaScript、函数名、FVS 参数、HTML 或脚本。
- Prompt 已补充非法页面请求的 `fallback` 输出要求。
- 更新 `docs/customers/zt-securities/SCREEN_ACTIONS.md`, 补充 Dora 对每个动作应输出的 JSON 示例。
- 更新 `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`, 标记 Docker、前端 Mock、Dora Adapter、基础日志、错误兜底等当前状态。
- 更新 `docs/12_CUSTOMER_HANDOFF.md`, 修正“尚未实现代码工程”的过期描述。

#### Verification

- 真实 Dora 控屏探测已执行 3 组问题: 普通“切换到组织建设”、强约束角色/JSON 指令、非法 action JSON 指令。
- 当前已发布 Agent “战区业绩分析Agent-刘峰”均未返回项目 `screen_control` JSON, 而是坚持战区业绩分析职责边界并返回自然语言 `answer`。
- Gateway 白名单路径本地验证通过: Dora-like 合法 `SWITCH_TAB_ORG` JSON 归一为 `screen_control`, Dora-like 非法 `UNKNOWN_ACTION` JSON 归一为 `fallback/ACTION_NOT_ALLOWED`。
- `/api/screen/execute` 复验通过: `SWITCH_TAB_ORG` 执行成功, `UNKNOWN_ACTION` 被拒绝。

#### Notes

- V0.2 代码侧已具备真实 Dora `screen_control` 接收和白名单校验能力。
- 真实 Dora 控屏端到端验证当前受阻于远端 Agent Prompt 未发布为党建大屏专用版本。
- 下一步需要在 Dora 后台发布 `docs/integrations/DORA_AGENT_PROMPT.md` 中的 Prompt, 或将 `.env` 指向一个已发布的党建大屏专用 Agent。

### V0.2 Dora 真实控屏联调完成

#### Completed

- 用户已在 Dora 后台发布专用 Agent: `中天证券党建大屏语音助手`。
- 独立 URL 已确认对应 OpenClaw agents 列表中的已发布 Agent `id=e969ca51-e898-440e-8ceb-b814d7fb83f6`。
- 本地 `.env` 已将 `DORA_AGENT_NAME` 从 `战区业绩分析Agent-刘峰` 切换为 `中天证券党建大屏语音助手`, `DORA_AGENT_ID` 保持为空。
- `.env.example` 已同步更新为 `DORA_AGENT_NAME=中天证券党建大屏语音助手`。
- 真实 Dora SSE 已验证 4 个白名单控屏动作: `SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_HOME`、`SWITCH_TAB_ACTIVITY`。
- 真实 Dora 非法页面“风险预警页面”返回 `fallback`, 未产生可执行 action。
- 真实 `/api/chat` HTTP 路径已验证 `screen_control` 返回和 `/api/screen/execute` 合法动作执行。

#### Verification

- `list_agents` 返回 313 个 Agent, 可精确匹配 `中天证券党建大屏语音助手`, 状态为 `PUBLISHED`。
- `resolve_agent_id` 在 `DORA_AGENT_ID` 为空时解析到新 Agent。
- 直接 Dora SSE 验证:
  - “请切换到组织建设页面” -> `screen_control` / `SWITCH_TAB_ORG`
  - “打开党员学习” -> `screen_control` / `SWITCH_TAB_STUDY`
  - “返回首页” -> `screen_control` / `SWITCH_HOME`
  - “请切换到党建活动页面” -> `screen_control` / `SWITCH_TAB_ACTIVITY`
  - “请打开风险预警页面” -> `fallback`
  - “入党流程是什么？” -> `answer`
- 临时设置 `ENABLE_MOCK_DORA=false` 后, `POST /api/chat` 输入“请切换到组织建设页面”返回 `screen_control` / `SWITCH_TAB_ORG`, 随后 `/api/screen/execute` 执行成功。
- 验证完成后已恢复运行态 `ENABLE_MOCK_DORA=true`, Mock smoke 通过。

#### Notes

- PowerShell / Docker CLI 直接传中文环境变量仍可能变成问号; 使用 `.env` 文件或 Unicode escape 可正常验证。
- PowerShell 控制台显示中文 JSON 时可能乱码; API 返回结构和类型校验正常。
- V0.2 Dora 接入阶段完成。下一阶段建议进入 V0.3 TTS / ASR。

### V0.3 TTS / ASR Adapter 最小实现准备

#### Completed

- 增加 `apps/api/app/services/asr_provider.py`, 定义 `AsrProvider`、`MockAsrProvider` 和真实 Provider 未配置时的安全兜底。
- 增加 `apps/api/app/services/tts_provider.py`, 定义 `TtsProvider`、`MockTtsProvider` 和真实 Provider 未配置时的安全兜底。
- `POST /api/asr/transcribe` 已支持 `mock_text` 和可选 `audio_base64` JSON 输入, Mock ASR 返回最终识别文本。
- `POST /api/tts` 已支持 Mock TTS 合成, 生成 WAV 文件并返回 `/api/tts/audio/{audio_id}`。
- `GET /api/tts/audio/{audio_id}` 已支持读取后端生成的 Mock TTS 音频, 并校验安全音频 ID。
- 前端增加语音输入面板, 支持浏览器录音、Mock ASR 文本提交、识别后自动进入 `/api/chat`。
- 前端在数字人回答后后台准备 TTS 音频, 展示“播报”按钮和原生音频控件; JS 播放路径使用 Web Audio API 更新语音能量条。
- `docker-compose.yml` 已补充 ASR / TTS 配置环境变量和 `TTS_CACHE_DIR`。
- 增加根目录 `.dockerignore`, 避免本机 `apps/web/node_modules` 污染 Docker build 上下文。
- 同步更新 `.env.example`、API 契约、数据契约、配置说明和 ASR/TTS 集成说明。

#### Changed Files

- `.dockerignore`
- `.env.example`
- `docker-compose.yml`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/asr_provider.py`
- `apps/api/app/services/tts_provider.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web install --frozen-lockfile` 完成依赖恢复。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `POST /api/asr/transcribe` 返回 `success=true`。
- `POST /api/tts` 返回 `success=true` 和 `format=wav`; `GET /api/tts/audio/{audio_id}` 下载到 28844 字节 WAV。
- `POST /api/chat` 使用 ASR 文本“返回首页”返回 `screen_control` / `SWITCH_HOME`。
- Codex 内置浏览器验证前端可点击“识别并发送”, 生成用户消息、数字人回复、`SWITCH_TAB_ORG` 动作和 TTS 原生音频控件; 控制台无 error。

#### Notes

- 当前未接入真实 ASR / TTS 供应商; `ENABLE_MOCK_ASR=false` 或 `ENABLE_MOCK_TTS=false` 时返回安全未配置错误。
- 浏览器自动播放策略可能阻止 JS 主动播放音频; 前端已改为后台准备音频并展示手动播报按钮和原生音频控件。
- PowerShell 控制台显示中文 JSON 时仍可能乱码; 结构化字段和浏览器链路验证正常。

### V0.3 阿里云百炼 ASR / TTS 真实配置

#### Completed

- 用户已完成人工验收 Mock 语音闭环。
- 用户已完成人工验收真实浏览器麦克风 ASR / TTS 语音闭环。
- 已确认 `compatible-mode/v1` 不是本项目 ASR / TTS 语音链路入口, 语音使用阿里云百炼 WebSocket `wss://dashscope.aliyuncs.com/api-ws/v1/inference`。
- 已根据阿里云文档选定 ASR `fun-asr-realtime` 和 TTS `cosyvoice-v3-flash`。
- 本地 `.env` 已配置阿里云百炼 ASR / TTS Key, 并切换 `ENABLE_MOCK_ASR=false`、`ENABLE_MOCK_TTS=false`; `.env` 不进入 Git。
- 后端新增阿里云 Fun-ASR WebSocket Provider, 支持 `run-task`、音频二进制上传、`finish-task` 和 `result-generated` 文本收敛。
- 后端新增阿里云 CosyVoice WebSocket Provider, 支持 `run-task`、`continue-task`、`finish-task`, 并将返回的二进制音频缓存为本地 mp3 / wav 等文件。
- 前端录音从 MediaRecorder WebM 改为 Web Audio 采集并编码 16k 单声道 WAV, 以适配 Fun-ASR。
- Docker / `.env.example` / 配置文档已补充 ASR / TTS WebSocket URL、模型、采样率、超时和音色配置。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/asr_provider.py`
- `apps/api/app/services/tts_provider.py`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/web/src/App.vue`
- `docker-compose.yml`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- 官方文档核对:
  - CosyVoice WebSocket API 使用 `wss://dashscope.aliyuncs.com/api-ws/v1/inference`, 鉴权头为 `Authorization: Bearer <api_key>`, 交互为 `run-task` -> `continue-task` -> 二进制音频 -> `finish-task`。
  - Fun-ASR WebSocket API 使用同一 WebSocket URL, `model=fun-asr-realtime`, 支持 `wav` / `mp3` 等音频格式。
  - CosyVoice `cosyvoice-v3-flash` 支持系统音色 `longanyang`。
- `docker run ... uv lock` 已刷新 `apps/api/uv.lock`。
- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose up -d --build` 通过。
- `GET /api/health` 返回 `status=ok`。
- 真实 TTS 英文和中文 UTF-8 请求验证通过, 返回 `success=true`, `provider=aliyun`, `format=mp3`; 中文 mp3 下载大小为 56515 字节。
- 真实 ASR 无音频请求返回 `ASR_AUDIO_REQUIRED`, 行为符合预期。
- 使用真实 TTS mp3 回灌 ASR 时, Fun-ASR 返回 `FLOW:AUDIO_DECODE_ERROR`; 判断为回灌音频编码不适合作 ASR 验证, 后续改用浏览器麦克风 16k WAV 实录验收。
- 用户人工验收通过: 浏览器麦克风 16k WAV 真实 ASR 可进入现有 `/api/chat` 和 TTS 链路。
- Codex 内置浏览器验证前端页面可渲染语音输入、录音、识别并发送控件, 控制台无 error。

#### Notes

- V0.3 阿里云百炼 ASR / TTS 最小真实接入已完成人工验收。
- 当前交互仍是按钮式录音 / 识别, 下一阶段进入 V0.4 语义唤醒 / 后台监听, 通过 VAD + 唤醒词减少后续点击。
- API Key 已出现在对话上下文中; 客户移交或正式演示前建议在阿里云百炼控制台轮换一次 Key。

### V0.4 语义唤醒 / 后台监听最小实现

#### Completed

- 增加 `apps/api/app/services/wake_words.py`, 从 `config/wake-words.yaml` 读取唤醒词配置。
- 增加 `GET /api/wake/config`, 返回唤醒词、VAD 阈值、短片段范围、冷却时间和唤醒后指令超时。
- `config/wake-words.yaml` 补充 `silence_ms`、`command_timeout_ms` 和 `vad_threshold`。
- 前端增加“后台监听”显式开关, 只在用户开启后请求麦克风权限。
- 前端增加 `idle` / `monitoring` / `wake_checking` / `recording` / `thinking` / `speaking` / `cooldown` 状态机展示。
- 前端增加本地 RMS 音量阈值 VAD, 只截取短音频片段并编码为 16k 单声道 WAV 后调用 `/api/asr/transcribe`。
- 唤醒词命中后, 如果同一句中已包含正式指令, 会去掉唤醒词后直接进入 `/api/chat`; 如果只有唤醒词, 会进入一次正式指令录音。
- 未命中唤醒词的短片段会丢弃并进入冷却, 不进入 `/api/chat`。
- 后台监听路径复用既有 ASR -> `/api/chat` -> TTS 链路, 并保留手动录音 / Mock ASR / 手动播报回退。
- 前端增加 Mock ASR “小天小天，请切换到组织建设页面”演示按钮。
- 同步更新 API 契约、数据契约、配置说明、测试计划、ASR/TTS 集成说明、风险和下一步文档。

#### Changed Files

- `config/wake-words.yaml`
- `config/README.md`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/wake_words.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回 `version=0.1.0`、`mode=semantic`、3 个唤醒词和 VAD 设置。
- 通过 Python Unicode escape 检查确认接口返回中文唤醒词为 `小天小天`、`中天小天`、`你好小天`。
- `GET http://localhost:18000` 返回 HTTP 200, 前端 JS / CSS 静态资源返回 HTTP 200。
- 容器日志未见启动错误。

#### Notes

- 当前会话未暴露 Codex in-app Browser 控制工具, Playwright 也未安装, 因此未完成浏览器控制台截图验证。
- 本轮未进行真实麦克风唤醒人工验收; 下一步需要在浏览器中点击“后台监听”, 用真实语音验证 VAD 阈值、唤醒命中率和浏览器自动播放策略。
- V0.4 仍不接 RAGFlow 和真实 FVS, 未改变 Dora / ASR / TTS / FVS Mock 开关。

### V0.4.1 连续对话窗口

#### Completed

- 用户已完成人工验收: V0.4 后台监听可唤醒后正常对话。
- `config/wake-words.yaml` 新增 `followup_enabled`、`followup_window_ms`、`max_followup_turns`。
- 后端 `WakeSettings` 新增连续对话窗口字段, `GET /api/wake/config` 可透出配置。
- 前端新增 `followup_listening` 状态, TTS 播报结束后进入短时追问窗口。
- 在 `followup_window_ms` 内用户可直接说下一句, 不需要再次说唤醒词。
- 达到 `max_followup_turns` 或追问窗口超时后, 前端进入冷却并回到唤醒监听。
- 自动播放被浏览器拦截、TTS 播放失败或 TTS 合成失败时, 已显示文字 / 音频控件并尽量进入追问窗口或安全回到监听。
- 监听卡片展示连续对话轮数, 便于现场验收。
- 同步更新 API 契约、数据契约、配置说明、测试计划、ASR/TTS 集成说明、风险和下一步文档。
- 用户已完成人工验收: V0.4.1 连续对话窗口可在播报结束后直接追问, 并能按超时 / 最大轮数退出。
- 文档状态已推进到 V0.5 RAGFlow MCP。

#### Changed Files

- `config/wake-words.yaml`
- `config/README.md`
- `apps/api/app/models.py`
- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回 `followup_enabled=true`、`followup_window_ms=12000`、`max_followup_turns=3`。
- `GET http://localhost:18000` 返回 HTTP 200。

#### Notes

- 本轮未接 RAGFlow 和真实 FVS。
- 当前运行态 `/api/chat` 仍是 `ENABLE_MOCK_DORA=true` 的 Mock Dora。
- 下一步进入 V0.5 RAGFlow MCP; 如需验证 Dora 调用 RAGFlow, 需要显式切换真实 Dora。

### V0.5 RAGFlow MCP 本地部署准备

#### Completed

- 用户提供远端服务器部署信息后, 先探测服务器 Docker / Compose / 内存 / 磁盘 / `vm.max_map_count`。
- 远端服务器 Docker 可用, 但内存约 7.5GiB, 低于 RAGFlow 官方建议的 16GiB; 初次尝试按 RAGFlow `v0.25.6` 拉起 CPU 版时发现默认端口冲突和 Elasticsearch profile 未启动问题。
- 用户中断远端部署并要求改为本地部署后, 已清理远端服务器本轮创建的 RAGFlow 容器、卷、网络和目录; 清理后目标目录不存在, RAGFlow 容器和卷无残留。
- 在本地 `D:\Project\ragflow` 克隆 RAGFlow 官方仓库 `v0.25.6`。
- 修改本地 RAGFlow `docker/.env`, 使用高位端口避免与当前 POC 前后端冲突: Web `18089`, API `19380`, MCP `19382`, MySQL `13306`, Redis `16379`, Elasticsearch `11200`, MinIO `19000/19001`。
- 通过 Docker Desktop 启动 RAGFlow CPU + Elasticsearch profile, 容器包括 `ragflow-cpu`、`es01`、`mysql`、`redis`、`minio`。
- 创建本地 RAGFlow 测试用户, 生成 self-host MCP API token, 并将 `RAGFLOW_MCP_HOST_API_KEY` 写入 `D:\Project\ragflow\docker\.env`; token 未写入本项目 Git 文档。
- 修改本地 RAGFlow `docker-compose.yml`, 在 `ragflow-cpu` 中启用 `--enable-mcpserver`、`--mcp-mode=self-host` 和 `/mcp` / `/sse` 传输。
- 新增 `docs/demo_knowledge/` 8 份最小党建知识库测试资料, 覆盖 3 位领导、2 篇新闻、3 份党建制度 / 流程文档。
- 更新 RAGFlow 集成说明, 记录本地路径、端口、MCP 地址、启动命令、验证结果和 Dora 远程可达性边界。
- 用户将临时公网域名映射到本机 MCP 端口后, 已验证 `http://liuchenxiang.uk:19382/mcp` 可完成 MCP 初始化和工具列表获取。

#### Changed Files

- `docs/demo_knowledge/`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- 远端清理验证: `/tmp/zfsv3/nvme12/18722229125/data/Docker/ragflow` 删除成功; 本轮创建的 RAGFlow 容器和卷无残留。
- 本地 Docker Desktop 可用: Docker Server `29.5.2`, Compose `v5.1.3`, Docker Desktop 内存约 16.5GB。
- `docker compose -f docker-compose.yml --profile cpu --profile elasticsearch config --services` 返回 `mysql`、`ragflow-cpu`、`redis`、`es01`、`minio`。
- `docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d` 成功启动本地 RAGFlow。
- `GET http://127.0.0.1:18089/` 返回 HTTP 200, 页面标题为 `RAGFlow`。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回 HTTP 200, `db` / `doc_engine` / `redis` / `storage` / `status` 均为 `ok`。
- RAGFlow MCP 日志显示 `Streamable HTTP endpoint available at /mcp` 和 `Uvicorn running on http://0.0.0.0:9382`。
- `GET http://127.0.0.1:19382/sse` 返回 HTTP 200 和 `text/event-stream`。
- `GET http://127.0.0.1:19382/mcp` 返回 HTTP 406, 提示客户端需要 `Accept: text/event-stream`, 说明 `/mcp` 端点已监听但需 MCP client 正确握手。
- `POST http://liuchenxiang.uk:19382/mcp` 的 MCP `initialize` 返回 HTTP 200, server 为 `ragflow-mcp-server`, protocolVersion 为 `2025-03-26`。
- `POST http://liuchenxiang.uk:19382/mcp` 的 MCP `tools/list` 返回 `ragflow_retrieval` 工具。
- `tools/call ragflow_retrieval` 当前返回 `No accessible datasets found.`, 与尚未导入 RAGFlow dataset 的状态一致。

#### Notes

- 本轮尚未在 RAGFlow Web 中导入 `docs/demo_knowledge/` 到 dataset, 也未创建 chat / assistant。
- 本轮尚未验证 Dora 通过 MCP 调用 RAGFlow 返回知识库答案; 当前 MCP 链路已通, 但 RAGFlow 还没有可访问 dataset。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 RAGFlow Dataset 导入和解析

#### Completed

- 在本地 RAGFlow 中创建 dataset `zt_party_building_demo`, ID 为 `d7481bc0649311f18b616324ad8eb1c0`。
- 上传 `docs/demo_knowledge/` 下 8 份测试 Markdown, 排除目录说明 `README.md`。
- 首次触发解析后 8 份文档均失败, 失败原因为 `No default embedding model is set.`。
- 使用本地 `.env` 中已有阿里云百炼 / DashScope Key, 在 RAGFlow 中验证并配置默认 Embedding `text-embedding-v3@Tongyi-Qianwen`; Key 未写入项目文档或 Git。
- 将 `zt_party_building_demo` 的 Embedding 更新为 `text-embedding-v3@Tongyi-Qianwen`。
- 为最小 Markdown 解析关闭 `zt_party_building_demo` 的 RAPTOR / GraphRAG, 避免额外依赖默认 Chat 模型。
- 重新触发解析后, 8 份测试文档全部解析完成, 均为 `DONE`。
- 通过本地 MCP 和临时公网 MCP 验证 `ragflow_retrieval` 可返回知识库 chunk。

#### Changed Files

- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- RAGFlow healthz 仍返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- `zt_party_building_demo` dataset 创建成功。
- 8 份文档解析结果:
  - `leader_zhang.md`: `DONE`, 1 chunk, 233 tokens。
  - `leader_li.md`: `DONE`, 1 chunk, 165 tokens。
  - `leader_wang.md`: `DONE`, 1 chunk, 149 tokens。
  - `news_2026_party_research.md`: `DONE`, 1 chunk, 189 tokens。
  - `news_2026_org_building.md`: `DONE`, 1 chunk, 171 tokens。
  - `party_study_policy.md`: `DONE`, 1 chunk, 221 tokens。
  - `join_party_process.md`: `DONE`, 1 chunk, 229 tokens。
  - `branch_org_building_standard.md`: `DONE`, 1 chunk, 229 tokens。
- 本地 MCP `tools/call ragflow_retrieval` 输入“张书记最近调研了什么?”返回 `leader_zhang.md` / `news_2026_party_research.md` 相关 chunk。
- 公网 MCP `tools/call ragflow_retrieval` 输入“入党流程是什么?”返回 `join_party_process.md` 相关 chunk。

#### Notes

- 当前 RAGFlow 尚未配置默认 Chat 模型, 因此 `ragflow_retrieval` 使用 `keyword=false` 可正常向量检索; 使用 `keyword=true` 会报 `No default chat model is set.`。
- 尚未创建 RAGFlow chat / assistant。
- 尚未验证 Dora Agent 通过 MCP 调用 RAGFlow 后返回最终自然语言知识库答案。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 Dora 通过 MCP 调用 RAGFlow 知识库验证

#### Completed

- 根据用户确认的边界调整 V0.5 方案: Dora 负责最终回答, RAGFlow 负责检索, MCP 调用固定 `keyword=false`。
- 将本地 `.env` 切换为 `ENABLE_MOCK_DORA=false`, 并重建 `zt-digital-human-api` 容器。
- 通过 `/api/chat` 调用真实 Dora OpenClaw SSE, Dora Agent 已接入公网 MCP `http://liuchenxiang.uk:19382/mcp`。
- 验证 Dora 可通过 MCP 调用 RAGFlow `zt_party_building_demo` dataset, 并返回项目契约中的 `answer`。
- 明确 RAGFlow 默认 Chat 模型和 chat / assistant 不再作为 V0.5 必需项; 仅在启用 `keyword=true`、TOC enhance、KG retrieval 或 RAGFlow 自答时需要。

#### Changed Files

- `.env`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/integrations/DORA_AGENT_PROMPT.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- `docker compose up -d --force-recreate api` 成功重建 API 容器。
- API 容器环境确认 `ENABLE_MOCK_DORA=false`, `DORA_AGENT_NAME=中天证券党建大屏语音助手`。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- `/api/chat` 输入 `张书记最近调研了什么?` 返回 `answer`, 内容包括基层营业部党建调研、党员学习、组织生活和党建引领业务发展。
- `/api/chat` 输入 `入党流程是什么?` 返回 `answer`, 内容包括递交申请、谈话、积极分子、培养考察、发展对象、政治审查、预备党员和转正。
- `/api/chat` 输入 `党员学习制度有哪些要求?` 返回 `answer`, 内容包括按月集中学习、计划 / 签到 / 台账、学习内容、补学整改和综合评价。
- `/api/chat` 输入 `党支部组织建设规范是什么?` 返回 `answer`, 内容包括组织设置、职责分工、三会一课、主题党日、党员发展、党费收缴和整改闭环。
- RAGFlow 日志在 Dora 测试期间出现 `POST /mcp` 和 `POST /api/v1/retrieval` 成功记录。

#### Notes

- 首次脚本验证时受 PowerShell 中文编码影响, Dora 收到问号乱码并返回编码提示; 已改用 Unicode escape 构造 JSON 后验证通过。
- `我是张书记, 请给我欢迎语。` 可返回欢迎语, 但未明显引用领导资料中的近期关注方向, 后续可通过 Dora Prompt 单独优化。
- `请严格依据知识库回答: 党支部组织建设规范是什么?` 触发了 RAGFlow retrieval, 但 Dora 最终返回 `fallback`; 记录为 Dora Agent 工具结果转回答的 Prompt 稳定性边角问题。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 Dora MCP 工具消息解析修复

#### Completed

- 复现用户在前端问“入党流程是什么?”和“张书记最近调研了什么?”时返回兜底话术的问题。
- 通过 `session_logs` 确认前端问题已进入 `/api/chat`, Dora 返回被 Gateway 归一为 `DORA_OUTPUT_INVALID: Dora output type is unsupported`。
- 通过 RAGFlow 日志确认同一时间已有 `POST /mcp` 和 `POST /api/v1/retrieval -> 200`, 说明 MCP 和 RAGFlow 检索成功。
- 抓取 Dora SSE 原始事件后定位原因: Dora 的 `messages` 流会先输出 MCP ToolMessage 原始 JSON chunks, 再输出最终回答; Gateway 旧逻辑把工具 JSON 和最终回答拼接后优先解析到前面的 `{"chunks": ...}`, 导致 unsupported fallback。
- 修改 `DoraClient._extract_text`, 忽略 `type=tool` / `ToolMessage` / `ToolMessageChunk` 的工具原始消息, 只收集最终 AI 回答内容。
- 重建 API 容器并复测通过。

#### Changed Files

- `apps/api/app/services/dora_client.py`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/integrations/DORA_INTEGRATION.md`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`

#### Verification

- `docker compose up -d --build api` 成功。
- `docker exec zt-digital-human-api uv run python -m compileall app` 通过。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- 新 session 输入 `入党流程是什么?` 返回 `type=answer`, 内容为 8 个入党流程环节。
- 新 session 输入 `张书记最近调研了什么?` 返回 `type=answer`, 内容为 2026 年 5 月基层营业部党建调研和 2026 年 6 月党建引领业务发展专题会议。
- 用户前端实际 session `demo-session-1781074089384` 复测以上两个问题也均返回 `type=answer`。

#### Notes

- 该问题不是 RAGFlow 未检索到, 而是 Gateway 解析 Dora SSE 时误把工具原始 JSON 当成最终回答解析。
- 当前修复不改变 API 契约, 只增强 Dora SSE 事件收敛逻辑。

### V0.5 RAGFlow MCP 返回量瘦身与分段 TTS 流式优化

#### Completed

- 根据用户要求, 暂不改 Dora 侧配置, 改为在本地 RAGFlow MCP server 和本地 POC Gateway / 前端优化慢交互。
- 修改 `D:\Project\ragflow\mcp\server\server.py`, 对 `ragflow_retrieval` 做 POC 返回量瘦身:
  - 强制 `keyword=false`。
  - 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`。
  - 单 chunk content 最长 1200 字符。
  - chunk 只返回 `content`、`document_name`、`document_id`、`dataset_id`、`similarity`。
  - 去掉每次 retrieval 额外拉取 document / dataset metadata cache 的步骤。
- 修改 `D:\Project\ragflow\docker\docker-compose.yml`, 将 `../mcp/server/server.py` 只读挂载到 `ragflow-cpu` 容器内 `/ragflow/mcp/server/server.py`。
- 重建 `ragflow-cpu`, 验证容器内已使用瘦身后的 MCP server 脚本。
- 新增后端 `POST /api/chat/stream`, 在真实 Dora 模式下消费 Dora OpenClaw SSE, 输出 `metadata`、`dora_delta`、`tts_ready`、`tts_error`、`answer`、`end`。
- 后端流式路径会从 Dora 最终回答 JSON 的 `speak_text` 中增量提取文本, 并按短段并发调用现有 TTS Provider。
- 若 Dora 某次只给最终 answer, 后端仍会把最终 `speak_text` 分段合成, 避免整段 TTS 阻塞。
- 前端优先调用 `/api/chat/stream`, 收到 `tts_ready` 后按 `index` 顺序播放分段音频; 流式失败时回退到原 `/api/chat` + `/api/tts`。
- 修复分段播放锁: 前端消息 ID 保持稳定, 避免 answer 事件到达后改 ID 导致重复拉起播放队列。
- 修复并发分段 TTS 到达顺序问题: 原生音频控件始终指向当前最早分段。

#### Changed Files

- `apps/api/app/main.py`
- `apps/api/app/services/dora_client.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/integrations/DORA_INTEGRATION.md`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `D:\Project\ragflow\mcp\server\server.py`
- `D:\Project\ragflow\docker\docker-compose.yml`

#### Verification

- `docker compose -f D:\Project\ragflow\docker\docker-compose.yml --profile cpu --profile elasticsearch config --services` 通过。
- `docker compose -f D:\Project\ragflow\docker\docker-compose.yml --profile cpu --profile elasticsearch up -d --force-recreate ragflow-cpu` 成功。
- RAGFlow healthz 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- 容器内 `grep` 验证 `/ragflow/mcp/server/server.py` 包含 `POC_MAX_PAGE_SIZE` 和精简 chunk payload 注释。
- `docker exec zt-digital-human-api uv run python -m compileall app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 通过。
- `docker compose up -d --build api web` 通过, API 和 Web 容器均为 `running`。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回全部 `ok`。
- 普通 `/api/chat` 输入 `入党流程是什么?` 返回 `type=answer`, 耗时约 20.0s。
- `/api/chat/stream` 输入 `入党流程是什么?` 验证通过: 本轮抽样中首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s, 全部分段 TTS 约 15.1s 到 27.1s 就绪。

#### Notes

- 当前优化不是音频字节级真流式 TTS, 而是“Dora 文本增量 + 短文本分段 TTS 文件 + 前端按段播放”。
- 当前最大剩余耗时仍在 Dora 工具调用前决策和工具结果后的回答生成; RAGFlow 检索自身通常不是主要瓶颈。
- 本轮未修改 Dora 侧 MCP 配置, 未接真实 FVS。

### V0.5 / V0.6 问数测试 Excel 数据准备

#### Completed

- 新增 `docs/demo_data/ask_metrics/` 目录, 存放党建问数功能测试用脱敏 Excel 样例数据。
- 生成 3 份 `.xlsx`:
  - `zt_party_study_metrics_2026.xlsx`: 党员学习数据, 覆盖党员总数、学习完成率、支部完成率、学习时长、测试成绩和心得提交情况。Dashboard 口径为党员总数 128 人、已完成学习 112 人、完成率 87.5%。
  - `zt_party_org_life_metrics_2026.xlsx`: 组织生活与党建活动数据, 覆盖活动完成率、主题党日次数、参会率、整改事项和闭环率。
  - `zt_party_development_metrics_2026.xlsx`: 党员发展流程数据, 覆盖申请人、入党积极分子、发展对象、预备党员、本年转正、材料状态和政审状态。
- 每份 Excel 均包含 Dashboard、明细 / 汇总表和字段说明, 并包含适合问数测试的示例问题。
- 新增 `docs/demo_data/ask_metrics/README.md`, 记录文件清单、典型问数问题和口径说明。

#### Changed Files

- `docs/demo_data/ask_metrics/README.md`
- `docs/demo_data/ask_metrics/zt_party_study_metrics_2026.xlsx`
- `docs/demo_data/ask_metrics/zt_party_org_life_metrics_2026.xlsx`
- `docs/demo_data/ask_metrics/zt_party_development_metrics_2026.xlsx`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`

#### Verification

- 三份 Excel 文件均已生成到 `docs/demo_data/ask_metrics/`。
- 使用 spreadsheet runtime 重新导入三份 Excel, 检查 Dashboard 关键区域可读取。
- 三份 Excel 均完成公式错误扫描, 未发现 `#REF!`、`#DIV/0!`、`#VALUE!`、`#NAME?` 或 `#N/A`。
- 对每份工作簿的 Dashboard 和主要表头区域完成渲染预览检查。

#### Notes

- 本轮只准备问数测试数据源, 尚未实现 Dora / Gateway 对 Excel 的真实问数解析或查询链路。
- Excel 内容为脱敏演示样例, 不包含真实客户或员工数据。

### V0.5 人工验收确认

#### Completed

- 用户确认 V0.5 RAGFlow MCP 阶段人工验收完成。
- V0.5 验收范围已覆盖:
  - 本地 RAGFlow Docker Desktop 部署和健康检查。
  - `zt_party_building_demo` dataset 导入 8 份测试资料并解析完成。
  - Dora Agent 通过公网 MCP 调用 RAGFlow `ragflow_retrieval(keyword=false)`。
  - Gateway 忽略 Dora SSE 中 MCP ToolMessage 原始 chunks, 避免误解析工具结果。
  - RAGFlow MCP 返回量瘦身。
  - `/api/chat/stream` 与前端分段 TTS 播放优化。
  - 前端 / 语音链路人工体验验收。
- 项目阶段推进到 V0.6 FVS 真实集成准备。

#### Changed Files

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`

#### Verification

- 人工验收结论来自用户确认: “V0.5确认验收，我人工验收完成了”。
- 本轮未新增代码变更, 无需重新构建前后端。

#### Notes

- V0.5 关闭后, 下一阶段默认进入 V0.6 FVS 真实集成。
- FVS 真实集成必须继续使用 `action_id` + 后端白名单校验, 不允许执行模型生成 JavaScript。

### V0.6 FVS iframe page_number 切页准备

#### Completed

- 用户提供本机 FVS 测试看板 URL, 入口参数为 `page_number=1`。
- 直接请求本机 FVS URL 返回 HTTP 200, 但响应头包含 `X-Frame-Options: SAMEORIGIN`, 跨端口 iframe 会被浏览器拦截。
- 新增 Web Nginx `/webroot/` 同源反向代理, 将请求转发到 `http://host.docker.internal:8075/webroot/`。
- 本地 `.env` 的 `VITE_FVS_URL` 改为相对路径 `/webroot/decision/view/duchamp?...&page_number=1`, `VITE_FVS_TARGET_ORIGIN` 置空。
- 新增 ADR-0008 记录 FVS 同源代理决策。
- 确认测试看板页面映射:
  - 1: 总览
  - 2: 成品库存
  - 3: 生产管理
  - 4: 设备分析
- `config/screen-actions.yaml` 已同步为 `gotoPage` + `pageNumber=1/2/3/4`。
- 前端 FVS Adapter 在 iframe 模式下优先识别 `params.pageNumber`, 并改写 FVS iframe URL 的 `page_number` 参数。
- 前端新增直接控屏按钮, 点击后仍调用 `/api/screen/execute` 做后端白名单校验, 不绕过安全路径。
- 示例输入按钮改名为 `输入总览`、`输入库存`、`输入生产`, 避免与直接控屏按钮同名。
- Dora Prompt、数据契约、API 契约、测试计划、FVS 集成说明和客户动作清单已同步当前四页测试映射。

#### Verification

- `GET /api/screen/actions` 可返回四个 `gotoPage` 动作及 `pageNumber=1/2/3/4`。
- `POST /api/screen/execute` 合法动作 `SWITCH_TAB_ORG` 返回 `success=true`。
- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build web` 成功。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- `GET http://127.0.0.1:18000/webroot/decision/view/duchamp?...&page_number=1` 经同源代理返回 HTTP 200。
- Codex 内置浏览器验证 FVS iframe 使用同源 `/webroot/...` 地址后看板可见。
- Codex 内置浏览器验证直接控屏按钮 `总览`、`成品库存`、`生产管理`、`设备分析` 分别切到 `page_number=1/2/3/4`, 最近动作显示 `iframe:gotoPage`, 控制台无 error。

#### Notes

- 当前方案优先使用 FVS URL 分页参数, 不要求 FVS 页面先预埋 `message` 监听脚本。
- 如果后续要控制分页以外的组件状态, 再走 `postMessage` / FVS 侧固定 `action_id` 映射。
- 正式环境需要确认是否部署同源代理, 或由 FVS 侧调整 iframe 允许策略。

### V0.6 FVS 主画布悬浮语音层与等待提示音

#### Completed

- 按用户要求将 FVS iframe host 模式调整为 FVS 主体画布, FVS iframe 铺满整个浏览器视口。
- 未唤醒 / 未处理语音时, 页面上层只保留右下角圆形麦克风语音交互入口。
- 唤醒、正式录音、连续追问、思考、TTS 加载或播报时, 右下角展开为悬浮语音面板。
- FVS 主画布展开态只保留语音监听状态、波形动画和对话文字记录; 文本表单、Mock ASR 输入、Demo 按钮和直接控屏调试栏已隐藏。
- 正式指令或连续追问进入处理后, 前端立即播报等待提示语音 `收到, 正在为您查找信息。`。
- 等待提示优先使用后端 TTS 预热音频; 如音频尚未就绪, 使用浏览器 `speechSynthesis` 本地兜底。
- AI 结果 TTS 与等待提示共用播放通道; AI 结果音频开始播放时会清理并打断等待提示, 优先播报最终回答。
- 新增 ADR-0009, 记录 FVS 主画布悬浮语音层和等待提示音打断策略。

#### Changed Files

- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/decisions/ADR-0009-fvs-floating-voice-overlay.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose up -d --build web` 成功, API 和 Web 容器均已重建并启动。
- Codex 内置浏览器打开 `http://127.0.0.1:18000` 验证: FVS iframe 使用同源 `/webroot/...` 地址, 视口内铺满 1280x720。
- Codex 内置浏览器验证未唤醒状态: `.conversation-panel.compact` 为 76x76, 右下角只显示麦克风入口; `voice-monitor`、`fvs-log`、`screen-action-row`、`chat-form`、`demo-row` 和 Mock ASR 输入均不可见; 控制台无 error。

#### Notes

- 本轮未在浏览器中接受麦克风权限, 因此真实唤醒展开、等待提示音自动播放和 AI 结果打断等待提示仍需用户现场人工验收。
- FVS 页面底部的 FineVis 未注册提示来自 FVS 本身, 不是本项目悬浮语音层。

### V0.6 人工验收确认

#### Completed

- 用户确认 V0.6 FVS 真实集成阶段人工验收完成。
- V0.6 验收范围已覆盖:
  - 数字人前端主页面 iframe 嵌入 FVS 看板。
  - Web Nginx `/webroot/` 同源代理加载本机 FVS。
  - `page_number=1/2/3/4` 对应 `总览`、`成品库存`、`生产管理`、`设备分析` 四页切换。
  - FVS 主画布未唤醒时仅显示角落语音 icon。
  - 唤醒 / 连续追问 / 思考 / 播报时展开悬浮语音动画和文字记录。
  - 等待提示音和 AI 结果 TTS 优先打断策略。
- 项目阶段推进到 V0.7 POC 稳定版。

#### Changed Files

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/decisions/ADR-0007-fvs-iframe-host.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/customers/zt-securities/SCREEN_ACTIONS.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- 人工验收结论来自用户确认: “0.6验收完成”。
- 本轮未新增代码变更, 无需重新构建前后端。

#### Notes

- V0.7 默认不再扩展新的外部系统能力, 优先形成稳定 POC 包和验收交付资料。
- 分页以外的 FVS 组件级控制仍作为后续增强项, 不影响 V0.6 验收结论。
