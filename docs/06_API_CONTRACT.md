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

文本对话接口。V0.1 使用 Mock Dora, V0.2 接入真实 Dora。

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

### Response: screen_control

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-002",
  "type": "screen_control",
  "speak_text": "已为您切换到组织建设页面。",
  "action": {
    "id": "SWITCH_TAB_ORG",
    "target": "organization_building"
  }
}
```

## GET /api/chat/sse

流式对话接口。

### Query

```text
session_id=demo-session-001
text=请总结一下当前党建工作
```

### Event Types

| Event | 用途 |
| --- | --- |
| metadata | 会话和消息元数据 |
| asr_text | ASR 识别文本 |
| dora_delta | Dora 增量文本 |
| tool_status | 工具调用状态 |
| screen_action | 大屏动作 |
| answer | 最终回答 |
| tts_ready | TTS 音频就绪 |
| error | 异常 |
| end | 结束 |

## WS /ws/asr

ASR WebSocket。V0.3 后实现。

### Client -> Server

- 发送 PCM / WebM 音频片段。
- 发送结束事件。

### Server -> Client

```json
{
  "type": "asr_final",
  "text": "小天小天，请切换到组织建设页面"
}
```

## POST /api/tts

TTS 合成。V0.3 后实现。

### Request

```json
{
  "text": "已为您切换到组织建设页面。",
  "voice": "Cherry",
  "format": "mp3"
}
```

### Response

```json
{
  "audio_url": "/api/tts/audio/tts-001.mp3",
  "duration_ms": 2300
}
```

## GET /api/screen/actions

获取大屏动作白名单。

### Response

```json
{
  "actions": [
    {
      "id": "SWITCH_TAB_ORG",
      "label": "组织建设",
      "type": "tab",
      "description": "切换到组织建设模块"
    }
  ]
}
```

## POST /api/screen/execute

校验并执行大屏动作。V0.1 只返回 Mock 执行结果。

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
  "speak_text": "已为您切换到组织建设页面。"
}
```

### Illegal Action Response

```json
{
  "success": false,
  "action_id": "UNKNOWN_ACTION",
  "speak_text": "当前大屏暂不支持这个切换动作。",
  "error": {
    "code": "ACTION_NOT_ALLOWED",
    "message": "Action is not in whitelist"
  }
}
```

