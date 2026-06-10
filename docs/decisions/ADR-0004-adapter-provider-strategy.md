# ADR-0004 Adapter Provider Strategy

## Status

Accepted

## Context

项目需要接入 Dora、ASR、TTS、RAGFlow、FVS, 且不同客户可能选择不同供应商或不同部署方式。若核心业务代码直接耦合供应商 API, 后续替换成本高。

## Decision

所有外部服务通过 Adapter / Provider 层接入:

- `DoraClient`
- `AsrProvider`
- `TtsProvider`
- `FvsActionAdapter`
- `RagflowMcpConfig`
- `MockProvider`

通过 `.env` 和 YAML 选择供应商和模式。

## Consequences

优点:

- 供应商可替换。
- Mock 和真实服务并存。
- 易于客户化交付。

代价:

- 初始代码结构比直接调用略复杂。
- 需要维护统一数据契约。

