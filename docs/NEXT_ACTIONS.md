# Next Actions

## Current Phase

V0.8 功能增强版准备。

## Phase Status

V0.5 已完成人工验收。已完成本地 RAGFlow Docker Desktop 基础部署、MCP self-host 启动、最小党建知识库资料准备、公网 MCP 映射连通性验证、`zt_party_building_demo` dataset 创建、8 份测试资料上传和解析。MCP `ragflow_retrieval` 已可通过本地和公网地址返回知识库 chunk。已按当前边界完成 Dora 通过公网 MCP 调用 RAGFlow 的真实知识库问答验证: RAGFlow 固定负责 `keyword=false` 向量检索, Dora 负责最终回答生成。已在本地 RAGFlow MCP server 做 POC 返回量瘦身, 并在 POC Gateway 新增 `/api/chat/stream` + 分段 TTS, 降低知识库问答的语音首响等待。

V0.6 已完成人工验收。已完成数字人前端主页面 iframe 嵌入 FVS 看板、Web Nginx `/webroot/` 同源代理、四个 FVS 测试页 `page_number=1/2/3/4` 切换、FVS 主画布悬浮语音层、未唤醒角落语音 icon、唤醒 / 连续追问 / 思考 / 播报展开语音动画和文字记录, 以及等待提示音被 AI 结果 TTS 优先打断的交互策略。用户确认“0.6验收完成”。

问数测试数据已准备并接入: `docs/demo_data/ask_metrics/` 下包含党员学习、组织生活与党建活动、党员发展流程 3 份脱敏 Excel, `config/ask-metrics.yaml` 管理工作簿和 sheet 映射。V0.7 已新增 Gateway 本地只读 Excel 问数 Adapter, `/api/chat` 和 `/api/chat/stream` 会在调用 Dora 前优先匹配问数意图, 目前已通过 11 个固定问数问题 smoke。

用户已决定调整后续顺序: 先做功能增强, 再做交付前优化, 最后输出验收报告、部署方案、用户手册等材料。路线已记录到 `docs/14_ENHANCEMENT_ROADMAP.md` 和 ADR-0011。

## Next Task

进入 V0.8 功能增强版。第一推荐 goal:

```text
完成 V0.8 功能增强第一阶段: 重构客户私有配置目录, 并实现 ASK_METRICS_MODE=dora|excel|auto 的问数模式切换, 保留当前 Excel fallback, 更新相关文档和验证用例。
```

本 goal 的边界:

- 新增 `CUSTOMER_ID` 和 `CUSTOMER_CONFIG_DIR`。
- 建立 `config/customers/zt-securities/` 客户私有配置目录。
- 把 FVS 地址、Dora Agent、RAGFlow 地址、ASR/TTS 参数、问数模式、动作白名单、演示用例等尽量配置化。
- 新增 `ASK_METRICS_MODE=excel|dora|auto`。
- `excel` 模式保留当前 11 个固定 Excel 问数问题。
- `dora` 模式让 Dora 承接通用问数。
- `auto` 模式优先 Dora, Dora 失败 / 超时 / 兜底时回退 Excel。
- 不执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell 命令。
- 不进入 TTS 真流式、运维看板、预检脚本或验收报告, 除非当前 goal 完成后用户继续指定。

继续保留 Mock Dora / ASR / TTS / FVS 回退。FVS 控制仍必须由后端白名单校验后的 `action_id` 驱动, 不允许执行模型生成 JavaScript。

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

- V0.8: 功能增强版, 覆盖 Dora 通用问数、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。
- V0.9: 交付优化版, 覆盖预检脚本、一键启停、日志导出、演示模式和异常体验优化。
- V1.0: POC 验收交付版, 输出验收报告、部署方案、用户手册、运维手册、配置手册和测试报告。

## Recommended Prompt

```text
请先阅读 AGENTS.md、docs/CODEX_CONTEXT.md、docs/NEXT_ACTIONS.md、docs/05_DEVELOPMENT_PLAN.md、docs/14_ENHANCEMENT_ROADMAP.md、docs/06_API_CONTRACT.md、docs/07_DATA_CONTRACT.md 和 docs/13_RISKS_AND_TODO.md。当前 V0.5 RAGFlow MCP、V0.6 FVS 真实集成均已人工验收, V0.7 已完成本地 Excel 问数 Adapter 和 11 个问数 smoke。用户已决定先做功能增强, 再做交付优化, 最后输出验收报告 / 部署方案 / 用户手册。下一步进入 V0.8 第一阶段: 重构客户私有配置目录, 实现 `ASK_METRICS_MODE=dora|excel|auto`, 保留 Excel fallback, 不执行模型生成 SQL/Python/JavaScript, 不绕过 action_id 白名单。完成后更新 DEV_LOG、NEXT_ACTIONS、CHANGELOG、风险记录和相关契约文档。
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
- 已实现 FVS 主画布悬浮语音层: 未唤醒时只显示角落麦克风入口, 唤醒 / 连续追问 / 思考 / 播报时展开语音状态、动画和文字记录。
- 已实现等待提示音策略: 正式指令或连续追问进入处理后立即播报“收到, 正在为您查找信息。”, AI 结果 TTS 开始时打断等待提示并优先播报最终回答。
- 已完成人工验收: V0.6 FVS 真实集成通过。
- 已实现 V0.7 Gateway 本地 Excel 问数 Adapter, 覆盖 11 个脱敏样例问数问题, 并已同步稳定演示脚本和客户验收清单。

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
config/customers/zt-securities/
config/README.md
config/ask-metrics.yaml
.env.example
docker-compose.yml
apps/api/app/config.py
apps/api/app/main.py
apps/api/app/services/ask_metrics.py
apps/api/app/services/dora_client.py
apps/api/app/services/yaml_loader.py
docs/06_API_CONTRACT.md
docs/07_DATA_CONTRACT.md
docs/08_CONFIG_GUIDE.md
docs/10_TEST_PLAN.md
docs/14_ENHANCEMENT_ROADMAP.md
docs/NEXT_ACTIONS.md
docs/DEV_LOG.md
docs/CHANGELOG.md
docs/13_RISKS_AND_TODO.md
docs/customers/zt-securities/
docs/integrations/DORA_INTEGRATION.md
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

- [ ] 新增客户私有配置目录 `config/customers/zt-securities/`。
- [ ] 新增 `CUSTOMER_ID` / `CUSTOMER_CONFIG_DIR` 配置并接入后端配置加载。
- [ ] 客户级 FVS、Dora、RAGFlow、Voice、Screen Actions、Ask Metrics、Demo Cases 可覆盖默认配置。
- [ ] 新增 `ASK_METRICS_MODE=excel|dora|auto`。
- [ ] `ASK_METRICS_MODE=excel` 保持现有 11 个 Excel 问数 smoke 通过。
- [ ] `ASK_METRICS_MODE=dora` 可由 Dora 承接通用问数。
- [ ] `ASK_METRICS_MODE=auto` 可在 Dora 失败 / 超时 / 兜底时回退 Excel。
- [ ] 问数链路不执行模型生成 SQL、Python、JavaScript 或 shell 命令。
- [ ] API / 数据 / 配置 / 测试文档同步更新。
