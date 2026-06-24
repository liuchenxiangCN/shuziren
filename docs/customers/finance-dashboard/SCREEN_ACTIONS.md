# 企业财务综合驾驶舱 - 大屏动作说明

## 页面映射

FVS 大屏通过 URL 参数 `page_number` 控制页面切换：

| action_id | 页面 | page_number | 说明 |
|---|---|---|---|
| SWITCH_HOME | 总览 | 1 | 集团财务概览（默认首页） |
| SWITCH_FINANCE_INDICATORS | 财务指标 | 2 | 核心财务指标详情 |
| SWITCH_COST_ANALYSIS | 成本分析 | 3 | 成本费用分类分析 |
| SWITCH_BUDGET | 预算执行 | 4 | 预算执行进度跟踪 |

## 动作流程

1. 用户语音指令（如："切换到财务指标页面"）
2. 后端 Mock Dora 或 ScreenControlResolver 匹配关键词，返回 `action_id`
3. `POST /api/screen/execute` 做白名单校验
4. 校验通过后返回授权动作（包含 `fvs_function=gotoPage`、`params.pageNumber`）
5. 前端 FVS Adapter 通过修改 iframe URL 的 `page_number` 参数实现切页
6. 数字人播报确认语（如："已为您切换到财务指标分析页面。"）

## 安全约束

- 只能执行白名单中已定义的 `action_id`
- 前端只使用 `/api/screen/execute` 本次授权响应中的参数
- 非法 `action_id`、非法参数或未知 target 均安全拒绝
- 不执行模型生成的 JavaScript
