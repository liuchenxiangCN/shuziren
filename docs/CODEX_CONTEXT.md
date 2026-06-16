# Codex Context

本文件是 Codex 跨对话恢复上下文的第一入口。新对话开始时, 先阅读本文件, 再阅读 `NEXT_ACTIONS.md` 和 `DEV_LOG.md`。

## Project

通用可配置数字人本地 POC 工程。中天证券党建大屏是当前客户配置实例, 不是项目本体。

## Goal

构建一套可复用给多个客户和多个大屏场景的本地 POC 模板, 通过配置完整跑通:

```text
语音唤醒 -> ASR -> 文本问题 -> Dora Agent
-> Dora 问数 / RAGFlow 知识库 / 大屏控制动作
-> 回复文本 / 图文结果 / screen_action
-> TTS -> 前端播报 + 字幕 + 动效 + FVS 控制
```

中天证券需求通过 `config/customers/zt-securities/`、`docs/customers/zt-securities/` 和客户交付包实现。

## Current Phase

V1.0 POC 验收交付包已输出。当前主线优化任务已切到通用可配置数字人定位和能力路由与配置中心: 先保持主线清洁基线, 再做只读 effective config 和配置页。

## Latest Update

2026-06-16 已完成通用可配置数字人阶段 4: 新增本地 `ScreenControlResolver`, 固定控屏命令可先按后端白名单 action label / description 解析为候选 `action_id`, 未命中仍走 Dora / Mock Dora。`/api/screen/execute` 在保留 `success`、`action_id`、`speak_text`、`request_id`、`error` 兼容字段的同时, 返回本次 `authorized_action` / `resolved_action`, 包含 `target`、`provider`、`fvs_function`、`fvs_routing`、净化后的 `params`、schema / allowlist 校验状态和拒绝原因。前端 FVS 执行路径已改为只使用本次 execute 响应中的授权动作, 不再依赖 `GET /api/screen/actions` 缓存执行参数; 该接口继续用于只读按钮展示。非法 action_id、非法 params、参数值覆盖和未知 target 均安全拒绝。本轮未实现可写配置、Prompt 编辑、可写 action 配置、配置 validate/test/reload/audit、Database Provider 真实查询、SQL 执行、外部 LLM summarizer 或 KnowledgeDirect 扩展。验证已通过: `corepack.cmd pnpm --dir apps/web build`; `python -m compileall apps/api/app`; uv + FastAPI TestClient 阶段 4 smoke 85 项; 静态验收搜索; `git diff --check`。

2026-06-16 已完成通用可配置数字人阶段 3: `KnowledgeDirectProvider`、`RagflowKnowledgeRetriever` 和后端受控 `SourceBoundSummarizer` 已落地。默认 `KNOWLEDGE_MODE=dora`, 既有 Dora -> RAGFlow MCP 知识库路径不退化; 显式启用 `local_ragflow_llm` 时, Gateway 只调用 RAGFlow 检索 chunks/metadata, summarizer 只基于来源回答, `require_sources=true`, `no_evidence_policy=fallback`。命中时返回标准 `answer` 且包含 `display.sources` / `source_summary`; 无检索结果或依据不足时返回 fallback, 不编造。当前 summarizer 为 `source_bound_extractive`, 不调用外部 LLM。Database Provider、外部 LLM summarizer、Prompt 编辑、可写 Prompt、可写 action 配置、配置 validate/test/reload/audit 和 `/api/screen/execute` 授权 action 响应增强仍未实现。新增 ADR-0024。验证已通过: uv + FastAPI TestClient 配置 / 问数 / KnowledgeDirect / stream / dora 模式 smoke; `corepack.cmd pnpm --dir apps/web build`; `python -m compileall apps/api/app`; 静态验收搜索; `git diff --check`。

2026-06-15 已完成通用可配置数字人阶段 2: 抽象 `AskMetricsProvider`, 新增配置驱动 `ExcelAskMetricsProvider`, 并将旧 `AskMetricsService` 中的客户实例问数规则迁移到 `config/customers/zt-securities/ask-metrics.yaml`。`apps/api/app/services/ask_metrics.py` 现在只做 provider 编排和 `ChatResponse` 包装, 不再包含客户实例 allowlist。根级 `config/ask-metrics.yaml` 保持通用空 metric 模板; `ASK_METRICS_MODE=excel|dora|auto` 行为不退化; `/api/config/effective` 和 `/api/config/schema` 已同步显示 AskMetricsProvider / Excel Provider implemented、Database Provider not_implemented。Database Provider 本轮未连接数据库、未执行 SQL, 也未开放可写配置、Prompt 编辑、KnowledgeDirectAdapter、LLM summarizer 或控屏授权响应增强。验证通过: 阶段 2 前 11 个问数基线 11/11; 迁移后 11/11; `corepack.cmd pnpm --dir apps/web build`; `python -m compileall apps/api/app`; uv + FastAPI TestClient 阶段 2 smoke; 验收搜索; `git diff --check`。

2026-06-15 已完成通用可配置数字人阶段 0A: `docker-compose.yml` 默认 `CUSTOMER_ID=default` 且 `CUSTOMER_CONFIG_DIR` 为空, API / Web 镜像名、容器名和包名均改为 `configurable-digital-human-*`; 根级唤醒词、演示用例、问数模板、前端 Mock 大屏、README 和脚本默认 smoke 均改为通用示例。中天证券内容继续保留在 `config/customers/zt-securities/` 等客户实例位置。阶段 0A 当时将 `apps/api/app/services/ask_metrics.py` 记录为阶段 2 前临时遗留 allowlist, 该遗留已在阶段 2 移除。未跟踪 `outputs/manual-20260614-212600/` 已标注为历史 / 手工输出, 不作为阶段 1 输入。验证通过: `corepack.cmd pnpm --dir apps/web build`; `python -m compileall apps/api/app`; `git diff --check`; 相关验收搜索通过。

2026-06-15 已按用户要求调整项目定位: 项目本体从“中天证券党建大屏数字人”改为“通用可配置数字人”。中天证券党建大屏只作为 `zt-securities` 客户 profile, 通过客户配置覆盖项目名称、客户名称、助手名称、Dora Agent、知识库、问数数据、FVS 看板、动作白名单、唤醒词和演示话术。代码侧已新增项目展示字段到 `Settings` 和 `/api/demo/config`, 前端首页标题和 Ops 客户显示改为读取配置, 运维日志导出标题改为配置化项目名; 根目录默认配置和 `.env.example` 改为通用默认, `config/customers/zt-securities/runtime.yaml` 保留中天证券实例元数据。新增 ADR-0023 记录该定位决策。

2026-06-15 已按用户要求恢复主线清洁基线: 本地临时宣传分支已删除, 主线工作树中的录屏页面、专用数字人组件、专用资产、临时客户配置、财务录屏动作白名单和临时 ADR 已移除。当前保留并更新主线架构图 `docs/15_MAINLINE_ARCHITECTURE_DIAGRAM.md`、能力路由与配置中心方案 `docs/16_CAPABILITY_ROUTING_AND_CONFIG_CENTER.md` 和 ADR-0022。方案已基于实际代码修正: 当前尚无 `/api/config/*`; `/api/screen/execute` 尚未返回完整授权 action; 前端仍依赖缓存动作列表执行 FVS; Compose 仍把 `config/` 只读挂载。阶段 0A 已完成后, 下一推荐 goal 是阶段 1: 新增脱敏只读 effective config 和 schema, 不直接开放可写配置, 不改变现有问答、问数、语音、TTS 或控屏行为。

2026-06-11 已实现“播报中长唤醒词确认打断”。新增 wake 配置 `barge_in_enabled`、`barge_in_wake_words`、`barge_in_vad_threshold`、`barge_in_min_audio_ms`、`barge_in_silence_ms`、`barge_in_max_audio_ms` 和 `barge_in_ignore_after_tts_start_ms`; 默认和中天证券客户配置启用播报中打断, 但只认长唤醒词“小天小天”“你好小天”, 不认短词“小天”。前端在 `speaking` 状态继续用 VAD 截短片段并调用 ASR 做 `barge_in` 确认; 命中后调用 `cleanupAudio()` 停止当前 TTS, 播放“您好。”并进入正式指令录音, 同句包含指令时剥离唤醒词后直接处理; 未命中、空识别或 ASR 失败时继续播报, 不进入 cooldown 或 `/api/chat`。新增 ADR-0017。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`。当前仍需真实麦克风复测播报中打断成功率和外放误打断率。

2026-06-11 已完成 V1.0 POC 验收交付包输出。新增 `docs/delivery/v1.0/` 正式交付包目录, 包含 `README.md`、`01_ACCEPTANCE_REPORT.md`、`02_DEPLOYMENT_PLAN.md`、`03_USER_MANUAL.md`、`04_OPERATIONS_MANUAL.md`、`05_CONFIGURATION_MANUAL.md`、`06_TEST_REPORT.md` 和 `07_CUSTOMER_HANDOFF_CHECKLIST.md`。交付包覆盖验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单, 并引用最近 smoke 证据 `logs/smoke/smoke-demo-20260611-011803.md` 以及日志包 `logs/exports/zt-poc-logs-20260611-011813.zip`。`NEXT_ACTIONS` 已更新为下一步客户现场验收复演: 按交付包启动环境、补齐截图附件、确认真实 Dora / RAGFlow / ASR / TTS / FVS 依赖、导出最终日志包并完成客户签字。交付包明确现场截图、真实客户网络、麦克风 / 播放权限、Dora / RAGFlow 连通性、`DEMO_STABLE_MODE` 状态和客户签字仍需现场确认; 继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

2026-06-11 已按用户要求完成 FVS 大屏交互精简与唤醒语音反馈优化。FVS iframe host 默认态由 76px 红色脉冲麦克风球改为小型低透明麦克风 icon, 未唤醒、唤醒词判定中、未命中唤醒词和冷却状态不展开悬浮对话层。展开态改为半透明直播评论流, 只显示最近用户识别文本和数字人回复文本, 不再显示监听调试、来源、`action_id`、reason、TTS 按钮或 audio 控件。FVS 主画布右上角“运维”悬浮入口已移除, 运维看板改为同一前端服务的独立路径 `/ops`, 继续复用只读脱敏 Ops API, 不新增端口或后端接口。命中唤醒词后前端立即播报“您好。”, 若同句包含指令则继续处理, 等待提示“收到, 正在为您查找信息。”排在“您好。”之后, AI 最终回复仍可打断短提示。新增 ADR-0016。验证通过: `corepack pnpm --dir apps/web build`; `git diff --check`; 本地 Vite preview `/` 和 `/ops` HTTP 200; 源码断言确认无 FVS 运维悬浮按钮、存在唤醒提示、`/ops` 路由和评论流。当前工具环境未做截图级浏览器验证和真实麦克风音频顺序人工验证。

2026-06-11 已完成 V0.9 交付优化当前 scope。新增 PowerShell 交付脚本: `scripts/check-poc.ps1` 覆盖 Docker、端口、配置、API、Web、Ops 依赖和 RAGFlow 预检; `scripts/start-poc.ps1` / `scripts/stop-poc.ps1` 支持一键启停 API / Web, 启动脚本支持 `-Build`、`-DemoStable` 和可选 `-WithRagflow`; `scripts/export-logs.ps1` 基于脱敏 Ops API 导出现场日志包, 默认不包含 Docker 原生日志; `scripts/smoke-demo.ps1` 使用固定演示问题集做 API smoke, 可选执行后端白名单校验后的大屏动作。新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 和 `GET /api/demo/config`; 演示稳态下 Dora 请求失败会优先回退本地 Excel 问数或 Mock Dora, 未命中仍返回安全 fallback。前端新增“演示稳态”标识、动态演示题按钮和 FVS iframe 加载超时 / 失败兜底提示。后端补充 Excel 问数缺文件、Dora 流式异常、TTS 分段异常的安全兜底, 不向前端暴露堆栈或供应商异常原文。新增 ADR-0015。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `scripts/check-poc.ps1 -SkipExternal -Json`; `scripts/start-poc.ps1 -Build -DemoStable`; `GET /api/health`; `GET /api/demo/config` 返回 `stable_mode=true`; `scripts/smoke-demo.ps1 -ExecuteScreenActions`; `scripts/export-logs.ps1 -Zip`; `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json`; Codex Browser 验证前端演示稳态标识、动态演示题和 FVS iframe 超时兜底。后续已进入并完成 V1.0 交付包输出。继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。演示稳态只能作为固定演示保底, 不能替代真实依赖验收。

2026-06-11 已完成 V0.8 功能增强第三阶段。新增只读脱敏 Ops API: `GET /api/ops/health`、`/api/ops/dependencies`、`/api/ops/sessions`、`/api/ops/session/{session_id}`、`/api/ops/errors`、`/api/ops/metrics`、`/api/ops/export`; 后端复用 SQLite `session_logs`, 新增最近会话、单会话明细、错误列表、聚合耗时、最近耗时样本和 Markdown 导出。日志摘要、错误消息和导出内容会截断并脱敏常见 `api_key` / `token` / `password` / `Bearer` / `sk-*` / `ak-*` 模式。依赖状态覆盖 SQLite、Screen Actions、Dora、RAGFlow、ASR、TTS、FVS; Dora / RAGFlow 只做轻量只读 HTTP 探测, ASR / TTS 不主动上传音频或触发合成。前端新增“演示 / 运维”视图切换, 运维看板可查看依赖状态、最近会话、错误列表、耗时指标并导出 Markdown 日志; FVS iframe host 模式下也有右上角“运维”悬浮入口。新增 ADR-0014。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `docker compose up -d --build api web`; `GET /api/health`; Ops API smoke; `/api/ops/export` 密钥模式扫描未命中; Codex Browser 验证 FVS host 和 mock 模式均可进入运维看板。当前依赖聚合状态为 `error`, 原因为 Dora 探测超时、RAGFlow 探测失败, Ops API 本身返回正常。下一轮推荐 goal: “完成 V0.9 交付优化: 新增预检脚本、一键启停脚本、演示模式、日志导出和关键异常兜底体验。”继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

2026-06-10 已完成 V0.8 功能增强第二阶段。新增 `TTS_STREAMING_ENABLED`、`TTS_STREAMING_FALLBACK`、`TTS_STREAMING_AUDIO_FORMAT`; 后端 `TtsProvider` 新增 `stream_synthesize`, Mock TTS 可输出 PCM chunk, 阿里云 CosyVoice Provider 可逐块转发 WebSocket 二进制音频帧。新增 `POST /api/tts/stream`, 通过 SSE 返回 `metadata -> audio_chunk* -> end`, 失败时返回 `tts_error` 并由前端按 `TTS_STREAMING_FALLBACK=segment` 回退。前端新增 `/api/tts/stream` 客户端和 PCM Web Audio 播放器, 收到最终 `answer` 后优先真流式播报, 首个 AI 音频 chunk 会通过统一 `cleanupAudio()` 打断等待提示音; 真流式失败时回退 `/api/chat/stream` 的 `tts_ready` 分段音频或完整 `/api/tts` 文件。新增 ADR-0013。验证通过: `python -m compileall apps/api/app`; `corepack pnpm --dir apps/web build`; `docker compose config --services`; `git diff --check`; `docker compose up -d --build api web`; `GET /api/health`; 真实 TTS 配置下 `/api/tts/stream` 首个 PCM chunk 约 567ms 到达, `end.duration_ms=3387`, 共 33 个 chunk; 临时关闭 `TTS_STREAMING_ENABLED` 返回 `TTS_STREAMING_DISABLED` 和 `fallback=segment`; `/api/chat/stream` 问数仍返回 4 个 `tts_ready`; 前端 HTML / JS / CSS 资源 HTTP 200。Codex Browser 控制工具本轮未暴露, 未做截图级交互验证。下一轮推荐 goal: “完成 V0.8 功能增强第三阶段: 新增运维监控和日志看板, 覆盖依赖状态、最近会话、错误列表、耗时指标和日志导出。”继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

2026-06-10 已完成 V0.8 功能增强第一阶段。新增 `CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR` 和 `ASK_METRICS_MODE=excel|dora|auto`; 新增 `config/customers/zt-securities/` 客户私有配置目录, 包含 `runtime.yaml`、`screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`、`wake-words.yaml`、`dora.yaml`、`ragflow.yaml`、`voice.yaml`、`fvs.yaml` 和 `customer.env.example`。后端启动时会加载客户级 Screen Actions / Ask Metrics / Demo Cases / Wake Words 覆盖层, 并读取 Dora / RAGFlow / Voice 非敏感客户配置; 旧 `.env` 中等于根目录默认路径的变量不会阻止客户覆盖, 真正自定义路径仍优先。`ASK_METRICS_MODE=excel` 保持 V0.7 Excel 优先, `dora` 不让 Excel Adapter 抢答, `auto` 在 Dora / Mock Dora 返回 fallback 或请求失败时回退 Excel。已新增 ADR-0012。验证通过: `python -m compileall apps/api/app`; `docker compose config --services`; `docker compose up -d --build api`; 容器内配置指向 `/app/config/customers/zt-securities/*.yaml`; `GET /api/health`; `excel` 模式 11 个问数 smoke; `入党流程是什么?` 未被 Excel 抢占; `/api/chat/stream` 问数事件 `metadata -> dora_delta -> answer -> tts_ready -> end`; `dora` / `auto` 路由函数级验证。当前默认容器已恢复 `ASK_METRICS_MODE=excel`。下一轮推荐 goal: “完成 V0.8 功能增强第二阶段: 实现 TTS 字节级真流式播放, 保留分段 TTS fallback, 更新 `/api/chat/stream` 或新增 `/api/tts/stream`, 并完成前端播放、打断和回退验证。”继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

2026-06-10 用户确认后续路线调整: 不立即输出验收报告、部署方案和用户手册, 而是先做功能增强, 再做交付前优化, 最后输出正式验收交付包。已新增 `docs/14_ENHANCEMENT_ROADMAP.md` 和 ADR-0011, 将后续拆为 V0.8 / V0.9 / V1.0。V0.8 功能增强版覆盖 Dora 通用问数 + Excel fallback、TTS 字节级真流式 + 分段 TTS fallback、运维监控 / 日志看板、客户私有配置目录。V0.9 交付优化版覆盖预检脚本、一键启停、日志导出、演示模式和异常体验优化。V1.0 POC 验收交付版输出验收报告、部署方案、用户手册、运维手册、配置手册和测试报告。继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

2026-06-10 已开始 V0.7 POC 稳定版准备, 并补齐本地问数链路。新增 `apps/api/app/services/ask_metrics.py`, 作为 Gateway 本地只读 Excel 问数 Adapter, 使用标准库读取 `docs/demo_data/ask_metrics/` 下三份脱敏 `.xlsx`; 文件名和 sheet 映射由 `config/ask-metrics.yaml` 管理。`/api/chat` 和 `/api/chat/stream` 会在调用 Mock Dora / 真实 Dora 前优先匹配问数意图, 命中后直接返回带 `display.source` 的 `answer`, 避免模型编造 Excel 查询结果。Docker 镜像已复制 `docs/demo_data`, Compose 已只读挂载 `./docs/demo_data:/app/docs/demo_data:ro`, 并新增 `ASK_METRICS_DATA_DIR=/app/docs/demo_data/ask_metrics`、`ASK_METRICS_CONFIG_PATH=/app/config/ask-metrics.yaml`。已验证 11 个问数问题: 学习完成率 87.5%、已完成学习 112 人、最低完成率支部信息技术支部 83.3%、主题党日 34 次、组织生活平均参会率 83.9%、整改闭环率 46.7%、入党积极分子 12 人、发展对象 7 人及分布、本年转正 3 人、材料待补充 3 人、党建整体总结。`/api/chat/stream` 问数已验证事件顺序 `metadata -> dora_delta -> answer`; “入党流程是什么?” 未被问数 Adapter 拦截。已同步 ADR-0010、演示脚本、测试计划、客户验收清单、配置 / 部署 / 风险 / 交付文档。下一步继续 V0.7 正式验收报告和现场复演记录, 并确认正式客户问数数据源和指标口径。

2026-06-10 用户确认“0.6验收完成”, 项目进入 V0.7 POC 稳定版。V0.6 已完成 FVS 真实集成: 最初尝试 FVS 网页框嵌入数字人页面, 后因消息调试和麦克风 iframe 权限问题切换为“以数字人前端为主体, iframe 嵌入 FVS 看板”。项目已新增前端 FVS Adapter, `VITE_FVS_INTEGRATION_MODE=iframe` 且配置 `VITE_FVS_URL` 时, 数字人主页面加载 FVS iframe。本地 `.env` 已切到 `iframe` 模式并使用相对路径 `/webroot/...`。前端还支持运行时 URL 参数 `?fvs_url=...` 临时指定 FVS 地址。用户提供的本机 FVS 测试看板页面映射为 `总览=page_number=1`、`成品库存=2`、`生产管理=3`、`设备分析=4`。直接跨端口嵌入 `localhost:8075` 时, FVS 返回 `X-Frame-Options: SAMEORIGIN`; 已通过 Web Nginx 同源代理 `/webroot/ -> http://host.docker.internal:8075/webroot/` 解决, 浏览器截图确认 FVS 看板可在 `http://127.0.0.1:18000` 中渲染。当前真实控制采用 FVS URL 参数切页: `/api/screen/execute` 白名单校验成功后, 前端改写 FVS iframe URL 的 `page_number`; 分页以外的复杂动作保留为后续增强。V0.6 还实现 FVS 主画布: 未唤醒时页面上层仅保留右下角语音交互 icon; 唤醒、连续追问、思考、TTS 加载或播报时展开悬浮语音面板, 显示监听状态、波形动画和文字记录。正式指令或连续追问进入处理后, 前端立即播报等待提示音 `收到, 正在为您查找信息。`; AI 结果 TTS 开始播放时会打断等待提示并优先播报最终回答。V0.7 下一步聚焦稳定演示脚本、10+ 测试问题、问数方案、部署移交和验收报告。仍禁止执行模型生成 JavaScript, FVS 侧也不得根据 `functionName` 动态执行脚本。

2026-06-10 已完成一轮 V0.5 交互速度优化: 在本地 `D:\Project\ragflow` 的 RAGFlow MCP server 中做 POC 返回量瘦身, 固定 `keyword=false`, 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`, 单 chunk content 最长 1200 字符, 只返回 Dora 生成回答所需的精简字段; `ragflow-cpu` 通过只读 volume 挂载该 server 脚本并已重建验证。主项目新增 `POST /api/chat/stream`, 后端消费 Dora SSE, 增量提取最终 JSON `speak_text`, 推送 `dora_delta`, 并用现有 TTS Provider 做短文本分段并发合成, 前端按 `tts_ready.index` 顺序播放。若 Dora 只返回最终 answer, 后端仍会对最终 `speak_text` 分段合成。本轮抽样验证“入党流程是什么?”时首个 `dora_delta` 约 8.5s 到 17.6s、首个分段 `tts_ready` 约 11.6s 到 19.8s、最终 `answer` 约 12.0s 到 21.3s、全部分段 TTS 约 15.1s 到 27.1s 就绪。当前仍不是音频字节级真流式 TTS; 最大剩余耗时主要在 Dora 工具调用前后推理。

2026-06-10 已新增 `docs/demo_data/ask_metrics/` 党建问数测试 Excel 数据, 包含 `zt_party_study_metrics_2026.xlsx`、`zt_party_org_life_metrics_2026.xlsx`、`zt_party_development_metrics_2026.xlsx` 三份脱敏样例。学习表 Dashboard 口径为党员总数 128 人、已完成学习 112 人、完成率 87.5%。当前仅完成问数数据源准备, 尚未实现真实 Excel 问数解析 / 查询链路。

2026-06-10 用户已确认 V0.5 人工验收完成。V0.5 验收范围包括真实 Dora 通过公网 MCP 调用本地 RAGFlow `zt_party_building_demo` 知识库、Gateway 工具消息解析修复、RAGFlow MCP 返回量瘦身、`/api/chat/stream` 分段 TTS 优化和前端/语音链路人工体验确认。

当前工程已可通过 Docker Compose 启动 Vue 3 前端和 FastAPI 后端, 跑通文本输入 -> Mock Dora -> Mock FVS -> 前端展示 -> SQLite 会话日志。后端已支持 `ENABLE_MOCK_DORA=false` 调用 Dora OpenClaw `agents` 和 `sse/chat`, 并把 Dora 输出归一为 `/api/chat` 的 `answer` / `screen_control` / `fallback`。Dora 后台已发布专用 Agent `中天证券党建大屏语音助手`, 本地 `.env` 使用 `DORA_AGENT_NAME=中天证券党建大屏语音助手` 且 `DORA_AGENT_ID` 为空, 已验证自动发现和真实控屏端到端: Dora 返回 `screen_control.action.id`, Gateway 白名单校验, `/api/screen/execute` 执行合法动作。V0.3 已新增 `AsrProvider` / `TtsProvider`、Mock ASR / Mock TTS、`POST /api/asr/transcribe`、`POST /api/tts` 和 `GET /api/tts/audio/{audio_id}`; 前端录音已改为 16k 单声道 WAV, ASR 文本进入 `/api/chat`, 回答后生成音频并展示播报按钮和原生音频控件。本地 `.env` 当前已切到真实阿里云语音: `ENABLE_MOCK_ASR=false`, `ENABLE_MOCK_TTS=false`, ASR 使用 `fun-asr-realtime`, TTS 使用 `cosyvoice-v3-flash` / `longanyang`; 真实 TTS 已验证可返回 mp3, 浏览器麦克风真实 ASR 已通过人工验收。V0.4 已新增 `GET /api/wake/config`, 前端“后台监听”显式开关、本地 RMS VAD 截段、唤醒词 ASR 判断、`idle` / `monitoring` / `wake_checking` / `recording` / `thinking` / `speaking` / `cooldown` 状态机、唤醒后同句指令提取或正式指令录音、TTS 自动播放尝试和冷却回监听, 且用户已验收可唤醒后正常对话。V0.4.1 已新增 `followup_listening` 连续对话窗口, 播报结束后可在 `followup_window_ms` 内直接追问, 达到 `max_followup_turns` 或超时后回到唤醒监听; 用户已完成人工验收。V0.5 已按用户要求改为本地 Docker Desktop 部署 RAGFlow, 本地路径 `D:\Project\ragflow`, 版本 `v0.25.6`, Web `http://127.0.0.1:18089`, 健康检查 `http://127.0.0.1:18089/api/v1/system/healthz`, MCP `/mcp` 为 `http://127.0.0.1:19382/mcp`, MCP `/sse` 为 `http://127.0.0.1:19382/sse`; RAGFlow self-host MCP Key 只写在 `D:\Project\ragflow\docker\.env`。已创建 `docs/demo_knowledge/` 8 份最小党建知识库资料。临时公网 MCP `http://liuchenxiang.uk:19382/mcp` 已通过 MCP `initialize` 和 `tools/list` 验证, 暴露 `ragflow_retrieval`。已配置默认 Embedding `text-embedding-v3@Tongyi-Qianwen`, 创建 `zt_party_building_demo` dataset, 上传 8 份测试资料并等待解析完成, 全部为 `DONE`; 本地和公网 MCP `ragflow_retrieval` 已可返回知识库 chunk。V0.5 边界为 Dora 负责最终回答、RAGFlow 负责 `keyword=false` 向量检索, 不要求 RAGFlow 默认 Chat 模型或 chat / assistant。当前 `.env` 已切换 `ENABLE_MOCK_DORA=false`, 已通过 `/api/chat` 验证 Dora Agent 经公网 MCP 调用 RAGFlow 后返回知识库 `answer`: 张书记近期调研、入党流程、党员学习制度、党支部组织建设规范均通过。V0.5 和 V0.6 均已完成人工验收。后续仍不直接执行真实 FVS JS, 不绕过动作白名单, 不持续上传环境音。

## Must Read First

1. `AGENTS.md`
2. `docs/00_INDEX.md`
3. `docs/NEXT_ACTIONS.md`
4. `docs/DEV_LOG.md`
5. `docs/05_DEVELOPMENT_PLAN.md`
6. `docs/13_RISKS_AND_TODO.md`
7. `docs/decisions/`

## Core Architecture

- Frontend: Vue 3 + TypeScript + Vite
- Backend: Python FastAPI
- Deployment: Docker Compose
- Frontend package manager: pnpm
- Backend package manager: uv
- Backend Python runtime: Python 3.12 in Docker, Python 3.11/3.12 acceptable for non-Docker local development
- Config: `.env` + YAML
- Storage: SQLite
- Animation: Canvas 2D + Web Audio API + CSS
- Chart: ECharts
- Agent: Dora
- Knowledge Base: RAGFlow
- Screen: FVS
- ASR / TTS: 国产供应商优先, 默认阿里云百炼, 其他供应商通过 Adapter 扩展

## Non-Negotiable Rules

- 不在前端暴露 API Key。
- 不让大模型直接生成并执行 JavaScript。
- 大屏控制只能使用 `action_id`。
- 后端必须通过动作白名单校验 `action_id`。
- Dora / ASR / TTS / FVS 必须保留 Mock 开关。
- 外部系统接入必须通过 Adapter / Provider 层隔离。
- 每完成一轮开发必须更新 `DEV_LOG.md`、`NEXT_ACTIONS.md`、必要时更新 `13_RISKS_AND_TODO.md`。
- 客户差异放在客户配置和客户文档中, 不写死到核心代码。

## Resume Protocol

开始开发前:

1. 阅读 `NEXT_ACTIONS.md`, 确认当前任务。
2. 阅读相关设计文档和 ADR。
3. 如任务涉及接口或数据结构, 先检查 `06_API_CONTRACT.md` 和 `07_DATA_CONTRACT.md`。
4. 执行任务时保持变更聚焦, 不跨阶段实现真实外部服务。
5. 完成后更新开发记录、下一步、风险和变更日志。

推荐对 Codex 的启动提示:

```text
请先阅读 AGENTS.md、docs/CODEX_CONTEXT.md、docs/NEXT_ACTIONS.md、docs/05_DEVELOPMENT_PLAN.md 和 docs/delivery/v1.0/README.md。当前 V0.5 RAGFlow MCP、V0.6 FVS 真实集成都已完成人工验收, V0.7 已实现 Gateway 本地 Excel 问数 Adapter 并通过 11 个问数 smoke。V0.8 已完成客户私有配置目录和 `ASK_METRICS_MODE=excel|dora|auto`、TTS 字节级真流式 `/api/tts/stream`、前端 PCM Web Audio 播放和分段 TTS fallback、只读脱敏 Ops API 与前端运维监控 / 日志看板。V0.9 已完成预检脚本、一键启停脚本、演示稳态模式、日志包导出流程和关键异常兜底体验。FVS 大屏悬浮层已精简为小型低透明 icon + 半透明对话评论流, 运维入口为 `/ops`, 命中唤醒词后会先播报“您好。”。V1.0 交付包已输出到 `docs/delivery/v1.0/`, 下一步是客户现场验收复演: 按交付包启动环境、补齐截图附件、确认真实 Dora / RAGFlow / ASR / TTS / FVS 依赖、导出最终日志包并完成签字。继续坚持 action_id 白名单校验, 禁止执行模型生成 SQL/Python/JavaScript/shell, 不在前端或运维页暴露 API Key。
```
