# 企业财务综合驾驶舱 - 演示用例

## 测试用演示问题

以下问题覆盖唤醒、欢迎、财务查询、页面切换四类场景：

| ID | 类型 | 问题 | 预期响应 |
|---|---|---|---|
| Q-001 | wakeup | 小财小财 | 进入 listening 状态 |
| Q-002 | welcome | 我是王总 | 返回集团财务欢迎语 |
| Q-003 | data | 当前营业收入是多少？ | 返回营业总收入 12.5 亿元 |
| Q-004 | data | 净利润怎么样？ | 返回净利润 2.8 亿元 |
| Q-005 | data | 成本费用情况如何？ | 返回总成本 8.9 亿元 |
| Q-006 | data | 总资产和负债情况？ | 返回总资产 85.3 亿元 |
| Q-007 | data | 预算执行进度？ | 返回预算执行率 65.3% |
| Q-008 | data | 现金流怎么样？ | 返回经营现金流净额 1.5 亿元 |
| Q-009 | screen | 切换到财务指标页面 | 大屏切换到 page_number=2 |
| Q-010 | screen | 返回总览 | 大屏切换到 page_number=1 |

## Smoke 测试命令

```powershell
# 完整 smoke（不含大屏动作）
scripts/smoke-demo.ps1

# 包含大屏动作的完整 smoke
scripts/smoke-demo.ps1 -ExecuteScreenActions
```
