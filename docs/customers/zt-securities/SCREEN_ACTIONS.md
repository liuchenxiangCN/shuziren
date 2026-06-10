# 中天证券大屏动作

本文件记录中天证券客户大屏动作设计。实际执行配置后续应同步到 `config/customers/zt-securities/screen-actions.yaml`。

## 初始动作

| action_id | 名称 | 类型 | 说明 |
| --- | --- | --- | --- |
| `SWITCH_HOME` | 首页 | page | 返回党建大屏首页 |
| `SWITCH_TAB_ORG` | 组织建设 | tab | 切换到组织建设模块 |
| `SWITCH_TAB_STUDY` | 党员学习 | tab | 切换到党员学习模块 |
| `SWITCH_TAB_ACTIVITY` | 党建活动 | tab | 切换到党建活动模块 |

## YAML 草案

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

  SWITCH_TAB_STUDY:
    label: 党员学习
    type: tab
    description: 切换到党员学习模块
    fvs_function: switchTab
    params:
      tabId: party_study
    speak_text: 已为您打开党员学习页面。

  SWITCH_TAB_ACTIVITY:
    label: 党建活动
    type: tab
    description: 切换到党建活动模块
    fvs_function: switchTab
    params:
      tabId: party_activity
    speak_text: 已为您切换到党建活动页面。
```

## 待确认

- FVS 真实函数名。
- FVS 真实页面 ID。
- FVS 真实 Tab ID。
- 是否支持 `postMessage`。
- 是否需要动作执行回执。

