# ADR-0006 FVS Web Frame Communication

## Status

Superseded by [ADR-0007](ADR-0007-fvs-iframe-host.md)

## Context

V0.6 需要把数字人控制链路接到真实 FVS 大屏。早期方案同时保留两种方向:

- 数字人外壳 iframe 嵌入 FVS。
- FVS 主模板网页框嵌入数字人页面。

用户在 V0.6 开始时确认先尝试第二种方向, 并提供帆软 FVS 网页框通信文档。

## Decision

V0.6 优先采用 FVS 主模板网页框嵌入数字人页面:

```text
FVS 主模板
-> 网页框加载数字人前端
-> Gateway 校验 action_id
-> 数字人网页框 window.parent.postMessage(...)
-> FVS 主模板 duchamp.addPostMessageListener(...)
-> FVS 按 action_id 固定映射真实控制 API
```

数字人前端新增 `parent` / `web-frame` 模式。该模式下, 只有 `/api/screen/execute` 返回 `success=true` 后才向父 FVS 页面发送 `FVS_ACTION` 消息。

## Consequences

优点:

- 不依赖 FVS 被外部 iframe 嵌入。
- 更贴近 FVS 大屏作为主画布的交付方式。
- 网页框通信使用帆软官方接口思路, 便于现场交付团队理解。
- 仍保留 Mock FVS 和备用 iframe 模式。

约束:

- FVS 主模板必须配置 `duchamp.onlyCommunicateWithOrigins`。
- FVS 主模板必须预埋 `duchamp.addPostMessageListener`。
- FVS 侧也必须按 `action_id` 做固定白名单映射。
- 不允许根据 `functionName` 拼接或动态执行 JavaScript。
