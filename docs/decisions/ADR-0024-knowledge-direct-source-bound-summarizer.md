# ADR-0024: KnowledgeDirect 来源约束回答边界

## Status

Accepted

## Date

2026-06-16

## Context

阶段 3 目标是在不破坏既有 Dora -> RAGFlow MCP 知识库路径的前提下, 新增 Gateway 本地 KnowledgeDirectAdapter。

必须满足:

- RAGFlow 只检索 chunks 和 metadata。
- 回答必须 `require_sources=true`。
- 无检索结果或依据不足时 fallback, 不编造。
- 不让 LLM 生成或执行 SQL、Python、JavaScript 或 shell。
- 不实现可写 Prompt、可写配置或控屏授权响应增强。
- 不暴露 API Key 到前端。

## Decision

- 新增 `KnowledgeDirectProvider` / `RagflowKnowledgeRetriever` / `SourceBoundSummarizer`。
- 默认 `KNOWLEDGE_MODE=dora`, 保持既有 Dora -> RAGFlow MCP -> Dora 最终回答路径不退化。
- `KNOWLEDGE_MODE=local_ragflow_llm` 时, Gateway 本地调用 RAGFlow 检索 chunks/metadata, 再由后端 summarizer 输出标准 `answer`。
- `KNOWLEDGE_MODE=auto` 时, 本地直连配置缺失或检索异常回到 Dora; 本地检索无依据时仍按 `no_evidence_policy=fallback` 返回兜底, 避免转交 Dora 后编造。
- 当前 summarizer 采用后端受控 `source_bound_extractive` 实现, 只从检索 chunk 中抽取和组织来源句子, 不调用外部 LLM。
- `display.sources`、`display.source_summary` 和 `display.audit` 必须随 KnowledgeDirect answer 返回。
- 外部 LLM summarizer 留作后续能力; 若实现, 只能通过后端受控 Provider 调用, API Key 仍只在后端环境变量中使用。

## Consequences

优点:

- 阶段 3 可在无新增 LLM Key 的情况下完成来源约束回答闭环。
- 现有 Dora 知识库路径默认不变。
- 无依据 fallback 由后端强制执行, 避免模型编造。
- 本地 summarizer 不会输出控屏动作或可执行代码。

约束:

- 当前 extractive summarizer 的表达能力弱于真正 LLM 总结, 更适合 POC 阶段验证来源边界。
- RAGFlow API 直连需要后端配置 `RAGFLOW_API_KEY` 和 dataset; 不写入 YAML, 不返回前端。
- MCP 直连仅作为检索 transport 边界保留, 真实联调仍需按 RAGFlow MCP server 协议验证。
- 可写 Prompt、配置 validate/test/reload/audit 和控屏授权 action 响应增强仍必须留到后续阶段。
