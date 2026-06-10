# ADR-0002 Mock-First Strategy

## Status

Accepted

## Context

真实 Dora、ASR、TTS、RAGFlow、FVS 都依赖外部环境、账号、网络和客户现场条件。如果一开始就强依赖真实系统, 开发会被外部条件阻塞。

## Decision

先实现 V0.1 Mock 闭环:

```text
文本输入 -> Mock Dora -> Mock FVS -> 前端展示 -> 会话日志
```

之后逐个替换真实能力:

```text
Dora -> TTS -> ASR -> 语义唤醒 -> RAGFlow MCP -> FVS 真实控制
```

所有外部服务必须保留 Mock 开关。

## Consequences

优点:

- 主链路可持续开发。
- 客户环境未准备好时仍可演示。
- 便于自动化测试。
- 后续联调可以逐个定位问题。

代价:

- Mock 效果不代表真实模型效果。
- 后续需要额外做真实服务联调和调优。

