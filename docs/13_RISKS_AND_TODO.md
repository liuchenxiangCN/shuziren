# 风险与遗留事项

本文档记录项目风险、限制和待确认事项。风险状态应随着开发和联调持续更新。

## 风险清单

| 编号 | 风险 | 影响 | 控制措施 | 状态 |
| --- | --- | --- | --- | --- |
| R-001 | Dora 无法访问本地 RAGFlow MCP | 知识库链路不通 | 本地 RAGFlow MCP 已在 `127.0.0.1:19382` 启动; 临时公网 `http://liuchenxiang.uk:19382/mcp` 已通过 MCP initialize、tools/list、retrieval 和 Dora Agent 真实知识库问答验证 | Closed |
| R-002 | FVS 禁止被数字人主页面 iframe 嵌入 | 当前推荐方案无法显示真实 FVS 看板 | 本机 FVS 曾通过 Web Nginx 同源代理 `/webroot/ -> http://host.docker.internal:8075/webroot/` 解决跨端口 iframe; 2026-06-16 上线前 smoke 当前 `/webroot/...` 返回 502, 说明本机 / 正式 FVS 代理未就绪, 生产环境仍需确认同源代理、反向代理路径或 FVS 侧允许嵌入策略 | Open |
| R-003 | FVS iframe 动作通信未预埋监听 | 分页以外的组件级动作无法控制 | 当前四个测试页先通过 `page_number` URL 参数切换, 不依赖 FVS 侧监听; 组件级控制再预埋 `message` 监听或 Adapter, 只按 `action_id` 固定映射真实控制 API | Open |
| R-004 | 云 ASR 识别不准 | 语音体验差 | 增加热词、换供应商、优化麦克风 | Open |
| R-005 | TTS 延迟高 | 播报慢 | V0.5 已新增 `/api/chat/stream` 和分段 TTS; V0.6 已新增等待提示音和 AI 结果打断; V0.8 已实现 TTS 字节级真流式和分段 fallback; V0.9 已补充 TTS 分段异常安全提示 | Mitigated |
| R-006 | Dora 输出格式不稳定 | 前端解析失败 | Gateway 做 JSON 修复和容错; 已修复 Dora SSE 中 MCP ToolMessage 原始 JSON chunks 被误解析为最终回答的问题 | Open |
| R-007 | RAGFlow 检索质量一般或返回量过大 | 知识问答效果差 / Dora post-tool 变慢 | V0.5 已在本地 RAGFlow MCP server 固定 `keyword=false` 并瘦身返回字段、`page_size`、`top_k`、相似度阈值和 chunk 长度; 后续仍需结合真实文档调切片和召回 | Open |
| R-008 | 问数口径不清 | 回答不准 | V0.7 已采用 Gateway 本地只读 Excel Adapter 承接脱敏样例问数, 并验证 11 个固定问题; 正式客户真实数据源和指标口径仍需确认 | Mitigated |
| R-009 | 大模型误触发控屏 | 页面误切换 | action 白名单 + 二次校验 | Open |
| R-010 | 证券客户合规要求高 | 云模型受限 | POC 前确认云模型、数据范围、脱敏策略 | Open |
| R-011 | 本机 pnpm / uv / Python 版本与 PATH 可能不一致 | 非 Docker 本地开发会受阻 | 2026-06-15 已确认 `uv` 安装在 `C:\Users\nifen\.local\bin\uv.exe`, 可用 uv Python 3.12.13 创建本地 `.venv` 并完成 FastAPI TestClient smoke; 当前 PowerShell PATH 尚未刷新, 需要用绝对路径或重启终端后再用 `uv` 命令 | Mitigated |
| R-012 | 当前真实 Dora Agent 尚未按党建大屏 JSON Prompt 固化 | 真实 `screen_control` 可能无法稳定输出项目动作 JSON | 已发布专用 Agent `中天证券党建大屏语音助手`, 真实控屏端到端验证通过 | Closed |
| R-013 | 浏览器自动播放策略阻止 TTS 主动播报 | 数字人回答后不能自动发声, 等待提示音也可能被拦截 | V0.3 改为后台合成音频, 展示手动播报按钮和原生音频控件; V0.6 等待提示优先预热后端 TTS, 并用浏览器 `speechSynthesis` 兜底, 当前环境已通过人工验收; 正式客户环境仍需演示前检查播放权限 | Mitigated |
| R-014 | 百炼 API Key 已出现在对话上下文中 | 密钥泄露风险升高 | `.env` 不入 Git, 前端不暴露 Key; 2026-06-16 已验证前端 bundle、Ops 导出、config effective/schema 未返回本地实际 secret 值; 但供应商控制台轮换无法由本机完成, 客户移交或正式演示前仍必须在百炼 / 相关供应商控制台轮换 Key | Open |
| R-015 | 真实 ASR 麦克风链路验收风险 | 语音输入可能受浏览器权限、麦克风或音频格式影响 | 前端已改为 16k 单声道 WAV; 用户已完成人工验收 | Closed |
| R-016 | 浏览器后台监听受权限、焦点、现场噪声和自动播放策略限制 | 免点击体验可能无法在所有演示环境稳定运行 | V0.4 已实现用户显式启用开关 + 本地 VAD 截段 + 唤醒词 ASR 判断 + 手动按钮回退, 且真实唤醒已人工验收; V0.4.1 连续对话窗口和 V0.6 FVS 悬浮语音层均已人工验收; 2026-06-11 已补充唤醒成功“您好。”语音反馈和未命中不展开策略; 同日针对高失败率增加 VAD 预录缓冲、ASR 同音字归一化、长唤醒词优先剥离和更宽松的客户唤醒参数; 已新增播报中长唤醒词确认打断, 只认 `barge_in_wake_words`, 仍需现场连续复测成功率和误唤醒 / 误打断率 | Mitigated |
| R-017 | RAGFlow 默认 Chat 模型未配置 | `keyword=true`、TOC enhance、KG retrieval 或 RAGFlow 自己生成回答不可用 | V0.5 已明确 Dora 负责最终回答、RAGFlow 只做 `keyword=false` 向量检索; Dora MCP 问答已通过, 默认 Chat 模型不再是当前阻断项 | Open |
| R-018 | Dora 通用问数结果不稳定或无法说明口径 | 客户可能质疑问数准确性 | V0.8 已新增 `ASK_METRICS_MODE=excel|dora|auto`, 保留 Excel fallback; Dora 问数必须带来源、口径、时间范围或无法确认说明, 后续仍需结合真实 Dora 数据源验证 | Open |
| R-019 | TTS 字节级真流式在浏览器播放或供应商协议上不稳定 | 播报卡顿、打断失败或无法播放 | V0.8 第二阶段已实现 `POST /api/tts/stream` + PCM Web Audio 播放, 并保留 `TTS_STREAMING_FALLBACK=segment`; 2026-06-16 上线前接口级 smoke 可收到真实 TTS stream metadata / audio_chunk; 真实浏览器自动播放、等待提示音打断和播报中打断仍需客户现场人工复测 | Mitigated |
| R-020 | 运维监控 / 日志看板暴露敏感信息 | 泄露 API Key、供应商响应或客户数据 | V0.8 第三阶段已实现只读脱敏 Ops API; 会话摘要和导出内容会截断并脱敏常见 Key / Token / Bearer / `sk-*` / `ak-*` 模式; 依赖探测不返回供应商原始响应 | Mitigated |
| R-021 | 客户私有配置覆盖顺序不清或配置漂移 | 同一套代码在不同客户环境表现不一致 | V0.8 第一阶段已实现默认配置 + 客户覆盖层 + 环境变量显式覆盖规则, 并通过容器内配置检查验证 `zt-securities` 客户目录生效 | Mitigated |
| R-022 | 运维看板当前未接入登录鉴权 | 本地 POC 之外访问可能泄露会话摘要或排障信息 | 当前仅按本地 POC 内网使用; Ops API 做脱敏和截断; 运维入口已从 FVS 主画布移除并改为 `/ops`; 2026-06-16 Docker Compose 默认 API / Web 端口已绑定 `127.0.0.1`, 但正式跨机器访问仍需反向代理鉴权、网关 ACL 或仅内网策略 | Mitigated |
| R-023 | 演示稳态模式掩盖真实依赖不可用 | 现场演示通过但真实 Dora / RAGFlow / ASR / TTS 未验收 | V0.9 已将 `DEMO_STABLE_MODE` 做成显式开关; 前端显示“演示稳态”; `scripts/check-poc.ps1 -RequireServices` 和 Ops 看板仍展示真实依赖状态; V1.0 验收报告需记录是否开启 | Open |
| R-024 | Docker 原生日志可能包含未脱敏运行信息 | 日志包误带外部库噪声或敏感响应 | V0.9 `scripts/export-logs.ps1` 默认只导出脱敏 Ops Markdown / JSON 和 Compose 状态; Docker 原生日志必须显式使用 `-IncludeDockerLogs` | Mitigated |
| R-025 | V1.0 现场验收附件和签字尚未补齐 | 交付包已输出, 但客户正式签收仍缺现场截图、真实依赖确认、麦克风 / 播放权限复核和签字 | V1.0 验收报告已预留 S-001 到 S-007 截图附件位, 客户移交清单已列出签收项; 下一步按 `docs/delivery/v1.0/` 执行现场复演并归档最终日志包 | Open |
| R-026 | 指定新闻网站 / 新闻源白名单暂未确认 | 自定义爬虫范围、解析策略和验收样例无法最终落定 | 客户汇报计划中先采用“客户确认的新闻源白名单 / 可配置新闻源”口径; 下一步需确认新闻源、采集字段、频率和失败兜底 | Open |
| R-027 | 自定义新闻爬虫存在合规、版权、频控和 SSRF 风险 | 可能访问未授权内容、触发网站限制或被滥用访问内网地址 | 仅采集公开页面; 遵守新闻源访问规则; 后端做 URL 白名单和内网地址拦截; 增加限频、日志审计和脱敏; 前端不得直接抓取新闻站点 | Open |
| R-028 | 指定人员同名或资料来源可信度不足 | 导入知识库后可能混入错误人员信息, 影响回答可信度 | 采集时增加单位、职务、关键词约束; 整理阶段保留来源 URL、发布时间和置信度; 低置信度内容进入待确认状态 | Open |
| R-029 | RAGFlow 导入解析状态不稳定或耗时不可控 | 新增资料无法按时进入 MCP 检索, 影响 6/30 上线验收 | 导入 Adapter 需记录批次日志、轮询解析状态、失败重试和小批量导入; 验收前准备人工导入兜底 | Open |
| R-030 | 临时宣传分支内容污染主线 | 后续架构和配置中心设计可能误把临时录屏页面、专用资产或临时动作白名单当成主线能力 | 2026-06-15 已删除本地临时宣传分支, 清理主线运行目录中的录屏页面、专用组件、临时客户配置、临时资产、临时 ADR 和财务录屏动作白名单; 后续阶段 0A 固化主线清洁搜索门禁 | Mitigated |
| R-031 | 配置页泄露敏感配置 | Dora / ASR / TTS Key、Token、数据库 DSN 或供应商密钥可能通过前端泄露 | 阶段 1 已新增脱敏只读 `GET /api/config/effective` 和 `/ops/config`; sensitive 字段只返回 configured / source / masked, API 不返回 Key、Token、密码、DSN、Bearer、`sk-*`、`ak-*`, 且不直接返回 `Settings.model_dump()` | Mitigated |
| R-032 | 可写 action 配置早于授权执行响应增强 | 前端仍可能根据旧缓存动作执行 FVS, 不能保证“本次后端授权结果”是唯一执行依据 | 阶段 4 已完成: `/api/screen/execute` 返回完整 `authorized_action` / `resolved_action`, 前端只执行该响应, 且 `params` 通过后端 schema / allowlist 校验和净化; 阶段 5 已开放的 action 覆盖仅限 `gotoPage/pageNumber`, 保存前复用 `ScreenActionService` dry-run | Mitigated |
| R-033 | 数据库问数和外部 LLM summarizer 引入越权或编造 | 后续扩展如果允许自由 SQL、模型生成 SQL / 代码或无来源 summarizer, 会破坏当前安全边界 | 阶段 2 仅预留 Database Provider `not_implemented` 状态, 未连接数据库、未执行 SQL; 阶段 3 已实现 KnowledgeDirectAdapter + `source_bound_extractive` summarizer, 固定 `require_sources=true` 和 `no_evidence_policy=fallback`; 后续数据库问数仍必须只允许只读账号、表 / 字段白名单、参数化查询、超时和 limit; 外部 LLM summarizer 仍必须走后端受控 Provider 且不得输出可执行代码或控屏动作 | Open |
| R-034 | 通用项目主线重新被客户实例污染 | 后续新增客户时可能继续把某个客户名称、场景、Prompt 或看板动作写回核心代码 / 默认模板 | 2026-06-15 已完成阶段 0A 默认入口和根模板清洁; 阶段 2 已移除 `apps/api/app/services/ask_metrics.py` 客户实例硬编码, 客户 Excel 问数规则仅保留在 `config/customers/zt-securities/ask-metrics.yaml` 客户 profile 中 | Mitigated |
| R-036 | 配置驱动问数定义缺少独立校验器 | 后续新增客户 metric 配置时, YAML 字段、模板或 workbook/sheet 名写错会导致问数 fallback | 阶段 5 validate/test 仅允许切换 `ASK_METRICS_MODE=excel|dora|auto`, 不开放 workbook/sheet/metric 模板写入, 因此不会校验新增 metric 定义; 后续如开放 ask-metrics YAML 编辑, 必须新增独立 metric dry-run | Open |
| R-035 | 配置来源误标导致排障误判 | 只读配置页可能把合并后的最终值误标为来自 env / customer_config, 误导现场排障或配置治理 | 阶段 1 已新增来源构造服务, 按 env / customer_config / root_config / code_default / frontend_runtime 契约显式标注; 对 action_count、provider 组合、Prompt 未实现项等无法精确追踪字段标 `derived` / `unknown` 并说明限制 | Mitigated |
| R-037 | KnowledgeDirect 真实 RAGFlow 参数和来源质量未现场复验 | 本地直连检索可能因为 dataset、API / MCP 参数或资料切片不匹配而频繁 fallback, 或返回来源质量不足 | 阶段 3 默认仍为 `knowledge.mode=dora`, 不影响既有 Dora -> RAGFlow MCP 路径; KnowledgeDirect 命中必须带 sources / source_summary, 无依据必须 fallback; 切换 `local_ragflow_llm` 或 `auto` 前需用客户 RAGFlow 环境做现场检索、来源质量和延迟复验 | Open |
| R-038 | 配置写接口被非本地操作者误用 | 可能改坏现场配置或暴露配置治理入口 | 阶段 5 写接口默认仅允许 localhost / testserver origin; 2026-06-16 已本地配置 `CONFIG_ADMIN_TOKEN` 并验证缺失 token、错误 token、非本机 Host / Origin 写入均被拒绝; audit 记录 operator、reason、摘要和错误; 正式跨机器访问仍需反向代理层访问控制 | Mitigated |
| R-039 | 上线前缺少完整风险处理和全链路 E2E 证据 | 真实用户测试时可能暴露访问控制、依赖连通、语音权限、FVS 嵌入、安全负测或核心业务回归缺口 | 2026-06-16 已完成并归档上线前 smoke、安全负测、核心业务回归、浏览器 / CDP 证据、Ops 导出、audit 和风险摘要到 `logs/prelaunch-20260616-161620/`; 剩余客户网络、供应商 key 轮换、正式 FVS、真实麦克风 / 自动播放人工测试继续按本风险清单跟踪 | Mitigated |

## 当前遗留事项

- 2026-06-15 已恢复主线清洁基线, 后续主线优化不再继承临时宣传录屏页面、临时客户配置、临时资产或临时白名单动作。
- 2026-06-15 项目定位已调整为通用可配置数字人; 中天证券党建大屏只作为 `zt-securities` 客户配置实例。
- 2026-06-15 已完成阶段 0A 默认入口和根模板清洁; 默认 Docker Compose、包名、根级唤醒词 / 演示用例 / 问数模板、前端 Mock 大屏、README 和脚本默认用例均切为通用示例。
- 2026-06-15 已完成阶段 1 只读 effective config 和 schema: 新增 `/api/config/effective`、`/api/config/schema` 和 `/ops/config` 只读页面, 只展示脱敏白名单配置快照和 schema, 不提供保存、reload、action 编辑或写入入口。
- 2026-06-15 已确认本机 `uv` 可用但当前 PowerShell PATH 尚未刷新; 阶段 1 请求级 smoke 使用 `C:\Users\nifen\.local\bin\uv.exe` 绝对路径完成。
- 未跟踪目录 `outputs/manual-20260614-212600/` 已清点为历史 / 手工输出, 不作为阶段 1 配置模型、schema、页面或 Provider 设计输入。
- 能力路由与配置中心方案已完成阶段 0A 默认入口 / 根模板清洁、阶段 1 只读 effective config、阶段 2 AskMetricsProvider 抽象、阶段 3 KnowledgeDirectAdapter、阶段 4 控屏 resolver / 授权 action 响应增强和阶段 5 可写配置页与审计; 数据库问数真实查询、外部 LLM summarizer 和 Prompt 内容编辑仍不属于已完成范围。
- 2026-06-15 已完成阶段 2 AskMetricsProvider 抽象: `apps/api/app/services/ask_metrics.py` 不再包含客户实例硬编码, Excel 问数由配置驱动 `ExcelAskMetricsProvider` 承接; 当前 Database Provider 仅保留 `not_implemented` 状态, 未连接数据库或执行 SQL。
- 2026-06-16 已完成阶段 3 KnowledgeDirectAdapter + 来源约束回答: 新增本地 RAGFlow 检索适配边界和 `source_bound_extractive` summarizer, 只基于检索 chunks / metadata 回答, 无来源或依据不足时 fallback; 默认 `knowledge.mode=dora`, 既有 Dora -> RAGFlow MCP 路径保持不变。
- 2026-06-16 已完成阶段 4 控屏 resolver 与授权 action 响应增强: 本地 `ScreenControlResolver` 只解析候选 `action_id`, `/api/screen/execute` 返回本次 `authorized_action` / `resolved_action` 和 FVS routing, 前端真实执行只使用本次响应; 非白名单 action、非法 params、参数值覆盖和未知 target 均安全拒绝。
- 2026-06-16 已完成阶段 5 可写配置页与审计: 新增 `data/config-overrides/active.yaml` 覆盖层、validate / dry-run / save / reload / audit API 和 `/ops/config` 受控编辑面板; 覆盖层只允许非敏感 runtime 字段和 `gotoPage/pageNumber` action 映射, 不允许密钥、DSN、自由 SQL、脚本、外部 LLM provider 或任意 FVS 函数。
- 2026-06-16 已执行上线前风险处理、完整启动 smoke、安全负测、核心业务回归和页面级 E2E 证据归档: `logs/prelaunch-20260616-161620/` 和 `logs/exports/zt-poc-logs-20260616-205839.zip`。本轮未实现 Database Provider、外部 LLM summarizer 或 Prompt 内容编辑。
- 2026-06-16 上线前 smoke 剩余现场项: 供应商控制台 key 轮换、客户网络 Dora / RAGFlow / ASR / TTS / FVS 复测、正式 FVS iframe 策略复测、真实麦克风唤醒 / 连续追问 / 播报中打断 / 自动播放人工验收。
- 当前 `Settings` 运行时仍只保留合并后最终值; 阶段 1 已通过独立 `ConfigSnapshot` 来源构造输出 `source` 字段, 对聚合或浏览器 runtime 字段标 `derived` / `frontend_runtime` / `unknown`。
- V0.1 Mock 闭环已完成。
- V0.2 Dora Adapter 已接入 OpenClaw `agents` 和 `sse/chat`, Mock 回退保留。
- 真实 Dora Agent `中天证券党建大屏语音助手` 已验证可返回 `answer` / `screen_control` / `fallback`。
- V0.3 已完成 ASR / TTS Provider 接口、Mock ASR、Mock TTS、最小前端语音输入和播报控件。
- 阿里云百炼真实 TTS 已验证通过; 浏览器麦克风真实 ASR 已通过人工验收。
- V0.4 语义唤醒 / 后台监听已完成真实麦克风人工验收, 已覆盖显式启用开关、本地 VAD、唤醒词 ASR 判断、状态机和手动按钮回退。
- V0.4.1 连续对话窗口已完成人工验收, 已覆盖播报后直接追问、超时退出和轮数退出。
- V0.5 已完成本地 RAGFlow Docker Desktop 基础部署和 MCP self-host 启动: Web `http://127.0.0.1:18089`, MCP `/mcp` `http://127.0.0.1:19382/mcp`, MCP `/sse` `http://127.0.0.1:19382/sse`。
- V0.5 已验证临时公网 MCP `http://liuchenxiang.uk:19382/mcp`: `initialize` 成功, `tools/list` 返回 `ragflow_retrieval`, `tools/call` 可返回 `zt_party_building_demo` 检索 chunk。
- V0.5 已验证 Dora Agent 通过公网 MCP 调用 RAGFlow, 并由 Dora 生成最终 `/api/chat` 的知识库 `answer`。
- V0.5 已对本地 RAGFlow MCP server 做 POC 返回量瘦身: 固定 `keyword=false`, 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`, 精简 chunk 字段和 content 长度。
- V0.5 已新增 `/api/chat/stream`, 前端优先使用 Dora SSE + 分段 TTS; 本轮抽样验证“入党流程是什么?”首个 `dora_delta` 约 8.5s 到 17.6s、首个分段 `tts_ready` 约 11.6s 到 19.8s、最终 `answer` 约 12.0s 到 21.3s、全部分段 TTS 约 15.1s 到 27.1s 就绪。
- 已准备 3 份党建问数测试 Excel: 党员学习、组织生活与党建活动、党员发展流程。
- V0.7 已实现 Gateway 本地只读 Excel 问数 Adapter, `/api/chat` 和 `/api/chat/stream` 会在调用 Dora 前优先匹配问数意图; 11 个脱敏样例问数问题已通过接口 smoke。
- 用户已确认后续不立即输出验收报告, 而是先进入 V0.8 功能增强: Dora 通用问数 + Excel fallback、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。
- V0.5 已完成人工验收, 用户确认真实 Dora + RAGFlow MCP + 分段 TTS 链路通过。
- 已创建 `docs/demo_knowledge/` 最小党建知识库测试资料。
- 已在 RAGFlow 创建 `zt_party_building_demo` dataset, 上传 8 份测试资料并等待解析完成, 全部为 `DONE`。
- V0.6 FVS 真实集成已完成人工验收: 以数字人前端为主体 iframe 嵌入 FVS 看板, 并先将 `action_id` 白名单映射到 FVS `page_number` 分页切换能力。
- 已确认本机 FVS URL 可通过数字人前端同源代理渲染; 客户正式环境仍需在 V0.7 演示准备中确认是否采用同源代理、网关转发或调整 FVS 侧嵌入策略。
- V0.6 已实现 FVS 主画布悬浮语音层; 2026-06-11 已进一步精简为未唤醒时只显示小型低透明麦克风入口, 唤醒词判定中和未命中不展开, 展开态只显示半透明对话评论流。
- V0.6 已新增等待提示音策略: 正式指令或连续追问进入处理后立即播报“收到, 正在为您查找信息。”; 2026-06-11 已调整语音命令自动播报顺序, 最终回答 TTS 会先等待确认播报完成或最多等待 1800ms, 避免本地 Excel 问数快速答案抢占提示。
- V0.6 已完成人工验收, 用户确认“0.6验收完成”。
- 尚未创建 RAGFlow chat / assistant; 当前 V0.5 不需要该能力。
- 尚未配置 RAGFlow 默认 Chat 模型; `keyword=true` 检索会要求 Chat 模型, 当前固定使用 `keyword=false`。
- 尚未确认客户演示环境的麦克风 / 播放权限。
- 语音唤醒高失败率已做一轮现场调优: 前端 VAD 增加约 360ms 预录缓冲, 唤醒词匹配增加常见 ASR 同音偏差归一化, 客户配置调宽收音窗口并新增短唤醒词 `小天`; 调优后仍需真实麦克风连续复测确认成功率和误唤醒率。
- 已实现播报中长唤醒词确认打断: `speaking` 状态下仅命中 `barge_in_wake_words` 才停止当前 TTS; 该能力仍需真实麦克风复测打断成功率和外放误打断率。
- 默认 `ASK_METRICS_MODE=excel` 下, 党员学习完成率等本地 Excel 问数会在调用 Dora 前由 Gateway 直接回答, 因此 Dora Agent 后台不会出现这些问题的记录; 如客户要求 Agent 后台留痕, 需切换到 `dora` 或 `auto` 并重新验证固定问数准确性。
- PowerShell 直接发送中文 JSON 时可能受本地终端编码影响; API 和浏览器 UTF-8 链路已验证正常。
- 当前 TTS 优化为分段文件播放, 不是音频字节级边合成边播放; 若后续要求更低首响, 需评估供应商 TTS 真流式接口和前端 MediaSource / WebAudio 播放方案。
- 已实现 `ASK_METRICS_MODE=dora|excel|auto`, 默认 `excel`, `auto` 可在 Dora / Mock Dora 失败或兜底时回退 Excel。
- 已实现客户私有配置覆盖层, 当前目录为 `config/customers/zt-securities/`。
- 已实现 TTS 字节级真流式: 后端 `POST /api/tts/stream` 返回 PCM `audio_chunk`, 前端使用 Web Audio API 播放, 失败时回退 `/api/chat/stream` 的分段 TTS 或完整 `/api/tts`。
- V0.8 第三阶段已实现运维监控和日志看板: Ops API 覆盖依赖状态、最近会话、错误列表、耗时指标和 Markdown 日志导出; 当前 FVS 大屏不显示运维入口, 运维看板通过 `/ops` 访问。
- V0.9 已实现预检 / 启停 / 日志导出 / smoke 脚本、演示稳态模式、`GET /api/demo/config` 和关键异常兜底体验。
- V1.0 已输出正式验收交付包到 `docs/delivery/v1.0/`, 包含验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。
- V1.0 交付包已引用最新 smoke 结果 `logs/smoke/smoke-demo-20260611-011803.md` 和日志包 `logs/exports/zt-poc-logs-20260611-011813.zip`; 客户现场仍需补齐截图、真实外部依赖连通性和签字。
- 已输出客户汇报用项目管理计划和实施甘特图 Excel: `outputs/customer-report-20260617/zt_project_plan_gantt_20260610_0630.xlsx`。
- 自定义新闻爬虫、新闻整理、自动导入本地 RAGFlow 知识库、性能优化和专项安全加固仍为计划专项; 阶段 3 仅完成 KnowledgeDirect 检索和来源约束回答边界。

## 上线前风险处理与 E2E 验证任务包

2026-06-16 已执行以下任务包, 证据已回写到 `DEV_LOG`、`NEXT_ACTIONS`、`CHANGELOG` 和本风险清单。当前未通过项不是代码继续扩展项, 而是客户 / 供应商 / 正式 FVS 环境复测项。

### 必须先处理的风险

- 配置 `CONFIG_ADMIN_TOKEN`, 并确认写配置 / reload 跨本机访问必须提交 `X-Config-Admin-Token`。
- 确认 `/ops` 和 `/ops/config` 访问边界: 本机、内网、反向代理鉴权或网关 ACL 至少落实一种, 不得公网裸露。
- 轮换曾出现在对话上下文中的百炼 / 供应商 API Key, 并检查前端 bundle、Ops 导出、config API 和日志包均不含明文密钥。
- 确认客户 / 生产环境 FVS iframe 策略: 正式同源代理、反向代理路径或 FVS 侧允许嵌入策略至少落实一种。
- 复测客户网络下 Dora、RAGFlow MCP、ASR、TTS、FVS、麦克风权限和浏览器自动播放。
- 如启用 `KNOWLEDGE_MODE=local_ragflow_llm|auto`, 必须复验客户资料检索命中、来源质量、fallback 和延迟; 否则保持默认 `dora`。

### 完整启动 smoke

- 记录 git 状态、当前 commit、`.env` 关键非敏感开关和是否开启 `DEMO_STABLE_MODE`。
- 执行 `python -m compileall apps/api/app`、`corepack.cmd pnpm --dir apps/web build`、`git diff --check`。
- 使用真实启动链路启动, 优先 `scripts/start-poc.ps1 -Build` 或实际部署脚本。
- 执行 `scripts/check-poc.ps1 -RequireServices` 或等价检查, 记录 API、Web、Ops、Dora、RAGFlow、ASR、TTS、FVS 状态。
- 打开 `/`、`/ops`、`/ops/config`, 检查页面渲染、控制台错误、Ops 脱敏和配置页访问边界。
- 对 `/ops/config` 做无害 runtime override 的 validate / dry-run / save / reload / effective / audit / rollback 验证。

### 安全负测

- 拒绝 API Key、Token、password、Bearer、DSN、RAGFlow MCP Key、URL secret query。
- 拒绝自由 SQL、`mode=database`、`query` / `sql` 字段和数据库连接配置。
- 拒绝脚本、shell、Python、JavaScript、可执行代码、任意 FVS function。
- 拒绝非白名单 action、未知 target、非法 params、参数值覆盖、嵌套对象、URL / 脚本类参数。
- 确认前端真实控屏只使用 `/api/screen/execute` 本次 `authorized_action` 响应。
- 确认 `/api/config/effective`、`/api/config/schema`、`/api/ops/export` 不返回明文密钥或未脱敏客户数据。

### 核心业务回归

- 11 个固定 Excel 问数 smoke 仍通过, 且回答带来源和口径说明。
- `ASK_METRICS_MODE=excel|dora|auto` 路由行为不退化。
- 知识库默认 Dora -> RAGFlow MCP 路径可回答固定知识问题; KnowledgeDirect 如启用必须验证 sources、fallback 和不编造。
- 控屏 resolver、`/api/screen/execute` 和 FVS iframe 跳页覆盖合法 / 非法动作场景。
- ASR / TTS 当前模式可用, TTS stream 失败能回退。
- 真实浏览器复测语音唤醒、连续追问、播报中长唤醒词打断、等待提示音和 AI 结果打断等待提示音。

### 完整全链路与异常 E2E

- 文本输入链路: 用户问题 -> chat / stream -> answer / screen_control / fallback -> 前端展示。
- 语音链路: 唤醒 -> ASR -> chat -> TTS -> 播报 / 字幕 / 动效 -> FVS 控屏。
- 配置链路: validate -> dry-run -> save -> reload -> effective/audit -> 业务链路使用新配置 -> rollback。
- 运维链路: `/ops` 依赖、会话、错误、耗时指标和脱敏日志导出。
- 异常场景: Dora 超时 / fallback、RAGFlow 不可达 / 无来源、Excel 缺失、TTS stream 失败、ASR 空结果、FVS iframe 失败、麦克风权限拒绝、自动播放被拦截、配置 reload 拒绝。
- 证据归档: smoke 输出、Ops 导出、audit 片段、截图 / 录屏、控制台结果、最终风险状态和用户测试结论。

## 待确认问题

- V1.0 现场验收时是否关闭 `DEMO_STABLE_MODE`, 或按演示稳态 / 真实依赖两套结果分别记录?
- V1.0 验收报告中的 S-001 到 S-007 截图附件由谁负责采集和归档?
- 客户是否确认 `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md` 中的签收角色和运维接收人?
- V0.7 / 正式演示环境是否沿用 `/webroot/` 同源代理, 还是由 FVS 侧调整 iframe 允许策略?
- FVS `page_number=1/2/3/4` 在正式演示环境刷新和切页后是否能稳定保持目标页面?
- 当前临时公网 MCP 映射是否满足客户演示网络和安全要求?
- 是否需要为后续增强检索或 RAGFlow 自答配置默认 Chat 模型?
- Dora Agent 通过公网 `/mcp` 调用 `ragflow_retrieval` 时能否长期稳定保持 `keyword=false`?
- RAGFlow MCP POC patch 在后续升级 RAGFlow 版本时如何维护?
- FVS 是否已有页面 / Tab 切换 JS API 或组件状态控制方式?
- FVS iframe 动作通信需要使用标准 `window.addEventListener("message")` 还是 FVS 自身 Adapter?
- 客户 POC 是否允许使用云 ASR / TTS?
- 客户 POC 演示环境是否允许长时间开启浏览器麦克风监听?
- 客户 POC 演示环境的现场噪声和麦克风增益是否需要单独调 VAD 阈值?
- POC 环境网络是否允许内网穿透?
- 正式客户党建问数执行链路是否继续沿用 Gateway Excel Adapter, 还是切换为 Dora、FineBI / FVS 数据源或数据库 Provider?
- 正式客户党建问数指标口径、数据刷新频率和授权范围是什么?
- Dora 通用问数是否已有可稳定调用的数据源、工具或客户侧数据集?
- TTS 供应商当前 WebSocket 协议是否支持边合成边返回可播放音频 chunk?
- 运维看板是否需要登录鉴权, 还是仅限本地 POC 内网访问?
- 客户私有配置目录最终是否需要支持多客户并存, 还是只保留 `zt-securities` 一个客户目录?
- V1.0 验收时是否要求关闭 `DEMO_STABLE_MODE`, 或在报告中按演示场景分别记录开启 / 关闭结果?
- 新增人员新闻爬虫专项需要采集哪些新闻网站? 是否有客户指定新闻源白名单?
- 指定人员输入字段是否只包含姓名, 还是需要单位、职务、别名、时间范围等辅助条件?
- 新闻采集结果是否允许自动入库, 还是需要人工确认后再导入 RAGFlow?
- 本地 RAGFlow 知识库是否沿用 `zt_party_building_demo` dataset, 还是为人员新闻专项新建独立 dataset?

## 风险处理规则

- 发现新风险必须新增编号。
- 风险关闭时保留记录, 状态改为 Closed, 并说明关闭原因。
- 影响阶段计划的风险必须同步更新 `NEXT_ACTIONS.md`。
