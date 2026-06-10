# 数据契约

本文档定义前后端、Dora、FVS、日志之间共享的数据结构。实现代码时应优先以本文档为准。

## Dora Output Types

Dora 或 Mock Dora 输出必须归一为以下类型:

- `answer`
- `screen_control`
- `clarify`
- `fallback`

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
  "speak_text": "已为您切换到组织建设页面。",
  "action": {
    "id": "SWITCH_TAB_ORG",
    "target": "organization_building"
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

## ScreenAction

动作白名单配置结构:

```yaml
actions:
  SWITCH_HOME:
    label: 首页
    type: page
    description: 返回党建大屏首页
    fvs_function: switchPage
    params:
      pageId: home
    speak_text: 已为您返回首页。

  SWITCH_TAB_ORG:
    label: 组织建设
    type: tab
    description: 切换到组织建设模块
    fvs_function: switchTab
    params:
      tabId: organization_building
    speak_text: 已为您切换到组织建设页面。
```

运行时返回给前端的动作结构:

```json
{
  "id": "SWITCH_TAB_ORG",
  "label": "组织建设",
  "type": "tab",
  "description": "切换到组织建设模块",
  "fvs_function": "switchTab",
  "params": {
    "tabId": "organization_building"
  },
  "speak_text": "已为您切换到组织建设页面。"
}
```

## Session Log

每一轮对话至少记录:

```json
{
  "session_id": "demo-session-001",
  "message_id": "msg-001",
  "created_at": "2026-06-10T20:00:00+08:00",
  "wake_text": "小天小天",
  "asr_text": "请切换到组织建设页面",
  "intent_type": "screen_control",
  "dora_request": {},
  "dora_response": {},
  "screen_action": {
    "action_id": "SWITCH_TAB_ORG",
    "success": true
  },
  "tts_text": "已为您切换到组织建设页面。",
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

