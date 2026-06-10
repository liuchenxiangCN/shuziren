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

V0.8 Draft。问数模式由 `ASK_METRICS_MODE` 控制:

```json
{
  "mode": "auto",
  "primary": "dora",
  "fallback": "excel",
  "allow_model_generated_code": false
}
```

模式:

- `excel`: 固定走 Gateway 本地 Excel Adapter。
- `dora`: 由 Dora 承接通用问数, Gateway 只做归一化和安全兜底。
- `auto`: 优先 Dora, Dora 失败 / 超时 / 兜底时回退 Excel。

规则:

- `excel` 模式必须保持 V0.7 11 个固定问数 smoke 不退化。
- `dora` / `auto` 模式下, Dora 输出仍归一为标准 `answer`。
- Dora 问数回答应包含来源、口径、时间范围或无法确认说明。
- Gateway 不执行 Dora 生成的 SQL、Python、JavaScript 或 shell。

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

规则:

- 前端只能在用户显式启用后台监听后请求麦克风权限。
- 前端用本地 VAD / 音量阈值截取短音频片段, 再调用 ASR 判断唤醒词。
- 未命中唤醒词的短片段不进入 `/api/chat`。
- 命中唤醒词后, 可复用同一句中的剩余文本作为正式指令, 或进入一次正式指令录音。
- `followup_enabled=true` 时, 前端在播报结束后进入短时连续对话窗口, 窗口内下一句直接作为正式指令。
- `followup_window_ms` 控制播报后等待追问的时长, `max_followup_turns` 控制单次唤醒后最多连续追问轮数。
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

V0.8 Draft。TTS 字节级真流式音频片段:

```json
{
  "index": 0,
  "audio_base64": "...",
  "mime_type": "audio/mpeg",
  "duration_ms": 160,
  "provider": "aliyun",
  "format": "mp3"
}
```

规则:

- `index` 表示播放顺序。
- 前端必须按顺序播放或缓冲。
- 流式失败时回退现有 `Streamed TTS Segment`。
- 不在前端暴露 TTS API Key。

## Ops Status

V0.8 Draft。运维看板使用的依赖状态结构:

```json
{
  "name": "dora",
  "status": "ok",
  "latency_ms": 320,
  "message": "reachable",
  "checked_at": "2026-06-10T20:00:00+08:00"
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

## Customer Config Overlay

V0.8 Draft。客户私有配置覆盖规则:

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
- `.env` 只放密钥、本机端口和部署参数。
- YAML 放非敏感客户配置。
- 前端只能获得后端透出的安全配置。

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
