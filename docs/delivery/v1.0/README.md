# V1.0 POC 验收交付包

> Lifecycle: `CUSTOMER_SPECIFIC` / `ARCHIVED_POC_SNAPSHOT`。本目录是中天证券 POC V1.0 历史交付证据，不是标准产品 P1-P5 的版本号或交付包。

## 交付说明

本目录为中天证券党建大屏对话数字人本地 POC 的 V1.0 验收交付包。交付包面向客户验收、现场部署、演示操作、日常运维、配置变更和后续移交。

交付日期: 2026-06-11

交付范围:

- Windows + Docker Desktop 本地 POC。
- 本项目 API / Web / Ops 看板。
- Dora Agent、RAGFlow MCP、ASR / TTS、FVS iframe host 的集成说明。
- 本地脱敏 Excel 问数演示和客户私有配置目录。
- 预检、启停、smoke 和日志导出脚本。

## 文件清单

| 文件 | 用途 |
| --- | --- |
| [01_ACCEPTANCE_REPORT.md](01_ACCEPTANCE_REPORT.md) | POC 验收报告, 汇总验收范围、结果、耗时、截图附件位和客户确认项 |
| [02_DEPLOYMENT_PLAN.md](02_DEPLOYMENT_PLAN.md) | 部署方案, 覆盖 Windows、Docker Desktop、RAGFlow、FVS、Dora、ASR / TTS |
| [03_USER_MANUAL.md](03_USER_MANUAL.md) | 用户手册, 覆盖唤醒、追问、问答、问数、大屏切换、TTS 和兜底 |
| [04_OPERATIONS_MANUAL.md](04_OPERATIONS_MANUAL.md) | 运维手册, 覆盖启停、预检、日志导出、Ops 看板和故障排查 |
| [05_CONFIGURATION_MANUAL.md](05_CONFIGURATION_MANUAL.md) | 配置手册, 覆盖 `.env`、客户目录、Mock 开关、问数模式、FVS URL 和密钥边界 |
| [06_TEST_REPORT.md](06_TEST_REPORT.md) | 测试报告, 汇总 V0.7 / V0.8 / V0.9 / V1.0 已验证项和现场待确认项 |
| [07_CUSTOMER_HANDOFF_CHECKLIST.md](07_CUSTOMER_HANDOFF_CHECKLIST.md) | 客户移交清单, 用于交付物、账号、环境、风险和签收核对 |

## 建议阅读顺序

1. 先读验收报告, 明确本次 POC 已验收能力和待现场确认项。
2. 按部署方案准备环境并启动服务。
3. 按用户手册完成演示复演。
4. 按运维手册完成预检、smoke、日志导出和问题排查。
5. 按配置手册替换客户现场配置。
6. 按测试报告和移交清单完成客户签收。

## 关键边界

- 演示稳态模式只能用于固定演示保底, 不替代真实 Dora / RAGFlow / ASR / TTS / FVS 验收。
- 大屏控制必须使用 `action_id`, 并由后端白名单校验后再执行。
- 不执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell。
- API Key、Token、密码只能放本地 `.env` 或部署环境变量, 不进入前端、Git 或运维导出内容。
- 当前 `/ops` 为本地 POC 运维入口; FVS 主画布不显示运维悬浮入口。
