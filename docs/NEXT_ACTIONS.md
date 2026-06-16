# Next Actions

## Current Phase

V1.0 POC 验收交付版已输出。

2026-06-15 项目定位已调整为通用可配置数字人 POC。中天证券党建大屏不再是项目本体, 而是当前客户实例: 通过 `config/customers/zt-securities/` 覆盖项目名称、客户名称、助手名称、Dora Agent、知识库、问数数据、FVS 看板、动作白名单、唤醒词和演示话术。根目录默认配置和 `.env.example` 改为通用默认, 前端标题和 Ops 导出标题改为读取配置。新增 ADR-0023 记录该定位决策。

2026-06-15 已恢复主线清洁基线: 本地临时宣传分支已删除, 主线工作树中的录屏页面、专用数字人组件、专用资产、临时客户配置、财务录屏动作白名单和临时 ADR 已移除。当前只保留主线架构图 `docs/15_MAINLINE_ARCHITECTURE_DIAGRAM.md`、能力路由与配置中心方案 `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md` 以及 ADR-0022。配置中心方案已进一步按实际代码修正: 阶段 0A 先做默认入口和根模板清洁; 阶段 1 做只读 effective config 时必须新增字段来源构造, 不能凭合并后的 `Settings` 猜测来源; 不直接进入可写配置。阶段 0A 当时列出的 `AskMetricsService` 临时遗留 allowlist 已在阶段 2 移除。

2026-06-15 已完成通用可配置数字人阶段 0A: 默认 Docker Compose 启动不再自动进入客户 profile, API / Web 镜像名、容器名和包名改为 `configurable-digital-human-*`; 根级 `wake-words.yaml`、`demo-cases.yaml`、`ask-metrics.yaml` 和前端 Mock 大屏默认态已改为通用示例; README 与 PowerShell 脚本默认 smoke 改为通用用例; `config/customers/zt-securities/` 继续作为客户实例保留。阶段 0A 当时记录 `apps/api/app/services/ask_metrics.py` 为阶段 2 前临时遗留 allowlist, 该遗留已在阶段 2 移除。未跟踪输出目录 `outputs/manual-20260614-212600/` 已清点为历史 / 手工输出, 不作为阶段 1 输入。

2026-06-15 已完成通用可配置数字人阶段 1: 新增只读脱敏 `GET /api/config/effective` 和 `GET /api/config/schema`; 后端通过 `ConfigSnapshot` 白名单构造和来源构造输出项目、客户、场景、助手、看板、问数、知识库、控屏 provider、Mock 开关、Prompt profile、敏感字段摘要和当前实现状态, 不直接返回 `Settings.model_dump()`。前端新增 `/ops/config` 只读配置页, 同时展示后端 effective FVS 配置和当前浏览器 FVS runtime; 页面无保存、reload、action 编辑或写入入口。当前 Database Provider、KnowledgeDirectAdapter、LLM summarizer、可写 Prompt、可写 action 配置、配置 validate/test/reload/audit 均明确未实现。验证通过: `corepack.cmd pnpm --dir apps/web build`; `python -m compileall apps/api/app`; `git diff --check`; uv + FastAPI TestClient 请求级 smoke; 相关静态验收搜索通过。

2026-06-15 已完成通用可配置数字人阶段 2: 新增 `AskMetricsProvider` 抽象与配置驱动 `ExcelAskMetricsProvider`, `apps/api/app/services/ask_metrics.py` 仅保留 provider 编排, 不再包含客户实例 allowlist 规则。当前 Excel 问数的关键词、字段、模板、来源和口径说明已迁移到 `config/customers/zt-securities/ask-metrics.yaml` 客户 profile; 根级 `config/ask-metrics.yaml` 保持通用空 metric 模板。`ASK_METRICS_MODE=excel|dora|auto` 行为保持不退化: excel 模式继续本地优先, dora 模式不被 Excel 抢答, auto 模式在 Dora / Mock Dora fallback 时回退 Excel。Database Provider 仅在配置快照中保留 `not_implemented` 状态, 未连接数据库、未执行 SQL、未开放写配置或 dry-run 接口。

2026-06-16 已完成通用可配置数字人阶段 3: 新增 `KnowledgeDirectProvider`、`RagflowKnowledgeRetriever` 和后端受控 `SourceBoundSummarizer`。默认 `KNOWLEDGE_MODE=dora`, 保持既有 Dora -> RAGFlow MCP 知识库路径; 显式启用 `local_ragflow_llm` 时, Gateway 只调用 RAGFlow 检索 chunks/metadata, summarizer 只基于来源回答, `require_sources=true`, `no_evidence_policy=fallback`。KnowledgeDirect 命中返回标准 `answer` 且包含 `display.sources` / `source_summary`; 无检索结果或依据不足时返回 fallback, 不编造。当前 summarizer 不调用外部 LLM; 外部 LLM summarizer、Database Provider、Prompt 编辑、可写配置、配置 validate/test/reload/audit、控屏授权 action 响应增强均未实现。新增 ADR-0024。

2026-06-16 已完成通用可配置数字人阶段 4: 新增本地 `ScreenControlResolver`, 固定控屏命令可先按白名单 action label / description 解析为候选 `action_id`, 未命中仍走 Dora / Mock Dora。`/api/screen/execute` 已返回本次 `authorized_action` / `resolved_action`, 包含 `target`、`provider`、`fvs_function`、`fvs_routing`、净化后的 `params`、校验状态和拒绝原因; 前端 FVS 执行路径只使用本次授权动作响应, `GET /api/screen/actions` 仅用于只读按钮展示。非法 action_id、非法 params、参数值覆盖和未知 target 均安全拒绝。本阶段未实现可写配置、Prompt 编辑、可写 action 配置、配置 validate/test/reload/audit、Database Provider 真实查询或外部 LLM summarizer。

2026-06-11 已补充客户汇报用项目管理计划和实施甘特图 Excel: `outputs/customer-report-20260617/zt_project_plan_gantt_20260610_0630.xlsx`。该材料按用户指定的客户汇报口径, 将 `2026-06-10` 到 `2026-06-17` 表述为已完成 Mock 链路联调与端到端流程验证, 将 `2026-06-18` 到 `2026-06-30` 表述为自定义新闻爬虫及导入知识库、RAGFlow 知识库调用、性能优化、安全优化、测试验收上线的专项计划。`2026-06-13`、`2026-06-14`、`2026-06-19`、`2026-06-20`、`2026-06-21`、`2026-06-27`、`2026-06-28` 在材料中标为非工作日, 仅保留风险响应 / 问题跟进。

2026-06-11 针对普通唤醒完全无法触发的问题完成热修: 前端 VAD 增加连续两帧超过阈值才正式开始收音的启动确认, 避免单帧环境 / 外放噪声触发空 ASR; 普通唤醒 `vad_threshold` 从 0.014 回调到 0.018, 播报中 `barge_in_vad_threshold` 保持 0.018。验证通过: `corepack pnpm --dir apps/web build`; `python -m compileall apps/api/app`; `docker compose up -d --build api web`; `GET /api/wake/config`; `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json`; `git diff --check`; Codex Browser 加载新 bundle。下一步需用户刷新页面、重新开启后台监听并做真实麦克风复测。

2026-06-11 针对党员学习完成率语音提问未播报“收到”完成修复: 默认 `ASK_METRICS_MODE=excel` 下该问题会由 Gateway 本地 Excel 问数 Adapter 在调用 Dora 前直接回答, 因此 Dora Agent 后台没有记录属于设计行为; 前端已改为语音命令自动播放最终回答前先等待“收到, 正在为您查找信息。”确认播报完成或最多等待 1800ms, 避免本地 Excel 快速答案抢占确认提示。验证通过: `corepack pnpm --dir apps/web build`; `python -m compileall apps/api/app`; `docker compose up -d --build web`; `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json`; `POST /api/chat` 指标问答返回 `zt_party_study_metrics_2026.xlsx / Dashboard`; `git diff --check`; Codex Browser 加载新 bundle `index-CQTUuisV.js` 且控制台无 error。下一步需用户刷新页面、重新开启后台监听后复测“当前党员学习完成率是多少?”。

## Phase Status

V0.5 已完成人工验收。已完成本地 RAGFlow Docker Desktop 基础部署、MCP self-host 启动、最小党建知识库资料准备、公网 MCP 映射连通性验证、`zt_party_building_demo` dataset 创建、8 份测试资料上传和解析。MCP `ragflow_retrieval` 已可通过本地和公网地址返回知识库 chunk。已按当前边界完成 Dora 通过公网 MCP 调用 RAGFlow 的真实知识库问答验证: RAGFlow 固定负责 `keyword=false` 向量检索, Dora 负责最终回答生成。已在本地 RAGFlow MCP server 做 POC 返回量瘦身, 并在 POC Gateway 新增 `/api/chat/stream` + 分段 TTS, 降低知识库问答的语音首响等待。

V0.6 已完成人工验收。已完成数字人前端主页面 iframe 嵌入 FVS 看板、Web Nginx `/webroot/` 同源代理、四个 FVS 测试页 `page_number=1/2/3/4` 切换、FVS 主画布悬浮语音层、未唤醒角落语音 icon、唤醒 / 连续追问 / 思考 / 播报展开语音动画和文字记录, 以及等待提示音被 AI 结果 TTS 优先打断的交互策略。用户确认“0.6验收完成”。

问数测试数据已准备并接入: `docs/demo_data/ask_metrics/` 下包含党员学习、组织生活与党建活动、党员发展流程 3 份脱敏 Excel, `config/ask-metrics.yaml` 管理工作簿和 sheet 映射。V0.7 已新增 Gateway 本地只读 Excel 问数 Adapter, `/api/chat` 和 `/api/chat/stream` 会在调用 Dora 前优先匹配问数意图, 目前已通过 11 个固定问数问题 smoke。

用户已决定调整后续顺序: 先做功能增强, 再做交付前优化, 最后输出验收报告、部署方案、用户手册等材料。路线已记录到 `docs/14_ENHANCEMENT_ROADMAP.md` 和 ADR-0011。

V0.8 第一阶段已完成: 新增 `CUSTOMER_ID` / `CUSTOMER_CONFIG_DIR`, 建立 `config/customers/zt-securities/` 客户私有配置目录, 后端启动时加载客户级动作白名单、Demo、唤醒词和问数映射覆盖层; `dora.yaml`、`ragflow.yaml`、`voice.yaml`、`fvs.yaml` 提供非敏感客户配置样例。新增 `ASK_METRICS_MODE=excel|dora|auto`: `excel` 保持 V0.7 Excel 优先行为, `dora` 不让 Excel Adapter 抢答, `auto` 在 Dora / Mock Dora 失败或兜底时回退 Excel。已新增 ADR-0012。容器验证确认客户目录配置生效, `excel` 模式 11 个问数 smoke 通过, `/api/chat/stream` 问数事件顺序为 `metadata -> dora_delta -> answer -> tts_ready -> end`, `dora` / `auto` 路由完成函数级验证。

V0.8 第二阶段已完成: 新增 TTS 字节级真流式接口 `POST /api/tts/stream`, 后端 `TtsProvider.stream_synthesize` 支持 Mock PCM chunk 和阿里云 CosyVoice WebSocket 二进制帧逐块转发; 新增 `TTS_STREAMING_ENABLED`、`TTS_STREAMING_FALLBACK`、`TTS_STREAMING_AUDIO_FORMAT`; 前端新增 PCM Web Audio 流式播放器, 自动播报和播报按钮优先真流式, 失败时回退 `/api/chat/stream` 的分段 `tts_ready` 或完整 `/api/tts`; 等待提示音仍会被 AI 结果音频打断。已新增 ADR-0013。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `docker compose up -d --build api web`; `GET /api/health`; 真实 TTS 配置下 `/api/tts/stream` 首个 PCM `audio_chunk` 约 567ms 到达, `end.duration_ms=3387`, 共 33 个 chunk; 临时关闭 `TTS_STREAMING_ENABLED` 时返回 `TTS_STREAMING_DISABLED` 并指向 `fallback=segment`; `/api/chat/stream` 问数仍返回 4 个 `tts_ready`; `GET http://127.0.0.1:18000` 和 JS / CSS 资源均为 HTTP 200。Codex Browser 控制工具本轮未暴露, 未做截图级交互验证。

V0.8 第三阶段已完成: 新增只读脱敏 Ops API: `GET /api/ops/health`、`/api/ops/dependencies`、`/api/ops/sessions`、`/api/ops/session/{session_id}`、`/api/ops/errors`、`/api/ops/metrics`、`/api/ops/export`。后端复用 SQLite `session_logs`, 新增最近会话、单会话明细、错误列表、聚合耗时和 Markdown 导出能力; 日志摘要会截断并脱敏常见 Key / Token / Bearer / `sk-*` / `ak-*` 模式。依赖状态覆盖 SQLite、动作白名单、Dora、RAGFlow、ASR、TTS、FVS; Dora / RAGFlow 只做轻量只读 HTTP 探测, ASR / TTS 不主动上传音频或触发合成。前端新增“演示 / 运维”视图切换, 运维看板可查看依赖状态、最近会话、错误列表、耗时指标并导出 Markdown 日志。新增 ADR-0014。后续 FVS 主画布运维入口已按用户要求拆出为 `/ops`。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `docker compose up -d --build api web`; `GET /api/health`; Ops API smoke; `/api/ops/export` 密钥模式扫描未命中; Codex Browser 验证 FVS host 和 mock 模式均可进入运维看板。当前依赖聚合状态为 `error`, 原因为 Dora 探测超时、RAGFlow 探测失败, Ops API 本身返回正常。

V0.9 已完成当前 scope: 新增 `scripts/check-poc.ps1`、`scripts/start-poc.ps1`、`scripts/stop-poc.ps1`、`scripts/export-logs.ps1`、`scripts/smoke-demo.ps1` 和 `scripts/poc-common.ps1`; 预检覆盖 Docker、端口、配置、API、Web、Ops 依赖和 RAGFlow; 启停脚本支持 `-Build`、`-DemoStable` 和可选本机 RAGFlow; 日志导出脚本复用脱敏 Ops API 生成现场日志包; smoke 脚本使用固定演示问题集, 可选执行白名单控屏动作。新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 和 `GET /api/demo/config`; Dora 失败时可在演示稳态下回退 Excel 问数或 Mock Dora; Excel 缺文件、Dora 流式异常、TTS 分段异常、FVS iframe 加载失败和麦克风权限失败均有安全提示。新增 ADR-0015。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `scripts/check-poc.ps1 -SkipExternal -Json`; `scripts/start-poc.ps1 -Build -DemoStable`; `GET /api/demo/config` 返回 `stable_mode=true`; `scripts/smoke-demo.ps1 -ExecuteScreenActions`; `scripts/export-logs.ps1 -Zip`; `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json`; Codex Browser 验证前端演示稳态标识、动态演示题和 FVS iframe 超时兜底。

FVS 大屏交互已按用户要求进一步精简: FVS iframe host 默认态只保留小型低透明麦克风 icon, 唤醒词判定中、未命中和冷却状态不展开对话浮层; 展开态改为半透明评论流, 只显示最近用户识别文本和数字人回复文本; 运维看板从 FVS 主画布悬浮层拆出, 改为 `/ops` 独立路径; 命中唤醒词后会立即播报“您好。”, 再进入正式指令录音或处理。新增 ADR-0016。验证通过: `corepack pnpm --dir apps/web build`; `git diff --check`; 本地 Vite preview `/` 和 `/ops` HTTP 200; 源码断言确认无 FVS 运维悬浮按钮、存在唤醒提示、`/ops` 路由和评论流。当前工具环境未做截图级浏览器验证和真实麦克风音频顺序人工验证。

2026-06-11 针对本地复测中语音唤醒失败率较高的问题完成一轮现场调优: 前端 VAD 增加约 360ms 预录缓冲, 避免唤醒词开头被固定阈值截掉; 唤醒词匹配增加 `晓/肖 -> 小`、`田/甜/添/填 -> 天` 的 ASR 同音偏差归一化, 并按长唤醒词优先匹配 / 剥离; 默认和中天证券客户唤醒配置新增短唤醒词 `小天`, 并将 `min_audio_ms=1000`、`silence_ms=1000`、`max_audio_ms=6500`、`cooldown_ms=800`、`vad_threshold=0.014`。验证通过: `corepack pnpm --dir apps/web build`。下一步需由用户在真实麦克风环境连续复测 10 次以上唤醒成功率; 若误唤醒增加, 优先把 `vad_threshold` 回调到 0.016 或移除短唤醒词。

2026-06-11 已实现“播报中长唤醒词确认打断”。前端在 `speaking` 状态下继续监听短片段, 但只用 `barge_in_wake_words` 中的长唤醒词确认打断, 当前为 `小天小天` 和 `你好小天`; 命中后停止当前 TTS, 播放“您好。”并进入下一轮, 同句包含指令时直接处理; 未命中、空识别或 ASR 失败时继续播报, 不进入 `/api/chat`。新增 ADR-0017。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`。下一步需真实麦克风复测播报中打断成功率和误打断率。

V1.0 验收交付包已输出到 `docs/delivery/v1.0/`, 包含交付包索引、验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。验收报告引用最新 smoke 结果 `logs/smoke/smoke-demo-20260611-011803.md` 和日志包 `logs/exports/zt-poc-logs-20260611-011813.zip`, 并明确记录现场截图、真实客户网络、麦克风 / 播放权限、Dora / RAGFlow 连通性和客户签字仍需现场补齐。交付包未新增外部系统能力, 继续保留 Mock Dora / ASR / TTS / FVS 回退, 且继续坚持 `action_id` 白名单和不执行模型生成代码。

## Next Task

V1.0 验收交付包、阶段 0A 默认入口和根模板清洁、阶段 1 只读 effective config / schema、阶段 2 AskMetricsProvider 抽象与 Excel 问数迁移、阶段 3 KnowledgeDirectAdapter + 来源约束回答、阶段 4 控屏 resolver 与授权 action 响应增强均已完成。下一推荐 goal:

```text
执行通用可配置数字人阶段 5: 可写配置页与审计。先设计并实现 data/config-overrides/ 覆盖层、配置 validate / dry-run / audit 和最小访问控制边界; 仍不得暴露密钥、不得执行模型生成代码、不得开放自由 SQL。
```

本 goal 的边界:

- 阶段 5 才允许新增配置覆盖层、validate / dry-run / audit 和受控 reload; 必须先限定非敏感字段和访问边界。
- 阶段 5 不应回头新增数据库问数真实查询; Database Provider 仍保持 `not_implemented`, 除非用户另开数据库问数阶段。
- 阶段 5 不应继续扩展 KnowledgeDirectAdapter; 外部 LLM summarizer 仍未实现, 除非用户另开知识库总结增强阶段。
- 可写 Prompt、Prompt 编辑和可写 action 配置如进入阶段 5, 必须只保存非敏感配置, 先 validate / dry-run, 并保留审计; 不得把 API Key、Token、DSN、任意脚本或可执行代码写入配置。
- 不让 LLM 生成或执行 SQL、Python、JavaScript 或 shell。
- FVS 控制继续使用 `action_id` + 后端白名单校验; 阶段 5 如开放 action 写入, 必须复用阶段 4 的 `authorized_action` 响应和 params allowlist。

Go / No-Go: 阶段 5 可以开始, 但必须另开 goal 且先做安全设计、validate / dry-run / audit 和访问控制; 数据库问数真实查询、外部 LLM summarizer、自由 SQL 和模型生成代码执行仍 No-Go。

客户现场验收复演仍可按 `docs/delivery/v1.0/` 执行, 但不与本轮配置中心主线优化混在同一个 goal 中推进。

## Context

当前仓库已有文档体系、Git 仓库、`.env.example`、第一版 `config/` 配置文件、Vue 3 前端、FastAPI 后端和 Docker Compose。V0.1 已跑通文本输入 -> Mock Dora -> Mock FVS -> 前端展示 -> SQLite 会话日志。

V0.2 已实现 Dora OpenClaw `list_agents`、按名称解析已发布 Agent、SSE chat 和输出归一化。`ENABLE_MOCK_DORA=true` 默认回退仍可运行; `ENABLE_MOCK_DORA=false` 已通过本地 `.env` 调用 Dora 并返回归一化 `answer` / `screen_control` / `fallback`。

Dora 后台已发布“中天证券党建大屏语音助手”专用 Agent, 本地 `.env` 已切换到 `DORA_AGENT_NAME=中天证券党建大屏语音助手`, `DORA_AGENT_ID` 保持为空以继续验证自动发现。

V0.2 真实控屏端到端已通过: Dora 返回 `screen_control.action.id`, Gateway 完成白名单校验, `/api/screen/execute` 可执行合法动作; 非法页面返回 `fallback`。

V0.3 已新增 ASR / TTS Provider 接口和 Mock 实现。后端提供 `POST /api/asr/transcribe`、`POST /api/tts` 和 `GET /api/tts/audio/{audio_id}`; 前端支持浏览器录音或 Mock ASR 文本提交, ASR 文本可进入现有 `/api/chat` 流程, 数字人回答后可生成音频并展示“播报”按钮和原生音频控件。

当前本地 `.env` 已配置阿里云百炼真实语音: `ENABLE_MOCK_ASR=false`, `ENABLE_MOCK_TTS=false`, ASR 使用 `fun-asr-realtime`, TTS 使用 `cosyvoice-v3-flash` / `longanyang`。真实 TTS 已通过接口验证并下载到 mp3; 浏览器麦克风 16k WAV 真实 ASR 已通过人工验收。不接真实 FVS, 继续保留 Dora / ASR / TTS / FVS Mock 开关。

V0.4 的关键边界: 当前仍允许一个“启用后台监听”开关, 用于满足浏览器麦克风权限和用户知情要求; 后续对话轮次应尽量避免每次点击“录音 / 识别并发送”。V0.4 不做永久无提示录音, 不把未命中唤醒的长音频保存到后端。

V0.4 已实现 `GET /api/wake/config`, 前端后台监听开关、本地 RMS VAD、唤醒词 ASR 判断、同句指令提取、唤醒后正式指令录音、TTS 自动播放尝试和冷却回到监听。用户已完成真实麦克风唤醒人工验收。V0.4.1 已新增连续对话窗口: 播报结束后进入 `followup_listening`, 窗口内直接追问, 超时或达到轮数后退出。用户已完成 V0.4.1 连续对话窗口人工验收。

V0.5 本轮按用户要求从“远端服务器部署”切换为本地 Docker Desktop 部署。远端服务器 `/tmp/zfsv3/nvme12/18722229125/data/Docker/ragflow` 中本轮创建的 RAGFlow 容器、卷、网络和目录已清理。当前本地 RAGFlow 位于 `D:\Project\ragflow`, 版本 `v0.25.6`, Web 地址 `http://127.0.0.1:18089`, API 健康检查 `http://127.0.0.1:18089/api/v1/system/healthz`, MCP Streamable HTTP 本地地址 `http://127.0.0.1:19382/mcp`, MCP SSE 本地地址 `http://127.0.0.1:19382/sse`, 临时公网 MCP 地址 `http://liuchenxiang.uk:19382/mcp`。本地 `RAGFLOW_MCP_HOST_API_KEY` 写在 `D:\Project\ragflow\docker\.env`, 不进入项目 Git。已配置默认 Embedding `text-embedding-v3@Tongyi-Qianwen`; `zt_party_building_demo` dataset ID 为 `d7481bc0649311f18b616324ad8eb1c0`, 8 份测试资料均解析为 `DONE`。

V0.5 Dora MCP 问答验证已通过: 当前 `.env` 已切换 `ENABLE_MOCK_DORA=false`, Dora Agent `中天证券党建大屏语音助手` 通过公网 `http://liuchenxiang.uk:19382/mcp` 调用 RAGFlow `ragflow_retrieval`; `张书记最近调研了什么?`、`入党流程是什么?`、`党员学习制度有哪些要求?`、`党支部组织建设规范是什么?` 均返回基于测试知识库的 `answer`。RAGFlow 日志可见 Dora 测试期间的 `POST /mcp` 和 `POST /api/v1/retrieval` 成功记录。

前端真实提问曾出现 `DORA_OUTPUT_INVALID` fallback, 根因是 Gateway 把 Dora SSE 中的 MCP ToolMessage 原始 JSON chunks 拼入最终回答并优先解析为 `{"chunks": ...}`。已修复 `apps/api/app/services/dora_client.py`, 忽略工具原始消息; 修复后同一前端 session 复测“入党流程是什么?”和“张书记最近调研了什么?”均返回 `answer`。

为优化慢交互, 本轮已调整本地 RAGFlow MCP server: 固定 `keyword=false`, 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`, 单 chunk content 最长 1200 字符, 只返回回答所需的精简字段。`docker-compose.yml` 通过只读 volume 挂载该 server 脚本, `ragflow-cpu` 已重建并验证健康。

本轮已新增 `POST /api/chat/stream`: 后端消费 Dora SSE, 提取最终回答 JSON 的 `speak_text` 增量, 推送 `dora_delta`, 并按短段并发调用 TTS 后推送 `tts_ready`。前端优先使用流式接口, 按 `tts_ready.index` 顺序播放分段音频; 流式失败时回退到原 `/api/chat` + `/api/tts`。本轮抽样验证“入党流程是什么?”时, 首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s, 全部分段 TTS 约 15.1s 到 27.1s 就绪。

用户已完成人工验收并确认 V0.5、V0.6 通过。V0.6 已完成“数字人前端主页面 iframe 嵌入 FVS 看板”方向, 本机 FVS 可通过同源代理在 iframe 中渲染, 可用 `page_number` 完成四页切换, 并已实现 FVS 主画布悬浮语音层和等待提示音打断策略。下一轮不要继续做 V0.5 / V0.6 收尾, 除非用户要求回归修复; 默认进入 V0.7 POC 稳定版, 聚焦演示脚本、测试问题、问数方案、部署移交和验收报告。

V0.8 之后路线:

- V0.8: 功能增强版, 覆盖 Dora 通用问数、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。已完成当前 scope。
- V0.9: 交付优化版, 覆盖预检脚本、一键启停、日志导出、演示模式和异常体验优化。已完成当前 scope。
- V1.0: POC 验收交付版, 输出验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。已完成交付包输出。

## Recommended Prompt

```text
请先阅读 AGENTS.md、docs/CODEX_CONTEXT.md、docs/NEXT_ACTIONS.md、docs/05_DEVELOPMENT_PLAN.md、docs/delivery/v1.0/README.md、docs/06_API_CONTRACT.md、docs/07_DATA_CONTRACT.md 和 docs/13_RISKS_AND_TODO.md。当前 V0.5 RAGFlow MCP、V0.6 FVS 真实集成均已人工验收, V0.7 已完成本地 Excel 问数 Adapter 和 11 个问数 smoke。V0.8 已完成客户私有配置目录和 `ASK_METRICS_MODE=excel|dora|auto`、TTS 字节级真流式 `/api/tts/stream`、前端 PCM Web Audio 播放和分段 TTS fallback、只读脱敏 Ops API 与前端运维监控 / 日志看板。V0.9 已完成 `scripts/check-poc.ps1`、`start-poc.ps1`、`stop-poc.ps1`、`export-logs.ps1`、`smoke-demo.ps1`、`DEMO_STABLE_MODE`、`GET /api/demo/config`、日志包导出流程和关键异常兜底体验。V1.0 验收交付包已输出到 `docs/delivery/v1.0/`, 下一步执行客户现场验收复演、补齐截图附件、确认真实依赖、导出最终日志包并完成签字。继续不执行模型生成 SQL/Python/JavaScript/shell, 不绕过 action_id 白名单, 不在前端或运维页暴露 API Key。
```

## Already Done

- 已初始化 Git 仓库。
- 已创建 `.gitignore`。
- 已创建 `.env.example`。
- 已创建 `config/screen-actions.yaml`。
- 已创建 `config/wake-words.yaml`。
- 已创建 `config/demo-cases.yaml`。
- 已创建 `config/dora-output-schema.json`。
- 已创建 `data/.gitkeep` 和 `logs/.gitkeep`。
- 已创建 `apps/web` Vue 3 + TypeScript + Vite + pnpm 工程。
- 已创建 `apps/api` FastAPI + uv 工程。
- 已创建 `docker-compose.yml`。
- 已实现 V0.1 Mock API 和前端 Mock 闭环。
- 已实现 SQLite 会话日志写入。
- 已完成 Docker 构建、接口验证和浏览器前端验证。
- 已实现 Dora OpenClaw Adapter, 包含 `list_agents`、`resolve_agent_id` 和 SSE chat。
- 已验证 `ENABLE_MOCK_DORA=false` 可调用 Dora 并返回归一化 `answer`。
- 已将 Dora Agent Prompt 对齐为党建大屏专用 Prompt, 并写入白名单动作示例。
- 已验证 Gateway 对 Dora-like 合法/非法 `screen_control` JSON 的白名单处理。
- 已发布并验证真实 Dora Agent “中天证券党建大屏语音助手”。
- 已验证真实 Dora `screen_control.action.id` 端到端通过后端白名单校验。
- 已新增 `AsrProvider` / `TtsProvider` 接口和 Mock Provider。
- 已新增 `POST /api/asr/transcribe`、`POST /api/tts`、`GET /api/tts/audio/{audio_id}`。
- 已实现前端浏览器录音 / Mock ASR 文本提交, ASR 文本可进入 `/api/chat`。
- 已实现 Mock TTS WAV 生成、后端音频 URL、前端播报按钮和原生音频控件。
- 已将前端录音改为 16k 单声道 WAV, 适配阿里云 Fun-ASR。
- 已实现阿里云 Fun-ASR WebSocket Provider 和 CosyVoice WebSocket Provider。
- 已配置本地 `.env` 使用阿里云百炼真实 ASR / TTS。
- 已验证真实 CosyVoice TTS 可返回 mp3 音频。
- 已完成人工验收: 浏览器麦克风真实 ASR 可识别语音并进入对话 / TTS 链路。
- 已新增 `GET /api/wake/config`, 从 `config/wake-words.yaml` 返回唤醒词和 VAD 设置。
- 已实现前端后台监听开关、VAD 截段、唤醒判断、正式指令识别和冷却状态机。
- 已实现唤醒词命中后自动进入 ASR -> `/api/chat` -> TTS 链路, 并保留手动录音回退。
- 已完成人工验收: V0.4 后台监听可唤醒后正常对话。
- 已实现 V0.4.1 连续对话窗口, 播报结束后短时间内可直接追问。
- 已完成人工验收: V0.4.1 连续对话窗口可在播报后直接追问, 并能按超时 / 轮数退出。
- 已按用户要求清理远端服务器上本轮 RAGFlow 部署残留。
- 已在本地 `D:\Project\ragflow` 克隆 RAGFlow `v0.25.6`。
- 已配置 RAGFlow 本地高位端口, 避免与当前 POC 前后端端口冲突。
- 已通过 Docker Desktop 启动 RAGFlow CPU + Elasticsearch profile。
- 已创建本地 RAGFlow 测试用户并生成 self-host MCP API Key, Key 仅写入 RAGFlow 本地 `.env`。
- 已启用 RAGFlow MCP self-host, `/sse` 返回 200, `/mcp` 端点已监听。
- 已创建 `docs/demo_knowledge/` 8 份最小党建知识库测试资料。
- 已验证公网 `http://liuchenxiang.uk:19382/mcp` 可完成 MCP `initialize` 和 `tools/list`, 暴露 `ragflow_retrieval` 工具。
- 已配置 RAGFlow 默认 Embedding `text-embedding-v3@Tongyi-Qianwen`。
- 已创建 `zt_party_building_demo` dataset 并上传 `docs/demo_knowledge/` 下 8 份测试资料。
- 已等待 8 份测试资料解析完成, 全部为 `DONE`, 每份 1 个 chunk。
- 已验证本地和公网 MCP `ragflow_retrieval` 可返回知识库 chunk。
- 已验证 Dora Agent 通过公网 MCP 调用 RAGFlow 真实知识库, 由 Dora 生成最终 `/api/chat` 的 `answer`。
- 已对本地 RAGFlow MCP 返回量做 POC 瘦身, 并通过 `ragflow-cpu` 挂载后的健康检查验证。
- 已新增 `/api/chat/stream`, 前端优先流式调用并播放分段 TTS。
- 已准备 3 份党建问数测试 Excel 数据。
- 已完成人工验收: V0.5 真实 Dora + RAGFlow MCP + 分段 TTS 链路通过。
- 已新增 V0.6 FVS iframe host 模式和运行时 `?fvs_url=` 配置。
- 已将本机 FVS 测试看板映射为 `总览=1`、`成品库存=2`、`生产管理=3`、`设备分析=4`, 并按 `page_number` 进行 iframe URL 切页。
- 已新增 Web Nginx `/webroot/` 同源代理, 本机 FVS 看板可在数字人主页面 iframe 中渲染。
- 已实现 FVS 主画布悬浮语音层: 未唤醒时只显示角落小型低透明麦克风入口, 唤醒词判定中和未命中不展开; 正式录音 / 连续追问 / 思考 / 播报时展开半透明评论流, 只显示最近对话文本。
- 已实现唤醒成功语音反馈: 命中唤醒词后立即播报“您好。”, 再进入正式指令录音或处理。
- 已实现等待提示音策略: 正式指令或连续追问进入处理后立即播报“收到, 正在为您查找信息。”, AI 结果 TTS 开始时打断等待提示并优先播报最终回答。
- 已完成人工验收: V0.6 FVS 真实集成通过。
- 已实现 V0.7 Gateway 本地 Excel 问数 Adapter, 覆盖 11 个脱敏样例问数问题, 并已同步稳定演示脚本和客户验收清单。
- 已实现 V0.9 交付脚本、演示稳态模式、日志包导出和关键异常兜底体验。

## V0.1 Acceptance

- [x] 创建 `apps/web` Vue 3 + TypeScript + Vite 工程。
- [x] 创建 `apps/api` FastAPI 工程。
- [x] 创建 `docker-compose.yml`。
- [x] `GET /api/health` 返回 ok。
- [x] `POST /api/chat` 可通过 Mock Dora 返回 `answer` / `screen_control` / `fallback`。
- [x] `GET /api/screen/actions` 返回动作白名单。
- [x] `POST /api/screen/execute` 合法 action 成功, 非法 action 被拒绝。
- [x] 前端可输入文本、调用 `/api/chat`、展示回复、执行 Mock FVS 动作。
- [x] 基础会话日志可写入 `data/` 或 SQLite。

## V0.2 Acceptance Draft

- [x] 增加 Dora Adapter / Client, 通过 `ENABLE_MOCK_DORA=false` 启用。
- [x] Mock Dora 默认仍可运行, 且 V0.1 验收不回退。
- [x] 支持 `DORA_AGENT_ID` 直接配置。
- [x] 支持 `DORA_AGENT_ID` 为空时按 `DORA_AGENT_NAME` 精确发现已发布 Agent。
- [x] Dora OpenClaw 请求使用 `.env` 中的 `DORA_BASE_URL`、`DORA_API_KEY`、`DORA_CHANNEL_TYPE`。
- [x] 支持 Dora 标准 JSON 输出解析。
- [x] 支持 Markdown 代码块包裹 JSON 的提取。
- [x] 支持自然语言输出包装为 `answer`。
- [x] Dora 输出非法 `screen_control.action.id` 时返回 `fallback`, 不执行动作。
- [x] Dora 请求失败或超时时返回安全兜底, 不暴露密钥或底层堆栈。
- [x] API 契约和数据契约同步更新。
- [x] Dora 后台发布党建大屏专用 Prompt 或切换到专用 Agent。
- [x] 真实 Dora Agent 输出项目 `screen_control` JSON 后, 完成端到端动作白名单验证。

## V0.3 Acceptance Draft

- [x] 保留 `ENABLE_MOCK_TTS=true` 和 `ENABLE_MOCK_ASR=true` 默认回退。
- [x] 增加 TTS Adapter / Provider 接口和 Mock TTS。
- [x] 增加 ASR Adapter / Provider 接口和 Mock ASR。
- [x] 前端可播放 TTS 返回音频或 Mock 音频状态。
- [x] 前端可上传或提交一段音频 / Mock ASR 输入, 返回识别文本。
- [x] ASR 文本可进入现有 `/api/chat` 流程。
- [x] 不接 RAGFlow, 不接真实 FVS。
- [x] 增加阿里云 Fun-ASR WebSocket Provider。
- [x] 增加阿里云 CosyVoice WebSocket Provider。
- [x] 本地 `.env` 可切换到真实 ASR / TTS。
- [x] 真实 TTS 接口验证通过。
- [x] 真实浏览器麦克风 ASR 人工验收通过。

## V0.4 Acceptance Draft

- [x] 前端提供“后台监听”启停开关, 只在用户授权后开启麦克风。
- [x] 前端具备 `idle` / `monitoring` / `wake_checking` / `recording` / `thinking` / `speaking` / `cooldown` 基础状态。
- [x] 通过本地 VAD 或音量阈值截取短音频片段, 避免持续上传环境音。
- [x] 命中 `config/wake-words.yaml` 中唤醒词后自动进入正式识别。
- [x] 未命中唤醒词时丢弃短片段, 不进入 `/api/chat`。
- [x] 唤醒后用户无需再点击“识别并发送”, 可完成 ASR -> Dora -> TTS。
- [x] 保留 Mock ASR / TTS / Dora / FVS 开关和手动按钮回退。
- [x] 浏览器真实麦克风唤醒人工验收通过。
- [x] 播报结束后进入短时连续对话窗口, 窗口内追问无需再次唤醒。
- [x] 连续对话窗口超时或达到最大轮数后回到唤醒监听。
- [x] 浏览器连续对话窗口人工验收通过。

## Files Created / Changed In V0.2

```text
apps/api/app/services/dora_client.py
apps/api/app/services/dora_normalizer.py
apps/api/app/main.py
apps/api/pyproject.toml
apps/api/uv.lock
.env.example
docs/integrations/DORA_INTEGRATION.md
```

## Files Created / Changed In V0.3

```text
.dockerignore
.env.example
docker-compose.yml
apps/api/app/config.py
apps/api/app/main.py
apps/api/app/models.py
apps/api/app/services/asr_provider.py
apps/api/app/services/tts_provider.py
apps/web/src/App.vue
apps/web/src/api.ts
apps/web/src/style.css
apps/web/src/types.ts
docs/06_API_CONTRACT.md
docs/07_DATA_CONTRACT.md
docs/08_CONFIG_GUIDE.md
docs/integrations/ASR_TTS_INTEGRATION.md
```

## Files Created / Changed In V0.4

```text
config/wake-words.yaml
config/README.md
apps/api/app/main.py
apps/api/app/models.py
apps/api/app/services/wake_words.py
apps/web/src/App.vue
apps/web/src/api.ts
apps/web/src/style.css
apps/web/src/types.ts
docs/06_API_CONTRACT.md
docs/07_DATA_CONTRACT.md
docs/08_CONFIG_GUIDE.md
docs/10_TEST_PLAN.md
docs/integrations/ASR_TTS_INTEGRATION.md
```

## Files Created / Changed In V0.4.1

```text
config/wake-words.yaml
config/README.md
apps/api/app/models.py
apps/web/src/App.vue
apps/web/src/style.css
apps/web/src/types.ts
docs/06_API_CONTRACT.md
docs/07_DATA_CONTRACT.md
docs/08_CONFIG_GUIDE.md
docs/10_TEST_PLAN.md
docs/integrations/ASR_TTS_INTEGRATION.md
```

## Files Created / Changed In V0.5

```text
docs/demo_knowledge/
docs/integrations/RAGFLOW_INTEGRATION.md
docs/CODEX_CONTEXT.md
docs/05_DEVELOPMENT_PLAN.md
docs/08_CONFIG_GUIDE.md
docs/10_TEST_PLAN.md
docs/12_CUSTOMER_HANDOFF.md
docs/13_RISKS_AND_TODO.md
docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md
docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md
docs/DEV_LOG.md
docs/NEXT_ACTIONS.md
docs/CHANGELOG.md
```

## Files Likely To Touch Next

```text
docs/11_POC_DEMO_SCRIPT.md
docs/12_CUSTOMER_HANDOFF.md
docs/08_CONFIG_GUIDE.md
docs/09_LOCAL_DEPLOY.md
docs/10_TEST_PLAN.md
docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md
docs/customers/zt-securities/DEMO_CASES.md
docs/customers/zt-securities/SCREEN_ACTIONS.md
docs/CODEX_CONTEXT.md
docs/NEXT_ACTIONS.md
docs/DEV_LOG.md
docs/CHANGELOG.md
docs/13_RISKS_AND_TODO.md
docs/decisions/
```

## V0.6 Guardrails

- 不绕过 `action_id` 白名单。
- 不执行模型生成的 JavaScript。
- 不把 FVS 控制 API Key 或敏感参数暴露到前端。
- 真实 FVS 控制接入前保留 Mock FVS 回退。
- 不做 2D / 3D 数字人形象。
- FVS 主模板侧如果后续接收消息, 也必须按 `action_id` 固定映射, 不根据 `functionName` 动态执行脚本。

## V0.7 Acceptance Draft

- [x] 标准演示脚本至少包含 10 个稳定问题。
- [x] 本地脱敏 Excel 问数链路可返回测试党建指标。
- [x] `/api/chat` 问数命中后不调用 Dora, 直接返回带数据来源的 `answer`。
- [x] `/api/chat/stream` 问数命中后返回 `metadata`、`dora_delta`、`answer`。
- [x] Docker Compose 中 API 可读取 `/app/docs/demo_data/ask_metrics`。
- [ ] 正式验收报告补充现场复演结果、截图和耗时。
- [ ] 客户确认正式问数数据源、指标口径和刷新方式。

## V0.8 Acceptance Draft

- [x] 新增客户私有配置目录 `config/customers/zt-securities/`。
- [x] 新增 `CUSTOMER_ID` / `CUSTOMER_CONFIG_DIR` 配置并接入后端配置加载。
- [x] 客户级 Screen Actions、Ask Metrics、Demo Cases、Wake Words 已接入覆盖; Dora、RAGFlow、Voice、FVS 非敏感客户配置样例已落地。
- [x] 新增 `ASK_METRICS_MODE=excel|dora|auto`。
- [x] `ASK_METRICS_MODE=excel` 保持现有 11 个 Excel 问数 smoke 通过。
- [x] `ASK_METRICS_MODE=dora` 不让 Excel Adapter 抢答, 问题进入 Dora / Mock Dora 链路。
- [x] `ASK_METRICS_MODE=auto` 可在 Dora / Mock Dora 失败或兜底时回退 Excel。
- [x] 问数链路不执行模型生成 SQL、Python、JavaScript 或 shell 命令。
- [x] API / 数据 / 配置 / 测试文档同步更新。
- [x] TTS 字节级真流式首个音频 chunk 早于完整文件合成。
- [x] TTS 真流式失败时可回退分段 TTS。
- [x] 运维看板可查看依赖状态、最近会话、错误和耗时。

## V0.9 Acceptance

- [x] 新增本地预检脚本, 覆盖 Docker、端口、API、Web、RAGFlow、Dora、FVS、ASR、TTS。
- [x] 新增一键启停脚本 `scripts/start-poc.ps1` 和 `scripts/stop-poc.ps1`。
- [x] 新增 `scripts/export-logs.ps1`, 复用脱敏 Ops API 固化现场日志包导出流程。
- [x] 新增 `scripts/smoke-demo.ps1`, 固定演示问题集可一键 smoke。
- [x] 新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 和 `GET /api/demo/config`。
- [x] Dora 请求失败时, 演示稳态可回退本地 Excel 问数或 Mock Dora。
- [x] Excel 缺文件、Dora 流式异常、TTS 分段失败、FVS iframe 加载失败和麦克风权限失败不出现裸堆栈。
- [x] 保留对话、问数、TTS 真流式、分段 TTS fallback 和 FVS 控屏链路。

## V1.0 Acceptance Draft

- [x] 验收报告包含现场复演结果、截图附件位、耗时和客户确认项。
- [x] 部署方案覆盖 Windows + Docker Desktop + RAGFlow + FVS + Dora + ASR/TTS。
- [x] 用户手册覆盖唤醒、连续追问、问答、问数、大屏切换和兜底。
- [x] 运维手册覆盖启停、预检、日志、故障排查和配置更换。
- [x] 配置手册覆盖客户私有配置、Mock 开关、问数模式和密钥边界。
- [x] 测试报告覆盖 V0.7 / V0.8 / V0.9 已验证项和客户现场待确认项。
- [x] 客户移交清单覆盖交付物、环境、密钥、操作、验收场景、风险和签收。
