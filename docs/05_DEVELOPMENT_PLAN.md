# 开发计划

## 总原则

- 文档先行: 先写清目标、边界、验收, 再开发。
- Mock 先行: 外部依赖先用 Mock 跑通主链路。
- Adapter 化: Dora、ASR、TTS、FVS、RAGFlow 都通过适配层接入。
- 通用优先: 项目本体是通用可配置数字人, 客户实例只能通过 `config/customers/<customer-id>/`、客户文档和环境变量进入系统。
- 可恢复: 每轮完成后更新 `DEV_LOG.md`、`NEXT_ACTIONS.md`、`CHANGELOG.md`。
- 可移交: 交付物必须让客户能读懂当前能力、部署方式、限制和后续路线。

## 阶段路线

| 阶段 | 名称 | 目标 |
| --- | --- | --- |
| V0.0 | 文档体系 | 建立跨对话上下文和交付文档体系 |
| V0.1 | Mock 闭环 | 文本输入 -> Mock Dora -> Mock FVS -> 前端展示 -> 日志 |
| V0.2 | Dora 接入 | 接入真实 Dora Agent 和 SSE 输出 |
| V0.3 | TTS / ASR | 接入 TTS 播报和 ASR 识别 |
| V0.4 | 语义唤醒 | VAD + ASR 判断唤醒词 |
| V0.5 | RAGFlow MCP | Dora 通过 MCP 调用 RAGFlow 知识库 |
| V0.6 | FVS 真实集成 | FVS iframe / postMessage / Adapter 联调 |
| V0.7 | POC 稳定版 | 演示脚本、测试报告、移交文档 |
| V0.8 | 功能增强版 | Dora 通用问数、TTS 字节级真流式、运维看板、客户私有配置 |
| V0.9 | 交付优化版 | 预检脚本、一键启停、日志导出、演示模式、异常兜底 |
| V1.0 | POC 验收交付版 | 验收报告、部署方案、用户手册、运维手册、测试报告 |

## V0.0 文档体系

### Goal

建立项目长期记忆系统, 让 Codex 和后续开发人员可跨对话继续。

### Scope

- 创建文档总入口。
- 创建项目蓝图、架构、开发计划、接口契约、数据契约。
- 创建 ADR 决策记录。
- 创建集成说明和客户资料目录。
- 创建开发日志、下一步、风险清单。

### Acceptance

- `docs/CODEX_CONTEXT.md` 可作为新对话入口。
- `docs/NEXT_ACTIONS.md` 明确下一阶段任务。
- `docs/DEV_LOG.md` 已记录文档体系初始化。

### Status

Done。

## V0.1 Mock 闭环

### Goal

初始化可 Docker 启动的最小工程, 先跑通文本 Mock 主链路。

### Scope

- 初始化项目结构。
- 创建 FastAPI 后端。
- 创建 Vue 3 前端。
- 增加 Docker Compose。
- 增加 `.env.example`。
- 增加 `/api/health`。
- 增加 `/api/chat` Mock Dora。
- 增加 `/api/screen/actions`。
- 增加 `/api/screen/execute`。
- 前端实现文本输入、状态展示、回复窗口、Mock 大屏动作。
- SQLite 或文件方式记录基础会话日志。

### Non-Scope

- 不接真实 Dora。
- 不接真实 ASR。
- 不接真实 TTS。
- 不部署真实 RAGFlow。
- 不真实调用 FVS JS。

### Acceptance

```text
docker compose up -d --build
前端 http://localhost:18000 可访问
后端 http://localhost:18080/api/health 返回 ok
POST /api/chat 输入“切换到组织建设”返回 screen_control JSON
GET /api/screen/actions 返回动作列表
POST /api/screen/execute 合法 action 成功
非法 action 被拒绝
前端可输入文字、展示回复、触发 Mock FVS 动作
```

### Status

Done。

## V0.2 Dora 接入

### Goal

在保留 Mock 的前提下接入真实 Dora Agent。

### Scope

- Dora Client。
- Dora SSE 解析。
- Dora 输出 JSON 容错。
- Markdown 包裹 JSON 提取。
- 自然语言包装为 `answer`。
- `screen_control` 强制白名单校验。

### Acceptance

```text
ENABLE_MOCK_DORA=false
真实调用 Dora Agent
前端能展示 Dora 返回内容
Dora 输出非法 action_id 时后端拒绝执行
```

### Status

Done。已实现 OpenClaw `list_agents`、按名称解析已发布 Agent、SSE chat 和输出归一化; V0.1 Mock 回归通过。Dora 后台已发布 `中天证券党建大屏语音助手`, 真实 Dora `/api/chat` 可返回归一化 `answer` / `screen_control` / `fallback`; `screen_control.action.id` 已端到端通过后端白名单校验。

## V0.3 TTS / ASR

### Goal

接入可演示的语音输入和语音播报。

### Scope

- TTS Adapter。
- Mock TTS。
- 前端音频播放。
- ASR Adapter。
- Mock ASR。
- 前端录音上传。

### Acceptance

```text
输入 speak_text 可返回音频 URL 或音频流
前端可播放
声波随播放音频变化
用户说一句话后前端显示 ASR 文本
ASR 文本可进入 chat 流程
```

### Status

Done。已实现 `AsrProvider` / `TtsProvider` 接口、Mock ASR、Mock TTS、HTTP ASR/TTS 接口、前端录音 / Mock ASR 输入、ASR 文本进入 `/api/chat`、TTS 音频生成和前端播报控件。已接入阿里云百炼 Fun-ASR WebSocket 和 CosyVoice WebSocket; 真实 TTS 已验证通过, 浏览器麦克风真实 ASR 已通过人工验收。

## V0.4 语义唤醒

### Goal

通过 VAD + ASR 判断唤醒词, 完成第一阶段唤醒体验。

### Scope

- 前端 VAD。
- 短音频片段识别。
- 唤醒词 YAML 配置。
- 用户显式开启后台监听并授权麦克风。
- 前端监听状态机和超时兜底。
- 命中唤醒词进入 listening。
- 未命中不进入正式对话。

### Acceptance

```text
说“小天小天”进入 listening
说“你好小天”进入 listening
普通闲聊不触发正式对话
唤醒后可自动完成 ASR -> chat -> TTS, 不需要每轮点击识别按钮
```

### Status

Done。已完成并通过真实麦克风唤醒人工验收。已实现 `GET /api/wake/config`、前端后台监听开关、本地 RMS VAD、唤醒词 ASR 判断、状态机、唤醒后正式指令识别和 TTS 播报尝试。V0.4.1 已补充连续对话窗口, 并通过人工验收追问窗口、超时退出和轮数退出。

## V0.5 RAGFlow MCP

### Goal

让 Dora 可通过 MCP 调用 RAGFlow 测试知识库。

### Scope

- 整理 RAGFlow 本地部署说明。
- 准备测试知识库文档。
- 启用 MCP Server。
- Dora 配置外接 MCP。
- 知识库问答测试。

### Acceptance

```text
RAGFlow Web 可访问
MCP 地址可访问
Dora 可配置 MCP
至少 4 个党建知识库问题可返回答案
```

### Status

Done。已按用户要求改为本地 Docker Desktop 部署 RAGFlow `v0.25.6`; Web `http://127.0.0.1:18089` 可访问, 健康检查通过, MCP `/mcp` 与 `/sse` 端点已启动。已准备 `docs/demo_knowledge/` 8 份最小党建知识库资料, 并导入 `zt_party_building_demo` dataset 解析完成。MCP `ragflow_retrieval` 已可通过本地和公网地址返回知识库 chunk。V0.5 边界为 Dora 负责最终回答、RAGFlow 负责 `keyword=false` 向量检索; 不要求 RAGFlow 默认 Chat 模型或 chat / assistant。已通过 `/api/chat` 验证 Dora Agent 经公网 MCP 返回知识库答案, 覆盖张书记近期调研、入党流程、党员学习制度、党支部组织建设规范。已对本地 RAGFlow MCP server 做返回量瘦身, 并新增 `/api/chat/stream` + 分段 TTS, 验证知识库问题可更早出现首段音频。用户已确认 V0.5 人工验收完成。

## V0.6 FVS 真实集成

### Goal

将 Mock FVS 动作替换为真实 FVS 页面或 Tab 控制。当前优先路线为数字人前端作为主页面 iframe 嵌入 FVS 看板, 数字人前端只执行已通过 Gateway 白名单校验的 `action_id`。测试看板分页动作优先使用 URL 参数 `page_number` 切页; 复杂动作再向 FVS iframe 发送消息。

### Scope

- 数字人前端 iframe 加载 FVS 看板验证。
- FVS iframe 嵌入策略验证。
- FVS `X-Frame-Options: SAMEORIGIN` 时的同源代理验证。
- 数字人前端基于 `page_number` 的 iframe URL 切页联调。
- FVS 主画布上的悬浮语音入口、唤醒展开动画和文字记录。
- 唤醒后 / 连续追问后即时等待提示音, 且 AI 结果 TTS 就绪后优先打断等待提示。
- 数字人前端 `iframe.contentWindow.postMessage` + FVS 侧 message 监听 / Adapter 作为后续复杂动作联调。
- 动作白名单映射真实函数。

### Acceptance

```text
语音指令 -> action_id -> Gateway 校验 -> 数字人前端切换 FVS iframe page_number -> FVS 页面切换
至少 4 个分页动作可稳定执行
```

### Status

Done。V0.6 已完成人工验收。已准备前端 FVS Adapter, 当前方向切换为数字人主页面 iframe 嵌入 FVS 看板。已确认测试看板页面映射为 `总览=1`、`成品库存=2`、`生产管理=3`、`设备分析=4`; 已通过 Web Nginx `/webroot/` 同源代理解决本机 FVS `X-Frame-Options: SAMEORIGIN` 跨端口 iframe 拦截, 并验证四个分页按钮可切换 `page_number=1/2/3/4`。已把 FVS iframe host 调整为主画布铺满, 未唤醒时只显示角落麦克风入口, 唤醒 / 连续追问 / 思考 / 播报时展开悬浮语音面板, 并新增等待提示音与 AI 结果优先打断策略。用户确认“0.6验收完成”。

## V0.7 POC 稳定版

### Goal

形成可交付客户的 POC 稳定版本。

### Scope

- 标准演示脚本。
- 10+ 测试问题。
- 会话日志样例。
- 本地部署说明。
- 客户移交文档。
- 风险清单。
- 联调测试报告。

### Acceptance

```text
完整链路至少跑通:
1. 领导欢迎语
2. 党建文档问答
3. 党建问数
4. 大屏切换
```

### Status

Done for current scope。V0.5 和 V0.6 均已人工验收完成。V0.7 第一轮已完成本地脱敏 Excel 问数 Adapter、10+ 稳定演示问题、部署 / 移交 / 测试文档同步。用户已决定在正式验收报告前先做功能增强, 因此下一阶段进入 V0.8。

## V0.8 功能增强版

### Goal

在不破坏现有稳定 POC 的前提下, 增强真实交付能力: Dora 通用问数、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。

### Scope

- 客户私有配置目录:
  - `CUSTOMER_ID`。
  - `CUSTOMER_CONFIG_DIR`。
  - `config/customers/zt-securities/`。
  - 客户级 `runtime.yaml`、`fvs.yaml`、`dora.yaml`、`ragflow.yaml`、`voice.yaml`、`screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`。
- Dora 通用问数:
  - `ASK_METRICS_MODE=dora|excel|auto`。
  - `excel` 保留当前固定 Excel Adapter。
  - `dora` 走 Dora 通用问数。
  - `auto` 优先 Dora, 失败或兜底后回退 Excel。
- TTS 字节级真流式:
  - `TTS_STREAMING_ENABLED`。
  - `TTS_STREAMING_FALLBACK=segment`。
  - 后端流式 TTS Provider。
  - 前端 Web Audio / MediaSource 播放。
- 运维监控和日志看板:
  - 依赖健康。
  - 最近会话。
  - 错误列表。
  - 耗时指标。
  - 日志导出。

### Non-Scope

- 不输出正式验收报告。
- 不取消 Excel fallback。
- 不取消分段 TTS fallback。
- 不接分页以外的 FVS 组件级控制, 除非当前 goal 明确要求。
- 不执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell 命令。

### Acceptance

```text
CUSTOMER_ID=zt-securities 时, 后端加载客户私有配置覆盖默认配置
ASK_METRICS_MODE=excel 时, 现有 11 个 Excel 问数问题不退化
ASK_METRICS_MODE=dora 时, Dora 可承接通用问数并返回 answer
ASK_METRICS_MODE=auto 时, Dora 失败可回退 Excel
TTS 真流式首个音频 chunk 早于完整文件合成
TTS 真流式失败时可回退分段 TTS
运维看板可查看依赖状态、最近会话、错误和耗时
API Key 不出现在前端和运维页面
```

### Status

Done for V0.8 scope。第一阶段已完成客户私有配置目录 + `ASK_METRICS_MODE=dora|excel|auto`: 后端可加载 `config/customers/zt-securities/` 覆盖层, `excel` 模式 11 个问数 smoke 通过, `dora` 模式不让 Excel 抢答, `auto` 模式可在 Dora / Mock Dora 失败或兜底时回退 Excel。第二阶段已完成 TTS 字节级真流式: 新增 `POST /api/tts/stream`、后端 `TtsProvider.stream_synthesize`、Mock / 阿里云流式 chunk、前端 PCM Web Audio 播放和分段 TTS fallback。第三阶段已完成运维监控 / 日志看板: 新增只读脱敏 Ops API、前端“演示 / 运维”视图切换、依赖状态、最近会话、错误列表、耗时指标和 Markdown 日志导出。

## V0.9 交付优化版

### Goal

把 V0.8 功能增强后的系统整理为现场可启动、可预检、可复演、可排障的交付形态。

### Scope

- 预检脚本:
  - Docker Desktop。
  - 端口占用。
  - API / Web。
  - RAGFlow / Dora / FVS / ASR / TTS。
- 一键启停:
  - `scripts/start-poc.ps1`。
  - `scripts/stop-poc.ps1`。
  - `scripts/check-poc.ps1`。
  - `scripts/export-logs.ps1`。
  - `scripts/smoke-demo.ps1`。
- 日志导出:
  - 最近会话。
  - 验收问题结果。
  - 依赖状态。
- 演示模式:
  - `DEMO_STABLE_MODE=true`。
  - 外部服务失败时提示 fallback。
- 异常体验优化:
  - Excel 缺文件。
  - Dora 超时。
  - TTS 流式失败。
  - FVS iframe 加载失败。
  - 麦克风权限失败。

### Acceptance

```text
新机器按文档和脚本可启动 POC
预检脚本能定位常见环境问题
演示问题集可一键 smoke
失败时不出现系统堆栈或裸错误
```

### Status

Done for V0.9 scope。已新增 PowerShell 预检、启停、日志导出和演示 smoke 脚本; 新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 演示稳态开关和 `GET /api/demo/config`; Dora 失败、Excel 问数缺文件、TTS 分段失败、FVS iframe 加载失败和麦克风权限失败均有安全兜底提示。V0.9 未进入正式验收报告、部署方案或用户手册输出, 下一阶段进入 V1.0。

## V1.0 POC 验收交付版

### Goal

输出客户可签收、可移交、可复演的完整 POC 交付包。

### Scope

- 验收报告。
- 部署方案。
- 用户手册。
- 运维手册。
- 配置手册。
- 演示脚本。
- 测试报告。
- 风险和后续路线。
- 客户移交清单。

### Acceptance

```text
验收报告包含现场复演结果、截图、耗时和客户确认项
部署方案覆盖 Windows + Docker Desktop + RAGFlow + FVS + Dora + ASR/TTS
用户手册覆盖唤醒、连续追问、问答、问数、大屏切换和兜底
运维手册覆盖启停、预检、日志、故障排查和配置更换
客户能按文档复现 POC 能力
```

### Status

Done for V1.0 delivery package scope。已输出 `docs/delivery/v1.0/` 验收交付包, 包含验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。现场截图、真实客户网络 / 外部依赖、麦克风 / 播放权限和客户签字仍需在客户现场验收复演时补齐。
