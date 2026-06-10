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
  "app": "zt-digital-human-api",
  "version": "0.1.0"
}
```

## POST /api/chat

文本对话接口。V0.1 使用 Mock Dora, V0.2 接入真实 Dora, V0.3 可接收 ASR 输出文本进入同一链路。V0.7 增加 Gateway 本地 Excel 问数 Adapter, 用于稳定回答 `docs/demo_data/ask_metrics/` 中的脱敏党建指标。

### Runtime Mode

- V0.7 问数优先级: 后端会先用本地 Excel Adapter 匹配问数意图; 命中后直接返回 `type=answer`, 不调用 Dora, 避免模型编造 Excel 查询结果。
- V0.8 Draft: 新增 `ASK_METRICS_MODE=excel|dora|auto`。`excel` 保持 V0.7 行为; `dora` 由 Dora 承接通用问数; `auto` 优先 Dora, Dora 失败 / 超时 / 兜底时回退 Excel。
- `ENABLE_MOCK_DORA=true`: 继续使用 V0.1 Mock Dora, 不依赖外部 Dora。
- `ENABLE_MOCK_DORA=false`: 后端使用 `.env` 中的 `DORA_BASE_URL`、`DORA_API_KEY`、`DORA_AGENT_ID` / `DORA_AGENT_NAME`、`DORA_CHANNEL_TYPE` 调用 Dora OpenClaw SSE。
- 前端接口契约不变, Dora 原始输出由后端归一为 `answer` / `screen_control` / `fallback`。
- Dora 请求失败、超时、Agent 未找到或输出无法解析时, 返回 `type=fallback`, 不暴露 API Key、底层堆栈或供应商错误细节。

### Request

```json
{
  "session_id": "demo-session-001",
  "text": "请介绍一下张书记近期调研情况",
  "context": {
    "screen_id": "party_building_home",
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
  "title": "张书记近期动态",
  "speak_text": "张书记近期调研了基层党建工作，并强调要加强党员学习。",
  "display": {
    "mode": "text",
    "summary": "张书记近期调研基层党建工作。",
    "bullets": [
      "关注基层组织建设",
      "强调党员学习",
      "要求强化党建引领"
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

流式对话接口。V0.5 当前用于真实 Dora + RAGFlow MCP 问答时降低感知等待: 后端透传 Dora SSE 中的最终回答增量, 并把 `speak_text` 拆成短段并发调用 TTS。若 Dora 某次只返回最终 answer, 后端仍会对最终 `speak_text` 做分段 TTS, 不再等待整段文本一次性合成。V0.7 问数命中本地 Excel Adapter 时, 该接口会直接返回 `metadata`、`dora_delta` 和 `answer`, 同样复用分段 TTS。

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

前端按 `tts_ready.index` 顺序播放分段音频。若浏览器自动播放被拦截, 仍保留文字回答和原生音频控件。该接口不改变 `POST /api/chat` 的兼容性; 流式接口失败时前端可回退到普通 `/api/chat` + `/api/tts`。

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
  "wake_words": ["小天小天", "中天小天", "你好小天"],
  "settings": {
    "min_audio_ms": 800,
    "max_audio_ms": 5000,
    "cooldown_ms": 1500,
    "require_exact_phrase": false,
    "vad_threshold": 0.018,
    "silence_ms": 700,
    "command_timeout_ms": 8000,
    "followup_enabled": true,
    "followup_window_ms": 12000,
    "max_followup_turns": 3
  }
}
```

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

## POST /api/tts/stream

V0.8 Draft。TTS 字节级真流式接口, 用于替代或增强当前“分段 TTS 文件播放”方案。实现前该接口可以不存在; 当前分段 TTS fallback 仍以 `/api/chat/stream` 的 `tts_ready` 事件为准。

### Request

```json
{
  "text": "当前党员学习完成率为87.5%。",
  "voice": "longanyang",
  "format": "mp3"
}
```

### Response

响应为 `text/event-stream` 或音频流。若采用 SSE, 推荐事件如下:

```text
event: metadata
data: {"provider":"aliyun","voice":"longanyang","format":"mp3"}

event: audio_chunk
data: {"index":0,"audio_base64":"...","mime_type":"audio/mpeg"}

event: end
data: {"ok":true,"chunks":12}
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
- 前端不得直接调用 TTS 供应商 API。

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

## GET /api/tts/audio/{audio_id}

读取 V0.3 Mock TTS 生成的音频文件。

### Response

- `200 audio/wav` / `audio/mpeg` / `audio/opus`: 返回音频文件。
- `404 JSON`: 音频不存在或 `audio_id` 非法。

## Ops APIs

V0.8 Draft。运维监控和日志看板接口。所有 Ops 接口不得返回 API Key、完整密钥、供应商敏感原始响应或未脱敏客户数据。

### GET /api/ops/health

聚合系统健康状态。

```json
{
  "status": "ok",
  "app": "zt-digital-human-api",
  "version": "0.1.0",
  "customer_id": "zt-securities",
  "time": "2026-06-10T20:00:00+08:00"
}
```

### GET /api/ops/dependencies

检查外部依赖连通性。

```json
{
  "dependencies": [
    {"name": "dora", "status": "ok", "latency_ms": 320},
    {"name": "ragflow_mcp", "status": "ok", "latency_ms": 80},
    {"name": "fvs", "status": "warning", "message": "iframe not checked"},
    {"name": "asr", "status": "unknown"},
    {"name": "tts", "status": "ok", "latency_ms": 900}
  ]
}
```

### GET /api/ops/sessions

返回最近会话摘要。

```json
{
  "sessions": [
    {
      "session_id": "demo-session-001",
      "last_message_at": "2026-06-10T20:00:00+08:00",
      "turns": 6,
      "last_intent_type": "answer",
      "last_error": null
    }
  ]
}
```

### GET /api/ops/session/{session_id}

返回单个会话的最近对话明细。

### GET /api/ops/metrics

返回聚合耗时和错误指标。

### GET /api/ops/export

导出验收日志摘要。V0.9 可进一步固化为文件下载或 Markdown / CSV。

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
