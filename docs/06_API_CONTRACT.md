# API 契约

本文档定义前端与后端 Gateway 的接口契约。实际实现前如需变更, 必须同步更新本文档。

## 通用约定

- Base URL: `http://localhost:18080`
- 前缀: `/api`
- 响应格式默认 JSON。
- 错误响应必须包含 `error.code`、`error.message`、`request_id`。
- 前端不得直接调用 Dora、ASR、TTS 供应商 API。

## GET /api/health

健康检查。

### Response

```json
{
  "status": "ok",
  "app": "configurable-digital-human-api",
  "version": "0.1.0"
}
```

## POST /api/chat

文本对话接口。V0.1 使用 Mock Dora, V0.2 接入真实 Dora, V0.3 可接收 ASR 输出文本进入同一链路。V0.7 增加 Gateway 本地 Excel 问数能力, 用于稳定回答 `docs/demo_data/ask_metrics/` 中的脱敏样例指标。阶段 2 已将问数链路抽象为 `AskMetricsProvider`, 当前本地 Excel 能力由配置驱动 `ExcelAskMetricsProvider` 承接。

### Runtime Mode

- V0.7 / 阶段 2 问数优先级: `ASK_METRICS_MODE=excel` 时, 后端会先用 `ExcelAskMetricsProvider` 按当前 `ask-metrics.yaml` metric 定义匹配问数意图; 命中后直接返回 `type=answer`, 不调用 Dora, 避免模型编造 Excel 查询结果。
- V0.8 已实现 `ASK_METRICS_MODE=excel|dora|auto`。`excel` 保持 V0.7 行为; `dora` 不让 Excel Adapter 抢答, 由 Dora / Mock Dora 承接; `auto` 优先 Dora / Mock Dora, Dora 请求失败或返回 `fallback` 时回退 Excel。
- 阶段 2 已移除运行代码中的客户实例问数 allowlist; 客户 Excel 文件、关键词、字段、模板和来源说明来自客户 profile, 根级默认配置保持通用空 metric 模板。
- Database Provider 仅预留 `not_implemented` 状态; 当前不会连接数据库、执行 SQL 或让 LLM 生成 SQL。
- `ENABLE_MOCK_DORA=true`: 继续使用 V0.1 Mock Dora, 不依赖外部 Dora。
- `ENABLE_MOCK_DORA=false`: 后端使用 `.env` 中的 `DORA_BASE_URL`、`DORA_API_KEY`、`DORA_AGENT_ID` / `DORA_AGENT_NAME`、`DORA_CHANNEL_TYPE` 调用 Dora OpenClaw SSE。
- `DEMO_STABLE_MODE=true`: Dora 请求失败时优先尝试本地 Excel 问数和 Mock Dora 演示兜底; 未命中时仍返回安全 `fallback`。该模式只用于演示稳态, 不能替代真实外部依赖验收。
- 前端接口契约不变, Dora 原始输出由后端归一为 `answer` / `screen_control` / `fallback`。
- Dora 请求失败、超时、Agent 未找到或输出无法解析时, 返回 `type=fallback`, 不暴露 API Key、底层堆栈或供应商错误细节。

### Request

```json
{
  "session_id": "demo-session-001",
  "text": "这个系统能做什么？",
  "context": {
    "screen_id": "dashboard_home",
    "mode": "text"
  }
}
```

`context.mode` 可为 `text` 或 `voice`; V0.3 中 ASR 识别文本会作为 `text` 调用本接口。

### Response: answer

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-001",
  "type": "answer",
  "title": "系统能力说明",
  "speak_text": "本系统支持语音唤醒、知识问答、指标问数、大屏控屏、语音播报和运维日志。",
  "display": {
    "mode": "text",
    "summary": "通用可配置数字人可通过客户配置适配不同大屏场景。",
    "bullets": [
      "客户名称、助手名称和场景名称可配置",
      "知识库和问数数据源可替换",
      "大屏动作必须通过 action_id 白名单执行"
    ]
  }
}
```

### Response: local ask_metrics answer

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-001",
  "type": "answer",
  "title": "党员学习完成率",
  "speak_text": "当前党员学习完成率为87.5%，党员总数128人，已完成学习112人。",
  "display": {
    "mode": "text",
    "summary": "当前党员学习完成率为 87.5%。",
    "bullets": [
      "党员总数：128 人",
      "已完成学习：112 人",
      "未完成：16 人",
      "数据来源：zt_party_study_metrics_2026.xlsx / Dashboard"
    ],
    "source": "zt_party_study_metrics_2026.xlsx / Dashboard"
  }
}
```

### Response: screen_control

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-002",
  "type": "screen_control",
  "speak_text": "已为您切换到成品库存页面。",
  "action": {
    "id": "SWITCH_TAB_ORG",
    "target": "finished_goods_inventory"
  }
}
```

### Response: Dora Fallback

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-003",
  "type": "fallback",
  "speak_text": "Dora 服务暂时不可用，请稍后再试。",
  "reason": "DORA_REQUEST_ERROR",
  "error": {
    "code": "DORA_REQUEST_ERROR",
    "message": "Dora 服务暂时不可用，请稍后再试。"
  }
}
```

## POST /api/chat/stream

流式对话接口。V0.5 当前用于真实 Dora + RAGFlow MCP 问答时降低感知等待: 后端透传 Dora SSE 中的最终回答增量, 并把 `speak_text` 拆成短段并发调用 TTS。若 Dora 某次只返回最终 answer, 后端仍会对最终 `speak_text` 做分段 TTS, 不再等待整段文本一次性合成。V0.7 问数命中本地 Excel Adapter 时, 该接口会直接返回 `metadata`、`dora_delta` 和 `answer`, 同样复用分段 TTS。V0.8 已同步 `ASK_METRICS_MODE`: `excel` 先走 Excel, `dora` 直接走 Dora / Mock Dora, `auto` 在 Dora / Mock Dora 失败或 `fallback` 时回退 Excel。

### Request

与 `POST /api/chat` 相同:

```json
{
  "session_id": "demo-session-001",
  "text": "入党流程是什么？",
  "context": {
    "screen_id": "party_building_home",
    "mode": "voice"
  }
}
```

### Response

响应为 `text/event-stream`。

```text
event: metadata
data: {"session_id":"demo-session-001","message_id":"msg-001"}

event: dora_delta
data: {"text":"入党流程共包括"}

event: tts_ready
data: {"index":0,"text":"入党流程共包括八个主要环节：","audio_url":"/api/tts/audio/tts-001.mp3","audio_id":"tts-001.mp3","duration_ms":2825,"provider":"aliyun","format":"mp3","mock":false}

event: answer
data: {"session_id":"demo-session-001","message_id":"msg-001","type":"answer","speak_text":"入党流程共包括八个主要环节：..."}

event: end
data: {"ok":true}
```

### Event Types

| Event | 用途 |
| --- | --- |
| metadata | 会话和消息元数据 |
| dora_delta | Dora 最终回答中的 `speak_text` 增量文本 |
| tts_ready | 某个分段 TTS 音频已就绪; `index` 表示播放顺序, 事件到达顺序不保证等于播放顺序 |
| tts_error | 某个分段 TTS 合成失败 |
| answer | 最终回答 |
| end | 结束 |

### Frontend Rule

前端按 `tts_ready.index` 顺序播放分段音频。V0.8 第二阶段起, 前端在收到最终 `answer` 后会优先调用 `POST /api/tts/stream` 做字节级真流式播报; 若真流式失败, 再回退到本接口返回的 `tts_ready` 分段音频。若浏览器自动播放被拦截, 仍保留文字回答和原生音频控件。该接口不改变 `POST /api/chat` 的兼容性; 流式接口失败时前端可回退到普通 `/api/chat` + `/api/tts`。

## POST /api/asr/transcribe

短音频 / Mock ASR 识别。V0.3 最小实现使用 JSON 提交, 不直接暴露供应商 API Key。

### Runtime Mode

- `ENABLE_MOCK_ASR=true`: 使用 Mock ASR, 返回 `mock_text` 或默认演示文本。
- `ENABLE_MOCK_ASR=false`: 后端调用阿里云百炼 Fun-ASR WebSocket, 使用 `.env` 中的 `ASR_API_KEY`、`ASR_MODEL`、`ASR_WS_URL`。
- 可选 `audio_base64` 用于前端录音上传; 真实 ASR 当前要求 16k 单声道 WAV / `audio_format=wav`。

### Request

```json
{
  "session_id": "demo-session-001",
  "mock_text": "请切换到成品库存页面",
  "audio_base64": "base64-webm-audio",
  "audio_format": "audio/webm"
}
```

### Response: success

```json
{
  "success": true,
  "session_id": "demo-session-001",
  "text": "请切换到成品库存页面",
  "provider": "mock",
  "mock": true,
  "duration_ms": 1
}
```

### Response: fallback

```json
{
  "success": false,
  "session_id": "demo-session-001",
  "text": "",
  "provider": "aliyun",
  "mock": false,
  "error": {
    "code": "ASR_PROVIDER_NOT_CONFIGURED",
    "message": "ASR 服务尚未配置真实供应商，请先使用 Mock ASR。"
  }
}
```

## WS /ws/asr

ASR WebSocket。后续流式 ASR 阶段实现; V0.3 最小闭环先使用 `POST /api/asr/transcribe`。

### Client -> Server

- 发送 PCM / WebM 音频片段。
- 发送结束事件。

### Server -> Client

```json
{
  "type": "asr_final",
  "text": "小天小天，请切换到成品库存页面"
}
```

## GET /api/wake/config

读取后台监听和语义唤醒配置。V0.4 前端使用该接口获取 `config/wake-words.yaml` 中的唤醒词、VAD 截段参数和冷却时间。前端仍只把本地 VAD 截取出的短音频片段提交给 `/api/asr/transcribe`, 不持续上传环境音。

### Response

```json
{
  "version": "0.1.0",
  "mode": "semantic",
  "wake_words": ["小天小天", "中天小天", "你好小天", "小天"],
  "settings": {
    "min_audio_ms": 1000,
    "max_audio_ms": 6500,
    "cooldown_ms": 800,
    "require_exact_phrase": false,
    "vad_threshold": 0.014,
    "silence_ms": 1000,
    "command_timeout_ms": 8000,
    "followup_enabled": true,
    "followup_window_ms": 12000,
    "max_followup_turns": 3,
    "barge_in_enabled": true,
    "barge_in_wake_words": ["小天小天", "你好小天"],
    "barge_in_vad_threshold": 0.018,
    "barge_in_min_audio_ms": 900,
    "barge_in_silence_ms": 700,
    "barge_in_max_audio_ms": 3500,
    "barge_in_ignore_after_tts_start_ms": 700
  }
}
```

`barge_in_*` 配置用于播报中长唤醒词确认打断。前端只在 `speaking` 状态下截取短片段做 ASR 判断, 命中 `barge_in_wake_words` 后才停止当前 TTS; 未命中、空识别或 ASR 失败不改变当前播报状态。

## GET /api/demo/config

V0.9 已实现。读取演示模式配置和固定演示问题集, 供前端演示按钮和交付 smoke 脚本使用。该接口只返回非敏感运行信息, 不返回 API Key、Token、供应商原始响应或客户敏感数据。

### Response

```json
{
  "stable_mode": true,
  "project_id": "configurable-digital-human",
  "project_name": "通用可配置数字人 POC",
  "product_name": "可配置大屏对话数字人",
  "customer_id": "default",
  "customer_name": "默认客户",
  "scenario_name": "通用大屏交互",
  "assistant_name": "小智",
  "ask_metrics_mode": "excel",
  "mock": {
    "dora": false,
    "asr": false,
    "tts": false,
    "fvs": true
  },
  "questions": [
    {
      "id": "Q-003",
      "text": "入党流程是什么？",
      "category": "knowledge",
      "expected": "返回入党流程摘要"
    }
  ],
  "notice": "演示稳态模式已开启，外部 Dora 失败时会优先使用本地演示兜底。"
}
```

## GET /api/config/effective

阶段 1 已实现。读取当前生效配置的脱敏只读快照, 供 `/ops/config` 展示。该接口只允许白名单构造 `ConfigSnapshot`, 不允许直接返回 `Settings.model_dump()` 或供应商原始响应。

### Response

```json
{
  "version": "1.0",
  "generated_at": "2026-06-15T20:00:00+08:00",
  "read_only": true,
  "provenance": {
    "sources": [
      "code_default",
      "root_config",
      "customer_config",
      "env",
      "frontend_build",
      "frontend_runtime",
      "derived",
      "unknown"
    ],
    "notes": [
      "本接口按白名单构造 ConfigSnapshot, 不返回 Settings.model_dump()。"
    ]
  },
  "project": {
    "project_id": {"value": "configurable-digital-human", "source": "code_default", "sensitive": false},
    "project_name": {"value": "通用可配置数字人 POC", "source": "code_default", "sensitive": false},
    "product_name": {"value": "可配置大屏对话数字人", "source": "code_default", "sensitive": false}
  },
  "customer": {
    "customer_id": {"value": "default", "source": "code_default", "sensitive": false},
    "customer_name": {"value": "默认客户", "source": "code_default", "sensitive": false},
    "scenario_name": {"value": "通用大屏交互", "source": "code_default", "sensitive": false},
    "assistant_name": {"value": "小智", "source": "code_default", "sensitive": false}
  },
  "dashboard": {
    "backend_effective": {
      "provider": {"value": "mock_fvs", "source": "derived", "sensitive": false},
      "integration_mode": {"value": "mock", "source": "code_default", "sensitive": false},
      "url": {"value": "", "source": "code_default", "sensitive": false},
      "action_count": {"value": 4, "source": "derived", "sensitive": false}
    },
    "frontend_runtime_contract": {
      "url": {
        "value": "VITE_FVS_URL 或 URL 参数 fvs_url",
        "source": "frontend_runtime",
        "sensitive": false
      }
    }
  },
  "capabilities": {
    "ask_metrics": {
      "mode": {"value": "excel", "source": "code_default", "sensitive": false},
      "current_provider": {"value": "excel", "source": "derived", "sensitive": false},
      "provider_interface": {
        "status": "implemented",
        "source": "code_default",
        "sensitive": false,
        "notes": "阶段 2 已抽象 AskMetricsProvider; Excel 问数由配置驱动的 ExcelAskMetricsProvider 承接。"
      },
      "implemented_providers": ["excel", "dora", "auto"],
      "planned_providers": ["database"],
      "excel_provider": {
        "status": "implemented",
        "source": "code_default",
        "sensitive": false,
        "notes": "Excel Provider 只读读取配置声明的 workbook/sheet/metric 模板。"
      },
      "database_provider": {
        "status": "not_implemented",
        "source": "code_default",
        "sensitive": false,
        "notes": "阶段 2 仅预留 Database Provider 状态; 不连接数据库, 不执行 SQL, 不让模型生成 SQL。"
      }
    },
    "knowledge": {
      "current_provider": {"value": "dora_ragflow_mcp", "source": "derived", "sensitive": false},
      "implemented_providers": ["dora_ragflow_mcp"],
      "planned_providers": ["local_ragflow_llm"],
      "knowledge_direct_adapter": {
        "status": "not_implemented",
        "source": "code_default",
        "sensitive": false
      }
    },
    "screen_control": {
      "resolver": {"value": "dora_or_mock", "source": "derived", "sensitive": false},
      "executor": {"value": "fvs_whitelist", "source": "root_config", "sensitive": false},
      "execute_returns_authorized_action": {"value": false, "source": "code_default", "sensitive": false},
      "writable_action_config": {"status": "not_implemented", "source": "code_default", "sensitive": false}
    }
  },
  "mock_switches": {
    "dora": {"value": true, "source": "code_default", "sensitive": false},
    "asr": {"value": true, "source": "code_default", "sensitive": false},
    "tts": {"value": true, "source": "code_default", "sensitive": false},
    "fvs": {"value": true, "source": "code_default", "sensitive": false}
  },
  "prompt_profiles": {
    "dora_direct_mode": {
      "profile": {"value": "mock_dora", "source": "derived", "sensitive": false},
      "writable": false
    },
    "knowledge_summarizer": {
      "profile": {
        "value": null,
        "source": "unknown",
        "sensitive": false,
        "notes": "阶段 3 前未实现本地 knowledge summarizer prompt profile。"
      },
      "writable": false
    }
  },
  "implementation_status": {
    "readonly_config_api": "implemented",
    "readonly_config_page": "implemented",
    "writable_config": "not_implemented",
    "ask_metrics_provider_interface": "implemented",
    "excel_ask_metrics_provider": "implemented",
    "database_provider": "not_implemented",
    "knowledge_direct_adapter": "not_implemented",
    "llm_summarizer": "not_implemented",
    "writable_prompt": "not_implemented"
  },
  "sensitive": {
    "dora_api_key": {
      "label": "Dora API Key",
      "configured": false,
      "source": "code_default",
      "sensitive": true,
      "masked": "not_configured"
    }
  }
}
```

规则:

- `source` 只能来自显式来源构造; 无法精确判断时必须使用 `derived` / `unknown` 并说明限制。
- sensitive 字段只返回 `configured` / `source` / `masked` / `sensitive`, 不返回 API Key、Token、密码、DSN、Bearer、`sk-*`、`ak-*` 或供应商原始响应。
- URL 字段如包含 `token`、`key`、`secret`、`password` 等查询参数, 返回前必须脱敏。
- 当前 `KnowledgeDirectAdapter`、Database Provider、可写 action 配置、LLM summarizer、可写 Prompt 均必须显示为 `not_implemented`。
- 本接口不得改变 `/api/chat`、`/api/chat/stream`、`/api/tts/stream`、`/api/screen/execute` 行为。

## GET /api/config/schema

阶段 1 已实现。返回只读配置快照 schema 和后续阶段才允许开放的接口列表。

### Response

```json
{
  "version": "1.0",
  "generated_at": "2026-06-15T20:00:00+08:00",
  "read_only": true,
  "sources": ["code_default", "root_config", "customer_config", "env", "frontend_runtime", "derived", "unknown"],
  "sections": {
    "project": {
      "description": "项目、客户、场景和助手展示字段。",
      "editable_stage": 5,
      "sensitive": false
    },
    "sensitive": {
      "description": "API Key、Token、密码、DSN 等敏感项只返回 configured/source/masked。",
      "editable_stage": null,
      "sensitive": true
    }
  },
  "disabled_endpoints": [
    "PUT /api/config/overrides",
    "POST /api/config/validate",
    "POST /api/config/test",
    "POST /api/config/reload",
    "GET /api/config/audit"
  ]
}
```

阶段 1 不实现 `PUT /api/config/overrides`、`POST /api/config/validate`、`POST /api/config/test`、`POST /api/config/reload` 或 `GET /api/config/audit`。

## POST /api/tts

TTS 合成。V0.3 最小实现使用 Mock TTS 生成完整 WAV 文件并返回音频 URL。

### Runtime Mode

- `ENABLE_MOCK_TTS=true`: 使用 Mock TTS, 生成 `wav` 文件并缓存到后端 `TTS_CACHE_DIR`。
- `ENABLE_MOCK_TTS=false`: 后端调用阿里云百炼 CosyVoice WebSocket, 使用 `.env` 中的 `TTS_API_KEY`、`TTS_MODEL`、`TTS_WS_URL`。
- 前端不得直接调用 TTS 供应商 API。

### Request

```json
{
  "text": "已为您切换到成品库存页面。",
  "voice": "longanyang",
  "format": "mp3"
}
```

### Response

```json
{
  "success": true,
  "audio_url": "/api/tts/audio/tts-001.wav",
  "audio_id": "tts-001.wav",
  "duration_ms": 2300,
  "provider": "mock",
  "voice": "longanyang",
  "format": "wav",
  "mock": true
}
```

V0.3 Mock TTS 不生成 mp3, 即使请求 `format=mp3`, 响应中的 `format` 仍以真实返回格式 `wav` 为准。真实 CosyVoice TTS 当前可返回 `mp3`、`wav`、`pcm` 或 `opus`, 以响应中的 `format` 为准。

### Response: fallback

```json
{
  "success": false,
  "audio_url": null,
  "provider": "aliyun",
  "voice": "longanyang",
  "format": "mp3",
  "mock": false,
  "error": {
    "code": "TTS_REQUEST_ERROR",
    "message": "TTS 服务暂时不可用，请稍后再试。"
  }
}
```

## POST /api/tts/stream

V0.8 第二阶段已实现。TTS 字节级真流式接口, 用于增强当前“分段 TTS 文件播放”方案。前端默认请求 `format=pcm`, 后端通过 SSE 逐块返回音频字节; 浏览器使用 Web Audio API 按 chunk 调度播放。当前分段 TTS fallback 仍以 `/api/chat/stream` 的 `tts_ready` 事件为准。

### Request

```json
{
  "text": "当前党员学习完成率为87.5%。",
  "voice": "longanyang",
  "format": "pcm"
}
```

### Response

响应为 `text/event-stream`:

```text
event: metadata
data: {"provider":"aliyun","voice":"longanyang","format":"pcm","mime_type":"audio/L16","sample_rate":22050,"mock":false,"fallback":"segment"}

event: audio_chunk
data: {"index":0,"audio_base64":"...","mime_type":"audio/L16","provider":"aliyun","format":"pcm","sample_rate":22050,"duration_ms":180,"mock":false}

event: end
data: {"ok":true,"chunks":12,"duration_ms":900,"fallback":"segment"}
```

### Event Types

| Event | 用途 |
| --- | --- |
| metadata | 流式 TTS 元数据 |
| audio_chunk | 一段可播放音频字节, `index` 表示顺序 |
| tts_error | 流式 TTS 合成失败 |
| end | 结束 |

### Fallback Rule

- `TTS_STREAMING_ENABLED=false`: 不使用真流式, 继续走分段 TTS 文件播放。
- `TTS_STREAMING_FALLBACK=segment`: 真流式失败时回退当前 `/api/chat/stream` + `tts_ready` 分段方案。
- `TTS_STREAMING_AUDIO_FORMAT=pcm`: 前端默认使用 PCM chunk + Web Audio 播放, 避免浏览器对 MP3 / Opus 流式容器支持不一致。
- 前端不得直接调用 TTS 供应商 API。

## GET /api/tts/audio/{audio_id}

读取 V0.3 Mock TTS 生成的音频文件。

### Response

- `200 audio/wav` / `audio/mpeg` / `audio/opus`: 返回音频文件。
- `404 JSON`: 音频不存在或 `audio_id` 非法。

## Ops APIs

V0.8 第三阶段已实现。运维监控和日志看板接口。所有 Ops 接口不得返回 API Key、完整密钥、供应商敏感原始响应或未脱敏客户数据; 会话文本、错误消息和导出摘要会做长度截断和常见密钥模式脱敏。

### GET /api/ops/health

聚合系统健康状态。

```json
{
  "status": "ok",
  "app": "configurable-digital-human-api",
  "version": "0.1.0",
  "customer_id": "default",
  "time": "2026-06-11T20:00:00+08:00"
}
```

### GET /api/ops/dependencies

检查外部依赖连通性。

```json
{
  "status": "warning",
  "dependencies": [
    {
      "name": "dora",
      "label": "Dora Agent",
      "status": "ok",
      "latency_ms": 320,
      "message": "HTTP 200",
      "checked_at": "2026-06-11T20:00:00+08:00",
      "details": {
        "mode": "real",
        "agent_configured": true,
        "channel_type": "feishu"
      }
    },
    {
      "name": "fvs",
      "label": "FVS",
      "status": "warning",
      "latency_ms": null,
      "message": "FVS 使用相对路径，需由前端同源代理验证",
      "checked_at": "2026-06-11T20:00:00+08:00",
      "details": {
        "mode": "iframe",
        "relative_url": true
      }
    }
  ]
}
```

当前依赖项包括 `session_log`、`screen_actions`、`dora`、`ragflow`、`asr`、`tts`、`fvs`。Mock 开启时会返回对应 Mock 状态; ASR / TTS 真实模式只做配置就绪检查, 不主动上传音频或触发合成。

### GET /api/ops/sessions

返回最近会话摘要。

```json
{
  "sessions": [
    {
      "session_id": "demo-session-001",
      "last_message_at": "2026-06-11T20:00:00+08:00",
      "turns": 6,
      "last_intent_type": "answer",
      "last_user_text": "当前党员学习完成率是多少?",
      "last_error": null,
      "last_latency_ms": 1200
    }
  ]
}
```

### GET /api/ops/session/{session_id}

返回单个会话的最近对话明细。

```json
{
  "session_id": "demo-session-001",
  "events": [
    {
      "id": 12,
      "session_id": "demo-session-001",
      "message_id": "msg-001",
      "created_at": "2026-06-11T20:00:00+08:00",
      "user_text": "当前党员学习完成率是多少?",
      "intent_type": "answer",
      "response_summary": "当前党员学习完成率为87.5%。",
      "screen_action": null,
      "error": null,
      "latency_total_ms": 1200
    }
  ]
}
```

### GET /api/ops/errors

返回最近错误和 `fallback` 摘要。

```json
{
  "errors": [
    {
      "id": 18,
      "session_id": "demo-session-001",
      "message_id": "msg-err",
      "created_at": "2026-06-11T20:05:00+08:00",
      "intent_type": "fallback",
      "code": "DORA_REQUEST_ERROR",
      "message": "Dora 服务暂时不可用，请稍后再试。",
      "user_text": "入党流程是什么?",
      "latency_total_ms": 60123
    }
  ]
}
```

### GET /api/ops/metrics

返回聚合耗时和错误指标。

```json
{
  "total_events": 120,
  "total_sessions": 12,
  "error_events": 3,
  "avg_latency_ms": 1800,
  "p50_latency_ms": 900,
  "p95_latency_ms": 6200,
  "max_latency_ms": 12000,
  "by_intent": [
    {
      "name": "answer",
      "count": 90,
      "avg_latency_ms": 1600,
      "max_latency_ms": 9000,
      "error_count": 0
    }
  ],
  "recent_latency": [
    {
      "created_at": "2026-06-11T20:00:00+08:00",
      "session_id": "demo-session-001",
      "intent_type": "answer",
      "latency_total_ms": 1200
    }
  ]
}
```

### GET /api/ops/export

导出 Markdown 格式的运维日志摘要, 内容包含依赖状态、聚合耗时、最近会话和最近错误。响应头包含 `Content-Disposition: attachment; filename="zt-ops-log-export.md"`。

## GET /api/screen/actions

获取大屏动作白名单。

### Response

```json
{
  "actions": [
    {
      "id": "SWITCH_TAB_ORG",
      "label": "成品库存",
      "type": "page",
      "description": "切换到成品库存页"
    }
  ]
}
```

## POST /api/screen/execute

校验大屏动作。V0.6 中真实 FVS 仍不由模型直接控制: 后端只根据白名单确认 `action_id` 是否允许, 前端再把已确认的动作应用到 FVS iframe。当前测试看板的分页动作会改写 iframe URL 的 `page_number`; 复杂动作才使用 `postMessage`。

### Request

```json
{
  "session_id": "demo-session-001",
  "action_id": "SWITCH_TAB_ORG",
  "params": {}
}
```

### Response

```json
{
  "success": true,
  "action_id": "SWITCH_TAB_ORG",
  "speak_text": "已为您切换到成品库存页面。"
}
```

### Illegal Action Response

```json
{
  "success": false,
  "action_id": "UNKNOWN_ACTION",
  "speak_text": "当前大屏暂不支持这个切换动作。",
  "request_id": "req-001",
  "error": {
    "code": "ACTION_NOT_ALLOWED",
    "message": "Action is not in whitelist"
  }
}
```
