# 配置说明

## 配置目标

核心代码保持通用, 客户差异通过配置和文档管理。后续建议增加:

```text
config/
├─ screen-actions.yaml
├─ wake-words.yaml
├─ demo-cases.yaml
├─ dora-output-schema.json
└─ customers/
   └─ zt-securities/
      ├─ screen-actions.yaml
      ├─ wake-words.yaml
      ├─ demo-cases.yaml
      └─ customer.env.example
```

当前已生成第一版配置:

```text
.env.example
config/
├─ README.md
├─ screen-actions.yaml
├─ wake-words.yaml
├─ demo-cases.yaml
└─ dora-output-schema.json
```

## .env.example

```env
# Runtime
APP_ENV=local
LOG_LEVEL=INFO

# Frontend
VITE_API_BASE_URL=http://localhost:18080
VITE_FVS_URL=https://your-fvs-url
VITE_FVS_INTEGRATION_MODE=iframe

# Dora
DORA_BASE_URL=https://your-dora-host
DORA_API_KEY=replace_me
DORA_AGENT_ID=replace_me
DORA_CHAT_MODE=sse
DORA_TIMEOUT_SECONDS=60

# RAGFlow
RAGFLOW_BASE_URL=http://host.docker.internal:9380
RAGFLOW_MCP_URL=http://host.docker.internal:9382/mcp
RAGFLOW_API_KEY=replace_me

# ASR
ASR_PROVIDER=aliyun
ASR_API_KEY=replace_me
ASR_MODEL=paraformer-realtime
ASR_REGION=cn-beijing

# TTS
TTS_PROVIDER=aliyun
TTS_API_KEY=replace_me
TTS_MODEL=qwen3-tts-flash-realtime
TTS_VOICE=Cherry
TTS_AUDIO_FORMAT=mp3

# Optional LLM in Gateway
LLM_PROVIDER=qwen
LLM_API_KEY=replace_me
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Screen Control
ACTION_WHITELIST_PATH=/app/config/screen-actions.yaml
ENABLE_MOCK_FVS=true
ENABLE_MOCK_DORA=true
ENABLE_MOCK_ASR=true
ENABLE_MOCK_TTS=true

# Session
SQLITE_PATH=/app/data/sessions.db
SAVE_AUDIO=false
```

## Mock 开关

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ENABLE_MOCK_DORA` | true | 使用 Mock Dora 返回 |
| `ENABLE_MOCK_ASR` | true | 使用 Mock ASR |
| `ENABLE_MOCK_TTS` | true | 使用 Mock TTS |
| `ENABLE_MOCK_FVS` | true | 只打印或模拟大屏动作 |

## 唤醒词配置

```yaml
wake_words:
  - 小天小天
  - 中天小天
  - 你好小天
```

## 大屏动作配置

详见 [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md) 的 `ScreenAction`。

## 客户配置原则

- 客户名称、演示问题、领导资料、FVS 地址、动作白名单都应配置化。
- 供应商 API Key 只能放 `.env`, 不进入 Git。
- 客户现场敏感信息不要写入公共模板。
- 客户交付前需要生成脱敏版文档和配置样例。
