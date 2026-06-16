# ADR-0025: Runtime Config Overrides and Audit

## Status

Accepted

## Date

2026-06-16

## Context

阶段 0A 到阶段 4 已完成通用默认入口、只读 effective config / schema、AskMetricsProvider、KnowledgeDirectAdapter、ScreenControlResolver 和 `/api/screen/execute` 授权 action 响应增强。下一步需要让现场人员在不修改根级 `config/`、不暴露密钥、不开放自由 SQL 的前提下调整非敏感配置。

`docker-compose.yml` 仍把 `config/` 作为只读默认配置挂载, 因此可写配置不能直接改默认 YAML 或客户 profile。阶段 5 还必须保留阶段 4 的控屏安全边界: action 写入只能形成后端白名单中的 `action_id` 映射, 前端真实执行仍必须来自 `/api/screen/execute` 本次返回的 `authorized_action`。

## Decision

- 新增运行时覆盖目录 `data/config-overrides/`。
- 只提交目录说明和 `.gitkeep`; `active.yaml`、`history/`、`audit.jsonl` 作为本地运行数据, 不进入 Git。
- 配置优先级为: 代码默认 / 根配置 -> 客户 profile -> `data/config-overrides/active.yaml` -> `.env` / 环境变量。
- 新增配置 API:
  - `GET /api/config/overrides`
  - `POST /api/config/validate`
  - `POST /api/config/test`
  - `PUT /api/config/overrides`
  - `POST /api/config/reload`
  - `GET /api/config/audit`
- 写接口采用最小访问边界: 如果配置 `CONFIG_ADMIN_TOKEN`, 必须通过 `X-Config-Admin-Token` 提交; 未配置 token 时仅允许 localhost / testserver origin 的本地 POC 写入。
- 允许保存的字段仅限非敏感展示字段、FVS 后端 effective 非敏感字段、`ASK_METRICS_MODE=excel|dora|auto`、知识库 mode 和受控检索数值参数、source-bound summarizer profile 标签、`demo_stable_mode`、以及 `gotoPage/pageNumber` 类 action 映射。
- action 覆盖保存前必须通过同一套 `ScreenActionService` 参数 allowlist 和 dry-run 校验。
- 显式禁止 API Key、Token、密码、DSN、Bearer、任意脚本、可执行代码、自由 SQL、数据库 Provider 真实查询配置、外部 LLM summarizer provider / model / key 和任意 FVS 函数写入。

## Consequences

优点:

- 默认模板和客户 profile 继续保持干净, 现场可写配置有独立可回滚覆盖层。
- 保存、dry-run、reload 和 audit 分离, 便于现场先验证再生效。
- action 可写范围受限在阶段 4 已建立的授权执行链路内。
- 密钥和 DSN 继续只由 `.env` / 部署环境变量管理。

限制:

- 当前配置页不是完整权限系统; 跨机器或正式环境必须配置 `CONFIG_ADMIN_TOKEN` 或在反向代理层加访问控制。
- Prompt 内容编辑、外部 LLM summarizer、Database Provider 真实查询和 SQL 配置仍未实现。
- 前端 URL 参数和 Vite build-time FVS runtime 仍可能覆盖浏览器实际执行效果, 配置页继续同时展示后端 effective 和前端 runtime。
