# 数据契约

本文档定义前后端、Dora、FVS、日志之间共享的数据结构。实现代码时应优先以本文档为准。

## Dora Output Types

Dora 或 Mock Dora 输出必须归一为以下类型:

- `answer`
- `screen_control`
- `clarify`
- `fallback`

V0.2 Dora Adapter 对外先稳定返回:

- `answer`
- `screen_control`
- `fallback`

如果真实 Dora 返回 `clarify`, Gateway 在 V0.2 中先包装为 `answer` 展示澄清文本和选项; 后续需要前端交互式澄清时再恢复为独立 `clarify` 流程。

## Answer

```json
{
  "type": "answer",
  "title": "党员学习情况总结",
  "speak_text": "当前党员学习完成率为百分之八十六，较上月提升六个百分点。",
  "display": {
    "mode": "text",
    "summary": "当前学习完成率较上月提升，整体情况良好。",
    "bullets": [
      "学习人数：120 人",
      "完成人数：103 人",
      "完成率：86%"
    ]
  }
}
```

## Ask Metrics Answer

V0.7 本地 Excel 问数 Adapter 命中后仍返回标准 `answer`, 不新增前端响应类型。回答必须说明数据来源, 防止把脱敏样例误认为真实客户数据。

```json
{
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

当前支持的本地问数范围:

- 党员学习: 党员总数、已完成学习人数、学习完成率、未完成人数、最低完成率支部。
- 组织生活与党建活动: 活动完成率、主题党日完成次数、平均参会率、整改闭环率。
- 党员发展: 入党积极分子、发展对象及支部分布、预备党员、本年转正、材料待补充、政审待完成。

规则:

- 数据源为 `docs/demo_data/ask_metrics/*.xlsx` 的脱敏样例。
- Gateway 在调用 Dora 前先匹配问数意图; 命中后直接读 Excel 返回。
- 未命中问数意图时继续走 Dora / Mock Dora, 不抢占知识库问答和控屏。
- 禁止执行模型生成的 SQL、Python 或 JavaScript 来查询数据。

## Ask Metrics Mode

V0.8 已实现。问数模式由 `ASK_METRICS_MODE` 控制:

```json
{
  "mode": "auto",
  "primary": "dora",
  "fallback": "excel",
  "allow_model_generated_code": false
}
```

模式:

- `excel`: Gateway 本地 Excel Adapter 先匹配问数; 未命中继续 Dora / Mock Dora。
- `dora`: Excel Adapter 不抢占, 由 Dora / Mock Dora 承接通用问数, Gateway 只做归一化和安全兜底。
- `auto`: 优先 Dora / Mock Dora, Dora 请求失败或返回 `fallback` 时回退 Excel。

规则:

- `excel` 模式必须保持 V0.7 11 个固定问数 smoke 不退化。
- `dora` / `auto` 模式下, Dora 输出仍归一为标准 `answer`。
- Dora 问数回答应包含来源、口径、时间范围或无法确认说明。
- Gateway 不执行 Dora 生成的 SQL、Python、JavaScript 或 shell。

## Demo Stable Mode

V0.9 已实现。演示稳态模式由 `DEMO_STABLE_MODE` 控制, 前端构建状态可由 `VITE_DEMO_STABLE_MODE` 显示:

```json
{
  "stable_mode": true,
  "fallback_order": ["ask_metrics_excel", "mock_dora", "safe_fallback"],
  "allow_model_generated_code": false
}
```

规则:

- 仅当 `DEMO_STABLE_MODE=true` 时启用。
- Dora 请求失败或流式 Dora 失败时, Gateway 优先尝试本地 Excel 问数和 Mock Dora 演示规则。
- 演示兜底仍返回标准 `answer` / `screen_control` / `fallback` 类型, 不新增对话响应类型。
- `screen_control` 仍必须通过 `action_id` 白名单校验。
- 未命中本地演示规则时返回安全 `fallback`, 不暴露 API Key、供应商原始响应或堆栈。
- 该模式只用于现场演示稳态, 正式验收应明确记录是否开启。

演示配置接口结构:

```json
{
  "stable_mode": true,
  "customer_id": "zt-securities",
  "ask_metrics_mode": "excel",
  "mock": {
    "dora": false,
    "asr": false,
    "tts": false,
    "fvs": true
  },
  "questions": [
    {
      "id": "Q-004",
      "text": "当前党员学习完成率是多少？",
      "category": "data",
      "expected": "返回学习完成率"
    }
  ],
  "notice": "演示稳态模式已开启，外部 Dora 失败时会优先使用本地演示兜底。"
}
```

## Chart Answer

```json
{
  "type": "answer",
  "title": "党员学习完成率趋势",
  "speak_text": "近三个月党员学习完成率持续提升。",
  "display": {
    "mode": "echarts",
    "chart_config": {
      "title": { "text": "党员学习完成率" },
      "xAxis": { "type": "category", "data": ["4月", "5月", "6月"] },
      "yAxis": { "type": "value" },
      "series": [
        { "type": "line", "data": [72, 80, 86] }
      ]
    }
  }
}
```

## Screen Control

```json
{
  "type": "screen_control",
  "speak_text": "已为您切换到成品库存页面。",
  "action": {
    "id": "SWITCH_TAB_ORG",
    "target": "finished_goods_inventory"
  }
}
```

规则:

- `action.id` 必须存在于白名单。
- 后端负责校验。
- 前端只执行后端已确认的动作。
- 禁止将模型生成的 JavaScript 直接传给前端执行。

## Clarify

```json
{
  "type": "clarify",
  "speak_text": "请问您指的是张某某书记，还是张某某副书记？",
  "options": ["张某某书记", "张某某副书记"]
}
```

## Fallback

```json
{
  "type": "fallback",
  "speak_text": "这个问题我还需要更多信息，请您换一种方式描述。",
  "reason": "无法判断用户意图"
}
```

## ASR Transcription

V0.3 最小 ASR 返回最终文本, 由前端继续调用 `/api/chat`。

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

规则:

- `text` 是进入 `/api/chat` 的唯一用户文本来源。
- `audio_base64` 只在请求中传输, 不进入前端日志展示。
- `ENABLE_MOCK_ASR=false` 且真实 Provider 未配置时返回安全错误, 不暴露供应商细节。

## Wake Config

V0.4 后台监听从 `config/wake-words.yaml` 读取配置, 经 `GET /api/wake/config` 返回给前端。

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

规则:

- 前端只能在用户显式启用后台监听后请求麦克风权限。
- 前端用本地 VAD / 音量阈值截取短音频片段, 再调用 ASR 判断唤醒词。
- 未命中唤醒词的短片段不进入 `/api/chat`。
- 命中唤醒词后, 可复用同一句中的剩余文本作为正式指令, 或进入一次正式指令录音。
- `followup_enabled=true` 时, 前端在播报结束后进入短时连续对话窗口, 窗口内下一句直接作为正式指令。
- `followup_window_ms` 控制播报后等待追问的时长, `max_followup_turns` 控制单次唤醒后最多连续追问轮数。
- `barge_in_enabled=true` 时, 前端在 `speaking` 播报状态下继续截取短片段, 但只用 `barge_in_wake_words` 中的长唤醒词确认是否打断当前 TTS。未命中、空识别或 ASR 失败时继续播报, 不进入 `/api/chat`。
- 不保存未命中唤醒词的环境音。

## TTS Synthesis

V0.3 最小 TTS 返回可播放音频 URL 或安全错误。

```json
{
  "success": true,
  "audio_url": "/api/tts/audio/tts-001.wav",
  "audio_id": "tts-001.wav",
  "duration_ms": 2300,
  "provider": "mock",
  "voice": "Cherry",
  "format": "wav",
  "mock": true
}
```

规则:

- 前端只使用后端返回的 `audio_url`, 不直接调用 TTS 供应商。
- V0.3 Mock TTS 固定生成 `wav`; 真实 CosyVoice TTS 可生成 `mp3`、`wav`、`pcm` 或 `opus`; `format` 字段必须表达实际返回格式。
- `audio_id` 必须由后端生成并校验, 禁止路径穿越。
- 浏览器禁止自动播放时, 前端保留文字展示和原生音频控件。

## Streamed TTS Segment

V0.5 `POST /api/chat/stream` 中, 后端会把最终 `speak_text` 拆成短段并发合成。每个就绪分段通过 `tts_ready` SSE 事件返回:

```json
{
  "index": 0,
  "text": "入党流程共包括八个主要环节：",
  "audio_url": "/api/tts/audio/tts-001.mp3",
  "audio_id": "tts-001.mp3",
  "duration_ms": 2825,
  "provider": "aliyun",
  "format": "mp3",
  "mock": false
}
```

规则:

- `index` 是播放顺序; 多个 TTS 分段并发合成时, SSE 到达顺序可能不是 `0, 1, 2...`。
- 前端必须按 `index` 顺序播放, 并在缺少下一段时等待后续 `tts_ready` 或 `end`。
- `audio_url` 仍只能来自后端, 前端不得直接调用 TTS 供应商。
- 若 Dora 没有稳定输出 `speak_text` 增量, 后端会在最终 `answer` 后再按同一规则分段合成。

## Streamed Audio Chunk

V0.8 第二阶段已实现。TTS 字节级真流式音频片段由 `POST /api/tts/stream` 通过 SSE 返回:

```json
{
  "index": 0,
  "audio_base64": "...",
  "mime_type": "audio/L16",
  "duration_ms": 160,
  "provider": "aliyun",
  "format": "pcm",
  "sample_rate": 22050,
  "mock": false
}
```

规则:

- `index` 表示播放顺序。
- 前端默认请求 `format=pcm`, 并用 Web Audio API 将每个 PCM chunk 解码为 `AudioBuffer` 后按时间轴排队播放。
- `metadata.sample_rate` / `audio_chunk.sample_rate` 表示 PCM 采样率。
- 流式失败时回退现有 `Streamed TTS Segment`。
- Mock TTS 也支持输出 PCM chunk, 便于无外部 TTS Key 时验证前端真流式播放器、打断和 fallback。
- 不在前端暴露 TTS API Key。

## Ops Status

V0.8 第三阶段已实现。运维看板使用的依赖状态结构:

```json
{
  "name": "dora",
  "label": "Dora Agent",
  "status": "ok",
  "latency_ms": 320,
  "message": "HTTP 200",
  "checked_at": "2026-06-11T20:00:00+08:00",
  "details": {
    "mode": "real",
    "agent_configured": true
  }
}
```

`status` 可为:

- `ok`
- `warning`
- `error`
- `unknown`

规则:

- 运维状态不得包含 API Key、完整密钥或供应商敏感原始响应。
- 错误消息应面向排障, 不泄露底层堆栈。
- 依赖探测只做轻量健康 / 配置检查, 不触发 Dora 对话、ASR 上传或 TTS 合成。
- Mock 模式会明确返回 `mode=mock`, 避免把 Mock 状态误认为真实外部服务连通。

## Ops Session Summary

运维看板的最近会话摘要来自 `session_logs` SQLite 表:

```json
{
  "session_id": "demo-session-001",
  "last_message_at": "2026-06-11T20:00:00+08:00",
  "turns": 6,
  "last_intent_type": "answer",
  "last_user_text": "当前党员学习完成率是多少?",
  "last_error": null,
  "last_latency_ms": 1200
}
```

规则:

- `turns` 表示该 session 在日志表中的事件数, 包含 chat 和 screen execute 事件。
- `last_user_text` 只保留截断后的摘要。
- `last_error` 仅包含脱敏后的 `code` 和 `message`。

## Ops Error Item

错误列表结构:

```json
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
```

规则:

- `fallback` 会纳入错误列表, 便于排查外部依赖或意图兜底。
- 错误消息不得包含 API Key、完整密钥、供应商原始响应或堆栈。

## Ops Metrics

耗时指标结构:

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

当前耗时来自 `session_logs.latency_total_ms`, 覆盖 `/api/chat`、`/api/chat/stream` 和 `/api/screen/execute` 已写入的事件。更细的 ASR / Dora / RAGFlow / TTS 分段耗时可作为后续增强项, V0.9 已先通过预检和日志包固化现场排障流程。

## Customer Config Overlay

V0.8 已实现第一阶段。客户私有配置覆盖规则:

```json
{
  "customer_id": "zt-securities",
  "customer_config_dir": "/app/config/customers/zt-securities",
  "overrides": [
    "runtime.yaml",
    "screen-actions.yaml",
    "ask-metrics.yaml",
    "fvs.yaml",
    "dora.yaml",
    "ragflow.yaml",
    "voice.yaml",
    "demo-cases.yaml"
  ]
}
```

规则:

- 根配置作为默认模板。
- 客户目录配置作为覆盖层。
- `.env` 和部署环境变量作为显式运行时覆盖。
- 旧 `.env` 中等于根目录默认路径的配置项不阻止客户目录覆盖; 真正自定义路径仍优先。
- `.env` 只放密钥、本机端口和部署参数。
- YAML 放非敏感客户配置。
- 前端只能获得后端透出的安全配置。
- V0.8 第一阶段已接入后端覆盖的文件: `screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`、`wake-words.yaml`。
- `dora.yaml`、`ragflow.yaml`、`voice.yaml` 提供后端可读取的非敏感参数; API Key 仍不从 YAML 读取。
- `fvs.yaml` 是客户侧 FVS 配置样例; 当前前端运行时仍通过 `VITE_FVS_*` 构建参数或 URL 参数获取安全配置。

## ScreenAction

动作白名单配置结构:

```yaml
actions:
  SWITCH_HOME:
    label: 总览
    type: page
    description: 切换到总览页
    fvs_function: gotoPage
    params:
      pageNumber: 1
    speak_text: 已为您切换到总览页面。

  SWITCH_TAB_ORG:
    label: 成品库存
    type: page
    description: 切换到成品库存页
    fvs_function: gotoPage
    params:
      pageNumber: 2
    speak_text: 已为您切换到成品库存页面。
```

运行时返回给前端的动作结构:

```json
{
  "id": "SWITCH_TAB_ORG",
  "label": "成品库存",
  "type": "page",
  "description": "切换到成品库存页",
  "fvs_function": "gotoPage",
  "params": {
    "pageNumber": 2
  },
  "speak_text": "已为您切换到成品库存页面。"
}
```

数字人前端执行 FVS 动作:

- 若动作包含 `params.pageNumber`, 前端 Adapter 会在 `/api/screen/execute` 成功后改写 iframe URL 中的 `page_number`。
- 若动作不包含 `pageNumber`, 前端 Adapter 才向 FVS iframe 发送动作消息。

动作消息结构:

```json
{
  "type": "FVS_ACTION",
  "source": "zt-digital-human",
  "action_id": "SWITCH_TAB_ORG",
  "actionId": "SWITCH_TAB_ORG",
  "functionName": "gotoPage",
  "params": {
    "pageNumber": 2
  }
}
```

规则:

- 该消息只能在 `/api/screen/execute` 已返回 `success=true` 后由前端 Adapter 发出。
- FVS 看板应以 `action_id` / `actionId` 做本地白名单映射。
- `functionName` 和 `params` 是配置字段, 不得作为任意 JavaScript 动态执行入口。

## Session Log

每一轮对话至少记录:

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-001",
  "created_at": "2026-06-10T20:00:00+08:00",
  "wake_text": "小天小天",
  "asr_text": "请切换到成品库存页面",
  "intent_type": "screen_control",
  "dora_request": {},
  "dora_response": {},
  "screen_action": {
    "action_id": "SWITCH_TAB_ORG",
    "success": true
  },
  "tts_text": "已为您切换到成品库存页面。",
  "latency": {
    "asr_ms": 1200,
    "dora_ms": 2800,
    "tts_ms": 900,
    "total_ms": 5300
  },
  "error": null
}
```

## Dora 输出容错

Gateway 必须处理:

- Dora 返回标准 JSON: 直接解析。
- Dora 返回 Markdown 代码块包裹 JSON: 提取 JSON。
- Dora 返回自然语言: 包装为 `answer`。
- Dora 返回非法 `screen_control`: 拒绝执行并返回 `fallback`。
- Dora 返回缺失 `speak_text`: 使用安全兜底话术。
- Dora SSE `metadata` / `values` 等非回答事件: 不进入最终回答。
- Dora SSE `messages` chunk: 收敛文本后再进入统一归一化。
- Dora 请求失败、超时或 Agent 未解析成功: 返回 `fallback`, 不暴露 API Key 或底层堆栈。
