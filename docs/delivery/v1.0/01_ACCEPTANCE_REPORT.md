# V1.0 POC 验收报告

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 项目名称 | 中天证券党建大屏对话数字人本地 POC |
| 版本 | V1.0 POC 验收交付版 |
| 报告日期 | 2026-06-11 |
| 部署形态 | Windows + Docker Desktop + 本项目 Docker Compose + 独立 RAGFlow Docker Compose |
| 客户配置 | `CUSTOMER_ID=zt-securities`, `CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities` |
| 运维入口 | `http://localhost:18000/ops` |
| 主演示入口 | `http://localhost:18000` |

## 验收范围

本次验收交付包覆盖以下 POC 能力:

- 语音唤醒、同句指令和连续追问。
- ASR 识别、Dora Agent 对话、RAGFlow 知识库问答。
- 本地 Excel 脱敏问数演示和 `ASK_METRICS_MODE=excel|dora|auto`。
- TTS 字节级真流式、分段 TTS fallback、完整 TTS fallback。
- FVS iframe host 主画布、`page_number=1/2/3/4` 四页切换。
- `action_id` + 后端白名单的大屏控制安全链路。
- `/ops` 运维看板、脱敏 Ops API、日志包导出。
- 预检、启停、演示 smoke 和演示稳态模式。

## 验收结果

| 编号 | 验收项 | 结果 | 证据 |
| --- | --- | --- | --- |
| A-001 | API / Web 可通过 Docker Compose 启动 | 通过 | `scripts/start-poc.ps1 -Build -DemoStable`, `GET /api/health` 返回 `status=ok` |
| A-002 | Dora + RAGFlow 知识库问答 | 通过 | V0.5 已验证张书记调研、入党流程、党员学习制度、党支部组织建设规范 |
| A-003 | Excel 问数演示 | 通过 | 11 个问数 smoke 通过, 数据来自 `docs/demo_data/ask_metrics/` |
| A-004 | TTS 真流式 | 通过 | `POST /api/tts/stream` 返回 `metadata -> audio_chunk* -> end`, 首个 PCM chunk 约 567ms |
| A-005 | FVS 四页切换 | 通过 | V0.6 人工验收: `总览=1`, `成品库存=2`, `生产管理=3`, `设备分析=4` |
| A-006 | 运维看板和日志导出 | 通过 | `/api/ops/*` smoke 通过, `scripts/export-logs.ps1 -Zip` 生成日志包 |
| A-007 | 演示 smoke | 通过 | `logs/smoke/smoke-demo-20260611-011803.md`, 5 条固定演示题全部 `True` |
| A-008 | 安全边界 | 通过 | 前端不暴露 Key, Ops 导出密钥模式扫描未命中, 控屏只走白名单 `action_id` |
| A-009 | 真实客户现场网络、麦克风、播放权限 | 待现场确认 | 需客户验收当天复核 |
| A-010 | 现场截图和客户签字 | 待现场补齐 | 本报告预留截图和签收附件位 |

## 复演记录

### 演示 Smoke

最近一次脚本复演:

```text
scripts/smoke-demo.ps1 -ExecuteScreenActions
```

记录文件:

```text
logs/smoke/smoke-demo-20260611-011803.md
```

复演结果摘要:

| 用例 | 输入 | 类型 | 耗时 |
| --- | --- | --- | ---: |
| ZT-L-001 | 我是张书记 | answer | 17587 ms |
| ZT-K-001 | 入党流程是什么？ | answer | 13092 ms |
| ZT-D-001 | 当前党员学习完成率是多少？ | answer | 41 ms |
| ZT-S-001 | 请切换到成品库存页面 | screen_control | 4376 ms |
| ZT-S-002 | 返回总览 | screen_control | 5063 ms |

### 运维日志包

最近一次日志包:

```text
logs/exports/zt-poc-logs-20260611-011813.zip
```

日志包包含:

- `ops-export.md`
- `ops-health.json`
- `ops-dependencies.json`
- `ops-sessions.json`
- `ops-errors.json`
- `ops-metrics.json`
- `demo-config.json`
- `docker-compose-ps.json`

当时 Ops 依赖聚合状态为 `error`, 主要原因:

- Dora 探测超时。
- RAGFlow 探测失败。

同时以下依赖正常:

- SQLite 会话日志。
- 大屏动作白名单。
- 真实 ASR 配置。
- 真实 TTS 配置。
- Mock FVS。

该结果说明: 固定演示 smoke 可通过, 但真实 Dora / RAGFlow 依赖仍需在客户现场按正式网络重新确认。

## 耗时记录

以下为开发和验收准备阶段的抽样耗时, 用于 POC 验收参考, 不作为生产 SLA:

| 链路 | 抽样结果 |
| --- | --- |
| Dora + RAGFlow 知识库流式问答 | 首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s |
| TTS 字节级真流式 | 首个 PCM chunk 约 567ms, 单次抽样 `end.duration_ms=3387`, 共 33 个 chunk |
| Excel 问数 | 脚本 smoke 中 `当前党员学习完成率是多少？` 约 41ms |
| 控屏动作 | 脚本 smoke 中 `成品库存` 约 4376ms, `总览` 约 5063ms |
| Ops 聚合指标 | `ops-metrics.json` 记录 `p95_latency_ms=15737`, `max_latency_ms=65187` |

## 截图附件位

现场验收时建议补齐以下截图, 并以附件形式随本报告归档:

| 附件编号 | 截图内容 | 状态 |
| --- | --- | --- |
| S-001 | `http://localhost:18000` 主页面启动成功 | 待现场补齐 |
| S-002 | FVS iframe 主画布显示, 右下角仅小型语音 icon | 待现场补齐 |
| S-003 | 唤醒词命中后播报“您好。”并进入正式录音 / 指令处理 | 待现场补齐 |
| S-004 | 问数回答显示 `87.5%` 和 Excel 数据来源 | 待现场补齐 |
| S-005 | 语音或文本指令切换到成品库存页面 | 待现场补齐 |
| S-006 | `/ops` 运维看板依赖状态和会话列表 | 待现场补齐 |
| S-007 | `scripts/export-logs.ps1 -Zip` 生成日志包 | 待现场补齐 |

## 客户确认项

| 确认项 | 结论 | 签字 / 日期 |
| --- | --- | --- |
| Windows + Docker Desktop 本地环境可启动 | 待确认 |  |
| 演示是否开启 `DEMO_STABLE_MODE` | 待确认 |  |
| Dora 真实依赖可访问 | 待确认 |  |
| RAGFlow MCP 可被 Dora 访问 | 待确认 |  |
| ASR / TTS 真实 Key 和供应商服务可用 | 待确认 |  |
| FVS iframe 嵌入和四页切换可用 | 待确认 |  |
| 客户演示环境允许浏览器麦克风和自动播放 | 待确认 |  |
| 问数指标口径和真实数据源后续方案 | 待确认 |  |
| 运维看板访问控制策略 | 待确认 |  |
| 当前 POC 作为验收交付包签收 | 待确认 |  |

## 验收结论

V1.0 POC 已形成可复演、可部署、可运维、可移交的验收交付包。基于当前开发验证和人工验收记录, 本地 POC 能完成党建大屏语音交互主链路和固定演示问题集复演。

正式客户签收前, 仍需在客户现场补齐真实网络、麦克风、播放权限、FVS 嵌入策略、Dora / RAGFlow 连通性、截图附件和签字确认。
