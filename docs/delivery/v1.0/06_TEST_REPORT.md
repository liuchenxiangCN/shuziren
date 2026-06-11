# V1.0 测试报告

## 报告说明

本报告汇总 V0.7、V0.8、V0.9 和 V1.0 验收交付准备阶段的验证记录。测试证据来自开发日志、测试计划、脚本输出、日志包和人工验收记录。

报告日期: 2026-06-11

## 测试范围

- 后端编译和前端构建。
- Docker Compose 配置。
- API / Web 启动。
- Dora + RAGFlow 知识库问答。
- Excel 问数 Adapter。
- TTS 字节级真流式和分段 fallback。
- 语音唤醒、连续追问和播报中长唤醒词确认打断。
- 运维 Ops API 和日志脱敏导出。
- V0.9 预检、启停、smoke、日志导出脚本。
- FVS iframe host 和四页切换。
- V1.0 交付文档完整性。

## 已验证命令

历史验证记录中已通过:

```powershell
python -m compileall apps/api/app
corepack pnpm --dir apps/web build
docker compose config --services
git diff --check
scripts\check-poc.ps1 -SkipExternal -Json
scripts\start-poc.ps1 -Build -DemoStable
scripts\smoke-demo.ps1 -ExecuteScreenActions
scripts\export-logs.ps1 -Zip
scripts\check-poc.ps1 -RequireServices -SkipExternal -Json
```

## 最新脚本证据

Smoke:

```text
logs/smoke/smoke-demo-20260611-011803.md
```

日志包:

```text
logs/exports/zt-poc-logs-20260611-011813.zip
```

Ops Health:

```json
{"status":"ok","app":"zt-digital-human-api","customer_id":"zt-securities"}
```

Ops Dependencies 摘要:

| 依赖 | 状态 | 说明 |
| --- | --- | --- |
| SQLite 会话日志 | ok | `sessions.db` 可读写 |
| 大屏动作白名单 | ok | 已加载 4 个 `action_id` |
| Dora | error | 当时探测超时 |
| RAGFlow | error | 当时探测失败 |
| ASR | ok | 真实 ASR 配置已就绪 |
| TTS | ok | 真实 TTS 配置已就绪, streaming enabled |
| FVS | ok | 当时 Mock FVS 已启用 |

## 功能测试结果

### V0.7 问数稳定版

| 用例 | 结果 |
| --- | --- |
| 11 个 Excel 问数 smoke | 通过 |
| `/api/chat` 问数命中后直接返回 `answer` | 通过 |
| `/api/chat/stream` 问数返回 `metadata -> dora_delta -> answer` | 通过 |
| `入党流程是什么?` 不被问数 Adapter 抢占 | 通过 |
| Docker Compose 挂载 `/app/docs/demo_data` | 通过 |

代表数据:

- 党员学习完成率: 87.5%。
- 党员总数: 128 人。
- 已完成学习: 112 人。
- 整改闭环率: 46.7%。
- 入党积极分子: 12 人。

### V0.8 功能增强版

| 用例 | 结果 |
| --- | --- |
| 客户私有配置目录加载 | 通过 |
| `ASK_METRICS_MODE=excel` | 通过 |
| `ASK_METRICS_MODE=dora` 不让 Excel 抢答 | 通过 |
| `ASK_METRICS_MODE=auto` 可回退 Excel | 通过 |
| `POST /api/tts/stream` 真流式 | 通过 |
| `TTS_STREAMING_ENABLED=false` 回退分段 TTS | 通过 |
| Ops API smoke | 通过 |
| Ops 导出密钥模式扫描 | 通过 |

TTS 抽样:

- 首个 PCM chunk 约 567ms。
- `end.duration_ms=3387`。
- 共 33 个 chunk。

### V0.9 交付优化版

| 用例 | 结果 |
| --- | --- |
| `check-poc.ps1` 预检 | 通过 |
| `start-poc.ps1 -Build -DemoStable` | 通过 |
| `GET /api/demo/config` | 通过 |
| `smoke-demo.ps1 -ExecuteScreenActions` | 通过 |
| `export-logs.ps1 -Zip` | 通过 |
| FVS iframe 超时 / 失败兜底 | 通过 |
| Excel 缺文件、Dora 流式异常、TTS 分段异常安全提示 | 通过 |

最近 smoke 结果:

| ID | OK | Type | Latency |
| --- | --- | --- | ---: |
| ZT-L-001 | True | answer | 17587 ms |
| ZT-K-001 | True | answer | 13092 ms |
| ZT-D-001 | True | answer | 41 ms |
| ZT-S-001 | True | screen_control | 4376 ms |
| ZT-S-002 | True | screen_control | 5063 ms |

### FVS 与语音人工验收

| 项目 | 结果 |
| --- | --- |
| V0.4 真实麦克风唤醒 | 用户已人工验收 |
| V0.4.1 连续对话窗口 | 用户已人工验收 |
| V0.5 Dora + RAGFlow MCP | 用户已人工验收 |
| V0.6 FVS iframe host 和四页切换 | 用户已人工验收 |
| V0.6 等待提示音和 AI 结果打断 | 用户已人工验收 |
| 2026-06-11 小型语音 icon、评论流和“您好。”顺序 | 源码和构建验证通过, 真实麦克风顺序需现场复核 |
| 2026-06-11 播报中长唤醒词确认打断 | `python -m compileall apps/api/app` 和 `corepack pnpm --dir apps/web build` 通过, 真实麦克风打断成功率和误打断率需现场复核 |

## 安全测试

| 项目 | 结果 |
| --- | --- |
| 前端不暴露 Dora / ASR / TTS Key | 通过设计和配置约束 |
| Ops 导出密钥模式扫描 | 通过 |
| 非法 `action_id` 拒绝执行 | 已验证 |
| 模型生成代码不执行 | 架构约束已落实 |
| `export-logs.ps1` 默认不导出 Docker 原生日志 | 已落实 |

## V1.0 文档测试

本轮交付包应至少包含:

- `01_ACCEPTANCE_REPORT.md`
- `02_DEPLOYMENT_PLAN.md`
- `03_USER_MANUAL.md`
- `04_OPERATIONS_MANUAL.md`
- `05_CONFIGURATION_MANUAL.md`
- `06_TEST_REPORT.md`
- `07_CUSTOMER_HANDOFF_CHECKLIST.md`

并同步:

- `docs/00_INDEX.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

本轮实际验证:

- 交付包文件完整性检查通过, 8 个 Markdown 文件均存在。
- `git diff --check` 通过。
- `scripts/check-poc.ps1 -SkipExternal -Json` 通过; 因本轮未启动 API / Web, 端口空闲和 API / Web 未连接显示为 warning, 外部依赖探测按参数跳过。

## 现场待确认项

| 项目 | 原因 |
| --- | --- |
| 客户现场 Dora 连通性 | 当前日志包中 Dora 探测超时 |
| 客户现场 RAGFlow MCP 连通性 | 当前日志包中 RAGFlow 探测失败 |
| 是否关闭 `DEMO_STABLE_MODE` 做真实依赖验收 | 演示稳态不能替代真实验收 |
| FVS 正式域名和 iframe 策略 | 本机已通过同源代理, 正式环境需确认 |
| 麦克风权限、现场噪声、自动播放策略 | 浏览器和设备相关 |
| 问数真实数据源和指标口径 | 当前为脱敏 Excel 样例 |
| Ops 看板访问控制 | 当前按本地 POC 内网使用 |

## 测试结论

V1.0 POC 已具备客户验收交付条件。固定演示链路、脚本化 smoke、日志导出和运维看板已经形成可重复验证流程。正式签收时应在客户现场补充真实依赖连通、麦克风 / 播放、FVS 嵌入、截图和签字确认。
