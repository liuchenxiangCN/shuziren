# ADR-0014: 只读脱敏运维监控和日志看板

## Status

Accepted

## Date

2026-06-11

## Context

V0.8 第三阶段要求新增运维监控和日志看板, 覆盖依赖状态、最近会话、错误列表、耗时指标和日志导出。当前项目已有 SQLite `session_logs` 表, 能记录 `/api/chat`、`/api/chat/stream` 和 `/api/screen/execute` 的响应、错误和总耗时。

运维看板面向本地 POC 和现场排障, 但不能成为新的敏感信息出口。尤其不能展示 API Key、完整密钥、供应商原始响应、底层堆栈或未脱敏客户数据。

## Decision

- 新增只读 Ops API:
  - `GET /api/ops/health`
  - `GET /api/ops/dependencies`
  - `GET /api/ops/sessions`
  - `GET /api/ops/session/{session_id}`
  - `GET /api/ops/errors`
  - `GET /api/ops/metrics`
  - `GET /api/ops/export`
- 运维数据优先复用现有 SQLite `session_logs` 表, 不引入新的持久化服务。
- 会话摘要、错误消息和导出内容做长度截断, 并对常见 Key / Token / Bearer / `sk-*` / `ak-*` 模式做脱敏。
- 依赖状态只做轻量检查:
  - SQLite 和动作白名单做本地读取检查。
  - Dora / RAGFlow 只调用健康或列表类只读接口。
  - ASR / TTS 真实模式只检查配置就绪, 不主动上传音频或触发合成。
  - FVS 由前端 iframe 实际承载; 后端只报告 Mock / URL / 相对代理配置状态。
- 前端不新增独立路由, 在现有主页面提供“演示 / 运维”视图切换; 运维视图展示依赖状态、最近会话、错误列表、耗时指标并支持导出 Markdown 摘要。

## Consequences

优点:

- V0.8 即可给实施人员一个本地可用的排障入口。
- 不增加新数据库和复杂权限体系, 降低本地 POC 维护成本。
- 不触发模型调用、ASR 上传或 TTS 合成, 避免运维页本身带来额外费用和副作用。
- API Key 仍只保留在后端 `.env` / 环境变量中, 不进入前端和导出文件。

约束:

- 当前耗时指标主要是 Gateway 记录的总耗时, 不是 ASR / Dora / RAGFlow / TTS 的全链路细分瀑布图。
- 当前看板未加入登录鉴权, 仍按本地 POC 内网使用前提控制访问范围。
- V0.9 的预检脚本、一键启停和更完整日志包仍需在后续阶段实现。
