# ADR-0010: V0.7 本地 Excel 问数 Adapter

## Status

Accepted

## Date

2026-06-10

## Context

V0.7 POC 稳定版需要覆盖“党建问数”。V0.5 已准备 `docs/demo_data/ask_metrics/` 下三份脱敏 Excel 测试数据, 但此前尚未实现真实查询链路。

可选方案包括 Dora 自带问数、Gateway 轻量 Excel 查询 Adapter、FineBI / FVS 数据源或临时 Mock。当前阶段目标是形成稳定本地 POC, 不再扩展新的外部系统能力, 且不能让模型凭空编造 Excel 查询结果。

## Decision

- V0.7 第一版问数由 Gateway 本地只读 Excel Adapter 承接。
- Adapter 读取 `docs/demo_data/ask_metrics/` 下三份 `.xlsx`, 不依赖额外 Python 包, 使用标准库解析 workbook 缓存值。
- `/api/chat` 和 `/api/chat/stream` 在调用 Mock Dora 或真实 Dora 前先匹配问数意图; 命中后直接返回 `answer`。
- 问数回答必须带 `display.source`, 并在 bullets 中标明数据来源工作簿 / sheet。
- 未命中问数意图时继续走原 Dora / Mock Dora 链路, 知识库问答和大屏控制不被问数 Adapter 抢占。
- Docker 镜像内复制 `docs/demo_data`, compose 运行时只读挂载 `./docs/demo_data:/app/docs/demo_data:ro`。

## Consequences

- POC 可以稳定回答 10+ 个固定问数问题, 且答案来自脱敏 Excel。
- 本地演示不依赖 Dora 问数、FineBI 数据集或 FVS 数据源, 降低现场不确定性。
- 当前不是通用自然语言 BI 引擎, 主要覆盖演示清单中的固定指标和相近问法。
- 后续若客户确认真实数据源, 可把 Adapter 替换为 FineBI / Dora 问数 / 数据库查询 Provider, 保持 `/api/chat` 响应契约不变。

## Guardrails

- Adapter 只读本地 Excel, 不写回客户数据。
- 不执行模型生成的 SQL、Python 或 JavaScript。
- 大屏控制仍只通过 `action_id` + Gateway 白名单。
- 客户真实问数口径确认前, 演示话术必须说明当前为脱敏样例数据。
