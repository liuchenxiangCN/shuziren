# ADR-0015: V0.9 Delivery Scripts And Demo Stable Mode

## Status

Accepted

## Date

2026-06-11

## Context

V0.8 已具备客户配置覆盖层、TTS 真流式、Ops API 和运维看板。V0.9 的目标不是新增真实外部系统能力, 而是把已有 POC 整理成现场可启动、可预检、可复演和可排障的形态。

现场演示常见风险包括 Docker 未启动、端口被占用、API / Web 未就绪、Dora / RAGFlow / FVS / ASR / TTS 配置缺失、FVS iframe 被浏览器策略拦截、麦克风权限失败, 以及日志导出流程依赖人工临场操作。

## Decision

- 新增 PowerShell 脚本:
  - `scripts/check-poc.ps1`: 预检 Docker、Compose、端口、配置、API、Web、Ops 依赖和 RAGFlow。
  - `scripts/start-poc.ps1`: 一键启动 API / Web, 可选 `-Build`、`-DemoStable`、`-WithRagflow`。
  - `scripts/stop-poc.ps1`: 一键停止 API / Web, 可选停止本机 RAGFlow。
  - `scripts/export-logs.ps1`: 基于只读脱敏 Ops API 导出现文件日志包。
  - `scripts/smoke-demo.ps1`: 用固定演示问题集做 API smoke, 可选执行白名单控屏动作。
- 新增 `DEMO_STABLE_MODE` 后端开关和 `VITE_DEMO_STABLE_MODE` 前端构建开关。
- 新增 `GET /api/demo/config`, 返回演示稳态、客户 ID、问数模式、Mock 开关和固定演示问题。
- `DEMO_STABLE_MODE=true` 时, Dora 请求失败会优先尝试本地 Excel 问数和 Mock Dora 演示兜底; 未命中时仍返回安全 fallback。
- Excel 问数数据缺失、Dora 流式异常、TTS 分段异常、FVS iframe 加载超时和麦克风权限失败均返回可理解提示, 不向前端暴露系统堆栈、API Key 或供应商原始敏感响应。
- 日志包默认只导出脱敏 Ops Markdown / JSON 和 Compose 状态; Docker 原生日志必须显式使用 `-IncludeDockerLogs`。

## Consequences

优点:

- 实施人员可以用脚本完成启动、预检、smoke 和日志导出。
- 演示稳态模式能降低 Dora 或外部依赖临时不可用对固定演示的影响。
- 现场日志导出流程复用 V0.8 的只读脱敏 Ops API, 不新增敏感信息出口。
- 预检和 smoke 使用固定问题和固定 API, 不执行模型生成 SQL、Python、JavaScript 或 shell。

约束:

- 演示稳态模式不能替代真实外部依赖验收; 正式验收仍需关闭或明确记录该模式。
- `scripts/start-poc.ps1 -WithRagflow` 只按当前本机路径 `D:\Project\ragflow\docker` 管理 RAGFlow, 其他环境需调整。
- Docker 原生日志可能包含运行时噪声或外部库信息, 因此不默认打包。
