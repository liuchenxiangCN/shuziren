# ADR-0012: 客户配置覆盖层与问数模式路由

## Status

Accepted

## Date

2026-06-10

## Context

V0.7 已实现 Gateway 本地 Excel 问数 Adapter, 能稳定回答 11 个脱敏党建指标问题。进入 V0.8 后, 用户要求先完成客户私有配置目录, 并实现 `ASK_METRICS_MODE=dora|excel|auto`, 让 Dora 承接通用问数, 同时保留 Excel fallback。

此前 Docker Compose 会把根目录配置路径直接写入容器环境变量, 导致后续客户目录很难覆盖默认配置。客户差异也分散在 `.env.example`、根配置和文档中, 不利于多客户复用。

## Decision

- 新增 `CUSTOMER_ID` 和 `CUSTOMER_CONFIG_DIR`。
- 新增客户私有配置目录 `config/customers/zt-securities/`, 存放非敏感 YAML:
  - `runtime.yaml`
  - `screen-actions.yaml`
  - `ask-metrics.yaml`
  - `demo-cases.yaml`
  - `wake-words.yaml`
  - `dora.yaml`
  - `ragflow.yaml`
  - `voice.yaml`
  - `fvs.yaml`
- 后端启动时按以下优先级解析配置:
  1. 代码内默认值和根目录 `config/*.yaml`。
  2. `config/customers/<customer-id>/` 客户覆盖层。
  3. `.env` 或容器环境变量中的显式运行时覆盖。
- 旧 `.env` 中等于根目录默认路径的 `ACTION_WHITELIST_PATH`、`DEMO_CASES_PATH`、`WAKE_WORDS_PATH`、`ASK_METRICS_CONFIG_PATH` 和 `ASK_METRICS_DATA_DIR` 不再阻止客户目录覆盖; 真正自定义路径仍优先。
- `ASK_METRICS_MODE` 路由规则:
  - `excel`: 先由 Gateway Excel Adapter 匹配问数, 命中后直接返回 `answer`; 未命中继续 Dora / Mock Dora。
  - `dora`: Excel Adapter 不抢占, 问题直接进入 Dora / Mock Dora 链路。
  - `auto`: 优先 Dora / Mock Dora; 若返回 `fallback` 或 Dora 请求失败, 再尝试 Excel Adapter。
- `/api/chat/stream` 保持既有 SSE 事件兼容, 问数 fallback 仍输出 `metadata -> dora_delta -> answer`。

## Consequences

优点:

- 客户动作、演示问题、唤醒词、问数映射、Dora Agent、RAGFlow 地址、语音参数和 FVS 地址都有客户私有样例。
- `ASK_METRICS_MODE=excel` 保留 V0.7 稳定演示能力。
- `ASK_METRICS_MODE=dora` 可让 Dora 承接通用问数, 不被固定 Excel 模板抢答。
- `ASK_METRICS_MODE=auto` 在 Dora 不可用或兜底时可回退 Excel。

约束:

- API Key、Token、密码仍只能放 `.env` 或部署环境变量, 不写入客户 YAML。
- Gateway 仍不执行 Dora 或模型生成的 SQL、Python、JavaScript 或 shell。
- 大屏控制仍必须使用 `action_id` + Gateway 白名单校验。
- V0.8 第一阶段不实现 TTS 字节级真流式和运维看板, 这两项继续留给后续 goal。
