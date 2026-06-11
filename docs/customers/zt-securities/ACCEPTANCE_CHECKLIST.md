# 中天证券 POC 验收清单

## 本地开发验收

| 项目 | 标准 | 状态 |
| --- | --- | --- |
| Docker 启动 | `docker compose up -d` 后前后端可访问 | 已完成 |
| 前端页面 | 能作为数字人主页面 iframe 嵌入 FVS, 或独立展示 Mock 大屏 | 已完成人工验收: FVS iframe host 主画布可加载本机 FVS, 未唤醒只显示角落语音 icon |
| 语音唤醒 | 中文唤醒词可进入对话态 | 已完成人工验收 |
| ASR | 能将语音识别为中文文本 | 已完成人工验收 |
| Dora | 能调用 Dora Agent 并返回结果 | 已完成 |
| RAGFlow | 能基于测试文档回答问题 | 已完成人工验收: Dataset 已导入并解析完成, Dora 已通过公网 MCP 返回知识库 `answer`; 本地 MCP 返回量已做 POC 瘦身 |
| 问数 | 能返回测试党建指标 | 已完成 V0.7 本地 Excel 问数 Adapter, `/api/chat` 和 `/api/chat/stream` 已验证 11 个脱敏样例问数问题 |
| 问数模式 | 可在 Excel、Dora、Auto 模式间切换 | 已完成 V0.8 第一阶段: `ASK_METRICS_MODE=excel|dora|auto`, 默认 `excel`, `auto` 可在 Dora / Mock Dora 兜底时回退 Excel |
| 大屏控制 | 能输出 action_id 并通过白名单执行 | 已完成人工验收: V0.6 通过 `action_id` 白名单和 `page_number=1/2/3/4` 切换 FVS 四页 |
| TTS | 能播报回答 | 已完成人工验收: 真实 TTS 和分段 TTS 流式优化可用 |
| 动效 | 语音球、字幕、声波状态可见 | 已完成人工验收: FVS 主画布悬浮语音层、唤醒展开动画、文字记录和等待提示音打断策略可用 |
| 日志 / 运维看板 | 能保存每轮对话和耗时, 并查看依赖状态、最近会话、错误列表和耗时指标 | 已完成 V0.8 第三阶段: 前端“运维”看板 + 只读脱敏 Ops API + Markdown 日志导出 |
| 预检 / 启停脚本 | 能通过脚本启动、停止、预检、smoke 和导出日志包 | 已完成 V0.9: `scripts/check-poc.ps1`、`start-poc.ps1`、`stop-poc.ps1`、`smoke-demo.ps1`、`export-logs.ps1` |
| 演示稳态 | 外部 Dora 临时失败时固定演示问题可走本地兜底 | 已完成 V0.9: `DEMO_STABLE_MODE=true` 时回退 Excel 问数或 Mock Dora, 前端显示“演示稳态” |
| Mock | Dora / ASR / TTS / FVS 均有 Mock 开关 | 开关已配置, Dora/FVS Mock 已验证 |
| 错误处理 | 任一服务失败时有兜底话术 | Dora、Excel 问数、TTS 分段、FVS iframe 和麦克风权限兜底已完成 |
| 客户配置 | 客户差异进入客户私有配置目录 | 已新增 `config/customers/zt-securities/`, 后端已加载客户级动作、Demo、唤醒词和问数映射 |

## POC 准备验收

| 项目 | 标准 | 状态 |
| --- | --- | --- |
| 演示脚本 | 至少 10 个稳定问题 | 已完成, 当前 `docs/11_POC_DEMO_SCRIPT.md` 保留 20 个稳定演示问题 |
| 知识库 | 至少 5 份测试文档 | 已准备并导入 8 份脱敏测试文档, RAGFlow 解析完成 |
| 领导资料 | 至少 3 位测试领导 | 已准备 3 位测试领导资料 |
| 大屏动作 | 至少 3 个可执行动作 | 已完成, 当前 4 个 |
| 响应时间记录 | 能输出 ASR / Dora / TTS / 总耗时 | 已完成接口级耗时抽样和 SQLite 会话日志; 后续正式验收报告再固化 |
| 失败兜底 | 不出现系统报错裸露 | Dora / RAGFlow / action 兜底已验证 |
| 安全边界 | 不执行模型生成 JS | 已通过架构规则和 action_id 白名单约束; V0.6 继续保持 |

## V1.0 交付包验收

| 项目 | 标准 | 状态 |
| --- | --- | --- |
| 验收报告 | 包含复演结果、耗时、截图附件位和客户确认项 | 已完成: `docs/delivery/v1.0/01_ACCEPTANCE_REPORT.md` |
| 部署方案 | 覆盖 Windows + Docker Desktop + RAGFlow + FVS + Dora + ASR/TTS | 已完成: `docs/delivery/v1.0/02_DEPLOYMENT_PLAN.md` |
| 用户手册 | 覆盖唤醒、连续追问、问答、问数、大屏切换和兜底 | 已完成: `docs/delivery/v1.0/03_USER_MANUAL.md` |
| 运维手册 | 覆盖启停、预检、日志导出、Ops 看板和故障排查 | 已完成: `docs/delivery/v1.0/04_OPERATIONS_MANUAL.md` |
| 配置手册 | 覆盖 `.env`、客户配置、Mock 开关、问数模式和密钥边界 | 已完成: `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md` |
| 测试报告 | 覆盖 V0.7 / V0.8 / V0.9 已验证项和现场待确认项 | 已完成: `docs/delivery/v1.0/06_TEST_REPORT.md` |
| 客户移交清单 | 覆盖交付物、环境、密钥、操作、验收场景和签收 | 已完成: `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md` |
| 现场截图 | 主页面、FVS、唤醒、问数、控屏、Ops、日志包截图 | 待现场补齐 |
| 真实依赖复核 | Dora / RAGFlow / ASR / TTS / FVS 真实环境确认 | 待现场补齐 |
| 签字归档 | 客户业务、客户技术、交付负责人、运维接收人签字 | 待现场补齐 |
