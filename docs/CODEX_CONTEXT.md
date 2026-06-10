# Codex Context

本文件是 Codex 跨对话恢复上下文的第一入口。新对话开始时, 先阅读本文件, 再阅读 `NEXT_ACTIONS.md` 和 `DEV_LOG.md`。

## Project

中天证券党建大屏对话数字人本地 POC 工程。

## Goal

构建一套可复用给客户的本地 POC 模板, 完整跑通:

```text
语音唤醒 -> ASR -> 文本问题 -> Dora Agent
-> Dora 问数 / RAGFlow 知识库 / 大屏控制动作
-> 回复文本 / 图文结果 / screen_action
-> TTS -> 前端播报 + 字幕 + 动效 + FVS 控制
```

## Current Phase

V0.8 功能增强版准备。

## Latest Update

2026-06-10 用户确认后续路线调整: 不立即输出验收报告、部署方案和用户手册, 而是先做功能增强, 再做交付前优化, 最后输出正式验收交付包。已新增 `docs/14_ENHANCEMENT_ROADMAP.md` 和 ADR-0011, 将后续拆为 V0.8 / V0.9 / V1.0。V0.8 功能增强版覆盖 Dora 通用问数 + Excel fallback、TTS 字节级真流式 + 分段 TTS fallback、运维监控 / 日志看板、客户私有配置目录。V0.9 交付优化版覆盖预检脚本、一键启停、日志导出、演示模式和异常体验优化。V1.0 POC 验收交付版输出验收报告、部署方案、用户手册、运维手册、配置手册和测试报告。下一轮推荐 goal: “完成 V0.8 功能增强第一阶段: 重构客户私有配置目录, 并实现 `ASK_METRICS_MODE=dora|excel|auto` 的问数模式切换, 保留当前 Excel fallback, 更新相关文档和验证用例。”继续坚持不执行模型生成 SQL / Python / JavaScript / shell, 不绕过 `action_id` 白名单, 不在前端或运维页暴露 API Key。

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
请先阅读 AGENTS.md、docs/CODEX_CONTEXT.md、docs/NEXT_ACTIONS.md、docs/05_DEVELOPMENT_PLAN.md 和 docs/14_ENHANCEMENT_ROADMAP.md。当前 V0.5 RAGFlow MCP、V0.6 FVS 真实集成都已完成人工验收, V0.7 已实现 Gateway 本地 Excel 问数 Adapter 并通过 11 个问数 smoke。用户已决定先做功能增强, 再做交付前优化, 最后输出验收报告 / 部署方案 / 用户手册。下一步进入 V0.8 第一阶段: 重构客户私有配置目录, 并实现 `ASK_METRICS_MODE=dora|excel|auto`, 保留当前 Excel fallback。继续坚持 action_id 白名单校验, 禁止执行模型生成 SQL/Python/JavaScript/shell, 不在前端或运维页暴露 API Key。完成后更新 DEV_LOG、NEXT_ACTIONS、CHANGELOG 和必要的风险 / 契约文档。
```
