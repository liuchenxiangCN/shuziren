# FVS 测试看板动作

本文件记录 V0.6 已验收的真实 FVS iframe 动作白名单。V0.8 起实际执行配置优先来自 `config/customers/zt-securities/screen-actions.yaml`, 根目录 `config/screen-actions.yaml` 仍作为默认模板。本轮测试看板为食品工厂管理看板, 页面编号来自 FVS URL 参数 `page_number`。

## 当前动作

| action_id | 名称 | 类型 | page_number | 说明 |
| --- | --- | --- | --- | --- |
| `SWITCH_HOME` | 总览 | page | 1 | 切换到总览页 |
| `SWITCH_TAB_ORG` | 成品库存 | page | 2 | 切换到成品库存页 |
| `SWITCH_TAB_STUDY` | 生产管理 | page | 3 | 切换到生产管理页 |
| `SWITCH_TAB_ACTIVITY` | 设备分析 | page | 4 | 切换到设备分析页 |

## Dora 输出要求

Dora 只允许输出上述 `action_id`。后端 Gateway 会再次校验白名单; 不在白名单中的动作不会执行。Dora 不应输出 JavaScript、FVS 函数名或 URL 参数。

### 成品库存

用户说法:

```text
请切换到成品库存页面
```

Dora 应输出:

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

### 生产管理

用户说法:

```text
请切换到生产管理页面
```

Dora 应输出:

```json
{
  "type": "screen_control",
  "speak_text": "已为您切换到生产管理页面。",
  "action": {
    "id": "SWITCH_TAB_STUDY",
    "target": "production_management"
  }
}
```

### 设备分析

用户说法:

```text
请切换到设备分析页面
```

Dora 应输出:

```json
{
  "type": "screen_control",
  "speak_text": "已为您切换到设备分析页面。",
  "action": {
    "id": "SWITCH_TAB_ACTIVITY",
    "target": "equipment_analysis"
  }
}
```

### 总览

用户说法:

```text
返回总览
```

Dora 应输出:

```json
{
  "type": "screen_control",
  "speak_text": "已为您切换到总览页面。",
  "action": {
    "id": "SWITCH_HOME",
    "target": "overview"
  }
}
```

### 非法动作

用户说法:

```text
打开风险预警页面
```

Dora 应输出:

```json
{
  "type": "fallback",
  "speak_text": "当前大屏暂不支持这个切换动作。",
  "reason": "action_id 不在白名单中"
}
```

## YAML 摘要

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

  SWITCH_TAB_STUDY:
    label: 生产管理
    type: page
    description: 切换到生产管理页
    fvs_function: gotoPage
    params:
      pageNumber: 3
    speak_text: 已为您切换到生产管理页面。

  SWITCH_TAB_ACTIVITY:
    label: 设备分析
    type: page
    description: 切换到设备分析页
    fvs_function: gotoPage
    params:
      pageNumber: 4
    speak_text: 已为您切换到设备分析页面。
```

## FVS iframe 控制策略

V0.6 已验收方案推荐以数字人前端为主体 iframe 嵌入 FVS 看板。数字人前端只在 Gateway 白名单校验通过后执行动作:

1. 若白名单动作包含 `params.pageNumber`, 前端直接更新 FVS iframe 的 URL 查询参数 `page_number`。
2. 若动作不含 `pageNumber`, 前端再向 FVS iframe 发送 `FVS_ACTION` 消息, 由 FVS 页面内固定白名单监听处理。

当前测试看板的第一页 URL 形态:

```text
/webroot/decision/view/duchamp?viewlet=...食品工厂管理看板.fvs&page_number=1
```

本机 FVS 原始地址为 `http://localhost:8075/webroot/...`。由于 FVS 返回 `X-Frame-Options: SAMEORIGIN`, 当前数字人前端通过 Web Nginx 同源代理 `/webroot/ -> http://host.docker.internal:8075/webroot/` 加载。

FVS 看板侧若后续需要预埋消息监听, 建议仍以 `action_id` 做固定映射:

| action_id | FVS 侧待映射能力 |
| --- | --- |
| `SWITCH_HOME` | 切换到总览, page_number=1 |
| `SWITCH_TAB_ORG` | 切换到成品库存, page_number=2 |
| `SWITCH_TAB_STUDY` | 切换到生产管理, page_number=3 |
| `SWITCH_TAB_ACTIVITY` | 切换到设备分析, page_number=4 |

正式联调时不要根据 `functionName` 拼接并执行 JavaScript。

## 待确认

- FVS 看板是否允许长期被本项目页面 iframe 嵌入。
- `localhost:8075` 在交付环境中的正式域名 / origin, 以及正式同源代理策略。
- 除分页外是否还需要组件级控制。
- 是否需要动作执行回执。
