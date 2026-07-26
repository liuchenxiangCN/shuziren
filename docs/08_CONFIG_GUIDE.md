# 配置说明

> Lifecycle: `AS_BUILT_POC`。本文描述当前单实例 POC 的环境变量、YAML 和客户覆盖层，不是目标产品的多屏配置、发布或 Secret 模型。

## 配置目标

核心代码保持通用, 客户差异通过配置和文档管理。项目默认定位是通用可配置数字人; 中天证券党建大屏通过客户配置覆盖层实现。V0.8 第一阶段已新增客户私有配置覆盖层:

```text
config/
├─ screen-actions.yaml
├─ wake-words.yaml
├─ demo-cases.yaml
├─ dora-output-schema.json
└─ customers/
   └─ zt-securities/
      ├─ runtime.yaml
      ├─ screen-actions.yaml
      ├─ ask-metrics.yaml
      ├─ fvs.yaml
      ├─ dora.yaml
      ├─ ragflow.yaml
      ├─ voice.yaml
      ├─ wake-words.yaml
      ├─ demo-cases.yaml
      └─ customer.env.example
```

通用配置仍保留为默认模板:

```text
.env.example
config/
├─ README.md
├─ screen-actions.yaml
├─ wake-words.yaml
├─ demo-cases.yaml
├─ ask-metrics.yaml
├─ dora-output-schema.json
└─ customers/
   └─ zt-securities/
      ├─ README.md
      ├─ customer.env.example
      ├─ runtime.yaml
      ├─ screen-actions.yaml
      ├─ ask-metrics.yaml
      ├─ dora.yaml
      ├─ ragflow.yaml
      ├─ voice.yaml
      ├─ fvs.yaml
      ├─ wake-words.yaml
      └─ demo-cases.yaml
```

## .env.example

```env
# Runtime
APP_ENV=local
APP_NAME=configurable-digital-human-api
LOG_LEVEL=INFO
PROJECT_ID=configurable-digital-human
PROJECT_NAME=通用可配置数字人 POC
PRODUCT_NAME=可配置大屏对话数字人
CUSTOMER_ID=default
CUSTOMER_NAME=默认客户
SCENARIO_NAME=通用大屏交互
ASSISTANT_NAME=小智
CUSTOMER_CONFIG_DIR=
DEMO_STABLE_MODE=false

# Frontend
VITE_API_BASE_URL=http://localhost:18080
VITE_FVS_URL=
VITE_FVS_INTEGRATION_MODE=mock
VITE_FVS_TARGET_ORIGIN=
VITE_DEMO_STABLE_MODE=false

# Dora
DORA_BASE_URL=https://your-dora-host
DORA_API_KEY=replace_me
DORA_AGENT_ID=
DORA_AGENT_NAME=your-published-agent-name
DORA_CHANNEL_TYPE=feishu
DORA_CHAT_MODE=sse
DORA_TIMEOUT_SECONDS=60

# RAGFlow
RAGFLOW_BASE_URL=http://host.docker.internal:9380
RAGFLOW_MCP_URL=http://host.docker.internal:9382/mcp
RAGFLOW_API_KEY=replace_me

# ASR
ASR_PROVIDER=aliyun
ASR_API_KEY=replace_me
ASR_MODEL=fun-asr-realtime
ASR_REGION=cn-beijing
ASR_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
ASR_AUDIO_FORMAT=wav
ASR_SAMPLE_RATE=16000
ASR_TIMEOUT_SECONDS=30

# TTS
TTS_PROVIDER=aliyun
TTS_API_KEY=replace_me
TTS_MODEL=cosyvoice-v3-flash
TTS_VOICE=longanyang
TTS_AUDIO_FORMAT=mp3
TTS_STREAMING_ENABLED=true
TTS_STREAMING_FALLBACK=segment
TTS_STREAMING_AUDIO_FORMAT=pcm
TTS_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
TTS_SAMPLE_RATE=22050
TTS_TIMEOUT_SECONDS=30
TTS_CACHE_DIR=/app/data/tts-cache

# Optional LLM in Gateway
LLM_PROVIDER=qwen
LLM_API_KEY=replace_me
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Screen Control
ASK_METRICS_MODE=excel
# Optional explicit path overrides. Leave commented to allow CUSTOMER_CONFIG_DIR overlays.
# ACTION_WHITELIST_PATH=/app/config/screen-actions.yaml
# DEMO_CASES_PATH=/app/config/demo-cases.yaml
# WAKE_WORDS_PATH=/app/config/wake-words.yaml
# ASK_METRICS_DATA_DIR=/app/docs/demo_data/ask_metrics
# ASK_METRICS_CONFIG_PATH=/app/config/ask-metrics.yaml
ENABLE_MOCK_FVS=true
ENABLE_MOCK_DORA=true
ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true

# Session
SQLITE_PATH=/app/data/sessions.db
SAVE_AUDIO=false
```

启用中天证券客户实例时, 在 `.env` 中覆盖:

```env
CUSTOMER_ID=zt-securities
CUSTOMER_NAME=中天证券
CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities
DORA_AGENT_NAME=中天证券党建大屏语音助手
```

## V0.9 演示稳态模式

```env
DEMO_STABLE_MODE=false
VITE_DEMO_STABLE_MODE=false
```

- `DEMO_STABLE_MODE=true`: 后端在 Dora 请求失败时优先尝试本地 Excel 问数和 Mock Dora 演示兜底。
- `VITE_DEMO_STABLE_MODE=true`: 前端显示“演示稳态”状态标识。
- `scripts/start-poc.ps1 -DemoStable` 会在本次启动进程中同时设置上述两个变量。
- 该模式只用于固定演示保底; 正式外部依赖验收仍应通过 `scripts/check-poc.ps1 -RequireServices` 和运维看板确认真实依赖状态。

## V0.9 脚本入口

脚本默认读取仓库根目录 `.env`:

```powershell
scripts\check-poc.ps1
scripts\start-poc.ps1 -Build
scripts\stop-poc.ps1
scripts\smoke-demo.ps1
scripts\export-logs.ps1 -Zip
```

- `check-poc.ps1` 覆盖 Docker、端口、配置、API、Web、Ops 依赖和 RAGFlow 检查。
- `start-poc.ps1 -WithRagflow` 会额外尝试启动 `D:\Project\ragflow\docker` 下的本机 RAGFlow。
- `export-logs.ps1` 默认只导出脱敏 Ops 摘要和 Compose 状态; Docker 原生日志需显式 `-IncludeDockerLogs`。

## Mock 开关

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ENABLE_MOCK_DORA` | true | 使用 Mock Dora 返回 |
| `ENABLE_MOCK_ASR` | true | 使用 Mock ASR |
| `ENABLE_MOCK_TTS` | true | 使用 Mock TTS |
| `ENABLE_MOCK_FVS` | true | 只打印或模拟大屏动作 |

> V0.8 之后, `ACTION_WHITELIST_PATH`、`DEMO_CASES_PATH`、`WAKE_WORDS_PATH`、`ASK_METRICS_DATA_DIR` 和 `ASK_METRICS_CONFIG_PATH` 建议只在确实需要强制指定路径时启用。保持注释时, 后端会按 `CUSTOMER_CONFIG_DIR` 自动加载客户目录覆盖层。

## 本地问数数据配置

V0.7 第一版问数由 Gateway 本地 Excel Adapter 承接, 默认读取:

```env
ASK_METRICS_DATA_DIR=/app/docs/demo_data/ask_metrics
ASK_METRICS_CONFIG_PATH=/app/config/ask-metrics.yaml
ASK_METRICS_MODE=excel
```

Docker Compose 会把仓库中的 `./docs/demo_data` 只读挂载到 `/app/docs/demo_data`。当前目录下的三份脱敏 Excel 为:

- `zt_party_study_metrics_2026.xlsx`
- `zt_party_org_life_metrics_2026.xlsx`
- `zt_party_development_metrics_2026.xlsx`

该 Adapter 不需要额外 API Key, 不调用外部系统。

`ASK_METRICS_CONFIG_PATH` 指向工作簿和 sheet 映射配置, 便于后续替换演示数据文件名。

V0.8 已新增 `ASK_METRICS_MODE`:

| 值 | 说明 |
| --- | --- |
| `excel` | 先走 Gateway 本地 Excel Adapter, 命中后直接返回; 未命中继续 Dora / Mock Dora |
| `dora` | Excel Adapter 不抢答, 由 Dora / Mock Dora 承接通用问数 |
| `auto` | 优先 Dora / Mock Dora, Dora 请求失败或返回 `fallback` 时回退 Excel |

## 客户私有配置目录

V0.8 第一阶段已新增客户私有配置覆盖层:

```env
CUSTOMER_ID=<customer-id>
CUSTOMER_CONFIG_DIR=/app/config/customers/<customer-id>
```

当前中天证券客户实例目录:

```text
config/customers/zt-securities/
├─ README.md
├─ customer.env.example
├─ runtime.yaml
├─ screen-actions.yaml
├─ ask-metrics.yaml
├─ fvs.yaml
├─ dora.yaml
├─ ragflow.yaml
├─ voice.yaml
└─ demo-cases.yaml
```

加载规则:

- 根目录配置作为默认模板。
- 客户目录配置作为覆盖层。
- `.env` 和容器环境变量作为显式运行时覆盖。
- 旧 `.env` 中等于根目录默认路径的配置项不再阻止客户目录覆盖; 真正自定义路径仍优先。
- `.env` 只放密钥、本机端口和部署参数。
- YAML 放非敏感客户配置。
- 前端只使用后端透出的安全配置。

V0.8 第一阶段后端已接入:

| 客户配置 | 作用 |
| --- | --- |
| `runtime.yaml` | 客户 ID、问数模式、问数数据目录 |
| `screen-actions.yaml` | 后端动作白名单 |
| `ask-metrics.yaml` | Excel 工作簿 / sheet 映射和默认问数模式 |
| `demo-cases.yaml` | Mock Dora / 演示问题 |
| `wake-words.yaml` | 唤醒词和连续追问参数 |
| `dora.yaml` | Dora Agent 名称、渠道、超时等非敏感参数 |
| `ragflow.yaml` | RAGFlow / MCP 地址等非敏感参数 |
| `voice.yaml` | ASR / TTS 模型、格式、超时等非敏感参数 |

`fvs.yaml` 已作为客户 FVS 地址和 page 参数样例落地。V0.8 第三阶段起, 后端 Ops API 会读取其中的非敏感 `integration_mode` / `url` / `target_origin` 用于依赖状态展示, 并兼容 `VITE_FVS_URL`、`VITE_FVS_INTEGRATION_MODE`、`VITE_FVS_TARGET_ORIGIN` 环境变量别名。前端实际 iframe 仍通过这些 `VITE_FVS_*` 构建参数或 `?fvs_url=` URL 参数使用安全配置。

## FVS iframe 配置

V0.6 已验收的推荐方式是让数字人前端作为主页面, iframe 嵌入 FVS 看板。此时麦克风权限留在数字人主页面, 交互浮层也由本项目控制:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=your-dashboard.fvs&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

变量说明:

| 变量 | 说明 |
| --- | --- |
| `VITE_FVS_INTEGRATION_MODE` | `mock` 为本地 Mock; `iframe` 表示数字人主页面嵌入 FVS; `parent` / `web-frame` / `fvs-web-frame` 为备用的 FVS 网页框嵌数字人方案 |
| `VITE_FVS_URL` | `iframe` 模式使用, 表示被数字人主页面嵌入的 FVS 看板地址 |
| `VITE_FVS_TARGET_ORIGIN` | 数字人前端向 FVS iframe 发送 `postMessage` 时使用的目标 origin。为空时前端从 `VITE_FVS_URL` 推断 |

如果 FVS 响应 `X-Frame-Options: SAMEORIGIN`, 推荐通过前端 Nginx 同源代理访问 FVS:

```text
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=...&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

当前 Web 容器会将 `/webroot/` 转发到 Docker Desktop 主机的 `http://host.docker.internal:8075/webroot/`。

若白名单动作配置了 `params.pageNumber`, V0.6 前端会优先改写 FVS iframe URL 中的 `page_number`, 例如测试看板中 `总览=1`、`成品库存=2`、`生产管理=3`、`设备分析=4`。这种分页切换不要求 FVS 页面先预埋 `message` 监听。

为了减少每次修改 `.env` 后重建, 可用 URL 参数临时指定 FVS 地址:

```text
http://localhost:18000/?fvs_url=https%3A%2F%2Fyour-fvs-url
```

如果还要指定目标 origin:

```text
http://localhost:18000/?fvs_url=https%3A%2F%2Fyour-fvs-url&fvs_origin=https%3A%2F%2Fyour-fvs-origin
```

FVS 看板如果需要响应分页以外的动作消息, 应在 FVS 页面中监听 `message`, 并只按 `action_id` 固定映射。详见 [FVS 集成说明](integrations/FVS_INTEGRATION.md)。

备用的 FVS 网页框嵌数字人方案仍可使用:

```js
duchamp.onlyCommunicateWithOrigins(["http://localhost:18000"]);
```

但该方案下麦克风可能受 iframe 权限策略影响, 当前不再作为首选。

## Dora 配置

| 变量 | 说明 |
| --- | --- |
| `DORA_BASE_URL` | Dora / FineBI 环境地址, 例如 `https://<host>/webroot/decision`; 客户环境必须通过 `.env` 配置, 不写死到代码 |
| `DORA_API_KEY` | Dora OpenClaw Key, 只能放本地 `.env`, 不进入 Git |
| `DORA_AGENT_ID` | 已发布 Agent ID; 如果为空, V0.2 将按 `DORA_AGENT_NAME` 自动发现 |
| `DORA_AGENT_NAME` | 已发布 Agent 名称, 用于在不知道 ID 时从 `/external/api/openclaw/agents` 精确匹配; 本地 V0.2 真实控屏验证使用 `中天证券党建大屏语音助手` |
| `DORA_CHANNEL_TYPE` | Dora OpenClaw 接口要求的渠道参数, 当前先使用 `feishu` |
| `DORA_CHAT_MODE` | 当前规划使用 `sse` |
| `DORA_TIMEOUT_SECONDS` | Dora 请求超时时间 |

启用真实 Dora:

```env
ENABLE_MOCK_DORA=false
```

关闭 Mock 后, 后端仍会把 Dora 原始输出归一为 `/api/chat` 的既有响应结构, 前端不直接接触 Dora Key 或 Dora API。

## ASR / TTS 配置

| 变量 | 说明 |
| --- | --- |
| `ASR_PROVIDER` | 真实 ASR 供应商标识, 当前默认预留 `aliyun` |
| `ASR_API_KEY` | ASR Key, 只能放本地 `.env`, 不进入前端或 Git |
| `ASR_MODEL` | ASR 模型名, 当前使用 `fun-asr-realtime` |
| `ASR_REGION` | ASR 区域配置, 当前使用华北 2（北京） |
| `ASR_WS_URL` | 阿里云百炼实时 ASR WebSocket URL |
| `ASR_AUDIO_FORMAT` | 前端上传给真实 ASR 的音频格式, 当前使用 `wav` |
| `ASR_SAMPLE_RATE` | ASR 采样率, 当前前端录音输出 16k 单声道 WAV |
| `ASR_TIMEOUT_SECONDS` | ASR 请求超时时间 |
| `TTS_PROVIDER` | 真实 TTS 供应商标识, 当前默认预留 `aliyun` |
| `TTS_API_KEY` | TTS Key, 只能放本地 `.env`, 不进入前端或 Git |
| `TTS_MODEL` | TTS 模型名, 当前使用 `cosyvoice-v3-flash` |
| `TTS_VOICE` | 默认音色, 当前使用 CosyVoice 系统音色 `longanyang` |
| `TTS_AUDIO_FORMAT` | 真实 TTS 输出格式, 当前使用 `mp3`; V0.3 Mock TTS 固定生成 `wav` |
| `TTS_STREAMING_ENABLED` | 是否启用 V0.8 字节级真流式 TTS, 当前默认 `true` |
| `TTS_STREAMING_FALLBACK` | 真流式失败时的回退策略, 当前使用 `segment` 回退分段 TTS |
| `TTS_STREAMING_AUDIO_FORMAT` | 真流式播放格式, 当前使用 `pcm`, 前端用 Web Audio API 排队播放 chunk |
| `TTS_WS_URL` | 阿里云百炼实时 TTS WebSocket URL |
| `TTS_SAMPLE_RATE` | TTS 输出采样率, 当前使用 `22050` |
| `TTS_TIMEOUT_SECONDS` | TTS 请求超时时间 |
| `TTS_CACHE_DIR` | TTS 音频缓存目录, Docker 默认 `/app/data/tts-cache` |

V0.3 已支持阿里云百炼真实 ASR / TTS 最小 Provider。关闭 `ENABLE_MOCK_ASR` 或 `ENABLE_MOCK_TTS` 时, 后端会读取 `.env` 中的 Key 和 WebSocket 配置调用百炼; 前端不直接接触 Key。

V0.5 新增 `POST /api/chat/stream` 后, 前端优先使用流式接口。TTS Provider 不需要新增供应商配置; 后端复用现有 `TTS_*` 配置, 将 Dora 最终 `speak_text` 拆成短段并发合成。

V0.8 第二阶段已新增 TTS 字节级真流式配置:

```env
TTS_STREAMING_ENABLED=true
TTS_STREAMING_FALLBACK=segment
TTS_STREAMING_AUDIO_FORMAT=pcm
```

`POST /api/tts/stream` 会以 SSE 返回 `metadata`、`audio_chunk` 和 `end`。前端默认请求 PCM chunk 并使用 Web Audio API 播放; `TTS_STREAMING_FALLBACK=segment` 表示真流式失败时回退当前分段 TTS 文件播放方案。

## RAGFlow 配置

V0.5 本地 RAGFlow 已部署在仓库外:

```text
D:\Project\ragflow
```

当前本地端口:

| 配置 | 地址 |
| --- | --- |
| Web | `http://127.0.0.1:18089` |
| API | `http://127.0.0.1:19380` |
| Health | `http://127.0.0.1:18089/api/v1/system/healthz` |
| MCP Streamable HTTP | `http://127.0.0.1:19382/mcp` |
| MCP SSE | `http://127.0.0.1:19382/sse` |
| Public MCP | `http://liuchenxiang.uk:19382/mcp` |

启动命令:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d
```

停止命令:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch down
```

注意:

- `RAGFLOW_MCP_HOST_API_KEY` 只写在 `D:\Project\ragflow\docker\.env`, 不进入本项目 Git。
- RAGFlow 默认 Embedding 已设置为 `text-embedding-v3@Tongyi-Qianwen`; 使用的供应商 Key 只来自本地 `.env`, 不进入 Git。
- `zt_party_building_demo` dataset 已上传 8 份测试 Markdown 并解析完成。
- 当前未设置默认 Chat 模型; V0.5 Dora MCP 路径固定使用 `ragflow_retrieval(keyword=false)`, 由 Dora 生成最终回答。只有启用 `keyword=true`、TOC enhance、KG retrieval 或让 RAGFlow 自己生成回答时, 才需要配置默认 Chat 模型。
- 当前本地 RAGFlow MCP server 已做 POC 返回量瘦身: `page_size<=3`, `top_k<=16`, `similarity_threshold>=0.35`, 单 chunk content 最长 1200 字符, 并只返回 Dora 回答所需的精简字段。
- 如需调整返回量, 在 `D:\Project\ragflow\docker\.env` 中增加或修改 `RAGFLOW_MCP_MAX_PAGE_SIZE`、`RAGFLOW_MCP_MAX_TOP_K`、`RAGFLOW_MCP_MIN_SIMILARITY`、`RAGFLOW_MCP_MAX_CONTENT_CHARS`, 然后重启 `ragflow-cpu`。
- 本项目 `.env.example` 中的 `RAGFLOW_BASE_URL` / `RAGFLOW_MCP_URL` 是 Gateway 侧预留配置; 当前 V0.5 主要由 Dora 直接配置 MCP。
- Dora 远端不能访问本机 `127.0.0.1`, 真实 Dora MCP 联调时需要换成 Dora 可访问地址。
- 当前临时公网 `http://liuchenxiang.uk:19382/mcp` 已完成 Dora Agent 知识库问答验证; 正式演示前需确认网络和访问控制方案。

## 唤醒词配置

```yaml
version: 0.1.0
mode: semantic
wake_words:
  - 小天小天
  - 中天小天
  - 你好小天
  - 小天
settings:
  min_audio_ms: 1000
  max_audio_ms: 6500
  silence_ms: 1000
  cooldown_ms: 800
  command_timeout_ms: 8000
  followup_enabled: true
  followup_window_ms: 12000
  max_followup_turns: 3
  vad_threshold: 0.014
  barge_in_enabled: true
  barge_in_wake_words:
    - 小天小天
    - 你好小天
  barge_in_vad_threshold: 0.018
  barge_in_min_audio_ms: 900
  barge_in_silence_ms: 700
  barge_in_max_audio_ms: 3500
  barge_in_ignore_after_tts_start_ms: 700
  require_exact_phrase: false
```

V0.4 前端通过 `GET /api/wake/config` 读取该配置。`min_audio_ms` / `max_audio_ms` 控制唤醒检查短片段长度, `silence_ms` 控制本地 VAD 判断一句话结束, `command_timeout_ms` 控制唤醒后等待正式指令的最长时间, `cooldown_ms` 控制未命中或退出连续对话后的短暂冷却。V0.4.1 增加连续对话窗口: `followup_enabled` 控制是否启用, `followup_window_ms` 控制播报后等待追问多久, `max_followup_turns` 控制单次唤醒后最多连续追问几轮。`barge_in_*` 控制播报中的长唤醒词确认打断: 只在 `speaking` 状态下识别 `barge_in_wake_words`, 命中后停止当前 TTS 并进入下一轮; 未命中、空识别或 ASR 失败时继续播报。

## 大屏动作配置

详见 [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md) 的 `ScreenAction`。

## 客户配置原则

- 客户名称、演示问题、领导资料、FVS 地址、动作白名单都应配置化。
- 供应商 API Key 只能放 `.env`, 不进入 Git。
- 客户现场敏感信息不要写入公共模板。
- 客户交付前需要生成脱敏版文档和配置样例。
