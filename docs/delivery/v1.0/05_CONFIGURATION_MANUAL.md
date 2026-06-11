# V1.0 配置手册

## 配置层级

配置优先级从低到高:

1. 根目录默认 YAML, 如 `config/screen-actions.yaml`。
2. 客户目录覆盖层, 如 `config/customers/zt-securities/screen-actions.yaml`。
3. `.env` 和容器环境变量。
4. 前端 URL 临时参数, 如 `?fvs_url=...`。

原则:

- `.env` 放密钥、本机端口和部署参数。
- YAML 放非敏感客户配置。
- 前端只接收安全配置。
- 客户差异不写死到核心代码。

## `.env` 核心配置

### Runtime

```env
APP_ENV=local
LOG_LEVEL=INFO
CUSTOMER_ID=zt-securities
CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities
DEMO_STABLE_MODE=false
```

### Frontend

```env
VITE_API_BASE_URL=http://localhost:18080
VITE_FVS_URL=
VITE_FVS_INTEGRATION_MODE=mock
VITE_FVS_TARGET_ORIGIN=
VITE_DEMO_STABLE_MODE=false
```

### Mock 开关

```env
ENABLE_MOCK_DORA=true
ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true
ENABLE_MOCK_FVS=true
```

说明:

- Mock 开关必须保留, 用于现场兜底。
- 真实验收时应记录各开关状态。
- `DEMO_STABLE_MODE=true` 不等于真实外部依赖验收通过。

## Dora 配置

```env
DORA_BASE_URL=https://your-dora-host
DORA_API_KEY=replace_me
DORA_AGENT_ID=
DORA_AGENT_NAME=中天证券党建大屏语音助手
DORA_CHANNEL_TYPE=feishu
DORA_CHAT_MODE=sse
DORA_TIMEOUT_SECONDS=60
```

规则:

- `DORA_API_KEY` 只能在 `.env` 或部署环境变量中出现。
- 前端不直接调用 Dora。
- `DORA_AGENT_ID` 为空时, 后端按 `DORA_AGENT_NAME` 查找已发布 Agent。
- Dora 输出 `screen_control` 时, Gateway 仍会校验 `action_id`。

## RAGFlow 配置

```env
RAGFLOW_BASE_URL=http://host.docker.internal:9380
RAGFLOW_MCP_URL=http://host.docker.internal:9382/mcp
RAGFLOW_API_KEY=replace_me
```

当前本地 RAGFlow:

| 项目 | 地址 |
| --- | --- |
| Web | `http://127.0.0.1:18089` |
| API | `http://127.0.0.1:19380` |
| MCP | `http://127.0.0.1:19382/mcp` |

注意:

- Dora 远端不能访问本机 `127.0.0.1`。
- Dora MCP 地址必须替换为 Dora 可访问地址。
- 当前 POC 固定使用 `ragflow_retrieval(keyword=false)`。
- RAGFlow 默认 Chat 模型不是当前 POC 必需项。

## ASR / TTS 配置

```env
ASR_PROVIDER=aliyun
ASR_API_KEY=replace_me
ASR_MODEL=fun-asr-realtime
ASR_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
ASR_AUDIO_FORMAT=wav
ASR_SAMPLE_RATE=16000

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
```

规则:

- ASR / TTS Key 只在后端使用。
- 前端录音会编码为 16k 单声道 WAV 后提交给后端。
- TTS 真流式默认使用 PCM chunk + Web Audio。
- 真流式失败时回退分段 TTS。

## 问数模式

```env
ASK_METRICS_MODE=excel
```

| 值 | 行为 |
| --- | --- |
| `excel` | Gateway 本地 Excel Adapter 先回答固定指标 |
| `dora` | Excel Adapter 不抢答, 由 Dora / Mock Dora 承接 |
| `auto` | 优先 Dora / Mock Dora, 失败或兜底时回退 Excel |

当前 Excel 数据:

```text
docs/demo_data/ask_metrics/
```

客户目录映射:

```text
config/customers/zt-securities/ask-metrics.yaml
```

安全边界:

- 不执行模型生成 SQL。
- 不执行模型生成 Python。
- 不执行模型生成 JavaScript。
- 不执行模型生成 shell。

## FVS 配置

推荐 iframe host:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=your-dashboard.fvs&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

临时指定 FVS URL:

```text
http://localhost:18000/?fvs_url=<url-encoded-fvs-url>
```

动作白名单:

```text
config/customers/zt-securities/screen-actions.yaml
```

当前动作:

| action_id | 页面 | page_number |
| --- | --- | --- |
| `SWITCH_HOME` | 总览 | 1 |
| `SWITCH_TAB_ORG` | 成品库存 | 2 |
| `SWITCH_TAB_STUDY` | 生产管理 | 3 |
| `SWITCH_TAB_ACTIVITY` | 设备分析 | 4 |

规则:

- Dora 不应输出 FVS 函数名或 JavaScript。
- 前端只执行 `/api/screen/execute` 成功后的动作。
- FVS 侧如需监听 `postMessage`, 也必须按 `action_id` 固定映射。

## 客户目录

```text
config/customers/zt-securities/
├─ runtime.yaml
├─ screen-actions.yaml
├─ ask-metrics.yaml
├─ demo-cases.yaml
├─ wake-words.yaml
├─ dora.yaml
├─ ragflow.yaml
├─ voice.yaml
├─ fvs.yaml
└─ customer.env.example
```

文件说明:

| 文件 | 作用 |
| --- | --- |
| `runtime.yaml` | 客户 ID、问数模式和运行时非敏感配置 |
| `screen-actions.yaml` | 大屏动作白名单 |
| `ask-metrics.yaml` | Excel 工作簿和 sheet 映射 |
| `demo-cases.yaml` | 固定演示问题和 Mock Dora 规则 |
| `wake-words.yaml` | 唤醒词、VAD 和连续追问参数 |
| `dora.yaml` | Dora Agent 非敏感配置 |
| `ragflow.yaml` | RAGFlow / MCP 非敏感地址样例 |
| `voice.yaml` | ASR / TTS 模型、格式、超时 |
| `fvs.yaml` | FVS URL、模式和页面参数 |
| `customer.env.example` | 客户 `.env` 样例 |

## 演示稳态

```env
DEMO_STABLE_MODE=false
VITE_DEMO_STABLE_MODE=false
```

启用方式:

```powershell
scripts\start-poc.ps1 -Build -DemoStable
```

启用后:

- Dora 请求失败时优先回退 Excel 问数或 Mock Dora。
- 前端显示“演示稳态”。
- Ops 和预检仍应展示真实依赖状态。

## 配置变更后验证

```powershell
scripts\check-poc.ps1 -SkipExternal
scripts\start-poc.ps1
scripts\smoke-demo.ps1
scripts\export-logs.ps1 -Zip
```

## 禁止事项

- 不把 `.env` 提交到 Git。
- 不在前端源码写入 API Key。
- 不在客户 YAML 中写 API Key。
- 不让模型生成代码并执行。
- 不绕过 `action_id` 白名单直接控制 FVS。
