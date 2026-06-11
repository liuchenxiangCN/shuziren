# V1.0 客户移交清单

## 交付物清单

| 编号 | 交付物 | 路径 / 说明 | 状态 |
| --- | --- | --- | --- |
| H-001 | 验收报告 | `docs/delivery/v1.0/01_ACCEPTANCE_REPORT.md` | 已提供 |
| H-002 | 部署方案 | `docs/delivery/v1.0/02_DEPLOYMENT_PLAN.md` | 已提供 |
| H-003 | 用户手册 | `docs/delivery/v1.0/03_USER_MANUAL.md` | 已提供 |
| H-004 | 运维手册 | `docs/delivery/v1.0/04_OPERATIONS_MANUAL.md` | 已提供 |
| H-005 | 配置手册 | `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md` | 已提供 |
| H-006 | 测试报告 | `docs/delivery/v1.0/06_TEST_REPORT.md` | 已提供 |
| H-007 | 客户移交清单 | `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md` | 已提供 |
| H-008 | 演示脚本 | `docs/11_POC_DEMO_SCRIPT.md` | 已提供 |
| H-009 | 客户验收清单 | `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md` | 已提供 |
| H-010 | 客户配置目录 | `config/customers/zt-securities/` | 已提供 |
| H-011 | 预检 / 启停 / 日志脚本 | `scripts/` | 已提供 |
| H-012 | 脱敏问数样例 | `docs/demo_data/ask_metrics/` | 已提供 |
| H-013 | 脱敏知识库样例 | `docs/demo_knowledge/` | 已提供 |
| H-014 | 最近 smoke 结果 | `logs/smoke/smoke-demo-20260611-011803.md` | 已生成 |
| H-015 | 最近日志包 | `logs/exports/zt-poc-logs-20260611-011813.zip` | 已生成 |

## 环境移交

| 项目 | 交付状态 | 客户确认 |
| --- | --- | --- |
| Windows 演示机 | 待现场确认 |  |
| Docker Desktop + WSL2 | 待现场确认 |  |
| 主项目目录 `D:\Project\shuziren` | 待现场确认 |  |
| RAGFlow 目录 `D:\Project\ragflow` | 待现场确认 |  |
| `.env` 客户现场配置 | 待现场确认 |  |
| API / Web 容器启动 | 待现场确认 |  |
| RAGFlow 容器启动 | 待现场确认 |  |
| 浏览器麦克风权限 | 待现场确认 |  |
| 系统音箱 / 播放设备 | 待现场确认 |  |

## 账号和密钥移交

| 项目 | 存放位置 | 移交状态 |
| --- | --- | --- |
| Dora API Key | 客户现场 `.env` / 密钥系统 | 待客户提供 |
| ASR API Key | 客户现场 `.env` / 密钥系统 | 待客户提供 |
| TTS API Key | 客户现场 `.env` / 密钥系统 | 待客户提供 |
| RAGFlow MCP Key | `D:\Project\ragflow\docker\.env` 或客户密钥系统 | 待客户确认 |
| FVS 访问凭据 | 客户 FVS 系统 | 待客户确认 |

密钥规则:

- 不进入前端。
- 不进入 Git。
- 不写入客户 YAML。
- 不随日志包默认导出。
- 若密钥曾出现在调试上下文中, 正式交付前建议轮换。

## 操作移交

| 操作 | 命令 / 入口 | 客户确认 |
| --- | --- | --- |
| 预检 | `scripts\check-poc.ps1` |  |
| 启动 | `scripts\start-poc.ps1 -Build` |  |
| 演示稳态启动 | `scripts\start-poc.ps1 -Build -DemoStable` |  |
| 停止 | `scripts\stop-poc.ps1` |  |
| Smoke | `scripts\smoke-demo.ps1 -ExecuteScreenActions` |  |
| 日志导出 | `scripts\export-logs.ps1 -Zip` |  |
| 主页面 | `http://localhost:18000` |  |
| 运维看板 | `http://localhost:18000/ops` |  |
| API 健康 | `http://localhost:18080/api/health` |  |

## 验收场景清单

| 场景 | 示例 | 客户确认 |
| --- | --- | --- |
| 唤醒 | 小天小天 |  |
| 同句指令 | 小天小天, 当前党员学习完成率是多少 |  |
| 连续追问 | 本月主题党日开展了几次 |  |
| 领导欢迎 | 我是张书记 |  |
| 知识库问答 | 入党流程是什么 |  |
| 问数 | 当前党员学习完成率是多少 |  |
| 大屏切换 | 切换到成品库存 |  |
| 返回总览 | 返回总览 |  |
| 非法动作兜底 | 打开不存在页面 |  |
| Ops 查看 | 打开 `/ops` |  |
| 日志包导出 | `export-logs.ps1 -Zip` |  |

## 风险和限制确认

| 编号 | 内容 | 客户确认 |
| --- | --- | --- |
| R-002 | FVS 正式环境 iframe / 同源代理策略仍需确认 |  |
| R-003 | 分页以外的 FVS 组件级控制未纳入当前 POC 验收 |  |
| R-006 | Dora 输出格式仍需由 Gateway 容错, 真实 Prompt 需持续维护 |  |
| R-008 | 正式问数数据源、指标口径和刷新方式未最终确认 |  |
| R-014 | 正式演示前建议轮换曾用于调试的 API Key |  |
| R-022 | `/ops` 当前未接登录鉴权, 需确认访问控制策略 |  |
| R-023 | 演示稳态不能替代真实依赖验收 |  |
| R-025 | 现场截图、真实依赖和客户签字需在验收当天补齐 |  |

## 交接签收

| 角色 | 姓名 | 日期 | 签字 |
| --- | --- | --- | --- |
| 客户业务验收人 |  |  |  |
| 客户技术验收人 |  |  |  |
| 交付负责人 |  |  |  |
| 运维接收人 |  |  |  |

## 后续建议

- 正式上线前完成登录鉴权、网络安全和合规评审。
- 确认正式问数数据源和指标口径后, 再替换脱敏 Excel 样例。
- 确认 FVS 组件级控制接口后, 再扩展分页以外的动作。
- 对 Dora Prompt、RAGFlow 切片和召回阈值做客户真实资料调优。
- 对 ASR 热词、现场麦克风、噪声和播放权限做专项优化。
